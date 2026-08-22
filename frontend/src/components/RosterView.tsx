import type { Situation } from '../types'

// "The bench" — the second and last input the page takes.
//
// Selection is an inset hairline, never a fill. That is not decoration: the
// design system applies colour as stroke throughout, and a filled card here
// would be the one place it did not.

const BENCH: { value: Situation; title: string; body: string }[] = [
  {
    value: 'identical',
    title: 'One model, seven times',
    body: 'A single model drawn from the pool sits in all seven chairs, as seven independent calls sharing no state.',
  },
  {
    value: 'different',
    title: 'Seven different models',
    body: 'Seven distinct models from the pool, one per slot, in the order the pool names them.',
  },
]

export function RosterView({
  situation,
  onChange,
  disabled,
}: {
  situation: Situation
  onChange: (situation: Situation) => void
  disabled?: boolean
}) {
  return (
    <section>
      <h3 className="mb-[6px] mt-0 text-h3">The bench</h3>
      <p className="text-muted mb-[18px] mt-0 max-w-[62ch] text-body-sm">
        Seven slots, filled either by one model seven times over or by seven distinct models.
        Everything else — the charge, the instructions, the order of the stages — is identical
        between the two.
      </p>

      <div className="mb-[28px] grid grid-cols-2 gap-[18px]">
        {BENCH.map((option) => (
          <label
            key={option.value}
            className="card cursor-pointer gap-[8px]"
            style={
              situation === option.value
                ? { boxShadow: 'inset 0 0 0 1px var(--color-accent)' }
                : undefined
            }
          >
            <div className="flex items-center gap-[10px]">
              <span className="radio">
                <input
                  type="radio"
                  name="bench"
                  checked={situation === option.value}
                  disabled={disabled}
                  onChange={() => onChange(option.value)}
                />
                <span className="dot" />
              </span>
              <span className="card-title text-card-title-sm">{option.title}</span>
            </div>
            <p className="card-body m-0 text-body-sm">{option.body}</p>
          </label>
        ))}
      </div>
    </section>
  )
}
