"""How fast the calls go out, and what a rate limit means.

Pacing is not method. What matters in this file is that slowing the calls down
changes *nothing* about what is sent, changes it identically in both
situations, and keeps a rate limit from being recorded as a model's failure.
"""

from __future__ import annotations

import asyncio

import pytest

from app.tribunal.orchestrator import pacing_gate, run_trial
from app.tribunal.roles import ADVOCATE_SLOTS, ALL_SLOTS, JUDGE_SLOTS
from conftest import FakeCompletion, ScriptedCaller, ruling_json, statement_text


class Watcher:
    """Records how many calls are in flight at any moment."""

    def __init__(self, inner):
        self.inner = inner
        self.in_flight = 0
        self.peak = 0
        self.order: list[str] = []

    async def __call__(self, model, prompt, on_chunk=None):
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        self.order.append(model)
        try:
            # Yield, so anything else that could overlap would.
            await asyncio.sleep(0)
            return await self.inner(model, prompt, on_chunk=on_chunk)
        finally:
            self.in_flight -= 1


def full_script(roster):
    answers = {roster[slot]: statement_text(f"Statement from {slot}.") for slot in ADVOCATE_SLOTS}
    for slot in JUDGE_SLOTS:
        answers[roster[slot]] = ruling_json()
    return answers


async def test_one_at_a_time_means_one_at_a_time(reference_charge, roster_different):
    watcher = Watcher(ScriptedCaller(full_script(roster_different)))

    trial = await run_trial(
        reference_charge, roster_different, call=watcher, target_words=300, max_concurrent=1
    )

    assert trial.status == "finished"
    assert watcher.peak == 1, f"{watcher.peak} calls were in flight at once"


async def test_the_calls_go_out_in_slot_order(reference_charge, roster_different):
    """The gate is first-come-first-served, so a paced run is also an ordered
    one -- the room fills left to right, not by whoever answers first."""
    watcher = Watcher(ScriptedCaller(full_script(roster_different)))

    await run_trial(
        reference_charge, roster_different, call=watcher, target_words=300, max_concurrent=1
    )

    assert watcher.order == [roster_different[slot] for slot in ALL_SLOTS]


async def test_raising_the_limit_lets_calls_overlap(reference_charge, roster_different):
    """The setting does something. A pacing knob that paced nothing would be
    the kind of widget that always shows the same value."""
    watcher = Watcher(ScriptedCaller(full_script(roster_different)))

    await run_trial(
        reference_charge, roster_different, call=watcher, target_words=300, max_concurrent=4
    )

    assert watcher.peak > 1


async def test_pacing_changes_nothing_that_is_sent(reference_charge, roster_different):
    """The whole claim of this file, stated as an assertion: the prompts of a
    sequential run and a parallel one are the same prompts."""
    sequential = ScriptedCaller(full_script(roster_different))
    parallel = ScriptedCaller(full_script(roster_different))

    await run_trial(
        reference_charge, roster_different, call=sequential, target_words=300, max_concurrent=1
    )
    await run_trial(
        reference_charge, roster_different, call=parallel, target_words=300, max_concurrent=7
    )

    assert sorted(sequential.prompts) == sorted(parallel.prompts)


async def test_the_stage_boundary_survives_pacing(reference_charge, roster_different):
    """Sequential or not, no judge is called before all four statements exist."""
    watcher = Watcher(ScriptedCaller(full_script(roster_different)))

    await run_trial(
        reference_charge, roster_different, call=watcher, target_words=300, max_concurrent=1
    )

    judges = [roster_different[slot] for slot in JUDGE_SLOTS]
    first_judge = min(watcher.order.index(model) for model in judges)
    advocates = [roster_different[slot] for slot in ADVOCATE_SLOTS]
    assert all(watcher.order.index(model) < first_judge for model in advocates)


async def test_only_the_call_in_flight_is_announced_live(reference_charge, roster_different):
    """Written from what a real run showed: all four advocate cards pulsing
    "reasoning..." while one model worked and three waited their turn.

    The stage used to announce every slot as it opened. A slot goes live when
    its own call goes out, so the page shows the one participant that is
    actually working.
    """
    live: list[str] = []
    peak = 0

    class Watch:
        async def call_started(self, slot, stage, model):
            nonlocal peak
            live.append(slot)
            peak = max(peak, len(live))

        async def call_progress(self, slot, text): ...

        async def statement_done(self, statement):
            live.remove(statement.slot)

        async def ruling_done(self, ruling):
            live.remove(ruling.slot)

        async def stage_failed(self, failures): ...

    trial = await run_trial(
        reference_charge,
        roster_different,
        call=ScriptedCaller(full_script(roster_different)),
        target_words=300,
        observer=Watch(),
        max_concurrent=1,
    )

    assert trial.status == "finished"
    assert peak == 1, f"{peak} participants were announced live at once"


async def test_a_slot_is_announced_in_the_order_it_is_called(
    reference_charge, roster_different
):
    announced: list[str] = []

    class Watch:
        async def call_started(self, slot, stage, model):
            announced.append(slot)

        async def call_progress(self, slot, text): ...
        async def statement_done(self, statement): ...
        async def ruling_done(self, ruling): ...
        async def stage_failed(self, failures): ...

    await run_trial(
        reference_charge,
        roster_different,
        call=ScriptedCaller(full_script(roster_different)),
        target_words=300,
        observer=Watch(),
        max_concurrent=1,
    )

    assert announced == list(ALL_SLOTS)


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_is_refused(limit):
    with pytest.raises(ValueError, match="at least 1"):
        pacing_gate(limit)


# ── a rate limit is not a failure ────────────────────────────────────────


async def test_the_gate_releases_when_a_call_fails(reference_charge, roster_different):
    """A failing call must not hold the gate shut behind it, or one bad slot
    would stall the run instead of failing it."""
    answers = full_script(roster_different)
    answers[roster_different["advocate_against_1"]] = TimeoutError("never answered")

    trial = await run_trial(
        reference_charge,
        roster_different,
        call=ScriptedCaller(answers),
        target_words=300,
        max_concurrent=1,
    )

    assert trial.status == "failed"
    # The other three were still attempted; the gate did not deadlock.
    assert [f.slot for f in trial.failures] == ["advocate_against_1"]


async def test_a_rate_limit_does_not_spend_the_one_retry(monkeypatch):
    """429 means the model never saw the prompt. Waiting and asking again is
    the same question asked once -- so a call may be told to wait several
    times and still have its single retry intact for a real failure."""
    import httpx

    from app.ai.openrouter import OpenRouterClient
    from app.config import Settings

    settings = Settings(
        openrouter_api_key="k",
        max_attempts=2,
        rate_limit_pause_seconds=0.0,
        rate_limit_max_wait_seconds=10.0,
    )

    sent = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        if sent <= 3:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "slow down"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "A statement."}}],
                "usage": {"cost": 0.0},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        answer = await client.complete("test/model:free", "prompt")

    assert answer.text == "A statement."
    assert sent == 4, "three 429s then the answer, none of them counted as an attempt"


async def test_waiting_too_long_fails_the_call(monkeypatch):
    """The budget is what bounds it. Past that a rate limit fails like anything
    else -- there is no waiting forever for a nicer outcome."""
    import httpx

    from app.ai.openrouter import OpenRouterClient, OpenRouterError
    from app.config import Settings

    settings = Settings(
        openrouter_api_key="k",
        rate_limit_pause_seconds=0.0,
        rate_limit_max_wait_seconds=0.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "5"}, json={"error": "no"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        with pytest.raises(OpenRouterError, match="rate limited"):
            await client.complete("test/model:free", "prompt")


async def test_a_real_failure_still_gets_exactly_one_retry():
    """The rule that pays for everything else: demand twice, then fail."""
    import httpx

    from app.ai.openrouter import OpenRouterClient, OpenRouterError
    from app.config import Settings

    settings = Settings(openrouter_api_key="k", max_attempts=2)
    sent = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        with pytest.raises(OpenRouterError):
            await client.complete("test/model:free", "prompt")

    assert sent == 2


async def test_a_streamed_error_reports_the_gateways_message_not_an_httpx_crash():
    """Observed failure: a streamed call that errors before any chunk arrives
    raised `Attempted to access streaming response content, without having
    called read()` instead of the gateway's actual message -- because the
    error body was never read before `raise_for_status`."""
    import httpx

    from app.ai.openrouter import OpenRouterClient, OpenRouterError
    from app.config import Settings

    settings = Settings(openrouter_api_key="k", max_attempts=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "Reasoning is mandatory for this endpoint"}}
        )

    async def on_chunk(text: str) -> None:
        pass

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        with pytest.raises(OpenRouterError, match="Reasoning is mandatory"):
            await client.complete("test/model:free", "prompt", on_chunk=on_chunk)


def test_fake_completion_is_structurally_a_completion():
    """Guards the seam the whole suite rests on."""
    from app.tribunal.roles import Completion

    assert isinstance(FakeCompletion(model="m", text="a b c"), Completion)
