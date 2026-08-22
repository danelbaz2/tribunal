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

// The active run, held only in memory for the life of the tab. One run at a
// time: convening a second replaces the first, and a reload starts over with
// no run at all — nothing is kept across a refresh.
//
// The stream is an optimisation over the record, not the record itself — each
// event carries the whole run, and a dropped connection is repaired by
// refetching, never by patching what the UI happens to be holding.

interface RunStore {
  run: Run | null
  error: string | null
  /** Convenes the tribunal and follows it to its end. No further input is taken. */
  start: (caseId: number, situation: Situation) => Promise<Run>
  /** Drops the run and its stream, back to no run at all — the failed-run
   *  escape hatch. The stored case is untouched; only the client's memory of
   *  having convened is cleared. */
  reset: () => void
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

  useEffect(() => () => unsubscribe.current?.(), [])

  const start = useCallback(
    async (caseId: number, situation: Situation) => {
      const started = await convene(caseId, situation)
      setRun(started)
      setError(null)
      follow(started.id)
      return started
    },
    [follow],
  )

  const reset = useCallback(() => {
    unsubscribe.current?.()
    unsubscribe.current = null
    setRun(null)
    setError(null)
  }, [])

  const value = useMemo<RunStore>(
    () => ({ run, error, start, reset }),
    [run, error, start, reset],
  )
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>
}

export function useRunStore(): RunStore {
  const store = useContext(RunContext)
  if (!store) throw new Error('useRunStore must be used inside a RunProvider')
  return store
}
