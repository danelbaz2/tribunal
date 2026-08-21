"""Criteria 9, 10 and 11 -- the project's core requirement.

Every assertion here reads the **captured prompt text**: what the code actually
sent. A test that read the template instead would pass forever while the
orchestrator quietly passed a judge somebody else's opinion.
"""

from __future__ import annotations

import pytest

from app.tribunal.orchestrator import run_trial
from app.tribunal.roles import ADVOCATE_SLOTS, JUDGE_SLOTS
from conftest import ScriptedCaller, ruling_json

STATEMENTS = {
    "advocate_against_1": "VEGA-STATEMENT the diversion was avoidable and unlogged.",
    "advocate_against_2": "LYRA-STATEMENT the record cannot be checked by a second person.",
    "advocate_for_1": "ORION-STATEMENT the authorisation channel was itself unavailable.",
    "advocate_for_2": "DRACO-STATEMENT the annex contemplates exactly this event.",
}

RULINGS = {
    "judge_1": ruling_json("justified", 0.78),
    "judge_2": ruling_json("justified", 0.61),
    "judge_3": ruling_json("not_justified", 0.71),
}


@pytest.fixture
async def held(reference_charge, roster_different):
    answers = {
        roster_different[slot]: text
        for slot, text in (STATEMENTS | RULINGS).items()
    }
    caller = ScriptedCaller(answers)
    trial = await run_trial(
        reference_charge, roster_different, call=caller, target_words=300
    )
    assert trial.status == "finished"
    return trial, caller, roster_different


async def test_no_advocate_is_sent_another_advocates_output(held):
    """Criterion 10."""
    _, caller, roster = held

    for slot in ADVOCATE_SLOTS:
        sent = "\n".join(caller.prompts_for(roster[slot]))
        others = [text for other, text in STATEMENTS.items() if other != slot]
        for other_statement in others:
            assert other_statement not in sent


async def test_no_judge_is_sent_another_judges_output(held):
    """Criterion 9."""
    _, caller, roster = held

    for slot in JUDGE_SLOTS:
        sent = "\n".join(caller.prompts_for(roster[slot]))
        for other, ruling in RULINGS.items():
            if other == slot:
                continue
            assert ruling not in sent
            # Not the whole object, and not the verdict word paired with the
            # other judge's confidence either.
            assert f'"confidence": {ruling.split("confidence")[1][2:6]}' not in sent


async def test_no_judge_is_sent_a_model_identifier(held):
    """Criterion 11 -- for every model in the pool, that string is absent."""
    _, caller, roster = held
    pool = set(roster.values())

    for slot in JUDGE_SLOTS:
        sent = "\n".join(caller.prompts_for(roster[slot]))
        for model in pool:
            assert model not in sent
        # Nor the bare vendor, which would narrow it just as well.
        for vendor in {model.split("/")[0] for model in pool}:
            assert vendor not in sent


async def test_every_judge_is_sent_all_four_statements(held):
    """The other half of the same rule: a judge reads the whole room."""
    _, caller, roster = held

    for slot in JUDGE_SLOTS:
        sent = "\n".join(caller.prompts_for(roster[slot]))
        for statement in STATEMENTS.values():
            assert statement in sent


async def test_the_judges_all_read_the_same_transcript(held):
    """Three judges, one room. If they differ, they are not comparable."""
    _, caller, roster = held

    prompts = {caller.prompts_for(roster[slot])[0] for slot in JUDGE_SLOTS}
    assert len(prompts) == 1


async def test_a_judge_is_never_told_which_chair_it_sits_in(held):
    """Slot names are internal. A judge told it is `judge_3` learns that two
    others exist."""
    _, caller, roster = held

    for slot in JUDGE_SLOTS:
        sent = "\n".join(caller.prompts_for(roster[slot]))
        for name in JUDGE_SLOTS:
            assert name not in sent
