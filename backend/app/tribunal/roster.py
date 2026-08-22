"""Who sits where.

The bench is read off the top of the pool, not drawn at random: `identical`
seats the first model in all seven chairs, `different` seats the first seven,
one per slot, in the order `MODEL_POOL` names them.
"""

from __future__ import annotations

from typing import Literal

from .roles import ALL_SLOTS

Situation = Literal["identical", "different"]


class BenchTooSmall(ValueError):
    """Fewer models in the pool than there are chairs to fill."""


def seat_bench(pool: tuple[str, ...] | list[str], situation: Situation) -> dict[str, str]:
    """Assign a model to each of the seven slots.

    * `identical` -- the first model in the pool, seated in all seven slots.
      They remain seven independent calls sharing no state; one model in
      seven chairs is not one conversation.
    * `different` -- the first seven distinct models in the pool, one per
      slot.
    """
    ordered = _ordered_unique(pool)

    if not ordered:
        raise BenchTooSmall("The pool is empty; no bench can be seated.")

    if situation == "identical":
        return {slot: ordered[0] for slot in ALL_SLOTS}

    if len(ordered) < len(ALL_SLOTS):
        raise BenchTooSmall(
            f"{len(ordered)} distinct models are configured and {len(ALL_SLOTS)} "
            "chairs need distinct ones. Add models to MODEL_POOL, or run `identical`."
        )

    return dict(zip(ALL_SLOTS, ordered[: len(ALL_SLOTS)], strict=True))


def _ordered_unique(pool: tuple[str, ...] | list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for model in pool:
        if model not in seen:
            seen.add(model)
            ordered.append(model)
    return ordered
