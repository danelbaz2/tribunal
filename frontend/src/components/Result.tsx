import type { Run } from '../types'
import { headline, verdictTally } from '../lib/derive'

// The headline block — the count, and the three-rule tally that reads it at a
// glance. Both are derived from the judgment rows at read time and stored
// nowhere; the sentence is not a field on the run.

export function Result({ run }: { run: Run }) {
  const { justified, notJustified } = headline(run)
  const tally = verdictTally(run)

  return (
    <header className="border-b border-divider px-[44px] pb-[34px] pt-[46px] text-center">
      <p className="mb-4 mt-0 font-heading text-kicker uppercase tracking-kicker-widest text-accent">
        The tribunal finds
      </p>
      <h1 className="tnum mb-[14px] mt-0 text-display-lg font-normal">
        {justified} justified <span className="text-neutral-400">—</span> {notJustified} not
        justified
      </h1>
      <div className="mb-4 flex justify-center gap-[8px]">
        {tally.map((verdict, index) => (
          <div
            key={index}
            className="w-[64px] border-t-[3px]"
            style={{
              borderTopColor:
                verdict === 'justified'
                  ? 'var(--color-accent)'
                  : verdict === 'not_justified'
                    ? 'var(--color-neutral-400)'
                    : 'var(--color-neutral-300)',
            }}
          />
        ))}
      </div>
      <p className="text-muted m-0 text-meta">
        Counted from three judgment rows. The sentence above is derived at read time and stored
        nowhere.
      </p>
    </header>
  )
}
