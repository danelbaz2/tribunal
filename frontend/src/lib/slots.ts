import type { AdvocateSlot, JudgeSlot, Slot } from '../types'

// Slots and personas are fixed and identical in both situations; only the model
// changes (`SPECIFICATION.md` Part 3). The UI orders by these lists and never
// by arrival — a slot that has not produced text yet holds its place.

export const AGAINST_SLOTS: AdvocateSlot[] = ['advocate_against_1', 'advocate_against_2']
export const FOR_SLOTS: AdvocateSlot[] = ['advocate_for_1', 'advocate_for_2']
export const ADVOCATE_SLOTS: AdvocateSlot[] = [...AGAINST_SLOTS, ...FOR_SLOTS]
export const JUDGE_SLOTS: JudgeSlot[] = ['judge_1', 'judge_2', 'judge_3']
export const ALL_SLOTS: Slot[] = [...ADVOCATE_SLOTS, ...JUDGE_SLOTS]

/** Display names only. No judge learns another judge exists. */
export const PERSONA: Record<Slot, string> = {
  advocate_against_1: 'Advocate Vega',
  advocate_against_2: 'Advocate Lyra',
  advocate_for_1: 'Advocate Orion',
  advocate_for_2: 'Advocate Draco',
  judge_1: 'Judge Meridian',
  judge_2: 'Judge Zenith',
  judge_3: 'Judge Solstice',
}
