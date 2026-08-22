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
from conftest import BenchCaller

@pytest.fixture
async def api():
    """A clean database, and an engine that never outlives its event loop.

    The engine is module-level and every test gets its own loop, so a pooled
    aiosqlite connection opened in one test and reused in the next fails with
    "Event loop is closed". Disposing at both ends keeps each test's
    connections inside the loop that made them.
    """
    await engine.dispose()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await create_tables()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # A run is a background task. Let it reach its end before the loop closes
    # under it -- reaching into `_tasks` because that is exactly what the
    # module keeps them for.
    pending = [task for task in runner._tasks if not task.done()]
    if pending:
        await asyncio.wait(pending, timeout=5)
    await engine.dispose()


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


def _caller(overrides: dict[str, object] | None) -> BenchCaller:
    """A bench that answers by role, so it works whichever models are seated."""
    return BenchCaller(overrides)


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


async def test_a_charge_arriving_as_a_file_is_stored(api, reference_charge):
    """The upload path, which the paste path does not exercise: one URL takes
    both, dispatched on content type, and a regression in either is invisible
    to the other."""
    response = await api.post(
        "/api/cases",
        files={"file": ("case.md", reference_charge.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["wordCount"] > 100
    assert body["hasTextLayer"] is True


async def test_an_uploaded_scan_is_refused_at_upload(api):
    """Pitfall 13, through the endpoint: a valid PDF with no text layer."""
    import io as _io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = _io.BytesIO()
    writer.write(buffer)

    response = await api.post(
        "/api/cases",
        files={"file": ("scan.pdf", buffer.getvalue(), "application/pdf")},
    )

    assert response.status_code == 422
    assert "No extractable text" in response.json()["detail"]


async def test_a_multipart_post_with_no_file_says_so(api):
    response = await api.post("/api/cases", files={"notafile": ("x.txt", b"hello")})

    assert response.status_code == 422


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
        await api.post("/api/runs", json={"case_id": case["caseId"], "situation": "different"})
    ).json()
    finished = await wait_for(api, started["id"])

    assert {"id", "caseId", "caseTitle", "status", "situation", "roster",
            "startedAt", "finishedAt", "calls"} <= set(finished)

    statement = next(c for c in finished["calls"] if c["slot"] in ADVOCATE_SLOTS)
    assert {"slot", "stage", "model", "status", "text", "words", "durationMs",
            "cost", "error"} <= set(statement)
    assert statement["words"] > 0

    judgment = next(c for c in finished["calls"] if c["slot"] in JUDGE_SLOTS)
    assert judgment["verdict"] in {"justified", "not_justified"}
    assert 0.0 <= judgment["confidence"] <= 1.0
    assert len(judgment["reasons"]) >= 2


async def test_identical_seats_one_model_and_different_seats_seven(
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
    surfaced, so a re-run is one click.

    Every model in the pool is broken rather than one, because the draw takes
    seven of however many the tier is offering -- singling out one model would
    pass or fail depending on whether it happened to be seated.
    """
    from app import pool as pool_module

    models = pool_module.get_pool()
    replay({model: TimeoutError("the model never answered") for model in models})

    case = await create_case(api, reference_charge)
    started = (
        await api.post("/api/runs", json={"case_id": case["caseId"], "situation": "different"})
    ).json()
    finished = await wait_for(api, started["id"])

    assert finished["status"] == "failed"

    failed = [call for call in finished["calls"] if call["status"] == "failed"]
    assert failed, "the failing slots must be recorded, not swallowed"
    for call in failed:
        assert call["error"], f"{call['slot']} failed without saying why"
        assert call["model"] in models, "the failing slot must name its model"

    # Stage 1 never completed, so no judge was ever asked.
    assert all(call["verdict"] is None for call in finished["calls"])


async def test_an_unknown_run_is_a_404(api):
    assert (await api.get("/api/runs/4242")).status_code == 404
