"""Stage 1 -- the four statements.

Four advocates write at the same time and in isolation. No advocate is ever
passed another advocate's output; that is enforced here, by what this module
puts into the prompt, and is asserted in the tests against the captured prompt
text rather than against the template.

Advocate output is plain text and is never parsed for meaning. The prompt names
a target length; nothing is truncated, and the actual word count is recorded
as a finding in its own right.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .prompts_loader import fill, persona_brief, statement_template
from .roles import (
    ADVOCATE_SLOTS,
    BY_SLOT,
    Caller,
    Completion,
    Announce,
    Gate,
    NullGate,
    Progress,
    Report,
    Role,
    SlotFailure,
    StageFailed,
)

class NotAStatement(ValueError):
    """What came back is not an argument at all.

    A refusal, a classification, a preamble, or three words. This is not a
    length rule -- the prompt still enforces nothing and truncates nothing.
    It is the floor below which there is no case to put before a judge, and
    below which a recorded word count would be a lie about what happened.
    """


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
    finish_reason: str | None = None
    #: The complete raw response, kept whole (criterion 8).
    raw: dict[str, object] = field(default_factory=dict)


def build_prompt(role: Role, charge: str, target_words: int) -> str:
    """The prompt for one advocate.

    It contains this advocate's persona, their position, and the charge file --
    and nothing else. In particular it contains no other advocate's statement,
    no other advocate's persona, no judge, and no model identifier.
    """
    if role.position is None:
        raise ValueError(f"{role.slot} is not an advocate")
    return fill(
        statement_template(),
        persona=persona_brief(role.slot),
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
    min_words: int,
    on_progress: Progress | None = None,
    on_start: Announce | None = None,
    on_done: Report | None = None,
    gate: Gate | None = None,
) -> Statement:
    """One advocate states its position. Raises if the call failed."""
    prompt = build_prompt(role, charge, target_words)

    async def relay(text: str) -> None:
        if on_progress is not None:
            await on_progress(role.slot, text)

    # The announcement belongs *inside* the gate. Outside it, all four
    # coroutines announce themselves and then queue -- which is what a real run
    # showed: four cards reasoning while one model worked and three waited.
    async with gate or NullGate():
        if on_start is not None:
            await on_start(role.slot)
        completion: Completion = await call(
            model, prompt, on_chunk=relay if on_progress is not None else None
        )

    if completion.words < min_words:
        raise NotAStatement(
            f"{model} answered {completion.words} words, which is not a statement: "
            f"{completion.text.strip()[:120]!r}"
        )

    statement = Statement(
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
        finish_reason=completion.finish_reason,
        raw=dict(completion.raw),
    )

    # Reported as it lands, not when the stage closes. Reporting the four
    # together would leave every card reasoning until the last one returned --
    # and would throw away the statements that did arrive if a later one failed.
    if on_done is not None:
        await on_done(statement)

    return statement


async def hear_all(
    roster: dict[str, str],
    charge: str,
    *,
    call: Caller,
    target_words: int,
    min_words: int,
    on_progress: Progress | None = None,
    on_start: Announce | None = None,
    on_done: Report | None = None,
    gate: Gate | None = None,
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
                min_words=min_words,
                on_progress=on_progress,
                on_start=on_start,
                on_done=on_done,
                gate=gate,
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
