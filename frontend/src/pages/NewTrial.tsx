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
 * Pinned to the bottom of the viewport, not dropped into the page flow: when a
 * run fails the reader is scrolled deep into the statements or the judges, and
 * an inline banner there is as easy to miss as the top of the page. This one
 * is in view wherever they are, and carries the two ways forward — retry the
 * same charge, or clear everything and start again.
 */
function FailureBanner({
  run,
  onRetry,
  onStartOver,
  busy,
}: {
  run: Run
  onRetry: () => void
  onStartOver: () => void
  busy: boolean
}) {
  return (
    <div
      className="tb-enter fixed inset-x-0 bottom-0 z-50 border-t border-accent bg-accent-100 shadow-lg"
      role="alert"
    >
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-4 px-[48px] py-[16px]">
        <p className="m-0 max-w-[70ch] text-meta text-accent-800">
          <span className="font-medium">The run failed after every retry</span> —{' '}
          {failedCalls(run)
            .map((call) => `${call.slot} (${call.model})`)
            .join(', ')}
          . All seven calls must succeed or nothing is kept.
        </p>
        <div className="flex shrink-0 gap-3">
          <button
            type="button"
            className="btn btn-primary"
            onClick={onRetry}
            disabled={busy}
          >
            {busy ? 'Convening…' : 'Try the same charge again'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={onStartOver}>
            Start over
          </button>
        </div>
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
  const failed = run?.status === 'failed'

  const following = useAutoScrollEscape(running)
  const sequencer = useSequencedScroll(stepFor(done, started), following)

  const wordCount = useMemo(() => countWords(text), [text])

  const charge: Charge = useMemo(() => ({ text, wordCount }), [text, wordCount])

  const valid = wordCount >= MIN_CHARGE_WORDS

  async function convene(caseId?: number) {
    setSubmitError(null)
    setConvening(true)
    try {
      // No caseId and nothing pasted: the run falls back to the default charge.
      const id =
        caseId ?? (wordCount > 0 ? (await submitCharge(charge)).caseId : undefined)
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

    if (wordCount > 0 && !valid) {
      setSubmitError(
        `A charge of ${wordCount} words is too short to argue. Supply at least ${MIN_CHARGE_WORDS}, or clear the box to try the default charge.`,
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
    <div className={`min-h-screen${failed ? ' pb-[140px]' : ''}`}>
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
              disabled={convening || running}
              onClick={handleConvene}
            >
              {convening ? 'Convening…' : started ? 'Convene again' : 'Convene the tribunal'}
            </button>
            <span className="text-muted max-w-[52ch] text-meta">
              {wordCount === 0
                ? 'No charge supplied: the tribunal will try the canonical charge sheet, The Realm v. Jon Snow.'
                : 'Once convened the trial runs to its end without you: four statements, then three judgments, then the count.'}
            </span>
          </div>
        </div>
      </section>

      {run && <StatementsView run={run} sequencer={sequencer} />}
      {run && done >= 4 && <JudgePanel run={run} sequencer={sequencer} />}
      {run && failed && (
        <FailureBanner
          run={run}
          busy={convening}
          onRetry={() => void convene(run.caseId)}
          onStartOver={startOver}
        />
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
