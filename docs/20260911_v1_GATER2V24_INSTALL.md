# docs/20260911_v1_GATER2V24_INSTALL.md

# Gate R2v2-4 install runbook: final free branch round, tagged judging, stopping rule (no API call)

Operator ruling 2026-09-11, binding: one final free branch round; if the
fourth measurement's held-out precision has a Wilson lower bound below
p2's (12/13, 0.667), R2 closes as a measured negative result with a
decision record, the table kept at extractor-version provenance and
excluded from the matcher, and the session moves to R3 (classifier on the
verdict ledger). No paid calls in any of this. Expected HEAD: ca63d90.

## 1. Package installs
None.

## 2. New files (download name -> deploy path)
1. 20260911_v1_r2v2_verdicts_round3_20260911.csv -> tests\unit\fixtures\r2v2_verdicts_round3_20260911.csv
   (round-3 worksheet, 30 correct / 30 wrong, verbatim)
2. 20260911_v1_GATER2V24_INSTALL.md -> docs\20260911_v1_GATER2V24_INSTALL.md

## 3. Replaced files (full-file replacements of the ca63d90 versions)
1. 20260911_v8_priorities.py -> src\biointel\priorities.py
   New branches: financing, may-hedge, conditional-fragment,
   historical-or-practice, debris, belief-without-plan (We believe ... with
   no plan verb). Widened: trial-milestone (interim futility, breakthrough
   designation, accelerated approval, roman-numeral phases, combination
   with an inhibitor), risk-conditional (depend on our ability),
   agreement-terms (assert the validity, exclusive forum).
   judge_batch(..., tag="") prefixes r2 notes with the tag; r2_compare(...,
   tag="") counts only verdicts of that tag in the acceptance line;
   cli: judge-batch --r2 --tag T, r2-compare --v2 --tag T.
2. 20260911_v8_test_priorities.py -> tests\unit\test_priorities.py
   Appends 3 tests (83 -> 86). Collect-only 342 -> 345.

## 4. Surgical edits
None.

## 5. Fit-set measurement (pinned)
Round 3 fixture: 26 of 30 wrongs refused, 30 of 30 corrects kept
(financing 7, conditional-fragment 4, historical-or-practice 4,
trial-milestone 4, may-hedge 3, agreement-terms 1, belief-without-plan 1,
debris 1, risk-conditional 1). Round 1 fixture unchanged: 33/36 and 23/23.

## 6. The fourth measurement (held-out, uncontaminated)
1. r2-refilter --seed 20260911 re-filters the 1,658 survivors and writes a
   fresh 60-row worksheet of unjudged survivors.
2. The operator judges it and ingests with `judge-batch --r2 --tag round4`.
3. `r2-compare 60 --seed 20260911 --v2 --tag round4` prints the acceptance
   line counting round-4 verdicts only; the HELD-OUT line decides. Earlier
   rounds' verdicts (fit sets) are excluded by the tag.

## 7. Exit criteria (evidence 20260911_v51t_r2v24_evidence.txt)
State lines and live listings printed; hashes match; collect-only 345;
345 passed; Found 3 errors; no live snapshot change; commit and push;
ORIGIN MATCH True; R2-REFILTER and R2-WORKSHEET lines printed.
