# docs/20260911_v1_R2v2_Stance_First_Extraction_Decision_Record.md

# Decision record: R2 trial failure diagnosis and the R2-v2 stance-first design
Operator-commissioned research record (2026-09-11). Companion to
docs/20260910_v1_Text_Extraction_Research_and_Roadmap.md (R2 entry) and the
R2 trial evidence (20260911_v51g). Binding as the R2-v2 scope basis.

## 1. The measured failure (trial of record)

1. Trial: 400 calls, 39 docs, Haiku, prompt extract_priority_v1
   (topic-defined categories, no stance requirement). Evidence: v51g.
2. Result: 1,051 survivors (28.4/doc) vs 13 p2 rows on the same docs;
   operator precision on the 60-row judged sample 10/60 ~ 0.17 vs the
   0.923 baseline; recall FAIL (8 p2 rows dropped, not judged-wrong).
3. Failure mechanism, from the 49 wrong verdicts: the model matched
   TOPIC (trials->data, sales->commercial_infrastructure,
   financing->financial) where the table requires STANCE (the company
   declaring an intention). Descriptions, risk factors, status updates,
   and historical agreements all matched topics. The validators refuse
   p2's failure modes (mis-stamps, slicer damage), not "true sentence,
   right topic, zero intent" - a new failure mode with no branch.

## 2. What the field does (research trail, 2026-09-11)

1. THE TARGET HAS A LEGAL DEFINITION. Securities law's forward-looking
   statements (FLS) are "statements that refer to plans, intentions,
   objectives, goals, targets, strategies" - and every 10-K prints the
   canonical trigger lexicon in its safe-harbor section: may, will,
   intend, plan, goal, target, strategy, aim, expect, seek, continue,
   believe, anticipate, opportunity, future (verified: safe-harbor
   sections of multiple 10-Ks on EDGAR, e.g. sec.gov/Archives/edgar/
   data/1081745/000149315221007156). The stance filter R2 lacked is
   printed in the documents themselves.
2. STANCE-FIRST TWO-STAGE IS THE ESTABLISHED REMEDY. Clinical action
   extraction (arXiv 2605.06191) formalizes it: stage 1 judges only
   "is this sentence actionable/declared?"; stage 2 categorizes
   survivors; the separation exists because it "improves robustness by
   reducing false positives from descriptive or narrative text" - our
   defect verbatim. The rule-based-candidate-filter -> LLM-classifier
   shape recurs across extraction pipelines (medrxiv 2026.04.29,
   arXiv 2505.01077).
3. FINANCE HAS RUN THIS AT SCALE. Feng Li (SSRN 1267235): FLS extracted
   FIRST by trigger words, then 13M sentences classified by a model
   trained on 30,000 hand-coded ones. Industry: FinBERT fine-tuned on
   3,500 MD&A sentences as a dedicated forward-looking-language
   detector (LSEG, via intuitionlabs.ai/articles/
   llm-financial-document-analysis).

## 3. R2-v2 design (scope basis; each piece gated as usual)

1. STAGE 1 - deterministic FLS trigger filter, zero API calls: a
   sentence is a candidate only if it (a) contains an FLS trigger from
   the safe-harbor lexicon (boundary-anchored, dictionary-swept per
   manual rule 6) and (b) has first-person corporate subject (we, our,
   the Company) in the trigger clause. Expected effect: candidate pool
   and call count drop by an order of magnitude; descriptions, risk
   factors, and status text never reach the model.
2. STAGE 2 - LLM classify-or-refuse on triggered sentences only: the
   prompt requires DECLARED INTENT in the span ("the sentence must
   state what the company intends, plans, aims, or seeks to do;
   descriptions of products, studies, risks, history, or market
   conditions are refusals"), then assigns one of the nine categories
   or refuses. Verbatim-span, negation, cluster-validator, and enum
   gates unchanged from R2-1.
3. VALIDATION SET EXISTS: the 60 operator verdicts of 2026-09-11. The
   10 corrects all carry declaration language ("selectively expand",
   "we aim", "plan to launch", "build a", "pursuing opportunities");
   the 49 wrongs largely do not. Acceptance for the stage-1 filter:
   it must pass all 10 corrects and refuse >= 40 of the 49 wrongs
   BEFORE any paid rerun (free, in tests).
4. TRIAL RERUN: same 120-doc seed, same caps, same Wilson-bound
   acceptance and recall-regression rules as R2-2; the p1-wrong
   judged rows remain the only excusable p2-only drops.
5. CONVERGENCE WITH R3: stage 1's trigger filter + the operator's
   ~1,800 cumulative verdicts approximate the training corpus the
   literature deems sufficient (3.5K); a FinBERT-class stage-2
   classifier remains the cost-collapse path after R2-v2 measures.

## 4. Binding constraints carried forward
Proposer-only; frozen versions; provenance; source-or-silence with
verbatim spans; R2-only verdicts through the R-key recorder, zero
writes to the priorities tables; section-5 disclosure before any paid
run.
