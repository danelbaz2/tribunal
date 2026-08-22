import type { Charge, LlmCall, Run, Situation } from './types'
import {
  REFERENCE_RUN,
  fixtureExtract,
  fixtureRun,
  fixtureStream,
} from './fixtures/referenceRun'

// Calls the backend. The paths below are the contract the FastAPI app in
// `backend/app/api/` has to meet; the frontend holds no other knowledge of it.
//
// `VITE_USE_FIXTURES=true` swaps every call for the committed reference run, so
// the three screens can be worked on with no network and no API key. It is a
// development switch, never a fallback: when it is off and the backend is not
// answering, the UI reports the failure rather than showing invented rows.

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === 'true'

/**
 * The backend row says `writing` for a call in flight; the interface says
 * `live`. Normalised here, once, so nothing downstream has to know both words.
 */
function normalise(run: Run): Run {
  return {
    ...run,
    calls: run.calls.map((call) =>
      (call.status as string) === 'writing' ? { ...call, status: 'live' as const } : call,
    ) as LlmCall[],
  }
}


export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError('The backend did not answer. Is it running on port 8000?')
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new ApiError(detail || `${response.status} ${response.statusText}`, response.status)
  }
  return (await response.json()) as T
}

export interface ExtractedCharge {
  caseId: number
  title: string
  wordCount: number
  pages?: number
  hasTextLayer: boolean
}

/**
 * Stores the pasted charge text and returns what extraction found. A charge
 * that accuses nobody of anything is rejected here — loudly, at upload, not
 * at the verdict.
 */
export async function submitCharge(charge: Charge): Promise<ExtractedCharge> {
  if (USE_FIXTURES) return fixtureExtract(charge)

  return request<ExtractedCharge>('/api/cases', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: charge.text }),
  })
}

/** Starts the run. There is no human in the loop after this call returns. */
export async function convene(caseId: number, situation: Situation): Promise<Run> {
  if (USE_FIXTURES) return fixtureRun(situation)

  return normalise(
    await request<Run>('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: caseId, situation }),
    }),
  )
}

/** Refetched on reconnect — the stream is an optimisation, not the record. */
export async function fetchRun(runId: number): Promise<Run> {
  if (USE_FIXTURES) return Promise.resolve(REFERENCE_RUN)
  return normalise(await request<Run>(`/api/runs/${runId}`))
}

/**
 * Subscribes to the run's event stream. Each event carries the whole run, so a
 * dropped message cannot leave the UI holding a half-applied delta.
 *
 * Returns an unsubscribe function.
 */
export function subscribeToRun(
  runId: number,
  onRun: (run: Run) => void,
  onError: (error: Error) => void,
): () => void {
  if (USE_FIXTURES) return fixtureStream(onRun)

  const source = new EventSource(`/api/runs/${runId}/events`)

  source.onmessage = (event) => {
    try {
      onRun(normalise(JSON.parse(event.data) as Run))
    } catch {
      onError(new ApiError('The run stream sent something that is not a run.'))
    }
  }
  source.onerror = () => {
    // The stream closes on its own when the run reaches a terminal status.
    // Anything else is a dropped connection, and the caller refetches.
    source.close()
    onError(new ApiError('The run stream closed.'))
  }

  return () => source.close()
}
