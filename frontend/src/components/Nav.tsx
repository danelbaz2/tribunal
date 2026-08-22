// The sticky header. It carries the only sense of place the page has, because
// the four stages are sections of one route rather than four screens: the
// current stage is the accent, the rest recede to neutral-500.

const STAGES = [
  '1 · The charge',
  '2 · The advocates',
  '3 · The judges',
  '4 · The verdict',
] as const

/** Which stage the run is in, derived from how many participants have returned. */
export function currentStage(started: boolean, done: number): number {
  if (!started) return 0
  if (done < 4) return 1
  if (done < 7) return 2
  return 3
}

export function Nav({
  started,
  done,
}: {
  started: boolean
  done: number
}) {
  const stage = currentStage(started, done)
  const status = started ? `${done} of 7 calls returned` : 'idle · 7 slots waiting'

  return (
    <nav className="nav sticky top-0 z-20 bg-bg">
      <span className="nav-brand">Tribunal</span>
      {STAGES.map((label, index) => (
        <span
          key={label}
          className="font-heading text-kicker uppercase tracking-kicker-wide"
          style={{
            color: index === stage ? 'var(--color-accent)' : 'var(--color-neutral-500)',
          }}
          aria-current={index === stage ? 'step' : undefined}
        >
          {label}
        </span>
      ))}
      <span className="text-muted tnum ml-auto text-kicker">{status}</span>
    </nav>
  )
}
