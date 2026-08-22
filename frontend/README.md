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

**One route.** The trial is one continuous page — intake, the advocates, the judges,
the verdict — as sections that appear as the run reaches them, not screens the
user navigates between. There is one act in the whole flow: supply a charge and
a bench, press convene. Everything after that happens without the user.

| Path | What it is |
| --- | --- |
| `src/index.css` | The Classical token block and component classes, ported from the handoff bundle. **The source of truth for every visual value.** |
| `tailwind.config.js` | The same tokens as Tailwind theme entries — each reads the CSS variable, never a repeated literal. |
| `src/pages/NewTrial.tsx` | The whole run page. |
| `src/components/` | `Nav` (sticky, four stages), `ChargeUpload`, `RosterView`, `StatementsView`, `JudgePanel`, `Result`, `PulseDots`. |
| `src/lib/slots.ts` | The seven slots, their personas, and `DISPLAY_ORDER` — which is not slot order: the sides are set opposite so a claim and its answer share a row. |
| `src/lib/derive.ts` | Everything computed at read time — the verdict word, the tally, the counts, the totals, the wall clock. Nothing here is stored. |
| `src/lib/useSequencedScroll.ts` | The page following the run to three landings — the statements heading, the judgment heading, the verdict — and the escape hatch that stops it once the reader scrolls. |
| `src/lib/runStore.tsx` | The active run: convene, follow the event stream, `reset()` back to no run at all. Nothing survives a reload — a refresh starts over, on purpose. |
| `src/api.ts` | The contract the backend has to meet, and the one place `writing` is normalised to `live`. |

## Two things worth knowing

**A statement is one block, not a parsed-out lede over a separate body.**
That split used to print the opening sentence twice or read as two
disconnected paragraphs. Collapsed it's two lines with a one-time wipe
reveal; opening the card continues the same text. Live text is *not*
rendered chunk-by-chunk — the backend streams it, but repainting on every
chunk stutters on a slow connection — so the card shows a phase instead
(`reading` → `reasoning` → `writing`; only the last is a real signal, the
first visible character arriving) and reveals the whole thing once done.

**The scroll only stops three times** — the statements, judgment and verdict
headings, never mid-card — driven by the stream, not a timer. It waits on
`document.fonts.ready` before measuring anything (the heading font swaps in
async and reflows the hero title otherwise) and every landing section
reserves `min-height: 100vh` so there's room to scroll into before its cards
have content. Any wheel or touch scroll hands control back for the run.

## The fixtures switch

`VITE_USE_FIXTURES=true` replaces every backend call with the reference run in
`src/fixtures/referenceRun.ts` and replays the arrival of the seven calls, so
the sequence can be watched with no network and no key. It is a development
switch, **never a fallback**: with it off, a backend that does not answer
produces a reported failure, not invented rows. It is compiled out of a normal
production build.

## Not built here

- The **invalid-charge rejection**, the **3–0 verdict** and the
  `NOT JUSTIFIED` slab are not designed either. Where the code must render
  them it says only what is true, keeps the colour rule (stroke, never
  fill), and carries a comment pointing here. Ask the designer before
  improvising more.
- The **failed-run** state now has a shape: a banner naming which slot and
  model failed, next to a "Start over" button that calls `reset()`. It is
  functional, not designed — treat it the same as the two above.
