"""Stage 2 -- three independent judgments.

Two rules are enforced here by what the code passes, not by what the prompt
asks for.

**No judge reads another judge.** Each judge is built one transcript, from the
charge file and the four statements. A judge's own ruling never enters anything
built for another judge; there is no place in this module where it could.

**No judge sees a model identifier.** The transcript labels statements by
persona. Nothing in it names a model, so a judge cannot be indulgent toward its
own family.

And the rule that outranks convenience: **a verdict is never inferred.** The
verdict is read from the `verdict` field of a JSON object or it is not read at
all. There is no regex fallback, no keyword matching, no reading of prose. A
judge that answers in another form is asked once more with the form restated;
a second failure fails the call, and a failed call fails the run.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from .advocates import Statement
from .prompts_loader import fill, judge_retry_template, judge_template
from .roles import (
    BY_SLOT,
    JUDGE_SLOTS,
    VERDICTS,
    Caller,
    Completion,
    Role,
    SlotFailure,
    StageFailed,
    Verdict,
)


class RulingFormatError(ValueError):
    """The answer was not the required object. Never a reason to guess."""


@dataclass(frozen=True)
class Ruling:
    slot: str
    persona: str
    model: str
    prompt: str
    verdict: Verdict
    confidence: float
    reasons: list[str]
    #: The complete answer as it arrived, kept whole.
    raw_text: str
    attempts: int
    duration_ms: int
    cost: float
    temperature_requested: float
    temperature_reported: float | None


def build_transcript(statements: list[Statement]) -> str:
    """The four statements as a judge receives them.

    Persona and position only. No slot internals, no model, no timing, no cost
    -- a judge is given what was argued and by which persona, and nothing that
    could identify the machine behind it.
    """
    blocks = []
    for statement in statements:
        role = BY_SLOT[statement.slot]
        assert role.position is not None
        side = "justified" if role.position == "justified" else "not justified"
        blocks.append(
            f"{statement.persona}, arguing that the act was {side}:\n\n{statement.text.strip()}"
        )
    return "\n\n\n".join(blocks)


def build_prompt(charge: str, statements: list[Statement]) -> str:
    return fill(judge_template(), charge=charge, transcript=build_transcript(statements))


def build_retry_prompt(charge: str, statements: list[Statement]) -> str:
    return build_prompt(charge, statements).rstrip() + "\n\n" + judge_retry_template()


def parse_ruling(answer: str) -> tuple[Verdict, float, list[str]]:
    """Read the required object, or raise.

    The only leniency is a surrounding code fence, which is a wrapper around
    the object rather than a different answer. Nothing is extracted from prose,
    and no value is defaulted: a missing field is a format failure, not a zero.
    """
    body = answer.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1] if "\n" in body else ""
        if body.rstrip().endswith("```"):
            body = body.rstrip()[: -len("```")]
        body = body.strip()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise RulingFormatError(f"not a JSON object: {error}") from error

    if not isinstance(payload, dict):
        raise RulingFormatError(f"expected an object, got {type(payload).__name__}")

    verdict = payload.get("verdict")
    if verdict not in VERDICTS:
        raise RulingFormatError(f"verdict must be one of {VERDICTS}, got {verdict!r}")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise RulingFormatError(f"confidence must be a number, got {confidence!r}")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise RulingFormatError(f"confidence must be in [0.0, 1.0], got {confidence}")

    reasons = payload.get("reasons")
    if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
        raise RulingFormatError("reasons must be an array of strings")
    reasons = [item.strip() for item in reasons if item.strip()]
    if len(reasons) < 2:
        raise RulingFormatError(f"at least 2 reasons are required, got {len(reasons)}")

    return verdict, confidence, reasons


async def rule(
    role: Role,
    model: str,
    charge: str,
    statements: list[Statement],
    *,
    call: Caller,
) -> Ruling:
    """One judge rules. Demands the fixed form twice, then fails."""
    prompts = [build_prompt(charge, statements), build_retry_prompt(charge, statements)]
    last_error: RulingFormatError | None = None

    for attempt, prompt in enumerate(prompts, start=1):
        completion: Completion = await call(model, prompt)
        try:
            verdict, confidence, reasons = parse_ruling(completion.text)
        except RulingFormatError as error:
            last_error = error
            continue

        return Ruling(
            slot=role.slot,
            persona=role.persona,
            model=model,
            prompt=prompt,
            verdict=verdict,
            confidence=confidence,
            reasons=reasons,
            raw_text=completion.text,
            attempts=attempt,
            duration_ms=completion.duration_ms,
            cost=completion.cost,
            temperature_requested=completion.temperature_requested,
            temperature_reported=completion.temperature_reported,
        )

    raise RulingFormatError(
        f"{role.slot} on {model} did not state a verdict in the required form twice: {last_error}"
    )


async def rule_all(
    roster: dict[str, str],
    charge: str,
    statements: list[Statement],
    *,
    call: Caller,
) -> list[Ruling]:
    """The three judges, in parallel and in ignorance of one another.

    They are given the same `statements` list and nothing derived from each
    other. Returned in fixed slot order. Every failure of the stage is
    reported, not only the first to surface.
    """
    results = await asyncio.gather(
        *(
            rule(BY_SLOT[slot], roster[slot], charge, statements, call=call)
            for slot in JUDGE_SLOTS
        ),
        return_exceptions=True,
    )

    failures = [
        SlotFailure(slot, "judgment", roster[slot], str(result))
        for slot, result in zip(JUDGE_SLOTS, results, strict=True)
        if isinstance(result, BaseException)
    ]
    if failures:
        raise StageFailed(failures)

    return [result for result in results if isinstance(result, Ruling)]
