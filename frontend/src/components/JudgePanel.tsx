import { Fragment } from 'react'
import type { JudgeSlot, LlmCall, Run } from '../types'
import { JUDGE_SLOTS, PERSONA } from '../lib/slots'
import { bySlot, formatConfidence, formatCost, formatSeconds, verdictLabel } from '../lib/derive'

// Stage 2 — the three judges side by side, parted by 1px dividers. Each judge
// returned its verdict in the required form or the run failed; nothing here is
// read out of prose.
//
// A verdict is never animated from one value to another: a column renders once
// its row exists, and does not change afterwards.

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

function JudgeColumn({ slot, call }: { slot: JudgeSlot; call?: LlmCall }) {
  const justified = call?.verdict === 'justified'

  return (
    <section className="flex flex-col gap-[14px] px-[30px] pb-[32px] pt-[28px]">
      <div className="card-kicker">{slot}</div>
      <h3 className="m-0 text-h3-sm font-normal">{PERSONA[slot]}</h3>

      {call?.verdict ? (
        <>
          <div className="fade-in flex items-baseline gap-[10px]">
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
          <ol className="mb-0 mt-[6px] list-decimal pl-[18px] text-statement">
            {(call.reasons ?? []).map((reason, index, all) => (
              <li key={index} className={index < all.length - 1 ? 'mb-[10px]' : undefined}>
                {reason}
              </li>
            ))}
          </ol>
        </>
      ) : (
        // Waiting and failed judge columns are not designed yet (handoff,
        // "Not designed yet"). Until they are, the column holds its place and
        // says only what is true.
        <p className="text-muted m-0 text-meta">
          {call?.status === 'failed'
            ? (call.error ?? 'The call failed twice. The run is marked failed.')
            : 'Has not ruled.'}
        </p>
      )}

      <div className="hr mb-0 ml-0 mr-0 mt-auto" />
      <div className="card-meta tnum">
        <span>{call?.model ?? 'model not drawn'}</span>
        {call?.status === 'done' && (
          <>
            <span>·</span>
            <span>{formatSeconds(call.durationMs)}</span>
            <span>·</span>
            <span>{formatCost(call.cost)}</span>
          </>
        )}
      </div>
    </section>
  )
}

export function JudgePanel({ run }: { run: Run }) {
  const index = bySlot(run.calls)
  return (
    <div className="grid grid-cols-[1fr_1px_1fr_1px_1fr]">
      {JUDGE_SLOTS.map((slot, position) => (
        <Fragment key={slot}>
          {position > 0 && <div className="bg-divider" />}
          <JudgeColumn slot={slot} call={index[slot]} />
        </Fragment>
      ))}
    </div>
  )
}
