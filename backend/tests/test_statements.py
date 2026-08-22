"""What counts as a statement.

Both rules here were written from an observed failure, not from an argument.
A real run drew `nvidia/nemotron-3.5-content-safety:free` -- a classifier, not
an advocate -- and it answered:

    User Safety: unsafe
    Safety Categories: Unauthorized Advice

Three words. The row was stored `done`, its word count was recorded as if the
model had chosen to stop there, and all four such "statements" were put in
front of three judges. Nothing in the code noticed.
"""

from __future__ import annotations

import httpx
import pytest

from app.ai.openrouter import OpenRouterClient, OpenRouterError
from app.config import Settings
from app.tribunal.advocates import NotAStatement, speak
from app.tribunal.orchestrator import run_trial
from app.tribunal.roles import BY_SLOT
from conftest import BenchCaller, FakeCompletion, statement_text

CLASSIFIER_ANSWER = "User Safety: unsafe\nSafety Categories: Unauthorized Advice"


def caller_answering(text: str):
    async def call(model, prompt, on_chunk=None):
        return FakeCompletion(model=model, text=text)

    return call


# ── the floor ────────────────────────────────────────────────────────────


async def test_a_classifier_answer_is_not_a_statement(reference_charge):
    """The observed failure, as a test."""
    with pytest.raises(NotAStatement, match="which is not a statement"):
        await speak(
            BY_SLOT["advocate_against_1"],
            "nvidia/nemotron-3.5-content-safety:free",
            reference_charge,
            call=caller_answering(CLASSIFIER_ANSWER),
            target_words=300,
            min_words=60,
        )


async def test_the_failure_names_the_model_and_quotes_what_came_back(reference_charge):
    """Which slot failed on which model is the finding. So is what it said
    instead -- a refusal and a classification are different problems."""
    with pytest.raises(NotAStatement) as caught:
        await speak(
            BY_SLOT["advocate_for_1"],
            "some/classifier:free",
            reference_charge,
            call=caller_answering(CLASSIFIER_ANSWER),
            target_words=300,
            min_words=60,
        )

    assert "some/classifier:free" in str(caught.value)
    assert "User Safety" in str(caught.value)


async def test_a_non_statement_fails_the_whole_run(reference_charge, roster_different):
    """Not a shorter trial -- no trial. Four half-answers are not comparable
    to four arguments, and three judges must not rule on them."""
    trial = await run_trial(
        reference_charge,
        roster_different,
        call=BenchCaller({roster_different["advocate_for_2"]: CLASSIFIER_ANSWER}),
        target_words=300,
        min_statement_words=60,
    )

    assert trial.status == "failed"
    assert [f.slot for f in trial.failures] == ["advocate_for_2"]
    assert trial.rulings == []


async def test_a_real_statement_passes_the_floor(reference_charge):
    """The floor is a floor, not a length rule: nothing above it is touched,
    trimmed or judged for length."""
    long_enough = statement_text("A proper argument.", words=95)

    statement = await speak(
        BY_SLOT["advocate_against_2"],
        "test/model:free",
        reference_charge,
        call=caller_answering(long_enough),
        target_words=300,
        min_words=60,
    )

    assert statement.text == long_enough
    assert statement.words == len(long_enough.split())


async def test_nothing_is_truncated_above_the_floor(reference_charge):
    """A very long statement is recorded whole. The prompt names a target;
    it has never been a limit."""
    enormous = statement_text("A long argument.", words=1200)

    statement = await speak(
        BY_SLOT["advocate_for_1"],
        "test/model:free",
        reference_charge,
        call=caller_answering(enormous),
        target_words=300,
        min_words=60,
    )

    assert statement.text == enormous
    assert statement.words >= 1200


# ── cut off mid-argument ─────────────────────────────────────────────────


def responder(status: int, payload: dict) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, json=payload))


async def test_a_body_cut_off_at_the_token_limit_is_a_failed_call():
    """`finish_reason: length` means the model was still arguing. Storing that
    would put half a case in front of a judge and count its words as a choice."""
    transport = responder(
        200,
        {
            "choices": [
                {"message": {"content": "The countersignature rule was written for"},
                 "finish_reason": "length"}
            ],
            "usage": {"cost": 0.0},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(Settings(openrouter_api_key="k"), client=http)
        with pytest.raises(OpenRouterError, match="cut off at the token limit"):
            await client.complete("test/model:free", "prompt")


async def test_a_body_that_ended_because_it_was_finished_is_kept():
    transport = responder(
        200,
        {
            "choices": [{"message": {"content": "A complete argument."}, "finish_reason": "stop"}],
            "usage": {"cost": 0.0},
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        client = OpenRouterClient(Settings(openrouter_api_key="k"), client=http)
        answer = await client.complete("test/model:free", "prompt")

    assert answer.text == "A complete argument."
    assert answer.finish_reason == "stop"


async def test_room_to_finish_is_asked_for_on_every_call():
    """A provider default is silent and differs between providers, which would
    make statement length a measure of the gateway rather than of the model."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"cost": 0.0},
            },
        )

    settings = Settings(openrouter_api_key="k", max_response_tokens=2048)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://x") as h:
        await OpenRouterClient(settings, client=h).complete("test/model:free", "prompt")

    assert seen["max_tokens"] == 2048
    assert seen["temperature"] == settings.temperature


async def test_the_same_room_is_asked_for_whatever_the_model_is():
    """One value for all seven slots and both situations. A per-model figure
    would make word count a measure of the cap, and word count is a reported
    finding (criterion 18)."""
    asked: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        asked.append(json.loads(request.content)["max_tokens"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"cost": 0.0},
            },
        )

    settings = Settings(openrouter_api_key="k")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://x") as h:
        client = OpenRouterClient(settings, client=h)
        for model in ("a/one:free", "b/two:free", "c/three:free"):
            await client.complete(model, "prompt")

    assert len(set(asked)) == 1


# ── thinking that nobody reads ───────────────────────────────────────────


async def test_reasoning_is_capped_on_every_call():
    """Measured on real runs: 65% of every output token was hidden reasoning.
    One judgment generated 1712 tokens, 1485 of them thinking, for 168 visible
    words in 126 seconds -- and a model that spends its whole budget reasoning
    has none left for an answer, which is where the empty bodies came from.

    `effort` is what stops them being generated. `exclude` would only hide
    them and save nothing.
    """
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"cost": 0.0},
            },
        )

    settings = Settings(openrouter_api_key="k", reasoning_effort="none")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://x") as h:
        await OpenRouterClient(settings, client=h).complete("test/model:free", "prompt")

    assert seen["reasoning"] == {"effort": "none"}
    assert "exclude" not in seen["reasoning"], "exclude hides reasoning without saving anything"


async def test_the_same_effort_is_asked_of_every_model():
    """One value for all seven slots and both situations, like temperature and
    max_tokens. A per-model setting would make duration a measure of the
    setting rather than of the model."""
    asked: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        asked.append(json.loads(request.content)["reasoning"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"cost": 0.0},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://x") as h:
        client = OpenRouterClient(Settings(openrouter_api_key="k"), client=h)
        for model in ("a/one:free", "b/two:free", "c/three:free"):
            await client.complete(model, "prompt")

    assert len({repr(a) for a in asked}) == 1


async def test_the_token_counts_come_back_on_the_response():
    """They replaced cost on screen, so they have to survive the trip."""
    transport = responder(
        200,
        {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {
                "cost": 0.0,
                "completion_tokens": 866,
                "completion_tokens_details": {"reasoning_tokens": 447},
            },
        },
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        answer = await OpenRouterClient(Settings(openrouter_api_key="k"), client=http).complete(
            "test/model:free", "prompt"
        )

    assert answer.tokens == 866
    assert answer.thinking_tokens == 447
