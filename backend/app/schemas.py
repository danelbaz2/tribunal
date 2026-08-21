"""What crosses the wire.

Fields are camelCase on the wire because the frontend reads them that way, and
snake_case in Python. Nothing derived appears here: the headline sentence, the
verdict counts, the total words, the wall clock and the total cost are computed
by the reader from the rows below, which is the only place they exist.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Wire(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


# ── cases ────────────────────────────────────────────────────────────────


class ExtractedCharge(Wire):
    case_id: int
    title: str
    #: What extraction actually found -- the live readout the screen shows.
    word_count: int
    pages: int | None = None
    has_text_layer: bool


# ── runs ─────────────────────────────────────────────────────────────────


class ConveneRequest(BaseModel):
    """The only two inputs in the whole flow."""

    case_id: int = Field(alias="case_id")
    situation: str

    model_config = ConfigDict(populate_by_name=True)


class CallOut(Wire):
    slot: str
    stage: str
    model: str
    status: str
    text: str | None = None
    verdict: str | None = None
    confidence: float | None = None
    reasons: list[str] | None = None
    words: int
    duration_ms: int
    cost: float
    #: Which slot failed, and why. Surfaced, never swallowed.
    error: str | None = None


class RunOut(Wire):
    id: int
    case_id: int
    case_title: str
    status: str
    situation: str
    seed: str
    roster: dict[str, str]
    started_at: datetime
    finished_at: datetime | None = None
    calls: list[CallOut]


# ── comparisons ──────────────────────────────────────────────────────────


class SlotAgreement(Wire):
    """Did the same slot rule the same way in both situations?"""

    slot: str
    identical_verdict: str
    different_verdict: str
    agreed: bool
    identical_model: str
    different_model: str


class SituationSummary(Wire):
    run_id: int
    justified_count: int
    not_justified_count: int
    wall_clock_ms: int
    words_argued: int
    cost: float
    #: Per slot, so a duration difference is attributable.
    duration_by_slot: dict[str, int]
    #: Per statement, so a verbosity difference between situations is visible.
    words_by_slot: dict[str, int]


class ComparisonOut(Wire):
    id: int
    case_id: int
    case_title: str
    identical: SituationSummary
    different: SituationSummary
    #: The finding: agreement per judge slot.
    agreement: list[SlotAgreement]
