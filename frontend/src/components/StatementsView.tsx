import type { AdvocateSlot, LlmCall, Run } from '../types'
import { AGAINST_SLOTS, FOR_SLOTS, PERSONA } from '../lib/slots'
import { bySlot, formatCost, formatCount, formatSeconds } from '../lib/derive'

// Stage 1 — the four statements, against on the left, for on the right, parted
// by a 1px aisle. Sides are distinguished by position and label only, never by
// a color fill.
//
// Slot order is fixed and never sorted by arrival: a slot that has not produced
// text yet holds its place.

function SideHeading({ children }: { children: string }) {
  return (
    <div className="flex items-baseline gap-[12px]">
      <div className="w-[26px] border-t-2 border-accent" />
      <h4 className="m-0 text-[15px] uppercase tracking-kicker-wide">{children}</h4>
    </div>
  )
}

function CardHeader({ slot, right }: { slot: AdvocateSlot; right: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-[12px]">
      <div>
        <div className="card-title text-card-title">{PERSONA[slot]}</div>
        <div className="card-kicker">{slot}</div>
      </div>
      {right}
    </div>
  )
}

function Meta({ parts }: { parts: string[] }) {
  return (
    <div className="card-meta tnum">
      {parts.map((part, index) => (
        <span key={part + index}>
          {index > 0 && <span className="mr-[6px]">·</span>}
          {part}
        </span>
      ))}
    </div>
  )
}

function StatementBody({ text, caret }: { text: string; caret?: boolean }) {
  const paragraphs = text.split(/\n{2,}/)
  return (
    <p className="card-body prose-justified text-statement opacity-100">
      {paragraphs.map((paragraph, index) => (
        <span key={index}>
          {index > 0 && (
            <>
              <br />
              <br />
            </>
          )}
          {paragraph}
        </span>
      ))}
      {caret && (
        <span
          className="caret-blink ml-[2px] inline-block h-[15px] w-[8px] align-[-2px] bg-accent"
          aria-hidden
        />
      )}
    </p>
  )
}

export function StatementCard({ slot, call }: { slot: AdvocateSlot; call?: LlmCall }) {
  const status = call?.status ?? 'waiting'

  if (status === 'done' && call) {
    return (
      <article className="card fade-in">
        <CardHeader
          slot={slot}
          right={
            <span className="tag tag-neutral tnum">{formatCount(call.words)} words</span>
          }
        />
        <StatementBody text={call.text ?? ''} />
        <div className="hr my-[2px]" />
        <Meta parts={[call.model, formatSeconds(call.durationMs), formatCost(call.cost)]} />
      </article>
    )
  }

  if (status === 'writing' && call) {
    return (
      <article className="card fade-in" style={{ borderStyle: 'dashed' }}>
        <CardHeader slot={slot} right={<span className="tag tag-outline">writing…</span>} />
        <StatementBody text={call.text ?? ''} caret />
        <div className="hr my-[2px]" />
        <Meta
          parts={[call.model, `${formatSeconds(call.durationMs)} elapsed`, formatCost(call.cost)]}
        />
      </article>
    )
  }

  if (status === 'failed' && call) {
    // The failed-run state is not designed yet (handoff, "Not designed yet").
    // Until it is: name the slot and the model, say nothing more, and keep the
    // color rule — the mark is a neutral outline, not a red fill.
    return (
      <article className="card fade-in" style={{ borderStyle: 'dashed' }}>
        <CardHeader
          slot={slot}
          right={
            <span
              className="tag tag-neutral"
              style={{ border: '1px solid var(--color-neutral-400)' }}
            >
              failed
            </span>
          }
        />
        <p className="m-0 text-meta text-accent-700">
          {call.error ?? 'The call failed twice. The run is marked failed.'}
        </p>
        <div className="hr my-[2px]" />
        <Meta parts={[call.model, formatSeconds(call.durationMs), formatCost(call.cost)]} />
      </article>
    )
  }

  return (
    <article className="card" style={{ borderStyle: 'dashed' }}>
      <CardHeader slot={slot} right={<span className="tag tag-neutral">waiting</span>} />
      <div className="min-h-[64px]" />
      <div className="hr my-[2px]" />
      <Meta parts={[call?.model ?? 'model not drawn']} />
    </article>
  )
}

export function StatementsView({ run }: { run: Run }) {
  const index = bySlot(run.calls)

  const side = (slots: AdvocateSlot[], heading: string) => (
    <div className="flex flex-col gap-[24px] px-[32px] pb-[34px] pt-[26px]">
      <SideHeading>{heading}</SideHeading>
      {slots.map((slot) => (
        <StatementCard key={slot} slot={slot} call={index[slot]} />
      ))}
    </div>
  )

  return (
    <div className="grid grid-cols-[1fr_1px_1fr]">
      {side(AGAINST_SLOTS, 'Against — not justified')}
      {/* The aisle. */}
      <div className="bg-divider" />
      {side(FOR_SLOTS, 'For — justified')}
    </div>
  )
}
