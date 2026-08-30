docs/20260830_v1_FDA_Catalyst_Product_Design.md

# FDA catalyst price-action product — requirements (Model 2)

Bioindustry Intelligence Platform · design document v1 · 2026-08-30
Status: proposed, for review by J. Banks and H. Banks. Companion to the
Ontology and Matching Design v3 (attributes §3.2a, events and calendar
§3.6, benchmarks §3.7, manual notes §3.4) and the FDA Catalyst Research
note (evidence, theses T1–T6, taxonomy, models, rules). Principles
P1–P15 apply. This document states requirements only; nothing is built.

## 1. Purpose and boundaries

R1.1 Daily analysis that, for every entity with a scheduled or expected
     FDA-calendar event, forecasts the pre-event run-up path and the
     post-event path by outcome state (passed, failed by deficiency type,
     delayed), from daily closing prices and entity attributes.
R1.2 Ranks entities whose events fall on the same day or in the same
     window against each other on historical performance around
     comparable events, with full attribution for every rank (P15).
R1.3 Daily bars only; no intraday; the system does not trade or automate
     any position (P14).
R1.4 Uses public data and the manual layer (templated notes, attribute
     overrides); no other inputs.
R1.5 Global universe with stubs (P15); entities without prices are listed
     with their events but excluded from price models until prices exist.

## 2. Inputs (all from the shared tables; P1)

R2.1 Event table (ontology §3.6): every event class in Research §4, with
     scheduled date, disclosure datetime, outcome state and sub-type,
     source URL; delays are first-class events.
R2.2 Entity attributes (ontology §3.2, §3.2a): therapeutic profile, stage
     class, event dependence, size, capital position, event history,
     sponsor track record, designations, peer set, disclosure behaviour,
     listing.
R2.3 Prices: daily bars per entity and per benchmark; survivorship gaps
     documented per entity.
R2.4 Benchmarks (ontology §3.7): XBI default plus user-defined.
R2.5 Manual notes and overrides (ontology §3.4).

## 3. Forward-calendar maintenance job (daily)

R3.1 Queries the SEC EDGAR full-text endpoint for new 8-K and press
     exhibits mentioning goal-date, advisory-committee, CRL,
     resubmission, extension and readout language since the last run;
     dedupes on accession; stores exhibit URL.
R3.2 Parses scheduled dates, event class, asset and indication from the
     exhibit text; assigns to the entity by CIK; unparsed hits go to a
     review queue with the text excerpt.
R3.3 Pulls the FDA Advisory Committee calendar and ClinicalTrials.gov
     primary-completion dates; pulls outcomes from Drugs@FDA and the CRL
     feed and closes open events.
R3.4 Reconciles against one aggregator cross-check (default pdufa.bio):
     rows present in one and not the other are flagged, never auto-
     adopted.
R3.5 Emits a change report: added, changed (date moved = a delay event),
     resolved, flagged; runs unattended; idempotent; every row carries
     source, first-seen, last-verified.

## 4. Models (registered under the shared framework, P6)

R4.1 M2.1 Reaction magnitude: distribution of CAR[0,+1] per outcome
     state from event class and attributes; quantile outputs.
R4.2 M2.2 Run-up: CAR path over [−120,−1] with the day-before level and
     peak; features include attributes, benchmark regime, crowding, the
     stock's own event history.
R4.3 M2.3 Post-event path: CAR[+2,+60] by outcome state × size × CRL
     deficiency type; delay events have their own path model.
R4.4 M2.4 Crowding index: per day, count and dollar weight of catalysts
     in ±k days, in-sector and market-wide.
R4.5 M2.5 Outcome base rate: prior by event class, designation, AdCom
     vote, prior CRL, sponsor record; calibrated on FDA outcomes; a base
     rate, not a scientific judgement.
R4.6 M2.6 Peer spillover: expected CAR of partners and same-indication
     competitors given the focal outcome.
R4.7 M2.7 Daily ranking: entities with events in the same window ranked
     on expected value, dispersion and crowding, liquidity-filtered;
     every rank carries the events, attributes and peers it was computed
     from (R1.2).
R4.8 Each model declares its inputs; each is evaluated by the shared
     harness (Research §8) against class-median and zero baselines; each
     writes a standard result record; the ledger is generated.

## 5. Rules engine

R5.1 Rules R1–R8 of the research note are implemented as parameterised,
     testable rules; parameters are fitted on our history, not adopted
     from vendors; each rule reports its historical hit rate and drawdown
     with a transaction-cost haircut.
R5.2 Rules produce flags and explanations, not orders.

## 6. Daily run and outputs

R6.1 One command (`python -m biointel catalyst-daily`) runs: calendar
     maintenance (R3) → price refresh → attribute refresh → models M2.1–
     M2.6 → ranking M2.7 → rules → reports.
R6.2 Outputs to gold: `catalyst_calendar.csv` (all open events with
     forecasts), `catalyst_ranking.csv` (per-day ranked list with
     attribution columns), `catalyst_report_YYYYMMDD.md` (human report:
     what changed, upcoming windows, ranked entities with evidence, delays,
     flags for manual review), and one result record per model run.
R6.3 Per-entity view: `python -m biointel calendar IID` extended to show
     forward events, forecasts and history (ontology §3.6).
R6.4 Runtime target: the daily run completes within one hour on the
     operator machine without network beyond the listed sources.

## 7. Evaluation and acceptance (P10)

R7.1 Pre-registered protocol per Research §8: time split, holdout with
     a single access, metrics per model, null results reported.
R7.2 Acceptance thresholds set before the first measurement; the
     run-up may prove unexploitable after costs and that is reported.
R7.3 Leakage rules: no post-event data in features; disclosure
     timestamp defines the first tradeable price; delisted survivorship
     documented.

## 8. Data acquisition work required (ontology gaps)

R8.1 EFTS probe and parser for 8-K exhibits (probe-first rule).
R8.2 FDA AdCom calendar pull; FDA CRL letters pull (deficiency type).
R8.3 CT.gov primary-completion field added to the trials pull.
R8.4 Disclosure timestamps from EDGAR acceptance times.
R8.5 ADR listings and home-market identifiers for non-US entities.
R8.6 Shelf/ATM flags from S-3 filings.
R8.7 Benchmarks table and price pulls for user-defined benchmarks.

## 9. Roadmap (gated, regression-checked; each step one commit)

| Step | Deliverable | Depends on |
|---|---|---|
| F1 | Event table schema + migration of `events.csv` into it; `calendar IID` view | Ontology A |
| F2 | EFTS probe, 8-K exhibit parser, review queue | F1 |
| F3 | AdCom, CT.gov completion, CRL letters, disclosure timestamps | F1 |
| F4 | Forward-calendar daily job with change report and cross-check | F2, F3 |
| F5 | Price-action attribute group (§3.2a) computed into the entity table | F1 |
| F6 | Model framework (Ontology D) with M2.1–M2.3 wrapped/built; harness; result records | F5 |
| F7 | Crowding index, base rates, spillover (M2.4–M2.6) | F6 |
| F8 | Ranking M2.7 with attribution; rules engine; daily report | F7 |
| F9 | Benchmarks table and multi-benchmark evaluation | F5 |

## 10. Open decisions

1. Which aggregator, if any, as cross-check beyond pdufa.bio.
2. Window parameters (k for crowding; run-up window length) — fitted vs fixed.
3. Whether Model 4 discovery output enters the catalyst universe automatically or only after review.
4. Model 3 numbering (unassigned).
