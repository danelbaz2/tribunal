# Interview record — decisions taken before implementation

Method: lesson 6, slides 26–27. The agent drafted questions against the architecture sketch;
every question landed where the sketch went quiet. The questions are kept next to the answers so
that a later reader can see *what was undecided* and not only what was decided.

Date: 2026-08-17. Decided by: Dan. Drafted by: agent.

Every answer below is binding on `SPECIFICATION.md`. If an answer changes, the specification
changes first and the code is rebuilt from it — never the other way round.

---

## Round 1

**Q1 — A judge must return a verdict the code can count. How strictly is that enforced?**

**A — Strict schema, one retry, then fail.** The judge is required to return a fixed structure.
If it cannot be parsed, the call is retried once with the format restated. If it fails twice, the
run is marked `failed`. Nothing is ever inferred from prose by a parser.

*Why it was asked:* slide 22 names this as the project's first pitfall — "warn that a judge may
return prose". Slide 62 gives the rule to write down: "Demand the fixed form twice."

**Q2 — ARCHITECTURE.md said a trial continues with 3 advocates if one fails. Completing the run,
or protecting the comparison?**

**A — Retry once, then fail the whole run.** All 7 calls must succeed for a run to count. A run
with 3 statements is not comparable to a run with 4, so it is not kept as if it were.

*Consequence:* this contradicted `ARCHITECTURE.md`, which has been corrected.

**Q3 — What verdicts may a judge return?**

**A — Binary only: `justified` / `not_justified`.** Every judge must commit. Three judges
therefore always produce 3–0 or 2–1, and the headline is always well-formed. A judge that finds
the charge file insufficient must still choose a side.

**Q4 — How much evidence does the comparison rest on?**

**A — One run per situation, temperature fixed.** The simple version. Accepted knowingly: a
single A-run against a single B-run cannot separate a model difference from sampling noise. This
limitation is written into Part 5 and must be stated out loud in any conclusion.

---

## Round 2

**Q5 — When a judge reads the four statements, does it see which model wrote each one?**

**A — Personas, not model names.** Each slot has a fixed persona. Judges see *who* said what by
persona, so the four statements are attributable and distinguishable, but the underlying model is
never revealed to a judge. The reason given: a judge that is itself an OpenAI model, seeing that
a statement came from an OpenAI model, might be more indulgent toward it.

*Derived requirement:* personas are **identical in Situation A and Situation B**. Different
personas between situations would add a second variable and destroy the comparison.

**Q6 — Cap statement length?**

**A — Stated in the prompt, not enforced.** The prompt names a target length. Nothing is ever
truncated. The actual word count of every statement is recorded, so a verbosity difference
between situations becomes a finding rather than a hidden bias.

**Q7 — In Situation B, which model sits in which slot?**

**A — Randomly drawn from a pool of free OpenRouter models**, 7 distinct models, without
replacement. The seed and the resulting slot→model assignment are both stored, so the exact same
tribunal can be reconstituted later.

**Q8 — Part 4, the validation approach: what is committed before the agent codes?**

**A — Recorded real responses, replayed in tests.** Seven real OpenRouter calls are made once
against a reference charge file; the raw responses are committed as fixtures. All tests replay
them: free, offline, deterministic, and carrying the real response shapes. Deliberately broken
copies of those fixtures cover the failure paths.

---

## Round 3

**Q9 — In Situation A, which model occupies all 7 slots?**

**A — One free model, drawn from the same pool as Situation B.** Both situations therefore use
models of comparable quality, and the only difference between them is diversity itself — which is
precisely the question in Part 1. Cost is zero on both sides.

---

## Decisions the agent took, subject to your approval

These were not asked because the lesson supplies the answer; flagged here so nothing is silently
assumed.

1. **A verdict requires a confidence value and at least two reasons.** Slide 15: "Require a
   verdict plus at least two reasons" — replace "well reasoned" with a countable requirement.
2. **Advocates return plain text; only judges return a strict schema.** Advocate output is never
   parsed for meaning, so imposing a schema on it would add failure paths that buy nothing.
3. **Target statement length is 300 words**, stated in the prompt, never enforced (per Q6).
4. **Persona names are drawn from stars and constellations** — non-national, non-gendered, and
   carrying no connotation that could tilt a judge.
