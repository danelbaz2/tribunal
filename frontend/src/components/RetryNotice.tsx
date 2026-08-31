import { RotateCw } from 'lucide-react'
import type { LlmCall } from '../types'

// Shown on a card whose call is in flight for a second (or third) time. The
// backend fires an event when it retries — a transport failure, a rate-limit
// pause, or a judge asked again for the required form — and holds it in memory
// only for as long as that attempt is running. It never means the run failed:
// that is the failed state, with its own colour and its own banner.

export function RetryNotice({ call }: { call: LlmCall }) {
  const retry = call.retrying
  if (!retry) return null

  return (
    <div
      className="tb-enter flex items-start gap-[8px] border-l-2 border-accent bg-accent-100 px-[10px] py-[8px]"
      role="status"
    >
      <RotateCw
        size={13}
        strokeWidth={2}
        className="mt-[2px] shrink-0 text-accent-700"
        aria-hidden
      />
      <div className="flex flex-col gap-[2px]">
        <span className="text-meta-sm font-medium text-accent-800">
          The first attempt didn’t land — trying again ({retry.attempt}/{retry.max})
        </span>
        <span className="text-accent-700 text-[11px] leading-[1.4]">{retry.reason}</span>
      </div>
    </div>
  )
}
