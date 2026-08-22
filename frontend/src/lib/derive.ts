import type { LlmCall, Run, Slot, Verdict } from '../types'
import { ADVOCATE_SLOTS, DISPLAY_ORDER, JUDGE_SLOTS } from './slots'

// Store rows, derive totals. Everything in this file is computed from
// `run.calls` at read time and stored nowhere — the verdict word, the tally,
// the two counts, the total words, the wall clock, the cost.

/** Words as the extractor counts them: whitespace-separated tokens. */
export function countWords(text: string): number {
  const trimmed = text.trim()
  return trimmed === '' ? 0 : trimmed.split(/\s+/).length
}

export function bySlot(calls: LlmCall[]): Partial<Record<Slot, LlmCall>> {
  const index: Partial<Record<Slot, LlmCall>> = {}
  for (const call of calls) index[call.slot] = call
  return index
}

/** Advocate rows in fixed slot order, missing slots included as `undefined`. */
export function statements(run: Run): (LlmCall | undefined)[] {
  const index = bySlot(run.calls)
  return ADVOCATE_SLOTS.map((slot) => index[slot])
}

/** Judgment rows in fixed slot order, missing slots included as `undefined`. */
export function judgments(run: Run): (LlmCall | undefined)[] {
  const index = bySlot(run.calls)
  return JUDGE_SLOTS.map((slot) => index[slot])
}

/**
 * How many participants have returned, counted in display order.
 *
 * This one number drives the whole page: which stage the header highlights,
 * which sections exist, and where the page scrolls next. It is derived, so a
 * dropped stream frame costs a moment of staleness and never a wrong state.
 */
export function doneCount(run: Run): number {
  const index = bySlot(run.calls)
  return DISPLAY_ORDER.filter((slot) => index[slot]?.status === 'done').length
}

/** The participant currently working, as an index into `DISPLAY_ORDER`. */
export function activeIndex(run: Run): number {
  const index = bySlot(run.calls)
  return DISPLAY_ORDER.findIndex((slot) => index[slot]?.status === 'live')
}

/** True once all four statements exist. Stage 2 is sealed until then. */
export function stageOneComplete(run: Run): boolean {
  return statements(run).every((call) => call?.status === 'done')
}

export function statementsIn(run: Run): number {
  return statements(run).filter((call) => call?.status === 'done').length
}

/** "1 of 2 in", for one side of the courtroom. */
export function sideCount(run: Run, slots: readonly Slot[]): string {
  const index = bySlot(run.calls)
  const done = slots.filter((slot) => index[slot]?.status === 'done').length
  return `${done} of ${slots.length} in`
}

export function succeededCalls(run: Run): number {
  return run.calls.filter((call) => call.status === 'done').length
}

export function failedCalls(run: Run): LlmCall[] {
  return run.calls.filter((call) => call.status === 'failed')
}

export interface VerdictCounts {
  justified: number
  not_justified: number
}

/** Counted from the judgment rows present. A verdict is never inferred. */
export function verdictCounts(run: Run): VerdictCounts {
  const counts: VerdictCounts = { justified: 0, not_justified: 0 }
  for (const call of judgments(run)) {
    if (call?.verdict) counts[call.verdict] += 1
  }
  return counts
}

/** The verdicts in fixed judge order — the per-judge row reads this. */
export function verdictTally(run: Run): (Verdict | undefined)[] {
  return judgments(run).map((call) => call?.verdict)
}

/**
 * The outcome, and the count that carried it.
 *
 * Three judges each commit to a binary verdict, so the count is always 3-0 or
 * 2-1 and the majority is always well-formed. The 3-0 slab is not designed
 * yet (handoff, "Not designed yet"); it renders in the same shape, which is
 * the smallest honest thing to do until it is.
 */
export function outcome(run: Run): {
  verdict: Verdict | null
  winning: number
  losing: number
} {
  const counts = verdictCounts(run)
  if (counts.justified + counts.not_justified === 0) {
    return { verdict: null, winning: 0, losing: 0 }
  }
  const justifiedWins = counts.justified > counts.not_justified
  return {
    verdict: justifiedWins ? 'justified' : 'not_justified',
    winning: justifiedWins ? counts.justified : counts.not_justified,
    losing: justifiedWins ? counts.not_justified : counts.justified,
  }
}

export function totalWords(run: Run): number {
  return run.calls.reduce((sum, call) => sum + call.words, 0)
}

/** Words the advocates argued — the judgments are structure, not argument. */
export function wordsArgued(run: Run): number {
  return statements(run).reduce((sum, call) => sum + (call?.words ?? 0), 0)
}

export function totalCost(run: Run): number {
  return run.calls.reduce((sum, call) => sum + call.cost, 0)
}

/**
 * The span from the run's start to its end — not the sum of the call
 * durations, which would double-count anything that overlapped.
 */
export function wallClockMs(run: Run, now: number = Date.now()): number {
  const started = Date.parse(run.startedAt)
  const ended = run.finishedAt ? Date.parse(run.finishedAt) : now
  return Math.max(0, ended - started)
}

// — figure formatting — every one of these is set tabular where it is rendered

export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatCost(cost: number): string {
  return `$${cost.toFixed(2)}`
}

export function formatCount(value: number): string {
  return value.toLocaleString('en-US')
}

export function formatConfidence(confidence: number): string {
  return confidence.toFixed(2)
}

/**
 * "866 tokens · 447 thinking" — what replaced the cost on every card.
 *
 * Cost is still recorded; it is simply not worth a line, because the free
 * tier prices at zero and it would always read $0.00 (do not build a widget
 * that always shows the same value). Tokens vary per model and per call, and
 * the thinking share is the largest single explanation of duration — which
 * *is* a reported finding.
 *
 * The thinking half appears only when the model reported any, so it never
 * degenerates into a constant either.
 */
export function formatTokens(call: LlmCall): string | null {
  if (!call.tokens) return null
  const thinking = call.thinkingTokens
  return thinking
    ? `${formatCount(call.tokens)} tokens · ${formatCount(thinking)} thinking`
    : `${formatCount(call.tokens)} tokens`
}

/** Total tokens generated across the run, for the footer. */
export function totalTokens(run: Run): number {
  return run.calls.reduce((sum, call) => sum + (call.tokens ?? 0), 0)
}

export function totalThinkingTokens(run: Run): number {
  return run.calls.reduce((sum, call) => sum + (call.thinkingTokens ?? 0), 0)
}

export function verdictLabel(verdict: Verdict): string {
  return verdict === 'justified' ? 'justified' : 'not justified'
}

/** The plain-language line under the slab. Copy is final (handoff, Fidelity). */
export function verdictSentence(verdict: Verdict): string {
  return verdict === 'justified'
    ? "The accused's act is held defensible. She is not in the wrong."
    : "The accused's act is held indefensible. She is in the wrong."
}
