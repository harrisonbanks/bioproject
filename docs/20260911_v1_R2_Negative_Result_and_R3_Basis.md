# docs/20260911_v1_R2_Negative_Result_and_R3_Basis.md

# R2v2 stance-first extraction: decision record - measured negative result, R3 basis

Closes the R2/R2v2 campaign of 2026-09-11. Companion to
docs/20260911_v1_R2_Trial_Record.md (R2 v1 close),
docs/20260911_v1_R2v2_Stance_First_Extraction_Decision_Record.md (scope
basis), and the four judged worksheets referenced below. Binding: R2v2
tables are retained but excluded from the matcher; no further R2 calls
without a new scope through review.

## 1. What was tried

R2 (topic-only extraction): an LLM reads each 10-K's Item 1 in chunks and
emits candidates matching one of nine priority topics, validated by the
ruled machinery (span-locate, negation, cluster rules, enum). Trial:
39/120 docs, 400 calls, R2-only precision 10/59 = 0.169 vs p2's 12/13 =
0.923. Closed 2026-09-11 (docs/20260911_v1_R2_Trial_Record.md).

R2v2 (stance-first, two-stage): stage 1 a deterministic forward-looking-
statement filter (safe-harbor lexicon, first-person subject, strategy-verb
imperative/heading/progressive forms) admits only sentences carrying
declared intent by form; stage 2 an LLM classifies or refuses admitted
sentences by numbered index (eliminating span-not-verbatim structurally).
Gates R2v2-1/2a delivered the code (commits 787a8b3, 5e91243, suites 332
and 335, no API calls). The paid trial (R2v2-2b, seed 20260911, Haiku,
120 documents) ran 291 calls, 0 failures, wrote 1,871 survivors on 112 of
120 documents at a measured pace of 5.0 calls/min (40-sentence prompts).

## 2. Four measurements, all free after the one trial

| Round | Worksheet | Branches added | Held-out precision | Wilson |
|---|---|---|---|---|
| 1 | 60 rows, no branches | none | 10/59 = 0.169 | 0.095-0.285 |
| 2 | 60 rows | trial-milestone, risk-conditional, out-partnering, ops-financial-necessity, agreement-terms, belief-or-fragment, designed-based-description | 23/59 = 0.390 | 0.276-0.517 |
| 3 | 60 rows | financing, may-hedge, conditional-fragment, historical-or-practice, debris, belief-without-plan | 30/60 = 0.500 | (fit-set) |
| 4 | 60 rows | 2 escape fixtures only (bullet debris, comma/conjunction-opener), no re-measurement claimed | 21/43 = 0.488 (held-out, deciding) | 0.346-0.632 |

Baseline: p2 10k_strategy operator precision 12/13 = 0.923 (Wilson
0.667-0.986), PROJECT_STATUS v1.28. Every branch round was validated against
its own fit set (corrects-kept, wrongs-refused, per-branch attribution
pinned in tests/unit/test_priorities.py) before the next held-out
measurement; the held-out number never rewarded the branches that produced
it. Round 4's Wilson lower bound (0.346) sits below p2's exact lower bound
(0.667): the operator ruling's stopping condition.

## 3. Recall (held-out, frozen p2 snapshot)

Of 33 p2 rows on 76 held-out documents, R2-v2 paired 18 (all by
containment, 0 exact) and dropped 15: 14 the operator judged correct at
p2 (a recall regression under the operator's amendment 2) and 1 excused
(judged wrong at p2, the Vaxart financing-dependence row S224d39984a42e0d0).
The branch passes that raised precision in round 4 cost one previously-
paired row, moving recall the wrong direction. R2v2 never beat p2 on
recall at any measurement.

## 4. Root cause

Every branch round measured 100% retention of operator-correct rows on its
own fit set (round 2: 23/23; round 3: 30/30; round 4's two additions:
30/30 unchanged), while held-out precision plateaued at 0.39, 0.50, 0.49.
The remaining wrong rows are not a pattern the branches missed; they are
sentences carrying declared intent by grammatical form about routine
operations - financing posture, expense expectations, compliance stance,
hedged possibility ("we may..."), regulatory-path plans, present-practice
description - indistinguishable from a true stated priority by form alone.
Separating them requires judgment about what counts as strategy versus
operations, a boundary deterministic filters cannot encode without
approaching the LLM classification the design was meant to constrain.

## 5. Verdict and disposition

R2v2 CLOSED as a measured negative result. stated_priorities_r2 (1,871
rows, R2-v1 and R2-v2, 1,485 surviving the final refilter) is RETAINED
under extractor_version provenance and EXCLUDED from the matcher; no
downstream code reads the table (verified: only priorities.py and its own
schema.py declaration reference it). No further R2 calls without a new
scope through review, per the operator's standing ruling.

## 6. The asset: the R3 training corpus

candidate_reviews holds 10,040 review rows on 5,673 distinct judged keys
across every rule version to date; under the frozen ruleset L3-a3-p2
specifically, 4,951 current verdicts (240 R-keys from the R2 campaign,
4,711 S-keys from p1/p2 carry-forward and fresh p2 judging). This is the
R3 training set: a classifier trained on the operator's own verdicts,
above the sufficiency threshold the decision record's research trail
cited (Feng Li, SSRN 1267235, 30,000 hand-coded sentences at a different
task scale; FinBERT precedent, 3,500 MD&A sentences). R3 makes zero new
API calls to build; its own acceptance test is a separate scope.

## 7. Spend of record

291 API calls total across the entire R2v2 campaign (the one paid trial);
approximately $0.44 at the Haiku anchor. Every branch round and every
worksheet measurement after the trial was free. No full-corpus run
occurred.
