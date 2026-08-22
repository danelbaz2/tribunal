"""Reads the prompt files.

The instructions live in `prompts/` as text, not as strings in Python, for two
reasons. They are the single biggest factor in the quality of the results and
the thing most often adjusted, so they should be editable without touching
code. And the case-independence rule is *checked* by reading them: open the two
files and confirm that no name, crime, country, date or fact from any specific
case appears. The proof fits on one screen (criterion 12).

Substitution is by literal token replacement, not `str.format`, because a
charge file may contain braces of its own and a case must never be able to
change the shape of the instruction that carries it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

#: Splits `judge.txt` into the prompt proper and the restatement used on the
#: one format retry. Both are text in the same file, so a reader sees together
#: everything a judge can ever be told.
RETRY_MARKER = "--- RETRY ---"


@lru_cache
def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


@lru_cache
def persona_brief(slot: str) -> str:
    """The voice one slot argues or rules in.

    Seven files, one per chair. They carry manner and method only: what to
    press, what to concede, how to read a rule. The task, the output contract,
    the target length and the charge file itself live in the shared template,
    so what can make a call *fail* is identical for all seven.

    Personas are fixed for every run, a constant of the experiment rather than
    a variable in it.
    """
    return (PROMPTS_DIR / "personas" / f"{slot}.txt").read_text(encoding="utf-8").strip()


def statement_template() -> str:
    return _read("statement.txt")


def judge_template() -> str:
    return _read("judge.txt").split(RETRY_MARKER, 1)[0].rstrip() + "\n"


def judge_retry_template() -> str:
    body = _read("judge.txt")
    if RETRY_MARKER not in body:
        raise ValueError(f"judge.txt has no {RETRY_MARKER!r} section")
    return body.split(RETRY_MARKER, 1)[1].strip() + "\n"


def fill(template: str, **values: str) -> str:
    """Replace `{name}` tokens literally, leaving any other braces alone."""
    filled = template
    for name, value in values.items():
        filled = filled.replace("{" + name + "}", value)
    return filled
