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
from app.tribunal.roles import ADVOCATE_SLOTS, BY_SLOT, JUDGE_SLOTS

from app.tribunal.prompts_loader import persona_brief
from app.tribunal.roles import ALL_SLOTS

TEMPLATES = {
    "statement.txt": statement_template(),
    "judge.txt": judge_template(),
    "judge.txt (retry)": judge_retry_template(),
    **{f"personas/{slot}.txt": persona_brief(slot) for slot in ALL_SLOTS},
}

#: Splits a rendered prompt into the voice and the task. Everything after the
#: marker is shared; everything before it is one chair's own.
TASK_MARKER = "--- THE TASK, WHICH IS THE SAME FOR EVERY"


def task_half(prompt: str) -> str:
    assert TASK_MARKER in prompt, "the shared contract must be findable"
    return prompt.split(TASK_MARKER, 1)[1]


def voice_half(prompt: str) -> str:
    return prompt.split(TASK_MARKER, 1)[0]


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


def test_all_four_advocates_are_given_the_same_task(reference_charge):
    """The invariant that replaced "one prompt per side".

    Personas differ by chair; the task, the output rules, the target length and
    the charge file do not. So what can make a call *fail* is identical for all
    four, and a difference between two statements is a difference of voice, not
    of instruction.
    """
    tasks = {
        task_half(advocate_prompt(BY_SLOT[slot], reference_charge, 300)).replace(
            "not justified", "justified"
        )
        for slot in ADVOCATE_SLOTS
    }

    assert len(tasks) == 1


def test_the_two_sides_differ_only_in_the_position(reference_charge):
    against = task_half(advocate_prompt(BY_SLOT["advocate_against_1"], reference_charge, 300))
    for_ = task_half(advocate_prompt(BY_SLOT["advocate_for_1"], reference_charge, 300))

    assert against.replace("not justified", "justified") == for_


def test_every_advocate_argues_in_its_own_voice(reference_charge):
    """What this change is for. Before it, the two advocates on a side were
    sent the same prompt -- and at temperature 0 on one model they returned the
    same statement, so the tribunal had four chairs and two arguments.
    """
    voices = {
        voice_half(advocate_prompt(BY_SLOT[slot], reference_charge, 300))
        for slot in ADVOCATE_SLOTS
    }

    assert len(voices) == len(ADVOCATE_SLOTS)


def test_every_judge_rules_in_its_own_voice(reference_charge):
    voices = {voice_half(judge_prompt(reference_charge, [], slot)) for slot in JUDGE_SLOTS}

    assert len(voices) == len(JUDGE_SLOTS)


def test_all_three_judges_are_given_the_same_task(reference_charge):
    tasks = {task_half(judge_prompt(reference_charge, [], slot)) for slot in JUDGE_SLOTS}

    assert len(tasks) == 1


def test_no_persona_names_a_model_or_tells_a_chair_who_else_sits(reference_charge):
    """A persona shapes how one chair reasons. It must not tell that chair who
    the others are, or a judge learns another judge exists."""
    for slot in ALL_SLOTS:
        brief = persona_brief(slot).lower()
        for other in ALL_SLOTS:
            if other != slot:
                assert other not in brief


def test_the_charge_file_cannot_reshape_the_instruction():
    """A charge file containing braces is text, not a format string."""
    hostile = "{transcript} {charge} {position_phrase} " + "x " * 30

    rendered = advocate_prompt(BY_SLOT["advocate_for_1"], hostile, 300)

    assert hostile in rendered
    assert rendered.count("BEGIN CHARGE FILE") == 1


def test_the_judge_prompt_states_the_required_form_and_forbids_inference(reference_charge):
    body = judge_prompt(reference_charge, [], "judge_1")

    assert '"verdict"' in body
    assert '"confidence"' in body
    assert '"reasons"' in body
    assert "never guessed from your prose" in body
