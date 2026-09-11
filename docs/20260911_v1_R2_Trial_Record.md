# docs/20260911_v1_R2_Trial_Record.md

# R2 holistic extraction pass: trial record and verdict (2026-09-11)

Status: FAIL on precision and on recall. R2 as prompted (extract_priority_v1)
is closed. Any rerun is a new scope through review before any call.

## 1. Run of record (evidence 20260911_v51g_r2_trial_evidence.txt)
1. HEAD a3044dc; seed 20260911; model claude-haiku-4-5; max_tokens 1500;
   chunk 20,000 chars; cap 400 calls (the cap-600 block did not run: a
   block-name collision, two blocks named v51g).
2. Population 5,945 10k_strategy documents (p2's `write` predicate);
   sample 120; measured chunks 1,288 (10.7 per document).
3. Completed 39 documents in 400 calls, 0 API failures; 81 documents capped.
4. Candidates 1,667; deduped 47; relabeled 87; survivors 1,051 on 37
   documents (28.4 per document); refused 567: span-not-verbatim 273,
   generic 168, ip-protection 70, garbled 13, boilerplate 11,
   category-enum 11, historical-relationship-statement 6, out-licensing 6,
   competitor-risk 5, negation 3, granted-exclusive-license 1.
5. Pace 20.3 calls/min measured at 36 calls; 400 calls in 37 minutes.

## 2. Head-to-head (r2-compare, same documents)
1. p2 rows 13; R2 rows 1,051; overlap 4 (exact 4, contained 0);
   R2-only 1,047; p2-only 9.
2. p2-only by category: pipeline_gap judged_wrong 1 / not_judged_wrong 4;
   therapeutic_area 0 / 3; commercial_infrastructure 0 / 1. Regression on
   rows not judged wrong at p2: 8 (amendment 2: FAIL).

## 3. Operator verdicts on the 60-row R2-only worksheet (seed 20260911)
1. correct 10, wrong 49, unsure 1; precision 10/59 = 0.169
   (Wilson 0.095-0.285) against p2's 12/13 = 0.923 (0.667-0.986).
2. Wrong rows by category: data 17, commercial_infrastructure 9,
   financial 8, therapeutic_area 7, pipeline_gap 2, platform 2,
   mechanism_modality 2, geography 1, defensive 1.
3. Wrong-row character (operator): trial-status descriptions, risk-factor
   text, SPAC and financing boilerplate, historical agreements, product
   descriptions. The model extracted what the document says, not what the
   company declares it wants.

## 4. Verdict
1. FAIL on both axes under the ruled acceptance (_r2_verdict): Wilson lower
   bound 0.095 < 0.667 and regression 8 > 0.
2. Root cause: the prompt admits descriptive sentences; the validators
   (span, negation, cluster rules, enum) cannot distinguish description
   from declaration and were never designed to.
3. Constraint for any rescope (operator ruling 2026-09-11): the span must
   carry declaration language or first-person intent; the rescope goes
   through review before any calls.

## 5. Scale figures superseding the roadmap
1. Full corpus at the measured 10.7 chunks/doc: ~63,800 calls, ~$96 at the
   Haiku anchor ($1.51/1k), ~$334 at Sonnet ($5.24/1k), ~52 hours at
   20.3 calls/min. The roadmap's 14,000-21,000 estimate is superseded.
2. Trial spend of record: 400 Haiku calls, ~$0.60 at the anchor; the
   Console row replaces this when it populates.

## 6. What stays
1. stated_priorities untouched by the trial and by judging (r2_judge writes
   candidate_reviews only; verified by test and by the compare line).
2. stated_priorities_r2 holds the 1,051 R2-v1 rows for any classifier work
   (R3) or rescope; the 60 verdicts live in candidate_reviews under R-keys,
   rule_version L3-a3-p2, note prefix r2:.
3. Verdicts live only in the database: run `manual export` at session end.
