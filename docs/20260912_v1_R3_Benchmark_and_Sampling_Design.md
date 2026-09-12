# docs/20260912_v1_R3_Benchmark_and_Sampling_Design.md

# R3 benchmark, sampling, evaluation and adoption design

Version v1. Status: BINDING, per operator ruling 2026-09-12. Companion to
docs/20260912_v1_Strategic_Priority_Annotation_Rule.md (`SP-ANNOT-v1`).
Governed by docs/20260912_v1_R3_Recovery_Benchmark_and_Learned_Extraction_Design.md,
which controls on any conflict; Appendix A3 of that document is folded into
§§3, 4, 5 and 11 below. The freeze checklist in §8 governs the single
locked run.

---

## 1. What the benchmark must answer

1. Every precision figure on record answers one question: of the rows a
   method produced, how many were correct (verified: PROJECT_STATUS v1.28,
   p2 12/13 = 0.923).
2. No measurement on record answers the other: of all real strategic
   priorities present in a document, how many did a method find (verified:
   negative-result record §3, handoff v56 §3 item 2).
3. The benchmark exists to answer the second question, so its unit of
   truth is the complete Item 1 section with every segment labelled.
4. A random sample of sentences is rejected for this purpose: positives
   are rare and p2 selects at document-and-category level with longest-wins
   resolution, so a random sentence sample yields a recall denominator that
   is both small and structurally unlike the production surface (verified:
   `priorities.py:916` selection logic; handoff §16).
5. Random and active sampling remain correct for training and development
   labour reduction, and are used there (§6).

## 2. Two corpora, different rules

| | Development corpus | Locked benchmark |
|---|---|---|
| Composition | complete Item 1 sections, every segment labelled | complete Item 1 sections, every segment labelled |
| Document ids | frozen at R3-0e | frozen at R3-0e, before any model exists |
| Annotated | at R3-0e, before modelling | only after the §8 freeze checklist passes |
| Reuse | unlimited | exactly one evaluation run |
| May inform | rule refinement, prevalence, thresholds, model choice, error analysis, active learning, benchmark sizing | nothing before the run |
| Training exclusion | excluded from training examples | excluded from training and development |

6. No recovered historical judgement from a development or locked document
   may enter any training export (verified: handoff §25).
7. Locked document ids are selected early and annotated late, which is what
   makes the final measurement untouched rather than merely unremembered
   (verified: handoff §17).

## 3. Selection procedure, frozen before it runs

8. Eligible population: documents that reach the p2 writer with a valid
   Item 1 slice; the exact denominator is set by the R3-0c census, not
   assumed here (verified: handoff §29).
9. Stratification dimensions are proposed from measured population
   structure, not chosen now: size class, filing-year band, and p2 yield
   (documents where p2 emitted at least one row versus none).
10. No size threshold is invented; the reproducible filing-time and company
    fields that actually exist in the repository are inspected first, the
    simplest defensible stratification is proposed from them, and it is
    documented before sampling (design document A3.3).
10a. Filing-year bands come from the observed corpus distribution so strata
    are not arbitrarily sparse; bands are never chosen for symmetry (A3.4).
10b. Weights and p2-zero oversampling are set only after R3-0b and the
    SEG-v1 census report the population by document type, year, p2-zero
    status and available company characteristics (A3.1).
10c. The p2-zero stratum may be deliberately oversampled because it is
    especially informative about missed recall; if it is, stratum-specific
    metrics are reported and any population-level aggregate is computed with
    frozen population weights, never as a raw oversampled aggregate (A3.2).
11. Procedure: build the eligible frame, stratify, draw a seeded randomised
    ordered list per stratum, record the seed and the frame hash in the
    design record, and annotate strictly in that order.
12. No document is selected, skipped or reordered after inspection; the
    ordered list is the commitment (verified: handoff §18).
13. The frame, seed, ordered list and stratum assignments are written to a
    committed artefact so the selection is reproducible by a third party.

## 4. Sizing, by positives rather than filings

14. "Five to ten filings" is rejected as a target because it names the
    wrong denominator (verified: handoff §19).
15. Sizing proceeds in two stages: the development corpus is annotated
    first, in frozen order, until the positive count supports a stable
    prevalence estimate; that prevalence then determines how many complete
    documents the locked benchmark needs for the adoption rule's intervals
    to be narrower than the effect the rule requires.
16. The locked size is computed from measured prevalence and the
    precommitted effect size, and recorded before locked annotation begins.
16a. The annotation budget is not set before SEG-v1 reports sentences per
    Item 1 and development annotation reports prevalence (A3.5).
17. Development annotation runs in batches, with prevalence and its
    interval reported after each batch, so the operator sees the curve
    rather than a single terminal number.

## 5. Annotation quality control

18. After development annotation completes, a random subset is re-annotated
    blind, without sight of the original label (verified: handoff §21).
19. Reported agreement is not raw overall agreement, because the negative
    class dominates and would inflate it; the reported measures are
    priority-versus-non-priority agreement, agreement restricted to units
    called positive in either pass, and category agreement among positives.
20. A second annotator is desirable but not required to proceed: the
    minimum reliability check is the operator's blind re-annotation of a
    frozen random subset, and a qualified second annotator, if available,
    judges a smaller independent subset reported separately (A3.6).
21. Weak agreement is itself a result: it means the definition cannot
    support small model differences, and the adoption rule's effect size
    must widen accordingly.

## 6. Training data and active learning

22. Training draws on three sources: unambiguously recovered historical
    judgements from R3-0c, representative ordinary Item 1 segments from
    non-benchmark documents, and active-learning additions.
23. The recovered historical corpus is p2-selected and therefore
    distributionally biased; it is seed data and can never serve as the
    acceptance population (verified: handoff §15).
24. Active learning surfaces uncertain, boundary, novel-positive and
    diverse high-information segments from p2-missed text for labelling,
    then retrains, repeating until improvement stops or the annotation
    budget is spent (verified: handoff §23).
25. Bulk random negative labelling is avoided; the negative class is
    abundant and cheap to sample without operator time.

## 7. Splits and leakage controls

26. Splits are document-level at minimum; no sentence-level random split is
    permitted (verified: handoff §25).
27. Company overlap across splits is reported, because the same company
    repeats language across filing years and would otherwise leak.
28. Every training export states the excluded development and locked
    document ids and their count, as a checkable line rather than an
    assurance.

## 8. Freeze checklist before the locked run

29. Training-data version, preprocessing, model architecture, thresholds,
    candidate-generation logic, code and model version, evaluation script,
    and the adoption rule are each frozen and hashed.
30. Only then is the locked benchmark annotated, under the same `ANNOT`
    version used for development.
31. The comparison runs once.

## 9. What the locked run reports

32. Three systems on identical documents: p2 alone, the learned layer's
    incremental additions alone, and the union.
33. Measures: p2 precision and recall, incremental-addition precision,
    union precision and recall, recall gain over p2, each with a Wilson
    interval.
34. Incremental precision is reported separately and prominently, so a weak
    learned layer cannot shelter behind p2's strong rows (verified: handoff
    §26).
35. The historical 0.923 is context only and is never the comparator,
    because it was measured on a different population (verified: handoff
    §27).

## 10. Adoption rule template

36. The rule is precommitted, with three blanks filled from business
    utility and development results before locked labels exist:
37. **Union precision floor:** the combined feed's precision must not fall
    below `____` (Wilson lower bound).
38. **Required recall gain:** union recall must exceed p2 recall by at
    least `____` percentage points, with the interval excluding zero.
39. **Incremental precision floor:** rows added by the learned layer must
    themselves reach at least `____`, so recall is not bought with noise.
40. Failure on any one of the three closes R3 as a measured negative
    result, with p2 remaining the production feed, and the closure is
    written as a decision record in the manner of R2 and R2v2 (verified:
    handoff §27, Operating Manual v2 §9).

## 11. Parameters derived from measurement, not chosen

41. Stratum weights and p2-zero oversampling: derived after the SEG-v1
    population census, then frozen before sampling (A3.1, A3.2).
42. Size-class boundary and its source field: proposed from the fields that
    exist, documented before sampling (A3.3).
43. Filing-year bands: derived from the observed distribution (A3.4).
44. Annotation budget: set after SEG-v1 segment counts and development
    prevalence (A3.5).
45. Second annotator: optional, not gating (A3.6).
46. The three adoption thresholds in §10 stay unset until development
    results establish the realistic tradeoff, and are frozen before locked
    annotation (A4.1).
