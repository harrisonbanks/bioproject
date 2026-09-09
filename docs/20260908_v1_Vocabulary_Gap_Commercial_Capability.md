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
