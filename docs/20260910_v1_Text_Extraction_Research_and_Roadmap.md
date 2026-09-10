# docs/20260910_v1_Text_Extraction_Research_and_Roadmap.md

# How other systems extract strategic information from filings — research record and build roadmap

Status: operator-commissioned research record (2026-09-10), binding as a
roadmap input. Web research conducted 2026-09-09/10; citations are the
retrieval trail. Companion decision records:
20260908_v1_Vocabulary_Gap_Commercial_Capability.md (the
commercial_infrastructure category) and the v48 handoff precedent table.

## 0. The question this answers

The operator asked: our extraction is a keyword net over declaration
sentences, not a holistic read of the documents — how does everyone else
capture this information, and what should we build next? Three layers of
practice were surveyed: commercial extraction products, academic financial
NLP, and the M&A-prediction-from-text literature.

## 1. What the field does

### 1.1 Commercial / engineering practice: LLM reading, schema-driven,
### human-verifiable
- The consensus stack reads whole filings with LLMs under a target schema
  ("structured generation"), replacing three approaches that are
  documented failures at scale: manual extraction (slow, error-prone),
  custom parsers (break when formats change), and the SEC's own XBRL
  (custom tags defeat cross-company comparison). Source: dottxt,
  "Extracting Financial Data from SEC 10-K Filings with LLMs"
  (blog.dottxt.ai/extracting-financial-data.html).
- Mature pipelines are CASCADING TIERS: structured lookups first (XBRL
  caches), algorithmic HTML scraping second, LLM+RAG fallback only for
  hard cases — cost and determinism first, model reading last. Source:
  10-K_Metric_Extractor (github.com/ykande1/10-K_Metric_Extractor).
- The standing caveat is printed by practitioners themselves: "LLMs can
  invent information"; reliable results require prompt engineering,
  testing against manually extracted ground truth, and data cleaning
  (dottxt, ibid.). Products mitigate with per-extraction CITATIONS
  (page anchors) so a human can verify each claim — LlamaExtract
  (llamaindex.ai/blog/mining-financial-data-from-sec-filings-with-
  llamaextract); Sensible (sensible.so/extract/10-k) sells exactly this
  as a service.
- Long-document handling: chunking + embeddings + retrieval, section
  isolation by agents, multi-turn comparison (IntuitionLabs,
  intuitionlabs.ai/articles/llm-financial-document-analysis;
  servicesground.com/blog/sec-filing-analysis-ai). Framework papers do
  section extraction -> classification into performance categories ->
  LLM-generated ratings (arXiv:2409.17581).

### 1.2 Academic financial NLP: small supervised classifiers on
### human-labeled sentences
- The dominant pattern for sentence-level meaning in filings is a
  FinBERT-class model fine-tuned on a few thousand expert-labeled
  sentences. Benchmarks: Financial PhraseBank, 4,845 sentences labeled by
  16 finance-literate annotators (arXiv:2006.08097); finbert-tone,
  10,000 manually annotated analyst-report sentences
  (huggingface.co/yiyanghkust/finbert-tone).
- Data efficiency is the headline: FinBERT surpassed prior state of the
  art with as few as ~500 labeled examples, and reaches ~80% accuracy
  around 250 (openreview.net/pdf?id=HylznxrYDr).
- FinAI-BERT (arXiv:2507.01991) is OUR PIPELINE, published: a
  domain keyword lexicon, iteratively refined; lexicon-matched sentences
  provisionally labeled; MANUAL VALIDATION to remove false positives;
  final corpus 1,586 balanced sentences; then a classifier trained on it.
  Weak supervision + human validation is a recognized method, not a
  shortcut.
- Taxonomy-grounded weak supervision scales it: GRAB labels 1.61M
  sentences from 8,247 filings without manual annotation by combining
  model attention, keyphrase signals, and a 193-term taxonomy mapped to
  21 types (arXiv:2509.21698) — the industrial version of our
  category keyword map, with the same validation needs.

### 1.3 M&A prediction from text: similarity and tone, not stated intent
- The canonical text signal is Hoberg-Phillips product-market SIMILARITY:
  measures built from 10-K product descriptions, used to predict targets
  and acquirers (Hoberg & Phillips 2010, via CMU text-regression paper,
  sulawesi.tepper.cmu.edu/pdf/ma_ste_latest.pdf). Complementarity drives
  deals: the probability a deal completes relates to whether the target
  has assets/skills/technologies the acquirer can use (arXiv:2404.07298).
- Text regressions on management's words + financials beat financials
  alone for acquirer prediction (CMU paper, ibid.). News-based linguistic
  features outperform traditional financial indicators for target
  prediction (ScienceDirect S0040162524000660). Bank-merger work finds
  annual-report TONE predicts bidder/target status (ScienceDirect
  S0377221723005982). Patent-similarity work ties technological
  relatedness to deal likelihood (PMC12880743).
- NOTHING in the surveyed record extracts verified STATED PRIORITIES the
  way this platform does. The field measures similarity and tone;
  stated-intent extraction with measured precision and human-adjudicated
  provenance is this platform's differentiated asset, and the
  similarity/tone signals are complements to add, not replacements.

## 2. Where our system stands against each layer

STRENGTHS (ahead of much of the surveyed practice):
- Verification rigor: two-model proposer/dissent triage, human verdicts
  of record, precedent rulings enforced as code and tests, per-row
  provenance, measured precision with Wilson bounds, repair-not-delete.
  Commercial products bolt on citations; we adjudicate.
- A labeled corpus as a byproduct: ~1,700 operator-verified sentence
  verdicts (correct/wrong/relabel with rationale) — larger than the
  training sets the literature says suffice (500-1,586-4,845 range).
- Determinism where it matters: frozen rule versions make measurements
  reproducible; the field's LLM-first stacks cannot re-run yesterday.

GAPS (behind the frontier):
- G1. No holistic read: recall-bound at 54% of documents because only
  declaration-anchored sentences are caught; the field reads whole
  sections with schema-driven LLMs.
- G2. No learned middle tier: every new row costs either regex (brittle)
  or two API calls (money); the field's cheap deterministic classifier
  layer (FinBERT-class) is missing — and we already own its training set.
- G3. No similarity features: the one text signal with an M&A-prediction
  pedigree (product-description similarity) is absent from the matcher.
- G4. Single-source doc-type bias: 10-K Item 1 + investor-day press
  releases; the field also mines risk-factor deltas, MD&A, and footnotes.

## 3. The roadmap (ordered; each stage gated and measured as usual)

R1. (p2, already scheduled) Rule-version bump lands: commercial_
    infrastructure category with rules from banked specimens; negation
    guard + sentence-start capture (Opus/Biogen specimens); boundary-
    anchored extraction keywords; overflow table; fresh per-tier
    measurement through the triage surface.
R2. HOLISTIC EXTRACTION PASS (closes G1): an LLM reads each full Item 1
    (chunked per practice) against the priority schema (categories +
    definitions + precedent rulebook), emits candidate rows WITH verbatim
    span citations; deterministic validators (negation, boilerplate, IP,
    attribution, payload rules) filter; survivors enter the SAME triage ->
    cluster -> operator surface. Measured head-to-head against the regex
    baseline on a blind sample before it feeds anything. Design follows
    industry SOP: schema-driven generation + citations + human-in-loop.
R3. LEARNED MIDDLE TIER (closes G2): fine-tune a FinBERT-class classifier
    on the operator-verdict corpus (sentence -> correct/wrong + category).
    Literature says our corpus size is 3x sufficient. Use it as tier-1
    screener: free, deterministic, versioned like a rule set; API models
    drop to tier-2 for low-confidence rows only. Cuts triage cost per
    sweep by an order of magnitude.
R4. SIMILARITY FEATURES (closes G3): Hoberg-Phillips-style embeddings of
    Item 1 product/business descriptions; acquirer-target similarity and
    complementarity scores as matcher features alongside stated-priority
    aspect matches. This is the literature's proven signal and slots into
    aspect-match v2.
R5. DOC-TYPE EXPANSION (closes G4, opportunistic): risk-factor delta
    mining and MD&A capture ride the existing collector; earnings-call
    transcripts remain the recorded coverage hole pending a free source.

## 4. Binding constraints carried into every stage
- Proposer-only: no LLM output enters a table of record unjudged; the
  triage/cluster/operator surface is the only gate.
- Frozen versions: every extractor (regex, classifier, LLM-prompted) is
  versioned; measurements attach to versions; mid-version edits are void.
- Provenance: reviewer classes (operator / operator-pattern /
  draft-agree / draft-restore) stay separated in every metric.
- Source-or-silence: extracted rows carry verbatim spans and document
  ids; the holistic pass additionally carries span citations per the
  industry pattern.
