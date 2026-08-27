# Deploy — frontend on Vercel, backend on Render

```
Browser ─> <you>.vercel.app ─(rewrite /api/*)─> tribunal-api.onrender.com ─> Supabase
```

The Vercel rewrite keeps everything same-origin for the browser: no CORS, and
the SSE run stream works because the backend sends a heartbeat every 15s.

The backend **cannot** run on Vercel — a run is a background task that lives
1–6 minutes, with an SSE stream and in-process state. It needs a real process,
which is what the Render web service is.

---

## 1. Backend → Render

1. Push this repo to GitHub (the two new files `render.yaml` and
   `frontend/vercel.json` must be committed).
2. Render dashboard → **New → Blueprint** → pick this repo. It reads
   `render.yaml` and proposes one web service, `tribunal-api`.
3. Fill the three secrets it asks for (marked `sync: false`):
   - `OPENROUTER_API_KEY` — the paid key from `.env`
   - `DATABASE_URL` — the Supabase **session pooler** URL, port **5432**,
     `postgresql+asyncpg://…` (not 6543 — that one breaks asyncpg)
   - `MODEL_POOL` — the JSON array from `.env`
   Leave `ALLOWED_ORIGINS` empty (the rewrite means the browser never calls
   Render cross-origin).
4. Deploy. First boot runs `create_tables()` against Supabase, so no migration
   step. Health check is `/api/health`.
5. Note the service URL. It should be `https://tribunal-api.onrender.com`; if
   that name was taken it will have a suffix — **copy the real one**.

Free plan: the service sleeps after 15 min idle (~40s cold start next
request). A running trial holds its SSE connection so it never sleeps
mid-trial. Upgrade to Starter ($7/mo) only if the cold start bothers you.

## 2. Point the rewrite at the real Render URL

If step 1.5 gave a URL other than `https://tribunal-api.onrender.com`, edit
`frontend/vercel.json` and replace both occurrences of the host, then commit.

## 3. Frontend → Vercel

1. Vercel dashboard → **Add New → Project** → pick this repo.
2. **Root Directory: `frontend`**. Framework preset: Vite (auto-detected).
   Build `npm run build`, output `dist`. No env vars needed.
3. Deploy. `vercel.json` rewrites `/api/*` to Render.

## 4. Check

- `https://<you>.vercel.app/api/health` → `{"status":"ok","pool_size":7,…}`
- Open the app, convene a run with the default charge, watch the stream.

---

## Spend cap

`DAILY_BUDGET_USD=1.0` is set in `render.yaml`. `POST /api/runs` returns 429
once `sum(llm_calls.cost)` over the last rolling 24h reaches $1. It is **not**
per-visitor — one person can use the whole dollar. Also set a hard limit on
the OpenRouter key itself (dashboard → Keys → limit) as a backstop.

## Updating

Both platforms auto-deploy on push to the default branch. Backend redeploy =
a restart: any run in flight is marked `failed` by `abandon_interrupted_runs()`
at startup, which is correct — a half-run is not a run.
