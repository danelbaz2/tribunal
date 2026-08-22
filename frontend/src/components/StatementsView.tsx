import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { AdvocateSlot, LlmCall, Run } from '../types'
import { ADVOCATE_ROWS, AGAINST_SLOTS, APPROACH, FOR_SLOTS, PERSONA, SIDE } from '../lib/slots'
import { bySlot, formatCount, formatSeconds, formatTokens, sideCount } from '../lib/derive'
import { PulseDots } from './PulseDots'
import type { Sequencer } from '../lib/useSequencedScroll'

// Stage one. Against on the left, for on the right, parted by a spine that
// runs the height of the grid.
//
// The pairing is the argument of the layout: row 1 sets the combative
// prosecutor against the purposive defence, row 2 the institutional against the
// forensic. A claim and the answer to it sit on the same line, so the two sides
// can be read across rather than scrolled between. A slot that has not spoken
// keeps its place, so nothing jumps as the room fills.

/**
 * How much of a statement shows before the reader asks for the rest —
 * counted in lines, not pixels, so every card stops at the same point and a
 * collapsed card never cuts a line in half. Four advocates, same clamp: the
 * room reads as one height until a reader opens a card themselves.
 */
const COLLAPSED_LINES = 2

/**
 * How long a slot may sit with no visible text before the label admits it
 * doesn't know whether that is still "reading" -- there is no signal that
 * marks the boundary, only the elapsed wait.
 */
const REASONING_AFTER_MS = 3000

const PHASE = {
  reading: { tag: 'reading…', pulse: 'reading the charge file' },
  reasoning: { tag: 'reasoning…', pulse: 'still reasoning' },
  writing: { tag: 'writing…', pulse: 'writing the statement' },
} as const

/**
 * Three labels, but only one boundary is a real signal: the first visible
 * character arriving marks "writing", because that is the one transition
 * OpenRouter's stream actually reports (`delta.content`, captured in
 * `openrouter.py::_stream`). Reasoning tokens are never sent incrementally --
 * only their count, after the call ends -- so nothing distinguishes "reading"
 * from "reasoning" except how long the wait has gone on. That threshold is a
 * UX convention, not a fact about the model, and does not pretend otherwise.
 */
function useAdvocatePhase(live: boolean, hasText: boolean): keyof typeof PHASE {
  const since = useRef<number | null>(null)
  const [, tick] = useState(0)

  useEffect(() => {
    if (!live) {
      since.current = null
      return
    }
    since.current ??= Date.now()
    if (hasText) return
    const id = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [live, hasText])

  if (hasText) return 'writing'
  if (since.current !== null && Date.now() - since.current >= REASONING_AFTER_MS) return 'reasoning'
  return 'reading'
}

function StatementCard({ slot, call }: { slot: AdvocateSlot; call?: LlmCall }) {
  const [open, setOpen] = useState(false)
  const status = call?.status ?? 'waiting'
  const live = status === 'live'
  const phase = useAdvocatePhase(live, Boolean(call?.text))

  return (
    <article
      className="card gap-3"
      style={{ borderStyle: live ? 'dashed' : 'solid' }}
      aria-busy={live || undefined}
    >
      <header className="flex items-baseline justify-between gap-[12px]">
        <div>
          <div className="card-title text-[20px]">{PERSONA[slot]}</div>
          <div className="card-kicker">
            {slot} · {SIDE[slot]}
          </div>
          {/* What this chair is for. The bench is a set of methods, not a
              cast: a reader should see why two advocates on one side differ. */}
          <div className="text-muted mt-[3px] text-meta-sm italic">{APPROACH[slot]}</div>
        </div>
        {live && <span className="tag tag-outline">{PHASE[phase].tag}</span>}
        {status === 'done' && call && (
          <span className="tag tag-neutral tnum">{formatCount(call.words)} words</span>
        )}
        {status === 'failed' && (
          <span
            className="tag tag-neutral"
            style={{ border: '1px solid var(--color-neutral-400)' }}
          >
            failed
          </span>
        )}
      </header>

      {status === 'waiting' && (
        <p className="text-muted m-0 text-meta">Awaiting the floor.</p>
      )}

      {/* The backend does push the growing text live, but rendering it as it
          arrives repaints the card on every chunk — on a slow connection
          that reads as stutter, not progress. The reveal happens once,
          after the call is whole, on the block below. */}
      {live && <PulseDots label={PHASE[phase].pulse} />}

      {/* The failed state is not designed yet (handoff, "Not designed yet").
          Until it is: name the model, say what happened, keep the colour rule. */}
      {status === 'failed' && call && (
        <p className="m-0 text-meta text-accent-700">
          {call.error ?? 'The call failed twice. The run is marked failed.'}
        </p>
      )}

      {status === 'done' && call && (
        <div className="tb-enter flex flex-col gap-3">
          <div className="w-[34px] border-t-2 border-accent" />

          {/* One block, start to finish — collapsed to a few lines or open to
              the whole thing, never a separate "lede" repeated above it. A
              reader who opens the card should find themselves reading on
              from where they stopped, not starting over. The wipe plays once,
              on arrival — the whole statement is already there, this is a
              reveal of it, not a simulation of writing it. */}
          <StatementProse
            text={call.text ?? ''}
            clampLines={open ? undefined : COLLAPSED_LINES}
            reveal
          />

          <button
            type="button"
            className="btn btn-ghost gap-[6px] self-start text-meta"
            onClick={() => setOpen((was) => !was)}
            aria-expanded={open}
          >
            {open ? 'Fold the statement' : 'Read the full statement'}
            <ChevronDown
              size={14}
              strokeWidth={2}
              className="transition-transform duration-[250ms] ease-out"
              style={{ transform: open ? 'rotate(180deg)' : undefined }}
              aria-hidden
            />
          </button>

          <div className="hr my-[2px]" />
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
    </article>
  )
}

/**
 * `clampLines` set clips to that many lines with a trailing ellipsis, cut
 * clean at a line boundary — never mid-word. Omit it for the full statement.
 *
 * `reveal` plays a one-time wipe on mount — the statement is already whole
 * by the time this renders; the wipe stands in for the wait that just ended,
 * it does not simulate the writing itself.
 */
function StatementProse({
  text,
  clampLines,
  reveal,
}: {
  text: string
  clampLines?: number
  reveal?: boolean
}) {
  const paragraphs = text.split(/\n{2,}/).filter(Boolean)
  return (
    <p
      className={`card-body prose-justified m-0 text-statement opacity-100${reveal ? ' tb-reveal' : ''}`}
      style={
        clampLines
          ? {
              display: '-webkit-box',
              WebkitLineClamp: clampLines,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }
          : undefined
      }
    >
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
    </p>
  )
}

function SideHeading({
  title,
  gloss,
  count,
  align,
}: {
  title: string
  gloss: string
  count: string
  align: 'left' | 'right'
}) {
  return (
    <div
      className="flex items-baseline gap-[12px] py-3"
      style={align === 'left' ? { paddingRight: 30 } : { paddingLeft: 30 }}
    >
      <h4 className="m-0 text-[14px] uppercase tracking-kicker-wide">{title}</h4>
      <span className="text-muted text-meta-sm">{gloss}</span>
      <span className="text-muted tnum ml-auto text-kicker">{count}</span>
    </div>
  )
}

export function StatementsView({ run, sequencer }: { run: Run; sequencer: Sequencer }) {
  const index = bySlot(run.calls)

  return (
    // `min-h-screen`: the auto-scroll to this section fires the instant the
    // trial starts, when every card still reads "Awaiting the floor" and is
    // barely tall. A page that short cannot be scrolled as far as the target
    // math asks for — the browser clamps to what exists and never revisits
    // it once the cards grow. Reserving a full viewport up front means there
    // is always enough room, regardless of how little has arrived yet.
    <section
      ref={sequencer.register('statements', 'section')}
      className="min-h-screen scroll-mt-[60px]"
    >
      <div className="mx-auto max-w-[1320px] px-[48px] pb-6 pt-[44px]">
        <p className="mb-[10px] mt-0 font-heading text-kicker uppercase tracking-kicker-wider text-accent">
          Stage one · statements
        </p>
        <h2 className="mb-2 mt-0 text-[32px] font-normal">The advocates speak, each alone.</h2>
        <p className="text-muted m-0 text-meta">
          Four calls, no rebuttals, no advocate reading another. Each is given the charge file and
          nothing else — the two sides are set opposite so their claims can be read against each
          other.
        </p>
      </div>

      {/* Sticky, so the two sides stay labelled and counted while scrolling —
          which is what makes the comparison readable at all. */}
      <div className="sticky top-[52px] z-[15] border-t border-divider bg-bg [border-bottom:1px_solid_var(--color-accent)]">
        <div className="mx-auto grid max-w-[1320px] grid-cols-[1fr_1px_1fr] px-[48px]">
          <SideHeading
            title="Against"
            gloss="the act was not justified"
            count={sideCount(run, AGAINST_SLOTS)}
            align="left"
          />
          <div className="bg-divider" />
          <SideHeading
            title="For"
            gloss="the act was justified"
            count={sideCount(run, FOR_SLOTS)}
            align="right"
          />
        </div>
      </div>

      <div className="mx-auto grid max-w-[1320px] grid-cols-[1fr_1px_1fr] items-start px-[48px] pb-5">
        {/* The spine, spanning every row. */}
        <div className="col-start-2 row-start-1 bg-divider" style={{ gridRow: '1 / -1' }} />

        {ADVOCATE_ROWS.map((pair, rowIndex) => (
          <Row
            key={rowIndex}
            row={rowIndex + 1}
            pair={pair}
            index={index}
            register={sequencer.register(rowIndex === 0 ? 'rowA' : 'rowB', 'row')}
          />
        ))}
      </div>
    </section>
  )
}

function Row({
  row,
  pair,
  index,
  register,
}: {
  row: number
  pair: { against: AdvocateSlot; for: AdvocateSlot }
  index: Partial<Record<AdvocateSlot, LlmCall>>
  register: (element: HTMLElement | null) => void
}) {
  return (
    <>
      <div
        ref={register}
        className="scroll-mt-[118px] py-[20px] pl-0 pr-[30px]"
        style={{ gridColumn: 1, gridRow: row }}
      >
        <StatementCard slot={pair.against} call={index[pair.against]} />
      </div>
      <div
        className="scroll-mt-[118px] py-[20px] pl-[30px] pr-0"
        style={{ gridColumn: 3, gridRow: row }}
      >
        <StatementCard slot={pair.for} call={index[pair.for]} />
      </div>
    </>
  )
}
