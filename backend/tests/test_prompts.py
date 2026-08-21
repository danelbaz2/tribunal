"""Criterion 12 -- the prompts carry no case.

"Verifiable by reading two files." This is that reading, done by a machine so
it stays true after the next edit: three templates (against, for, judge)
rendered from two files, and no name, place, date or fact from any specific
case in any of them.
"""

from __future__ import annotations

import re

import pytest

from app.tribunal.advocates import build_prompt as advocate_prompt
from app.tribunal.judges import build_prompt as judge_prompt
from app.tribunal.prompts_loader import (
    judge_retry_template,
    judge_template,
    statement_template,
)
from app.tribunal.roles import BY_SLOT

TEMPLATES = {
    "statement.txt": statement_template(),
    "judge.txt": judge_template(),
    "judge.txt (retry)": judge_retry_template(),
}


@pytest.mark.parametrize("name", list(TEMPLATES))
def test_no_template_contains_a_date_or_a_time(name):
    body = TEMPLATES[name]
    assert not re.search(r"\b\d{1,2}:\d{2}\b", body), "a clock time"
    assert not re.search(r"\b(19|20)\d{2}\b", body), "a year"
    assert not re.search(
        r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        body,
    ), "a calendar date"


@pytest.mark.parametrize("name", list(TEMPLATES))
def test_no_template_contains_a_word_from_the_reference_case(name, reference_charge):
    """The strongest available form of "contains no fact from any case": take
    the distinctive words of the committed case and require their absence.

    Distinctive means capitalised mid-sentence or numeric -- names, places,
    quantities. If the reference case is replaced, this test re-derives its
    own list and keeps holding.
    """
    body = TEMPLATES[name].lower()

    distinctive = {
        word.strip(".,;:'\"()")
        for word in re.findall(r"\b[A-Z][a-zA-Z'-]{3,}\b", reference_charge)
    }
    # Words any English instruction may legitimately use.
    ordinary = {
        "The", "This", "That", "There", "Where", "During", "Policy", "Station",
        "Standing", "Their", "Each", "Every", "None", "Both", "After", "Before",
        "Nothing", "Which", "While", "Whether", "Written", "November",
    }
    distinctive -= ordinary

    present = sorted(w for w in distinctive if re.search(rf"\b{re.escape(w.lower())}\b", body))
    assert not present, f"{name} names case material: {present}"


@pytest.mark.parametrize("name", list(TEMPLATES))
def test_no_template_names_a_model_or_a_vendor(name):
    """Read against a real captured catalogue rather than a written pool: the
    pool is discovered at startup now, so there is no list to go stale."""
    import json
    from pathlib import Path

    catalogue = json.loads(
        (Path(__file__).parent / "data" / "openrouter_models.json").read_text(encoding="utf-8")
    )["data"]

    body = TEMPLATES[name].lower()
    for entry in catalogue:
        identifier = entry["id"]
        if not isinstance(identifier, str):
            continue
        assert identifier.lower() not in body
        assert identifier.split("/")[0].lower() not in body


def test_the_two_advocate_prompts_differ_only_in_the_position(reference_charge):
    """The same file serves all four advocates. If a per-side prompt ever
    diverged beyond the position, the two sides would stop being comparable."""
    against = advocate_prompt(BY_SLOT["advocate_against_1"], reference_charge, 300)
    for_ = advocate_prompt(BY_SLOT["advocate_for_1"], reference_charge, 300)

    assert against.replace("not justified", "justified") == for_


def test_the_four_advocates_share_one_prompt_per_side(reference_charge):
    first = advocate_prompt(BY_SLOT["advocate_against_1"], reference_charge, 300)
    second = advocate_prompt(BY_SLOT["advocate_against_2"], reference_charge, 300)

    assert first == second


def test_the_charge_file_cannot_reshape_the_instruction():
    """A charge file containing braces is text, not a format string."""
    hostile = "{transcript} {charge} {position_phrase} " + "x " * 30

    rendered = advocate_prompt(BY_SLOT["advocate_for_1"], hostile, 300)

    assert hostile in rendered
    assert rendered.count("BEGIN CHARGE FILE") == 1


def test_the_judge_prompt_states_the_required_form_and_forbids_inference(reference_charge):
    body = judge_prompt(reference_charge, [])

    assert '"verdict"' in body
    assert '"confidence"' in body
    assert '"reasons"' in body
    assert "never guessed from your prose" in body
