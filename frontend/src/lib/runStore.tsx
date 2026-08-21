import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { convene, fetchRun, subscribeToRun } from '../api'
import type { Run, Situation } from '../types'

// The active run, held for the whole session so the courtroom and the judgment
// read the same rows. One run at a time: convening a second replaces the first.
//
// The stream is an optimisation over the record, not the record itself — each
// event carries the whole run, and a dropped connection is repaired by
// refetching, never by patching what the UI happens to be holding.

const RUN_ID_KEY = 'tribunal.activeRunId'

interface RunStore {
  run: Run | null
  error: string | null
  /** Convenes the tribunal and follows it to its end. No further input is taken. */
  start: (caseId: number, situation: Situation) => Promise<Run>
}

const RunContext = createContext<RunStore | null>(null)

export function RunProvider({ children }: { children: ReactNode }) {
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const unsubscribe = useRef<(() => void) | null>(null)

  const follow = useCallback((runId: number) => {
    unsubscribe.current?.()
    unsubscribe.current = subscribeToRun(
      runId,
      (next) => {
        setRun(next)
        setError(null)
      },
      () => {
        // A closed stream is not itself a failure — refetch and let the run's
        // own status say whether it finished or failed.
        void fetchRun(runId)
          .then(setRun)
          .catch((cause: Error) => setError(cause.message))
      },
    )
  }, [])

  // Reconnect after a reload: the run id is the only thing kept client-side.
  useEffect(() => {
    const stored = sessionStorage.getItem(RUN_ID_KEY)
    if (!stored) return
    const runId = Number(stored)
    void fetchRun(runId)
      .then((existing) => {
        setRun(existing)
        if (existing.status === 'running') follow(runId)
      })
      .catch(() => sessionStorage.removeItem(RUN_ID_KEY))
  }, [follow])

  useEffect(() => () => unsubscribe.current?.(), [])

  const start = useCallback(
    async (caseId: number, situation: Situation) => {
      const started = await convene(caseId, situation)
      sessionStorage.setItem(RUN_ID_KEY, String(started.id))
      setRun(started)
      setError(null)
      follow(started.id)
      return started
    },
    [follow],
  )

  const value = useMemo<RunStore>(() => ({ run, error, start }), [run, error, start])
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>
}

export function useRunStore(): RunStore {
  const store = useContext(RunContext)
  if (!store) throw new Error('useRunStore must be used inside a RunProvider')
  return store
}
