# docs/20260911_v1_GATER2V23_INSTALL.md

# Gate R2v2-3 install runbook: stage-2 refusal branches, zero-call refilter, p2-only diagnose (no API call)

Operator go 2026-09-11. Expected HEAD before install: a5535ca.

## 1. Package installs
None.

## 2. New files (download name -> deploy path)
1. 20260911_v1_r2v2_verdicts_20260911.csv -> tests\unit\fixtures\r2v2_verdicts_20260911.csv
   (the 60 R2-v2 trial verdicts, verbatim)
2. 20260911_v1_Manual_Errata_Block_Discipline.md -> docs\20260911_v1_Manual_Errata_Block_Discipline.md
3. 20260911_v1_GATER2V23_INSTALL.md -> docs\20260911_v1_GATER2V23_INSTALL.md

## 3. Replaced files (full-file replacements of the a5535ca versions)
1. 20260911_v7_priorities.py -> src\biointel\priorities.py
   Added: R2V2_REFUSED_VERSION, _R2V2_INTENT_RX, _R2V2_DESIGN_RX,
   _R2V2_BRANCHES (trial-milestone, risk-conditional, out-partnering,
   ops-financial-necessity, agreement-terms, belief-or-fragment),
   _r2v2_stage2_refuse (adds designed-based-description and fragment),
   r2_refilter, r2_diagnose; cli branches r2-refilter [--seed S] and
   r2-diagnose. Changed: extract_priorities_llm_v2 applies the branches
   after _r2_validate. Unchanged: judge, write, extract_priorities, the v1
   extractor, r2_judge, r2_compare, RULE_VERSION_F2.
2. 20260911_v7_test_priorities.py -> tests\unit\test_priorities.py
   Appends 6 tests (77 -> 83). Collect-only 336 -> 342.

## 4. Surgical edits
None.

## 5. Migration
None. Refused rows are re-stamped extractor_version R2-v2-refused and kept;
nothing is deleted; R-keys do not include the version, so verdicts attach.

## 6. Fit-set measurement (pinned in the fixture test)
1. 33 of 36 wrongs refused; 23 of 23 corrects kept; the unsure row kept.
2. Attribution: trial-milestone 8, out-partnering 6, risk-conditional 5,
   designed-based-description 5, ops-financial-necessity 4,
   agreement-terms 2, belief-or-fragment 2, fragment 1; 3 wrongs survive
   (generic mission and method statements with intent verbs).
3. The 60 rows are the fit set; the re-filtered worksheet is the held-out
   measure; the block runs the refilter and writes it.

## 7. Block sequence in this gate (all free)
1. Install, suite 342, commit, push.
2. `priorities judge S224d39984a42e0d0 wrong --note "r2: excused, S224d family"`
   (the pending p2-only row: the real judge path retires it; the snapshot
   keeps it; the compare's pending count clears to 0).
3. `priorities r2-diagnose`: attribution of every p2-only row in the
   R2-v2 snapshot (stage1:<rule>, stage2:<branch>, or model-or-validator)
   with the S-key's full verdict history across rule versions, which
   answers the pending-lookup question of record.
4. `priorities r2-refilter --seed 20260911`: refusals per branch over the
   stored R2-v2 rows; fresh 60-row worksheet of unjudged survivors.
5. `priorities r2-compare 60 --seed 20260911 --v2`: precision on the
   surviving judged rows per group (fit-side signal only) and the recall
   line with pending 0.

## 8. Exit criteria (evidence 20260911_v51s_r2v23_evidence.txt)
1. State lines printed first (HEAD, tracked changes, untracked, live
   snapshots) and live-folder listings before and after the suite.
2. AT-HEAD hashes equal the a5535ca hashes; every DOWNLOAD and DEPLOYED
   hash equals its card.
3. collect-only 342; suite 342 passed; ruff Found 3 errors; no new live
   snapshot after the suite.
4. Commit lands; push succeeds; ORIGIN MATCH: True; the four commands in
   section 7 print their lines.

## 9. Next
The operator judges the re-filtered 60-row worksheet; the next compare
prints the held-out precision that decides whether R2-v2 proceeds to a
corpus ask or the design is revisited. No paid run before that.
