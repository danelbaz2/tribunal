import { useMemo, useState } from 'react'
import { Nav } from '../components/Nav'
import { ChargeUpload } from '../components/ChargeUpload'
import { RosterView } from '../components/RosterView'
import { StatementsView } from '../components/StatementsView'
import { JudgePanel } from '../components/JudgePanel'
import { Result } from '../components/Result'
import { submitCharge } from '../api'
import { countWords, doneCount, failedCalls } from '../lib/derive'
import { useRunStore } from '../lib/runStore'
import { ADVOCATE_SLOTS } from '../lib/slots'
import { stepFor, useAutoScrollEscape, useSequencedScroll } from '../lib/useSequencedScroll'
import type { Charge, Run, Situation } from '../types'

// The whole trial, on one page.
//
// It is one route rather than four screens because there is one act in it: the
// user supplies a charge, presses convene, and everything after that happens
// without them. Three routes implied three decisions; there is only ever one.
//
// The page follows the run down: the statements heading when it starts, the
// judgment heading once every advocate has spoken, the verdict once every
// judge has ruled — each stage's own framing first, its cards read together
// underneath. It stops following the moment the reader scrolls for
// themselves.

/**
 * The client-side floor for "too short". A pre-check, not the ruling — whether
 * a document accuses anybody of anything is decided by the backend at upload,
 * and its refusal is what gets shown.
 */
const MIN_CHARGE_WORDS = 25

/**
 * Where the reader already is when a run fails — not at the top of the page,
 * which by then is scrolled well out of view. A run only ever fails one
 * stage: every failed slot is an advocate, or every failed slot is a judge,
 * never a mix, so the failed slots alone say which section to land next to.
 */
function FailureBanner({ run, onStartOver }: { run: Run; onStartOver: () => void }) {
  return (
    <div className="mx-auto max-w-[1320px] px-[48px] pb-[34px]">
      <div
        className="tb-enter flex items-center justify-between gap-4 border border-accent px-5 py-4"
        role="alert"
      >
        <p className="m-0 text-meta text-accent-700">
          The run failed —{' '}
          {failedCalls(run)
            .map((call) => `${call.slot} (${call.model})`)
            .join(', ')}
          . All seven calls must succeed or nothing is kept.
        </p>
        <button type="button" className="btn btn-secondary shrink-0" onClick={onStartOver}>
          Start over
        </button>
      </div>
    </div>
  )
}

export function NewTrial() {
  const { run, error, start, reset } = useRunStore()

  const [text, setText] = useState('')
  const [situation, setSituation] = useState<Situation>('identical')
  const [convening, setConvening] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const started = run !== null
  const done = run ? doneCount(run) : 0
  const running = run?.status === 'running'
  // A run fails one stage at a time: every failed slot is an advocate, or
  // every failed slot is a judge, never a mix — so the first failed slot
  // alone says which section the banner belongs next to.
  const failedInAdvocates = run
    ? failedCalls(run).every((call) => (ADVOCATE_SLOTS as readonly string[]).includes(call.slot))
    : true

  const following = useAutoScrollEscape(running)
  const sequencer = useSequencedScroll(stepFor(done, started), following)

  const wordCount = useMemo(() => countWords(text), [text])

  const charge: Charge = useMemo(() => ({ text, wordCount }), [text, wordCount])

  const valid = wordCount >= MIN_CHARGE_WORDS

  async function convene(caseId?: number) {
    setSubmitError(null)
    setConvening(true)
    try {
      const id = caseId ?? (await submitCharge(charge)).caseId
      await start(id, situation)
      sequencer.goTo('statements')
    } catch (cause) {
      setSubmitError((cause as Error).message)
    } finally {
      setConvening(false)
    }
  }

  function handleConvene() {
    setSubmitError(null)

    if (wordCount === 0) {
      setSubmitError('The charge file is empty. There is nothing here to try.')
      return
    }
    if (!valid) {
      setSubmitError(
        `A charge of ${wordCount} words is too short to argue. Supply at least ${MIN_CHARGE_WORDS}.`,
      )
      return
    }
    void convene()
  }

  function startOver() {
    reset()
    setSubmitError(null)
    sequencer.toTop()
  }

  return (
    <div className="min-h-screen">
      <Nav started={started} done={done} />

      <section className="border-b border-divider px-[48px] pb-[72px] pt-[64px]">
        <div className="mx-auto max-w-[900px]">
          <p className="mb-[14px] mt-0 font-heading text-kicker uppercase tracking-kicker-wider text-accent">
            Instrument of deliberation
          </p>
          <h1 className="mb-[18px] mt-0 max-w-[15ch] text-[54px] font-normal leading-[1.12] tracking-[-0.02em]">
            A trial held entirely by machines.
          </h1>
          <p className="prose-justified mb-[30px] mt-0 max-w-[62ch] text-lede">
            Four advocates read the charge and never read one another — two arguing the act was{' '}
            <em>not justified</em>, two that it <em>was</em>. Three judges then read the four
            statements, and never read one another either. Each commits to a binary verdict with a
            confidence and at least two reasons. Seven independent calls, and nothing inferred from
            prose.
          </p>

          <div className="hr mb-6 mt-0" />

          <ChargeUpload text={text} onTextChange={setText} wordCount={wordCount} />

          <div className="hr mb-6 mt-0" />

          <RosterView situation={situation} onChange={setSituation} disabled={running} />

          <div className="hr mb-[22px] mt-0" />

          {(submitError || error) && (
            <p className="tb-enter mb-[14px] text-meta text-accent-700" role="alert">
              {submitError ?? error}
            </p>
          )}

          <div className="flex items-center gap-4">
            <button
              type="button"
              className="btn btn-primary px-[22px] py-[11px] text-[15px]"
              disabled={!valid || convening || running}
              onClick={handleConvene}
            >
              {convening ? 'Convening…' : started ? 'Convene again' : 'Convene the tribunal'}
            </button>
            <span className="text-muted max-w-[52ch] text-meta">
              Once convened the trial runs to its end without you: four statements, then three
              judgments, then the count.
            </span>
          </div>
        </div>
      </section>

      {run && <StatementsView run={run} sequencer={sequencer} />}
      {run && run.status === 'failed' && failedInAdvocates && (
        <FailureBanner run={run} onStartOver={startOver} />
      )}
      {run && done >= 4 && <JudgePanel run={run} sequencer={sequencer} />}
      {run && run.status === 'failed' && !failedInAdvocates && (
        <FailureBanner run={run} onStartOver={startOver} />
      )}
      {run && done >= 7 && (
        <Result
          run={run}
          sequencer={sequencer}
          busy={convening}
          onNewCharge={() => {
            setText('')
            sequencer.toTop()
          }}
          onRunAgain={() => void convene(run.caseId)}
        />
      )}
    </div>
  )
}
