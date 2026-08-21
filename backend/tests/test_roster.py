"""Criteria 5 and 15 -- the draw, and putting it back together."""

from __future__ import annotations

import pytest

from app.tribunal.roles import ALL_SLOTS
from app.tribunal.roster import draw_roster, new_seed
from conftest import TEST_POOL


def test_a_bench_needs_seven_models_to_draw_from():
    """The pool itself is discovered at startup, not written down -- see
    `test_pool.py`. What matters here is that the draw refuses a pool too
    small to seat seven distinct chairs."""
    assert len(set(TEST_POOL)) >= len(ALL_SLOTS)


def test_situation_a_seats_exactly_one_model_seven_times():
    """Criterion 5, first half."""
    roster = draw_roster("seed-a", TEST_POOL, "identical")

    assert set(roster) == set(ALL_SLOTS)
    assert len(set(roster.values())) == 1


def test_situation_b_seats_exactly_seven_distinct_models():
    """Criterion 5, second half."""
    roster = draw_roster("seed-b", TEST_POOL, "different")

    assert set(roster) == set(ALL_SLOTS)
    assert len(set(roster.values())) == len(ALL_SLOTS)


@pytest.mark.parametrize("situation", ["identical", "different"])
def test_the_same_seed_redraws_the_same_bench(situation):
    """Criterion 15 -- reconstitution, byte for byte."""
    seed = new_seed()

    first = draw_roster(seed, TEST_POOL, situation)
    second = draw_roster(seed, TEST_POOL, situation)

    assert first == second


def test_the_draw_does_not_depend_on_the_order_the_pool_was_written_in():
    """The seed reproduces the bench; a reshuffled config file must not
    silently redraw it."""
    seed = "stable"
    forwards = draw_roster(seed, TEST_POOL, "different")
    backwards = draw_roster(seed, tuple(reversed(TEST_POOL)), "different")

    assert forwards == backwards


def test_a_pool_too_small_to_seat_the_bench_is_refused():
    with pytest.raises(ValueError, match="models are needed|are needed"):
        draw_roster("seed", ("only/one:free", "and/another:free"), "different")
