docs/20260831_v5_Design_Principles.md

# Design principles — Bioindustry Intelligence Platform (v5, 2026-08-31; supersedes v4 of 2026-08-30 by appending P19)

Binding for every session. Loaded at session start with the handoff. Each
principle records the decision, its date, and the reason it was taken.
Decisions here override any generic rule in any other document.

## P1. Data tables are model-agnostic (2026-08-30)
Every silver and gold table is an attribute store keyed by entity (and
period where applicable). No table is shaped for, named after, or
restricted to a model. Any current or future model may read any table.
Reason: the 2026-08-29 proposal to split the feature panel by model was
rejected; it would have tied storage to one model's rules.

## P2. Model separation is enforced at the model's input list (2026-08-30)
The rule "the M&A model must not use price-derived or event-reaction
features" is a rule about what a fitted model is trained on, because
missing prices for delisted firms leaked the outcome (the retracted 6.2×
result). It is enforced by each model declaring the columns it reads and
the harness checking that declaration. It is not enforced by removing
columns from tables. A hand scorecard is not trained on anything and may
read any attribute; the paper must describe its inputs.

## P3. Entities are neutral bundles of attributes and relationships (2026-08-30)
A company, a private biotech, a fund, or any other actor is one entity
type in one registry with a `listed` flag and a `type` field. Attributes
(what it develops, modality, sector, financials, stage, geography,
relationships) are stored once and used by any matcher. See the Ontology
and Matching Design document.

## P4. Acquisition objectives are a dimension, not a property of a model (2026-08-30)
Hunters have heterogeneous goals (pipeline gap, therapeutic deepening,
mechanism or modality, platform, data, geography, financial, defensive).
Objectives are a maintained list; a matching run is hunter × objective ×
candidate set; each objective has its own matcher and its own evaluation
labels. `predict` is a composition over objectives, not a single score.

## P5. Manual input is a general layer over all entities and attributes (2026-08-30)
One manual table can add entities (private biotechs, funds), add or
correct any attribute of any entity, and record hunter objectives and
flags. Every manual value carries source, entered-by, entered-on, and
overrides the machine value per attribute while the machine value is
retained. Applied at load, before any model reads. It is not merely a
"curated source for private companies".

## P6. Every model has the same shape and the same yardstick (2026-08-30)
Models implement one interface (name, declared inputs, fit, score),
register themselves, and are evaluated by one harness under the
pre-registered protocol (same events, same sampled negatives, mean rank,
Hits@k, lift) that writes one standard result record. The ledger is
generated from result records, not copied by hand.

## P7. Existing models keep their purposes (2026-08-30)
Scorecard (`score.py`): transparent, auditable rating — to be measured,
not assumed. Fitted screen (`improve.py`): best accuracy, validated 2.2×.
Gen-1 screen (`fit.py`) and rejected engines (`baselines.py`): frozen
paper baselines. Pairing engine (`pairs.py`): buyer-specific fit,
validated HR@10 0.27. Event study (`study.py`): Model 2, independent.
Open decision: which screen drives `predict` (recommendation: fitted
screen ranks, scorecard explains).
Amendment (2026-08-30): finished measurements whose code will not run in
the target design (`baselines.py`, `improve.holdout`, gen-1 `fit`) are
legacy: kept in the tree and marked `LEGACY`, never re-pointed to new
storage or reporting, never re-run, listed in the Implementation Plan
legacy register, removed at a named cleanup gate. Their reports enter the
ledger as `historical-file` rows carrying the file fingerprint and the
commit that produced them. Reason: no maintenance of code that will not
run again; the code stays available to diagnose a baseline mismatch.

## P8. Requirements are stated as the general case first (2026-08-30)
Examples are instances of a requirement, not the requirement. Before any
design answer the assistant restates: general case, instances given,
derived requirements, and asks when scope is unclear. Reason: two
narrow-reading errors on 2026-08-29/30 (table split; manual layer).

## P9. No refactor for its own sake (2026-08-29)
No file splits by line count, no domain/services/adapters layering, no
mypy --strict, no uv. venv + pip, ruff for lint and format, pytest for
unit tests, regression hashes for behaviour. Industry practice, not
invented rules. The 2026-08-29 Architecture Instructions are superseded.

## P10. Results are accepted by pre-registered rule, never by judgement (standing)
Both holdout accesses are spent. Substrate and engine comparisons use
identical events and shared sampled negatives. Implausibly strong results
are quarantined and audited before adoption.

## P11. Free public data first; manual second; paid never (standing)
SEC EDGAR (incl. Form D for private raises), ClinicalTrials.gov, openFDA,
Orange Book, ChEMBL, BigQuery patents, Yahoo prices. Manual layer fills
what public data cannot. No vendor feeds.

## P12. Every claim of done carries pasted evidence (standing)
Commands are absolute-path, annotated with expected results, one block
per turn; regression hashes prove behaviour unchanged; output drops in
pasted terminals are known and never treated as proof either way.

## P13. Calendar sources of record are official, free and machine-accessible (2026-08-30)
Past decisions from the FDA (Drugs@FDA, CRL endpoint, CRL letters);
forward goal dates from sponsor 8-Ks and press exhibits via the SEC EDGAR
full-text search endpoint; advisory committees from the FDA calendar;
readout windows from ClinicalTrials.gov. Aggregator calendars are
cross-checks, never the feed. Every event row links to its source
document.

## P14. Daily bars only; no intraday; no trade automation (2026-08-30)
Model 2 forecasts run-up and post-event paths from daily closes. The
system never trades and never uses intraday data. Positions and exits are
human decisions outside the system.

## P15. Global universe, stub entities, configurable benchmarks (2026-08-30)
Any jurisdiction with a US-traded line (ADRs included), no size or
liquidity floor; entities without market data exist as stubs filled by
the manual layer; abnormal returns are measured against XBI by default
and any user-defined benchmark side by side. Rankings across competing
events carry full attribution and assume nothing about the reader's
purpose or instruments.

## P16. Two data stores: raw files and one DuckDB file (2026-08-30)
`data/bronze/` holds raw API responses and documents exactly as received,
with manifests, never edited. Every silver, gold and ledger table lives in
one embedded DuckDB database, `data/biointel.duckdb`; `schema.py` defines
the tables and the database enforces types, keys and allowed values.
Reports and CSVs the paper or the regression baseline need are exports
under `data/exports/`, never read back; `freeze` copies the database file
to `data/snapshots/`. No other store (no SQLite, no MLflow, no CSV read by
live code once migration completes). Reason: DuckDB is the established
embedded engine for analytical work at this scale, reads the existing CSVs
directly, types columns strictly, and keeps the whole platform in two
places instead of four.

## P17. One run ledger in MLflow's structure, without MLflow (2026-08-30)
Every model run writes one row to `runs` (run id, model, version, command,
time, duration, status, operator, code commit, environment hash, data
snapshot hash, declared inputs, objective, holdout access flag, source =
run or historical-file) with rows in `run_params`, `run_metrics` and
`run_artefacts` (path and fingerprint of every file written, including the
rendered report). Every human-readable report is rendered from its record.
The structure copies MLflow's run record so the ledger can be exported to
MLflow later; the software is not adopted, to avoid a third store.

## P18. One store layer; set operations converge to SQL, modelling stays in Python (2026-08-30)
Every table read or write in live code goes through `store.read_table` /
`store.write_table`; no module opens a data file itself. Target computation
style: set operations (joins, group-bys, as-of lookups, window functions)
belong in SQL inside DuckDB; model fitting, scoring and statistics stay in
Python on the result rows; no module mixes the two styles for the same
operation. Convergence rule: a module's set operations move to SQL only in a
gate that touches that module for its own reason, each move proved against
the fingerprint baseline; nothing is rewritten speculatively (P9). Gate 0.2
stored values as text with the declared types, allowed values and keys
enforced as database constraints; typed reads (`typed=True`) are for new code
and for modules as they converge. Legacy code (P7) never converges.

## P19. Evidence (2026-08-31)
Every fact in a deal dossier, every stated priority, equity stake, asset
attribute and every event class introduced at Ontology v4 carries the
`doc_id` of a document in the research library and the span it was read
from; a fact without a document does not enter the store. Library documents
are stored once under their SHA-256 in `data/bronze/library/` and are never
edited (P16 applies). Dossiers are regenerated from the library, never
hand-edited; corrections go through the manual layer with provenance (P5).
Patterns derived from dossiers are tested only on deals dated after the
deals they were derived from (P10). Reason: the Tempus record (Ontology v4
§2.5) showed that a deal is a dossier of dated facts whose value depends on
being re-readable at source; the retracted 6.2× result showed what an
untraceable number costs.
