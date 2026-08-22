import { useCallback, useEffect, useRef, useState } from 'react'

// The page follows the run. One number — how many participants have returned —
// decides where it goes next.
//
// In the prototype a timer drove this. Here the backend's event stream does:
// a step fires on the transition that produced it, not on a schedule, so a
// slow free model simply means the page waits with the reader rather than
// scrolling past an empty card.

/** Clearance for the sticky chrome above a row or judge column target. */
const OFFSET = {
  row: 118, // header + the sticky side header
  judge: 70,
} as const

/** Fallback clearance for a section heading, if the sticky nav cannot be measured. */
const FALLBACK_SECTION_OFFSET = 60

export type ScrollTarget = keyof typeof OFFSET | 'section'

/**
 * Scroll one element into view under the sticky chrome.
 *
 * `scrollIntoView` is deliberately not used: it cannot be told about the
 * sticky header, and with `block: 'start'` it puts the target underneath it.
 *
 * A section heading's offset is measured from the live nav bar rather than a
 * constant, so the title lands flush against it exactly — a guessed pixel
 * figure drifts the moment the nav's own height changes.
 */
function scrollToElement(element: HTMLElement, kind: ScrollTarget) {
  const offset =
    kind === 'section'
      ? (document.querySelector('nav.nav')?.getBoundingClientRect().height ??
        FALLBACK_SECTION_OFFSET)
      : OFFSET[kind]
  const top = element.getBoundingClientRect().top + window.scrollY - offset
  window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
}

export interface Sequencer {
  /** Register an element as a scroll target. */
  register: (key: string, kind: ScrollTarget) => (element: HTMLElement | null) => void
  /** Go somewhere directly — the convene button and the reset action use this. */
  goTo: (key: string) => void
  toTop: () => void
}

/**
 * @param step   the key to scroll to, or null to stay put. Changing it moves
 *               the page once.
 * @param enabled  the escape hatch: false leaves the reader where they are.
 */
export function useSequencedScroll(step: string | null, enabled: boolean): Sequencer {
  const nodes = useRef(new Map<string, { element: HTMLElement; kind: ScrollTarget }>())
  const lastStep = useRef<string | null>(null)

  const register = useCallback(
    (key: string, kind: ScrollTarget) => (element: HTMLElement | null) => {
      if (element) nodes.current.set(key, { element, kind })
      else nodes.current.delete(key)
    },
    [],
  )

  const goTo = useCallback((key: string) => {
    // The heading font (Cormorant Garamond) loads after first paint. A
    // measurement taken before it swaps in is stale the moment it does: the
    // hero title rewraps onto an extra line and every target below it moves.
    // `fonts.ready` is the actual signal for "layout has stopped moving for
    // this reason" — a fixed delay would either fire too soon on a slow
    // connection or waste time on a warm cache.
    const settled = document.fonts?.ready ?? Promise.resolve()
    void settled.then(() => {
      // After the frame that rendered the section, or it has no position yet.
      requestAnimationFrame(() => {
        const node = nodes.current.get(key)
        if (node) scrollToElement(node.element, node.kind)
      })
    })
  }, [])

  const toTop = useCallback(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (!enabled || step === null || step === lastStep.current) return
    lastStep.current = step
    goTo(step)
  }, [step, enabled, goTo])

  return { register, goTo, toTop }
}

/**
 * Where the page should be, given how many participants have returned.
 *
 * Three stops, one per stage: the statements heading when the trial starts,
 * the judgment heading once every advocate has spoken, and the verdict once
 * every judge has ruled. Each lands on the section's own header, not on a
 * card inside it, so the stage's framing (title, intro, sticky bar) is what
 * the reader sees first, with its cards read together underneath.
 */
export function stepFor(done: number, started: boolean): string | null {
  if (!started) return null
  if (done === 0) return 'statements'
  if (done === 4) return 'judges'
  if (done === 7) return 'verdict'
  return null
}

/**
 * Stops following once the reader takes over.
 *
 * A page that keeps yanking someone back while they are reading a statement is
 * worse than one that never scrolled. Any wheel, touch or key scroll turns it
 * off for the rest of the run.
 */
export function useAutoScrollEscape(active: boolean): boolean {
  const [escaped, setEscaped] = useState(false)

  useEffect(() => {
    if (!active) {
      setEscaped(false)
      return
    }
    const surrender = () => setEscaped(true)
    const options = { passive: true } as const
    window.addEventListener('wheel', surrender, options)
    window.addEventListener('touchmove', surrender, options)
    return () => {
      window.removeEventListener('wheel', surrender)
      window.removeEventListener('touchmove', surrender)
    }
  }, [active])

  return !escaped
}
