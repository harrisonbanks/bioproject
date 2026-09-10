# docs/20260908_v1_Vocabulary_Gap_Commercial_Capability.md

# Decision record: the commercial-capability vocabulary gap (F2, 2026-09-08)

## Finding (operator, during the F2 blind-sample adjudication)
Building out channels, delivery networks, market access, payer models and
commercial reach is among the MOST COMMON stated corporate priorities in
the collected corpus — and the fixed 8-value category vocabulary
(PRIORITY_CATEGORIES, Q3 of the F2 scope, sourced from P4's objective
dimensions) has no value that holds it:
- `geography` covers only the where, not the capability;
- `financial` covers only the returns motive;
- `platform` means technology, and stamping commercial networks as
  platform was a live mislabel (Viatris row, judged wrong 2026-09-08).

Evidence from one 120-row sample alone: Viatris (Global Healthcare
Gateway), bluebird (delivery network / value-based payment), Travere
(commercial execution), ARS (neffy access), BioCryst (ORLADEYO access).
Five of 120 — the single most frequent unlabelable theme in the sample.

## Ruling of record
1. A ninth category, working name `commercial_capability`, is APPROVED IN
   PRINCIPLE by the operator (2026-09-08) and enters the vocabulary at the
   next legal moment: the deal-aspects half of F2, where assets.category
   joins the enum and a rule-version bump with fresh per-tier measurement
   is already scheduled. It does NOT enter mid-measurement: the sealed
   L3-a3-p1 precision numbers are measurements of the stamps that existed,
   and mid-stream vocabulary edits would invalidate them (Q3's own terms).
2. Until then, commercial-capability sentences carrying any other stamp
   are judged `wrong` (mislabeled is mislabeled), and every such
   retirement is EVIDENCE for the new category, listed here.
3. When the category lands: extraction rules for it are written from
   these retired specimens (capture-first, rule 4.20), and the matcher
   gains the commercial-synergy dimension the operator identified as
   strategically central.

## Standing list of retired commercial-capability specimens
- S164691c348181724 Viatris 2023 (stamped platform)
- Sb4b99e06dcaba9d2 bluebird 2019 (stamped therapeutic_area)
- Sac12ebd781f0704a Travere 2025 (stamped therapeutic_area)
- Sd8101a43fd461c58 ARS 2024 (stamped therapeutic_area)
- S1a5ff2eb8465d80e BioCryst 2021 (stamped therapeutic_area)
(extend as further rows retire on this ground)

## Appended 2026-09-09 (operator-approved commercial holds from the v2 triage surface)
Held `unsure` at L3-a3-p1 via cluster pipeline_gap--commercial-hold-p2
(reviewer=operator-pattern); each carries genuine channel/access language and
enters the extraction-rule specimen set when `commercial_infrastructure` lands
at p2:
- S0671b187e69a2448 (stamped pipeline_gap): "seeking partners with suitable infrastructure, expertise and a long-term initiative in our medical f..."
- S0d8ac69ec0679910 (stamped pipeline_gap): "seeking partners with commercial reach and experience in pain management in their respective regions..."
- S10aee1ec7089d5d9 (stamped pipeline_gap): "seeking partners with suitable infrastructure, expertise and a long-term initiative in our medical f..."
- S10d848546c9db34e (stamped pipeline_gap): "seeking partners with suitable infrastructure, expertise and a long-term initiative in our medical f..."

Also banked here (p2 negation/sentence-start specimen, operator override
2026-09-09): S02a95e01d937cb32 — "we seek to acquire carry on business; and
[bullet] our inability to generate revenue from acquired technology..." —
garbled truncation of risk-factor text, judged wrong; the slicer's
sentence-start capture must refuse bullet debris.

## Appended 2026-09-09, second batch (final v2 surface + residual, operator rulings)
Commercial-infrastructure holds (unsure at L3-a3-p1, banked for p2 rules):
- S16d531edd84b7a06 (stamped therapeutic_area): "Our strategy is to leverage our strong scientific and clinical expertise and global commercial infrastructure..."
- S223b1b984d92b3bf (stamped therapeutic_area): same leverage-commercial-infrastructure family
- S330db4c88981e03b (stamped therapeutic_area): same family, "...to maximize v[alue]"
- S124cac20372c3ad5 (residual, Mylan/Viatris class): Brazil market-access "platform" — commercial-infrastructure hold

p2 negation/sentence-start specimens (banked):
- S1e6a836b015eca6c (Opus-class negation clip): "we plan to acquire, the infrastructure or capability internally to manufacture..." — slicer inverted a negated acquire; validator now routes the pattern to garbled (verbatim test in tests/unit/test_priorities.py).

p2 successor-name / wrong-entity evidence (attribution class, from the residual):
- S0dfdb38f1ca4d458 — AgeX text on Serina's row
- S11c5f23183045644 — AVROBIO text on another company's row

## Appended 2026-09-10 (corpus completion — final holds, misquote diffs, attribution pile)
Commercial-infrastructure holds (unsure at L3-a3-p1, reviewer noted per row):
- S13ec6c24b1171518: Phexxi telehealth-supported sales strategy (channel decision)
- S3402b7d828477926: Brazil local platform, $22B market access (Mylan/Viatris class)
- S75578fa53bedb528: Brazil family, same CIK as S124cac/S3402
- S77945fd78818bc2b: "partners with suitable infrastructure" round-1 family
- S9332133e6abeb05a: Brazil local-platform family, CIK 1623613 ("build upon this local platform ... access the $13.")
- Sa5221e6ba16abe1b / Sc4dce91dee07f2ef: build-vs-partner commercialization, same sentence two years running ("develop, manufacture, and commercialize at least some of these programs on our own, although we may selectively consider partnerships...")

p2 slicer-misquote specimens (verdict wrong; Sonnet's text-vs-filing diffs quoted as evidence):
- Sa0aafbb3410df2a5 — extracted: "focused on discovering, acquiring, developing and commercializing therapeutic medicines for patients suffering from debilitating diseases with significant unmet medical need." Sonnet: "The excerpt's actual sentence reads 'for patients with significant unmet medical need,' not 'for patients suffering from debilitating diseases with significant unmet medical need,' so the quoted sentence does not match." (Clean 2022 sibling S8f61eee0 ruled correct separately — per-document defect.)
- Sde5e86d23a090a40 — extracted: "we aim to act with greater speed and to provide better potential upside when compared to the companies or spin-out startups to whom the institution might also consider licensing." Sonnet: "does not match the excerpt's actual text ('pharmaceutical companies or venture-backed biotechnology compa[nies]')."

p2 attribution / successor-name evidence pile (all judged wrong; company field is a Q5 field, attribution defeats any content reading including Nomad):
- S0dfdb38f1ca4d458, S2d111415c3789845, Sc90440210f0b31a6 — AgeX text on Serina rows
- S11c5f23183045644, Sa0e08f5306e2e39e — AVROBIO text on other companies' rows
- S69de997e7bae4081 — Histogenics/NeoCart text on Ocugen row
- S6fc257b2b1240545 — Silverback text on ARS row
- Sb1c5cc5d02128429, Sb945a972c2a55151 — Zeltiq description on Allergan rows
- Sa4d0c5939efea34a, Sc9e9bd0c66bd2a09, Sd944f8d5698203a8 — Sesen/Vicinium content on Carisma CIK ("seeking partners for a combination program"; the same sentence stands correct under Nomad at S5bc77f where no mismatch exists)
- S9fadedf2bc6e87e1 — subsidiary (NTWO) agricultural text on Nexentis row
