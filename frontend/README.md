# Tribunal — frontend

React + TypeScript + Tailwind. Three screens, built from
`design_handoff_tribunal_ui/README.md` on the **Classical** design system.

```
npm install
npm run dev                              # http://localhost:5173
VITE_USE_FIXTURES=true npm run dev       # the three screens with no backend
npm run build                            # tsc -b, then vite build
npm run typecheck
```

`/api` proxies to `http://127.0.0.1:8000` — the FastAPI backend. Point it elsewhere with
`VITE_API_TARGET`.

## Where things are

| Path | What it is |
| --- | --- |
| `src/index.css` | The Classical token block and component classes, ported from the handoff bundle. **The source of truth for every visual value.** |
| `tailwind.config.js` | The same tokens as Tailwind theme entries — each one reads the CSS variable, never a repeated literal. |
| `src/types.ts` | One run: the charge, the situation, the run, one row per call. |
| `src/lib/slots.ts` | The seven slots and their personas. Fixed order; the UI never sorts by arrival. |
| `src/lib/derive.ts` | Everything computed at read time — the headline, the counts, the totals, the wall clock. Nothing here is stored. |
| `src/lib/runStore.tsx` | The active run: convene, follow the event stream, refetch on reconnect. |
| `src/api.ts` | The contract the backend has to meet, and nothing else about it. |
| `src/pages/` | `NewTrial`, `Courtroom`, `Judgment`. |
| `src/components/` | `ChargeUpload`, `StatementsView`, `JudgePanel`, `Result`, `Nav`. |

## The fixtures switch

`VITE_USE_FIXTURES=true` replaces every backend call with the reference run in
`src/fixtures/referenceRun.ts` — the placeholder case material from the handoff — and replays the
arrival of the seven calls so the live states can be seen. It is a development switch, **never a
fallback**: with it off, a backend that does not answer produces a reported failure, not invented
rows. It is compiled out of a normal production build; the case text is absent from `dist/`.

## Not built here

- `Comparison.tsx` (Situation A vs B) — deliberately outside this handoff and not designed.
- The **failed-run** and **invalid-charge rejection** states, and the **3–0 verdict** variant, are
  not designed either. Where the code must render them it says only what is true, keeps the color
  rule (stroke, never fill), and carries a comment pointing here. Ask the designer before
  improvising more.
