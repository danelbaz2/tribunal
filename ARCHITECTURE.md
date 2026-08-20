# LLM Tribunal — Architecture

---

# Part 1 — The Problem

## What we are building

A software system that simulates a **trial conducted entirely by artificial intelligence**.

The system receives a **charge file** — a document describing an accusation against someone —
and runs a complete judicial deliberation on it:

- **4 advocates** each state their position on the case. Two argue that the accused's actions
  were **not justified**, two argue that they **were justified**. They do not respond to each
  other — each simply says what it thinks.
- **3 judges** then read all four statements and each delivers **their own verdict**, with a
  written justification.
- The system displays the result: for example, **2 judges say justified, 1 says not justified**.

Each of these 7 participants is a separate Large Language Model call. None of them is a human.

## The real question being asked

Building one trial is not the point. The point is a **comparison between two situations**:

| | Who plays the 7 roles |
|---|---|
| **Situation A — Identical models** | All 7 participants run on the *same* model |
| **Situation B — Different models** | Each of the 7 participants runs on a *different* model |

"Different" can mean different companies (Anthropic vs OpenAI vs Google) or the same company
with different models (Claude Opus vs Claude Sonnet).

**The question:** does it change anything? Does a tribunal of diverse models reach a different
verdict, or reason differently, than a tribunal of seven copies of the same mind?

To answer this honestly, the two situations must be **identical in every respect except the
models**: same charge file, same instructions, same tribunal structure, same order of operations.
The only variable allowed to change is which model sits in which chair. This single requirement
drives most of the architectural decisions that follow.

## One important constraint

**The system must work with any charge file.** No name, crime, country, or fact is written into
the code. The charge file is the only source of information about the case. If you replace it
with a completely different accusation tomorrow, the system runs unchanged.

This means the AI instructions (prompts) describe only *roles* — "you are an advocate arguing
the accused's actions were justified" — never the specific case.

---

# Part 2 — How the Tribunal Works

The trial happens in **two stages**, in order. The first stage must fully finish before the
second one begins.

```
   ┌─────────────────────────────────────────────────────────┐
   │  The charge file is uploaded and read                    │
   └─────────────────────────────────────────────────────────┘
                              │
   ┌──────────────────────────▼──────────────────────────────┐
   │  STAGE 1 — STATEMENTS                                    │
   │                                                          │
   │  The 4 advocates each write their argument, at the same  │
   │  time, without seeing each other.                        │
   │                                                          │
   │     Against ×2                    For ×2                 │
   │                                                          │
   │  Each one only says what it thinks. Nobody answers       │
   │  anybody.                                                │
   └──────────────────────────┬──────────────────────────────┘
                              │
              The complete transcript: 4 arguments
                              │
   ┌──────────────────────────▼──────────────────────────────┐
   │  STAGE 2 — JUDGMENT                                      │
   │                                                          │
   │  The 3 judges each read the charge file and all four     │
   │  statements, and rule independently.                     │
   │                                                          │
   │  Judge 1        Judge 2        Judge 3                   │
   └──────────────────────────┬──────────────────────────────┘
                              │
   ┌──────────────────────────▼──────────────────────────────┐
   │  RESULT:  2 justified — 1 not justified                  │
   └─────────────────────────────────────────────────────────┘
```

**Three design points are worth defending explicitly:**

**1. Advocates never see each other.** There is no rebuttal round. The four advocates argue in
parallel, in isolation, and each one is given exactly one thing: the charge file. This keeps the
advocates' output free of any cross-influence — the strongest possible statement of each of the
four positions, uncontaminated by who spoke first or who argued loudest.

It also removes a confound from the experiment. If advocates responded to each other, a
difference between Situation A and Situation B could come from the *interaction* between models
rather than from the models themselves. With no rebuttals, each statement is attributable to
exactly one model reading exactly one document.

**2. Judges never see each other.** This is not enforced by asking them politely in the prompt —
it is enforced by the code. Each judge is given exactly two things: the charge file and the four
statements. There is no path in the program through which one judge's opinion could reach
another. Independence is a structural guarantee, not a request.

**The weighing happens in the judges.** Nobody rebuts, nobody concedes: the judges are the only
place where the four positions meet, and deciding between them is their entire job.

**3. Within a stage, everyone works simultaneously.** The 4 advocates are called in parallel,
then the 3 judges are called in parallel. But the *boundary between the two stages* is strict: no
judge starts until all 4 arguments exist, so every judge reads exactly the same transcript.

**Total: 7 AI calls per trial** (4 statements + 3 judgments).

---

# Part 3 — The Architecture

Three layers, each with one job.

```
┌───────────────────────────────────────────────────────────────┐
│  FRONTEND — React                                             │
│                                                               │
│  Upload the charge file · choose the situation (A or B) ·     │
│  watch the statements appear live · read the verdicts ·       │
│  compare situation A against situation B                      │
└───────────────────────────────────┬───────────────────────────┘
                                    │  HTTP / live event stream
┌───────────────────────────────────▼───────────────────────────┐
│  BACKEND — Python + FastAPI                                   │
│                                                               │
│   ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│   │ Reads the   │  │ ORCHESTRATOR │  │ Compares situation │  │
│   │ charge file │─▶│ runs the 2   │  │ A against B        │  │
│   │ (PDF/TXT/MD)│  │ stages       │  │                    │  │
│   └─────────────┘  └──────┬───────┘  └────────────────────┘  │
└───────────────────────────┼───────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
   ┌────────────────────┐      ┌───────────────────────┐
   │  OPENROUTER        │      │  POSTGRESQL           │
   │                    │      │                       │
   │  One gateway to    │      │  Every trial, every   │
   │  every AI model    │      │  argument, every      │
   │  (Claude, GPT,     │      │  verdict, every cost  │
   │  Gemini, Llama…)   │      │  — permanently stored │
   └────────────────────┘      └───────────────────────┘
```

### Why OpenRouter matters here

OpenRouter is a single API that reaches every AI provider. Without it, supporting seven
different models would mean seven different SDKs, seven authentication schemes, and seven
response formats to handle.

With it, **the choice of model becomes a single line of text**. Switching from Situation A to
Situation B is literally changing a list of seven strings — no code changes at all. That is
precisely what turns "compare identical models vs different models" from a large engineering
task into a configuration change.

### The key idea: the "slot"

Each of the 7 participants has a fixed position, called a **slot**:

```
advocate_against_1    advocate_against_2
advocate_for_1        advocate_for_2
judge_1    judge_2    judge_3
```

**These slots are identical in both situations.** Only the model assigned to each slot changes.

This is what makes the comparison meaningful. Because `judge_2` exists in both runs, you can ask
a precise question: *"Judge 2 said 'justified' when it was Claude. Did Judge 2 still say
'justified' when it became GPT?"* Without stable slots, you could only compare two piles of
results and hope they lined up.

---

# Part 4 — Technology Choices

| Layer | Choice | Why |
|---|---|---|
| **Backend** | Python + FastAPI | Handles many simultaneous AI calls natively (`async`). Python is where AI tooling lives. |
| **AI gateway** | OpenRouter | One API for all providers. Model choice becomes configuration. |
| **Database** | PostgreSQL | See Part 7 — this is the choice that needs justifying. |
| **Frontend** | React + TypeScript | Standard, well-known, good for a live-updating interface. |
| **Styling** | Tailwind CSS | Build the courtroom layout quickly, without writing a design system. |

**Development runs entirely on your machine.** No Docker. The backend and frontend each start
with one command. The database is either a free hosted Postgres (Supabase) or a local install —
either way, one line in a config file.

**Deployment, at the end of the project:** frontend on Vercel, backend on Render, database on
Supabase. Render rather than Vercel for the backend, because a trial takes minutes to run and
Vercel's serverless functions time out before it finishes.

---

# Part 5 — Project Structure

The project is one repository containing two independent applications: the backend and the
frontend. They talk to each other over HTTP and can be started, stopped and deployed separately.

```
tribunal/
│
├── ARCHITECTURE.md          this document
├── README.md                how to install and run
├── .env                     the two secrets: AI key + database address
│
├── backend/                 ─────── the Python application ───────
│   └── app/
│       ├── main.py              starts the server
│       ├── config.py            settings and default model list
│       ├── database.py          connection to PostgreSQL
│       ├── models.py            the 4 tables from Part 6
│       │
│       ├── api/                 what the frontend can ask for
│       │   ├── cases.py             upload a charge file
│       │   ├── runs.py              start a trial, follow it, read it
│       │   └── comparisons.py       compare situation A with B
│       │
│       ├── ai/                  talking to the AI models
│       │   └── openrouter.py        send a request, measure cost and time
│       │
│       ├── tribunal/            ★ the heart of the project
│       │   ├── roles.py             the 7 slots and their definitions
│       │   ├── roster.py            assigns models to slots (A or B)
│       │   ├── advocates.py         stage 1 — the four statements
│       │   ├── judges.py            stage 2 — independent judgment
│       │   ├── orchestrator.py      runs the 2 stages in order
│       │   └── prompts/             the instructions given to the AI
│       │       ├── statement.txt
│       │       └── judge.txt
│       │
│       └── charge_file.py       reads PDF / TXT / MD
│
└── frontend/                ─────── the React application ───────
    └── src/
        ├── api.ts               calls the backend
        ├── pages/
        │   ├── NewTrial.tsx         screen 1 — upload and configure
        │   ├── Courtroom.tsx        screen 2 — the live trial
        │   └── Comparison.tsx       screen 3 — situation A vs B
        └── components/
            ├── ChargeUpload.tsx     drag and drop the file
            ├── RosterView.tsx       the pool, the seed, the 7 drawn models
            ├── StatementsView.tsx   the four statements, against vs for
            ├── JudgePanel.tsx       the 3 verdicts
            └── Result.tsx           "2 justified — 1 not justified"
```

## How to read this structure

Each folder answers one question:

| Folder | Its job |
|---|---|
| `api/` | **What can be asked of the system?** The list of available operations. |
| `ai/` | **How do we talk to the models?** Isolated so that OpenRouter could be replaced without touching anything else. |
| `tribunal/` | **How does a trial actually work?** The rules of the statements and the judgment. |
| `pages/` | **What screens exist?** One file per screen. |
| `components/` | **What visual pieces do the screens reuse?** |

## The two decisions worth explaining

**1. `tribunal/` is separate from everything else.**

This folder contains the trial logic and nothing else — no database code, no web code, no HTTP.
It is the part that is genuinely yours: the definition of the roles, the order of the stages, the
rule that neither advocates nor judges ever see one another.

Keeping it isolated means it can be read and tested on its own. When you have to defend how judge
independence is guaranteed, you point at `judges.py` — a single small file — rather than
searching through code that also handles uploads and web requests.

**2. `prompts/` holds text files, not code.**

The instructions given to the AI are the single biggest factor in the quality of the results, and
they are the thing you will modify most often. Kept as separate text files, they can be adjusted
and compared without touching a line of Python.

It is also where the **case-independence rule** is enforced and can be verified: open these two
files, and confirm that no specific case is ever mentioned. The proof fits on one screen.

---

# Part 6 — The Data Model

Four tables.

```
   ┌──────────────────┐
   │  cases           │   The charge files that were uploaded
   │                  │
   │  title           │
   │  content         │   the text of the accusation
   └────────┬─────────┘
            │  one case can have many trials
            ▼
   ┌──────────────────┐
   │  runs            │   One trial
   │                  │
   │  situation       │   'identical' or 'different'
   │  status          │   running / finished / failed
   │  seed            │   reproduces the model draw
   │  roster          │   which model landed in which slot
   │  total cost      │
   └────────┬─────────┘
            │  one trial has 7 AI calls
            ▼
   ┌──────────────────┐
   │  llm_calls       │   One row per AI call
   │                  │
   │  slot            │   'judge_2'
   │  stage           │   'statement' / 'judgment'
   │  model           │   'anthropic/claude-sonnet-4.5'
   │  answer          │   what it said (verdict, reasoning…)
   │  cost, duration  │
   └──────────────────┘

   ┌──────────────────┐
   │  comparisons     │   Links one 'identical' trial to one
   │                  │   'different' trial of the same case
   └──────────────────┘
```

The important table is **`llm_calls`**. Advocates and judges are stored together in one table
rather than two separate ones, because every question you will ask — *what did each model cost?
how did each slot vote? how long did each provider take?* — is then a single query over a single
table.

---

# Part 7 — Why a Relational Database (and not NoSQL)

This is the choice most worth explaining, because at first glance the opposite seems obvious:
an AI returns JSON, and NoSQL databases store JSON. So why not MongoDB?

## The simple version

**A relational database stores data in tables that are linked to each other.** A NoSQL document
database stores each item as a separate, self-contained document.

Here is the difference in practice.

**In NoSQL,** one trial is one big document containing everything:

```
{ trial: 1, charge: "the full text of the accusation...",
  advocates: [ ... 4 statements ... ],
  judges: [ ... 3 verdicts ... ] }
```

That looks convenient. The problem appears on the second trial: the charge file text is copied
again. And on the tenth trial, it has been copied ten times. If you fix a typo in it, you must
fix it in ten places, and if you miss one, your comparison is now between two slightly different
cases — a silent error that invalidates the result.

**In relational,** the charge file is stored **once**, in the `cases` table. Every trial points
to it. There is exactly one copy, so it cannot drift.

## The four reasons

### 1. The data is naturally made of links

One case → many trials. One trial → 7 AI calls. One comparison → two trials.

These are exactly the relationships a relational database is built for. NoSQL either duplicates
the data (the problem above) or stores an ID and forces you to reconnect everything by hand in
Python code.

### 2. The result of the project is a database query

Remember the actual goal: compare Situation A to Situation B. In SQL, that is one short query:

```sql
SELECT slot, model, verdict
FROM llm_calls
WHERE stage = 'judgment'
ORDER BY slot;
```

The answer to your research question is produced *by the database*, in five lines you can show
on a slide and explain in ten seconds.

Without SQL, you write a Python script that opens files, loops through them, and counts by hand
— and you rewrite that script every time you think of a new question.

### 3. A fixed structure prevents silent mistakes

The usual argument for NoSQL is freedom: you don't have to decide your fields in advance.

But here, you *have* decided them. Every AI call produces the same fields: a slot, a model, a
verdict, a cost, a duration. That structure is fixed by the experiment itself.

And that freedom would actively hurt you. If one trial saves `"justified"` and another saves
`"JUSTIFIED"`, your count is wrong — and **nothing warns you**. NoSQL accepts both happily. A
relational database refuses the second one at the moment you try to write it. The error is
caught immediately instead of quietly corrupting your final results.

When your entire project is a measurement, consistency of the data is not a constraint. It is
the whole point.

### 4. PostgreSQL gives you the NoSQL advantage anyway

There is one part that genuinely is unpredictable: the **raw response** from each AI provider.
Its shape differs per model and will change as you refine your prompts. This is the case where
NoSQL flexibility is real.

PostgreSQL handles it with a column type called **JSONB**, which stores free-form JSON exactly
like MongoDB does — and lets you search inside it.

So the design is:

- **Normal columns** for everything you count, filter, or compare — model, slot, verdict, cost.
- **One JSONB column** for the complete raw response, so nothing is ever lost.

**You get both.** Structure where structure helps, flexibility where flexibility helps. You give
up nothing by choosing PostgreSQL.

## Summary

| | NoSQL (MongoDB) | Relational (PostgreSQL) |
|---|---|---|
| Charge file stored | copied into every trial | once, referenced by all |
| Comparing A vs B | Python script | 5-line SQL query |
| Inconsistent data | accepted silently | rejected immediately |
| Free-form AI responses | supported | supported (JSONB) |
| 4 AI calls writing at once | fine | fine |

**In one sentence:** this project is a measurement, and a relational database is the tool that
keeps a measurement honest.

---

# Part 8 — What the User Sees

**Screen 1 — Start a trial.** Drop in the charge file (PDF, TXT or MD). Choose the situation:
*identical models* (one model drawn from the free pool, placed in all 7 slots) or *different
models* (7 distinct models drawn from the same pool). The draw is shown before you commit, and
its seed is stored. Press start.

**Screen 2 — The courtroom.** The two sides face each other, the two statements against on the
left, the two for on the right. Each statement shows which model wrote it and how long it took.
**Statements appear live as the AI produces them** — the room fills up in front of you.

Then the three judges appear side by side: verdict, confidence, and their written reasoning.

At the top, the headline the project asks for:

> ### 2 justified — 1 not justified

**Screen 3 — The comparison.** Situation A and Situation B, side by side. Did each judge slot
rule the same way in both? Which was faster? How much did each side write? Both draws come from
the free pool, so cost is recorded but is zero on both sides — agreement per slot is the finding.
**This screen is the result of the project.**

---

# Part 9 — Build Order

1. **Foundation** — project skeleton, database connection, frontend talking to backend.
2. **OpenRouter connection** — prove one AI call works, and that we capture its cost and speed.
3. **Database tables** — the four tables above.
4. **Charge file upload** — read PDF/TXT/MD, store the text.
5. **The prompts** — the instructions for advocates and judges. *Most of the quality lives here*;
   test with two unrelated charge files to prove the system is truly case-independent.
6. **The control case** — capture 7 real responses on the reference charge file and **commit them
   as fixtures, plus the hand-damaged copies, before the orchestrator exists** (`SPECIFICATION.md`
   Part 4). Everything after this step is built against a test that already exists.
7. **The advocates** — stage 1, four statements running in parallel.
8. **The judges** — stage 2, running in parallel and independently.
9. **The orchestrator** — the full trial from start to finish.
10. **The interface** — upload, live courtroom, verdicts.
11. **The comparison screen** — the final result.
12. **Deployment** — Vercel, Render, Supabase.

## How we know it works

- Run the same case twice, in both situations, and confirm both complete and display verdicts.
- Verify by test that **what is sent to each judge contains no other judge's opinion**, and that
  **what is sent to each advocate contains no other advocate's statement** — a direct check of
  the project's core requirement.
- Run the whole system on a completely unrelated charge file, with **zero code changes**, to
  prove case-independence.
- Simulate failures: **all 7 calls must succeed for a run to count.** Any call is retried once;
  a second failure marks the whole run failed and excludes it from comparisons. A run of 3
  statements is not comparable to a run of 4, and a verdict from two judges is not the
  deliverable. See `SPECIFICATION.md` Part 2 and Part 5.
