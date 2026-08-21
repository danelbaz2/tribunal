import type { Charge, LlmCall, Run, Situation, Slot } from '../types'
import type { ExtractedCharge } from '../api'
import { ALL_SLOTS } from '../lib/slots'
import { countWords } from '../lib/derive'

// The reference run, used only when `VITE_USE_FIXTURES=true`.
//
// The text is the placeholder case material from the design handoff — a
// hospital medication-override case. It demonstrates length and shape; it is
// not fixed copy, and it is not the committed backend fixture (`fixtures/`,
// `SPECIFICATION.md` Part 4). Nothing here is used when the backend answers.

export const REFERENCE_CASE_TITLE =
  "Adeyemi — controlled-substance override, St. Alder's Ward 4"

export const REFERENCE_CHARGE_TEXT =
  'On 3 March, during a 41-minute failure of the hospital network, R. Adeyemi, senior duty ' +
  'nurse, forced the emergency override on a locked controlled-substance cabinet and ' +
  'administered 4mg of morphine to a post-operative patient reporting severe pain. Standing ' +
  "policy requires a second clinician's countersignature, recorded electronically, before any " +
  'controlled substance leaves the cabinet. No countersignature was obtained. Adeyemi entered a ' +
  'handwritten record at 21:14 and reported the override to the ward manager the following ' +
  'morning.'

const VEGA = `The countersignature rule was not written for ordinary evenings. It was written for exactly the evening described here: a night when the electronic record is unavailable, when no one can afterwards reconstruct who was present, and when a single clinician holds unsupervised access to a controlled substance. A safeguard that dissolves the moment it becomes inconvenient is not a safeguard.

The hospital had a paper fallback protocol for network failure. It is two pages long, it names the ward manager as the countersigning authority out of hours, and it was not followed. The accused did not face a choice between the patient's pain and the rules; she faced a choice between the rules as written for outages and a faster route she preferred. That the faster route ended well is a fact about luck, not about judgement.

Nor was the interval brief in the sense that matters. Forty-one minutes is time enough to walk to the third floor and return with a second clinician. The record shows the attending was on the premises. No attempt to reach him is documented, and the handwritten note at 21:14 was made after the fact, by the only person with an interest in how it read.

The tribunal should also weigh what it licenses. If the override is held justified here, on this record, then it is justified wherever a clinician sincerely believes the patient is suffering — which is to say, always. The rule would survive only in cases where nobody wanted to break it. I say the act was not justified.`

const LYRA = `I will not argue that the accused was indifferent to her patient. I will argue that the charge file does not contain what would be needed to justify her, and that the absence is her doing.

Consider what is missing. There is no pain score recorded before the override, and none after. There is no note of an attempt to telephone the attending, though the switchboard log would have shown one. There is no second clinician named, no time at which one was sought, no refusal recorded. The only evidence that the situation was urgent is the account of the person who decided it was — written the next morning, to a manager, in the knowledge that a rule had been broken.

Justification is not a feeling; it is a set of facts that a second person can check. Where a clinician bypasses the one control designed to make her account checkable, she cannot then rely on her own account as the ground of her defence. This is not a technicality. It is the difference between a professional judgement and an assertion.

There is a further cost. Every override of this kind that passes unchallenged makes the next one easier and less documented. The ward's medication controls are not a monument to bureaucracy; they are the reason that a missing ampoule can be traced to a person rather than to a night. On the record before this tribunal, the act was not justified.`

const ORION = `A rule that cannot be obeyed does not bind. On the evening in question the countersignature required by policy was an electronic one, and the electronic record was down. The accused was not choosing between compliance and speed; she was standing in front of a locked cabinet holding a control that the institution itself had rendered unavailable, beside a patient in severe pain hours out of surgery.

What she did next is the whole of the case, and it is entirely to her credit. She used the override that the cabinet manufacturer provides for precisely this circumstance — an act which is logged, mechanically, in the cabinet's own memory, and which she could not have concealed had she wished to. She gave a standard dose of a standard drug, not an unusual one. She wrote the administration down within minutes, in ink, with the time. She reported herself the following morning, to the person with the authority to discipline her. Every one of these is the behaviour of a clinician who expected to be examined and intended to be.

Set against that is a countersignature that would have recorded nothing the cabinet did not already record. The safeguard's purpose is traceability, and traceability was preserved. My colleagues opposite ask what this licenses; the answer is narrow and easily stated. It licenses a clinician, during a documented failure of the institution's own systems, to relieve severe pain with a logged and self-reported override. That is not the erosion of a control. It is the control working through its manual channel, which is the reason a manual channel exists.

The duty of care is not suspended when the network is. The act was justified.`

const DRACO = `The charge describes a failure of the institution before it describes an act of the accused. Forty-one minutes without a record is not a condition a ward nurse creates; it is a condition a ward nurse is left standing in. Policy is silent on what a single clinician should do when the countersigning system it depends on has failed, and silence is not permission to let a patient wait.

The tribunal is asked to treat a paper protocol as though it were a live instruction. It is a two-page document filed against an outage that had, at that hour, no precedent on the ward. Its existence is a fact; its reachability at 21:14, on a floor with one duty nurse, is an assumption.

Against that assumption stands a record made in ink, within minutes, by the person the rule was meant to constrain, and handed the next morning to the person able to punish her. The act was justified.`

const ROSTER_IDENTICAL: Record<Slot, string> = Object.fromEntries(
  ALL_SLOTS.map((slot) => [slot, 'meta-llama/llama-3.3-70b-instruct:free']),
) as Record<Slot, string>

const ROSTER_DIFFERENT: Record<Slot, string> = {
  advocate_against_1: 'meta-llama/llama-3.3-70b-instruct:free',
  advocate_against_2: 'qwen/qwen-2.5-72b-instruct:free',
  advocate_for_1: 'google/gemma-2-27b-it:free',
  advocate_for_2: 'mistralai/mistral-small-3.1:free',
  judge_1: 'deepseek/deepseek-r1:free',
  judge_2: 'nousresearch/hermes-3-llama-3.1-405b:free',
  judge_3: 'microsoft/phi-4:free',
}

function statement(slot: Slot, model: string, text: string, durationMs: number): LlmCall {
  return {
    slot,
    stage: 'statement',
    model,
    status: 'done',
    text,
    words: countWords(text),
    durationMs,
    cost: 0,
  }
}

const FINISHED_CALLS: LlmCall[] = [
  statement('advocate_against_1', ROSTER_DIFFERENT.advocate_against_1, VEGA, 12_400),
  statement('advocate_against_2', ROSTER_DIFFERENT.advocate_against_2, LYRA, 9_800),
  statement('advocate_for_1', ROSTER_DIFFERENT.advocate_for_1, ORION, 14_100),
  statement('advocate_for_2', ROSTER_DIFFERENT.advocate_for_2, DRACO, 11_600),
  {
    slot: 'judge_1',
    stage: 'judgment',
    model: ROSTER_DIFFERENT.judge_1,
    status: 'done',
    verdict: 'justified',
    confidence: 0.78,
    reasons: [
      "The countersignature the policy demands was electronic, and the institution's own outage made it unobtainable. A control that the institution has disabled cannot be the ground of the accused's fault.",
      "Traceability, which is the purpose of the control, was preserved: the cabinet logged the override mechanically, and the accused's handwritten entry and self-report add to that record rather than substitute for it.",
      'The dose was ordinary and the indication was severe pain hours after surgery. Nothing in the transcript alleges clinical excess.',
    ],
    words: 0,
    durationMs: 21_600,
    cost: 0,
  },
  {
    slot: 'judge_2',
    stage: 'judgment',
    model: ROSTER_DIFFERENT.judge_2,
    status: 'done',
    verdict: 'justified',
    confidence: 0.61,
    reasons: [
      'The paper fallback protocol raised against the accused names an authority to be reached, not a period during which the patient must wait. Its existence weakens her case but does not defeat it.',
      'Her conduct after the act — an immediate written entry and a voluntary report to the person able to discipline her — is inconsistent with an intent to evade the control.',
      "I hold the act justified with reservation. Had the attending's presence on the premises been shown to be known to her at the time, I would have decided otherwise.",
    ],
    words: 0,
    durationMs: 18_300,
    cost: 0,
  },
  {
    slot: 'judge_3',
    stage: 'judgment',
    model: ROSTER_DIFFERENT.judge_3,
    status: 'done',
    verdict: 'not_justified',
    confidence: 0.71,
    reasons: [
      'A written fallback for network failure existed and was not attempted. The impossibility argued by the advocates for justification is an impossibility only if that document is ignored.',
      'Forty-one minutes, with an attending clinician on the premises, is not an interval in which no second signature could be obtained. The transcript contains no attempt to obtain one.',
      "The urgency relied upon appears only in the accused's own later account. Where the control that would have made her account checkable was bypassed, I cannot treat that account as sufficient.",
    ],
    words: 0,
    durationMs: 16_900,
    cost: 0,
  },
]

const STARTED_AT = new Date(Date.now() - 41_200).toISOString()

/** The run as it stands once all seven calls have succeeded. */
export const REFERENCE_RUN: Run = {
  id: 24,
  caseId: 24,
  caseTitle: REFERENCE_CASE_TITLE,
  status: 'finished',
  situation: 'different',
  seed: '0x5f3a91',
  roster: ROSTER_DIFFERENT,
  startedAt: STARTED_AT,
  finishedAt: new Date(Date.parse(STARTED_AT) + 41_200).toISOString(),
  calls: FINISHED_CALLS,
}

export function fixtureExtract(charge: Charge, file?: File): Promise<ExtractedCharge> {
  if (charge.source === 'file') {
    return Promise.resolve({
      caseId: 24,
      title: file?.name ?? 'charge.pdf',
      wordCount: 1842,
      pages: 4,
      hasTextLayer: true,
    })
  }
  return Promise.resolve({
    caseId: 24,
    title: REFERENCE_CASE_TITLE,
    wordCount: countWords(charge.text),
    hasTextLayer: true,
  })
}

/** The bench last convened, so the replay shows the roster that was chosen. */
let lastSituation: Situation = 'different'

/** The run at the moment it is convened: seven slots, none of them filled. */
export function fixtureRun(situation: Situation): Promise<Run> {
  lastSituation = situation
  const roster = situation === 'identical' ? ROSTER_IDENTICAL : ROSTER_DIFFERENT
  return Promise.resolve({
    ...REFERENCE_RUN,
    status: 'running',
    situation,
    roster,
    startedAt: new Date().toISOString(),
    finishedAt: undefined,
    calls: ALL_SLOTS.map((slot) => ({
      slot,
      stage: slot.startsWith('judge') ? 'judgment' : 'statement',
      model: roster[slot],
      status: 'waiting',
      words: 0,
      durationMs: 0,
      cost: 0,
    })),
  })
}

/**
 * Replays the arrival order: each statement writes, then finishes, in slot
 * order; stage 2 opens only once all four exist; the three judgments then
 * arrive. Timings are compressed — the point is the sequence of states, not
 * how long a free model actually takes.
 */
export function fixtureStream(onRun: (run: Run) => void): () => void {
  const timers: ReturnType<typeof setTimeout>[] = []
  let cancelled = false

  void fixtureRun(lastSituation).then((initial) => {
    if (cancelled) return
    let current = initial
    onRun(current)

    const at = (delay: number, mutate: (run: Run) => Run) => {
      timers.push(
        setTimeout(() => {
          if (cancelled) return
          current = mutate(current)
          onRun(current)
        }, delay),
      )
    }

    const setCall = (run: Run, slot: Slot, patch: Partial<LlmCall>): Run => ({
      ...run,
      calls: run.calls.map((call) => (call.slot === slot ? { ...call, ...patch } : call)),
    })

    const finished = new Map(FINISHED_CALLS.map((call) => [call.slot, call]))
    let clock = 0

    for (const slot of ALL_SLOTS) {
      const done = finished.get(slot)!
      const partial = done.text ? `${done.text.slice(0, 320)}` : undefined
      clock += 700
      at(clock, (run) => setCall(run, slot, { status: 'writing', text: partial, durationMs: 0 }))
      clock += 1400
      at(clock, (run) => setCall(run, slot, { ...done }))
    }

    at(clock + 400, (run) => ({
      ...run,
      status: 'finished',
      finishedAt: new Date().toISOString(),
    }))
  })

  return () => {
    cancelled = true
    timers.forEach(clearTimeout)
  }
}
