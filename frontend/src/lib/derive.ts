import type { LlmCall, Run, Slot, Verdict } from '../types'
import { ADVOCATE_SLOTS, JUDGE_SLOTS } from './slots'

// Store rows, derive totals. Everything in this file is computed from
// `run.calls` at read time and stored nowhere — the headline sentence, the two
// verdict counts, the total words, the wall clock, the cost.

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

/** True once all four statements exist. Stage 2 is sealed until then. */
export function stageOneComplete(run: Run): boolean {
  return statements(run).every((call) => call?.status === 'done')
}

export function statementsIn(run: Run): number {
  return statements(run).filter((call) => call?.status === 'done').length
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

/** The verdicts in fixed judge order — the three tally rules read this. */
export function verdictTally(run: Run): (Verdict | undefined)[] {
  return judgments(run).map((call) => call?.verdict)
}

/**
 * "2 justified — 1 not justified".
 *
 * Both halves are always stated, including when one count is zero: the 3-0
 * variant is not designed yet (handoff, "Not designed yet"), and stating the
 * derivation plainly is preferable to inventing a second layout for it.
 */
export function headline(run: Run): { justified: number; notJustified: number } {
  const counts = verdictCounts(run)
  return { justified: counts.justified, notJustified: counts.not_justified }
}

export function totalWords(run: Run): number {
  return run.calls.reduce((sum, call) => sum + call.words, 0)
}

export function totalCost(run: Run): number {
  return run.calls.reduce((sum, call) => sum + call.cost, 0)
}

/**
 * The span from the run's start to its end — not the sum of the call
 * durations, which would double-count the parallel stages. While the run is
 * still going, `now` measures against the present.
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

export function verdictLabel(verdict: Verdict): string {
  return verdict === 'justified' ? 'justified' : 'not justified'
}
