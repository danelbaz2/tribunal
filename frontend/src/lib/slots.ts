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
 *   row 1   Daenerys (against)  ↔  Jon Snow (for)
 *   row 2   Grey Worm (against) ↔  Tyrion (for)
 *   then    Barak, Elon, Shamgar
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
 * The seven archetypes of the case design dossier — four representatives with
 * fixed sides, three judges each after a school of judicial reasoning. The
 * voice lives in `backend/app/tribunal/prompts/personas/`, fixed across every
 * run, and carries method only.
 */
export const PERSONA: Record<Slot, string> = {
  advocate_against_1: 'Daenerys Targaryen',
  advocate_against_2: 'Grey Worm',
  advocate_for_1: 'Jon Snow',
  advocate_for_2: 'Tyrion Lannister',
  judge_1: 'The Barak model',
  judge_2: 'The Elon model',
  judge_3: 'The Shamgar model',
}

/** What each chair is for, shown under the name so the bench reads as a set
 *  of methods rather than as a cast. */
export const APPROACH: Record<Slot, string> = {
  advocate_against_1: 'command, and a killing taken in private is not justice',
  advocate_against_2: 'the timeline, and the safer step not taken',
  advocate_for_1: 'duty, and what was known in the moment',
  advocate_for_2: 'motives, consequences, and every alternative',
  judge_1: 'purposive interpretation and proportionality',
  judge_2: 'tradition, and the limits of a court',
  judge_3: 'offices and powers before moral intuition',
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
