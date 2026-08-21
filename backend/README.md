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
| `app/models.py` | The four tables. |
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
| `POST /api/runs` | `{case_id, situation}`. Draws the bench, creates seven waiting rows, returns immediately and runs unattended. |
| `GET /api/runs/{id}` | The run and its seven rows. |
| `GET /api/runs/{id}/events` | Server-sent events. Each message carries the whole run, so a dropped one costs a frame, not consistency. |
| `POST /api/comparisons` | Links one `identical` run to one `different` run of the same case. Both must be `finished`. |

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

**The model pool is discovered, not written down.** At startup the server asks
OpenRouter what it is offering and keeps the models that cost nothing, carry the
`:free` suffix, take and return text, and can hold a transcript
(`ai/openrouter.py:select_free_models`). Seventeen qualified on 21 August 2026.
`GET /api/health` reports the resolved pool.

Set `MODEL_POOL` to pin it instead — to reproduce an old run, or to hold the
bench still across a comparison. A pinned pool is validated at startup and fails
loudly if a member has gone.

The cost of a live pool, stated plainly: two runs convened a week apart may draw
from different candidate sets, so comparing them carries a third uncontrolled
variable on top of the draw itself. Every run records the pool it drew from
(`runs.pool`), which is what keeps criterion 15 true — reconstitution needs the
seed *and* the pool, and both are on the row. Compare runs from the same
sitting.
