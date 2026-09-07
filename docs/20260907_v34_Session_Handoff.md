# docs/20260907_v34_Session_Handoff.md — paste this as the first message of the new chat

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`
(private), branch `jason/refactor`, HEAD = the F1-close commit after `ba63cf3`
(verify with `git --no-pager log --oneline -1`). Windows, root
`C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`, Python 3.13, single
DuckDB store at `data\biointel.duckdb`.

**FIRST ACTIONS for the new chat:** clone/pull, build venv,
`pip install -e ".[dev]"`, prove `PYTHONPATH=src pytest -q tests/unit`
(expect **244 passed**), read `docs/PROJECT_STATUS.md` v1.16 in full, then
this handoff. Do not propose code before reading.

## 1. F1 IS CLOSED. What closed it (all with pasted proof, 2026-09-06/07)

1. `verify-direction` final: 40,617/520/0 of 41,137 (run 20260906T031232).
2. 520 classified: 434 genuine inversions, 86 benign (35 filer-of-record,
   14 issuer-CIK-only, 37 NAME). Root cause: orient()'s `if by_name:`
   trusted off-party name-index hits; _norm suffix-stripping collides
   predecessor/successor names (Allergan Inc -> Allergan plc etc.).
3. r8 (commit 9564753): orient() refuses off-party name hits and off-party
   members; `stakes fix-direction` re-oriented the 434 from cached SGML
   headers (fixed 434, ambiguous 2 self-filings, benign 84, dupes 1);
   table of record **41,136 rows**; residual export exactly 86.
4. `stakes crosscheck` (run 20260906T040611): 12,553 disagreements in
   structural families; 58 real percent conflicts; 5,390-row date family =
   route A stores the filing date where the document states an event date
   (year-end 13G/A hypothesis confirmed 60/60 by blind judging).
5. Judging done by LLM-drafts-human-approves (excerpt dump -> proposed
   verdicts -> operator approval): 97 verdicts recorded; **52 ambiguous
   rows remain queued** (multi-person filings, warrants-vs-common,
   as-converted sums) in `20260906_v1_Remaining_Review.md` — judging them
   later harms nothing. `stakes precision` on the disputed sample:
   7/96 = 0.073 [0.036, 0.143] (run 20260906T200507) — the low number is
   the finding, not a defect.
6. entity_lineage (schema 0.14, manual layer; commits a1c6d54, ba63cf3):
   five predecessor->successor pairs entered on SEC formerNames evidence
   (850693->1578845 Allergan, 1100962->1593034 Endo, 820096->1585364
   Perrigo, 874663->1520262 Alkermes, 930184->885590 Valeant — direction
   per SEC record); Theravance/Innoviva, Biofrontera AG/Inc and the two
   Catalysts REJECTED as false pairs. Pairs live in the DATABASE manual
   layer, not git — `manual export` before any rebuild.
7. `stakes stubs` (run 20260907T044737): 17 approved company stubs added
   (IIDs 1381-1397); 6 individuals rejected (person-holders are an open
   design question). Entry went through pipeline.add_company_stub because
   the `add --stub` CLI token loop is defective (feeds NAME and CIK to
   add_company as tickers) — known defect, not yet fixed.
8. Thirteen fingerprints MATCH after the full settled-loop re-run
   (runs 20260907T051335/51444/51603/51611/51653) — this also closed
   L4-P, the store extension, and the constants-annotation pass.
9. Gate M scope committed (4fc8498): docs/20260906_v1_GATEM_Maintained_
   Accuracy_Scope.md — ingest-time header verification (M1), scheduled
   crosscheck (M2), standing judge queue (M3), LLM judge-assist (M4).
   Operator has approved the DIRECTION; each sub-gate still needs its own
   scope-go-build cycle. Two open decision points at the doc's end.

## 2. Open queue, in order

1. **Gate M sub-gates** (M1 first) — the operator wants these built; probe
   first, own commits, own tests, per the scope doc.
2. **r9 event-date repair** (~5,400 rows) — deferred, rule 4.20 binding:
   read three real specimens before writing any regex; own gate.
3. **52 queued verdicts** — operator judges whenever; excluded rows are
   fine indefinitely.
4. **F2 (stated priorities)** — scoped, probe unrun; needs network and a
   quiet SEC window.
5. **fetch-probe 5 200** then `config.FETCH_POOL_ENABLED = True` — still
   pending, must not run alongside any other SEC job.
6. **Known gaps recorded, not built:** relation types beyond merged_into
   (spin-off, subsidiary — Aventis/Sanofi is the live example); the
   `add --stub` CLI defect; individual 13D holders as entities; GUI build
   order unchanged (projects -> boards -> Judge queues -> jobs).

## 3. Standing operating rules (unchanged, binding)

One block per turn with `# expected:` per command (exact values, not
approximations), then stop and wait. **Container diligence before every
deliverable: execute the exact block/script against a replica of its exact
inputs — including replica STATE persisted in one process — before handing
it over.** Deployment messages: what -> precondition -> download -> block ->
then. Every block asserts landed files. Timestamps everywhere. No raw SQL
outside store/results/schema/migrate. No numeric constant without a source.
Unique dated download filenames. `git --no-pager`; push stderr suppressed.
No commits without pasted proof. Every message handing the operator a task
OPENS with one plain sentence stating exactly what to do. Plain-English
explanations on first use of any technical concept. LLM analysis is
proposer-only: deterministic rules extract, humans hold the verdict of
record, provenance recorded.

**Goal unchanged:** best model, however long it takes, en route to a
publishable paper and a working product. Harrison remains blocked pending
merge/key-rotation/repo-visibility (untouched again this session).
