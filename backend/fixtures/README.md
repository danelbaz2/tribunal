# fixtures — the control case

`SPECIFICATION.md` Part 4. One reference charge file, seven real responses
captured against it once, and hand-damaged copies of those responses. From then
on the entire test suite replays these files: **no network, no API key, no
cost, identical every run.**

```
reference_case.md   the committed charge file
responses/          7 real captured responses -- one per slot
broken/              hand-damaged copies, for the failure paths
latency_probe.json   scripts/probe_latency.py output -- speed, not the control case
pool_probe.json      scripts/probe_pool.py output -- which candidates qualify, not the control case
```

## The envelope

Every file in `responses/` and `broken/` has the same shape, so a test can
replay either without knowing which it holds:

```json
{
  "slot":     "judge_1",
  "model":    "provider/model:free",
  "prompt":   "exactly what was sent",
  "response": { "...": "the raw OpenRouter payload, verbatim" },
  "duration_ms": 21600,
  "captured_at": "2026-08-21T09:14:22Z"
}
```

A file may instead carry `"failure"` in place of `"response"`, for a call that
never produced a body at all:

```json
{ "slot": "advocate_for_2", "model": "...", "failure": "timeout" }
```

`prompt` is kept because criteria 9-11 are asserted against **the captured
prompt text**, never against the template it was rendered from.

## Capturing

`responses/` is empty until it is filled once, by a human with a key:

```
cd backend && python scripts/capture_fixtures.py
```

It makes seven real calls against `reference_case.md` and writes the seven
files. **Run it once.** Re-capturing silently changes what every test means --
these files are the control case, so replacing them is a decision, not a
refresh. If a capture must be redone, say so out loud and commit it as its own
change.

Until it has been run, the tests that need real response shapes skip with a
message saying so. Everything else -- the arithmetic, the independence
assertions, the failure paths -- runs offline today against `broken/` and
against the reference case.
