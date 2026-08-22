"""The seven slots and what each one is.

Slots and personas are fixed. Only the model in each chair varies from run to
run.

This package holds trial logic only: no database, no web, no HTTP. What it
needs from the outside arrives as the `Caller` protocol below, so the rules of
the trial can be read and tested on their own.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

Stage = Literal["statement", "judgment"]
Position = Literal["justified", "not_justified"]
Verdict = Literal["justified", "not_justified"]


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


#: The bench. Each chair has a fixed persona, written as a voice and a method
#: in `prompts/personas/<slot>.txt`, and stylised after a school of legal
#: reasoning rather than after a person: purposive interpretation, textual
#: restraint, practical balance, and four ways of putting a case.
#:
#: Personas are fixed for every run -- a constant of the experiment, not a
#: variable in it. They replaced the star names of INTERVIEW.md decision
#: 4, deliberately: with one voice per chair the two advocates on a side can no
#: longer return the same statement, which at temperature 0 on one model is
#: exactly what they did.
ROLES: tuple[Role, ...] = (
    Role("advocate_against_1", "statement", "Prosecutor Ben-Ari", "not_justified"),
    Role("advocate_against_2", "statement", "Prosecutor Eldad", "not_justified"),
    Role("advocate_for_1", "statement", "Advocate Feldman", "justified"),
    Role("advocate_for_2", "statement", "Advocate Ben Zur", "justified"),
    Role("judge_1", "judgment", "Justice Barak"),
    Role("judge_2", "judgment", "Justice Sohlberg"),
    Role("judge_3", "judgment", "Justice Rubinstein"),
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
    #: Why the model stopped, and the whole body it came in. Criterion 8 wants
    #: every row to carry the complete raw response, statements included --
    #: what is not counted or filtered on still has to be kept.
    finish_reason: str | None
    raw: dict[str, object]

    @property
    def words(self) -> int: ...


#: Sends one prompt to one model. Supplied from outside; the trial logic does
#: not know how a model is reached, only that it can be asked.
Caller = Callable[..., Awaitable[Completion]]

#: Reports partial text as it arrives, for the slot named.
Progress = Callable[[str, str], Awaitable[None]]

class NullGate:
    """No pacing: every call goes when it is ready."""

    async def __aenter__(self) -> "NullGate":
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


#: Held for the duration of one participant's turn -- the announcement and the
#: call together. `asyncio.Semaphore` satisfies it.
Gate = AbstractAsyncContextManager


#: Says that this slot's call has just gone out. One at a time, in the order
#: the pacing gate lets them through.
Announce = Callable[[str], Awaitable[None]]

#: Hands over a finished statement or ruling the moment it exists, so a row is
#: written and a card settles as it lands rather than when its stage closes.
Report = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class SlotFailure:
    """One slot that could not be filled, and on which model.

    Which slot failed on which model is the finding here, not noise. Free
    models fail often -- the failures are recorded, every one of them, rather
    than swallowed by whichever exception happened to surface first.
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
