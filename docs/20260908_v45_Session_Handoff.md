# docs/20260908_v45_Session_Handoff.md — paste this as the first message of the new chat

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`
(private), branch `jason/refactor`, HEAD = `b891281` or a later commit the
operator names (verify with `git --no-pager log --oneline -1`). Windows, root
`C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`, Python 3.13, single
DuckDB store at `data\biointel.duckdb`.

**FIRST ACTIONS for the new chat, in this exact order:**
1. Clone/pull; `git --no-pager log --oneline -1` must show `b891281` or a
   later commit the operator names. If the container has no credentials,
   say so and work from this handoff plus operator-staged files (the
   2026-09-07 session ran entirely from an eight-file staged mirror; ask
   for the same set plus this session's four changed files).
2. Build venv, `pip install -e ".[dev]"` (container Pythons below 3.13
   need `--ignore-requires-python`; the suite passes on 3.12).
3. Prove `PYTHONPATH=src pytest -q tests/unit` -> expect **262 passed**,
   and `ruff check src tests` -> exactly 3 pre-existing findings
   (improve.py E731, score.py F841, study.py F841), nothing new. Without
   a tree, state both as unverifiable-in-container and rely on the
   operator's machine-pasted proof.
4. Read in full: `docs/PROJECT_STATUS.md` v1.24, this handoff,
   `docs/20260906_v1_GATEM_Maintained_Accuracy_Scope.md`,
   `docs/20260903_v6_Design_Principles.md` (P1-P21),
   `docs/20260903_v1_Stakes_Parser_Development_Record.md` §7-§10.
5. Report the self-check with exact numbers BEFORE any design or code.

**THE FIRST TASK: the operator judges the F2 blind samples.** Stages
3-5 are committed and the table of record holds 4,644 rows at frozen
rules L3-a3-p1 (collector: 6,945 10-Ks + 513 investor-day docs, 0
failures; coverage 3,500/6,500 docs after two miss-loop rounds; writer:
longest-per-key, 2,221 overflow rows preserved). `priorities sample
[N] [--tier T]` prints the seeded worksheet with doc URLs;
`priorities judge KEY correct|wrong|unsure [--note T]` records
(wrong retires the row immediately - the Q5 verdict gating,
implemented as the F1 judge-then-retire precedent); `priorities
precision` seals per-tier Wilson numbers. ~60 per live tier;
earnings_call is a recorded coverage hole (three dead query
hypotheses). After precision: the deal-aspects half (analyser L3-a3
bump + a3 agenda, ~129 resolvable deals, assets.category enum joins
after live-value mapping) closes gate F2 and unblocks aspect-match v2.

DELIVERY RULES LEARNED THE HARD WAY TODAY (binding): run `git
ls-files` on every path before delivering it as a new file — a
tracked file delivered as new destroyed three committed tests
(restored same day from 058d729); never ship a CHECK constraint
against a table with live rows — defer to a mapping stage; evidence
redirects use absolute paths only.

## 1d. M4 IS CLOSED — GATE M COMPLETE (2026-09-07, commit b891281)

1. Operator rulings: model CONFIGURABLE (default claude-sonnet-5), cap
   200/run, ASSIST_ENABLED committed False (explicit switch). assist.py
   is a PROPOSER only: bounded field-aware excerpts, versioned prompt
   (src/biointel/prompts/judge_assist_v1.txt, package-relative — stated
   deviation from the GATEM root path), structured verdicts with
   mandatory abstain for two-values-in-one-box, proposals in
   review_proposals (SCHEMA 0.17) with model/prompt/excerpt provenance,
   shown beside the queue worksheet, never auto-applied; precision
   counts human verdicts only; API failure degrades to no proposal;
   key from environment only.
2. Acceptance of record vs r9 two-route ground truth: claude-sonnet-5
   99/99 = 1.000 (1 unusable); claude-haiku-4-5 100/100 = 1.000. The
   ledger carries the measured license to run Haiku at a third of the
   cost. Whole-queue proposing costs ~$3-4 on Haiku.
3. GATE M FAMILY COMPLETE: M1 + M2 + M3 (+amendment) + r9 + M4 all
   closed 2026-09-07 with pasted proof; excluded rows ~13.6% -> ~1.9%.

## 1c. r9 IS CLOSED (2026-09-07, commit c489eb2, pasted proof)

1. RULE_VERSION F1-r9. Five specimens dumped before any rule (rule
   4.20, run 20260907T151724): four dash-run-before-label documents,
   one label-first with a closing paren before the date. Two rules:
   event-date search on rule-run-flattened text; _EVENT_AFTER
   tolerates the paren. Windows locked verbatim as tests.
2. `stakes r9-repair` (no network; row-driven; repair only where r9
   extraction == route B): 5,533 disputed as_of rows -> 4,879 repaired
   (88.2%), routes_disagree 2, no_extraction 471, key_collision 181,
   entries_closed 4,856. No candidate_reviews rows (fix-direction
   precedent). Crosscheck after: date family 5,533 -> 654, pct 57,
   agree 30,682/38,349. Queue open 5,563 -> 707; second rebuild 0/0.
   Excluded share ~13.6% -> ~1.9%. Precision ledger restarts at F1-r9
   (per-rule-version scoping, standing design).

## 1b. M3 IS CLOSED (2026-09-07, commits abd4e62 + 099ccc8, pasted proof)

1. Operator ruling of record: NO EXPIRY — nothing is ever discarded;
   unsure rows stay excluded and re-judgeable forever; queue rows flip
   open -> judged and are never deleted; verdicts append-only.
2. review_queue (SCHEMA_VERSION 0.16), queue_id deterministic on
   source|doc_id|field. `stakes queue [--since D] [--until D]` builds
   idempotently from M1 disputed rows + M2 conflicts (re-derived from
   cached captures, P16) and prints the worksheet; `stakes run` queues
   its own fresh disputes (queued_new metric). `stakes judge-queue QID
   correct|wrong|unsure [--note T]`: correct clears disputed; wrong
   corrects (direction via cached header + _fix_decision, refused
   unless it rules a single correction; percent/as_of from route-B;
   key columns via wholesale rewrite); unsure stays excluded.
   `stakes precision` gains M-era counts. Late-verdict == same-day
   proven as a unit test (the GATEM criterion).
3. Live build: 5,563 entries (all m2_crosscheck; the 86 benign
   residuals were classified 2026-09-06 and deliberately unmarked),
   rebuild 0/0. The 27 id-collision sibling rows found in the live
   build are closed by 099ccc8 (_mark_disputes outside the dedup;
   live proof disputes_marked 27 then 0). Defects caught in diligence:
   clock-second review_id collision (now per-entry sequence);
   queue-before-first-run crash (disputed column added at queue
   start). ~5,590 rows excluded until judged or r9 — coverage, never
   accuracy; no fingerprinted model reads equity_stakes.

## 1a. M2 IS CLOSED (2026-09-07, commit 6644e4a, all with pasted proof)

1. Queue rule of record: value-vs-value conflicts only; route-B silence
   is a coverage gap, counted and never exported. Full export under the
   new rule (run 20260907T134138): agree 25,886 / checked 38,349 of
   41,046 rows; pct conflicts 57, date conflicts 5,533; silences 3,893
   pct / 6,122 date. The 2026-09-06 export is superseded. 41,046 =
   41,136 minus the 90 judged-wrong rows precision retired.
2. `stakes crosscheck [N] [--since D] [--until D]`: filing_date window,
   window-named export, lines carry `filed YYYY-MM-DD`. Exit criterion
   proven live: February 2015 window (48 lines) equals the full run
   restricted to the month, exactly (run 20260907T134141).
3. `stakes run` ends every pass by crosschecking exactly its fresh rows
   (shared _crosscheck_rows / _active_doc_caps), xc_* metrics in the
   run record, run-stamped export. Tests 248 -> 251; ruff 3; no schema
   change. Known interaction: date-family conflicts keep accruing until
   r9; accumulation costs coverage, never accuracy.

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

1. **52 deferred F-era verdicts + the 707 open M3 entries** (654 date + 57 percent conflicts) — operator judges whenever; excluded rows are
   fine indefinitely.
2. **F2 (stated priorities)** — scoped, probe unrun; needs network and a
   quiet SEC window.
3. **Known gaps recorded, not built:** relation types beyond merged_into
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
