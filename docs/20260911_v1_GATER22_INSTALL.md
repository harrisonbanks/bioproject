# docs/20260911_v1_GATER22_INSTALL.md

# Gate R2-2 install runbook: trial, r2 verdicts, head-to-head compare

Scope of record: operator "go" 2026-09-11 on the R2-2 scope with the
reviewer's blocking amendment (r2 verdicts never touch stated_priorities)
and the merge-write resolution. Install only: this gate makes NO API call.
The paid trial is a separate block after this gate's exit criteria pass and
after the section-5 ask. Expected HEAD before install: 3884f76.

## 1. Package installs
None.

## 2. New files (download name -> deploy path)
1. 20260911_v1_GATER22_INSTALL.md -> docs\20260911_v1_GATER22_INSTALL.md

## 3. Replaced files (full-file replacements of the 3884f76 versions; the
## block refuses if the deployed hash is not the 3884f76 hash)
1. 20260911_v3_priorities.py -> src\biointel\priorities.py
   Changed: judge_batch gains r2=False (r2 mode routes to r2_judge; default
   worksheet path priorities_r2_worksheet.csv; no retire accounting); the
   judge-batch cli branch passes r2=("--r2" in argv).
   Added before `def cli`: R2_TRIAL_DOCS (120), R2_WORKSHEET_N (60),
   R2_ANCHOR_HAIKU (1.51), R2_ANCHOR_SONNET (5.24), R2_P2_BASELINE (12, 13),
   _r2_key, _r2_norm, _r2_docs, _r2_unit, _r2_write_doc, r2_trial,
   r2_judge, _latest_verdicts, _r2_verdict, r2_compare; cli branches
   r2-trial [N] [--seed S], r2-compare [N] [--seed S], r2-judge KEY VERDICT
   [--note T]. extract_priorities, judge, write, RULE_VERSION_F2 unchanged.
2. 20260911_v3_test_priorities.py -> tests\unit\test_priorities.py
   Appends 10 tests (56 -> 66 in the file); collect-only 315 -> 325.

## 4. Surgical edits
None. Every touched file ships whole.

## 5. Migration
None. stated_priorities_r2 is created on the trial's first write.

## 6. Design decisions folded in
1. Verdict path (reviewer blocking amendment): r2_judge appends to
   candidate_reviews only, candidate_id = R-key = "R" + sha256(entity|date|
   category|statement)[:16], rule_version L3-a3-p2, reviewer operator, note
   prefixed "r2:"; it never reads-for-mutation or writes either priorities
   table. A test asserts both tables are identical before and after.
2. Trial unit (merge-write resolution): survivors are merge-written per
   (entity_key, stated_at, doc_id) under R2-v1; rows of other units and
   other extractor versions are kept; re-running a document is idempotent
   and interruption is safe.
3. Population: _r2_docs applies exactly the `write` predicate for
   10k_strategy (captured-by-priorities-probe reference, cik and file_date
   parsed, active capture, readable text, item1_slice accepts). No further
   filter. The sample is a seeded shuffle of that population.
4. Pairing in compare: exact (entity, date, category, normalized sentence)
   first, then containment within the same (entity, date, category) because
   p2 statements can carry _capture_sentence lookback text ahead of the
   sentence while R2 spans are bare sentences; each row pairs at most once;
   the line prints exact and contained counts separately.
5. Acceptance (_r2_verdict): NO-VERDICTS until an operator verdict on an
   R-key exists; FAIL if the R2-only Wilson lower bound is below p2's exact
   lower bound (12/13) or any p2-only row not judged wrong at p2 exists;
   PASS if the point estimate reaches p2's (12/13); else OPERATOR-JUDGMENT.
   Unsure verdicts are counted and excluded from the denominator.
6. Section-5 line: r2_trial prints R2-TRIAL PLAN (population, docs, measured
   chunk total, projected calls under cap, model, max_tokens, cost at cap at
   both S5 anchors) before the first call; R2-PACE at 25 calls; R2-GAUGE
   every 10 documents; every counter and refused-by-branch in the run ledger.

## 7. Verification in container (advisory, Python 3.12.3)
ruff exactly 3 pre-existing findings; collect-only 325; suite 321 passed,
4 failed (the documented test_stakes fixture failures). Separate-process
disk read confirmed each new symbol once and judge/write/extract unchanged.

## 8. Exit criteria (operator's machine, evidence 20260911_v51f_r22_install_evidence.txt)
1. AT-HEAD hashes of the two replaced files equal their 3884f76 hashes.
2. Every DOWNLOAD and DEPLOYED hash equals its card hash.
3. collect-only reports 325; suite reports 325 passed; ruff Found 3 errors.
4. Commit lands; push succeeds; ORIGIN MATCH: True.

## 9. After this gate: the trial (separate block, separate ask)
1. Block sets ANTHROPIC_API_KEY presence check, R2_ENABLED = True inside its
   own python process, runs `priorities r2-trial 120 --seed S`, then
   `priorities r2-compare 60 --seed S`.
2. Disclosure before it runs: <= 400 calls; <= $0.60 at the Haiku anchor;
   runtime unknown until R2-PACE prints; interruption-safe.
3. Operator judges priorities_r2_worksheet.csv, runs `priorities judge-batch
   --r2`, then `priorities r2-compare` again for the acceptance line.
