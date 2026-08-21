// The shapes the UI holds for one run. They mirror `SPECIFICATION.md` Part 3
// (the seven slots, the two output contracts) and `ARCHITECTURE.md` Part 6
// (one row per call).
//
// Nothing derived is stored here: the headline sentence, the verdict counts,
// the total words, the wall clock and the total cost are all computed from
// `calls` at read time — see `lib/derive.ts`.

export type AdvocateSlot =
  | 'advocate_against_1'
  | 'advocate_against_2'
  | 'advocate_for_1'
  | 'advocate_for_2'

export type JudgeSlot = 'judge_1' | 'judge_2' | 'judge_3'

export type Slot = AdvocateSlot | JudgeSlot

export type Stage = 'statement' | 'judgment'

/** A judge states its verdict in this form or the call fails. It is never inferred. */
export type Verdict = 'justified' | 'not_justified'

export type Situation = 'identical' | 'different'

export type CallStatus = 'waiting' | 'writing' | 'done' | 'failed'

export type RunStatus = 'running' | 'finished' | 'failed'

export interface Charge {
  source: 'text' | 'file'
  text: string
  filename?: string
  pages?: number
  wordCount: number
  hasTextLayer: boolean
}

/** One `llm_calls` row. Every call is a row, including the ones that failed. */
export interface LlmCall {
  slot: Slot
  stage: Stage
  model: string
  status: CallStatus
  /** Advocates return plain text; nothing in it is parsed for meaning. */
  text?: string
  /** Judgment fields. Absent until the judge has returned a valid structure. */
  verdict?: Verdict
  confidence?: number
  reasons?: string[]
  words: number
  durationMs: number
  cost: number
  /** Why the call failed, when it did. Failures are data here, not noise. */
  error?: string
}

export interface Run {
  id: number
  /** The stored case this run read. A stored case is immutable — convening
   *  again on it is a second run, never an edit. */
  caseId: number
  caseTitle: string
  status: RunStatus
  situation: Situation
  seed: string
  /** The draw: slot → model identifier, recorded with the run. */
  roster: Record<Slot, string>
  startedAt: string
  /** Set when the run reaches a terminal status. The wall clock is the span
   *  between the two, not the sum of the call durations — the stages run in
   *  parallel. */
  finishedAt?: string
  calls: LlmCall[]
}
