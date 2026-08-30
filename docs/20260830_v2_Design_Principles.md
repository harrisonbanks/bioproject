docs/20260830_v2_Design_Principles.md

# Design principles — Bioindustry Intelligence Platform (v2, 2026-08-30)

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
