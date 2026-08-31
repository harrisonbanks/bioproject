docs/20260831_v1_Research_Process_Diagram.md

# Research process — analyse the company, build the ontology, matchmake, test against history

The analyst's method as the platform runs it (Ontology v4 §3.9–§3.10,
§5.5–§5.7). Mermaid source; GitHub renders it inline. The order is the
one decided on 2026-08-31: the description and the matchmaker are built
first from analyst reasoning; the deal history is opened afterwards to
test the hypothetical pairs; the deal analyser is code and a person
checks a sample.

## 1. The four steps and the loop between them

```mermaid
flowchart TB
  subgraph S1["Step 1 — Analyse the company (every entity, listed or private)"]
    direction LR
    IN1["Sources: SEC filings · CT.gov · FDA · prices · Orange Book · ChEMBL · patents · 13D/13G · reimbursement notices · transcripts and letters (library)"]
    PROF["Company profile as of a date<br/>identity and listing · assets and continuum step (risk → diagnosis → treatment selection → monitoring) · trials and indications · FDA and reimbursement events · financials: cash, revenue, growth, burn · size · relationships (typed, dated) · stakes held and held by others · stated priorities · past deals as buyer"]
    IN1 --> PROF
  end

  subgraph S2["Step 2 — Ontology (how the profile is stored, model-agnostic, P1)"]
    direction LR
    ENT["Entities: company (listed, ADR, private stub) · fund · institution · asset · trial · regulatory event · deal · patent · document"]
    ATT["Attributes: identity · therapeutic · mechanism/modality · sector · stage · financial · IP · price-action · equity_stakes · stated_priorities · assets"]
    REL["Relationships: sponsors · licenses · partners_with · exclusive_commercial_partner · distributes_for · customer_of · holds_stake_in · acquired"]
    EVT["Events: FDA decisions · forward calendar · reimbursement · non-FDA clearance · acquisition announced/closed · stake purchase · takeover interest"]
    OBJ["Objectives O1–O8 and the aspect vocabulary (§3.10)"]
  end
  PROF --> ENT & ATT & REL & EVT

  subgraph S3["Step 3 — Matchmaking (buyer × pattern × candidates)"]
    direction LR
    BUY["Buyer profile: continuum steps covered · data assets · stated priorities · stakes held · partners · cash/stock currency · past-deal pattern"]
    CAND["Candidate profiles: products and continuum step · growth and reimbursement momentum · relationship with the buyer · stake held by the buyer · competing stakeholders · size relative to buyer"]
    MATCH["aspect-match: weighted count of the pattern's aspects present for the pair<br/>mass-exact: therapeutic-area overlap (as-is)"]
    LIST["Ranked pairs with the evidence documents per aspect"]
    BUY & CAND --> MATCH --> LIST
  end
  ENT & ATT & REL & EVT & OBJ --> BUY & CAND

  subgraph S4["Step 4 — Historical analysis (the deal analyser and the forward test)"]
    direction LR
    LIBR[("Research library: announcement filings · press exhibits · 10-K notes · 13D/13G · prior agreements between the pair · transcripts · news; one copy per document, hash-named, indexed")]
    DA["Deal analyser (code): per deal → terms · dated timeline · rationale verbatim · aspects with evidence · comparables"]
    RQ["Review queue: a person checks a sample; precision recorded in the ledger"]
    DOSS[("Deal dossiers, regenerable from the library; corrected through the manual layer with provenance")]
    PAT["Patterns: recurring aspect combinations from dossiers of deals dated ≤ T, with weights"]
    FWD["Forward test: lists generated at each year-end T with information ≤ T; deals announced after T checked → hits and false alarms vs chance; pass mark written before the run (P10)"]
    LIBR --> DA --> RQ --> DOSS --> PAT
  end
  LIST --> FWD
  DOSS --> FWD
  PAT -.patterns and weights feed the matcher, versioned.-> MATCH
  PAT -.new aspects widen the vocabulary.-> OBJ
  DA -.new attributes discovered in deals.-> ATT
  RQ -.documents added by hand.-> LIBR
```

## 2. Worked example on one record (Tempus → Personalis, Ontology v4 §2.5)

```mermaid
flowchart LR
  T1["2023-11<br/>five-year commercialisation agreement + equity investment"] --> T2["2024-08<br/>expansion + $36M more stock via warrants"] --> T3["2024-12<br/>extended to biopharma customers"] --> T4["2025-07<br/>fourth indication added (colorectal)"] --> T5["2026 Q1<br/>Medicare coverage, volume +258% y/y"] --> T6["2026-06/07<br/>takeover interest reported (Merck 13.4%, Tempus 12.5%), +55% run-up"] --> T7["2026-07-20<br/>agreement: $16.25/share, EV $1.5B net of stake, 100% stock with 50% cash option"]
  T7 --> ASP["Aspects present: prior_commercial_relationship (3 y, 3 escalations) · prior_equity_stake (12.5%, built in steps) · continuum_extension (monitoring) · reimbursement_catalyst · buyer_stated_priority_match · competing_stakeholder · consideration_type = stock · target_revenue_growth"]
  ASP --> Q["Matchmaker question for today: which other buyer–candidate pairs show the same aspects, and did such pairs become deals in past years?"]
```

## 3. Rules the picture encodes

1. Step 1 and step 2 are built before step 4 is opened: the profile and the matcher come from analyst reasoning; the deal history tests them (decision 2026-08-31).
2. Every arrow into a dossier field carries a `doc_id` and a span; a fact without a document does not enter (Ontology v4 §3.9).
3. Patterns learned from deals up to a year are tested only on deals after that year (P10).
4. The analyser is code; the person checks a sample and that sample's precision is the number reported (label-QA pattern, `labels.qa_pass`).
