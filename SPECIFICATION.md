# LLM Tribunal — Specification

This document, not the code, is the deliverable. The code is generated from it. When the output
is wrong, this file is corrected first and the code is rebuilt — never the reverse.

Written to the five-part structure of lesson 6 (slides 12–25). Every decision recorded here was
taken by a human and is traceable to `INTERVIEW.md`. `ARCHITECTURE.md` explains *why* the design
is shaped this way; this file states *what must be true*.

Status: **draft awaiting approval.** No code is written until this file is approved.

---

# Part 1 — The goal and its reason

**Goal.** Build a system that runs a complete judicial deliberation on an arbitrary charge file
using seven independent LLM calls — four advocates who state a position, three judges who rule —
and that compares two situations: all seven slots on one model, versus seven distinct models.

**Reason, in one sentence.** *To find out whether a tribunal of diverse models reaches a different
verdict, or reasons differently, than a tribunal of seven copies of the same mind.*

**How the agent uses this reason.** Every unwritten fork is settled in favour of the comparison
remaining valid, never in favour of a nicer trial. Concretely:

- If completing a run and protecting comparability conflict, **comparability wins** — abandon the
  run.
- If a feature would make the courtroom more impressive but would differ between Situation A and
  Situation B, **do not build it**.
- Prefer recording a fact over displaying it. The database is the instrument; the UI is the
  readout.

**The standard for the agent's own conduct:** show reasoned disagreement (slide 13). If a request
in this file would damage the measurement, say so before building it.

---

# Part 2 — Testable success criteria

Each criterion has exactly one true-or-false answer that a second reader can confirm.

## Arithmetic — settles by counting

1. A run with status `finished` has **exactly 7** `llm_calls` rows: 4 with stage `statement`,
   3 with stage `judgment`.
2. The 4 statement rows are exactly 2 in `against` slots and 2 in `for` slots.
3. The 3 verdicts sum to 3. `justified_count + not_justified_count = 3`, always.
4. The headline on screen equals those counts — the string "2 justified — 1 not justified"
   is derived from the rows, never stored as prose and never computed twice.
5. In Situation A, the 7 rows contain **exactly 1 distinct** model identifier.
   In Situation B, they contain **exactly 7 distinct** model identifiers.
6. Every judgment row has `verdict ∈ {justified, not_justified}`, `confidence ∈ [0.0, 1.0]`, and
   **at least 2** reasons.
7. No run reaches status `finished` unless all 7 calls succeeded. A run where any call failed
   twice has status `failed` and appears in no comparison.
8. Every `llm_calls` row records model, slot, stage, duration, cost, word count, and the complete
   raw response.

## Structural — settles by inspecting what was sent

These are the project's core requirement and are asserted against the **captured prompt text**,
not against the prompt template.

9. The text sent to `judge_N` contains **no** output produced by any other judge.
10. The text sent to any advocate contains **no** output produced by any other advocate.
11. The transcript sent to any judge contains **zero** model identifiers: for every model string
    in the pool, that string does not appear anywhere in the judge's input.
12. The three prompt templates contain no name, crime, country, date or fact from any specific
    case. Verifiable by reading two files.

## Reference-based — settles against a human reader

13. **Verdict fidelity.** A human reads all 3 written judgments of a run and records the verdict
    each one reached. The stored verdict must match the human's reading in **20 of 20** judgments
    across the first 7 runs. Any single mismatch is a defect, not a tolerance.
14. **Case independence.** The whole system runs on a second, entirely unrelated charge file with
    **zero code changes** and produces a finished run.
15. **Reconstitution.** Given a stored seed and pool, re-deriving the roster produces the same
    slot→model assignment, byte for byte.

## What the comparison screen must answer

16. For each of the 3 judge slots: did the same slot reach the same verdict in Situation A and in
    Situation B? Answerable at a glance, per slot.
17. Wall-clock duration per situation, and per slot.
18. Word count per statement, so a verbosity difference between situations is visible.

Cost is recorded but is expected to be **zero on both sides**, since both situations draw from the
free pool. Duration and agreement are the live differentiators — see Part 5.

---

# Part 3 — Architectural guidance

Boundaries the agent must respect. The interior is the agent's to design.

**The three sentences of boundary.** Reach every model through the single OpenRouter client in
`ai/openrouter.py`, which is the only place credentials, retries, timing and cost live. Keep
`tribunal/` free of database code, web code and HTTP, so the rules of the trial can be read and
tested alone. Store every call as its own row and derive every total from those rows — never store
a computed count as the source of truth.

File and function choices inside those boundaries are the agent's. Everything below is a contract,
not a layout.

## The 7 slots and their personas

Slots are fixed and identical in both situations. Personas are fixed and identical in both
situations. Only the model changes.

| Slot | Persona shown to judges | Position |
|---|---|---|
| `advocate_against_1` | Advocate Vega | not justified |
| `advocate_against_2` | Advocate Lyra | not justified |
| `advocate_for_1` | Advocate Orion | justified |
| `advocate_for_2` | Advocate Draco | justified |
| `judge_1` | Judge Meridian | — |
| `judge_2` | Judge Zenith | — |
| `judge_3` | Judge Solstice | — |

Judge personas are for display only; no judge learns another judge exists.

## The two output contracts

**Advocates return plain text.** Nothing in their output is parsed for meaning. The prompt names a
target of **300 words**; this is never enforced and never truncated. The actual word count is
recorded.

**Judges return a strict structure**, and nothing else:

```
verdict     : "justified" | "not_justified"      (required, exactly one)
confidence  : number in [0.0, 1.0]               (required)
reasons     : array of strings, length >= 2       (required)
```

On a parse failure the call is retried **once**, with the required form restated. A second failure
fails the run. No fallback parser, no keyword matching, no inference from prose — ever.

## Model assignment

A pool of **free OpenRouter model identifiers** lives in config and must hold at least 7 entries.

- **Situation A** draws **1** model from the pool and places it in all 7 slots as 7 independent
  calls that share no state.
- **Situation B** draws **7 distinct** models from the pool, without replacement, one per slot.
- The **seed** and the resulting **slot→model assignment** are stored on the run.
- Temperature is fixed at the lowest value each model supports; the value actually sent is
  recorded per call.

## Stage boundary

Stage 1 (4 statements, parallel, isolated) must complete before stage 2 (3 judgments, parallel,
isolated) begins. No advocate reads another advocate. No judge reads another judge. Enforced by
what the code passes, not by prompt wording.

---

# Part 4 — The validation approach

Decided before any code exists, per slide 21: *commit the recording first.*

**The control case.** One reference charge file, committed. Seven real OpenRouter calls are made
against it **once**; the raw responses are saved verbatim and committed as fixtures. From then on,
the entire test suite replays those files: no network, no cost, identical every run.

```
fixtures/
  reference_case.md            the committed charge file
  responses/                   7 real captured responses
  broken/                      hand-damaged copies of the above
    judge_prose.json             prose instead of the required form
    judge_missing_verdict.json   confidence and reasons, no verdict
    judge_one_reason.json        only 1 reason
    advocate_timeout.json        a call that never returns
```

**What the fixtures must prove.**

- Every criterion in Part 2's arithmetic and structural lists, offline.
- `judge_prose.json` → one retry, then the run is `failed`. Never a guessed verdict.
- `advocate_timeout.json` → one retry, then the run is `failed`. Never a 3-statement run.
- Judge independence, by asserting on the captured prompts (criteria 9–11).

**Before the agent codes**, in this order: the reference charge file is committed; the 7 real
responses are captured and committed; the broken copies are committed. Only then is the
orchestrator written.

**Live validation, once per spiral turn.** Run both situations on the reference case and confirm
criterion 13 by hand. Then run the second, unrelated charge file for criterion 14.

---

# Part 5 — The known pitfalls

The warnings you would give a colleague. Written once, permanently (slides 22–24).

**From the lesson, verbatim to this project**

1. A judge may return prose instead of the required form. Demand the fixed form twice, then fail.
2. A model call may time out or return an empty body. Treat both as a failed call, not as an empty
   verdict.
3. A charge file may arrive with no question in it — a document that accuses nobody of anything.
   The system must fail loudly at upload, not produce three confident verdicts about nothing.

**Consequences of the free-model pool**

4. **Free models fail often** — rate limits, queue timeouts, silent truncation. Combined with
   "all 7 calls must succeed", expect a high rate of `failed` runs. This is the accepted cost of
   comparability; surface the failing slot and model clearly so a re-run is one click.
5. **Free models frequently ignore output format instructions.** Weak models fail the schema more
   than strong ones. Since Situation B draws 7 different models, B will fail more often than A —
   and that asymmetry is a bias in *which runs survive to be compared*, not a neutral annoyance.
   Record every failure so it can be reported.
6. **Free models may ignore temperature.** Record what was requested and what the response
   reports; do not claim determinism you did not verify.
7. **Free models disappear.** OpenRouter's free tier changes without notice. Validate the pool at
   startup and fail with a clear message rather than mid-trial.
8. **Cost comparison is dead on arrival.** Both situations cost zero, so "which was cheaper" has
   no answer. Do not build a cost-comparison widget that always shows 0.00 — record cost, and
   compare duration and agreement instead.

**Threats to the measurement itself**

9. **One run per situation cannot separate signal from noise.** A judge slot that flips between A
   and B might flip again on a re-run of A alone. Never phrase a result as "diverse models
   disagree more" — phrase it as "in this run, slot 2 differed". The schema should tolerate
   repeats being added in a later spiral turn.
10. **Random draw is a second uncontrolled variable.** A Situation B difference may come from
    *which* seven models were drawn, not from diversity. The seed is stored precisely so this can
    be interrogated.
11. **Model and slot are confounded.** Whatever model lands in `judge_1` is the only evidence you
    have about `judge_1`. Never attribute a slot's behaviour to its model from a single run.
12. **A model may unmask itself inside its own statement** — "as an AI developed by …", or a
    house style so distinctive a judge could guess it. Persona anonymity protects against the
    *label*, not against self-disclosure. Assert that no pool identifier appears in judge input
    (criterion 11), and read early transcripts by hand for self-identification.
13. **PDF extraction produces garbage silently.** A scanned PDF yields empty or scrambled text and
    the trial proceeds on nonsense. Check extracted length and reject at upload.
14. **A judge may hedge into both verdicts** — "justified, though one could argue not". The binary
    contract means the structured field is authoritative; if it is absent or doubled, that is a
    parse failure, and parse failures fail the run.

**The pitfalls only we know**

15. The charge file is uploaded once and referenced by every run. Editing it after a comparison
    exists silently invalidates that comparison — the two runs no longer read the same case. Treat
    a stored case as immutable; a correction is a new case.
16. The same prompt template must serve both situations. Any per-model prompt tweak — even to help
    a weak model return valid output — makes A and B non-comparable. If a tweak is needed, it
    applies to all seven slots or to none.

---

# Approval

This specification is a hypothesis, not a settled truth (slide 28). It will be revised after every
turn of the spiral, and each turn locks only what use confirmed — not what argument confirmed.

- [ ] Read in full and approved by Dan
- [ ] The four agent-taken decisions at the end of `INTERVIEW.md` accepted or overridden
