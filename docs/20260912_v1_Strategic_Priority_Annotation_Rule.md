# docs/20260912_v1_Strategic_Priority_Annotation_Rule.md

# Annotation rule: what counts as a stated strategic priority

Version `SP-ANNOT-v1`. Status: RATIFIED on the three semantic questions
below by operator ruling 2026-09-12; frozen from that date. Any material
change creates `SP-ANNOT-v2`, documents the reason, identifies affected
development annotations, and re-annotates them. The locked benchmark is
annotated under one version only.

Governed by docs/20260912_v1_R3_Recovery_Benchmark_and_Learned_Extraction_Design.md,
which controls on any conflict; §§22 and 23 of that document are this
document's parent sections, and Appendix A2 is folded into §§3 and 8 below.

Derived from the business objective and the existing schema and rulings.
The R2 and R2v2 specimens appear here as illustrations of the boundary,
never as the source of the definition.

---

## 1. Why this class exists

1. The platform's thesis is that acquisitions become more predictable when
   what a company says it wants is matched against what other companies
   actually have (verified: R3 recalibration handoff §1).
2. `stated_priorities` is the substrate for the buyer side of that match,
   so a row earns its place only if it would change which counterparty the
   matcher proposes (verified: docs/20260902_v1_Data_Feeder_Roadmap.md).
3. That is the operational test behind everything below: a sentence is a
   strategic priority when a reasonable analyst, reading it, would revise
   their view of what this company is looking to acquire, build, enter or
   defend.

## 2. The question put to the annotator

> Does this sentence state a meaningful strategic direction or intended
> strategic action of the company itself?

4. Answer is binary at Stage A: `priority` or `not_priority`.
5. Category assignment is recorded for positives only, and Stage B remains
   out of scope until Stage A succeeds (verified: handoff §28).

## 3. The three tests, all of which must pass

6. **Agent test.** The company itself is the actor. Statements about what
   the market does, what regulators require, what partners have done, or
   what a subsidiary or an unrelated company does, fail.
7. **Commitment test.** The sentence asserts direction, intent, strategy,
   goal, mission or planned action. Description of present operations,
   history, capability inventory, or risk fails.
8. **Consequence test.** The direction named is strategic rather than
   routine: it concerns what the company will pursue, acquire, build,
   enter, prioritise or defend, not the ordinary execution of business it
   is already committed to.
9. All three must pass. The R2v2 negative result is exactly a corpus of
   sentences that pass tests 6 and 7 and fail test 8 (verified:
   docs/20260911_v1_R2_Negative_Result_and_R3_Basis.md §4).

## 4. Categories for positives

Nine values, unchanged from the production enum (verified:
`schema.py` `PRIORITY_CATEGORIES`).

| Category | Covers |
|---|---|
| `pipeline_gap` | acquiring, in-licensing or partnering to fill a pipeline or asset gap |
| `therapeutic_area` | entering, prioritising or building a franchise in a disease area |
| `mechanism_modality` | committing to a mechanism or therapeutic modality |
| `platform` | building or expanding a technology platform |
| `data` | strategic evidence, data or real-world-evidence generation |
| `geography` | entering or expanding into a market or region |
| `financial` | strategically motivated capital allocation or portfolio reshaping |
| `defensive` | intellectual-property, lifecycle or competitive defence |
| `commercial_infrastructure` | commercial reach, market access, channel, payer, delivery network or sales capability |

10. `commercial_infrastructure` was added because channel, access and
    delivery-network intent was the single most frequent unlabelable theme
    in a 120-row sample, and was previously mis-stamped as `platform` or
    `therapeutic_area` (verified:
    docs/20260908_v1_Vocabulary_Gap_Commercial_Capability.md).
11. If a sentence plausibly carries more than one category, the annotator
    records every category that applies; whether Stage B is single-label
    or multi-label is settled later from these counts, not assumed now
    (verified: handoff §28).

## 5. Positive examples, with provenance

12. `pipeline_gap`: a company stating it seeks to acquire businesses,
    assets or products complementing its existing business (verified:
    `priorities.py` PRIORITY_RULES, Akorn 10-K 2015 specimen `03fdcee3d8f8`).
13. `pipeline_gap`: strategic priorities listed as including in-licensing
    or acquiring investigational compounds (verified: BMY 10-K 2019
    specimen `62ab199b8ecc`).
14. `therapeutic_area`: a stated principal business objective to identify,
    develop and commercialise products for named disease indications
    (verified: Tenax 10-K 2018 specimen `e49b72a0ef3e`).
15. `commercial_infrastructure`: a stated strategy to leverage scientific
    and clinical expertise together with global commercial infrastructure
    to maximise value (verified: `S16d531edd84b7a06`, vocabulary-gap
    record).
16. `commercial_infrastructure`: seeking partners with commercial reach
    and experience in a named area in their respective regions (verified:
    `S0d8ac69ec0679910`, vocabulary-gap record).
17. `platform`: a stated aim to build a proprietary pipeline from a named
    technology platform (verified: aTYR 2016 specimen, `_DECLARATIONS`).

## 6. Negative classes, named

18. **Routine forward operations.** Expected expense growth, planned
    hiring, ordinary manufacturing scale-up, standard regulatory steps.
19. **Trial execution.** Enrolment plans, readout timing, study conduct,
    conference presentation plans.
20. **Financing posture.** Generic capital-raising language, going-concern
    dependence on future financings, hedging and treasury statements.
21. **Compliance stance.** Statements of intent to comply with law,
    regulation or listing requirements.
22. **Hedged possibility.** "We may" constructions carrying no commitment,
    and conditional fragments whose antecedent is a contingency.
23. **Belief without plan.** "We believe" statements asserting a view
    rather than an intended action.
24. **Description.** Product descriptions, technology overviews,
    "designed to" statements, capability inventories, market descriptions.
25. **History.** Completed transactions, existing agreements, past
    partnering, prior approvals.
26. **Risk disclosure.** Risk-factor text, including risk text that is
    grammatically forward-looking.
27. These nine classes are the measured failure distribution of R2 and
    R2v2, not a speculative list (verified: R2 trial record §3,
    negative-result record §4).

## 7. Disqualifiers that override any content reading

28. **Wrong entity.** If the sentence describes a company other than the
    one the row is attributed to, the unit is `not_priority` regardless of
    content; attribution defeats content (verified: vocabulary-gap record,
    attribution pile, twelve specimens).
29. **Negation inversion.** A sentence whose extracted form reverses a
    negated clause is `not_priority` (verified: `S1e6a836b015eca6c`).
30. **Truncation or debris.** Bullet debris, mojibake, table fragments and
    mid-sentence clips are `not_priority`, and the annotator marks the
    unit `malformed` so segmentation defects are countable separately
    (verified: `S02a95e01d937cb32`).
31. **Misquote.** If the unit's text does not occur verbatim in the source
    document, it is `not_priority` and marked `not_verbatim` (verified:
    `Sa0aafbb3410df2a5`, `Sde5e86d23a090a40`).

## 8. Borderline conventions, decided in advance

32. Identity declarations ("a company developing X for Y") count as
    positive only when they name a direction the company is pursuing, not
    merely what it presently is.
33. Mission statements count as positive when they name a domain or
    action; generic uplift language without an object does not.
34. Aspirational language with no object ("we aim to create value") is
    `not_priority`.
35. A sentence naming both a strategic direction and routine detail is
    judged on the strategic clause and remains positive.
36. A strategic direction stated once and repeated verbatim in a later
    filing is positive in both, flagged with the repeat indicator, and the
    duplication is handled at the training-split stage rather than by the
    annotator (verified: design document A2.3, §36).
37. When the annotator cannot decide, the unit is marked `unsure` and
    excluded from both training and benchmark denominators until the rule
    is amended; `unsure` counts are themselves a measurement of definition
    stability.

## 9. Annotation unit and context

38. The unit is one `SEG-v1` segment, and the target text is stored
    separately from the displayed context (verified: handoff §§11, 20).
39. The annotator is shown the containing paragraph or nearest neighbours,
    because some strategic statements depend on an antecedent.
40. Judgement is made on the target sentence read in that context; the
    context is never itself labelled.

## 10. Recorded fields per annotation

41. `segment_id`, document and capture id, entity key, filing date,
    sentence index, verbatim target text, context span reference,
    `SP-ANNOT` version, label, categories if positive, flags
    (`malformed`, `not_verbatim`, `wrong_entity`, `repeat`), note,
    annotator, timestamp.
42. Every annotation is written to the immutable adjudication ledger
    delivered at R3-0d, and no annotation begins before that gate closes
    (verified: handoff §§10, 32).

## 11. Ratified rulings of 2026-09-12

43. **No proper name required.** A positive does not require a named
    disease, asset, modality or geography; it requires a discernible
    strategic object, direction, capability, market, portfolio action or
    strategic domain (operator ruling, design document A2.1).
44. "We intend to expand our commercial capabilities" qualifies; "we intend
    to grow our business" does not, lacking content sufficient to establish
    a meaningful strategic direction (same ruling).
45. **`financial` requires a deliberate direction.** Generic financing need,
    runway language, statements that additional capital may be required, and
    ordinary fundraising possibility are negative; prioritising
    acquisitions, debt reduction, repurchases, divestitures or another
    identifiable capital-allocation strategy can be positive (A2.2).
46. **Repetition does not demote.** Year-over-year repeated language stays
    positive in each filing if it still expresses a current strategic
    priority there; a repeat or boilerplate indicator is recorded
    separately, and leakage is handled by document-level and company-level
    splitting rather than by the annotator (A2.3).
47. Annotation begins only after R3-0d, when the immutable adjudication
    ledger exists (design document §17).
