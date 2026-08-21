import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Nav } from '../components/Nav'
import { Result } from '../components/Result'
import { JudgePanel } from '../components/JudgePanel'
import { useRunStore } from '../lib/runStore'
import {
  formatCost,
  formatCount,
  formatSeconds,
  statements,
  succeededCalls,
  totalCost,
  wallClockMs,
} from '../lib/derive'

// Screen 3 — the count, and the reasoning that produced it. Every figure in
// the footer is derived from the call rows; none of them is stored.

export function Judgment() {
  const { run } = useRunStore()
  const navigate = useNavigate()
  const [convening, setConvening] = useState(false)
  const { start } = useRunStore()

  if (!run) return <Navigate to="/" replace />

  const wordsArgued = statements(run).reduce((sum, call) => sum + (call?.words ?? 0), 0)

  async function convokeAgain() {
    if (!run) return
    setConvening(true)
    try {
      // A stored case is immutable; convening again reads the same case and
      // produces a second run, which is what makes the two comparable.
      await start(run.caseId, run.situation)
      navigate('/courtroom')
    } finally {
      setConvening(false)
    }
  }

  return (
    <>
      <Nav
        status={`Run ${run.id} · ${run.status} · ${succeededCalls(run)} of 7 calls succeeded`}
      />

      <Result run={run} />
      <JudgePanel run={run} />

      <footer className="tnum flex items-center gap-[26px] border-t border-divider px-[44px] py-5">
        <span className="text-muted text-meta-sm">7 calls · 4 statements, 3 judgments</span>
        <span className="text-muted text-meta-sm">
          wall clock {formatSeconds(wallClockMs(run))}
        </span>
        <span className="text-muted text-meta-sm">{formatCount(wordsArgued)} words argued</span>
        <span className="text-muted text-meta-sm">cost {formatCost(totalCost(run))}</span>
        <span className="ml-auto flex gap-[10px]">
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/courtroom')}>
            Read the transcript
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={convening}
            onClick={() => void convokeAgain()}
          >
            {convening ? 'Convening…' : 'Convene again on this case'}
          </button>
        </span>
      </footer>
    </>
  )
}
