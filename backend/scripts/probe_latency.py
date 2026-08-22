"""How fast is each model on the bench?

`probe_pool.py` asks whether a model can do the job. This asks how quickly it
does anything at all -- a different question, and a much cheaper one: **one
call per model**, a trivial prompt, a small token budget.

It exists because the bench is ranked on reliability at the required form, and
reliability says nothing about speed. A real run showed the rank-1 model taking
44 seconds for one statement while a model called "lightning" sat at rank 9.

What it measures, and why that and not raw duration:

* **tokens per second** -- the part of a call that scales with how much the
  model writes. A real statement runs to ~550 tokens, so throughput is what
  decides whether a call takes 20 seconds or 90.
* **duration** on a fixed small task, which carries the queue wait and the
  prefill that throughput does not.

Ranking on throughput and reading duration beside it separates a model that is
slow because it is thinking from one that is slow because it is queued.

    cd backend && .venv/Scripts/python scripts/probe_latency.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.openrouter import OpenRouterClient, OpenRouterError  # noqa: E402
from app.config import get_settings  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "latency_probe.json"

#: A task every chat model can do, that produces a predictable amount of text
#: and requires no thought. The point is the rate, not the answer.
TASK = (
    "List the numbers from 1 to 40, separated by commas, on one line. "
    "Write nothing else."
)

#: Enough to measure a rate, far less than a statement costs.
BUDGET = 200

#: What a real statement runs to, measured. Used only to project the probe's
#: rate onto the work the model would actually be asked to do.
STATEMENT_TOKENS = 550


@dataclass
class Speed:
    model: str
    ok: bool = False
    seconds: float = 0.0
    tokens: int = 0
    thinking: int = 0
    note: str = ""

    @property
    def per_second(self) -> float:
        return self.tokens / self.seconds if self.ok and self.seconds > 0 else 0.0

    @property
    def projected_statement_seconds(self) -> float:
        """What one real statement would cost at this rate.

        A projection, not a measurement: it assumes the rate holds at length
        and ignores the queue wait, which does not scale. Treat it as an
        ordering, not a promise.
        """
        return STATEMENT_TOKENS / self.per_second if self.per_second else 0.0


async def measure(client: OpenRouterClient, model: str) -> Speed:
    result = Speed(model=model)
    started = time.perf_counter()
    try:
        answer = await client.complete(model, TASK)
        result.seconds = round(time.perf_counter() - started, 2)
        result.tokens = answer.tokens or answer.words
        result.thinking = answer.thinking_tokens or 0
        result.ok = result.tokens > 0
        if not result.ok:
            result.note = "answered nothing measurable"
    except OpenRouterError as error:
        result.seconds = round(time.perf_counter() - started, 2)
        result.note = str(error).split(": ", 1)[-1][:90]
    return result


async def main(only: list[str] | None) -> int:
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("No OPENROUTER_API_KEY.", file=sys.stderr)
        return 1

    models = list(only) if only else list(settings.model_pool)
    if not models:
        print("MODEL_POOL is empty; nothing to probe.", file=sys.stderr)
        return 1

    print(f"probing {len(models)} models, one call each, effort={settings.reasoning_effort!r}\n")

    results: list[Speed] = []
    async with OpenRouterClient(settings) as client:
        for index, model in enumerate(models, 1):
            print(f"[{index}/{len(models)}] {model}", flush=True)
            speed = await measure(client, model)
            results.append(speed)
            if speed.ok:
                print(
                    f"        {speed.seconds:>6.1f}s  {speed.tokens:>4} tok  "
                    f"{speed.per_second:>5.1f} tok/s  "
                    f"thinking {speed.thinking}",
                    flush=True,
                )
            else:
                print(f"        FAILED  {speed.note}", flush=True)

    working = sorted((r for r in results if r.ok), key=lambda r: -r.per_second)
    broken = [r for r in results if not r.ok]

    print("\n" + "=" * 74)
    print("BY THROUGHPUT, fastest first")
    print("=" * 74)
    print(f"{'#':>2}  {'model':<44} {'tok/s':>7} {'probe':>7} {'~stmt':>7}")
    for index, r in enumerate(working, 1):
        print(
            f"{index:>2}  {r.model:<44} {r.per_second:>7.1f} "
            f"{r.seconds:>6.1f}s {r.projected_statement_seconds:>6.0f}s"
        )

    if broken:
        print("\nNo answer:")
        for r in broken:
            print(f"    {r.model:<44} {r.note}")

    if len(working) >= 7:
        print("\nA bench ordered by speed alone — paste into .env only if you also")
        print("trust these models on the required form (scripts/probe_pool.py):\n")
        print("MODEL_POOL=" + json.dumps([r.model for r in working]))
    else:
        print(f"\n!! Only {len(working)} models answered; Situation B needs 7 distinct.")

    OUT.write_text(
        json.dumps(
            {
                "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "reasoning_effort": settings.reasoning_effort,
                "task_tokens_budget": BUDGET,
                "ranked": [asdict(r) | {"per_second": round(r.per_second, 2)} for r in working]
                + [asdict(r) for r in broken],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwritten to {OUT.relative_to(OUT.parents[1])}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="probe just these model ids")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.only)))
