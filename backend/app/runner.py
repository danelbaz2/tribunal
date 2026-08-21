"""Runs a trial and tells the browser what is happening.

This is the seam between the trial logic, which knows nothing about databases
or sockets, and the two things the interface needs: rows that survive, and a
stream that arrives while they are being made.

Two decisions worth stating.

**Partial text is never written to the database.** While an advocate is
writing, the text so far is held in memory and pushed to whoever is watching.
The row gets the complete statement when the call completes. The database
records what happened, not the frames along the way.

**Each event carries the whole run.** A dropped message therefore cannot leave
the interface holding a half-applied delta -- it simply misses one frame and
gets the next.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import SessionFactory
from .models import LlmCall, Run
from .schemas import CallOut, RunOut
from .tribunal.advocates import Statement
from .tribunal.judges import Ruling
from .tribunal.orchestrator import run_trial
from .tribunal.roles import SlotFailure

#: Live subscribers, per run.
_subscribers: dict[int, set[asyncio.Queue[RunOut | None]]] = defaultdict(set)

#: Partial statement text, per run and slot. In memory only.
_live_text: dict[int, dict[str, str]] = defaultdict(dict)

#: Background trials, kept referenced so they are not garbage-collected.
_tasks: set[asyncio.Task[None]] = set()

#: Slow the progress stream to something a reader can follow, and a database
#: does not have to care about at all.
_PROGRESS_INTERVAL_SECONDS = 0.4


def subscribe(run_id: int) -> asyncio.Queue[RunOut | None]:
    queue: asyncio.Queue[RunOut | None] = asyncio.Queue(maxsize=64)
    _subscribers[run_id].add(queue)
    return queue


def unsubscribe(run_id: int, queue: asyncio.Queue[RunOut | None]) -> None:
    _subscribers[run_id].discard(queue)
    if not _subscribers[run_id]:
        _subscribers.pop(run_id, None)


async def _publish(run_id: int, payload: RunOut | None) -> None:
    for queue in list(_subscribers.get(run_id, ())):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # A reader too slow to keep up misses a frame. The next one carries
            # the whole run again, so nothing is lost but latency.
            pass


async def build_run_out(session: AsyncSession, run_id: int) -> RunOut | None:
    run = await session.get(Run, run_id)
    if run is None:
        return None

    rows = (
        await session.execute(select(LlmCall).where(LlmCall.run_id == run_id).order_by(LlmCall.id))
    ).scalars().all()

    live = _live_text.get(run_id, {})
    calls = []
    for row in rows:
        call = CallOut.model_validate(row)
        if row.status == "writing" and live.get(row.slot):
            call = call.model_copy(update={"text": live[row.slot]})
        calls.append(call)

    return RunOut(
        id=run.id,
        case_id=run.case_id,
        case_title=run.case.title if run.case else "",
        status=run.status,
        situation=run.situation,
        seed=run.seed,
        roster=run.roster,
        started_at=run.started_at,
        finished_at=run.finished_at,
        calls=calls,
    )


class _Recorder:
    """The orchestrator's observer: writes rows, then tells the watchers."""

    def __init__(self, run_id: int):
        self.run_id = run_id
        self._last_progress: dict[str, float] = {}

    async def _with_row(self, slot: str, apply) -> None:
        async with SessionFactory() as session:
            row = (
                await session.execute(
                    select(LlmCall).where(
                        LlmCall.run_id == self.run_id, LlmCall.slot == slot
                    )
                )
            ).scalar_one()
            apply(row)
            await session.commit()

    async def _announce(self) -> None:
        async with SessionFactory() as session:
            payload = await build_run_out(session, self.run_id)
        if payload is not None:
            await _publish(self.run_id, payload)

    async def call_started(self, slot: str, stage: str, model: str) -> None:
        def apply(row: LlmCall) -> None:
            row.status = "writing"
            row.model = model
            row.stage = stage

        await self._with_row(slot, apply)
        await self._announce()

    async def call_progress(self, slot: str, text: str) -> None:
        _live_text[self.run_id][slot] = text

        now = time.monotonic()
        if now - self._last_progress.get(slot, 0.0) < _PROGRESS_INTERVAL_SECONDS:
            return
        self._last_progress[slot] = now
        await self._announce()

    async def statement_done(self, statement: Statement) -> None:
        def apply(row: LlmCall) -> None:
            row.status = "done"
            row.prompt = statement.prompt
            row.text = statement.text
            row.words = statement.words
            row.duration_ms = statement.duration_ms
            row.cost = statement.cost
            row.temperature_requested = statement.temperature_requested
            row.temperature_reported = statement.temperature_reported
            row.attempts = 1

        _live_text[self.run_id].pop(statement.slot, None)
        await self._with_row(statement.slot, apply)
        await self._announce()

    async def ruling_done(self, ruling: Ruling) -> None:
        def apply(row: LlmCall) -> None:
            row.status = "done"
            row.prompt = ruling.prompt
            row.text = ruling.raw_text
            row.verdict = ruling.verdict
            row.confidence = ruling.confidence
            row.reasons = ruling.reasons
            row.words = len(ruling.raw_text.split())
            row.duration_ms = ruling.duration_ms
            row.cost = ruling.cost
            row.temperature_requested = ruling.temperature_requested
            row.temperature_reported = ruling.temperature_reported
            row.attempts = ruling.attempts
            row.raw_response = {"answer": ruling.raw_text}

        await self._with_row(ruling.slot, apply)
        await self._announce()

    async def stage_failed(self, failures: list[SlotFailure]) -> None:
        settings = get_settings()
        for failure in failures:

            def apply(row: LlmCall, failure: SlotFailure = failure) -> None:
                row.status = "failed"
                row.error = failure.message
                row.attempts = settings.max_attempts

            _live_text[self.run_id].pop(failure.slot, None)
            await self._with_row(failure.slot, apply)
        await self._announce()


@asynccontextmanager
async def _openrouter_caller() -> AsyncIterator[object]:
    """The real door to the models. Imported here so nothing outside a live
    run needs a key or an HTTP client."""
    from .ai.openrouter import OpenRouterClient

    async with OpenRouterClient(get_settings()) as client:
        yield client.complete


#: How a run reaches the models. Replaced in tests by a replay of the captured
#: fixtures, which is the only reason it is a variable and not a call.
caller_factory = _openrouter_caller


async def _hold_trial(run_id: int) -> None:
    """The unattended part: convene, then run to the end without asking."""
    settings = get_settings()

    async with SessionFactory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        charge = run.case.content
        roster = dict(run.roster)

    recorder = _Recorder(run_id)

    try:
        async with caller_factory() as call:
            trial = await run_trial(
                charge,
                roster,
                call=call,
                target_words=settings.statement_target_words,
                observer=recorder,
            )
        status = trial.status
        finished_at = trial.finished_at
    except Exception as error:  # a failure to even start is still a failed run
        # A run that ended has an end time, whatever ended it.
        status, finished_at = "failed", datetime.now(timezone.utc)
        async with SessionFactory() as session:
            run = await session.get(Run, run_id)
            if run is not None:
                for row in run.calls:
                    if row.status in {"waiting", "writing"}:
                        row.status = "failed"
                        row.error = str(error)
                await session.commit()

    async with SessionFactory() as session:
        run = await session.get(Run, run_id)
        if run is not None:
            run.status = status
            run.finished_at = finished_at
            await session.commit()

    _live_text.pop(run_id, None)

    async with SessionFactory() as session:
        payload = await build_run_out(session, run_id)
    if payload is not None:
        await _publish(run_id, payload)
    # A closing sentinel, so a watcher stops waiting instead of hanging on a
    # run that is already over.
    await _publish(run_id, None)


def start(run_id: int) -> None:
    task = asyncio.create_task(_hold_trial(run_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
