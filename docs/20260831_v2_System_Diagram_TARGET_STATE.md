docs/20260831_v2_System_Diagram_TARGET_STATE.md

# Target-state diagram v2 — after Ontology v4 (deal dossiers on a research library)

Supersedes docs/20260830_v1_System_Diagram_TARGET_STATE.md (its .png/.svg
poster is kept as the pre-Ontology-v4 picture until a v2 poster is
rendered). Mermaid source; GitHub renders it inline. Current state as
built: docs/20260831_v2_System_Diagram.md. Tags: AS-IS exists at 79524bd ·
EXT extended by v4 · NEW built by gates L1–L4 and 2.9′ (Implementation
Plan v9).

## 1. Target data flow with the research library and the deal dossier

```mermaid
flowchart LR
  subgraph SRC["1 Sources — official, free; manual where no feed exists"]
    SEC["SEC EDGAR AS-IS<br/>submissions · XBRL · 8-K/10-K · Form D · S-3"]
    EFTS["SEC EDGAR full-text search NEW<br/>8-K / 425 / S-4 / DEFM14A exhibits: goal dates, deal announcements, rationale"]
    OWN["SEC Schedules 13D / 13G NEW<br/>equity stakes: holder, issuer, percent, date"]
    FDA["FDA AS-IS: Drugs@FDA · CRL · AdCom calendar"]
    CT["ClinicalTrials.gov AS-IS"]
    PX["Prices AS-IS: Yahoo daily bars · benchmarks"]
    OBC["Orange Book · ChEMBL · BigQuery patents AS-IS"]
    REIMB["Reimbursement and non-FDA clearances NEW<br/>Medicare / MolDX notices · UKCA · CE-IVD"]
    MANDOC["Manual documents NEW<br/>transcripts · investor letters · analyst notes · news · PDFs"]
    MAN["Manual layer EXT<br/>entities · attributes · templated notes · dossier corrections"]
  end

  subgraph ADP["2 Adapters and cache"]
    A1["sources/* AS-IS"]
    A2["efts adapter NEW (shared by gates 1.5 and L3)"]
    A3["stakes adapter NEW (13D/13G)"]
    A4["library add NEW (url or file, entity, deal, type)"]
    A5["manual adapter (gate 2.10)"]
    STORE["store.py AS-IS: one HTTP path, bronze cache, manifests"]
  end
  SEC & FDA & CT & PX & OBC --> A1
  EFTS --> A2
  OWN --> A3
  REIMB & MANDOC --> A4
  MAN --> A5
  A1 & A2 & A3 & A4 --> STORE

  subgraph BR["3 Store 1 — data/bronze (raw, never edited, P16)"]
    RAW[("api responses + *.meta.json AS-IS")]
    LIB[("library/&lt;sha256&gt;.&lt;ext&gt; NEW<br/>every evidence document, one copy, named by hash")]
  end
  STORE --> RAW
  STORE --> LIB

  subgraph DB["4 Store 2 — data/biointel.duckdb (schema.py enforced, model-agnostic, P1)"]
    direction TB
    REG[("entity registry EXT<br/>listed · ADR · private stubs · funds · institutions; universe widened to diagnostics / tools / data (2.9′)")]
    ATTR[("attributes EXT<br/>therapeutic · stage · financial · IP · price-action<br/>+ equity_stakes · stated_priorities · assets (continuum step)")]
    RELS[("relationships EXT<br/>typed and dated: partners · licenses · exclusive_commercial_partner · distributes_for · customer_of · holds_stake_in")]
    EVT[("event table EXT<br/>FDA past + forward calendar<br/>+ reimbursement_decision · regulatory_clearance_non_fda · acquisition_announced/closed · stake_purchase · takeover_interest_reported")]
    DOCS[("documents · document_links NEW<br/>index of the library: doc_id = sha256, type, publisher, dates, links to entity / deal / event")]
    DOSS[("deal dossier NEW<br/>ma_events (index, deal_id) · deal_terms · deal_timeline · deal_rationale · deal_aspects · deal_comparables<br/>every field carries doc_id + span")]
    MANT[("manual_entities · manual_attributes · manual_notes (gate 2.10)")]
    GOLD[("gold: panels · ma_predictions · match lists with evidence · forward-test results")]
    LED[("run ledger AS-IS: runs · run_params · run_metrics · run_artefacts")]
  end
  RAW --> REG & ATTR & RELS & EVT
  LIB --> DOCS
  MANT -.overrides with provenance.-> ATTR & DOSS & REG

  subgraph PROC["5 Process layer"]
    P1["universe · ingest · partners · relationships AS-IS/EXT"]
    P3["catalyst-calendar daily (gates 1.4–1.7)"]
    ANA["deal analyser NEW (gate L3)<br/>gather documents → library → extract terms, timeline, rationale, aspects → review queue"]
    QA["review queue NEW<br/>random sample + suspicious rows; hand-checked precision to the ledger"]
  end
  RAW --> P1 --> REG
  EVT --> P3
  DOCS & REG & ATTR & RELS & EVT --> ANA --> DOSS
  ANA --> QA -.corrections.-> MANT

  subgraph MOD["6 Model framework — registry, declared inputs, enforcing harness (P2, P6)"]
    TS["target-screen AS-IS<br/>scorecard · fitted"]
    AP["acquirer-pairing EXT<br/>mass-exact AS-IS · aspect-match NEW (gate L4)"]
    ES["fda-event-study AS-IS<br/>daily-bars; announcement reactions for both deal sides"]
    FT["forward test NEW (gate L4)<br/>propose for every buyer at each year-end → hits and false alarms vs deal history, patterns from deals ≤ T tested on deals > T"]
  end
  ATTR & RELS & EVT & DOSS --> AP
  ATTR --> TS
  EVT & PX --> ES
  AP --> FT
  DOSS -.patterns and weights, versioned.-> AP

  subgraph REP["7 Reporting AS-IS/EXT"]
    LEDG["report ledger · report runs · ledger.csv"]
    ML["match lists with the evidence documents per aspect NEW"]
    DR["dossier view per deal NEW"]
  end
  TS & AP & ES & FT --> LED --> LEDG
  AP --> ML
  DOSS --> DR
```

## 2. What is new in one sentence each

1. The research library is the evidence store: every document the platform relies on is kept once, named by its hash, indexed with its type, dates and links, and every asserted fact points back to a document and a passage.
2. The deal dossier replaces the single `ma_events` row as the unit of record for an acquisition; `ma_events` stays as the index.
3. Three new attribute families (equity stakes, stated priorities, assets with continuum step), typed dated relationships, and seven new event classes give the dossier and the matcher what the Tempus record showed they need.
4. `aspect-match` sits beside `mass-exact` under `acquirer-pairing`, hand-built, with declared inputs, and its output lists the evidence per aspect.
5. The forward test is the honesty mechanism: lists are generated with information dated on or before each year-end, then compared with the deals announced after it.

## 3. Gate mapping for the new items

| Item | Gate |
|---|---|
| library/, `documents`, `document_links`, `library add` | L1 |
| dossier tables; `equity_stakes`, `stated_priorities`, `assets`; typed edges; new event classes | L2 |
| efts adapter (shared), stakes adapter, deal analyser, review queue | L3 (efts may land in 1.5 first) |
| `aspect-match`, forward test, match lists with evidence | L4 |
| universe widening, private stubs, new baseline | 2.9′ |
