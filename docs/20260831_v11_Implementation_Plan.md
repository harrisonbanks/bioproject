docs/20260831_v11_Implementation_Plan.md

# Implementation plan and gate ledger

Bioindustry Intelligence Platform · v11 · 2026-08-31 (v11: L1 rewritten to the approved file-room design, Ontology v5 §3.9; AI-over-store, Zotero-as-reader and video_dl recorded in §4 as deferred/policy items; v10: sequencing decided, §3; P19 Evidence binding for L1–L4 (Design Principles v5); order: L1 → 1.4 → L2 → 1.5 → L3 → L4, with 1.6, 1.7 and 2.9′ placed as they fall due; v9: dossier track L1–L4 and 2.9′ added per Ontology v4 §3.9–§3.10, §5.5–§5.7, §7; v8: data-snapshot policy decided, §4 and §5; v7: gate 0.4 DONE, Phase 0 complete; v6: gate 0.3 DONE; v5: gate 0.2 DONE; v4: Phase 0 reordered — storage migration to DuckDB as 0.2, reporting layer 0.3, model framework 0.4; legacy rule; thirteen-file regression baseline; v3: gate 0.1 DONE; v2: ontology roadmap steps mapped; gates M1-G/H/I added) · Status: agreed in
principle 2026-08-30 ("all makes sense"); formal go per gate.
Target state: docs/20260830_v1_System_Diagram_TARGET_STATE.*.
Requirements: Ontology v4, FDA Catalyst Product Design v1, Horizon Scanning
Design v1. Rules: Design Principles v4 (P1–P18). Process: operating manual +
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
| 0.1 | `schema.py` (entity types, attributes, event classes, allowed values, table map) + `validate` command; `config.py` de-duplicated with guard test (added to scope 2026-08-30) | — | tree at latest docs commit, clean | `validate` reports every silver/gold table conformant or lists violations; 2+ unit tests; regression unchanged | DONE 2026-08-30 (validate 17 conformant / 1 violations / 9 absent / 5 planned; pytest 37; regression 04061e33…530d, 960307e2…e81b; runbook docs/20260830_v1_GATE01_INSTALL.md) |
| 0.2 | Storage migration (P16, P18): `schema.py` creates all silver/gold/ledger tables in `data\biointel.duckdb` with typed columns, keys and allowed values as database constraints; every live read/write site re-pointed from CSV to DuckDB; `migrate` command loads the existing CSVs once; `freeze` snapshots the database file; `validate` checks the database; `ma_predictions.csv` and all report text written to `data\exports\`; legacy code untouched on CSV | 0.1 | thirteen-file regression baseline recorded with current code (§5); decisions committed | `migrate` row counts equal the CSV counts; all live commands run against DuckDB; all thirteen fingerprints match; `validate` all conformant; pytest passes | DONE 2026-08-30 (migrate 19 tables, counts equal; validate 19/0/8/5; pytest 46; thirteen fingerprints True; runbook docs/20260830_v1_GATE02_INSTALL.md) |
| 0.3 | Reporting layer (P17): ledger tables `runs`, `run_params`, `run_metrics`, `run_artefacts` in DuckDB (MLflow structure); `results.py` record/render; every live report writer re-pointed; `report <model> <date>`; legacy reports entered as `historical-file` rows with fingerprint and commit 880da16 | 0.2 | 0.2 DONE | seven live reports byte-identical to baseline; one `runs` row per live re-run and per legacy file; fingerprints match | DONE 2026-08-30 (ledger-seed 7 rows; 7 runs recorded; thirteen fingerprints True before and after render-from-record; ledger 14 runs; validate 23/0/8/5; pytest 58; runbook docs/20260830_v1_GATE03_INSTALL.md) |
| 0.4 | Model framework: interface, registry, harness; five existing models wrapped | 0.2, 0.3 | 0.2, 0.3 DONE | `python -m biointel models` lists the live models with declared inputs; harness reproduces ledger metrics for pairs-exact and gen-2 screen; regression unchanged | DONE 2026-08-31 (models: 3 models / 5 impl / 6 eval; enforcement live on every routed command; thirteen fingerprints True; ledger 24 runs; pytest 65; runbook docs/20260831_v1_GATE04_INSTALL.md) |
| 1.4 (F1) | Event table schema + migration of `events.csv`; `calendar IID` as view | 0.2 | — | row count preserved; `study-all` and `predict` hashes unchanged; view prints trials + FDA + (empty) forward rows | PLANNED |
| 1.5 (F2) | EFTS probe; 8-K exhibit query set; date/asset parser; review queue | 1.4 | probe passes (documented endpoint behaviour, User-Agent, partitioning) | on a 90-day sample: ≥ N parsed forward events with source URLs; parse precision measured on a hand-checked sample; unparsed hits queued | PLANNED |
| 1.6 (F3) | FDA AdCom calendar pull; CT.gov primary-completion field; FDA CRL letters; EDGAR acceptance timestamps | 1.4 | probes pass | fields populated for the universe; counts reported; regression unchanged | PLANNED |
| 1.7 (F4) | `catalyst-calendar` daily job: mine, parse, close outcomes, reconcile vs pdufa.bio, change report, delay detection | 1.5, 1.6, 0.3 | — | two consecutive daily runs; change report lists added/changed/resolved/flagged; delays appear as events; report produced through 0.2 | PLANNED |
| 2.8 (F5) | Price-action attribute group (§3.2a) computed into the entity/attribute tables | 1.4, 0.2 | — | attributes present and dated for all listed entities; validate passes; regression unchanged | PLANNED |
| 2.9 (F9) | Global universe: ADR listings, home-market identifiers, stub rows; benchmarks table + price pulls (XBI, SPX, user baskets) | 0.2 | — | ADR entities ingest with prices; stubs load without breaking models; event study runs against ≥ 2 benchmarks | PLANNED |
| 2.10 (B) | Manual layer: `manual_entities`, `manual_attributes`, `manual_notes` (template), precedence, provenance, validation, load-time merge | 0.2 | — | a manual override is visible to a model with machine value retained; notes attach to entity and event; validate rejects a malformed row | PLANNED |
| 3.11 (F6) | M2.1 reaction magnitude, M2.2 run-up, M2.3 post-event path (incl. delay paths) under the framework; protocol pre-registered | 0.4, 1.7, 2.8 | thresholds written before first measurement | result records with metrics vs class-median and zero baselines; nulls reported | PLANNED |
| 3.12 (F7) | M2.4 crowding index, M2.5 outcome base rates, M2.6 peer spillover | 3.11 | — | as above | PLANNED |
| 3.13 (F8) | M2.7 daily ranking with attribution; rules R1–R8 parameterised and back-tested; `catalyst-daily`; daily report + CSVs | 3.12 | — | two consecutive daily runs; every ranked row carries attribution columns; rules report hit rate and drawdown | PLANNED |
| M1-O | Objective labels on historical deals; objective matchers O3–O8 as registered models | 0.4, 2.10 | after Phase 3 measured | per-objective metrics on held-out deals | DEFERRED |
| M1-P | `predict` composition decision (fitted screen ranks, scorecard explains) | 0.4 | decision by Jason + Harrison | new baseline recorded with ledger note | DEFERRED |
| M1-G | Modality and sector classification (10-K text, patents, manual) — ontology step G; also feeds Model 2 attribute "modality" | 0.2, 2.10 | after Phase 2 | classifier precision on a hand-checked sample; attribute populated for the universe | DEFERRED |
| M1-H | Financial matcher (O7) and fund entities — ontology step H | 0.4, 2.9, 2.10 | after Phase 3 | metrics on financial-buyer deals | DEFERRED |
| M1-I | Product-text similarity (O4, O8) from 10-K text — ontology step I | 0.4 | after Phase 3 | metrics on platform/horizontal deals | DEFERRED |
| M4-S1..S7 | Horizon Scanning per its design §8 | 0.2, 0.3, 2.9, 2.10 | after Phase 3 (S1 may start earlier) | extraction precision ≥ 0.9 on organisations before auto-stubs | DEFERRED |
| L1 | Research library / file room (Ontology v5 §3.9, approved 2026-08-31; NEXT GATE per §3 order): `references`, `captures`, `reference_links` in `schema.py`; content-addressed store `data\bronze\library\<aa>\<sha256>.<ext>`; collectors manual, folder, pipeline, zotero (optional extra, skipped when absent); commands add (incl. --no-fetch, --for), import, import-zotero, find, show, open, list, view, site, manifest, merge, verify, dedupe, retire-capture; the 733 sec_filing_doc filings copied in as references+captures; every import a ledger run; `validate` covers the three tables | 0.2 | scope go | index of the 733 filings idempotent (second run adds 0); one URL add, one file add, one --no-fetch reference, one retire-capture and one dedupe-merge each behave as §3.9 specifies; manifest+verify pass on the store; `validate` conformant; pytest and ruff clean; fingerprints unchanged | PLANNED |
| L2 | Dossier schema (Ontology v4 §3.10: `deal_terms`, `deal_timeline`, `deal_rationale`, `deal_aspects`, `deal_comparables`) and entity attributes (`equity_stakes`, `stated_priorities`, `assets`; typed edges; v4 event classes) declared in `schema.py`; `ma_events` gains `deal_id` | L1, 2.10 | L1 DONE; manual layer available for corrections | tables created empty and conformant; one hand-entered dossier (Tempus–Personalis) loads through the manual layer with every field carrying `doc_id`; fingerprints unchanged | PLANNED |
| L3 | EDGAR full-text search adapter (shared with gate 1.5) and deal analyser v1 (Ontology v4 §5.7) over the 447 existing target-role events; review queue; aspect vocabulary as code | L2 | EFTS probe passes | dossiers for ≥ 90% of the 447 events with terms and at least one rationale statement each; precision of stated-reason and aspect extraction measured on a hand-checked sample of ≥ 60 dossiers and recorded in the ledger; fingerprints unchanged (dossiers are new tables) | PLANNED |
| L4 | `aspect-match` implementation under `acquirer-pairing` (Ontology v4 §5.5) and the forward hit/false-alarm test (§5.6); pass mark written in the scope message | L3, 0.4 | L3 precision accepted | hits and false alarms per buyer-year against chance in a ledger record; `predict` unchanged until a separate composition decision | PLANNED |
| 2.9′ | Universe widened to diagnostics, tools and data companies (SIC set to be decided; Tempus and Personalis are the test cases); private targets as stub entities; new regression baseline recorded with a ledger note | L2 | check on the operator machine whether Tempus and Personalis are among the 1,379 members | new member count reported; all live commands run; thirteen fingerprints re-baselined with a ledger note (§1 step 5) | PLANNED |
| DOC | Current-state diagram and PROJECT_STATUS PART 0 regenerated after each phase | each phase | — | diagram and module map match the tree | recurring |

## 2a. Cross-reference: design roadmaps → gates

| Ontology v3 §7 | Gate | | Product Design §9 | Gate | | Horizon Scanning §8 | Gate |
|---|---|---|---|---|---|---|---|
| A schema + validate | 0.1 | | F1 event table | 1.4 | | S1 ingest two sources | M4-S1 |
| B manual layer | 2.10 | | F2 EFTS parser | 1.5 | | S2 extraction + resolution | M4-S2 |
| C registry generalised | 2.9 | | F3 official feeds | 1.6 | | S3 review queue + report | M4-S3 |
| D model framework | 0.4 | | F4 daily job | 1.7 | | S4 Form D / RePORTER / preprints | M4-S4 |
| E predict composition | M1-P | | F5 attributes | 2.8 | | S5 NER + relations | M4-S5 |
| F objective labels + O1–O3 | M1-O | | F6 M2.1–M2.3 | 3.11 | | S6 signals + watchlists | M4-S6 |
| G modality/sector | M1-G | | F7 M2.4–M2.6 | 3.12 | | S7 usefulness evaluation | M4-S7 |
| H financial matcher | M1-H | | F8 ranking, rules, report | 3.13 | | | |
| I product-text similarity | M1-I | | F9 benchmarks | 2.9 | | | |
| L1–L4 research library, dossier, analyser, aspect matcher (Ontology v4 §7) | L1–L4 | | | | | | |
| 2.9′ universe widening and stubs (Ontology v4 §7) | 2.9′ | | | | | | |
Storage migration (0.2) and central reporting (0.3) have no design-roadmap row; it was added in the gameplan and is referenced by the Product Design R6 and Horizon Scanning H6.

## 3. Order of execution

Phase 0 (0.1 → 0.2 → 0.3 → 0.4, all DONE 2026-08-31) → Phase 1 (1.4 → 1.5 ∥ 1.6 → 1.7) → Phase 2
(2.8 ∥ 2.9 ∥ 2.10) → Phase 3 (3.11 → 3.12 → 3.13) → deferred items.
1.5/1.6 and the Phase 2 gates are independent of each other and may be
interleaved; nothing in Phase 3 starts before 1.7, 2.8 and 0.4 are DONE.
Order of record (decided 2026-08-31, Ontology v4 §8 Q8 answered):
L1 → 1.4 → L2 → 1.5 → L3 → L4, with 1.6, 1.7 and 2.9′ placed as they fall due. Reasons: L1 touches no
fingerprint and both tracks need it; L2 writes its event classes to the
table 1.4 creates, so 1.4 precedes L2; L3 needs the EDGAR full-text
adapter that 1.5 builds, so 1.5 precedes L3. Next gate: L1.

## 4. Standing items outside the gates

- Deferred from gate 0.1, absorbed by the named gate: typed edge columns `type`, `date`, `source` on `relationships.csv` (declared as optional in schema.py) → 2.10; `silver/prices.csv` declared in config.py with no writer → the first gate that needs it (1.4 or 2.8); harvest-derived `ma_events.csv` rows carry blank S1–S5 signal columns (labels.merged_events) → the first gate that edits labels.py; `scripts/refactor/50_config_logging.py` lint/format findings → left as refactor tooling.

- Harrison: rotate the Alpha Vantage key; set the repository private.
- Pull request `jason/refactor` → `main` at a point both agree
  (recommended: after Phase 0, so Harrison's machine gets the layout,
  framework and reporting before the calendar work starts).
- Deferred (recorded 2026-08-31, Ontology v5 §3.9/§7): AI-over-store MCP server after L3; Zotero-as-reader export after two verifications (link-not-copy on import; duplicate-safe re-import); `video_dl` collector defined, off by default, run deliberately per reference.
- Universe check before 2.9′ is scoped: whether Tempus AI and Personalis are among the 1,379 members (one query on the operator machine); if not, 2.9′ precedes L3 for the lead example (Ontology v4 §8 Q9).
- Data snapshot policy (Ontology §8 Q5): DECIDED 2026-08-31, option A. The snapshot of record from Phase 1 onward is Jason's 2026-08-29 data, frozen as it stood on 2026-08-31: `data\snapshots\20260831\biointel.duckdb`, 95,170,560 bytes, SHA-256 `B93A833BE46667AD402C71776C41D5E34EF1AC2126A73138D24C74D3928C0E65`; `manifest.json` 12,053 fetches, no credential. It reaches Harrison on a USB drive after the merge, never through git; identity by SHA-256 and by equal `data_snapshot_hash` in `report runs`. Harrison's 2026-08-25/26 results stay `historical-file` ledger rows labelled with the earlier snapshot; the paper states that in one sentence. No `ingest`, `labels`, `features`, `study-all`, `text-ingest` or `cparty-all` runs outside a named gate that records a new baseline with a ledger note (§1 step 5).

## 5. Regression baseline (decision 2026-08-30)

Thirteen fingerprints, recorded in `docs/regression_baseline.txt` on 2026-08-30 at
commit dc7465c, replace the two-file baseline from gate 0.2 onward: `ma_predictions.csv`
plus six live report files regenerated by the current code on Jason's snapshot
(`pair_full_exact_report.txt`, `robustness_report.txt`, `improve_report.txt`,
`pair_exact_report.txt`, `development_report.txt`, `tuning_report.txt`;
`text_sweep_report.txt` is absent because no 10-K text corpus exists on that machine
and stays absent), and six legacy report files copied unchanged from Harrison's
machine (`fit_report.txt`, `holdout_report.txt`, `pair_report.txt`,
`pair_supervised_report.txt`, `pair_protocol_report.txt`, `pair_substrate_report.txt`),
never regenerated. Every gate from 0.2 must reproduce each of the thirteen byte for
byte. Note: the live-report numbers on Jason's snapshot differ from the ledger numbers
recorded from Harrison's snapshot (e.g. development best 0.0561/1.87× vs 0.0674/2.13×);
the data-snapshot policy was decided on 2026-08-31 (§4): the live-report numbers on Jason's snapshot are the numbers of record; Harrison's are historical.

## 6. Legacy register (P7 as amended 2026-08-30)

`src/biointel/baselines.py` (whole module: `pairs`, `pairs-fit`, `pairs-protocol`,
`pairs-substrate`), `improve.holdout` (both holdout accesses spent, P10), `fit.fit`
(gen-1 screen). Kept and marked `LEGACY`, not re-pointed to DuckDB or the reporting
layer, not re-run, removed at a cleanup gate named when Phase 3 is measured.

## 7. Model naming (decision 2026-08-31)

Models are named by the question they answer: `target-screen` (which
companies will be acquired in the next 12 months; implementations
`scorecard`, `fitted`), `acquirer-pairing` (for a given target, which buyer;
implementation `mass-exact`), `fda-event-study` (how a stock moves around an
FDA decision; implementation `daily-bars`). Evaluations are runs of a model,
not models. The labels "M1"/"M2" are retired from new code and documents and
remain only in the historical record. Model 4 joins later as
`entity-discovery`.

