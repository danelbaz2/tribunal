"""Capture the control case. Run once, by a human, with a key.

Seven real OpenRouter calls are made against `fixtures/reference_case.md` and
the raw responses are written to `fixtures/responses/`. From then on the test
suite replays those files: no network, no cost, identical every run.

**Run this once.** Re-capturing silently changes what every test means -- these
files are the control against which everything else is measured, so replacing
them is a decision to be stated out loud and committed on its own, not a
refresh to be done because a run looked odd.

    cd backend && python scripts/capture_fixtures.py
    cd backend && python scripts/capture_fixtures.py --situation identical

The draw is Situation B by default: seven distinct models, so the captured
fixtures carry seven real response shapes rather than one repeated seven times.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.openrouter import OpenRouterClient, OpenRouterError  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.tribunal import advocates, judges  # noqa: E402
from app.tribunal.roles import ADVOCATE_SLOTS, BY_SLOT, JUDGE_SLOTS  # noqa: E402
from app.tribunal.roster import draw_roster, new_seed  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RESPONSES = FIXTURES / "responses"


def _write(slot: str, model: str, prompt: str, response: dict, duration_ms: int) -> None:
    body = {
        "slot": slot,
        "model": model,
        "prompt": prompt,
        "response": response,
        "duration_ms": duration_ms,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path = RESPONSES / f"{slot}.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(FIXTURES.parent)}")


async def capture(situation: str, seed: str) -> int:
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("No OPENROUTER_API_KEY. Copy .env.example to .env and set it.", file=sys.stderr)
        return 1

    charge = (FIXTURES / "reference_case.md").read_text(encoding="utf-8")
    roster = draw_roster(seed, settings.model_pool, situation)

    print(f"seed {seed}  situation {situation}")
    for slot, model in roster.items():
        print(f"  {slot:<20} {model}")

    RESPONSES.mkdir(parents=True, exist_ok=True)

    async with OpenRouterClient(settings) as client:
        print("\nstage 1 -- four statements")
        statements = []
        for slot in ADVOCATE_SLOTS:
            role = BY_SLOT[slot]
            prompt = advocates.build_prompt(role, charge, settings.statement_target_words)
            completion = await client.complete(roster[slot], prompt)
            _write(slot, roster[slot], prompt, completion.raw, completion.duration_ms)
            statements.append(
                advocates.Statement(
                    slot=slot,
                    persona=role.persona,
                    model=roster[slot],
                    prompt=prompt,
                    text=completion.text,
                    words=completion.words,
                    duration_ms=completion.duration_ms,
                    cost=completion.cost,
                    temperature_requested=completion.temperature_requested,
                    temperature_reported=completion.temperature_reported,
                )
            )

        print("\nstage 2 -- three judgments")
        prompt = judges.build_prompt(charge, statements)
        for slot in JUDGE_SLOTS:
            completion = await client.complete(roster[slot], prompt)
            _write(slot, roster[slot], prompt, completion.raw, completion.duration_ms)
            # Report, do not correct. A judge that answered badly is part of
            # what the control case is for; damaged copies belong in broken/
            # and are made by hand, not by a re-run.
            try:
                verdict, confidence, reasons = judges.parse_ruling(completion.text)
                print(f"    {slot}: {verdict} ({confidence}) with {len(reasons)} reasons")
            except judges.RulingFormatError as error:
                print(f"    {slot}: DID NOT PARSE -- {error}")

    (RESPONSES / "capture.json").write_text(
        json.dumps(
            {
                "seed": seed,
                "situation": situation,
                "roster": roster,
                "pool": list(settings.model_pool),
                "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("\nDone. Commit fixtures/responses/ as its own change.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--situation", choices=("identical", "different"), default="different")
    parser.add_argument("--seed", default=None, help="reuse a seed to redraw the same bench")
    args = parser.parse_args()

    if RESPONSES.exists() and any(RESPONSES.glob("*.json")):
        print(
            "fixtures/responses/ already holds captures. They are the control case.\n"
            "Delete them deliberately, and say why in the commit, before capturing again.",
            file=sys.stderr,
        )
        return 1

    try:
        return asyncio.run(capture(args.situation, args.seed or new_seed()))
    except OpenRouterError as error:
        print(f"OpenRouter: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
