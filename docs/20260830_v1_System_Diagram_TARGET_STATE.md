docs/20260830_v1_System_Diagram_TARGET_STATE.md

# Target-state diagrams — Bioindustry Intelligence Platform

Target state = the intended architecture once the agreed gameplan is
built (Phases 0–3 of handoff v6 §5 item 3c; Models 1, 2, 4). Current
state (as built at commit da29a85) remains in
`20260829_v1_System_Diagram.md/.png/.svg` and is updated as code changes.
Poster: `20260830_v1_System_Diagram_TARGET_STATE.png/.svg`. Tags in the
poster: AS-IS exists today · EXT extended · NEW to build.

## 1. Target data flow

```mermaid
flowchart LR
  subgraph SRC[1 Sources — official, free]
    SEC[SEC EDGAR: submissions · XBRL · 8-K/10-K · Form D · S-3 · 13D]
    EFTS[SEC EDGAR full-text search: 8-K/PR exhibits — goal dates · CRL · readouts]
    FDA[FDA: Drugs@FDA · CRL endpoint · CRL letters · AdCom calendar]
    CT[ClinicalTrials.gov v2: trials · sponsors · primary completion]
    PX[Prices: Yahoo daily bars US + ADR; benchmarks XBI/SPX/baskets]
    OBC[Orange Book · ChEMBL · BigQuery patents]
    LIT[Literature & news: PubMed/Europe PMC · preprints · NIH RePORTER · press wires · abstracts]
    MAN[Manual layer: entities · attributes · templated notes]
  end
  subgraph ADP[2 Adapters + cache]
    A1[sources/* as-is]; A2[calendar adapters: efts · adcom · ctgov completion]; A3[scanning adapters]; A4[manual adapter]
    STORE[(store.py: one HTTP path, bronze cache, manifests)]
    SCHEMA[schema.py: ontology as code + validate]
  end
  SEC & FDA & CT & PX & OBC --> A1; EFTS --> A2; FDA --> A2; CT --> A2; LIT --> A3; MAN --> A4
  A1 & A2 & A3 --> STORE --> BRONZE[(bronze)]
  subgraph PROC[3 Process layer — daily jobs]
    P1[universe · ingest · partners · relationships — global registry incl. ADR + stubs]
    P2[labels + objective labels O1–O8]
    P3[catalyst-calendar daily: EFTS mining → event table; AdCom; CT.gov; close outcomes; reconcile; delays]
    P4[features + price-action attribute group]
    P5[Model 2 daily: run-up · reaction · post-path · crowding · base rates · spillover · ranking · rules]
    P6[horizon-scan daily: ingest docs → extract → resolve → review queue]
    P7[predict: fitted screen ranks · scorecard explains · objective matchers]
    P8[validate · evaluate · report]
  end
  BRONZE --> P1 & P3 & P6; A4 -.manual overrides.-> P4
  subgraph DATA[4 Data — model-agnostic tables P1]
    REG[(entity registry: listed/ADR/stub · funds · institutions)]
    ATTR[(attributes, dated: therapeutic · modality · stage · financial · IP · price-action)]
    EVT[(EVENT TABLE: past FDA actions + forward calendar)]
    REL[(relationships typed · partners · deals)]
    TAB[(trials · financials · prices · benchmarks)]
    LAB[(ma_events + objective labels)]
    MANT[(manual_entities · manual_attributes · manual_notes)]
    SCAN[(scan_documents · scan_entities)]
    GOLD[(gold: panels · catalyst_calendar · ma_predictions · catalyst_ranking · results.csv · scan_candidates)]
  end
  P1 --> REG; P2 --> LAB; P3 --> EVT; P4 --> ATTR & GOLD; P5 --> GOLD; P6 --> SCAN & GOLD; P7 --> GOLD; P8 --> GOLD
  subgraph MOD[5 Model framework — interface · registry · harness]
    M1[Model 1 M&A: fitted screen · scorecard · MASS-exact pairing · objective matchers O3–O8 · baselines]
    M2[Model 2 FDA catalyst price action: event study · M2.1–M2.7 · rules R1–R8]
    M4[Model 4 Horizon Scanning: SciNER + relations · resolution · interest signals]
    M3[Model 3 — unassigned]
    EVAL[evaluation protocol P10: same events & negatives · mean rank · Hits@k · single holdout · result records]
  end
  GOLD & ATTR & LAB --> M1; EVT & TAB & ATTR --> M2; SCAN --> M4
  subgraph REP[6 Central reporting]
    RES[(results.csv: model · version · run date · snapshot hash · inputs · metrics · artefacts)]
    GEN[report generator: templates over gold + results]
    R1[daily catalyst report + catalyst_ranking.csv]
    R2[M&A predictions report]
    R3[horizon scan report + review queue]
    R4[generated ledger → PROJECT_STATUS · paper exhibits]
  end
  M1 & M2 & M4 --> RES --> GEN --> R1 & R2 & R3 & R4
```

## 2. Target daily run (Model 2 product)

```mermaid
flowchart LR
  A[catalyst-calendar] --> B[price refresh incl. ADRs + benchmarks] --> C[attribute refresh §3.2a] --> D[M2.1–M2.6] --> E[M2.7 ranking with attribution] --> F[rules R1–R8 → flags] --> G[daily catalyst report + CSVs + result records]
  H[horizon-scan] -.new entities/stubs.-> C
  M[manual notes & overrides] -.-> C
```

## 3. Gate mapping (what builds each NEW/EXT item)

| Item | Gate |
|---|---|
| schema.py + validate | Phase 0.1 |
| results.csv + report generator | Phase 0.2 |
| framework core (interface, registry, harness) | Phase 0.3 |
| EVENT TABLE + calendar view | Phase 1.4 (F1) |
| EFTS adapter + parser + review queue | Phase 1.5 (F2) |
| AdCom · CT.gov completion · CRL letters · timestamps | Phase 1.6 (F3) |
| catalyst-calendar daily job | Phase 1.7 (F4) |
| price-action attribute group | Phase 2.8 (F5) |
| ADR/stub universe · benchmarks table | Phase 2.9 (F9) |
| manual layer tables + adapter | Phase 2.10 (B) |
| M2.1–M2.3 | Phase 3.11 (F6) |
| M2.4–M2.6 | Phase 3.12 (F7) |
| M2.7 ranking · rules · daily report | Phase 3.13 (F8) |
| objective matchers O3–O8 | after Phase 3 |
| Model 4 S1–S7 | after Phase 3 (or S1 earlier) |
