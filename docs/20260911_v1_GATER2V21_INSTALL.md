# docs/20260911_v1_GATER2V21_INSTALL.md

# Gate R2v2-1 install runbook: stance-first two-stage extraction (code, tests, no API call)

Scope basis: docs/20260911_v1_R2v2_Stance_First_Extraction_Decision_Record.md.
Operator go 2026-09-11 with two conditions: heading rule approved; the
fixture test pins per-rule attribution. Expected HEAD before install: 83cac01.

## 1. Package installs
None.

## 2. New files (download name -> deploy path)
1. 20260911_v1_extract_priority_v2.txt -> src\biointel\prompts\extract_priority_v2.txt
   (prompt text; no deploy-path line inside)
2. 20260911_v1_r2_verdicts_20260911.csv -> tests\unit\fixtures\r2_verdicts_20260911.csv
   (the 60 operator verdicts, verbatim: key, verdict, category, sentence)
3. 20260911_v1_GATER2V21_INSTALL.md -> docs\20260911_v1_GATER2V21_INSTALL.md

## 3. Replaced files (full-file replacements of the 83cac01 versions; the
## block refuses if the deployed hash is not the 83cac01 hash)
1. 20260911_v4_priorities.py -> src\biointel\priorities.py
   Added before `def cli`: R2V2_EXTRACTOR_VERSION ("R2-v2"),
   R2V2_PROMPT_VERSION, R2V2_BATCH (40), _STRATEGY_VERBS, _FLS_TRIGGER_RX,
   _FLS_SUBJECT_RX, _FLS_IMPERATIVE_RX, _FLS_HEADING_NOUN_RX,
   _FLS_PROGRESSIVE_RX, _FLS_REFUSE_RX, _FLS_DATE_RX, _FLS_CLAUSE_SPLIT_RX,
   _fls_stage1, _r2v2_candidates, _R2V2_LINE_RX, _parse_r2v2_reply,
   _r2v2_prompt, extract_priorities_llm_v2.
   Changed signatures (default = prior behavior): _r2_write_doc(...,
   version=R2-v1); r2_trial(..., version=R2-v1) prints R2V2-STAGE1 and
   dispatches to the v2 extractor when version is R2-v2; r2_compare(...,
   version=R2-v1) filters r2 rows by version and prints it; cli r2-trial and
   r2-compare accept --v2. Unchanged: extract_priorities, judge, write,
   r2_judge, judge_batch, extract_priorities_llm, RULE_VERSION_F2.
2. 20260911_v4_test_priorities.py -> tests\unit\test_priorities.py
   Appends 7 tests (66 -> 73 in the file); two R2-2 assertions updated for
   the "version" token in the R2-COMPARE line and the new r2_trial keyword.
   Collect-only 325 -> 332.

## 4. Surgical edits
None.

## 5. Migration
None. R2-v2 rows share stated_priorities_r2 with R2-v1 rows, separated by
extractor_version; merge-write and compare are version-keyed.

## 6. Stage-1 measurement on the fit set (pinned in the fixture test)
1. Corrects passed 10/10 (record floor: all 10); wrongs refused 46/49 (floor
   40); the unsure row is refused.
2. Per-rule attribution: corrects by fls-trigger 3, progressive 4,
   imperative 2, heading 1; wrongs by refuse-lexicon 11, refuse-date 5,
   none 30, fls-trigger 3 (the three wrongs that reach stage 2); unsure by
   none 1. The heading rule catches exactly one row ("Increasing product
   uptake and sales of PROCYSBI ...").
3. The record's §3.1 filter as written (safe-harbor lexicon plus first-person
   clause) measured 5/10 and 33/49; the strategy-verb imperative, heading,
   and progressive rules and the refusal lexicon close the gap. The 60 rows
   are the fit set; gate R2v2-2's 120-document rerun is the held-out test.

## 7. Design decisions
1. Stage 1 rule order: refuse-lexicon, refuse-date, imperative, heading,
   progressive, fls-trigger, none. Refusals precede passes so a risk or
   history clause defeats a trigger in the same sentence.
2. Stage 2 span by index: each call carries at most 40 numbered stage-1
   sentences; the model answers "N: <category>" or "N: refuse"; the span is
   the sentence at N. span-not-verbatim cannot occur (273 refusals in the v1
   trial). Negation, cluster validator, enum, and dedup unchanged.
3. Stage 1 passes negated declarations by form ("nor do we plan to acquire"
   carries a trigger and a subject); the negation validator refuses them at
   stage 2, as the end-to-end test shows.
4. Sentence unit: split on the p2 break class ([.!?;bullet]); 20-500 chars.
   Heading run-ons without a terminator stay attached to the following
   sentence and are judged as one string (the fixture world's only stance
   sentence is refused for that reason: "Risk Factors 12 ITEM 1 BUSINESS We
   seek ..."); the held-out rerun measures the cost of this.
5. Dictionary traps: every trigger is boundary-anchored and inflection-listed;
   the test asserts goodwill, planetary, willow, and "targeted therapies"
   never fire, and third-party subjects never fire. No wordlist sweep exists
   in the container; a full sweep is queued behind a committed wordlist.

## 8. Verification in container (advisory, Python 3.12.3)
ruff exactly 3 pre-existing; collect-only 332; suite 328 passed, 4 failed
(the documented test_stakes fixture failures); separate-process disk read
confirmed each new symbol once and the p2 and R2-1/R2-2 symbols unchanged.

## 9. Exit criteria (operator's machine, evidence 20260911_v51j_r2v21_install_evidence.txt)
1. AT-HEAD hashes of the two replaced files equal their 83cac01 hashes.
2. Every DOWNLOAD and DEPLOYED hash equals its card hash.
3. collect-only 332; suite 332 passed; ruff Found 3 errors.
4. Commit lands; push succeeds; ORIGIN MATCH: True.

## 10. Gate R2v2-2 (paid, separate ask after this gate closes)
`r2-trial 120 --seed 20260911 --v2`: the R2V2-STAGE1 line prints the
measured candidate count and the PLAN line the projected calls (batches of
40) before the first call; cap set from that count; Haiku; then
`r2-compare 60 --seed 20260911 --v2`, operator judging through
`judge-batch --r2`, and the same Wilson-bound acceptance and amendment-2
recall test against the 13 p2 rows on the same documents.
