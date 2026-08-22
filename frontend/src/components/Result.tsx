import type { Run } from '../types'
import { JUDGE_SLOTS, PERSONA } from '../lib/slots'
import {
  bySlot,
  formatConfidence,
  formatCount,
  formatSeconds,
  outcome,
  totalThinkingTokens,
  totalTokens,
  verdictLabel,
  verdictSentence,
  wallClockMs,
  wordsArgued,
} from '../lib/derive'
import type { Sequencer } from '../lib/useSequencedScroll'

// The verdict, on the surface ground — the one block in the page that changes
// its footing, because it is the one that answers the question.
//
// Every figure here is derived from the judgment rows at read time. The
// outcome word, the tally, the counts, the totals: none of them is a column
// anywhere, and none is computed twice.

export function Result({
  run,
  sequencer,
  onNewCharge,
  onRunAgain,
  busy,
}: {
  run: Run
  sequencer: Sequencer
  onNewCharge: () => void
  onRunAgain: () => void
  busy?: boolean
}) {
  const { verdict, winning, losing } = outcome(run)
  const index = bySlot(run.calls)

  if (!verdict) return null

  return (
    // `min-h-screen`: see the same note in `StatementsView` — this section
    // is the last one on the page, so if it were shorter than the viewport
    // the browser would have nowhere left to scroll to bring its heading
    // flush under the nav.
    <section
      ref={sequencer.register('verdict', 'section')}
      className="min-h-screen scroll-mt-[60px]"
    >
      <div className="tb-enter border-t border-divider bg-surface px-[48px] pb-[84px] pt-[72px]">
        <div className="mx-auto max-w-[940px] text-center">
          {/* Paragraph-size accent text takes the deep ramp step: the accent on
              this ground is ~3:1, which is chrome contrast, not reading contrast. */}
          <p className="mb-[26px] mt-0 font-heading text-kicker uppercase tracking-kicker-widest text-accent-700">
            The tribunal, having heard four advocates and three judges, finds
          </p>

          <div className="mb-[30px] border-y-2 border-accent px-6 pb-[30px] pt-[34px]">
            <p className="mb-[14px] mt-0 font-heading text-[96px] font-normal uppercase leading-none tracking-[-0.03em]">
              {verdictLabel(verdict)}
            </p>
            <p className="m-0 mx-auto max-w-[38ch] font-heading text-[22px] font-normal">
              {verdictSentence(verdict)}
            </p>
          </div>

          <p className="tnum mb-5 mt-0 font-heading text-base uppercase tracking-kicker">
            Carried {winning} <span className="text-neutral-500">to</span> {losing}
          </p>

          <div className="mb-6 grid grid-cols-3 border-y border-divider">
            {JUDGE_SLOTS.map((slot, position) => {
              const call = index[slot]
              const ruled = call?.verdict
              return (
                <div
                  key={slot}
                  className="px-4 py-[18px]"
                  style={
                    position < JUDGE_SLOTS.length - 1
                      ? { borderRight: '1px solid var(--color-divider)' }
                      : undefined
                  }
                >
                  <div
                    className="mx-auto mb-3 w-[52px] border-t-[3px]"
                    style={{
                      borderTopColor:
                        ruled === 'justified'
                          ? 'var(--color-accent)'
                          : 'var(--color-neutral-400)',
                    }}
                  />
                  <p className="mb-1 mt-0 font-heading text-card-title-sm">{PERSONA[slot]}</p>
                  <p className="text-muted tnum m-0 text-meta-sm">
                    {ruled ? verdictLabel(ruled) : '—'} ·{' '}
                    {formatConfidence(call?.confidence ?? 0)}
                  </p>
                </div>
              )
            })}
          </div>

          <p className="text-muted mx-auto mb-[30px] max-w-[60ch] text-meta">
            Counted from three judgment rows; the line above is derived at read time and stored
            nowhere. One run of one bench is not evidence about models — it is evidence about this
            run.
          </p>

          <div className="tnum mb-7 flex flex-wrap items-center justify-center gap-[26px]">
            <span className="text-muted text-meta-sm">7 calls · 4 statements, 3 judgments</span>
            <span className="text-muted text-meta-sm">
              wall clock {formatSeconds(wallClockMs(run))}
            </span>
            <span className="text-muted text-meta-sm">
              {formatCount(wordsArgued(run))} words argued
            </span>
            <span className="text-muted text-meta-sm">
              {formatCount(totalTokens(run))} tokens generated
              {totalThinkingTokens(run) > 0 &&
                `, ${formatCount(totalThinkingTokens(run))} of them thinking`}
            </span>
          </div>

          <div className="flex justify-center gap-3">
            <button type="button" className="btn btn-secondary" onClick={onNewCharge}>
              Convene on a new charge
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onRunAgain}
              disabled={busy}
            >
              {busy ? 'Convening…' : 'Run it again on this one'}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
