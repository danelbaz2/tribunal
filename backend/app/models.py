"""The four tables of ARCHITECTURE.md Part 6.

Two rules shape this file.

**Store rows, derive totals.** Every model call is one `llm_calls` row. No
count, headline or total is a column anywhere: `justified_count`, the wall
clock, the total cost and the word totals are all computed from these rows at
read time. This is a deliberate departure from the Part 6 sketch, which drew a
`total cost` column on `runs` -- a stored total is a second source of truth
that can disagree with the rows it came from.

**A stored case is immutable.** There is no update path for `cases`. Editing a
charge file after a comparison exists silently invalidates that comparison,
because the two runs no longer read the same case. A correction is a new case.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: JSONB on PostgreSQL, plain JSON on the SQLite used by the offline tests.
JSONColumn = JSONB().with_variant(JSON(), "sqlite")


class Base(DeclarativeBase):
    pass


class Case(Base):
    """A charge file. Written once, never edited."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: What extraction actually found, recorded at upload.
    word_count: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    runs: Mapped[list["Run"]] = relationship(back_populates="case")

    __table_args__ = (CheckConstraint("source IN ('text', 'file')", name="ck_cases_source"),)


class Run(Base):
    """One trial: seven calls against one case, in one situation."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))

    situation: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="running")

    #: The draw is reproducible from these two together: re-deriving the roster
    #: from the seed and the pool gives the same assignment, byte for byte.
    seed: Mapped[str] = mapped_column(String(64))
    roster: Mapped[dict[str, str]] = mapped_column(JSONColumn)
    pool: Mapped[list[str]] = mapped_column(JSONColumn)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped[Case] = relationship(back_populates="runs", lazy="selectin")
    calls: Mapped[list["LlmCall"]] = relationship(
        back_populates="run", order_by="LlmCall.id", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("situation IN ('identical', 'different')", name="ck_runs_situation"),
        CheckConstraint("status IN ('running', 'finished', 'failed')", name="ck_runs_status"),
    )


class LlmCall(Base):
    """One model call -- the important table.

    Advocates and judges live here together rather than in two tables, because
    every question worth asking (what did each slot cost, how did each slot
    vote, how long did each model take) is then one query over one table.

    Failures are rows too. A call that failed twice is recorded with its error,
    its model and its slot, because which slot failed on which model is the
    finding, not noise to be swallowed.
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))

    slot: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="waiting")

    #: Exactly what was sent to the model, kept verbatim. The independence
    #: criteria (9-11) are asserted against this text, never against the
    #: template it was rendered from.
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Advocates return plain text; nothing in it is parsed for meaning.
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Judgment fields. Stated in the required form or the call failed.
    verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[list[str] | None] = mapped_column(JSONColumn, nullable=True)

    words: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)

    #: What was asked for, and what the response said it used. Free models may
    #: ignore temperature; recording both is how that stays visible.
    temperature_requested: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_reported: Mapped[float | None] = mapped_column(Float, nullable=True)

    #: The complete raw response, and anything else worth keeping that is not
    #: counted or filtered on.
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="calls")

    __table_args__ = (
        UniqueConstraint("run_id", "slot", name="uq_llm_calls_run_slot"),
        CheckConstraint("stage IN ('statement', 'judgment')", name="ck_llm_calls_stage"),
        CheckConstraint(
            "status IN ('waiting', 'writing', 'done', 'failed')", name="ck_llm_calls_status"
        ),
        CheckConstraint(
            "verdict IS NULL OR verdict IN ('justified', 'not_justified')",
            name="ck_llm_calls_verdict",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_llm_calls_confidence",
        ),
    )


class Comparison(Base):
    """Links one `identical` run to one `different` run of the same case.

    Both runs must have status `finished`; a failed run appears in no
    comparison, because a run of three statements is not comparable to a run
    of four.
    """

    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    run_identical_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    run_different_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "run_identical_id", "run_different_id", name="uq_comparisons_run_pair"
        ),
    )
