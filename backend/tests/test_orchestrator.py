"""Criteria 1, 2, 3 and 7 -- what a run is, and when it is not one."""

from __future__ import annotations

import pytest

from app.tribunal.judges import RulingFormatError
from app.tribunal.orchestrator import run_trial
from app.tribunal.roles import ADVOCATE_SLOTS, BY_SLOT, JUDGE_SLOTS
from conftest import ScriptedCaller, content_of, ruling_json


def full_script(roster: dict[str, str], verdicts=("justified", "justified", "not_justified")):
    answers = {roster[slot]: f"Statement from {slot}." for slot in ADVOCATE_SLOTS}
    for slot, verdict in zip(JUDGE_SLOTS, verdicts, strict=True):
        answers[roster[slot]] = ruling_json(verdict, 0.7)
    return answers


async def test_a_finished_run_is_exactly_seven_calls(reference_charge, roster_different):
    """Criteria 1 and 2."""
    caller = ScriptedCaller(full_script(roster_different))

    trial = await run_trial(reference_charge, roster_different, call=caller, target_words=300)

    assert trial.status == "finished"
    assert len(trial.statements) == 4
    assert len(trial.rulings) == 3

    positions = [BY_SLOT[s.slot].position for s in trial.statements]
    assert positions.count("not_justified") == 2
    assert positions.count("justified") == 2


async def test_the_three_verdicts_always_sum_to_three(reference_charge, roster_different):
    """Criterion 3."""
    caller = ScriptedCaller(full_script(roster_different))

    trial = await run_trial(reference_charge, roster_different, call=caller, target_words=300)

    assert trial.justified_count + trial.not_justified_count == 3
    assert (trial.justified_count, trial.not_justified_count) == (2, 1)


async def test_slots_come_back_in_fixed_order_not_in_order_of_arrival(
    reference_charge, roster_different
):
    caller = ScriptedCaller(full_script(roster_different))

    trial = await run_trial(reference_charge, roster_different, call=caller, target_words=300)

    assert [s.slot for s in trial.statements] == list(ADVOCATE_SLOTS)
    assert [r.slot for r in trial.rulings] == list(JUDGE_SLOTS)


async def test_stage_two_does_not_begin_until_all_four_statements_exist(
    reference_charge, roster_different
):
    """The stage boundary is real. Every judge reads the whole room or none of
    them does."""
    order: list[str] = []

    class Watcher:
        async def call_started(self, slot, stage, model):
            order.append(f"start:{stage}")

        async def call_progress(self, slot, text): ...

        async def statement_done(self, statement):
            order.append("done:statement")

        async def ruling_done(self, ruling):
            order.append("done:judgment")

        async def stage_failed(self, failures): ...

    caller = ScriptedCaller(full_script(roster_different))
    await run_trial(
        reference_charge,
        roster_different,
        call=caller,
        target_words=300,
        observer=Watcher(),
    )

    first_judgment_start = order.index("start:judgment")
    assert order[:first_judgment_start].count("done:statement") == 4


# ── the failure paths ────────────────────────────────────────────────────


async def test_an_advocate_that_never_returns_fails_the_whole_run(
    reference_charge, roster_different, broken
):
    """`advocate_timeout.json`. Never a three-statement run (criterion 7)."""
    envelope = broken("advocate_timeout")
    answers = full_script(roster_different)
    answers[roster_different["advocate_for_2"]] = TimeoutError(envelope["failure"])

    trial = await run_trial(reference_charge, roster_different, call=answers_caller(answers),
                            target_words=300)

    assert trial.status == "failed"
    assert trial.rulings == []  # stage 2 never opened
    assert [f.slot for f in trial.failures] == ["advocate_for_2"]
    assert trial.failures[0].model == roster_different["advocate_for_2"]


async def test_a_judge_that_will_not_state_a_verdict_fails_the_whole_run(
    reference_charge, roster_different, broken
):
    """`judge_prose.json`, twice. One retry, then the run is failed -- and the
    two judges who did rule are not kept as a result."""
    prose = content_of(broken("judge_prose"))
    answers = full_script(roster_different)
    answers[roster_different["judge_3"]] = [prose, prose]

    trial = await run_trial(reference_charge, roster_different, call=answers_caller(answers),
                            target_words=300)

    assert trial.status == "failed"
    assert [f.slot for f in trial.failures] == ["judge_3"]
    assert "required form" in trial.failures[0].message


async def test_every_failure_of_a_stage_is_reported_not_only_the_first(
    reference_charge, roster_different
):
    """Situation B has seven chances to botch the schema where A has one. Which
    slots failed on which models is the finding."""
    answers = full_script(roster_different)
    answers[roster_different["advocate_against_1"]] = TimeoutError("timed out")
    answers[roster_different["advocate_for_1"]] = TimeoutError("timed out")

    trial = await run_trial(reference_charge, roster_different, call=answers_caller(answers),
                            target_words=300)

    assert trial.status == "failed"
    assert {f.slot for f in trial.failures} == {"advocate_against_1", "advocate_for_1"}


async def test_a_failed_run_never_reaches_finished(reference_charge, roster_different):
    """Criterion 7, stated as plainly as it can be."""
    answers = full_script(roster_different)
    answers[roster_different["judge_1"]] = RulingFormatError("nope")

    trial = await run_trial(reference_charge, roster_different, call=answers_caller(answers),
                            target_words=300)

    assert trial.status != "finished"
    assert trial.status == "failed"


def answers_caller(answers: dict) -> ScriptedCaller:
    return ScriptedCaller(answers)


@pytest.mark.parametrize("situation", ["identical", "different"])
async def test_both_situations_run_the_same_way(reference_charge, situation):
    """The same prompt serves all seven slots, in both situations. A run in A
    and a run in B differ in the roster and in nothing else."""
    from app.tribunal.roster import draw_roster

    pool = tuple(f"test/model-{n}:free" for n in range(1, 10))
    roster = draw_roster("fixed-seed", pool, situation)

    answers: dict[str, object] = {}
    for slot in ADVOCATE_SLOTS:
        answers.setdefault(roster[slot], f"A statement about the case.")
    for slot in JUDGE_SLOTS:
        answers[roster[slot]] = ruling_json("justified", 0.5)

    caller = ScriptedCaller(answers)
    trial = await run_trial(reference_charge, roster, call=caller, target_words=300)

    assert trial.status == "finished"
    assert len(set(roster.values())) == (1 if situation == "identical" else 7)

    # Whatever the bench, the four advocate prompts are the same four prompts.
    advocate_prompts = {
        prompt for model, prompt in caller.prompts if "BEGIN STATEMENTS" not in prompt
    }
    assert len(advocate_prompts) == 2  # one per position, four slots
