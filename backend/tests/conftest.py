"""Test scaffolding.

Everything here runs with **no network and no API key**. If a test needs
either, it is written wrong: the control case is replayed from
`fixtures/`, never re-requested.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "fixtures"
RESPONSES = FIXTURES / "responses"
BROKEN = FIXTURES / "broken"

# Point the app at a throwaway SQLite file before anything imports the engine.
# A test must never be able to reach the real database, and there is no
# PostgreSQL on a machine that is only running the suite.
_DB_FILE = Path(tempfile.gettempdir()) / "tribunal_tests.sqlite"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE.as_posix()}"
os.environ["OPENROUTER_API_KEY"] = ""


# ── the control case ──────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def reference_charge() -> str:
    return (FIXTURES / "reference_case.md").read_text(encoding="utf-8")


def load_envelope(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def content_of(envelope: dict) -> str:
    choices = envelope["response"]["choices"]
    return choices[0]["message"]["content"]


@pytest.fixture(scope="session")
def broken() -> Callable[[str], dict]:
    """One hand-damaged fixture, by file stem."""

    def load(name: str) -> dict:
        return load_envelope(BROKEN / f"{name}.json")

    return load


def captured_slots() -> list[Path]:
    """The seven real captures, if they have been taken yet."""
    if not RESPONSES.exists():
        return []
    return sorted(p for p in RESPONSES.glob("*.json") if p.stem != "capture")


needs_captures = pytest.mark.skipif(
    len(captured_slots()) < 7,
    reason=(
        "The 7 real responses have not been captured yet. "
        "Run `python scripts/capture_fixtures.py` once, with a key. "
        "See fixtures/README.md -- these are the control case."
    ),
)


# ── replaying a model without one ─────────────────────────────────────────


@dataclass
class FakeCompletion:
    """Structurally a `Completion`; carries no HTTP anywhere near a test."""

    model: str
    text: str
    duration_ms: int = 1000
    cost: float = 0.0
    temperature_requested: float = 0.0
    temperature_reported: float | None = None
    finish_reason: str | None = "stop"
    raw: dict = field(default_factory=dict)

    @property
    def words(self) -> int:
        return len(self.text.split())


class ScriptedCaller:
    """Answers by model identifier, in the order the answers were given.

    A value may be a string (the answer), an exception (a call that failed),
    or a list of either, consumed one per call -- which is how the judge's one
    format retry is exercised.

    Every prompt it is given is kept. The independence criteria are asserted
    against these captured prompts, never against the template.
    """

    def __init__(self, answers: dict[str, object]):
        self._answers = {model: self._as_queue(value) for model, value in answers.items()}
        self.prompts: list[tuple[str, str]] = []

    @staticmethod
    def _as_queue(value: object) -> list[object]:
        return list(value) if isinstance(value, list) else [value]

    def prompts_for(self, model: str) -> list[str]:
        return [prompt for sent_model, prompt in self.prompts if sent_model == model]

    async def __call__(self, model: str, prompt: str, on_chunk=None) -> FakeCompletion:
        self.prompts.append((model, prompt))

        queue = self._answers.get(model)
        if not queue:
            raise AssertionError(f"the script has no answer left for {model}")
        answer = queue.pop(0) if len(queue) > 1 else queue[0]

        if isinstance(answer, BaseException):
            raise answer

        text = str(answer)
        if on_chunk is not None:
            # Arrive in two pieces, so the writing state is really exercised.
            half = len(text) // 2
            await on_chunk(text[:half])
            await on_chunk(text)
        return FakeCompletion(model=model, text=text)


class BenchCaller(ScriptedCaller):
    """Answers whatever the prompt is asking for.

    Keyed on the role rather than on the model, so it works for any roster. A
    judge prompt is the one carrying the transcript.

    Overrides by model still win, which is how a single slot is broken in a
    test without breaking the bench.
    """

    def __init__(self, overrides: dict[str, object] | None = None):
        super().__init__(overrides or {})

    async def __call__(self, model: str, prompt: str, on_chunk=None) -> FakeCompletion:
        if model in self._answers:
            return await super().__call__(model, prompt, on_chunk=on_chunk)

        self.prompts.append((model, prompt))
        text = ruling_json() if "BEGIN STATEMENTS" in prompt else statement_text("A statement.")
        if on_chunk is not None:
            await on_chunk(text[: len(text) // 2])
            await on_chunk(text)
        return FakeCompletion(model=model, text=text)


@pytest.fixture
def scripted() -> Callable[[dict[str, object]], ScriptedCaller]:
    return ScriptedCaller


# ── a bench of stand-in models ────────────────────────────────────────────

#: Distinct per slot, so a scripted answer can be addressed to one chair.
TEST_POOL: tuple[str, ...] = tuple(f"test/model-{index}:free" for index in range(1, 10))


@pytest.fixture(autouse=True)
def _seated_pool():
    """Every test runs against a fixed stand-in pool, in place of the real
    hand-picked `MODEL_POOL`. Cleared afterwards so no test inherits
    another's bench."""
    from app import pool

    pool.clear()
    pool.set_pool(TEST_POOL)
    yield
    pool.clear()


@pytest.fixture
def roster_different() -> dict[str, str]:
    from app.tribunal.roles import ALL_SLOTS

    return dict(zip(ALL_SLOTS, TEST_POOL, strict=False))


#: Below this a call is not a statement at all -- see `advocates.NotAStatement`.
#: Test statements have to clear it, because a three-word answer is exactly
#: what the floor exists to catch.
MIN_STATEMENT_WORDS = 60


def statement_text(marker: str, words: int = 90) -> str:
    """A statement long enough to be one, carrying a searchable marker.

    The marker is what the independence tests look for: if it turns up in
    another slot's prompt, isolation is broken.
    """
    body = f"{marker} "
    filler = (
        "The record before this tribunal supports the position I am asked to argue, "
        "and the silences in it cut the same way. "
    )
    while len(body.split()) < words:
        body += filler
    return body.strip()


def ruling_json(verdict: str = "justified", confidence: float = 0.7, reasons: int = 2) -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "confidence": confidence,
            "reasons": [f"Reason number {n + 1}, stated plainly." for n in range(reasons)],
        }
    )
