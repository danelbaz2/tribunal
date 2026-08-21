"""Who sits where.

The draw is a pure function of the seed and the pool. Given both, re-deriving
a roster produces the same slot-to-model assignment byte for byte -- which is
the only reason the seed is worth storing (criterion 15).

The seed exists for a second reason too. A difference found in Situation B may
come from *which* seven models were drawn rather than from diversity itself;
storing the seed is what makes that interrogable instead of arguable.
"""

from __future__ import annotations

import secrets
from random import Random

from .roles import ALL_SLOTS, Situation


def new_seed() -> str:
    """A fresh seed, recorded with the run it draws."""
    return secrets.token_hex(8)


def draw_roster(seed: str, pool: tuple[str, ...] | list[str], situation: Situation) -> dict[str, str]:
    """Assign a model to each of the seven slots.

    * `identical` -- one model drawn from the pool, seated in all seven slots.
      They remain seven independent calls sharing no state; one model in seven
      chairs is not one conversation.
    * `different` -- seven distinct models drawn without replacement, one per
      slot.
    """
    models = sorted(set(pool))
    if len(models) < len(ALL_SLOTS):
        raise ValueError(
            f"The pool holds {len(models)} models; {len(ALL_SLOTS)} are needed. "
            "Correct the pool in app/config.py."
        )

    random = Random(seed)

    if situation == "identical":
        chosen = random.choice(models)
        return {slot: chosen for slot in ALL_SLOTS}

    drawn = random.sample(models, len(ALL_SLOTS))
    return dict(zip(ALL_SLOTS, drawn, strict=True))


def distinct_models(roster: dict[str, str]) -> int:
    return len(set(roster.values()))
