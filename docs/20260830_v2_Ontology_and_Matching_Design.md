docs/20260830_v2_Ontology_and_Matching_Design.md

# Ontology and M&A matching design

Bioindustry Intelligence Platform · design document v2 · 2026-08-30
Status: proposed, for review by J. Banks and H. Banks. Supersedes v1 (adds
the Regulatory-event extension for Model 2, §3.1 and §3.6) and the implicit
design in the v0.68–0.81 code. Principles P1–P12 apply.

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
pursuing one objective repeatedly with different modalities. Tempus-style
data acquisitions (illustrative, not verified as completed deals) show an
objective — complementary data assets — that the current attribute set
cannot express.

## 3. Ontology

### 3.1 Entity types
| Type | Instances | Registry today | Gap |
|---|---|---|---|
| Company (listed) | 1,379 SIC 2834/2836 filers | `companies.csv`, `universe.csv` (IID) | none |
| Company (private) | biotechs, tools, diagnostics | appear only as deal counterparties | needs registry rows with `listed=0` |
| Financial buyer | PE, hedge funds, royalty buyers | absent | new entity rows; attributes largely manual |
| Asset (drug program) | one per (company, molecule/indication) | implicit in `trials.csv`, `events.csv` | optional explicit table |
| Trial | ClinicalTrials.gov record | `trials.csv` | none |
| Regulatory event | approval, CRL (by deficiency type), designation, PDUFA goal date, AdCom, filing milestone, extension/delay, resubmission, post-approval action | `events.csv` (approvals, CRLs) | forward calendar absent; CRL deficiency type; disclosure timestamp; AdCom votes — see §3.6 and docs/20260830_v1_FDA_Catalyst_Research.md §4 |
| Deal | acquisition, licence, partnership | `ma_events.csv`, `deals.csv`, `partners.csv` | objective label absent |
| Patent | Orange Book listing, CPC patent | `patents.csv`, Orange Book cache | none |
| Person | founders, executives, board | absent | optional, manual |

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

### 3.3 Relationship types
`sponsors`, `co_sponsors`, `licenses_to/from`, `partners_with`,
`acquired`, `acquired_by`, `invested_in`, `founded`, `supplies` — stored
in one edge table (`relationships.csv` extended with `type`, `date`,
`source`). Relationships are attributes of both endpoints (P3).

### 3.4 Manual layer (P5)
`manual_attributes.csv`: `entity_key, attribute, value, valid_from,
source, entered_by, entered_on, note`. `manual_entities.csv`: new entity
rows with the identity attributes. Rules: manual overrides machine per
attribute; machine value retained as `<attribute>_auto`; provenance
columns mandatory; validated on load; committed to git. Uses: new entities
(private, funds), augmentation/correction of any attribute, hunter
objectives and flags.

### 3.6 Regulatory-event extension (shared with Model 2)
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

### 3.5 Schema as code
`src/biointel/schema.py`: entity types, attribute names, types, allowed
values, and the table each is read from; a `validate` command checks every
silver/gold table against it. This is the written ontology.

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

## 8. Open questions

1. Which screen drives `predict` (P7).
2. Objective label taxonomy granularity (8 objectives, or finer).
3. Candidate-set rules for private entities with sparse attributes
   (minimum attribute count before a private entity enters a match run).
4. Whether Person entities are worth maintaining manually.
5. Snapshot policy: whether the shared repository carries silver/gold so
   both contributors evaluate on one data snapshot.
6. Ownership of the forward-calendar builder: a Model 2 deliverable that
   Model 1 also consumes (catalyst proximity as a target attribute);
   sequence it in roadmap step C or as its own step.

## 9. References

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
