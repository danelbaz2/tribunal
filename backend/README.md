# Tribunal — backend

Python + FastAPI + PostgreSQL. Seven independent model calls per run, all of
them reaching OpenRouter through one client.

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt       # everywhere else

cp ../.env.example ../.env        # then fill in the two secrets
.venv/Scripts/python -m uvicorn app.main:app --reload
.venv/Scripts/python -m pytest
```

The tests need **no network and no API key**. If one ever does, it is written
wrong — see `fixtures/README.md`.

## The shape of it

| Path | Its job |
| --- | --- |
| `app/api/` | What can be asked of the system. |
| `app/ai/openrouter.py` | The only door to a model. Credentials, transport retries, timing and cost live here and nowhere else. |
| `app/tribunal/` | How a trial works. **No database, no web, no HTTP** — it can be read and tested on its own, which is where the project's claim lives. |
| `app/tribunal/prompts/` | The instructions, as text files. Open the two of them and confirm no case is named. |
| `app/runner.py` | The seam: runs a trial, writes the rows, streams the events. |
| `app/models.py` | The three tables: cases, runs, llm_calls. |
| `fixtures/` | The control case. |

## What is enforced, and where

- **All seven calls succeed or the run is `failed`** — `tribunal/orchestrator.py`.
  A run of three statements is not comparable to a run of four.
- **A verdict is never inferred** — `tribunal/judges.py:parse_ruling`. It reads
  the `verdict` field of a JSON object or it raises. No regex fallback, no
  keyword matching, no reading of prose. One retry with the form restated, then
  the call fails.
- **No judge reads another judge, and no advocate reads another advocate** —
  enforced by what `tribunal/judges.py` and `tribunal/advocates.py` put in a
  prompt, and asserted in `tests/test_independence.py` against the *captured
  prompt text*, never against the template.
- **No model identifier reaches a judge** — the transcript labels statements by
  persona only.
- **Store rows, derive totals** — `app/models.py` has no count, headline or
  total column anywhere. This is a deliberate departure from the
  `ARCHITECTURE.md` Part 6 sketch, which drew `total cost` on `runs`.
- **A stored case is immutable** — `cases` has no update path.

## The endpoints

| | |
| --- | --- |
| `POST /api/cases` | JSON `{text}` or multipart `file`. Extracts, and refuses at upload what cannot be tried. |
| `POST /api/runs` | `{case_id}`. Seats the bench, creates seven waiting rows, returns immediately and runs unattended. |
| `GET /api/runs/{id}` | The run and its seven rows. |
| `GET /api/runs/{id}/events` | Server-sent events. Each message carries the whole run, so a dropped one costs a frame, not consistency. |

Field names are camelCase on the wire, because `frontend/src/types.ts` reads
them that way. `tests/test_api.py` asserts the names, so a rename on either
side breaks a test rather than a screen.

## Still outstanding

**The seven real responses have not been captured.** `SPECIFICATION.md` Part 4
requires them committed before the orchestrator exists; that step needs a key,
so it is a human's to run:

```
.venv/Scripts/python scripts/capture_fixtures.py
```

Until then, `fixtures/responses/` is empty and the tests that need real
response shapes skip with a message saying so. Everything else — the
arithmetic, the independence assertions, every failure path — runs offline
today against `fixtures/broken/`.

**The bench is ranked, not drawn.** `MODEL_POOL` is a hand-picked, ordered list,
best first, set in `.env`. Seating reads off the top of it: the first 7
distinct entries, one per slot. It is checked only for length at startup —
not against OpenRouter — so a model that has left the free tier is discovered
when the run that draws it fails, not before. `GET /api/health` reports the
configured bench.

There is no random draw, so there is nothing to reconstitute: with the pool
unchanged, the same bench is seated every time (criterion 15), and the roster
stored on each run is the whole record of what ran.

`scripts/probe_pool.py --only <ids...>` gives each candidate the real work —
one statement, one judgment in the required form — and ranks by what it
measures. Two calls per model: most of a day on the bare 50/day tier, an
afternoon once $10 of credit raises it to 1000/day. Run without `--only` and
it tries to discover the free catalogue itself, which no longer exists in
this codebase — always pass explicit ids.

## Pacing, and what a 429 means

`MAX_CONCURRENT_CALLS` (default **4**) caps calls in flight at once — high
enough that every advocate, and every judge, can hold the floor together. It
is pacing, not method: nothing about what a call is sent changes, and no
advocate reads another whether they speak at once or in turn. A slot is
announced live *inside* the gate, so a card shows live only once its call is
actually out. The free tier is documented to answer 429 to a burst of exactly
four, so this is the setting most likely to need turning back down.

A 429 is not an attempt — the model never saw the prompt, so it doesn't spend
the one retry a real failure gets. `RATE_LIMIT_MAX_WAIT_SECONDS` bounds how
long a call waits one out before failing anyway. Two other things it can mean:

- **The account is out for the day, not the model.** The free tier caps at
  50 requests/day on a bare key, 1000/day once $10 of credit is added —
  `Rate limit exceeded: free-models-per-day` in the body names it. Every
  model failing at once on a key that worked an hour ago is the daily cap.
- **A slow read, not a hung call.** `REQUEST_TIMEOUT_SECONDS` (default
  **60**) wraps each attempt in `asyncio.wait_for`, not just `httpx.Timeout`
  — the latter only bounds the gap between two reads, so a model that
  dribbles output steadily can run for minutes under a "30s" timeout and
  never trip it.

## Speed, and the thinking nobody reads

Measured on real runs: **65% of every output token was hidden reasoning** —
one judgment spent 1485 of 1712 tokens thinking, for 168 visible words in
126s, and it's also where empty bodies come from. `REASONING_EFFORT` (default
`low`) caps it via OpenRouter's `reasoning` parameter: 447 → 6 reasoning
tokens on one verified call, 71.6s → 44.4s. **Never `none`** — some models
(`gpt-oss-20b`) answer `400 Reasoning is mandatory`, same for `enabled: false`
and `max_tokens: 0`; `low`/`minimal` are what's confirmed to work.

Even at `low`, the share varies by model and by call: one advocate slot on
`dots-3-note-preview:free` spent 92% of its completion budget on reasoning
one time and 80% the next, same model, same prompt shape.
`MAX_RESPONSE_TOKENS` (default **4096**) is the headroom for that swing — 2048
measured too tight and cost real calls (one cut off, one empty body) in a
single run.

Cost always reads $0.00 (free tier) and is recorded but never shown — the
card meta line carries tokens and the thinking share instead, plus
`asked twice` when a judge needed the format restated.

## The bench of voices

`tribunal/prompts/personas/` holds seven briefs, one per chair — a manner and
a method, nothing else. Task, output contract, target length and charge file
live in the shared template, so what can make a call fail is identical for
all seven; a difference between two statements is voice, not instruction.

They exist because, with one model seated in all seven chairs, the two
advocates on a side got the same prompt (they differ only by position) and at
temperature 0 returned byte-identical statements — four chairs, two
arguments, each served to the judges twice. Personas are fixed per run, never
a variable, styled after a school of legal reasoning, not a person. This
reverses `INTERVIEW.md` decision 4 (star names, no connotation) — a
deliberate trade, not an oversight.
