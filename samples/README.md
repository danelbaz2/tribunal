# samples — charge files for trying the tribunal

Not fixtures. `backend/fixtures/reference_case.md` is the control case and is
replayed by the test suite; nothing in this folder is. These are documents to
paste or drop into screen 1 when you want to watch a real run.

| File | Shape of the case |
| --- | --- |
| `published-memo.md` | A journalist publishes a document obtained in breach of a confidentiality undertaking. Deliberate over weeks, not a moment; two goods in conflict, and an outcome that partly vindicates and partly undercuts each side. |

`published-memo.md` doubles as the unrelated second charge file criterion 14
asks for: run the whole system on it with **zero code changes** and confirm it
produces a finished run. It is deliberately unlike the reference case — no
emergency, no procedure overridden under time pressure — so a system that only
works on override-shaped cases will show it.
