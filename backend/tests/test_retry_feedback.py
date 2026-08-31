"""The retry is surfaced, not silent.

A call that failed and is being tried again reaches the interface as an event,
so a card can say why it is slower than its neighbours. This is feedback about
what happened -- it changes no failure rule: a call still fails after its
retries, and a failed call still fails the run.
"""

from __future__ import annotations

import httpx
import pytest

from app.ai.openrouter import OpenRouterClient, OpenRouterError
from app.config import Settings
from app.tribunal.orchestrator import run_trial
from app.tribunal.roles import ADVOCATE_SLOTS, JUDGE_SLOTS
from conftest import ScriptedCaller, ruling_json, statement_text


# ── the transport retry calls back ───────────────────────────────────────


async def test_a_transport_retry_fires_on_retry_then_the_call_succeeds():
    settings = Settings(openrouter_api_key="k", max_attempts=3)
    sent = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        if sent == 1:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "A statement."}}], "usage": {"cost": 0.0}},
        )

    seen: list[tuple[int, int, str]] = []

    async def on_retry(attempt: int, max_attempts: int, reason: str) -> None:
        seen.append((attempt, max_attempts, reason))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        answer = await client.complete("test/model:free", "prompt", on_retry=on_retry)

    assert answer.text == "A statement."
    assert len(seen) == 1
    assert seen[0][0] == 2 and seen[0][1] == 3


async def test_a_rate_limit_pause_also_fires_on_retry():
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
        if sent == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "slow down"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "A statement."}}], "usage": {"cost": 0.0}},
        )

    reasons: list[str] = []

    async def on_retry(attempt: int, max_attempts: int, reason: str) -> None:
        reasons.append(reason)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        await client.complete("test/model:free", "prompt", on_retry=on_retry)

    assert reasons and "rate limited" in reasons[0]


# ── the dev fault switches ───────────────────────────────────────────────


async def test_dev_fault_retry_once_makes_every_call_retry_exactly_once():
    settings = Settings(openrouter_api_key="k", max_attempts=3, dev_fault_retry_once=True)
    sent = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "A statement."}}], "usage": {"cost": 0.0}},
        )

    seen: list[int] = []

    async def on_retry(attempt: int, max_attempts: int, reason: str) -> None:
        seen.append(attempt)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)
        answer = await client.complete("test/model:free", "prompt", on_retry=on_retry)

    assert answer.text == "A statement."
    assert seen == [2], "failed attempt 1, retried into attempt 2, then the real call ran"
    assert sent == 1, "the injected fault never reached the transport"


async def test_dev_fault_fail_model_fails_only_the_named_model():
    settings = Settings(
        openrouter_api_key="k", max_attempts=2, dev_fault_fail_model="test/doomed:free"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fine"}}], "usage": {"cost": 0.0}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(settings, client=http)

        with pytest.raises(OpenRouterError, match="DEV_FAULT_FAIL_MODEL"):
            await client.complete("test/doomed:free", "prompt")

        ok = await client.complete("test/other:free", "prompt")
        assert ok.text == "fine"


# ── the event reaches the observer ──────────────────────────────────────


class _RetryWatcher:
    def __init__(self) -> None:
        self.retries: list[tuple[str, int, int, str]] = []

    async def call_started(self, slot, stage, model): ...
    async def call_progress(self, slot, text): ...
    async def call_retrying(self, slot, attempt, max_attempts, reason):
        self.retries.append((slot, attempt, max_attempts, reason))
    async def statement_done(self, statement): ...
    async def ruling_done(self, ruling): ...
    async def stage_failed(self, failures): ...


class _RetryingCaller(ScriptedCaller):
    """Answers normally, but the first time a given model is asked it first
    reports a retry -- standing in for `openrouter.complete`'s own retry loop,
    which the scripted caller does not have."""

    def __init__(self, answers: dict[str, object]) -> None:
        super().__init__(answers)
        self._retried: set[str] = set()

    async def __call__(self, model, prompt, on_chunk=None, on_retry=None):
        if on_retry is not None and model not in self._retried:
            self._retried.add(model)
            await on_retry(2, 3, "the model did not answer the first time")
        return await super().__call__(model, prompt, on_chunk=on_chunk, on_retry=on_retry)


def _full_script(roster):
    answers = {roster[s]: statement_text(f"Statement from {s}.") for s in ADVOCATE_SLOTS}
    for s in JUDGE_SLOTS:
        answers[roster[s]] = ruling_json()
    return answers


async def test_a_retry_reaches_the_observer_and_the_run_still_finishes(
    reference_charge, roster_different
):
    watcher = _RetryWatcher()
    caller = _RetryingCaller(_full_script(roster_different))

    trial = await run_trial(
        reference_charge, roster_different, call=caller, target_words=300, observer=watcher
    )

    assert trial.status == "finished"
    # One retry per seat, all seven seats.
    assert {slot for slot, *_ in watcher.retries} == set(ADVOCATE_SLOTS) | set(JUDGE_SLOTS)


async def test_a_judge_format_retry_is_reported_as_a_retry(
    reference_charge, roster_different, broken
):
    from conftest import content_of

    prose = content_of(broken("judge_prose"))
    answers = _full_script(roster_different)
    answers[roster_different["judge_2"]] = [prose, ruling_json()]

    watcher = _RetryWatcher()
    caller = ScriptedCaller(answers)

    trial = await run_trial(
        reference_charge, roster_different, call=caller, target_words=300, observer=watcher
    )

    assert trial.status == "finished"
    judge_retries = [r for r in watcher.retries if r[0] == "judge_2"]
    assert judge_retries and "required form" in judge_retries[0][3]
