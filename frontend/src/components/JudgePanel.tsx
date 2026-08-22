import { Fragment } from 'react'
import type { JudgeSlot, LlmCall, Run } from '../types'
import { APPROACH, JUDGE_SLOTS, PERSONA } from '../lib/slots'
import { bySlot, formatConfidence, formatSeconds, formatTokens, verdictLabel } from '../lib/derive'
import { PulseDots } from './PulseDots'
import type { Sequencer } from '../lib/useSequencedScroll'

// Stage two. Three columns parted by hairlines, each judge alone in theirs.
//
// A verdict is never animated from one value to another: a column renders once
// its row exists and does not change afterwards.

function ConfidenceBar({ confidence, justified }: { confidence: number; justified: boolean }) {
  const remaining = Math.round((1 - Math.min(Math.max(confidence, 0), 1)) * 100)
  return (
    <div className="relative h-[2px] bg-neutral-300">
      <div
        className="absolute"
        style={{
          inset: `0 ${remaining}% 0 0`,
          background: justified ? 'var(--color-accent)' : 'var(--color-neutral-700)',
        }}
      />
    </div>
  )
}

function JudgeColumn({
  slot,
  call,
  register,
}: {
  slot: JudgeSlot
  call?: LlmCall
  register: (element: HTMLElement | null) => void
}) {
  const status = call?.status ?? 'waiting'
  const justified = call?.verdict === 'justified'

  return (
    <section
      ref={register}
      className="flex scroll-mt-[70px] flex-col gap-[14px] px-[30px] pb-[34px] pt-[28px]"
    >
      <div className="card-kicker">{slot}</div>
      <h3 className="m-0 text-h3-sm font-normal">{PERSONA[slot]}</h3>
      <p className="text-muted -mt-2 text-meta-sm italic">{APPROACH[slot]}</p>

      {status === 'waiting' && (
        <p className="text-muted m-0 text-meta">Sealed until every statement exists.</p>
      )}

      {status === 'live' && (
        <div className="flex flex-col gap-[10px]">
          <PulseDots label="weighing the statements" />
          {/* No partial verdict exists to show — a judge returns one
              structured object or nothing. These stand for the wait without
              pretending to be the reasons that haven't been written yet. */}
          <div className="flex flex-col gap-[7px]" aria-hidden>
            <div className="tb-shimmer-line" style={{ width: '92%' }} />
            <div className="tb-shimmer-line" style={{ width: '78%' }} />
            <div className="tb-shimmer-line" style={{ width: '85%' }} />
          </div>
        </div>
      )}

      {status === 'failed' && call && (
        <p className="m-0 text-meta text-accent-700">
          {call.error ?? 'The call failed twice. The run is marked failed.'}
        </p>
      )}

      {status === 'done' && call?.verdict && (
        <div className="tb-enter flex flex-col gap-[14px]">
          <div className="flex items-baseline gap-[10px]">
            <span
              className={justified ? 'tag tag-outline' : 'tag tag-neutral'}
              style={{
                fontSize: '12px',
                padding: '4px 12px',
                ...(justified ? {} : { border: '1px solid var(--color-neutral-400)' }),
              }}
            >
              {verdictLabel(call.verdict)}
            </span>
            <span className="text-muted tnum text-meta-sm">
              confidence {formatConfidence(call.confidence ?? 0)}
            </span>
          </div>

          <ConfidenceBar confidence={call.confidence ?? 0} justified={justified} />

          {/* At least two reasons, always — the contract requires it. */}
          <ol className="m-0 list-decimal pl-[18px] text-statement">
            {(call.reasons ?? []).map((reason, index, all) => (
              <li key={index} className={index < all.length - 1 ? 'mb-[10px]' : undefined}>
                {reason}
              </li>
            ))}
          </ol>

          <div className="hr mb-0 mt-[6px]" />
          <div className="card-meta tnum">
            <span>{call.model}</span>
            <span>·</span>
            <span>{formatSeconds(call.durationMs)}</span>
            {formatTokens(call) && (
              <>
                <span>·</span>
                <span>{formatTokens(call)}</span>
              </>
            )}
            {(call.attempts ?? 0) > 1 && (
              <>
                <span>·</span>
                <span>asked twice</span>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

export function JudgePanel({ run, sequencer }: { run: Run; sequencer: Sequencer }) {
  const index = bySlot(run.calls)

  return (
    // `min-h-screen`: see the same note in `StatementsView` — the scroll to
    // this section fires the instant it mounts, when every column still
    // reads "Sealed until every statement exists" and is too short for the
    // browser to scroll as far as the target math asks for.
    <section
      ref={sequencer.register('judges', 'section')}
      className="min-h-screen scroll-mt-[60px] border-t border-divider"
    >
      <div className="tb-enter">
        <div className="mx-auto max-w-[1320px] border-b border-divider px-[48px] pb-[22px] pt-[44px]">
          <p className="mb-[10px] mt-0 font-heading text-kicker uppercase tracking-kicker-wider text-accent">
            Stage two · judgment
          </p>
          <h2 className="mb-2 mt-0 text-[32px] font-normal">
            The judges read the four statements.
          </h2>
          <p className="text-muted m-0 text-meta">
            The same transcript to each, carrying personas and no model names. No judge learns
            another judge exists. The three read by different lights — purpose, text, and
            practice.
          </p>
        </div>

        <div className="mx-auto grid max-w-[1320px] grid-cols-[1fr_1px_1fr_1px_1fr]">
          {JUDGE_SLOTS.map((slot, position) => (
            <Fragment key={slot}>
              {position > 0 && <div className="bg-divider" />}
              <JudgeColumn
                slot={slot}
                call={index[slot]}
                register={sequencer.register(slot, 'judge')}
              />
            </Fragment>
          ))}
        </div>
      </div>
    </section>
  )
}
