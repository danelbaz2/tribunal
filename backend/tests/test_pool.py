"""Which models may sit on the bench.

Asserted against a captured OpenRouter catalogue in `tests/data/`, so it runs
offline and keeps holding after the free tier moves again -- which it will.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import pool
from app.ai.openrouter import select_free_models
from app.tribunal.roles import ALL_SLOTS

CATALOGUE = json.loads(
    (Path(__file__).parent / "data" / "openrouter_models.json").read_text(encoding="utf-8")
)["data"]

MIN_CONTEXT = 16384


@pytest.fixture(scope="module")
def selected() -> tuple[str, ...]:
    return select_free_models(CATALOGUE, MIN_CONTEXT)


def test_it_finds_enough_models_to_seat_the_bench(selected):
    assert len(selected) >= len(ALL_SLOTS)


def test_a_paid_model_is_never_seated(selected):
    """Cost must be zero on both sides, as a measured fact rather than a
    belief about a tier."""
    paid = [
        entry["id"]
        for entry in CATALOGUE
        if float(entry["pricing"].get("prompt") or 0) > 0
    ]
    assert paid, "the fixture must contain a paid model or it proves nothing"
    for identifier in paid:
        assert identifier not in selected


def test_the_router_alias_is_never_seated(selected):
    """`openrouter/free` resolves to a different model on every call. Seating
    it in all seven chairs would look like Situation A and be nothing of the
    kind -- seven models pretending to be one."""
    assert "openrouter/free" in {entry["id"] for entry in CATALOGUE}
    assert "openrouter/free" not in selected


def test_a_zero_priced_model_that_is_not_a_free_chat_model_is_not_seated(selected):
    """A music model and an anonymous stealth endpoint both price at zero and
    both declare text output. The `:free` suffix is what excludes them."""
    assert "google/lyria-3-pro-preview" not in selected
    assert "stealth/ox-alpha" not in selected


def test_a_context_too_small_to_hold_a_transcript_is_not_seated(selected):
    """A judge is sent the charge file plus four statements. A model that
    cannot hold that fails stage 2 every time."""
    assert "tiny/pocket-model:free" not in selected


def test_the_selection_is_sorted_and_free_of_duplicates(selected):
    """The pool is a stable ordered set, so one seed draws one bench from one
    tier."""
    assert list(selected) == sorted(set(selected))


def test_raising_the_context_floor_narrows_the_pool():
    wide = select_free_models(CATALOGUE, 16384)
    narrow = select_free_models(CATALOGUE, 200_000)

    assert set(narrow) < set(wide)


def test_an_empty_catalogue_selects_nothing():
    assert select_free_models([], MIN_CONTEXT) == ()


def test_a_malformed_entry_is_skipped_not_crashed_on():
    """OpenRouter's catalogue is not this project's to validate."""
    rubbish = [
        {},
        {"id": None},
        {"id": "x:free"},
        {"id": "y:free", "pricing": {"prompt": "free"}},
        {"id": "z:free", "pricing": {"prompt": "0", "completion": "0"}, "architecture": None},
    ]

    assert select_free_models(rubbish, MIN_CONTEXT) == ()


# ── the resolved pool ────────────────────────────────────────────────────


def test_a_pool_smaller_than_the_bench_is_refused():
    """Situation B cannot draw seven distinct models from fewer than seven.
    Failing here beats failing three minutes into a deliberation."""
    pool.clear()
    try:
        with pytest.raises(pool.PoolTooSmall, match="7 are needed"):
            pool.set_pool(["a:free", "b:free", "c:free"])
    finally:
        pool.clear()


def test_reading_an_unresolved_pool_says_so():
    pool.clear()
    with pytest.raises(pool.PoolTooSmall, match="No model pool has been resolved"):
        pool.get_pool()


def test_the_resolved_pool_is_sorted_and_deduplicated(selected):
    pool.clear()
    try:
        resolved = pool.set_pool(list(selected) + list(selected))
        assert resolved == tuple(sorted(set(selected)))
        assert pool.get_pool() == resolved
    finally:
        pool.clear()
