// Three dots, staggered. The only motion on the page besides the chevron —
// nothing slides, nothing bounces, and a verdict is never animated from one
// value to another.

export function PulseDots({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-[6px] py-[6px]">
      <span className="tb-dot" />
      <span className="tb-dot" />
      <span className="tb-dot" />
      <span className="text-muted ml-[6px] text-meta-sm">{label}</span>
    </div>
  )
}
