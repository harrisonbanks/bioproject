# docs/20260911_v1_GATER2V22A_INSTALL.md

# Gate R2v2-2a install runbook: benchmark fixes for the R2-v2 head-to-head (code, tests, no API call)

Operator go 2026-09-11 with the snapshot amendment: the comparison's p2
denominators freeze at first print; operator verdicts still retire p2 rows
for the table's own integrity. Expected HEAD before install: 787a8b3.

## 1. Package installs
None.

## 2. New files
1. 20260911_v1_GATER2V22A_INSTALL.md -> docs\20260911_v1_GATER2V22A_INSTALL.md

## 3. Replaced files (full-file replacements of the 787a8b3 versions)
1. 20260911_v5_priorities.py -> src\biointel\priorities.py
   Changed: _r2_verdict(k, n_dec, regression, pending=0) adds PENDING-P2;
   r2_compare rewritten (see section 6); r2_trial --v2 raises the process
   cap to the measured stage-1 call count and prints calls_needed and
   configured_cap on the R2V2-STAGE1 line. Added: _r2_pair,
   _r2_snapshot_path, _r2_p2_snapshot, _r2_write_worksheet. Unchanged:
   extract_priorities, judge, write, r2_judge, judge_batch, both
   extractors, RULE_VERSION_F2.
2. 20260911_v5_test_priorities.py -> tests\unit\test_priorities.py
   Appends 3 tests (73 -> 76); four earlier assertions updated to the new
   line formats (group token, R2-VERDICT line, P2ONLY states).
   Collect-only 332 -> 335.

## 4. Surgical edits
None.

## 5. Migration
None. The snapshot is a JSON file under data\snapshots
(r2_compare_p2_snapshot_<version>.json), created by the first compare for a
version and read by every later one; delete it only to restart a comparison
from scratch, never mid-trial.

## 6. What r2_compare now does
1. Loads the version's R2 rows and their units (entity, date, capture).
2. p2 side = the frozen snapshot of stated_priorities rows on those units,
   written at first print (R2-SNAPSHOT CREATED line) and reused afterward,
   so a p2 row retired by a verdict still counts in p2_rows and p2_only.
3. R2-v2 splits units into HELD-OUT (no R2-v1 survivor rows; the fit set
   came from R2-v1 survivors) and FIT; R2-v1 uses one group ALL. Each group
   prints R2-COMPARE, R2-P2ONLY per category with three states
   (judged_correct, judged_wrong, pending), and R2-ACCEPTANCE; the HELD-OUT
   (or ALL) line is marked "(decides)" and feeds the final R2-VERDICT line.
4. Regression = p2-only rows the operator judged correct; judged wrong is
   excused; unjudged is pending and holds PENDING-P2 unless precision already
   fails (FAIL dominates).
5. Two worksheets: priorities_r2_worksheet.csv (<= n unjudged R2-only rows,
   R-keys, `judge-batch --r2`, candidate_reviews only) and
   priorities_p2only_worksheet.csv (all pending p2-only rows, S-keys,
   `judge-batch <path>`, the real p2 judge path: wrong retires).

## 7. Verification in container (advisory, Python 3.12.3)
ruff exactly 3 pre-existing; collect-only 335; suite 331 passed, 4 failed
(the documented test_stakes fixture failures); separate-process disk read
confirmed each new symbol once and judge/write/extractors unchanged.

## 8. Exit criteria (evidence 20260911_v51l_r2v22a_install_evidence.txt)
1. AT-HEAD hashes of the two replaced files equal their 787a8b3 hashes.
2. Every DOWNLOAD and DEPLOYED hash equals its card hash.
3. collect-only 335; suite 335 passed; ruff Found 3 errors.
4. Commit lands; push succeeds; ORIGIN MATCH: True.

## 9. R2v2-2b, the paid rerun (separate ask after this gate)
`r2-trial 120 --seed 20260911 --v2` prints the measured stage-1 candidate
count and calls_needed before the first call; `r2-compare 60 --seed
20260911 --v2` prints the snapshot, both groups, both worksheets, and
R2-VERDICT; the operator judges both worksheets; a final compare prints the
deciding line.
