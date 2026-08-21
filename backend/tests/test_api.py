"""The contract the frontend reads.

Offline: the run reaches its models through `runner.caller_factory`, which is
replaced here by a replay. No network, no key, no PostgreSQL -- the suite runs
against a throwaway SQLite file set up in `conftest.py`.

The field names asserted below are camelCase on purpose. That is what
`frontend/src/types.ts` reads, and a rename on either side should break a test
rather than a screen.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from app import runner
from app.database import create_tables, engine
from app.main import app
from app.models import Base
from app.tribunal.roles import ADVOCATE_SLOTS, ALL_SLOTS, JUDGE_SLOTS
from conftest import ScriptedCaller, ruling_json

VERDICTS = ("justified", "justified", "not_justified")


@pytest.fixture
async def api():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await create_tables()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def replay(monkeypatch):
    """Seat a scripted bench in place of OpenRouter."""

    def install(answers_for: dict[str, object] | None = None) -> ScriptedCaller:
        caller: ScriptedCaller | None = None

        @asynccontextmanager
        async def factory():
            nonlocal caller
            caller = _caller(answers_for)
            yield caller

        monkeypatch.setattr(runner, "caller_factory", factory)
        return factory

    return install


def _caller(overrides: dict[str, object] | None) -> ScriptedCaller:
    from app.config import get_settings
    from app.tribunal.roster import draw_roster

    # Every model in the pool gets an answer, whichever way the draw fell.
    pool = get_settings().model_pool
    answers: dict[str, object] = {}
    for model in pool:
        answers[model] = "A statement of about three hundred words would go here."

    # Judges answer in the required form. The draw decides which models sit as
    # judges, so every model must be able to answer as one.
    for index, model in enumerate(pool):
        answers[model] = [
            answers[model],
            ruling_json(VERDICTS[index % 3], 0.7),
        ]

    del draw_roster
    if overrides:
        answers.update(overrides)
    return ScriptedCaller(answers)


async def create_case(api: httpx.AsyncClient, text: str) -> dict:
    response = await api.post("/api/cases", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


async def wait_for(api: httpx.AsyncClient, run_id: int, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        body = (await api.get(f"/api/runs/{run_id}")).json()
        if body["status"] != "running":
            return body
        await asyncio.sleep(0.05)
    raise AssertionError(f"run {run_id} was still running after {timeout}s")


# ── cases ────────────────────────────────────────────────────────────────


async def test_a_charge_is_stored_and_its_extraction_reported(api, reference_charge):
    body = await create_case(api, reference_charge)

    assert set(body) == {"caseId", "title", "wordCount", "pages", "hasTextLayer"}
    assert body["wordCount"] > 100
    assert body["hasTextLayer"] is True


async def test_a_charge_that_accuses_nobody_is_refused_at_upload(api):
    response = await api.post("/api/cases", json={"text": "Hello."})

    assert response.status_code == 422
    assert "too short" in response.json()["detail"]


# ── runs ─────────────────────────────────────────────────────────────────


async def test_convening_creates_seven_waiting_rows(api, reference_charge, replay):
    replay()
    case = await create_case(api, reference_charge)

    body = (
        await api.post("/api/runs", json={"case_id": case["caseId"], "situation": "different"})
    ).json()

    assert body["status"] == "running"
    assert [call["slot"] for call in body["calls"]] == list(ALL_SLOTS)
    assert len(body["roster"]) == 7
    await wait_for(api, body["id"])


async def test_a_run_reaches_the_count_without_being_asked_again(
    api, reference_charge, replay
):
    """No human in the loop after convening: stage 1, stage 2, result."""
    replay()
    case = await create_case(api, reference_charge)
    started = (
        await api.post("/api/runs", json={"case_id": case["caseId"], "situation": "different"})
    ).json()

    finished = await wait_for(api, started["id"])

    assert finished["status"] == "finished"
    assert len(finished["calls"]) == 7
    assert all(call["status"] == "done" for call in finished["calls"])

    verdicts = [c["verdict"] for c in finished["calls"] if c["stage"] == "judgment"]
    assert len(verdicts) == 3
    assert verdicts.count("justified") + verdicts.count("not_justified") == 3


async def test_the_run_carries_the_fields_the_courtroom_reads(
    api, reference_charge, replay
):
    replay()
    case = await create_case(api, reference_charge)
    started = (
        await api.post("/api/runs", json={"case_id": case["caseId"], "situation": "identical"})
    ).json()
    finished = await wait_for(api, started["id"])

    assert {"id", "caseId", "caseTitle", "status", "situation", "seed", "roster",
            "startedAt", "finishedAt", "calls"} <= set(finished)

    statement = next(c for c in finished["calls"] if c["slot"] in ADVOCATE_SLOTS)
    assert {"slot", "stage", "model", "status", "text", "words", "durationMs",
            "cost", "error"} <= set(statement)
    assert statement["words"] > 0

    judgment = next(c for c in finished["calls"] if c["slot"] in JUDGE_SLOTS)
    assert judgment["verdict"] in {"justified", "not_justified"}
    assert 0.0 <= judgment["confidence"] <= 1.0
    assert len(judgment["reasons"]) >= 2


async def test_situation_a_seats_one_model_and_b_seats_seven(
    api, reference_charge, replay
):
    """Criterion 5, end to end."""
    replay()
    case = await create_case(api, reference_charge)

    for situation, expected in (("identical", 1), ("different", 7)):
        started = (
            await api.post(
                "/api/runs", json={"case_id": case["caseId"], "situation": situation}
            )
        ).json()
        finished = await wait_for(api, started["id"])
        assert len({call["model"] for call in finished["calls"]}) == expected


async def test_a_failed_call_fails_the_run_and_names_the_slot(
    api, reference_charge, replay, monkeypatch
):
    """Criterion 7, and pitfall 4: which slot failed on which model is
    surfaced, so a re-run is one click."""
    from app.config import get_settings

    broken_model = get_settings().model_pool[0]
    replay({broken_model: TimeoutError("the model never answered")})

    case = await create_case(api, reference_charge)
    started = (
        await api.post("/api/runs", json={"case_id": case["caseId"], "situation": "different"})
    ).json()
    finished = await wait_for(api, started["id"])

    assert finished["status"] == "failed"
    failed = [call for call in finished["calls"] if call["status"] == "failed"]
    assert failed, "the failing slot must be recorded, not swallowed"
    assert all(call["error"] for call in failed)
    assert any(call["model"] == broken_model for call in failed)


async def test_an_unknown_run_is_a_404(api):
    assert (await api.get("/api/runs/4242")).status_code == 404
