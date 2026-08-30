docs/20260830_v1_Horizon_Scanning_Design.md

# Model 4 — Horizon Scanning: entity and actor discovery (requirements)

Bioindustry Intelligence Platform · design document v1 · 2026-08-30
Status: proposed, for review by J. Banks and H. Banks. Companion to the
Ontology and Matching Design v3 (§3.1a stubs, §3.3 relationships, §3.4
manual notes, §3.8 summary). Principles P1–P15 apply. Requirements only.

## 1. Purpose

H1.1 Find interesting companies, research groups, institutions, people
     and assets (drug programs, platforms, datasets) from research
     papers, preprints, news, articles, press releases, conference
     abstracts, grants, patents and filings — anything interesting —
     and document the entities involved with the source document.
H1.2 Feed the entity registry: new entities enter as stubs (§3.1a) with
     provenance; known entities gain attributes, relationships and notes.
     This is how the platform learns about private companies and
     companies never seen before.
H1.3 Serve every other model: Model 1 (new candidate targets and
     hunters), Model 2 (new catalyst holders, new sponsors), and the
     manual layer (pre-filled notes for review).

## 2. Formal basis and naming (research 2026-08-30)

H2.1 *Horizon scanning* — OECD definition: a technique for detecting
     early signs of potentially important developments through a
     systematic examination of potential threats and opportunities, with
     emphasis on new technology; practised by ingesting millions of
     science and innovation documents, examining rapidly growing research
     areas, identifying key actors, and integrating human interpretation
     (bibliometric horizon scanning, arXiv 2202.13480).
H2.2 *Technology scouting* — the enterprise practice; platforms aggregate
     patent databases, scientific literature, startup information and
     market intelligence to discover relevant technologies; horizon
     scanning is its first layer.
H2.3 Method — *scientific named-entity recognition* (SciNER) and
     *relation extraction* over full text; entity types and relation types
     are defined per domain (here: organisation, person, asset, disease,
     mechanism, modality, funding event, deal event).
H2.4 Name adopted: **Model 4 — Horizon Scanning (entity and actor
     discovery)**.

## 3. Inputs (document sources; official/free first, P11; each probe-gated)

| Source | Content | Access | Entity yield |
|---|---|---|---|
| PubMed / Europe PMC | abstracts, full text (OA), author affiliations | free APIs (E-utilities; Europe PMC REST) | research groups, institutions, people, diseases, mechanisms |
| bioRxiv / medRxiv | preprints with affiliations | free API | same, earlier in time |
| ClinicalTrials.gov v2 | new sponsors, collaborators, sites | already integrated | private sponsors, academic centres |
| NIH RePORTER | grants: PI, institution, abstract, funding | free API | research groups with funding (early-stage signal) |
| SEC EDGAR (Form D, 8-K, S-1, 13D) | private raises, deals, IPO filings, activist stakes | already integrated (EDGAR APIs, EFTS full-text) | private companies, investors, deal counterparties |
| FDA press announcements, designations lists | new designations, approvals, warnings | free (RSS/HTML) | assets, sponsors |
| Press-wire RSS (GlobeNewswire, PR Newswire, Business Wire) | company announcements | free RSS | companies, assets, partners, dates |
| Conference abstracts (ASCO, AACR, ASH, ESMO) | late-breaking data, presenting institutions | free web, varies | assets, sponsors, investigators |
| Google Patents (BigQuery, already used) | assignees, inventors, CPC | in place | companies, inventors, technology areas |
| Manual notes (§3.4) | anything the operators read | template | any |
| Paid news/data (Endpoints, Fierce, Crunchbase, PitchBook) | — | not used (P11) unless chosen | — |

H3.1 Every ingested document is stored in bronze with URL, retrieval
     time and hash; extraction never runs on text that is not stored.

## 4. Extraction and resolution

H4.1 Entity types: organisation (company, academic, government, fund),
     person, asset (drug/program/platform/dataset), disease, mechanism or
     target, modality, event (raise, deal, designation, readout).
H4.2 Relation types (extend ontology §3.3): affiliated_with, sponsors,
     develops, targets, licenses, invested_in, collaborates_with,
     acquired, presented_at, funded_by.
H4.3 Resolution: extracted organisation names resolve to the registry
     through `match.canon()` plus alias tables; unresolved names create
     stub entities with `status=candidate`; people and institutions get
     their own registry types (§3.1).
H4.4 Every extracted fact carries: source document, sentence span,
     extractor and version, confidence, extraction date.
H4.5 Tooling: rule-based and dictionary matching first (disease,
     mechanism and modality vocabularies we already hold or can load:
     MeSH, ChEMBL targets, CPC); a trained NER model (spaCy or a
     biomedical model) second; LLM-assisted extraction only with the
     source span recorded and a review step. No dependency is added
     without stating name, reason and rejected alternative.

## 5. Scoring "interesting" and the review queue

H5.1 Interest is not one number; the scanner emits signals per document
     and per entity: novelty (first appearance of an actor or asset),
     momentum (growth of mentions, grants, trials), proximity (overlap
     with existing universe diseases/mechanisms, or with a hunter's
     objectives — Model 1 O1–O8), catalyst proximity (an upcoming event
     — Model 2), and capital signals (Form D raise, IPO filing).
H5.2 A ranked review queue (like today's label QA) presents new
     candidates with the evidence; a human accepts, rejects or edits;
     accepted entities become registry rows, rejected ones are remembered
     so they are not re-proposed.
H5.3 Watchlists: operators can register topics (a disease, a mechanism,
     a modality, a geography, an institution) and receive the daily
     scanner output filtered to them.

## 6. Outputs

H6.1 Registry deltas (new stubs, enriched attributes, new relationships)
     with provenance, applied through the same load path as the manual
     layer (machine-extracted values rank below manual, above nothing).
H6.2 `scan_candidates.csv` (review queue), `scan_report_YYYYMMDD.md`
     (daily: new actors, notable documents, watchlist hits), result
     records for the central reporting layer.
H6.3 Notes pre-filled from documents for the manual notes table,
     flagged `machine_generated=1` until reviewed.

## 7. Evaluation

H7.1 Extraction quality: precision/recall of entities and relations on a
     hand-labelled sample per source (target ≥ 0.9 precision on
     organisations before auto-creating stubs; below that, queue only).
H7.2 Usefulness: of entities first surfaced by the scanner, how many
     later appear as targets (Model 1 labels), catalyst holders (Model 2
     events), or trial sponsors, and how early relative to other sources.
H7.3 Same harness and result records as the other models (P6).

## 8. Dependencies and sequencing

H8.1 Requires: schema as code (Phase 0.1), central reporting (0.2),
     registry with types and stubs (Phase 2.9), manual layer (2.10).
H8.2 Independent of Model 2 models; can start after Phase 2 in parallel
     with Phase 3, or earlier for the document-ingest and storage part
     (bronze store already exists).
H8.3 Roadmap: S1 document ingest for two sources (PubMed/Europe PMC,
     press-wire RSS) into bronze with probes; S2 dictionary extraction and
     resolution to registry; S3 review queue and scan report; S4 Form D /
     NIH RePORTER / preprints; S5 NER model and relation extraction; S6
     interest signals and watchlists; S7 usefulness evaluation.

## 9. Open decisions

1. Source order for S1 (papers first or press wires first).
2. Whether people are first-class entities from the start or after S4.
3. Auto-create stubs above a precision threshold, or always review.
4. Model 3 numbering (unassigned).
