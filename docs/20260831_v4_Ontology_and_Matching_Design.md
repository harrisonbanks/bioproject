docs/20260831_v4_Ontology_and_Matching_Design.md

# Ontology and M&A matching design

Bioindustry Intelligence Platform · design document v4 · 2026-08-31
Status: proposed, for review by J. Banks and H. Banks. Supersedes v3
(2026-08-30). v4 (decision 2026-08-31, "deal dossiers on top of a research
library"): adds the research library (§3.9), the deal dossier (§3.10), the
entity attributes and event classes the dossier needs (§3.2, §3.3, §3.6),
the aspect matcher and the forward hit/false-alarm test (§5.5, §5.6),
roadmap steps L1–L4 and 2.9′ (§7), and answers §8 Q5. v3 added
the global universe and stub entities (§3.1a), the price-action attribute
group (§3.2a), the forward-calendar sources of record (§3.6), the manual
notes template (§3.4), benchmarks (§3.7), and Model 4 Horizon Scanning
(§3.8). Principles P1–P15 apply.

---

## 1. Purpose

Rebuild commercial-grade M&A intelligence for the bioindustry from free
public data plus a manual layer, on a design where:

1. every actor (listed company, private biotech, fund, other) is a neutral
   entity described by attributes and relationships;
2. acquisition objectives are an explicit, extensible list;
3. matching is a separate process that pairs a hunter with candidates under
   a stated objective; and
4. every matcher is evaluated on real historical deals under one protocol.

The current code is a working, validated instance of one objective
(therapeutic-area overlap plus patent-cliff pressure, HR@10 0.27). This
document generalises it without discarding it.

## 2. Justification

### 2.1 Theory
"Like buys like": merging firms pair on similar and complementary
characteristics, explained by search, scarcity and asset complementarity
(Rhodes-Kropf & Robinson, *Journal of Finance* 2008). Subsequent work
finds matching on product descriptions, ownership, strategy, human
capital, technology (Hoberg & Phillips 2010; Bena & Li 2014; Bettinazzi et
al. 2020; Lee, Mauer & Xu 2018). A distinct strand — Q-theory, "buy low" —
explains valuation-driven deals (Jovanovic & Rousseau 2002; Servaes 1991).
Both strands are needed: strategic hunters follow complementarity,
financial hunters follow valuation. Hence objectives as a dimension (P4).

### 2.2 Representation
Firms as points in an attribute space with a continuous similarity
measure is the standard representation: Hoberg–Phillips text-based
product space from 10-K descriptions (JPE 2016; RFS 2010, where more
similar product text raises merger likelihood). The project's disease
vectors and MASS-exact similarity (Albora, Straccamore & Zaccaria, PLOS One
2026, eqs 6–10) are the same construction on a biopharma-specific
attribute, and outperformed patent-class and molecular-target substrates in
the project's own pre-registered comparison.

### 2.3 Method
Knowledge-graph target recommendation research follows the sequence
proposed here: ontology design → entity and relationship extraction →
embedding or similarity → top-N recommendation, evaluated by mean rank and
Hits@k (2025 KG-based M&A recommendation study; the same metrics the
project already reports). One such study found structural similarity a
stronger predictor of fit than human-centric filters such as geography.

### 2.4 Practice
Corporate and PE dealmaking has moved to always-on screening of
attribute-matched candidates against a buyer's thesis (BCG 2026; PE
sourcing platforms modelling companies, funds, deals, sectors and
relationships as a graph). This is the commercial product the project
reproduces from public data.

### 2.5 Evidence from deals
Lilly–Ajax (announced 2026-04-27, up to $2.3B, upfront + milestones):
a Phase 1 Type II JAK2 inhibitor for myelofibrosis bought to deepen a
blood-cancer position and replace a failed internal JAK2 program, amid
industry patent-cliff restocking. Objective: mechanism-level gap inside an
existing therapeutic area. Ajax was private — outside the current listed
universe. Lilly's 2026 sequence (Orna, Kelonia, Ajax) shows one hunter
pursuing one objective repeatedly with different modalities.

Tempus AI's sequence (web-sourced 2026-08-31; sources in §9): Ambry Genetics
(agreed 2024-11-04, closed 2025-02-03; $375M cash plus 4,843,136 Tempus
shares; Tempus was an Ambry customer; stated reason: expanded testing for
inherited cancer risk plus data; Ambry ~$300M 2024 revenue growing >25%),
Deep 6 AI (March 2025; $17.4M, mostly stock; records of >30M patients),
Paige (2025-08-22; $81.25M, predominantly stock, plus an assumed Azure
commitment; ~7M annotated digitised pathology slides and the first
FDA-cleared AI application in pathology; stated reason: accelerate the
largest oncology foundation model), and Personalis (agreed 2026-07-20;
$16.25/share, 6% premium to prior close, 28% to unaffected 30-day VWAP;
equity value $1.9B, enterprise value $1.5B net of Tempus' 12.5% stake;
100% stock with a cash option up to 50%; exchange ratio capped at 0.3356;
target may terminate below $46.00 Tempus; Merck, 13.4% holder, agreed to
vote in favour; outside date 2027-04-20). The Personalis deal was preceded
by a dated relationship: a five-year Commercialization and Reference
Laboratory Agreement (2023-11) with an equity investment; an expansion and
a further $36M stake purchase via warrants (2024-08); extension to biopharma
customers (2024-12); a fourth indication, colorectal, added (2025-07);
Medicare coverage of the target's test in a third indication and clinical
volume up 258% year on year (2026 Q1); reported takeover interest from
Merck and two other suitors and a 55% share-price run-up (2026-06/07). The
stated reason: extend Tempus from diagnosis and treatment selection into
recurrence monitoring; the buyer had stated in public, two weeks before the
Paige deal, that it would prioritise deals enhancing its data or
applications businesses without derailing profitability. Comparables in
the same category and window: Natera–Foresight (2025-12, up to $450M,
all stock) and Roche–Saga (2026-04, up to $595M).

What that record teaches the design: a deal is a dossier of dated facts,
each with its source, not one row; the aspects that recur across the four
Tempus deals — an escalating commercial relationship, a minority stake
built in steps, a product that extends the buyer's continuum into an
adjacent step, a data asset the buyer's AI business can use, mostly-stock
consideration, recent reimbursement wins and fast volume growth at the
target, a category the buyer's CEO named in public beforehand, and a
competing stakeholder — are the starting vocabulary of §3.10; and several of
them (equity stakes, stated priorities, reimbursement events, consideration
type, competing holders) are attributes the ontology did not hold before v4.

## 3. Ontology

### 3.1 Entity types
| Type | Instances | Registry today | Gap |
|---|---|---|---|
| Company (listed) | 1,379 SIC 2834/2836 filers | `companies.csv`, `universe.csv` (IID) | universe rule to widen to diagnostics, tools and data companies (Tempus, Personalis are outside SIC 2834/2836; roadmap 2.9′) |
| Company (private) | biotechs, tools, diagnostics | appear only as deal counterparties | needs registry rows with `listed=0` |
| Financial buyer | PE, hedge funds, royalty buyers | absent | new entity rows; attributes largely manual |
| Asset (drug program) | one per (company, molecule/indication) | implicit in `trials.csv`, `events.csv` | optional explicit table |
| Trial | ClinicalTrials.gov record | `trials.csv` | none |
| Regulatory event | approval, CRL (by deficiency type), designation, PDUFA goal date, AdCom, filing milestone, extension/delay, resubmission, post-approval action | `events.csv` (approvals, CRLs) | forward calendar absent; CRL deficiency type; disclosure timestamp; AdCom votes — see §3.6 and docs/20260830_v1_FDA_Catalyst_Research.md §4 |
| Deal | acquisition, licence, partnership | `ma_events.csv`, `deals.csv`, `partners.csv` | objective label absent |
| Patent | Orange Book listing, CPC patent | `patents.csv`, Orange Book cache | none |
| Person | founders, executives, board | absent | optional, manual |

### 3.1a Universe and stub entities (decision 2026-08-30)
The registry is global: any company with a US-traded line (common stock or
ADR) from any jurisdiction (Japan, Europe, elsewhere) is in scope, with no
market-cap or liquidity floor. Entities without market data (private
companies, research groups, companies discovered by Model 4) are held as
stub rows with `listed=0` and `has_prices=0`; the manual layer fills what
public data lacks. Every model declares whether it requires prices and
skips stubs accordingly; nothing else changes.

### 3.2 Attributes (per entity, with source)
| Attribute group | Examples | Source | Status |
|---|---|---|---|
| Identity | name, aliases, CIK, ticker, listed, type, HQ | SEC, manual | present (listed only) |
| Therapeutic profile | diseases by trial count and phase, approvals | CT.gov, openFDA | present |
| Mechanism / modality | targets (ChEMBL), modality (small molecule, biologic, cell/gene, RNA, device, diagnostic, data) | ChEMBL, 10-K text, manual | targets present; modality absent |
| Sector | pharma, biotech, tools, CDMO, diagnostics, data | SIC + classifier + manual | partial (partner ecosystem only) |
| Stage | lead phase, phase mix, first approval date | CT.gov, openFDA | present |
| Financial | cash, revenue, burn, runway, market cap, valuation | XBRL, Yahoo, Form D, manual | present (listed); private absent |
| IP position | Orange Book expiries, CPC classes, LOE exposure | Orange Book, BigQuery | present |
| Relationships | partners, co-sponsors, counterparties, investors, acquirer | CT.gov, 8-K, Form D, manual | corporate present; investors absent |
| Strategy / intent | stated objectives, in-play flags, rumours | manual, press releases | absent |
| Objectives (hunters) | list from §4 with weights | manual, deal history | absent |
| Equity stakes (v4) | holder, issuer, percent, as-of date, source filing | SEC Schedules 13D/13G, 10-K/10-Q notes, proxies | absent (13D dates read for the activist feature; holder and percent dropped) |
| Stated priorities (v4) | dated statements of what the entity says it will buy or build, with category | earnings-call transcripts, investor letters, 10-K strategy sections (research library) | absent |
| Assets / products (v4) | product, category, continuum step (risk → diagnosis → treatment selection → monitoring), modality, indications, regulatory and reimbursement status | CT.gov, openFDA, press releases, manual | implicit in trials/events; explicit table required (§3.1 asset row) |
| Deal history as acquirer (v4) | dossiers of the entity's past deals (§3.10): consideration habit, category pattern, cadence | deal dossier tables | absent |

### 3.2a Price-action attribute group (Model 2 inputs; any model may read)
| Attribute | Definition | Source | Status |
|---|---|---|---|
| Event dependence | share of pipeline value in the asset under decision (single-asset flag; count of clinical assets; lead-asset phase) | trials, events, manual | derivable |
| Stage class | pre-revenue / first-approval pending / commercial / big pharma | events, financials | derivable |
| Size | market cap, float (if available), average daily dollar volume | prices; manual for float | partial |
| Capital position | cash, burn, runway months, shelf/ATM on file, months since last raise | financials, 8-K/S-3 | runway present; shelf flag to add |
| Event history | prior events for the stock by class and outcome; prior run-up and post-event paths | event table + prices | derivable once the event table exists |
| Sponsor track record | prior CRLs, prior approvals, prior delays across all assets | events | derivable |
| Designation | Fast Track, Breakthrough, Orphan, Priority Review, Accelerated | events, 8-K text | partial |
| Peer set | same-indication competitors (disease vectors), alliance partners (relationships) | trials, relationships | derivable |
| Disclosure behaviour | typical disclosure timing (after close / pre-market), press-release cadence | 8-K timestamps | to add |
| Listing | exchange, ADR ratio, home market, currency | SEC, manual | to add for ADRs |
Every attribute is stored once on the entity (P1) and dated; models read a declared subset (P2).

### 3.3 Relationship types
`sponsors`, `co_sponsors`, `licenses_to/from`, `partners_with`,
`acquired`, `acquired_by`, `invested_in`, `founded`, `supplies`, and (v4)
`exclusive_commercial_partner`, `distributes_for`, `customer_of`,
`holds_stake_in` (with percent and as-of date) — stored
in one edge table (`relationships.csv` extended with `type`, `date`,
`source`). Relationships are attributes of both endpoints (P3).

### 3.4 Manual layer (P5)
`manual_attributes.csv`: `entity_key, attribute, value, valid_from,
source, entered_by, entered_on, note`. `manual_entities.csv`: new entity
rows with the identity attributes. `manual_notes.csv` (templated notes,
decision 2026-08-30): `note_id, entity_key, event_id (optional), date,
title, text, source_url, entered_by, entered_on, tags` — any information
you gather, attached to an entity or an event, readable by any model as
text and surfaced in reports with its provenance. Rules: manual overrides machine per
attribute; machine value retained as `<attribute>_auto`; provenance
columns mandatory; validated on load; committed to git. Uses: new entities
(private, funds), augmentation/correction of any attribute, hunter
objectives and flags.

### 3.6 Regulatory-event extension and forward calendar (shared with Model 2)
The Regulatory-event entity is one table used by both models: Model 1
reads realised outcomes (approvals, CRLs) as target attributes; Model 2
reads the same table plus forward-dated rows (scheduled PDUFA goal dates,
AdCom dates, expected readouts) and disclosure timestamps. Columns per
row: entity, asset, indication, event class, scheduled date, disclosure
datetime, outcome state, outcome sub-type (e.g. CRL deficiency type),
source URL, provenance. Forward-dated rows are populated by the
forward-calendar builder from sponsor 8-Ks and press releases (already
ingested), FDA AdCom notices, and ClinicalTrials.gov completion dates;
the manual layer (§3.4) may add or correct any row. The event taxonomy
and outcome states are defined in the FDA Catalyst Research note §4 and
are binding for both models (P1: one table, model-agnostic).

Sources of record (decision 2026-08-30; all official, free, machine-
accessible; P13):
- Past decisions: Drugs@FDA (approvals) and the openFDA CRL endpoint,
  plus the FDA's published CRL letters for deficiency type — as built.
- Forward goal dates (PDUFA), filing milestones, delays, resubmissions,
  readout guidance: sponsor 8-Ks and press-release exhibits found through
  the SEC EDGAR full-text search JSON endpoint
  (`https://efts.sec.gov/LATEST/search-index`; no key; descriptive
  User-Agent required; undocumented, probe-gated; results partitioned by
  form type and date; dedupe on accession), with the date parsed from the
  exhibit text and the exhibit URL stored on the row.
- Advisory committees: the FDA Advisory Committee calendar (dates,
  briefing documents).
- Expected readouts: ClinicalTrials.gov primary-completion dates (field to
  add to the existing v2 pull).
- Cross-check only, not a feed: one aggregator (default pdufa.bio, free,
  source-linked); paid APIs (BiopharmaWatch, BPIQ, RTTNews) only if
  chosen later. The daily maintenance job reconciles counts and flags
  disagreements for manual review.
The existing `calendar IID` command becomes a per-entity view over this
table (trials + past FDA actions + forward rows), not a separate builder.

Event classes added in v4, written to the same table so Phase 1 (calendar)
and the deal dossier (§3.10) share it: `reimbursement_decision` (Medicare
coverage, MolDX, payer decisions), `regulatory_clearance_non_fda` (UKCA,
CE-IVD, other jurisdictions), `acquisition_announced`, `acquisition_closed`,
`acquisition_terminated`, `stake_purchase`, `takeover_interest_reported`.
Every row carries `doc_id` (§3.9) in `source_url`/`provenance`.

### 3.7 Benchmarks (decision 2026-08-30)
Abnormal returns are computed against a configurable benchmark set:
XBI (SPDR S&P Biotech ETF) by default, plus any user-defined benchmark —
SPX, another index, or a named basket of entities — evaluated side by
side and reported per benchmark. Benchmark definitions live in a
committed table (`benchmarks.csv`: name, type, constituents or ticker).

### 3.8 Model 4 — Horizon Scanning (entity and actor discovery)
Purpose: find interesting companies, research groups, people and assets
from research papers, news, articles, preprints, conference abstracts,
patents and filings, and record the entities involved with the source
document. Formal basis: horizon scanning (OECD definition: systematic
examination of early signs of important developments) and technology
scouting; method: scientific named-entity recognition and relation
extraction over ingested documents. Output: new or enriched registry rows
(stubs allowed, §3.1a), relationships (§3.3), and notes (§3.4) with
provenance; a human review queue like today's label QA. It feeds all
other models and is evaluated on precision of extracted entities and on
how many later became targets, sponsors, or catalyst holders. Detailed
requirements: a separate Model 4 design document (not yet written).

### 3.5 Schema as code
`src/biointel/schema.py`: entity types, attribute names, types, allowed
values, and the table each is read from; a `validate` command checks every
silver/gold table against it. This is the written ontology.

### 3.9 Research library (v4)
Purpose: every fact the platform asserts about a company or a deal can be
traced to a document, and the document can be re-read later; the whole
extraction can be re-run against the same corpus when the vocabulary
changes. Storage: `data/bronze/library/<sha256>.<ext>`, one copy per
document, named by its hash, never edited (P16). Index tables:
`documents` (`doc_id` = sha256, `url`, `source_type` — sec_8k, sec_425,
sec_s4, sec_defm14a, sec_13d, sec_13g, sec_10k, sec_10q, press_release,
transcript, investor_letter, analyst_note, news, regulatory_notice,
manual_upload — `publisher`, `title`, `published_at`, `retrieved_at`,
`accession` where SEC, `access` public/paywalled, `added_by` code or
person, `note`) and `document_links` (`doc_id`, `entity_key` / `deal_id` /
`event_id`, `role` acquirer / target / third_party / comparable /
commentary). Two ways in: code (every `fetch_json` document already carries
URL, status and time; the library adds hash, type and links) and a manual
`library add <url-or-file> --entity --deal --type` command for anything a
person finds. Every dossier field (§3.10), every stated priority (§3.2) and
every v4 event row cites `doc_id` plus a character span. Each regeneration
of dossiers from the library is a ledger run (P17) with its
`data_snapshot_hash`, so two dossier versions are comparable.

### 3.10 Deal dossier (v4)
The unit of record for an acquisition. `ma_events` remains the index
(one row per deal, `deal_id`); the dossier tables hang off it:
- `deal_terms`: announce, signing and close dates, status, price per share,
  premium to prior close and to 30-day VWAP, equity value, enterprise value
  net of any existing stake, consideration mix (stock %, cash option %),
  exchange-ratio cap, financing source, termination conditions, outside
  date, voting agreements — each with `doc_id`.
- `deal_timeline`: one row per dated step in the relationship before and
  after announcement (first agreement, expansions, stake purchases,
  indications added, reimbursement decisions, clearances, reported
  takeover interest, board approval, vote, close) with type, description,
  `doc_id`.
- `deal_rationale`: stated reasons verbatim, speaker, `doc_id`, span,
  aspect tags.
- `deal_aspects`: one row per (deal, aspect): value, method (stated /
  derived from tables / manual), confidence, evidence `doc_id` and span.
  Starting vocabulary: prior_commercial_relationship (duration, escalation
  count), prior_equity_stake (percent, steps), continuum_extension (step
  added), complementary_data_asset, mechanism_or_target_gap,
  therapeutic_area_overlap, reimbursement_catalyst,
  buyer_stated_priority_match, competing_stakeholder, consideration_type,
  target_revenue_growth, target_profitability, buyer_financing_capacity,
  patent_cliff_pressure, category_consolidation.
- `deal_comparables`: pairs of deals in the same category and window with
  the basis for the comparison.
Market reaction around announcement, for both sides, comes from the event
study (Model 2) once acquisition announcements are an event class (§3.6);
it is not duplicated. Dossiers are produced by the deal analyser (§5.7),
regenerable from the library, corrected through the manual layer (§3.4,
P5) with provenance.

## 4. Objectives (P4)

| # | Objective | Hunter type | Attributes required | Matcher | Evaluation labels |
|---|---|---|---|---|---|
| O1 | Pipeline replenishment / LOE gap | pharma | hunter LOE exposure by area; target phase mix, approvals | current MASS-exact + LOE urgency | deals where acquirer had LOE ≤ 5y in target's area |
| O2 | Therapeutic-area deepening | pharma, large biotech | disease vectors | MASS-exact (implemented) | all strategic deals (current ledger) |
| O3 | Mechanism / modality acquisition | pharma | ChEMBL targets, modality label | target/modality similarity within area | deals citing mechanism in rationale (Lilly–Ajax) |
| O4 | Platform / technology | pharma, biotech | platform type from 10-K/patents | text + CPC similarity | deals citing platform |
| O5 | Data / diagnostics | data-biotech, diagnostics | data assets, test menus (manual) | attribute complementarity | deals citing data/assay |
| O6 | Geographic / commercial | pharma | revenue by region, sales presence | geography gap | deals citing market access |
| O7 | Financial | PE, hedge, royalty | valuation, cash flow, leverage, royalties | undervaluation / cash-flow screen | financial-buyer deals |
| O8 | Consolidation / defensive | any | competitive overlap (product text) | Hoberg–Phillips-style similarity | horizontal deals |

Objective labels on historical deals come from acquirer 8-K and press-
release rationale text (the `labels.py` pipeline already reads these
documents); each label is a manual-reviewable classification with a
confidence, like today's acquirer-fill.

## 5. Matching

### 5.1 Definition
A match run is `(hunter, objective) → ranked candidates` over a candidate
set (all entities, or filtered by type/size). Score = matcher(hunter
attributes, candidate attributes, objective parameters). `predict` for a
target is the union over hunters and objectives of where the target
ranks, presented as "best-fit hunters and why".

### 5.2 Matchers as registered models (P6)
Interface: `name`, `objective`, `inputs` (declared attribute list),
`fit(panel)` (optional), `score(hunter, candidates) → rows`. Registry maps
names to classes. Harness: loads the merged entity view once, checks
declared inputs, runs the protocol, writes a result record
(`model, version, data_snapshot_hash, objective, metrics, timestamp`).
Existing engines are wrapped first: `pairs.py` (O1/O2), `improve.py`
(buyer-agnostic screen), `score.py` (scorecard), `baselines.py` (frozen).

### 5.3 Evaluation protocol (P10)
Per objective: held-out deals with that label; for each deal, the true
target among sampled negatives; metrics mean rank, Hits@5/10/25, lift vs
chance; identical events and negatives across matchers being compared;
acceptance by pre-registered rule. Leakage rules: no post-deal data, no
price-derived inputs for fitted models (P2).

### 5.4 Screen and pairing composition
Buyer-agnostic attractiveness (fitted screen) and hunter-specific fit
(objective matchers) are separate scores, both shown; the product ranking
is the fitted screen (recommendation), with scorecard rules as the plain-
language explanation and objective matches as the "who and why".

### 5.5 Aspect matcher (v4; implementation `aspect-match` under `acquirer-pairing`)
Buyer profile as of a date: continuum steps covered, data assets, stated
priorities (§3.2), stakes held, partners, cash and stock currency, pattern
of past deals (consideration habit, category, cadence). Candidate profile
as of the same date: products and continuum step, revenue growth and
reimbursement momentum, existing relationship with the buyer, stake held
by the buyer, competing stakeholders, size relative to the buyer. Score
per pattern = weighted count of the pattern's aspects present for the
pair; output lists the evidence documents next to each aspect so the
reader sees why. Registered under the framework with declared inputs
enforced by the harness; hand-built, not trained, so it may read any
attribute (P2) and the paper describes its inputs. Patterns and weights
come from the dossiers (§3.10) and are versioned with them.

### 5.6 Forward test for the matcher (v4)
For every buyer at every past year-end, generate the ranked list using
only information dated on or before that year-end; then open the deal
history and count (a) how many deals announced in the following year had
the true target in the buyer's top-k (hits) and (b) how many proposed
pairs never happened (false alarms), both against chance. Patterns
learned from deals up to a year are tested on deals after that year,
never on the deals they were read from (P10). The pass mark is written
before the run, as in every protocol test in this project.

### 5.7 Deal analyser (v4; pipeline, not a model)
Per deal: gather the documents (both sides' announcement 8-K/425 filings
and press exhibits through the EDGAR full-text search adapter that Phase 1
gate 1.5 also needs — built once; acquirer 10-K/10-Q business-combination
notes; 13D/13G for stakes; all prior 8-Ks between the pair for the
timeline; transcripts, letters and news through `library add` until a
free machine source is proved), store them in the library, and extract
the dossier fields: stated reasons and terms by phrase matching against
the aspect vocabulary with the span kept, the relationship timeline from
dated filings between the pair, the numbers from the financial tables
already ingested. Each field carries method and evidence. A review queue
like the label QA presents a random sample plus every suspicious row; the
hand-checked sample gives the precision the paper reports. The analyser
runs on the 447 target-role events already in the universe first, then on
deals the widened universe (2.9′) adds.

## 6. Use cases

1. **Pharma BD team, LOE gap (O1).** Input: hunter = the pharma, its LOE
   exposure by area. Output: ranked targets in those areas with phase mix
   and approvals, refreshed each quarter. Today: partially served by
   `predict`.
2. **Biotech seeking buyers (reverse match).** Input: the biotech as
   target. Output: hunters for whom it ranks highly, per objective, with
   the objective stated. Today: `predict` gives three acquirers by O2 only.
3. **PE or royalty fund thesis (O7).** Input: fund thesis as objective
   parameters. Output: undervalued or cash-generative candidates. Today:
   not possible (no financial matcher, no fund entity).
4. **Analyst validating a rumour.** Input: hunter, target, rumoured
   objective. Output: where the target ranks for that hunter under each
   objective, with the attribute evidence. Today: possible for O2 only.
5. **Mechanism-gap scan (O3), the Lilly–Ajax case.** Input: hunter's
   failed or expiring programs by target. Output: private and listed
   companies with alternative mechanisms on the same target. Today: not
   possible (private entities absent; mechanism matcher absent).
6. **Research and paper.** Every matcher's accuracy per objective in one
   generated ledger, with the null results preserved.

## 7. Roadmap (gated as before; each step regression-checked)

| Step | Deliverable | Depends on |
|---|---|---|
| A | `schema.py` + `validate` command; `relationships.csv` typed | — |
| B | Manual layer: two tables, loader, precedence, provenance, validation | A |
| C | Entity registry generalised: `type`, `listed`; private entities from counterparties, CT.gov sponsors, Form D | A, B |
| D | Model framework: interface, registry, harness, result record; wrap the five existing models; ledger generated | — |
| E | `predict` composition decision implemented (screen + explanation + objective matches) | D |
| F | Objective labels on historical deals from 8-K/press text; O1–O3 evaluated separately | C, D |
| G | Modality and sector classification (10-K text, patents, manual) | A |
| H | Financial matcher (O7) and fund entities | B, C, D |
| I | Product-text similarity (O4, O8) from 10-K text already ingested | D |
| L1 (v4) | Research library: `documents`, `document_links`, `library add`, hashing of existing bronze documents | A |
| L2 (v4) | Dossier schema (§3.10) and entity attributes (§3.2 equity stakes, stated priorities, assets; §3.3 typed edges; §3.6 event classes) in `schema.py` | L1, B |
| L3 (v4) | EDGAR full-text adapter (shared with Phase 1 gate 1.5) and deal analyser v1 (§5.7) over the 447 existing events; review queue; precision on a hand-checked sample | L2 |
| L4 (v4) | `aspect-match` matcher (§5.5) and the forward hit/false-alarm test (§5.6) | L3, D |
| 2.9′ (v4) | Universe widened to diagnostics, tools and data companies; private targets as stubs; new regression baseline | L2 |

## 8. Open questions

1. Which screen drives `predict` (P7).
2. Objective label taxonomy granularity (8 objectives, or finer).
3. Candidate-set rules for private entities with sparse attributes
   (minimum attribute count before a private entity enters a match run).
4. Whether Person entities are worth maintaining manually.
5. Snapshot policy — ANSWERED 2026-08-31: the repository does not carry
   data; Jason's 2026-08-29 data, frozen 2026-08-31, is the snapshot of
   record and is shared by USB (Implementation Plan §4; PROJECT_STATUS 0.5).
6. Ownership of the forward-calendar builder: a Model 2 deliverable that
   Model 1 also consumes (catalyst proximity as a target attribute);
   sequence it in roadmap step C or as its own step.
7. Model 3 number is unassigned (decision pending).
8. (v4) Sequencing of the dossier track L1–L4 relative to Phase 1 (the FDA
   calendar): ahead of it, alongside it, or after it — decision pending.
9. (v4) Universe widening (2.9′): which SIC codes or lists define
   diagnostics, tools and data companies; whether Tempus and Personalis
   are already among the 1,379 members is checked on the operator machine
   before the gate is scoped.
10. (v4) Free machine sources for earnings-call transcripts and investor
   letters (SEC 8-K exhibits carry some; the rest enter by `library add`
   until a source is proved).

## 9. References

Tempus record (v4 §2.5; retrieved 2026-08-31): Tempus press release
2026-07-20 (tempus.com/news/pr/tempus-to-acquire-personalis-integrating-mrd);
Tempus 10-Q for the quarter ended 2026-06-30 (sec.gov, CIK 1717115,
accession 0001193125-26-326090); Personalis 8-K 2023-11-25 (sec.gov, CIK
1527753, accession 0000950170-23-066458); Personalis press releases
2024-08-16, 2024-12-16, 2025-07-09 (investors.personalis.com); Personalis
Form 425 investor presentation 2026 (sec.gov, accession
0001193125-26-309090); Tempus press releases 2025-02-03 (Ambry) and
2025-08-22 (Paige) (investors.tempus.com); Tempus annual report FY2025
(Ambry and Deep 6 consideration; sec.gov, accession 0001193125-26-145547);
MedTech Dive 2024-11-06 and 2025-08-26; Investing.com 2026-07-18 (Needham,
takeover interest, holder percentages); OncoDaily 2026-07-27 (Merck voting
agreement; Natera–Foresight; Roche–Saga); The Pharma Letter, Personalis
profile, 2026-08 (FY2025 figures, Medicare coverage, outside date).


Rhodes-Kropf M., Robinson D.T. (2008) The market for mergers and the
boundaries of the firm. *J. Finance* 63(3). · Hoberg G., Phillips G. (2010)
Product market synergies and competition in M&A: a text-based analysis.
*RFS* 23(10); (2016) Text-based network industries. *JPE* 124(5). · Bena
J., Li K. (2014) Corporate innovations and M&A. *J. Finance*. · Jovanovic
B., Rousseau P. (2002) The Q-theory of mergers. *AER*. · Albora,
Straccamore, Zaccaria (2026) PLOS One (MASS-exact, eqs 6–10). ·
Knowledge-graph-based target recommendation for M&A (2025, ResearchGate
396009946). · BCG (2026) AI is turning M&A into a high-impact learning
machine. · Eli Lilly press release 2026-04-27 (Ajax).
