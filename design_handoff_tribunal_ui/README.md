# Handoff: LLM Tribunal — the single-page trial flow

## Overview
The UI for `danelbaz2/tribunal`: a tribunal of 7 LLM calls rules on an arbitrary charge file — 4 advocates state a position in isolation, then 3 judges rule independently, then a verdict reports the count.

**It is one continuous page, not three routes.** The user has exactly two inputs, both at the top: the charge file (pasted text or an uploaded document) and the bench choice (one model in all 7 slots, or 7 distinct models). Pressing *Convene the tribunal* starts an unattended run: the page scrolls down through the advocates as each one speaks, then through the judges as each one rules, and lands on the verdict. **There is no human in the loop after that click** — no confirmation, no step-through, no "next".

The primary design file is **`Tribunal Flow.dc.html`** — open it in a browser and run it; it is the specification of the behaviour described below. `Tribunal Mockups.dc.html` is the earlier three-screen study, kept for reference only. Where they differ, the flow file wins.

## About the Design Files
These are **design references written in HTML** — prototypes of the intended look and behaviour, not production code to copy. Recreate them in the repo's real frontend environment (React + TypeScript + Tailwind, per `ARCHITECTURE.md` Part 4).

Because the design is now one page, the repo's screen layout in `ARCHITECTURE.md` Part 5 should be read as sections of one route:

- `frontend/src/pages/NewTrial.tsx` → the whole run page (intake + advocates + judges + verdict)
- `frontend/src/components/ChargeUpload.tsx` → the charge block
- `frontend/src/components/RosterView.tsx` → the bench choice
- `frontend/src/components/StatementsView.tsx` → the advocates stage
- `frontend/src/components/JudgePanel.tsx` → the judges stage
- `frontend/src/components/Result.tsx` → the verdict block
- `Courtroom.tsx` / `Comparison.tsx` → the courtroom is no longer its own route; the A/B comparison screen is not designed yet.

## Fidelity
**High-fidelity.** Final colours, typography, spacing and interface copy. Recreate pixel-for-pixel from the values below. The case material (a hospital medication-override case) and the statement/judgment prose are placeholder content — they demonstrate length and shape. Interface copy *is* final.

## Design system
Everything visual comes from the **Classical** design system (`_ds/.../styles.css` in this bundle, with its `readme.md`). Port its `:root` token block into `tailwind.config.js` (`theme.extend.colors / fontFamily / spacing / borderRadius / boxShadow`) instead of hard-coding hexes.

Its binding rules, which the mock obeys:
- Serif only — Cormorant Garamond headings over Lora body. No sans-serif for emphasis; use size and italics.
- **Colour is stroke, never fill.** No filled buttons, no filled cards, no coloured banners. The accent (#b68235) appears as 1px borders, 2–3px rules, small uppercase kickers, tag outlines and the selected-card inset ring.
- Hairline dividers (`--color-divider`) carry structure — between sections, between the two sides, between judge columns.
- Elevation is a whisper (`--shadow-sm/md/lg`). Nothing floats.
- Body copy is justified at a comfortable measure (`text-align: justify; hyphens: auto`).
- Figures set tabular (`font-feature-settings: 'tnum'`) wherever a number stands as a figure: counts, durations, costs, confidences, word counts, the verdict tally.
- Icons are **Lucide**, inline SVG on `currentColor`. The only icon in the design is `chevron-down` on the expand control.

---

## The page, top to bottom

### Sticky header
`.nav`, `position: sticky; top: 0; z-index: 20`, background `--color-bg`. Brand "Tribunal", then four stage labels — "1 · The charge", "2 · The advocates", "3 · The judges", "4 · The verdict" — Cormorant 11px, `letter-spacing .14em`, uppercase. The current stage is `--color-accent`; the others `--color-neutral-500`. Right-aligned muted tabular status: `"idle · 7 slots waiting"` before the run, `"N of 7 calls returned"` during and after.

### 1 · The charge (intake)
`padding: 64px 48px 72px`, bottom hairline, inner column `max-width: 900px`.

1. Accent kicker "Instrument of deliberation" (Cormorant 11px, `.16em`, uppercase).
2. H1 "A trial held entirely by machines." — **54px, weight 400** (display sizes take the normal cut), `letter-spacing -.02em`, `max-width: 15ch`.
3. One justified paragraph, 16px / 1.72, `max-width: 62ch`, explaining the 4+3 structure and the binary contract.
4. `.hr`.
5. Row: h3 "The charge file" (24px) + a `.seg` control on the right — *Paste the text* | *Upload a document*.
6. `textarea.input`, `min-height: 168px`, 14px / 1.7. Under it, a `.tag.tag-neutral` word-count readout ("76 words extracted") and a muted 12.5px line: "Or drop a PDF, TXT or MD here. A file that accuses nobody of anything is refused now, not at the verdict."
   In the implementation the two input modes swap: paste shows the textarea, upload shows a dashed dropzone (1px dashed `--color-divider`, radius 4px) and, once a file is attached, a bordered card with filename, a `.tag.tag-outline` "attached", and muted lines for `N pages · N words extracted · text layer present` and "Once a run exists this case is sealed. A correction is a new case, never an edit."
7. `.hr`.
8. h3 "The bench" + muted 13px explainer, then a 2-column grid (18px gap) of two radio `.card`s — each a `.radio` + `.dot` beside a 17px `.card-title`, then a 13px body line. **The selected card is marked with `box-shadow: inset 0 0 0 1px var(--color-accent)`, never a fill.**
   - "One model, seven times" → `situation = 'identical'` — *A single model drawn from the free pool sits in all seven chairs, as seven independent calls sharing no state.*
   - "Seven different models" → `situation = 'different'` — *Seven distinct models drawn without replacement, one per slot. The draw and its seed are recorded with the run.*
9. `.hr`, then the action row: `.btn.btn-primary` "Convene the tribunal" (15px, padding 11px 22px) — label becomes "Convene again" after a first run — beside a muted 12.5px sentence: "Once convened the trial runs to its end without you: four statements, then three judgments, then the count."

**Validation** (`SPECIFICATION.md` Part 5, pitfalls 3 & 13): refuse at submit, loudly, an empty or accusation-free charge and a PDF with no extractable text layer. The word-count tag is the live extraction readout for both modes.

### 2 · The advocates
Appears only once the run starts. Header block (`max-width: 1320px`, `padding: 44px 48px 24px`): accent kicker "Stage one · statements", h2 32px weight 400 "The advocates speak, each alone.", muted 12.5px note that there are no rebuttals and that the two sides are set opposite so their claims can be read against each other.

**Sticky side header** — `position: sticky; top: 52px; z-index: 15`, background `--color-bg`, top hairline, **bottom border 1px `--color-accent`**. Inside, the same `1fr 1px 1fr` grid as the cards: left cell "AGAINST" (14px, `.14em`, uppercase) + muted "the act was not justified" + right-aligned tabular counter "1 of 2 in"; right cell "FOR" + "the act was justified" + its counter. This is what makes the comparison readable while scrolling — keep it.

**The grid** — `max-width: 1320px`, `padding: 0 48px 20px`, `grid-template-columns: 1fr 1px 1fr`, `align-items: start`. The middle column is a `--color-divider` fill spanning every row (`grid-column: 2; grid-row: 1 / -1`) — the courtroom spine. Cells carry 30px inner padding away from the spine.

**Pairs are aligned by row, deliberately:** row 1 = Vega (against) ↔ Orion (for); row 2 = Lyra (against) ↔ Draco (for). An argument and the opposing argument sit side by side.

**Statement card** (`.card`, `gap: var(--space-3)`, `border-style` solid, **dashed while that advocate is speaking**):
- Header row, baselines aligned: persona as `.card-title` 20px ("Advocate Vega"); below it `.card-kicker` with slot and side (`advocate_against_1 · against`); on the right a status marker — `.tag.tag-outline` "reasoning…" while live, `.tag.tag-neutral` tabular word count ("294 words") when done.
- *Waiting* state: muted 12.5px "Awaiting the floor." The card keeps its place in the grid so nothing jumps as the run proceeds.
- *Live* state: three 5px accent dots pulsing (1.2s ease-in-out, 0.18s stagger) beside muted 12px "reading the charge file".
- *Done* state, in order:
  1. **Thesis** — a 34px 2px accent rule, then the advocate's claim in one sentence, Cormorant **19px / 1.28**. This is what makes four statements scannable; every advocate has one.
  2. **The statement**, 13.5px / 1.75, justified, hyphenated, full opacity — inside a **collapsed wrapper**: `overflow: hidden; max-height: 152px; transition: max-height .4s ease`. Expanded → `max-height` large enough for the content.
  3. **The expand control** — `.btn.btn-ghost`, 12.5px, `align-self: flex-start`, label "Read the full statement" / "Fold the statement", with a 14px Lucide `chevron-down` that rotates 180° when open (`transition: transform .25s ease`). Collapse state is per card, default collapsed, so all four statements fit one screen.
  4. Hairline, then `.card-meta` (11px, 50% text, tabular): model · duration · cost — `meta-llama/llama-3.3-70b-instruct:free · 12.4s · $0.00`.

### 3 · The judges
Top hairline, header block: accent kicker "Stage two · judgment", h2 32px weight 400 "The judges read the four statements.", muted 12.5px "The same transcript to each, carrying personas and no model names. No judge learns another judge exists."

Grid `1fr 1px 1fr 1px 1fr` inside `max-width: 1320px`; the 1px columns are `--color-divider` fills. Each judge column, `padding: 28px 30px 34px`, `gap: 14px`:
- `.card-kicker` slot id (`judge_1`), h3 23px weight 400 persona name.
- *Waiting*: muted 12.5px "Sealed until every statement exists."
- *Live*: the same three pulsing dots + "weighing the statements".
- *Done*:
  - verdict row — `.tag.tag-outline` "justified" (12px, padding 4px 12px); for `not_justified` a `.tag.tag-neutral` with `1px solid var(--color-neutral-400)` — beside muted tabular "confidence 0.78";
  - **confidence bar** — 2px track `--color-neutral-300`, absolutely-positioned fill (`inset: 0 <100−pct>% 0 0`) in `--color-accent`, or `--color-neutral-700` when the verdict is `not_justified`;
  - `<ol>` of reasons, 13.5px / 1.7, 10px between items, `padding-left: 18px` — **at least 2, always** (spec criterion 6);
  - hairline, then `.card-meta`: model · duration · cost.

### 4 · The verdict
Full-width block on `--color-surface`, top hairline, `padding: 72px 48px 84px`, inner column `max-width: 940px`, centred.
- Kicker in `--color-accent-700` (paragraph-size accent text must use the deep step): "The tribunal, having heard four advocates and three judges, finds".
- **The verdict slab** — bordered top and bottom by 2px `--color-accent`, `padding: 34px 24px 30px`: the outcome word at **Cormorant 96px / 1, weight 400, uppercase, `letter-spacing -.03em`** ("JUSTIFIED"), then the plain-language line at Cormorant 22px, `max-width: 38ch` — "The accused's act is held defensible. She is not in the wrong." (for the other outcome: "NOT JUSTIFIED" and a line saying the act is held indefensible).
- Tally line — Cormorant 15px, `.1em`, uppercase, tabular: "Carried 2 to 1", the word *to* in `--color-neutral-500`.
- **Per-judge row** — a 3-column grid with hairline top/bottom and 1px dividers between: each cell a 52px 3px rule (accent for `justified`, `--color-neutral-400` for `not_justified`), the judge's name (Cormorant 17px), and muted tabular "justified · 0.78".
- Muted 12.5px caveat, `max-width: 60ch`: "Counted from three judgment rows; the line above is derived at read time and stored nowhere. One run of one bench is not evidence about models — it is evidence about this run."
- Run totals row (muted 12px, tabular, 26px gaps): "7 calls · 4 statements, 3 judgments" · "wall clock 41.2s" · "1,145 words argued" · "cost $0.00".
- Actions: `.btn.btn-secondary` "Convene on a new charge" (resets to the top) and `.btn.btn-primary` "Run it again on this one".

---

## Sequencing and scrolling — the core behaviour
One index drives everything. Participants complete **in display order**:

```
0 Vega (advocate_against_1)   1 Orion (advocate_for_1)
2 Lyra (advocate_against_2)   3 Draco (advocate_for_2)
4 Judge Meridian   5 Judge Zenith   6 Judge Solstice
```

`active` is the participant currently working; `done` is how many have returned. Each participant is exactly one of *waiting*, *live*, *done*.

Scroll steps (smooth, and each target has a `scroll-margin-top` clearing the sticky chrome):
- on convene → the advocates' **row 1** (offset 118px, clearing header + sticky side header);
- when `done === 2` → **row 2**;
- when `done === 4` (all statements in) → the judges section;
- when `done === 5` → **judge 1's column**, so his completed reasoning is what you land on; `done === 6` → judge 2; `done === 7` → judge 3, then after ~1.4s → the verdict.

The prototype fakes the pace with a timer (2000ms per participant, adjustable Deliberate 3200 / Normal 2000 / Brisk 1100). **In the real app the timer is the backend event stream** — a participant goes *live* when its call starts and *done* when its row arrives; the scroll steps fire on the same transitions. Keep an escape hatch equivalent to the prototype's `autoScroll` flag, and do not scroll if the user has scrolled away themselves.

Implementation note: scroll by computing `element.getBoundingClientRect().top + scrollTop − offset` on the scrolling container and calling `scrollTo({ behavior: 'smooth' })`. Do **not** use `scrollIntoView`.

## Other behaviour
- Reveal animation: `opacity 0 → 1` with a 10px rise, 0.5s ease-out, once per element. The pulsing dots and the chevron rotation are the only other motion. Nothing slides or bounces; never animate a verdict from one value to another.
- Hover / focus: don't restyle — `styles.css` themes hover, active and the 2px accent `:focus-visible` ring for `.btn`, `.input`, `.radio`, `.seg-opt` and `.nav a`.
- Bench mode changes what the seven `.card-meta` model identifiers read: one repeated identifier in *identical*, seven distinct ones in *different*.
- **Failure:** any call failing twice marks the run `failed`; surface which slot and which model failed and offer a one-click re-run (`SPECIFICATION.md` Part 5, pitfall 4). Not designed yet.

## State
```ts
charge:    { source: 'text' | 'file', text, filename?, pages?, wordCount, hasTextLayer }
situation: 'identical' | 'different'
run:       { id, status: 'running' | 'finished' | 'failed', seed, roster: Record<Slot, string>, startedAt }
calls:     { slot, stage: 'statement' | 'judgment', model,
             status: 'waiting' | 'live' | 'done' | 'failed',
             text?, thesis?, verdict?, confidence?, reasons?, words, durationMs, cost }[]
ui:        { expanded: Record<Slot, boolean>, autoScroll: boolean }
```
Derive, never store: the verdict word, the tally, `justified_count` / `not_justified_count`, total words, wall clock, total cost. Render in the fixed display order above, never in arrival order.

## Design tokens
From `_ds/.../styles.css` — use the variables, not the literals.

| Token | Value |
| --- | --- |
| `--color-bg` | `#f3f2f2` |
| `--color-surface` | `#eae9e9` (the verdict ground) |
| `--color-text` | `#201f1d` |
| `--color-accent` | `#b68235` |
| `--color-divider` | `color-mix(in srgb, #201f1d 16%, transparent)` |
| neutral 100→900 | `#f8f4f4 #eae7e7 #d7d3d3 #bab6b6 #9b9797 #7d7979 #605d5d #444141 #2d2b2b` |
| accent 100→900 | `#fff3e4 #ffe3bf #facb8d #e1ad66 #c28d41 #a06f24 #7d5411 #5a3b0a #3a270d` |
| `--font-heading` | Cormorant Garamond — 400 for display, 600 for interface headings |
| `--font-body` | Lora 400/600 |
| spacing 1–8 | `4.6 9.2 13.8 18.4 27.6 36.8` px |
| radius sm/md/lg | `2 / 4 / 7` px |

Type sizes in use: 96 / 54 / 32 (display, weight 400) · 24 / 23 / 22 / 20 / 19 / 17 (headings) · 16 / 15 / 14 / 13.5 / 13 / 12.5 / 12 / 11 / 10 (body, meta, kickers). Body line-heights 1.7–1.75; heading 1.12–1.3.

Accent-on-ground is ~3:1 — fine for chrome, rules and large text, **not** for paragraph text; paragraph-size accent copy uses `--color-accent-700`.

## Assets
None. No images. Icons: Lucide, inline SVG (`chevron-down` is the only one used).

## Not designed yet
- The **A/B comparison** view (`Comparison.tsx`).
- The **failed-run** state and the **invalid / empty charge file** rejection.
- The **3–0** verdict variant (the mock shows 2–1) and the `NOT JUSTIFIED` slab.
Ask the designer rather than improvising these.

## Files
- `Tribunal Flow.dc.html` — **the design.** The whole flow; run it in a browser and watch the sequence.
- `Tribunal Mockups.dc.html` — the earlier three-screen study; reference only.
- `support.js` — runtime for those files; not part of the design.
- `_ds/classical-…/styles.css` — the design system's tokens and component classes. **The source of truth for every visual value.**
- `_ds/classical-…/readme.md` — the design system's own guide.
