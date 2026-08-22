"""Criterion 5: one model in every chair, or seven distinct ones."""

from __future__ import annotations

import pytest

from app.tribunal.roles import ALL_SLOTS
from app.tribunal.roster import BenchTooSmall, seat_bench

# Deliberately in reverse alphabetical order, so a test that passes because
# the code happened to sort cannot pass here.
RANKED = (
    "zulu/rank-one:free",
    "yankee/rank-two:free",
    "xray/rank-three:free",
    "whiskey/rank-four:free",
    "victor/rank-five:free",
    "uniform/rank-six:free",
    "tango/rank-seven:free",
    "sierra/spare-eight:free",
    "romeo/spare-nine:free",
)


def test_identical_seats_one_model_seven_times():
    bench = seat_bench(RANKED, "identical")

    assert set(bench) == set(ALL_SLOTS)
    assert set(bench.values()) == {RANKED[0]}


def test_different_seats_the_first_seven_in_order():
    bench = seat_bench(RANKED, "different")

    assert set(bench) == set(ALL_SLOTS)
    assert len(set(bench.values())) == len(ALL_SLOTS)
    assert [bench[slot] for slot in ALL_SLOTS] == list(RANKED[:7])


def test_the_spares_sit_out_until_needed():
    bench = seat_bench(RANKED, "different")

    assert RANKED[7] not in bench.values()
    assert RANKED[8] not in bench.values()


@pytest.mark.parametrize("situation", ["identical", "different"])
def test_the_same_pool_seats_the_same_bench(situation):
    assert seat_bench(RANKED, situation) == seat_bench(RANKED, situation)


def test_order_is_the_ranking_and_is_never_sorted_away():
    bench = seat_bench(RANKED, "identical")

    assert set(bench.values()) == {RANKED[0]}
    assert min(RANKED) != RANKED[0], "the fixture must not be alphabetical or it proves nothing"


def test_a_duplicate_entry_does_not_take_two_chairs():
    bench = seat_bench(("a:free", "a:free", *RANKED), "different")

    assert len(set(bench.values())) == len(ALL_SLOTS)


def test_a_bench_that_cannot_be_seated_says_so():
    with pytest.raises(BenchTooSmall, match="chairs need distinct"):
        seat_bench(RANKED[:4], "different")


def test_identical_needs_only_one_model():
    """A tier down to a single model can still run `identical`. Refusing both
    would throw away the run that is still possible."""
    bench = seat_bench(("only/one:free",), "identical")

    assert set(bench.values()) == {"only/one:free"}


def test_an_empty_pool_seats_nothing():
    with pytest.raises(BenchTooSmall, match="pool is empty"):
        seat_bench((), "identical")
