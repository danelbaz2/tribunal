"""Send one chair's real prompt to one model, once, and show what came back.

`probe_pool.py` always argues `advocate_against_1` ("not justified") on the
Kestrel case -- so it never exercises the seat that has been failing: an
advocate on the *justified* side, on the violent default charge, and in
particular `advocate_for_1`, which asks the model to be the named killer and
argue his killing was justified.

This isolates that. Pick a slot, a model, and a charge; it builds the exact
prompt the orchestrator would send and prints the outcome -- a complete
statement, a refusal caught as `NotAStatement`, or the raw gateway error.

    cd backend && .venv/Scripts/python scripts/probe_slot.py \
        --slot advocate_for_1 --model dots-studio/dots-3-note-preview:free

    # the whole "justified" side, and both "against" seats for contrast:
    cd backend && .venv/Scripts/python scripts/probe_slot.py \
        --model dots-studio/dots-3-note-preview:free --all-advocates
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import charge_file  # noqa: E402
from app.ai.openrouter import OpenRouterClient, OpenRouterError  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.tribunal import advocates, judges  # noqa: E402
from app.tribunal.roles import ADVOCATE_SLOTS, BY_SLOT  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def build(slot: str, charge: str, target_words: int) -> str:
    role = BY_SLOT[slot]
    if role.stage == "statement":
        return advocates.build_prompt(role, charge, target_words)
    # A judge needs a transcript; reuse the canned one from probe_pool.
    from probe_pool import canned_statements

    return judges.build_prompt(charge, canned_statements(), slot)


async def probe_slot(client: OpenRouterClient, slot: str, model: str, charge: str) -> None:
    settings = get_settings()
    prompt = build(slot, charge, settings.statement_target_words)
    role = BY_SLOT[slot]

    print(f"\n── {slot}  ({role.persona}, {role.position or 'judge'})  on {model}")
    started = time.perf_counter()
    try:
        answer = await client.complete(model, prompt)
    except OpenRouterError as error:
        secs = time.perf_counter() - started
        print(f"   FAILED after {secs:4.1f}s")
        print(f"   error: {error}")
        return

    secs = time.perf_counter() - started
    head = " ".join(answer.text.split())
    print(f"   returned {answer.words} words in {secs:4.1f}s, finish={answer.finish_reason}")
    if role.stage == "statement" and answer.words < settings.min_statement_words:
        print(f"   -> NotAStatement (floor is {settings.min_statement_words} words)")
    print(f'   text: "{head[:400]}"')
    if len(head) > 400:
        print(f'   ...tail: "{head[-200:]}"')


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--slot", help="one slot, e.g. advocate_for_1 or judge_1")
    parser.add_argument(
        "--all-advocates", action="store_true", help="all four advocate seats, in order"
    )
    parser.add_argument(
        "--charge",
        default="default",
        help="'default' (the Jon Snow sheet), 'reference' (Kestrel), or a file path",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openrouter_api_key:
        print("No OPENROUTER_API_KEY.", file=sys.stderr)
        return 1

    if args.charge == "default":
        charge = charge_file.default_charge().text
    elif args.charge == "reference":
        charge = (FIXTURES / "reference_case.md").read_text(encoding="utf-8")
    else:
        charge = Path(args.charge).read_text(encoding="utf-8")

    if args.all_advocates:
        slots = list(ADVOCATE_SLOTS)
    elif args.slot:
        slots = [args.slot]
    else:
        parser.error("give --slot or --all-advocates")

    # Sequential on purpose: this is about content, not concurrency.
    async with OpenRouterClient(settings) as client:
        for slot in slots:
            await probe_slot(client, slot, args.model, charge)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
