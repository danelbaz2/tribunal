import { formatCount } from '../lib/derive'

// "The charge file" — the textarea and the live word-count readout.
// Presentational: the state and the validation live in `NewTrial`, which is
// where the submit is.

export interface ChargeUploadProps {
  text: string
  onTextChange: (text: string) => void
  /** Live word count for the current input. */
  wordCount: number
}

export function ChargeUpload({ text, onTextChange, wordCount }: ChargeUploadProps) {
  return (
    <section>
      <div className="mb-[18px] flex items-baseline justify-between gap-[24px]">
        <h3 className="m-0 text-h3">The charge file</h3>
      </div>

      <div className="field mb-[12px]">
        <label htmlFor="charge-body">The accusation, in full</label>
        <textarea
          className="input min-h-[168px] text-input"
          id="charge-body"
          rows={7}
          value={text}
          onChange={(event) => onTextChange(event.target.value)}
        />
      </div>

      <div className="mb-[22px] flex items-center gap-[14px]">
        <span className="tag tag-neutral tnum">{formatCount(wordCount)} words</span>
        <span className="text-muted text-meta-sm">
          A charge that accuses nobody of anything is refused now, not at the verdict.
        </span>
      </div>
    </section>
  )
}
