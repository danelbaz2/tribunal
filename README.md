# LLM Tribunal

A tribunal of seven independent LLM calls rules on an arbitrary charge file: four advocates state
a position in isolation, then three judges rule without seeing one another. The point is not the
trial — it is comparing **one model in all seven slots** against **seven distinct models**, to find
out whether model diversity changes the verdict.

`SPECIFICATION.md` states what must be true and is the deliverable; the code is generated from it.
`ARCHITECTURE.md` explains why the design is shaped this way. `INTERVIEW.md` records the decisions
already taken.

## Run it

Two secrets, in `.env` at the repository root — copy `.env.example` and fill it in.

```
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # .venv/bin/ elsewhere
.venv/Scripts/python -m uvicorn app.main:app --reload       # http://127.0.0.1:8000

cd frontend
npm install
npm run dev                                                 # http://localhost:5173
```

The frontend proxies `/api` to port 8000, so nothing else has to be configured. To look at the
three screens without a backend at all: `VITE_USE_FIXTURES=true npm run dev`.

```
cd backend && .venv/Scripts/python -m pytest
```

The tests run with no network and no API key.

## Where things are

```
backend/     the Python application — see backend/README.md
frontend/    the React application — see frontend/README.md
```

## Before a real run

The seven real model responses that form the control case have **not been captured yet**
(`SPECIFICATION.md` Part 4). That step needs an OpenRouter key and is run once, by hand:

```
cd backend && .venv/Scripts/python scripts/capture_fixtures.py
```

See `backend/fixtures/README.md`. Re-capturing afterwards silently changes what every test means.
