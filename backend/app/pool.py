"""The pool this process draws from.

Resolved once at startup -- either discovered from OpenRouter's live free tier
or pinned by hand through `MODEL_POOL` -- and read by every run afterwards.

Why it is resolved once rather than per run: a run that redrew the tier
mid-flight could seat a model in stage 2 that did not exist when stage 1 began.
Why it is not a constant: the free tier changes without notice, and a
hand-written list decays into a server that refuses to start.

**Every run stores the pool it drew from** (`runs.pool`). That is what keeps
criterion 15 true after this change: reconstitution needs the seed *and* the
pool, and both are on the row. A pool that shifts under the project would
otherwise make an old seed meaningless.

The cost of a live pool, stated plainly: two runs convened a week apart may
draw from different candidate sets, so a comparison across them carries a third
uncontrolled variable on top of the draw itself. Compare runs from the same
sitting, and read `runs.pool` before trusting an old pair.
"""

from __future__ import annotations

from .tribunal.roles import ALL_SLOTS

_resolved: tuple[str, ...] = ()


class PoolTooSmall(RuntimeError):
    """Fewer free models than there are chairs. Loud, and at startup."""


def set_pool(models: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Fix the pool for this process. Refuses a bench it cannot seat."""
    global _resolved
    unique = tuple(sorted(set(models)))

    if len(unique) < len(ALL_SLOTS):
        raise PoolTooSmall(
            f"OpenRouter is offering {len(unique)} usable free models; "
            f"{len(ALL_SLOTS)} are needed to seat the bench. "
            "Situation B cannot draw seven distinct models from fewer than seven. "
            "Wait for the free tier to recover, or pin MODEL_POOL deliberately."
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


def clear() -> None:
    """Tests only, so one test's pool never leaks into the next."""
    global _resolved
    _resolved = ()
