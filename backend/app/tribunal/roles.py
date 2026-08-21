"""The seven slots and what each one is.

Slots and personas are fixed and identical in both situations. Only the model
changes -- that is the whole of the experiment, and anything else that differs
between Situation A and Situation B is a second variable nobody asked for.

This package holds trial logic only: no database, no web, no HTTP. What it
needs from the outside arrives as the `Caller` protocol below, so the rules of
the trial can be read and tested on their own.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Stage = Literal["statement", "judgment"]
Position = Literal["justified", "not_justified"]
Verdict = Literal["justified", "not_justified"]
Situation = Literal["identical", "different"]


@dataclass(frozen=True)
class Role:
    slot: str
    stage: Stage
    #: Shown to judges so the four statements are distinguishable. It never
    #: reveals a model: a judge that recognised its own family in a statement
    #: might be indulgent toward it.
    persona: str
    #: Which side an advocate argues. Judges have none -- they are not seated
    #: on a side and are never told one.
    position: Position | None = None


ROLES: tuple[Role, ...] = (
    Role("advocate_against_1", "statement", "Advocate Vega", "not_justified"),
    Role("advocate_against_2", "statement", "Advocate Lyra", "not_justified"),
    Role("advocate_for_1", "statement", "Advocate Orion", "justified"),
    Role("advocate_for_2", "statement", "Advocate Draco", "justified"),
    Role("judge_1", "judgment", "Judge Meridian"),
    Role("judge_2", "judgment", "Judge Zenith"),
    Role("judge_3", "judgment", "Judge Solstice"),
)

BY_SLOT: dict[str, Role] = {role.slot: role for role in ROLES}

ADVOCATE_SLOTS: tuple[str, ...] = tuple(r.slot for r in ROLES if r.stage == "statement")
JUDGE_SLOTS: tuple[str, ...] = tuple(r.slot for r in ROLES if r.stage == "judgment")
ALL_SLOTS: tuple[str, ...] = tuple(r.slot for r in ROLES)

VERDICTS: tuple[Verdict, ...] = ("justified", "not_justified")


@runtime_checkable
class Completion(Protocol):
    """What a finished call looks like to the trial logic.

    Structural, so `tribunal/` never imports the HTTP client that produces it.
    """

    model: str
    text: str
    duration_ms: int
    cost: float
    temperature_requested: float
    temperature_reported: float | None

    @property
    def words(self) -> int: ...


#: Sends one prompt to one model. Supplied from outside; the trial logic does
#: not know how a model is reached, only that it can be asked.
Caller = Callable[..., Awaitable[Completion]]

#: Reports partial text as it arrives, for the slot named.
Progress = Callable[[str, str], Awaitable[None]]


@dataclass(frozen=True)
class SlotFailure:
    """One slot that could not be filled, and on which model.

    Which slot failed on which model is the finding here, not noise. Free
    models fail often, and Situation B has seven chances to fail where
    Situation A has one -- so the failures are recorded, every one of them,
    rather than swallowed by whichever exception happened to surface first.
    """

    slot: str
    stage: Stage
    model: str
    message: str


class StageFailed(Exception):
    """A stage in which at least one call failed twice.

    Carries every failure of the stage, not the first one. The run is over:
    all seven calls succeed or the run is `failed`.
    """

    def __init__(self, failures: list[SlotFailure]):
        self.failures = failures
        super().__init__(
            "; ".join(f"{f.slot} on {f.model}: {f.message}" for f in failures)
        )
