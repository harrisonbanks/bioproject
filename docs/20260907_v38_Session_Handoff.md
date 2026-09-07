# docs/20260907_v38_Session_Handoff.md — paste this as the first message of the new chat

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`
(private), branch `jason/refactor`, HEAD = `1e4418b` or a later commit the
operator names (verify with `git --no-pager log --oneline -1`). Windows, root
`C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`, Python 3.13, single
DuckDB store at `data\biointel.duckdb`.

**FIRST ACTIONS for the new chat, in this exact order:**
1. Clone/pull; `git --no-pager log --oneline -1` must show `1e4418b` or a
   later commit the operator names. If the container has no credentials,
   say so and work from this handoff plus operator-staged files (the
   2026-09-07 session ran entirely from an eight-file staged mirror; ask
   for the same set plus this session's four changed files).
2. Build venv, `pip install -e ".[dev]"` (container Pythons below 3.13
   need `--ignore-requires-python`; the suite passes on 3.12).
3. Prove `PYTHONPATH=src pytest -q tests/unit` -> expect **248 passed**,
   and `ruff check src tests` -> exactly 3 pre-existing findings
   (improve.py E731, score.py F841, study.py F841), nothing new. Without
   a tree, state both as unverifiable-in-container and rely on the
   operator's machine-pasted proof.
4. Read in full: `docs/PROJECT_STATUS.md` v1.17, this handoff,
   `docs/20260906_v1_GATEM_Maintained_Accuracy_Scope.md`,
   `docs/20260903_v6_Design_Principles.md` (P1-P21),
   `docs/20260903_v1_Stakes_Parser_Development_Record.md` §7-§10.
5. Report the self-check with exact numbers BEFORE any design or code.

**THE FIRST TASK IS THE GATE M2 SCOPE MESSAGE.** The GATEM doc's direction
is approved but each sub-gate needs its own scope -> operator "go" -> build.
Do not code before the go.

## 1. M1 IS CLOSED (2026-09-07, commit 1e4418b, all with pasted proof)

1. Probe (no-write, rule 4.20): `stakes check-probe 2015-02-01 2015-02-28`
   ruled 849 would-be rows — match 847 / fix 1 / ambiguous 0 / benign 1 /
   no_header 0; filings_seen 873; efts_errors 0; 38 minutes, SEC-rate-bound
   (evidence 20260907_M1_probe_evidence.txt). The fix specimen is accession
   0000059478-15-000094 (Lilly Ventures Fund I) — the inversion class M1
   exists to catch at row one; the benign is a NAME-holder row.
2. Wiring: `disputed` optional column on equity_stakes
   (EQUITY_STAKE_M1_COLS, SCHEMA_VERSION 0.14 -> 0.15). `stakes run` rules
   every fresh row at write time via the EXISTING parse_header +
   _fix_decision, unchanged. Agreeing rows write as before (disputed
   blank); disagreeing rows write disputed = fix|ambiguous|benign — the
   class rides free for the M3 judge. A row whose header cannot be
   acquired writes clean and is counted (five check_* run metrics; the
   scope marks disagreement, not absence; probe measured no_header 0/849).
   Headers cached-first inside the existing rate budget.
3. Enforcement: under any `store.enforce` (a model's declared inputs),
   rows with disputed set are invisible (store._guard_rows); every
   non-enforced read (CLI, crosscheck, judge tooling) sees every row.
4. Fingerprints untouched BY CONSTRUCTION: the live table gains the
   disputed column only when the next `stakes run` calls add_columns, and
   blank values are always included. CHECK-FIRST ITEM: after the first
   M-era `stakes run`, re-run the settled-loop fingerprint check to prove
   it on-machine rather than by construction.
5. Tests 244 -> 248 (two probe tests: rulings per the 2026-09-06 classes,
   probe plumbing writes nothing; two wiring tests: ingest-path exit
   criteria including self-filing -> ambiguous and Allergan off-party ->
   no row at all, and enforced-read exclusion). Ruff unchanged at 3.
6. Files changed: stakes.py (check_probe, _header_check, run() write-time
   check, CLI token), schema.py (0.15), store.py (_guard_rows filter),
   tests/unit/test_stakes.py. One commit: 1e4418b.

## 2. Open queue, in order

1. **M2 — scheduled second-route crosscheck** (GATEM doc): `stakes
   crosscheck --since <last run>` on every update run, new rows only;
   route-B silence is a coverage gap, not a disagreement; exit: replayed
   month's queue equals the full-run crosscheck restricted to that month,
   exactly. Scope message first.
2. **r9 event-date repair** (~5,400 rows) — rule 4.20 binding: read three
   real specimens before writing any regex; own gate, own commit.
3. **52 queued verdicts** — operator judges whenever; excluded rows are
   fine indefinitely.
4. **F2 (stated priorities)** — scoped, probe unrun; needs network and a
   quiet SEC window.
5. **fetch-probe 5 200** then `config.FETCH_POOL_ENABLED = True` — must
   not run alongside any other SEC job.
6. **M3 (standing judge queue), M4 (LLM judge-assist)** — each its own
   scope-go-build; M1's disputed column already carries the class M3
   consumes. M3 open decision: whether `unsure` ever expires (proposal:
   no). M4 open decisions: model choice and per-run cost cap (proposal:
   current small model, cap 200 calls/run).
7. **Known gaps recorded, not built:** relation types beyond merged_into
   (spin-off, subsidiary — Aventis/Sanofi live example); the `add --stub`
   CLI token-loop defect; individual 13D holders as entities; GUI build
   order unchanged (projects -> boards -> Judge queues -> jobs).

## 3. How we work — delivery mechanics (binding, follow exactly)

1. Per gate: scope message -> operator "go" -> container dry-run/diligence
   on a replica of the EXACT inputs -> deliver -> operator runs -> pasted
   proof -> commit. Never code before go; never commit before proof. When
   the container has no tree, diligence runs against a staged mirror plus
   stub interface modules at the same seams the unit tests monkeypatch,
   and is stated exactly as such (the 2026-09-07 pattern).
2. Files are delivered as download links (present-files), one file each,
   never pasted inline, never zipped, no data files ever. Download names
   are unique and dated: `YYYYMMDD_vN_name.ext` (docs follow
   `YYYYMMDD_ver_nameofdocument`); code keeps its functional name at the
   DEPLOY path. Every delivered file carries its Windows deploy path as
   line 1.
3. The operator downloads to `C:\Users\JB\Downloads\`, then runs ONE
   PowerShell block per turn: `Set-Location` first; every command's output
   to one named evidence file via `*>> $out`; a `# expected:` comment with
   EXACT values after each command (format-only expectations for discovery
   runs); `Test-Path`/`Select-String` asserts that each copied file landed
   BEFORE anything depends on it; timestamps at block start/end; the block
   ends by naming the file(s) to attach. Evidence files arrive UTF-16;
   convert before grepping in a container.
4. Commits are self-gated inside the block: compute `$ok` from exact
   strings in the evidence file, `if ($ok) { git --no-pager add/commit/
   push origin jason/refactor 2>$null } else { "GATE FAILED ... NOT
   committing" }`. Full-file replacements only for files this project owns
   from prior gates; surgical edits otherwise, against the deployed
   version read in full first.
5. Deployment messages follow: what -> precondition -> download -> block
   -> then. Every task-bearing message OPENS with one plain sentence
   saying exactly what to do.
6. Session start and end: prove the environment before designing; end by
   updating PROJECT_STATUS (+1 version), writing the next handoff (+1
   version), committing both, and reminding the operator to
   `manual export` (lineage pairs and verdicts live only in the database).

## 3b. Tone and decision discipline (binding)

1. Settled decisions stay settled. The operator's rulings (and everything
   marked "of record" in the docs) are worked WITHIN, not relitigated. Ask
   once if genuinely ambiguous; never reopen a closed question unless new
   EVIDENCE contradicts it — and then say so in one line and move on.
2. Do not invent problems. Raise an issue only when it changes what the
   operator does or decides; if a concern is speculative, it does not earn
   a mention. One real caveat beats three hypothetical ones.
3. Answer the question asked, then stop. Lead with the action or the
   answer in one plain sentence; detail after; no meta-commentary about
   process, no restating what was already agreed, no unnecessary options.
4. Be responsive but never at the cost of diligence: a short turn that ran
   the replica beats a fast turn that guessed. When the operator is
   frustrated, fix the thing — do not apologize at length or narrate.
5. Plain English on first use of any technical concept, formal written
   English throughout, one question at a time, fully answered before the
   next is posed.

## 3a. Standing operating rules (unchanged, binding)

One block per turn with `# expected:` per command (exact values, not
approximations; format-only for discovery runs), then stop and wait.
**Container diligence before every deliverable: execute the exact
block/script against a replica of its exact inputs — including replica
STATE persisted in one process — before handing it over; where the full
tree is absent, a staged-mirror replica with stub interface seams,
stated exactly.** Deployment messages: what -> precondition -> download ->
block -> then. Every block asserts landed files. Timestamps everywhere. No
raw SQL outside store/results/schema/migrate. No numeric constant without
a source. Unique dated download filenames. `git --no-pager`; push stderr
suppressed. No commits without pasted proof. Every message handing the
operator a task OPENS with one plain sentence stating exactly what to do.
Plain-English explanations on first use of any technical concept. LLM
analysis is proposer-only: deterministic rules extract, humans hold the
verdict of record, provenance recorded.

**Goal unchanged:** best model, however long it takes, en route to a
publishable paper and a working product. Harrison remains blocked pending
merge/key-rotation/repo-visibility (untouched again this session).
