"""Criterion 6, and the rule that a verdict is never inferred.

The broken fixtures are the point of this file: each one is a way a free model
actually misbehaves, and each one must fail rather than be rescued.
"""

from __future__ import annotations

import pytest

from app.tribunal.judges import RulingFormatError, parse_ruling, rule
from app.tribunal.roles import BY_SLOT
from conftest import ScriptedCaller, content_of, ruling_json


# ── what the required form is ────────────────────────────────────────────


def test_the_required_form_is_read():
    verdict, confidence, reasons = parse_ruling(ruling_json("not_justified", 0.42, reasons=3))

    assert verdict == "not_justified"
    assert confidence == 0.42
    assert len(reasons) == 3


def test_a_fenced_object_is_still_the_object():
    """A code fence is a wrapper, not a different answer. It is the only
    leniency there is."""
    fenced = "```json\n" + ruling_json() + "\n```"

    assert parse_ruling(fenced)[0] == "justified"


def test_at_least_two_reasons_are_required():
    """Criterion 6."""
    with pytest.raises(RulingFormatError, match="at least 2 reasons"):
        parse_ruling(ruling_json(reasons=1))


@pytest.mark.parametrize("confidence", [-0.1, 1.4, 87])
def test_confidence_outside_the_range_is_a_format_failure(confidence):
    with pytest.raises(RulingFormatError, match="confidence"):
        parse_ruling(ruling_json(confidence=confidence))


@pytest.mark.parametrize("verdict", ["Justified", "guilty", "not justified", "", None])
def test_only_the_two_verdicts_are_accepted(verdict):
    import json

    body = json.dumps({"verdict": verdict, "confidence": 0.5, "reasons": ["a", "b"]})
    with pytest.raises(RulingFormatError, match="verdict"):
        parse_ruling(body)


def test_a_verdict_is_never_read_out_of_prose(broken):
    """`judge_prose.json` says "I find the act was justified" in plain words,
    and states a confidence and three reasons in a sentence. A parser that
    rescued it would be the single worst change this project could make."""
    prose = content_of(broken("judge_prose"))
    assert "justified" in prose  # the words really are there

    with pytest.raises(RulingFormatError):
        parse_ruling(prose)


def test_a_missing_verdict_is_not_defaulted(broken):
    with pytest.raises(RulingFormatError, match="verdict"):
        parse_ruling(content_of(broken("judge_missing_verdict")))


def test_one_reason_is_not_two(broken):
    with pytest.raises(RulingFormatError, match="at least 2 reasons"):
        parse_ruling(content_of(broken("judge_one_reason")))


def test_a_confidence_out_of_range_is_refused(broken):
    with pytest.raises(RulingFormatError, match="confidence"):
        parse_ruling(content_of(broken("judge_confidence_out_of_range")))


# ── the one retry ────────────────────────────────────────────────────────


async def test_a_bad_form_is_demanded_once_more_and_then_accepted(broken, reference_charge):
    """Demand the fixed form twice: the second answer is in form, so the call
    succeeds -- and the retry is recorded on the row."""
    role = BY_SLOT["judge_1"]
    caller = ScriptedCaller(
        {"test/judge:free": [content_of(broken("judge_prose")), ruling_json("justified", 0.8)]}
    )

    ruling = await rule(role, "test/judge:free", reference_charge, [], call=caller)

    assert ruling.verdict == "justified"
    assert ruling.attempts == 2
    assert len(caller.prompts_for("test/judge:free")) == 2


async def test_the_retry_restates_the_required_form(broken, reference_charge):
    role = BY_SLOT["judge_1"]
    caller = ScriptedCaller(
        {"test/judge:free": [content_of(broken("judge_prose")), ruling_json()]}
    )

    await rule(role, "test/judge:free", reference_charge, [], call=caller)
    first, second = caller.prompts_for("test/judge:free")

    assert "could not be read as the required object" in second
    assert len(second) > len(first)


async def test_a_second_bad_form_fails_the_call(broken, reference_charge):
    """Twice, then fail. No third attempt, and no guess."""
    role = BY_SLOT["judge_2"]
    prose = content_of(broken("judge_prose"))
    caller = ScriptedCaller({"test/judge:free": [prose, prose]})

    with pytest.raises(RulingFormatError, match="did not state a verdict in the required form"):
        await rule(role, "test/judge:free", reference_charge, [], call=caller)

    assert len(caller.prompts_for("test/judge:free")) == 2
