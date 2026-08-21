"""Situation A against Situation B.

The result of the project. Everything reported here is computed from
`llm_calls` rows at read time; the comparison table stores only which two runs
are being compared.

Cost is recorded and reported, and is expected to be zero on both sides --
both situations draw from the free pool. "Which was cheaper" has no answer, so
nothing here presents one. Agreement per judge slot, duration and word count
are the live differentiators.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Comparison, Run
from ..schemas import ComparisonOut, SituationSummary, SlotAgreement
from ..tribunal.roles import ADVOCATE_SLOTS, JUDGE_SLOTS

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


class CompareRequest(BaseModel):
    run_identical_id: int
    run_different_id: int


def _summarise(run: Run) -> SituationSummary:
    calls = {call.slot: call for call in run.calls}
    wall_clock = 0
    if run.finished_at is not None:
        wall_clock = int((run.finished_at - run.started_at).total_seconds() * 1000)

    return SituationSummary(
        run_id=run.id,
        justified_count=sum(1 for c in run.calls if c.verdict == "justified"),
        not_justified_count=sum(1 for c in run.calls if c.verdict == "not_justified"),
        wall_clock_ms=wall_clock,
        words_argued=sum(calls[slot].words for slot in ADVOCATE_SLOTS if slot in calls),
        cost=sum(c.cost for c in run.calls),
        duration_by_slot={slot: call.duration_ms for slot, call in calls.items()},
        words_by_slot={slot: calls[slot].words for slot in ADVOCATE_SLOTS if slot in calls},
    )


def _agreement(identical: Run, different: Run) -> list[SlotAgreement]:
    """Per judge slot: did the same chair rule the same way in both?

    Read one slot at a time and never as a claim about models. Whatever model
    landed in `judge_1` is the only evidence there is about `judge_1`; a single
    pair of runs cannot separate a model difference from sampling noise.
    """
    a = {call.slot: call for call in identical.calls}
    b = {call.slot: call for call in different.calls}

    rows = []
    for slot in JUDGE_SLOTS:
        left, right = a[slot], b[slot]
        rows.append(
            SlotAgreement(
                slot=slot,
                identical_verdict=left.verdict or "",
                different_verdict=right.verdict or "",
                agreed=left.verdict == right.verdict,
                identical_model=left.model,
                different_model=right.model,
            )
        )
    return rows


async def _finished(session: AsyncSession, run_id: int, situation: str) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {run_id}.")
    if run.situation != situation:
        raise HTTPException(status_code=422, detail=f"Run {run_id} is not the {situation} side.")
    if run.status != "finished":
        # A failed run appears in no comparison. A run of three statements is
        # not comparable to a run of four.
        raise HTTPException(
            status_code=422, detail=f"Run {run_id} is {run.status}, not finished."
        )
    return run


@router.post("", response_model=ComparisonOut)
@router.post("/", response_model=ComparisonOut, include_in_schema=False)
async def create_comparison(
    request: CompareRequest, session: AsyncSession = Depends(get_session)
) -> ComparisonOut:
    identical = await _finished(session, request.run_identical_id, "identical")
    different = await _finished(session, request.run_different_id, "different")

    if identical.case_id != different.case_id:
        raise HTTPException(
            status_code=422, detail="The two runs read different cases; they are not comparable."
        )

    comparison = Comparison(
        case_id=identical.case_id,
        run_identical_id=identical.id,
        run_different_id=different.id,
    )
    session.add(comparison)
    await session.commit()
    await session.refresh(comparison)

    return _render(comparison, identical, different)


@router.get("/{comparison_id}", response_model=ComparisonOut)
async def read_comparison(
    comparison_id: int, session: AsyncSession = Depends(get_session)
) -> ComparisonOut:
    comparison = await session.get(Comparison, comparison_id)
    if comparison is None:
        raise HTTPException(status_code=404, detail="No such comparison.")

    runs = (
        await session.execute(
            select(Run).where(
                Run.id.in_([comparison.run_identical_id, comparison.run_different_id])
            )
        )
    ).scalars().all()
    by_id = {run.id: run for run in runs}

    return _render(
        comparison, by_id[comparison.run_identical_id], by_id[comparison.run_different_id]
    )


def _render(comparison: Comparison, identical: Run, different: Run) -> ComparisonOut:
    return ComparisonOut(
        id=comparison.id,
        case_id=comparison.case_id,
        case_title=identical.case.title,
        identical=_summarise(identical),
        different=_summarise(different),
        agreement=_agreement(identical, different),
    )
