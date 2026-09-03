# docs/20260903_v1_GATEF2_SCOPE.md

# Gate F2 scope — stated priorities and deal aspects (analyser rule version L3-a3)

Bioindustry Intelligence Platform · 2026-09-03 · scope closed on five decisions
taken one at a time (2026-09-03); build does not begin until F1 closes and the
operator gives an explicit go. Binding spec: Data-Feeder Roadmap §F2
(69bca93, amended b7f6cb5).

## 1. What F2 produces, in plain terms
Two tables the matcher currently reads as empty:
1. **`stated_priorities`** — sentences in which a company says what it wants to
   buy or build ("we are looking for late-stage oncology assets"), with who
   said it, when, which category, the exact sentence, and the document.
2. **`deal_aspects`** — for each historical deal with a resolvable acquirer,
   which of the 15 aspect-vocabulary tags applied, with the sentence that
   proves it.

Together they supply the substrate the L4 coverage metrics showed missing:
`buyer_stated_priority_match` and the stated aspects were evaluable at zero in
every L4 run. The aspect-match v2 re-test is blocked until this gate and F1
both close.

## 2. Decisions of record (closed 2026-09-03)
| # | Decision | Ruling |
|---|---|---|
| Q1 | Sources for stated priorities | **All three**: earnings-call transcripts filed as 8-K exhibits; 10-K Item 1 (Business/strategy) sections; investor-day presentations filed as 8-K exhibits. Every row tagged by source type and document section; precision measured per tier; the matcher's input list is set by those measurements, not by prediction. Rationale: excluding 10-Ks leaves every buyer who never files transcripts with no priorities at all — a coverage hole by construction. The L3 finding (0.625 on deal 8-Ks/proxies, 0.456 with 10-K risk boilerplate) makes this a filtering problem, solved by section-level guards and per-tier measurement |
| Q2 | Table change | Two optional columns on `stated_priorities`: `source_type` (`earnings_call` / `10k_strategy` / `investor_day`) and `section`. SCHEMA_VERSION 0.11 → 0.12 |
| Q3 | Category vocabulary | One shared, fixed enum used by both `stated_priorities.category` and `assets.category`, defined in `schema.py` before the probe, covering P4's objective dimensions (pipeline gap, therapeutic area, mechanism/modality, platform, data, geography, financial, defensive) with therapeutic areas as sub-values. Fixed for the gate; changing it mid-gate invalidates the precision measurement |
| Q4 | Which deals get aspect-tagged | **Option 2**: collect documents for every deal with a resolvable acquirer (~129, the same resolution the pairing protocol uses), then tag. Tagging only the 11 already in hand would leave the matcher scored against deals whose aspects were never read |
| Q5 | Measurement | Stated priorities: unit = one extracted sentence; passes only if company, date, category and sentence are all correct; **60 per source tier** (180 total), Wilson interval per tier, extendable under the same rule version. Deal aspects: unit = one deal-aspect tag; passes only if the cited sentence supports the aspect for that deal; 60 tags. Both through `judge`; judged-wrong rows never written (verdict-gated consume, unchanged from L3). Sample size is a command parameter, never hard-coded |

## 3. Deliverables
1. `analyser.py` rule version **L3-a3**: the a3 agenda of record (doc-type
   guards for rationale/price rules; two-tier and reverse termination-fee
   fields; termination-floor rule; price-context guard; ticker-less
   `deal_id` fix) plus two new rule families — stated-priority sentences and
   deal-aspect evidence. Section-level doc-type guard: in a 10-K, Item 1
   Business is strategy; Item 1A Risk Factors is legal hedging and is
   excluded from priority rules.
2. Collection: the three source types via the existing EFTS stack;
   deal documents for the ~129 resolvable deals via the L3 collector.
   Capture-first (rule 4.20): a probe block captures real specimens of each
   source type before any rule is written.
3. `schema.py`: Q2 columns, Q3 enum, SCHEMA_VERSION 0.12.
4. Tests: every rule locked against verbatim specimens (the F1 pattern);
   the enum asserted fixed.
5. CLI: collection and measurement commands under the analyser family.

## 4. Files touched
`analyser.py`, `schema.py`, `tests/unit/test_analyser.py`, `interfaces/cli.py`
if a collection command is added. No model file. `pairs.py`, `labels.py`,
`forward.py`, `aspects.py` untouched; `efts.py` beyond F1's judge branch only
if a source-type tag must ride on the review row.

## 5. Order of operations
1. Probe: capture specimens of each source type (earnings-call exhibit, 10-K
   Item 1, investor-day exhibit) and of a deal 8-K; operator attaches the
   bundle; rules are written against it.
2. Enum and columns land with the first rule delivery.
3. Collect all three sources across the universe (interruption-safe; the
   offline analyzer pattern from F1 runs alongside to measure per-tier parse
   rates while collection is in flight).
4. Collect deal documents for the ~129 resolvable deals.
5. Propose → span-verify → blind samples (180 + 60) → judge → precision per
   tier → consume.
6. Fingerprints, docs, commit.

## 6. Exit criteria (roadmap §F2 item 4, plus settled proofs)
1. `stated_priorities` > 0 across many buyers; coverage per tier recorded as
   run metrics (buyers with ≥1 row, per source type).
2. `deal_aspects` populated across the resolvable-deal set; coverage
   recorded (deals with ≥1 tag).
3. Precision recorded per tier at rule L3-a3 with Wilson intervals; the
   matcher's input tiers named from those numbers.
4. Thirteen fingerprints MATCH under the settled loop; untouched-surface
   diff over the model files empty.
5. Evidence to one file per block, rule 4.21.

## 7. Standing rules that bind this gate
No numeric constant without a source line (PROJECT_STATUS 1.11). Record to
the analyst's standard, not to what today's code consumes. Unique dated
download names with a verify line before every commit. Specimens into tests
verbatim, never abbreviated. Analysis tooling ships with any long-running
step.

## 8. Not in scope, named
Expert-hypothesis store (own gate; order relative to F2 undecided). Aspect
weights (own gate, own pre-registration). Aspect-match v2 (blocked on F1 +
F2). `store` extension and `references` rename (own gates).
