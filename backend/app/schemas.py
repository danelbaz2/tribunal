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
    """The only two inputs the whole flow takes: which case, and which bench."""

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
    #: Recorded because criterion 8 requires it, and reported nowhere: the
    #: free tier prices at zero, so a cost widget would always read $0.00.
    cost: float
    #: What the model generated, and how much of it was thinking nobody reads.
    #: Derived from the stored raw response -- no column, because it is not
    #: counted or filtered on. This is what replaced cost on screen: it varies
    #: per model, and it is the largest single explanation of duration.
    tokens: int | None = None
    thinking_tokens: int | None = None
    #: 2 when a judge had to be asked twice for the required form.
    attempts: int = 0
    #: Which slot failed, and why. Surfaced, never swallowed.
    error: str | None = None


class RunOut(Wire):
    id: int
    case_id: int
    case_title: str
    status: str
    situation: str
    roster: dict[str, str]
    started_at: datetime
    finished_at: datetime | None = None
    calls: list[CallOut]
