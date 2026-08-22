"""Start a trial, follow it, read it.

Starting is the last input the run takes. There is no confirmation mid-run, no
step the interface has to advance: stage 1, stage 2, result, unattended.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .. import pool, runner
from ..database import get_session
from ..models import Case, LlmCall, Run
from ..schemas import ConveneRequest, RunOut
from ..tribunal.roles import ALL_SLOTS, BY_SLOT
from ..tribunal.roster import BenchTooSmall, seat_bench

router = APIRouter(prefix="/api/runs", tags=["runs"])

#: Keeps proxies from closing an idle stream while a free model thinks.
_HEARTBEAT_SECONDS = 15.0


@router.post("", response_model=RunOut)
@router.post("/", response_model=RunOut, include_in_schema=False)
async def convene(
    request: ConveneRequest, session: AsyncSession = Depends(get_session)
) -> RunOut:
    if request.situation not in {"identical", "different"}:
        raise HTTPException(status_code=422, detail="situation must be identical or different")

    case = await session.get(Case, request.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="No such case.")

    try:
        models = pool.get_pool()
    except pool.PoolTooSmall as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        roster = seat_bench(models, request.situation)
    except BenchTooSmall as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    run = Run(case_id=case.id, status="running", situation=request.situation, roster=roster)
    session.add(run)
    await session.flush()

    # The seven rows exist before the first call does, so a slot that has not
    # spoken yet holds its place instead of appearing when it arrives.
    for slot in ALL_SLOTS:
        session.add(
            LlmCall(
                run_id=run.id,
                slot=slot,
                stage=BY_SLOT[slot].stage,
                model=roster[slot],
                status="waiting",
            )
        )
    await session.commit()

    runner.start(run.id)

    payload = await runner.build_run_out(session, run.id)
    assert payload is not None
    return payload


@router.get("/{run_id}", response_model=RunOut)
async def read_run(run_id: int, session: AsyncSession = Depends(get_session)) -> RunOut:
    payload = await runner.build_run_out(session, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="No such run.")
    return payload


@router.get("/{run_id}/events")
async def run_events(run_id: int, session: AsyncSession = Depends(get_session)):
    """Server-sent events: one message per change, each carrying the whole run.

    A dropped message therefore cannot leave the interface holding a
    half-applied delta -- it misses a frame and the next one repairs it.
    """
    first = await runner.build_run_out(session, run_id)
    if first is None:
        raise HTTPException(status_code=404, detail="No such run.")

    queue = runner.subscribe(run_id)

    async def stream():
        try:
            yield _event(first)
            if first.status != "running":
                return

            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                if payload is None:  # the run is over
                    return
                yield _event(payload)
        finally:
            runner.unsubscribe(run_id, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event(payload: RunOut) -> str:
    body = json.dumps(payload.model_dump(by_alias=True, mode="json"))
    return f"data: {body}\n\n"
