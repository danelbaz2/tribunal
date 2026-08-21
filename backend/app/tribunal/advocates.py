"""Stage 1 -- the four statements.

Four advocates write at the same time and in isolation. No advocate is ever
passed another advocate's output; that is enforced here, by what this module
puts into the prompt, and is asserted in the tests against the captured prompt
text rather than against the template.

Advocate output is plain text and is never parsed for meaning. The prompt names
a target length; nothing is truncated, and the actual word count is recorded so
a verbosity difference between the two situations becomes a finding.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .prompts_loader import fill, statement_template
from .roles import (
    ADVOCATE_SLOTS,
    BY_SLOT,
    Caller,
    Completion,
    Progress,
    Role,
    SlotFailure,
    StageFailed,
)

POSITION_PHRASE = {
    "justified": "justified",
    "not_justified": "not justified",
}


@dataclass(frozen=True)
class Statement:
    slot: str
    persona: str
    model: str
    #: Exactly what was sent, kept so independence can be asserted on it.
    prompt: str
    text: str
    words: int
    duration_ms: int
    cost: float
    temperature_requested: float
    temperature_reported: float | None


def build_prompt(role: Role, charge: str, target_words: int) -> str:
    """The prompt for one advocate.

    It contains the charge file, this advocate's position, and nothing else.
    In particular it contains no other advocate's statement, no judge, and no
    model identifier.
    """
    if role.position is None:
        raise ValueError(f"{role.slot} is not an advocate")
    return fill(
        statement_template(),
        position_phrase=POSITION_PHRASE[role.position],
        target_words=str(target_words),
        charge=charge,
    )


async def speak(
    role: Role,
    model: str,
    charge: str,
    *,
    call: Caller,
    target_words: int,
    on_progress: Progress | None = None,
) -> Statement:
    """One advocate states its position. Raises if the call failed."""
    prompt = build_prompt(role, charge, target_words)

    async def relay(text: str) -> None:
        if on_progress is not None:
            await on_progress(role.slot, text)

    completion: Completion = await call(
        model, prompt, on_chunk=relay if on_progress is not None else None
    )

    return Statement(
        slot=role.slot,
        persona=role.persona,
        model=model,
        prompt=prompt,
        text=completion.text,
        words=completion.words,
        duration_ms=completion.duration_ms,
        cost=completion.cost,
        temperature_requested=completion.temperature_requested,
        temperature_reported=completion.temperature_reported,
    )


async def hear_all(
    roster: dict[str, str],
    charge: str,
    *,
    call: Caller,
    target_words: int,
    on_progress: Progress | None = None,
) -> list[Statement]:
    """All four advocates, in parallel, each unaware of the others.

    Returns the statements in fixed slot order, never in order of arrival.
    Any one of them failing fails the stage, and with it the run: a trial of
    three statements is not comparable to a trial of four. Every failure of the
    stage is reported, not only the first to surface.
    """
    results = await asyncio.gather(
        *(
            speak(
                BY_SLOT[slot],
                roster[slot],
                charge,
                call=call,
                target_words=target_words,
                on_progress=on_progress,
            )
            for slot in ADVOCATE_SLOTS
        ),
        return_exceptions=True,
    )

    failures = [
        SlotFailure(slot, "statement", roster[slot], str(result))
        for slot, result in zip(ADVOCATE_SLOTS, results, strict=True)
        if isinstance(result, BaseException)
    ]
    if failures:
        raise StageFailed(failures)

    return [result for result in results if isinstance(result, Statement)]
