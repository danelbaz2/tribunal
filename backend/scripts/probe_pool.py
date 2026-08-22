"""Which free models can actually do this job?

The catalogue says what a model costs and what modalities it takes. It does not
say whether it can argue a case or return a verdict in the required form -- and
a run that discovers this seats a safety classifier as an advocate.

So ask. Each candidate is given the real work, twice:

1. the advocate prompt on the committed reference case -- did it produce a
   complete statement, or a refusal, a classification, or half an argument?
2. the judge prompt on four fixed statements -- did it return the required
   object, first time, without being asked twice?

The four statements are the same for every candidate, so the judging task is
identical across the bench. Sequential, because the free tier answers 429 to a
burst.

    cd backend && .venv/Scripts/python scripts/probe_pool.py

**What this ranks is reliability at the required form, not quality of
reasoning.** Whether a model argues *well* is not something this measures, and
no automatic score should be trusted to. It measures what makes runs fail.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.openrouter import OpenRouterClient, OpenRouterError  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.tribunal import advocates, judges  # noqa: E402
from app.tribunal.advocates import Statement  # noqa: E402
from app.tribunal.roles import BY_SLOT  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
OUT = FIXTURES / "pool_probe.json"

#: Fixed transcript material, so every candidate judges the same four
#: statements. Deliberately short: this probe measures whether a model returns
#: the required form, not how it handles length.
CANNED = {
    "advocate_against_1": (
        "The authorisation the procedure requires was not obtained, and the annex "
        "relied upon does not define the immediate risk it speaks of. The engineer "
        "decided alone that the condition was met, and the record of that decision "
        "is his own. A control that one person may invoke on their own judgement, "
        "and then record themselves, is not a control at all. The discharge reached "
        "a protected saltmarsh and closed a commercial lease for nine days."
    ),
    "advocate_against_2": (
        "No flooding was occurring on the eastern terrace at the time of the "
        "diversion. The prior flooding, eight days earlier, is not evidence of "
        "immediate risk on the night in question. The engineer had four failed "
        "call attempts logged over eight minutes, and stopped trying. Nothing in "
        "the record shows he attempted any other authority, and the station's "
        "annex names none. The harm that followed was certain; the harm avoided "
        "was assumed."
    ),
    "advocate_for_1": (
        "The controller's line was engaged for the entire eleven minutes, and the "
        "log records four attempts to reach it. Authorisation was not withheld; it "
        "was unobtainable. The annex, revised that spring, exists precisely for "
        "the case where authorisation cannot be had and property is at risk, and "
        "it instructs the duty engineer to act and record. He acted, restored the "
        "pump without instruction, and recorded the diversion himself."
    ),
    "advocate_for_2": (
        "The terrace on the eastern culvert had flooded eight days earlier in the "
        "same storm, on the third consecutive night of rain. A duty engineer who "
        "waits for a line that is engaged, while forty-one homes stand where two "
        "were flooded a week before, is not following a procedure but hiding "
        "behind one. He reported the event himself at the start of the following "
        "shift. That is the conduct of someone who expected to be examined."
    ),
}


@dataclass
class Result:
    model: str
    context_length: int = 0

    statement_ok: bool = False
    statement_words: int = 0
    statement_seconds: float = 0.0
    statement_finish: str | None = None
    statement_note: str = ""
    statement_head: str = ""

    judgment_ok: bool = False
    judgment_first_try: bool = False
    judgment_seconds: float = 0.0
    judgment_note: str = ""
    verdict: str | None = None
    reasons: int = 0

    @property
    def qualified(self) -> bool:
        """Can sit in any of the seven chairs.

        Both halves are required. A model that argues beautifully but cannot
        return the object fails every run it judges in, and the draw does not
        let anyone choose which chair a model takes."""
        return self.statement_ok and self.judgment_ok

    @property
    def rank_key(self) -> tuple:
        """Most reliable first, then fastest.

        Reliability before speed, deliberately: a slow model costs minutes, an
        unreliable one costs the whole run.
        """
        return (
            not self.qualified,
            not self.judgment_first_try,
            round(self.statement_seconds + self.judgment_seconds, 1),
        )


def canned_statements() -> list[Statement]:
    return [
        Statement(
            slot=slot,
            persona=BY_SLOT[slot].persona,
            model="probe",
            prompt="",
            text=text,
            words=len(text.split()),
            duration_ms=0,
            cost=0.0,
            temperature_requested=0.0,
            temperature_reported=None,
        )
        for slot, text in CANNED.items()
    ]


async def probe(client: OpenRouterClient, model: str, charge: str, min_words: int) -> Result:
    settings = get_settings()
    result = Result(model=model)

    # ── can it argue? ────────────────────────────────────────────────────
    prompt = advocates.build_prompt(
        BY_SLOT["advocate_against_1"], charge, settings.statement_target_words
    )
    started = time.perf_counter()
    try:
        answer = await client.complete(model, prompt)
        result.statement_seconds = round(time.perf_counter() - started, 1)
        result.statement_words = answer.words
        result.statement_finish = answer.finish_reason
        result.statement_head = " ".join(answer.text.split())[:110]
        if answer.words < min_words:
            result.statement_note = f"only {answer.words} words -- not a statement"
        else:
            result.statement_ok = True
    except OpenRouterError as error:
        result.statement_seconds = round(time.perf_counter() - started, 1)
        result.statement_note = str(error).split(": ", 1)[-1][:90]

    # ── can it rule in the required form? ────────────────────────────────
    # Judged as judge_1 -- the personas differ, but the task and the required
    # form are the same for all three chairs, and that is what is under test.
    statements = canned_statements()
    judging_slot = "judge_1"
    started = time.perf_counter()
    try:
        answer = await client.complete(model, judges.build_prompt(charge, statements, judging_slot))
        try:
            verdict, _confidence, reasons = judges.parse_ruling(answer.text)
            result.judgment_ok = result.judgment_first_try = True
            result.verdict, result.reasons = verdict, len(reasons)
        except judges.RulingFormatError as error:
            result.judgment_note = str(error)[:80]
            # Same second chance a real run gives it.
            retry = await client.complete(model, judges.build_retry_prompt(charge, statements, judging_slot))
            try:
                verdict, _confidence, reasons = judges.parse_ruling(retry.text)
                result.judgment_ok = True
                result.verdict, result.reasons = verdict, len(reasons)
                result.judgment_note = "needed the retry: " + result.judgment_note
            except judges.RulingFormatError as second:
                result.judgment_note = f"twice: {second}"[:90]
    except OpenRouterError as error:
        result.judgment_note = str(error).split(": ", 1)[-1][:90]
    result.judgment_seconds = round(time.perf_counter() - started, 1)

    return result


def render(results: list[Result]) -> None:
    qualified = [r for r in results if r.qualified]
    rejected = [r for r in results if not r.qualified]

    print("\n" + "=" * 78)
    print(f"QUALIFIED -- {len(qualified)} of {len(results)}, best first")
    print("=" * 78)
    print(f"{'#':>2}  {'model':<50} {'words':>6} {'sec':>6}  retry")
    for index, r in enumerate(qualified, 1):
        retry = "" if r.judgment_first_try else "yes"
        total = r.statement_seconds + r.judgment_seconds
        print(f"{index:>2}  {r.model:<50} {r.statement_words:>6} {total:>6.1f}  {retry}")

    if rejected:
        print("\n" + "-" * 78)
        print(f"NOT SEATABLE -- {len(rejected)}")
        print("-" * 78)
        for r in rejected:
            why = r.statement_note or r.judgment_note or "unknown"
            print(f"    {r.model:<50} {why}")
            if r.statement_head and not r.statement_ok:
                print(f'        answered: "{r.statement_head}"')

    if len(qualified) < 7:
        print(
            f"\n!! Only {len(qualified)} models qualified. Situation B needs 7 distinct "
            "models, so it cannot be run from this bench."
        )
    else:
        print("\nPaste into .env:\n")
        print("MODEL_POOL=" + json.dumps([r.model for r in qualified]))


async def main(only: list[str] | None) -> int:
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("No OPENROUTER_API_KEY.", file=sys.stderr)
        return 1

    charge = (FIXTURES / "reference_case.md").read_text(encoding="utf-8")

    async with OpenRouterClient(settings) as client:
        candidates = list(only) if only else list(
            await client.discover_free_pool(settings.min_context_length)
        )
        print(f"probing {len(candidates)} free models, one at a time\n")

        results: list[Result] = []
        for index, model in enumerate(candidates, 1):
            print(f"[{index}/{len(candidates)}] {model}", flush=True)
            result = await probe(client, model, charge, settings.min_statement_words)
            results.append(result)
            mark = "OK " if result.qualified else "no "
            detail = result.statement_note or result.judgment_note or ""
            print(
                f"        {mark} statement {result.statement_words}w "
                f"{result.statement_seconds}s | judgment "
                f"{'first try' if result.judgment_first_try else 'no'} "
                f"{result.judgment_seconds}s  {detail}",
                flush=True,
            )

    results.sort(key=lambda r: r.rank_key)
    render(results)

    OUT.write_text(
        json.dumps(
            {
                "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "ranked": [asdict(r) for r in results],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwritten to {OUT.relative_to(FIXTURES.parent)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="probe just these model ids")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.only)))
