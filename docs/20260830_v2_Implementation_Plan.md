docs/20260830_v2_Implementation_Plan.md

# Implementation plan and gate ledger

Bioindustry Intelligence Platform · v2 · 2026-08-30 (v2: ontology roadmap steps mapped; gates M1-G/H/I added) · Status: agreed in
principle 2026-08-30 ("all makes sense"); formal go per gate.
Target state: docs/20260830_v1_System_Diagram_TARGET_STATE.*.
Requirements: Ontology v3, FDA Catalyst Product Design v1, Horizon Scanning
Design v1. Rules: Design Principles v2 (P1–P15). Process: operating manual +
MACHINE_RUNBOOK v2.

## 1. How every gate proceeds (standing procedure)

1. Scope message: deliverable, files touched, entry criteria, exit
   criteria, what changes for the operator. Jason replies go / amend.
2. Build in the container; dry-run on a copy of the tree (manual, Code
   delivery format rule 2); unit tests where logic is added.
3. Delivery: single files with the deploy path on line 1; overwrite
   targets delivered under versioned download names (`NAME_vNNN.md`).
4. Run block: absolute paths, expected result per command, one block per
   turn; Jason pastes output.
5. Exit proof: regression hashes (`predict`, `pairs-full-exact`) unchanged
   unless the gate explicitly changes model output, in which case a new
   baseline is recorded with a ledger note; pytest passes; the gate's own
   exit criteria pasted.
6. Commit and push; PROJECT_STATUS changelog line; this ledger's status
   column updated; handoff updated at session end.
7. Any failure: one-line diagnosis with evidence, single next command,
   expected result. No gate advances on an unproven prior gate.

## 2. Gate ledger

Status: PLANNED · READY (entry criteria met) · IN PROGRESS · DONE (hash) · DEFERRED.

| Gate | Deliverable | Depends on | Entry criteria | Exit criteria (evidence) | Status |
|---|---|---|---|---|---|
| 0.1 | `schema.py` (entity types, attributes, event classes, allowed values, table map) + `validate` command | — | tree at latest docs commit, clean | `validate` reports every silver/gold table conformant or lists violations; 2+ unit tests; regression unchanged | PLANNED |
| 0.2 | Central reporting: `gold/results.csv` schema, `results.py` writer, `report <name> <date>` generator; existing report writers re-pointed | 0.1 | — | every existing report reproduced byte-identical from records or diff explained; `results.csv` has one row per historical report re-run; regression unchanged | PLANNED |
| 0.3 | Model framework: interface, registry, harness; five existing models wrapped | 0.1, 0.2 | — | `python -m biointel models` lists 5 models with declared inputs; harness reproduces ledger metrics for pairs-exact and gen-2 screen; regression unchanged | PLANNED |
| 1.4 (F1) | Event table schema + migration of `events.csv`; `calendar IID` as view | 0.1 | — | row count preserved; `study-all` and `predict` hashes unchanged; view prints trials + FDA + (empty) forward rows | PLANNED |
| 1.5 (F2) | EFTS probe; 8-K exhibit query set; date/asset parser; review queue | 1.4 | probe passes (documented endpoint behaviour, User-Agent, partitioning) | on a 90-day sample: ≥ N parsed forward events with source URLs; parse precision measured on a hand-checked sample; unparsed hits queued | PLANNED |
| 1.6 (F3) | FDA AdCom calendar pull; CT.gov primary-completion field; FDA CRL letters; EDGAR acceptance timestamps | 1.4 | probes pass | fields populated for the universe; counts reported; regression unchanged | PLANNED |
| 1.7 (F4) | `catalyst-calendar` daily job: mine, parse, close outcomes, reconcile vs pdufa.bio, change report, delay detection | 1.5, 1.6, 0.2 | — | two consecutive daily runs; change report lists added/changed/resolved/flagged; delays appear as events; report produced through 0.2 | PLANNED |
| 2.8 (F5) | Price-action attribute group (§3.2a) computed into the entity/attribute tables | 1.4, 0.1 | — | attributes present and dated for all listed entities; validate passes; regression unchanged | PLANNED |
| 2.9 (F9) | Global universe: ADR listings, home-market identifiers, stub rows; benchmarks table + price pulls (XBI, SPX, user baskets) | 0.1 | — | ADR entities ingest with prices; stubs load without breaking models; event study runs against ≥ 2 benchmarks | PLANNED |
| 2.10 (B) | Manual layer: `manual_entities`, `manual_attributes`, `manual_notes` (template), precedence, provenance, validation, load-time merge | 0.1 | — | a manual override is visible to a model with machine value retained; notes attach to entity and event; validate rejects a malformed row | PLANNED |
| 3.11 (F6) | M2.1 reaction magnitude, M2.2 run-up, M2.3 post-event path (incl. delay paths) under the framework; protocol pre-registered | 0.3, 1.7, 2.8 | thresholds written before first measurement | result records with metrics vs class-median and zero baselines; nulls reported | PLANNED |
| 3.12 (F7) | M2.4 crowding index, M2.5 outcome base rates, M2.6 peer spillover | 3.11 | — | as above | PLANNED |
| 3.13 (F8) | M2.7 daily ranking with attribution; rules R1–R8 parameterised and back-tested; `catalyst-daily`; daily report + CSVs | 3.12 | — | two consecutive daily runs; every ranked row carries attribution columns; rules report hit rate and drawdown | PLANNED |
| M1-O | Objective labels on historical deals; objective matchers O3–O8 as registered models | 0.3, 2.10 | after Phase 3 measured | per-objective metrics on held-out deals | DEFERRED |
| M1-P | `predict` composition decision (fitted screen ranks, scorecard explains) | 0.3 | decision by Jason + Harrison | new baseline recorded with ledger note | DEFERRED |
| M1-G | Modality and sector classification (10-K text, patents, manual) — ontology step G; also feeds Model 2 attribute "modality" | 0.1, 2.10 | after Phase 2 | classifier precision on a hand-checked sample; attribute populated for the universe | DEFERRED |
| M1-H | Financial matcher (O7) and fund entities — ontology step H | 0.3, 2.9, 2.10 | after Phase 3 | metrics on financial-buyer deals | DEFERRED |
| M1-I | Product-text similarity (O4, O8) from 10-K text — ontology step I | 0.3 | after Phase 3 | metrics on platform/horizontal deals | DEFERRED |
| M4-S1..S7 | Horizon Scanning per its design §8 | 0.1, 0.2, 2.9, 2.10 | after Phase 3 (S1 may start earlier) | extraction precision ≥ 0.9 on organisations before auto-stubs | DEFERRED |
| DOC | Current-state diagram and PROJECT_STATUS PART 0 regenerated after each phase | each phase | — | diagram and module map match the tree | recurring |

## 2a. Cross-reference: design roadmaps → gates

| Ontology v3 §7 | Gate | | Product Design §9 | Gate | | Horizon Scanning §8 | Gate |
|---|---|---|---|---|---|---|---|
| A schema + validate | 0.1 | | F1 event table | 1.4 | | S1 ingest two sources | M4-S1 |
| B manual layer | 2.10 | | F2 EFTS parser | 1.5 | | S2 extraction + resolution | M4-S2 |
| C registry generalised | 2.9 | | F3 official feeds | 1.6 | | S3 review queue + report | M4-S3 |
| D model framework | 0.3 | | F4 daily job | 1.7 | | S4 Form D / RePORTER / preprints | M4-S4 |
| E predict composition | M1-P | | F5 attributes | 2.8 | | S5 NER + relations | M4-S5 |
| F objective labels + O1–O3 | M1-O | | F6 M2.1–M2.3 | 3.11 | | S6 signals + watchlists | M4-S6 |
| G modality/sector | M1-G | | F7 M2.4–M2.6 | 3.12 | | S7 usefulness evaluation | M4-S7 |
| H financial matcher | M1-H | | F8 ranking, rules, report | 3.13 | | | |
| I product-text similarity | M1-I | | F9 benchmarks | 2.9 | | | |
Central reporting (0.2) has no design-roadmap row; it was added in the gameplan and is referenced by the Product Design R6 and Horizon Scanning H6.

## 3. Order of execution

Phase 0 (0.1 → 0.2 → 0.3) → Phase 1 (1.4 → 1.5 ∥ 1.6 → 1.7) → Phase 2
(2.8 ∥ 2.9 ∥ 2.10) → Phase 3 (3.11 → 3.12 → 3.13) → deferred items.
1.5/1.6 and the Phase 2 gates are independent of each other and may be
interleaved; nothing in Phase 3 starts before 1.7, 2.8 and 0.3 are DONE.

## 4. Standing items outside the gates

- Harrison: rotate the Alpha Vantage key; set the repository private.
- Pull request `jason/refactor` → `main` at a point both agree
  (recommended: after Phase 0, so Harrison's machine gets the layout,
  framework and reporting before the calendar work starts).
- Data snapshot policy (ontology §8.5) decided before Phase 3 measurement.
