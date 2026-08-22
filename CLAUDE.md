# LLM Tribunal — agent briefing

## The four rules that override everything

1. **`SPECIFICATION.md` is the deliverable.** Code is generated from it. When output is wrong,
   correct the specification first, then rebuild. Never patch code to hide a specification gap.
2. **All 7 calls must succeed or the run is `failed`.** Never store a partial trial as if it were
   whole.
3. **Never infer a verdict.** A judge states its verdict in the required form or the call is
   retried once and then fails the run. No regex fallback, no keyword matching, no reading prose.
4. **Nothing reaches a judge except the charge file and the four statements.** No other judge's
   output, no model identifier. This is enforced by what the code passes, not by prompt wording.

## What this project is

A tribunal of 7 LLM calls rules on an arbitrary charge file: 4 advocates state a position in
isolation (no rebuttals), then 3 judges rule independently, each reaching a binary verdict with a
confidence and at least two reasons.

There is deliberately no built-in A-vs-B comparison feature: the roster is seven distinct free
models, one per slot, drawn from a hand-picked static list. Comparing what happens with a
different roster (e.g. one model in all seven chairs) is done by hand, outside the app, by running
trials and reading them side by side — not something the code computes or stores.

Read `SPECIFICATION.md` for what must be true, `ARCHITECTURE.md` for why the design is shaped
this way, `INTERVIEW.md` for decisions already taken and closed.

Stack: Python + FastAPI, PostgreSQL, React + TypeScript + Tailwind, all models via OpenRouter.
No Docker. Three settings in `.env`: OpenRouter key, database URL, model pool.

## Commands

Verified — these have actually been run in this repository:

```
frontend dev     cd frontend && npm run dev          (fixtures: VITE_USE_FIXTURES=true npm run dev)
frontend build   cd frontend && npm run build        (tsc -b, then vite build)
frontend types   cd frontend && npm run typecheck

backend deps     cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
backend dev      cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
tests            cd backend && .venv/Scripts/python -m pytest
```

Paths are Windows (`.venv/Scripts/`); elsewhere it is `.venv/bin/`.

The frontend proxies `/api` to `http://127.0.0.1:8000` (`frontend/vite.config.ts`), so no base URL
is configured per machine. Override with `VITE_API_TARGET`.

An unverified command in a committed file is worse than no command, because the agent trusts it.
Candidates awaiting confirmation live in `CLAUDE.local.md`, which is not committed; they move here
once they have actually been run.

Tests must run with **no network and no API key**. If a test needs either, it is written wrong —
see the fixtures rule below.

## Standards

**Every model call goes through `ai/openrouter.py`.** It is the only place credentials, retries,
timing and cost live. Do not call an HTTP client from anywhere else.

**`tribunal/` holds trial logic only** — no database code, no web code, no HTTP. It must be
readable and testable on its own, because it is where the project's core claim lives.

**Store rows, derive totals.** Every call is one `llm_calls` row. Counts and headlines are computed
from rows at read time. Never store a count as the source of truth.

**Prompts are text files in `tribunal/prompts/`, not strings in Python.** They contain roles only.
No name, crime, country, date or fact from any case ever appears in them.

**A stored case is immutable.** There is no update path for `cases`. A correction is a new case.

**Record what happened, including failures.** Requested temperature and reported temperature.
Word counts. Which slot failed and on which model. Failures are data here, not noise.

**`MODEL_POOL` is a hand-picked, static list.** Set in `.env`, checked only for length at startup.
No live discovery, no catalogue call to OpenRouter. If a model leaves the free tier, the run that
draws it fails and names the slot and model — fix the list by hand when that happens.

## What good work looks like

- A criterion in `SPECIFICATION.md` Part 2 is now checkable by a test that runs offline.
- The change is small enough that one criterion explains why it exists.
- Independence assertions read the **captured prompt text**, never the template.
- New fields are added as columns when they are counted or filtered, and into the raw-response
  JSONB when they are not.
- Failure paths are exercised by the `fixtures/broken/` files, not left to a live model's mood.

Not good work: a feature that adds machinery for a question nobody asked the app to answer; a
widget that always displays the same value; a test that passes because it asserts nothing.

## How to approach the work

**Fixtures before orchestration.** The reference charge file, 7 captured real responses, and the
hand-damaged copies are committed *before* the orchestrator is written. Everything after that is
built against a test that already exists.

**One spiral turn at a time** (lesson 6, slides 29–31): revise the intent from what the last turn
taught, update these context files so the lesson survives, commit, branch, build, verify against
Part 2, record the evidence. Lock only what use confirmed — not what argument confirmed.

**Subtract before adding.** When output is wrong, first suspect that too much context buried the
instruction that mattered. Add only what an observed failure proved missing. Prefer removing a
mechanism over adding a flag to work around it.

**Write corrections down as rules.** A correction given in chat is gone at the next session. If
something must hold, it belongs in this file as a rule — the rule, not the complaint.

**Expect free models to misbehave.** The pool is OpenRouter's free tier: rate limits, timeouts,
ignored format instructions, models disappearing without notice. Handle it as a failed call and
surface which slot and model failed. Never paper over it.

## When to stop and ask

Stop and ask before:

- **Changing anything in `SPECIFICATION.md` Part 2 or Part 3.** Criteria and contracts are
  decided. Propose the change; do not apply it.
- **Weakening a failure rule** — a fallback parser, a partial run kept as finished, a retry count
  above one. These trade the measurement for a nicer demo. Always ask.
- **Adding a model to `MODEL_POOL`, or spending money.** The pool draws from the free tier. A paid
  model changes what a run costs to reproduce.
- **Re-capturing the committed fixtures.** They are the control case; replacing them silently
  changes what every test means.
- **Any schema change to `cases`, `runs`, `llm_calls`.**
- **Deploying, or anything outward-facing.**

Proceed without asking on: implementation inside the stated boundaries, file and function layout,
naming, tests, refactors that keep every Part 2 criterion true.

## Pitfalls that have already cost us

Full list in `SPECIFICATION.md` Part 5. The three easiest to forget:

- **A run has seven chances to botch the schema**, not one. Record every failure, by slot and
  model — which one failed is the finding, not noise.
- **Cost is always zero.** Compare duration and word count instead.
- **A model may unmask itself** inside its own statement ("as an AI developed by …"). Persona
  anonymity protects the label, not against self-disclosure.

Pitfalls that are shared knowledge belong here. Ones still being confirmed, or specific to one
machine, start in `CLAUDE.local.md` and move here once they have proven general.

## Repeated, because they cannot be lost

- **`SPECIFICATION.md` is the deliverable; code is generated from it.**
- **All 7 calls succeed or the run is `failed`.**
- **A verdict is stated in the required form or the run fails. It is never inferred.**
- **No judge ever sees another judge's output or any model identifier.**
