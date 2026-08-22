"""The pool this process draws from.

A hand-picked, static list of free models, set once at startup from
`MODEL_POOL` and read by every run afterwards. No discovery, no live check
against OpenRouter: if a model disappears from the free tier, the run that
draws it fails and says which slot and model failed, same as any other
failure.
"""

from __future__ import annotations

from .tribunal.roles import ALL_SLOTS

_resolved: tuple[str, ...] = ()


class PoolTooSmall(RuntimeError):
    """Fewer configured models than there are chairs."""


def set_pool(models: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Fix the pool for this process, in the order given."""
    global _resolved
    unique = tuple(_ordered_unique(models))

    if len(unique) < len(ALL_SLOTS):
        raise PoolTooSmall(
            f"MODEL_POOL has {len(unique)} distinct model(s); "
            f"{len(ALL_SLOTS)} are needed to seat the bench."
        )

    _resolved = unique
    return _resolved


def get_pool() -> tuple[str, ...]:
    if not _resolved:
        raise PoolTooSmall(
            "No model pool has been resolved. The server resolves one at startup; "
            "a test must call set_pool() itself."
        )
    return _resolved


def _ordered_unique(models: tuple[str, ...] | list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for model in models:
        if model not in seen:
            seen.add(model)
            ordered.append(model)
    return ordered


def clear() -> None:
    """Tests only, so one test's pool never leaks into the next."""
    global _resolved
    _resolved = ()
