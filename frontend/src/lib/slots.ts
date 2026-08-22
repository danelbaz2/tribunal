import type { AdvocateSlot, JudgeSlot, Slot } from '../types'

// Slots and personas are fixed; only the model in each chair varies.

export const AGAINST_SLOTS: AdvocateSlot[] = ['advocate_against_1', 'advocate_against_2']
export const FOR_SLOTS: AdvocateSlot[] = ['advocate_for_1', 'advocate_for_2']
export const ADVOCATE_SLOTS: AdvocateSlot[] = [...AGAINST_SLOTS, ...FOR_SLOTS]
export const JUDGE_SLOTS: JudgeSlot[] = ['judge_1', 'judge_2', 'judge_3']
export const ALL_SLOTS: Slot[] = [...ADVOCATE_SLOTS, ...JUDGE_SLOTS]

/**
 * The order participants complete in, which is not the order they are laid out
 * in. The two sides are set opposite so a claim and its answer sit on the same
 * row, so the room fills across the aisle rather than down one column:
 *
 *   row 1   Vega (against)  ↔  Orion (for)
 *   row 2   Lyra (against)  ↔  Draco (for)
 *   then    Meridian, Zenith, Solstice
 *
 * Everything is rendered and counted in this order, never in order of arrival.
 */
export const DISPLAY_ORDER: Slot[] = [
  'advocate_against_1',
  'advocate_for_1',
  'advocate_against_2',
  'advocate_for_2',
  'judge_1',
  'judge_2',
  'judge_3',
]

/** The two rows of the advocates' grid, each a facing pair. */
export const ADVOCATE_ROWS: { against: AdvocateSlot; for: AdvocateSlot }[] = [
  { against: 'advocate_against_1', for: 'advocate_for_1' },
  { against: 'advocate_against_2', for: 'advocate_for_2' },
]

/**
 * Display names only. No judge learns another judge exists.
 *
 * Each chair is a school of legal reasoning rather than a person — the voice
 * lives in `backend/app/tribunal/prompts/personas/`, fixed across every run.
 */
export const PERSONA: Record<Slot, string> = {
  advocate_against_1: 'Prosecutor Ben-Ari',
  advocate_against_2: 'Prosecutor Eldad',
  advocate_for_1: 'Advocate Feldman',
  advocate_for_2: 'Advocate Ben Zur',
  judge_1: 'Justice Barak',
  judge_2: 'Justice Sohlberg',
  judge_3: 'Justice Rubinstein',
}

/** What each chair is for, shown under the name so the bench reads as a set
 *  of methods rather than as a cast. */
export const APPROACH: Record<Slot, string> = {
  advocate_against_1: 'no tolerance for a rule treated as a suggestion',
  advocate_against_2: 'consequence and precedent, coldly',
  advocate_for_1: 'the purpose a rule was written to serve',
  advocate_for_2: 'the record, clause by clause',
  judge_1: 'purposive interpretation and proportionality',
  judge_2: 'textual fidelity and judicial restraint',
  judge_3: 'practical wisdom and balance',
}

/** The side an advocate argues, as it appears under their name. */
export const SIDE: Record<AdvocateSlot, 'against' | 'for'> = {
  advocate_against_1: 'against',
  advocate_against_2: 'against',
  advocate_for_1: 'for',
  advocate_for_2: 'for',
}

export function isAdvocate(slot: Slot): slot is AdvocateSlot {
  return slot.startsWith('advocate_')
}
