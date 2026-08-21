import { useEffect } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Nav } from '../components/Nav'
import { StatementsView } from '../components/StatementsView'
import { useRunStore } from '../lib/runStore'
import { judgments, stageOneComplete, statementsIn } from '../lib/derive'
import { JUDGE_SLOTS, PERSONA } from '../lib/slots'

// Screen 2 — stage 1 filling the room, in slot order, live. There is no human
// in the loop here: the run reaches its end on its own, and the judgment
// follows without asking.

export function Courtroom() {
  const { run, error } = useRunStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (run?.status === 'finished') navigate('/judgment', { replace: true })
  }, [run?.status, navigate])

  if (!run) return <Navigate to="/" replace />

  const stageOneDone = stageOneComplete(run)
  const judged = judgments(run).filter((call) => call?.status === 'done').length

  const status = stageOneDone
    ? `Run ${run.id} · stage 2 of 2 · ${judged} of 3 judgments in`
    : `Run ${run.id} · stage 1 of 2 · ${statementsIn(run)} of 4 statements in`

  const bench = JUDGE_SLOTS.map((slot) => PERSONA[slot].replace('Judge ', '')).join(' · ')

  return (
    <>
      <Nav status={status} />

      <header className="border-b border-divider px-[44px] pb-[20px] pt-[32px]">
        <p className="mb-[10px] mt-0 font-heading text-kicker uppercase tracking-kicker-wider text-accent">
          Case in hearing
        </p>
        <h2 className="mb-[10px] mt-0 text-h2 font-normal">{run.caseTitle}</h2>
        <p className="text-muted m-0 text-meta">
          The four advocates argue in parallel and in isolation. No rebuttals. No advocate reads
          another.
        </p>
      </header>

      {error && (
        <p className="fade-in px-[44px] py-3 text-meta text-accent-700" role="alert">
          {error}
        </p>
      )}

      <StatementsView run={run} />

      <footer className="flex items-center gap-5 border-t border-divider px-[44px] py-[18px]">
        <span className="font-heading text-body-sm uppercase tracking-kicker text-accent">
          Stage 2 · judgment
        </span>
        <span className="text-muted text-meta">
          Sealed until all four statements exist. Every judge then reads the same transcript, and
          none of them reads another judge.
        </span>
        <span className="text-muted tnum ml-auto text-meta-sm">
          Judges {bench} — {stageOneDone ? `${judged} of 3 returned` : 'waiting'}
        </span>
      </footer>
    </>
  )
}
