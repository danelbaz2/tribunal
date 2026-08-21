import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Nav } from '../components/Nav'
import { ChargeUpload, type ChargeMode } from '../components/ChargeUpload'
import { submitCharge, type ExtractedCharge } from '../api'
import { countWords } from '../lib/derive'
import { useRunStore } from '../lib/runStore'
import type { Charge, Situation } from '../types'

// Screen 1 — the charge file goes in and the bench is chosen. These are the
// only two user inputs in the whole flow: after "Convene the tribunal" the run
// goes stage 1 → stage 2 → result on its own.

/**
 * The client-side floor for "too short". It is a pre-check, not the ruling —
 * whether a document accuses anybody of anything is decided by the backend at
 * upload, and its refusal is what gets shown.
 */
const MIN_CHARGE_WORDS = 25

const BENCH: { value: Situation; title: string; body: string }[] = [
  {
    value: 'identical',
    title: 'One model, seven times',
    body: 'A single model drawn from the free pool sits in all seven chairs, as seven independent calls sharing no state.',
  },
  {
    value: 'different',
    title: 'Seven different models',
    body: 'Seven distinct models drawn without replacement, one per slot. The draw and its seed are recorded with the run.',
  },
]

export function NewTrial() {
  const navigate = useNavigate()
  const { start } = useRunStore()

  const [mode, setMode] = useState<ChargeMode>('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [extracted, setExtracted] = useState<ExtractedCharge | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [chargeError, setChargeError] = useState<string | null>(null)

  const [situation, setSituation] = useState<Situation>('identical')
  const [convening, setConvening] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // The word count is the live readout of extraction, in both input modes.
  const wordCount = useMemo(
    () => (mode === 'file' ? (extracted?.wordCount ?? 0) : countWords(text)),
    [mode, text, extracted],
  )

  const charge: Charge = useMemo(
    () => ({
      source: mode,
      text,
      filename: file?.name,
      pages: extracted?.pages,
      wordCount,
      hasTextLayer: mode === 'file' ? (extracted?.hasTextLayer ?? false) : true,
    }),
    [mode, text, file, extracted, wordCount],
  )

  const valid =
    mode === 'file'
      ? extracted !== null && extracted.hasTextLayer && extracted.wordCount >= MIN_CHARGE_WORDS
      : wordCount >= MIN_CHARGE_WORDS

  async function handleFileSelected(chosen: File) {
    setFile(chosen)
    setExtracted(null)
    setChargeError(null)
    setExtracting(true)
    try {
      // Extraction happens at upload so a scanned PDF is refused here rather
      // than sending the tribunal to deliberate on nonsense.
      const result = await submitCharge({ ...charge, source: 'file' }, chosen)
      if (!result.hasTextLayer || result.wordCount === 0) {
        setChargeError(
          'No extractable text in that document. A scanned page is not a charge file; supply one with a text layer.',
        )
        setExtracted(result)
        return
      }
      setExtracted(result)
    } catch (cause) {
      setChargeError((cause as Error).message)
    } finally {
      setExtracting(false)
    }
  }

  function handleFileCleared() {
    setFile(null)
    setExtracted(null)
    setChargeError(null)
  }

  async function handleConvene() {
    setSubmitError(null)

    if (mode === 'text' && countWords(text) === 0) {
      setSubmitError('The charge file is empty. There is nothing here to try.')
      return
    }
    if (!valid) {
      setSubmitError(
        `A charge of ${wordCount} words is too short to argue. Supply at least ${MIN_CHARGE_WORDS}.`,
      )
      return
    }

    setConvening(true)
    try {
      const caseId = extracted?.caseId ?? (await submitCharge(charge)).caseId
      await start(caseId, situation)
      navigate('/courtroom')
    } catch (cause) {
      setSubmitError((cause as Error).message)
    } finally {
      setConvening(false)
    }
  }

  return (
    <>
      <Nav status="7 slots · 4 advocates · 3 judges" />

      <div className="mx-auto max-w-[920px] px-[68px] pb-[56px] pt-[44px]">
        <p className="mb-[14px] mt-0 font-heading text-kicker uppercase tracking-kicker-wider text-accent">
          Instrument of deliberation
        </p>
        <h1 className="mb-[18px] mt-0 max-w-[15ch] text-display font-normal">
          A trial held entirely by machines.
        </h1>
        <p className="prose-justified mb-[8px] mt-0 max-w-[62ch] text-lede">
          One charge file is read by four advocates who never see one another — two arguing the act
          was <em>not justified</em>, two arguing it <em>was</em>. Their four statements are then
          read by three judges who never see one another either. Each judge commits to a binary
          verdict, states a confidence, and gives at least two reasons. Seven independent calls;
          nothing inferred from prose.
        </p>
        <p className="prose-justified m-0 max-w-[62ch] text-lede">
          Nothing about this particular case lives in the system. Replace the charge file and the
          tribunal sits again, unchanged.
        </p>

        <div className="hr mb-[30px] mt-[36px]" />

        <ChargeUpload
          mode={mode}
          onModeChange={setMode}
          text={text}
          onTextChange={setText}
          file={file}
          extracted={extracted}
          onFileSelected={handleFileSelected}
          onFileCleared={handleFileCleared}
          wordCount={wordCount}
          extracting={extracting}
          error={chargeError}
        />

        <div className="hr mb-[26px] mt-0" />

        <h3 className="mb-[6px] mt-0 text-h3">The bench</h3>
        <p className="text-muted mb-[18px] mt-0 max-w-[60ch] text-body-sm">
          Seven slots are filled either by one model seven times over, or by seven distinct models.
          Everything else — the charge, the instructions, the order of the stages — is identical
          between the two.
        </p>
        <div className="mb-[30px] grid grid-cols-2 gap-[18px]">
          {BENCH.map((option) => (
            <label
              key={option.value}
              className="card cursor-pointer gap-[8px]"
              // Selection is an inset hairline, never a fill.
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
                    name="situation"
                    checked={situation === option.value}
                    onChange={() => setSituation(option.value)}
                  />
                  <span className="dot" />
                </span>
                <span className="card-title text-card-title-sm">{option.title}</span>
              </div>
              <p className="card-body m-0 text-body-sm">{option.body}</p>
            </label>
          ))}
        </div>

        <div className="hr mb-[22px] mt-0" />

        {submitError && (
          <p className="fade-in mb-[14px] text-meta text-accent-700" role="alert">
            {submitError}
          </p>
        )}

        <div className="flex items-center gap-4">
          <button
            type="button"
            className="btn btn-primary px-[22px] py-[11px] text-[15px]"
            disabled={!valid || convening || extracting}
            onClick={() => void handleConvene()}
          >
            {convening ? 'Convening…' : 'Convene the tribunal'}
          </button>
          <span className="text-muted max-w-[52ch] text-meta">
            Once convened the trial runs to its end without you: four statements, then three
            judgments, then the count. All seven calls must succeed or the run is marked failed.
          </span>
        </div>
      </div>
    </>
  )
}
