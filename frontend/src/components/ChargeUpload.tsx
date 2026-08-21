import { useRef, useState, type DragEvent } from 'react'
import { FileText } from 'lucide-react'
import type { ExtractedCharge } from '../api'
import { formatCount } from '../lib/derive'

// "The charge file" — the segmented control, the textarea, the live extraction
// readout, and the drop target. Presentational: the state and the validation
// live in `NewTrial`, which is where the submit is.
//
// The dropzone and the attached-file card are two states of one control. The
// mockup shows them side by side for review; here the dropzone renders when
// nothing is attached and the card when something is.

export type ChargeMode = 'text' | 'file'

export interface ChargeUploadProps {
  mode: ChargeMode
  onModeChange: (mode: ChargeMode) => void
  text: string
  onTextChange: (text: string) => void
  file: File | null
  /** What extraction found in the attached file. Null until it has answered. */
  extracted: ExtractedCharge | null
  onFileSelected: (file: File) => void
  onFileCleared: () => void
  /** Live word count for the current input mode. */
  wordCount: number
  extracting: boolean
  /** An upload the backend refused — no text layer, nothing accused. */
  error: string | null
}

const ACCEPTED = '.pdf,.txt,.md'

export function ChargeUpload({
  mode,
  onModeChange,
  text,
  onTextChange,
  file,
  extracted,
  onFileSelected,
  onFileCleared,
  wordCount,
  extracting,
  error,
}: ChargeUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files[0]
    if (dropped) onFileSelected(dropped)
  }

  return (
    <section>
      <div className="mb-[20px] flex items-baseline justify-between gap-[24px]">
        <h3 className="m-0 text-h3">The charge file</h3>
        <div className="seg">
          <label className="seg-opt">
            <input
              type="radio"
              name="charge-source"
              checked={mode === 'text'}
              onChange={() => onModeChange('text')}
            />
            Paste the text
          </label>
          <label className="seg-opt">
            <input
              type="radio"
              name="charge-source"
              checked={mode === 'file'}
              onChange={() => onModeChange('file')}
            />
            Upload a document
          </label>
        </div>
      </div>

      {mode === 'text' && (
        <div className="field mb-[10px]">
          <label htmlFor="charge-body">The accusation, in full</label>
          <textarea
            className="input min-h-[172px] text-input"
            id="charge-body"
            rows={7}
            value={text}
            onChange={(event) => onTextChange(event.target.value)}
          />
        </div>
      )}

      <div className="mb-[26px] flex items-center gap-[14px]">
        <span className="tag tag-neutral tnum">
          {extracting ? 'extracting…' : `${formatCount(wordCount)} words extracted`}
        </span>
        <span className="text-muted text-meta-sm">
          A file that accuses nobody of anything is rejected here, not at the verdict.
        </span>
      </div>

      {/* The rejection state is not designed yet (handoff, "Not designed yet").
          Until it is, the refusal is stated in the accent's paragraph-safe
          ramp step and nothing else changes. */}
      {error && (
        <p className="fade-in mb-[26px] text-meta text-accent-700" role="alert">
          {error}
        </p>
      )}

      <div className="mb-[30px]">
        {file ? (
          <div className="flex flex-col gap-[10px] rounded-md border border-divider px-[20px] py-[18px]">
            <div className="flex items-baseline justify-between gap-[12px]">
              <span className="font-heading text-[15px]">{file.name}</span>
              <span className="tag tag-outline">attached</span>
            </div>
            <div className="hr m-0" />
            <p className="text-muted tnum m-0 text-meta-sm">
              {extracted
                ? [
                    extracted.pages !== undefined ? `${formatCount(extracted.pages)} pages` : null,
                    `${formatCount(extracted.wordCount)} words extracted`,
                    extracted.hasTextLayer ? 'text layer present' : 'no text layer',
                  ]
                    .filter(Boolean)
                    .join(' · ')
                : 'reading the document…'}
            </p>
            <p className="text-muted m-0 text-meta-sm">
              Once a run exists this case is sealed. A correction is a new case, never an edit.
            </p>
            <button type="button" className="btn btn-ghost self-start" onClick={onFileCleared}>
              Detach
            </button>
          </div>
        ) : (
          <div
            className="flex cursor-pointer flex-col justify-center gap-[8px] rounded-md border border-dashed border-divider px-[24px] py-[22px]"
            style={dragging ? { borderColor: 'var(--color-accent)' } : undefined}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            <p className="m-0 flex items-center gap-[8px] font-heading text-[16px]">
              <FileText size={16} strokeWidth={1.5} aria-hidden />
              Or drop a document here
            </p>
            <p className="text-muted m-0 text-meta">
              PDF, TXT or MD. Scanned pages are checked for extractable text and refused if there
              is none.
            </p>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              className="sr-only"
              onChange={(event) => {
                const chosen = event.target.files?.[0]
                if (chosen) onFileSelected(chosen)
                event.target.value = ''
              }}
            />
          </div>
        )}
      </div>
    </section>
  )
}
