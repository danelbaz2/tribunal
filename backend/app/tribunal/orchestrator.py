"""The whole trial, from convening to the count.

Stage 1 completes before stage 2 begins. That boundary is real, not cosmetic:
the four statements must all exist before any judge is built a transcript, so
that every judge reads the same four and none reads a partial room.

Nothing here touches a database or an HTTP client. Persistence and streaming
are somebody else's job, reached through the `Observer` below -- which is why
the rules of the trial can be read and tested on their own, offline.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .advocates import Statement, hear_all
from .judges import Ruling, rule_all
from .roles import (
    ALL_SLOTS,
    BY_SLOT,
    Caller,
    Gate,
    NullGate,
    SlotFailure,
    StageFailed,
)


class Observer(Protocol):
    """Told what happened, as it happens. Every method is optional in spirit;
    `NullObserver` supplies the do-nothing version."""

    async def call_started(self, slot: str, stage: str, model: str) -> None: ...

    async def call_progress(self, slot: str, text: str) -> None: ...

    async def statement_done(self, statement: Statement) -> None: ...

    async def ruling_done(self, ruling: Ruling) -> None: ...

    async def stage_failed(self, failures: list[SlotFailure]) -> None: ...


class NullObserver:
    async def call_started(self, slot: str, stage: str, model: str) -> None: ...

    async def call_progress(self, slot: str, text: str) -> None: ...

    async def statement_done(self, statement: Statement) -> None: ...

    async def ruling_done(self, ruling: Ruling) -> None: ...

    async def stage_failed(self, failures: list[SlotFailure]) -> None: ...


def pacing_gate(max_concurrent: int) -> Gate:
    """How many participants may hold the floor at once.

    Pacing, not method. It changes nothing about what any call is sent.
    Isolation is untouched: no advocate reads another whether they speak at
    once or in turn.

    It exists because the free tier answers 429 to a burst of four, and a rate
    limit that failed a call would bias which runs survive to be compared.

    A gate rather than a wrapper around the caller, because a participant's
    turn covers its announcement as well as its call: announcing outside the
    gate marks every slot live at once, which is what a real run showed --
    four cards reasoning while one model worked and three queued.

    The semaphore is first-come-first-served, so a limit of one also fixes the
    order: the room fills in display order.
    """
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be at least 1")
    return NullGate() if max_concurrent >= len(ALL_SLOTS) else asyncio.Semaphore(max_concurrent)


@dataclass
class Trial:
    """What the run produced. `finished` means all seven calls succeeded."""

    status: str
    statements: list[Statement] = field(default_factory=list)
    rulings: list[Ruling] = field(default_factory=list)
    failures: list[SlotFailure] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @property
    def justified_count(self) -> int:
        return sum(1 for ruling in self.rulings if ruling.verdict == "justified")

    @property
    def not_justified_count(self) -> int:
        return sum(1 for ruling in self.rulings if ruling.verdict == "not_justified")


async def run_trial(
    charge: str,
    roster: dict[str, str],
    *,
    call: Caller,
    target_words: int,
    min_statement_words: int = 60,
    observer: Observer | None = None,
    max_concurrent: int = 1,
) -> Trial:
    """Hold the trial.

    Returns a `Trial` with status `finished` only if all seven calls
    succeeded. Anything less is `failed`, with every failure named by slot and
    model -- a run of three statements is not comparable to a run of four, and
    a verdict from two judges is not the deliverable.
    """
    watcher: Observer = observer or NullObserver()
    # One gate for the whole trial: stage 2 inherits the pace stage 1 was held
    # to.
    gate = pacing_gate(max_concurrent)
    trial = Trial(status="running")

    async def progress(slot: str, text: str) -> None:
        await watcher.call_progress(slot, text)

    async def announce(slot: str) -> None:
        await watcher.call_started(slot, BY_SLOT[slot].stage, roster[slot])

    # ── stage 1 ───────────────────────────────────────────────────────────
    try:
        trial.statements = await hear_all(
            roster,
            charge,
            call=call,
            target_words=target_words,
            min_words=min_statement_words,
            on_progress=progress,
            on_start=announce,
            on_done=watcher.statement_done,
            gate=gate,
        )
    except StageFailed as failure:
        trial.status = "failed"
        trial.failures = failure.failures
        trial.finished_at = datetime.now(timezone.utc)
        await watcher.stage_failed(failure.failures)
        return trial

    # ── stage 2 ───────────────────────────────────────────────────────────
    # Reached only because all four statements exist.
    try:
        trial.rulings = await rule_all(
            roster, charge, trial.statements, call=call,
            on_start=announce,
            on_done=watcher.ruling_done,
            gate=gate,
        )
    except StageFailed as failure:
        trial.status = "failed"
        trial.failures = failure.failures
        trial.finished_at = datetime.now(timezone.utc)
        await watcher.stage_failed(failure.failures)
        return trial

    trial.status = "finished"
    trial.finished_at = datetime.now(timezone.utc)
    return trial
