docs/20260912_v1_R3_Recovery_Benchmark_and_Learned_Extraction_Design.md

# R3 Recovery, Benchmark, and Learned Extraction Design

**Date:** 2026-09-12
**Repository:** `harrisonbanks/bioproject`
**Branch of record:** `jason/refactor`
**HEAD at adoption:** `a4e0f952e9f5d0cc9ed42d433ce010f7d4be0f6a` (`a4e0f95`)
**Status:** DESIGN OF RECORD for the R3 phase. Operator-issued 2026-09-12.
**Supersedes:** every earlier R3 plan, including any plan that trains a
classifier directly from the 4,951 verdict rows and any acceptance test
based on a held-out split of p2-selected candidates.
**Subordinate to:** docs/20260910_v2_Operating_Manual.md, Addendum A and
its errata, and the boot protocol. Nothing here overrides them.

---

## 1. Project purpose

The platform identifies likely biotechnology and pharmaceutical acquisition
targets and likely acquirers. The thesis is that acquisitions become more
predictable when the system combines what a company says it wants with what
other companies actually have. The current text-extraction work is the first
half: extracting genuine strategic priorities from filings.

Strategic signals include intent to acquire or in-license assets; filling
pipeline gaps; expansion into a therapeutic area; commitment to a technology
platform; commitment to a modality or mechanism; commercial infrastructure
expansion; geographic expansion; strategic evidence and data generation;
financial or capital-allocation strategy; and defensive, exclusivity, IP or
lifecycle strategy. The `stated_priorities` substrate feeds buyer-target
matching.

Existing infrastructure covers public-source collection, bronze document
preservation, DuckDB tables of record, schema-as-code, provenance, the model
registry with input enforcement, run ledgers, deal analysis, FDA event
infrastructure, pairing models, aspect matching, manual review surfaces,
deterministic extraction rules, and operator verdict history. The bottleneck
is strategic-intent extraction and its evaluation, not infrastructure.

## 2. Current extraction baseline: p2

The deterministic ruleset of record is `L3-a3-p2`, the production baseline.
Historical operator measurement: 12 correct of 13 judged rows, precision
0.923, Wilson interval approximately 0.667 to 0.986.

p2's strength is precision. Its likely weakness is recall: it depends on
deterministic declaration patterns and almost certainly misses priorities
expressed outside them. True recall has never been measured against a
complete ground-truth Item 1 corpus.

The 0.923 figure answers "of the rows p2 returned, how many were correct."
It does not answer "of all real strategic priorities present in Item 1, how
many did p2 find." The next phase establishes that missing denominator.

## 3. Closed extraction experiments

**R2** had an LLM read Item 1 in large chunks and emit candidates. It failed
because topic relevance was confused with strategic stance; major
false-positive classes were trial execution, routine operating plans,
financing language, historical agreements, risk and contingency language,
and generic future activity. Measured precision approximately 0.169. Closed.

**R2v2** added a stance-first stage requiring forward-looking language and a
first-person corporate subject before LLM classification. It improved
materially but reached only about 0.488 held-out precision, failed its
precommitted stopping criterion, and showed no clear recall improvement over
p2.

The scientific result: forward-looking corporate intent is not the same as
strategically meaningful corporate priority. The remaining judgment boundary
is strategic direction versus routine future corporate activity. All future
learned work targets that boundary.

## 4. Critical repository finding: the review ledger is not yet a training corpus

The previous plan assumed approximately 4,951 current-ruleset verdicts meant
approximately 4,951 ready-to-train labeled sentences. They do not.

`candidate_reviews` stores verdict metadata (review id, candidate id, rule
version, verdict, reviewer, note, timestamp) and does not directly preserve
the judged sentence text. When a p2 candidate was judged `wrong` without a
relabel, `judge()` removed that row from live `stated_priorities`, so the
negatives are not recoverable by a simple join. The p2 `S` key is built from
approximately entity, filing date and category rather than the sentence, so
it is insufficient as permanent sentence identity.

The accurate statement: the project has approximately 4,951 historical
verdict records under the current ruleset, and the number of exact
sentence-level labeled examples recoverable from them remains to be
measured. No model work proceeds on the assumption that all 4,951 are usable.

## 5. The actual schema defect

Production state and adjudication evidence were not sufficiently separated.
Production rows may be inserted, deleted, relabeled, superseded, filtered or
regenerated. A human judgment should be append-only evidence containing the
exact material judged. The defect is not merely that a production row was
deleted; it is that a human verdict was not guaranteed to permanently
preserve the exact sentence and provenance to which it applied. This is
fixed before any additional manual annotation.

## 6. Recovery discovery: contemporaneous evidence exists

`data\exports\` holds a substantial historical record of worksheets, judging
surfaces, clusters, overflow files, miss and probe bundles, and session
evidence, much of it generated contemporaneously with the judging itself.
Where an artifact explicitly contains candidate key, verbatim sentence and
verdict together, it is stronger evidence of what the operator actually
judged than a later reconstruction from present-day code. This changes the
recovery hierarchy.

## 7. Recovery source hierarchy

**Level 1, contemporaneous direct evidence.** Parse historical judging
artifacts first: worksheets, full-surface worksheets, cluster files,
`VERBATIM` records, `JUDGED` records, ruling evidence, overflow outputs,
miss and probe bundles, regeneration evidence, and other operator-facing
output. Where the artifact establishes reviewed key to exact sentence to
verdict, that mapping is direct historical evidence. Formats differ; the
first task is to inspect and classify real formats.

**Level 2, surviving exact database mappings.** Use exact key-to-statement
relationships where a surviving table provides them.

**Level 3, frozen extractor replay.** Only keys unresolved at Levels 1 and 2
proceed to replay, which must recreate the candidate-generation behaviour
that existed when the judgment occurred.

**Level 4, ambiguous or unresolved.** Never guess. `ambiguous` means more
than one plausible mapping remains; `unresolved` means no defensible mapping
can be established. Neither enters the training corpus as a known label.

## 8. Pre-suppression recovery requirement

Recovery must reconstruct pre-suppression candidates. Production logic knows
which keys were judged wrong and suppresses them; applying that suppression
before recovery erases the negatives again.

Sequence: reconstruct the candidate pool under the appropriate frozen
extractor; reproduce the relevant selection logic; reproduce longest-wins
behaviour; reproduce overflow behaviour; establish original candidate
identity; map the historical verdict to that candidate; only afterwards
consider production suppression.

A permanent locking test proves that a historically `wrong` and currently
suppressed S-key still recovers to its original judged sentence.

## 9. Relabel history remains historical

Relabeling can make the resulting production identity differ from the
identity originally reviewed. Recovery stores both: original reviewed key,
original reviewed category, exact judged sentence, original verdict or
action, resulting category, and resulting production key where one exists.
The record is never rewritten as though the operator originally judged the
resulting key.

## 10. Evidence-file recovery parser

R3-0 begins with evidence forensics, not replay. For each real format
encountered: identify how keys are represented; how verbatim text is
represented; how verdicts are represented; whether the key, sentence and
verdict association is explicit; define parser rules; test them against real
specimens; refuse cases that do not establish an unambiguous association.
The parser never infers association from proximity unless the format itself
establishes it.

## 11. Recovery provenance

Every recovered mapping preserves reviewed key, sentence, verdict, original
category, resulting category where applicable, recovery source class, source
filename, source date and session, source artifact hash, parser version,
recovery status, recovery reason, raw evidence reference, and the resulting
stable segment id once SEG-v1 exists.

`recovery_source` classes: `worksheet_direct`, `judging_evidence_direct`,
`cluster_direct`, `overflow_direct`, `bundle_direct`, `table_direct`,
`extractor_replay`, `ambiguous`, `unresolved`. Direct and replayed evidence
remain permanently distinguishable.

## 12. Source artifact hashing

Every artifact used for recovery is content-hashed: SHA-256, filename, byte
length, file timestamp as metadata, and parser version. The SHA-256 is the
authoritative file identity, so a recovered judgment traces to the exact
bytes the parser consumed rather than to a filename. A recovery-source
manifest carries these hashes. Filenames and timestamps alone are never
relied on.

## 13. Raw evidence audit samples

The census includes a representative raw-evidence audit bundle per parser
and source class, preserving source filename, source SHA-256, source date
and session, the exact raw lines used, the parsed reviewed key, the parsed
sentence, the parsed verdict, the parser version, the recovery source class,
and any normalization performed. A future reviewer must be able to inspect
the raw evidence and verify the parser's interpretation. Aggregate counts
alone are not sufficient.

## 14. Recovery rate by date and session

Artifact formats changed across phases: early F1 and F2 era, r9 era, v48
triage and ruling era, p2-era worksheets, R2 and R2v2 evidence. Recovery
quality may differ materially by era.

For each meaningful date or session group report total review keys, direct
recoveries, replay recoveries, ambiguous, unresolved, positive recoveries,
negative recoveries, unique sentences, and recovery rate. This concentrates
replay and forensic effort where it is needed instead of applying it
uniformly.

## 15. Required recovery census

Before any classifier training, report: total historical review rows; total
distinct reviewed keys; latest verdict per reviewed key; review counts by
rule and extractor version; review counts by date and session; S-key count;
R-key count; direct worksheet recoveries; direct judging-evidence
recoveries; direct cluster recoveries; direct overflow and bundle
recoveries; direct surviving-table recoveries; extractor-replay recoveries;
ambiguous mappings; unresolved mappings; recoverable positives; recoverable
negatives; positive recovery rate; negative recovery rate; recovery rate by
S-key and R-key; recovery rate by date and session; recovery rate by
recovery source; unique recovered sentence count; duplicate-frequency
distribution; same sentence under multiple reviewed keys; same sentence
under multiple categories; same sentence receiving both positive and
negative row-level verdicts; same key associated with multiple historical
sentences; verdict-history conflicts; unresolved reason codes; number and
percentage requiring replay; number and percentage recovered directly.

The raw verdict-row count is never presented as effective training-set size
without the unique-sentence count beside it.

## 16. Conflict policy

Row-level verdicts are not automatically sentence-level labels. A sentence
judged wrong under one category may be valid under another. Recovery
explicitly detects same sentence with multiple categories, same sentence
with different verdicts, same sentence with relabel activity, and same
sentence across different extractor versions. These are never collapsed into
a binary sentence label without a documented resolution rule. For Stage A
training, a sentence receives a global label only when the evidence supports
that interpretation; category-specific rejection and sentence-level
rejection are not equivalent.

## 17. Immutable adjudication ledger

Before any new manual review, add a permanent append-only adjudication
representation preserving: exact target sentence; stable `segment_id`;
document id; capture id where applicable; source offsets; sentence index;
entity key; filing date; candidate id; original category; resulting category
if relabeled; extractor version; rule version; verdict; reviewer; note;
timestamp; annotation-definition version; and displayed context or context
reference where relevant.

Standing invariant: a human judgment may change production state, but it may
never delete or overwrite the evidence that was judged. A unit test enforces
this. No additional manual annotation occurs until this protection exists.

## 18. Historical backfill

After the census and the new schema exist, backfill all unambiguously
recovered judgments, preserving historical provenance, direct versus
replayed recovery source, original reviewed category and key, and resulting
category and key where relevant. Ambiguous stays ambiguous; unresolved stays
unresolved. The backfill count is never forced to equal the historical
review count by guessing; census and backfill reconcile exactly by status.

## 19. Stable sentence identity: SEG-v1

Every Item 1 segment carries document id, capture id where applicable, Item
1 slice identity, segmentation version, start offset, end offset, sentence
index, verbatim sentence, normalized text as auxiliary data only, text hash,
and a stable `segment_id` derived from immutable provenance such as document
or capture identity plus segmentation version plus offsets plus text hash.
The construction is documented and tested. `candidate_id` remains provenance
but is no longer the only identity.

## 20. Deterministic full-Item-1 segmentation

Build deterministic full-Item-1 segmentation before benchmark annotation.
Tests cover real corpus pathologies: abbreviations, decimal points,
headings, bullet debris, broken HTML and text extraction, table fragments,
sentence-start anomalies, punctuation irregularities, long legal clauses,
malformed fragments, repeated whitespace, quotations and section boundaries.

The goal is not linguistic perfection but deterministic, versioned
annotation units whose identity does not change during an evaluation
campaign. Once SEG-v1 is used for a frozen benchmark it is never edited in
place; a materially changed segmenter becomes SEG-v2.

## 21. Segmentation census

After SEG-v1 exists, report eligible documents, documents with valid Item 1
slices, total segments, segments per document, median, mean, percentile
distribution, the large-document tail, p2-positive document counts and
p2-zero document counts. Manual annotation burden is not estimated before
this measurement exists.

## 22. Positive-class definition

The primary question: does this sentence state a meaningful strategic
direction or intended strategic action of the company?

Potential positives: acquiring or in-licensing assets; filling a pipeline
gap; entering or prioritising a therapeutic area; expanding a technology
platform; pursuing a modality or mechanism; building commercial
infrastructure; entering or expanding a geography; strategic data and
evidence generation; strategically meaningful financial or asset-allocation
actions; defensive, IP and lifecycle strategy.

Potential negatives, being forward-looking but routine: expected R&D expense
growth; generic capital-raising statements; planned conference
presentations; routine trial execution; ordinary regulatory steps; routine
business operations; historical transactions; risk disclosure; conditional
possibilities; generic descriptions of what the company does.

The definition originates from the business objective and ontology. R2, R2v2
and p2 specimens serve as positive, negative and borderline examples and
never define the class by themselves.

## 23. Annotation-rule versioning

The annotation definition is itself versioned, for example `SP-ANNOT-v1`. A
material change creates a new version, documents the reason, identifies
affected development annotations, and re-annotates them as needed. The
semantic target is never changed silently mid-experiment. The locked
benchmark uses one frozen annotation definition.

## 24. R3 objective

The obsolete question was whether a learned classifier can replace p2. The
actual question is whether a learned method can recover additional true
strategic priorities that p2 misses without materially reducing the
precision of the combined feed.

The first production design to test is additive: p2 accepted priorities
union learned-model additions from outside p2. The learned layer targets
p2's blind spots and does not need to reapprove or replace p2's output to
prove value.

## 25. Why historical p2 verdicts are not enough

Recovered p2 judgments are selection-biased: every sentence in them was
selected because p2 already considered it candidate-like. A classifier
trained only on that corpus has not seen the ordinary Item 1 sentences it
would meet when searching beyond p2. Recovered judgments are valuable seed
training data, not a representative production-distribution training set and
not an unbiased acceptance benchmark. Training must eventually include
ordinary p2-missed Item 1 text.

## 26. Why a held-out split of p2 candidates is not the acceptance test

Such a split answers whether the model reproduces human judgments on
p2-selected sentences, which is at best an internal diagnostic. It does not
answer whether the model finds priorities p2 misses. The previous R3-1 and
R3-2 acceptance design based on held-out historical p2 rows is obsolete.

## 27. Benchmark purpose

The benchmark must answer what real strategic priorities exist in a complete
Item 1 section and which ones each method found. That requires annotation
outside the candidate distribution p2 generates.

## 28. Permanent benchmark unit

Complete Item 1 sections with every frozen SEG-v1 unit labeled. A simple
random sentence sample is not the permanent recall benchmark: priorities are
rare and p2 selects at document and category level with longest-wins logic,
so a random sample gives a weak and unrepresentative recall denominator.
Random sampling remains appropriate for training and survey estimation.

## 29. Development corpus versus locked benchmark

**Development corpus:** fully annotated complete Item 1 sections, reusable
for refining the annotation rule, prevalence, p2 recall, false-negative
examination, training design, threshold selection, model comparison, active
learning, error analysis and benchmark sizing. Never part of the locked
benchmark.

**Locked benchmark:** separate documents, frozen independently. No text from
them enters historical-recovery training exports, training, threshold
tuning, active learning, feature selection, error analysis, or parser and
model debugging. Their labels are created only after the final challenger
and adoption rule are frozen.

## 30. Locked documents selected early, annotated late

Freeze locked document identities before model development so they cannot be
cherry-picked; do not annotate them immediately and rely on the operator not
remembering. Sequence: select and freeze; exclude from training and
development; develop elsewhere; freeze the final model and thresholds;
freeze the adoption rule; then annotate the locked documents; run the final
comparison.

## 31. Sampling requirements

Development and locked documents cover meaningful variation: large
pharmaceutical companies, small clinical-stage biotechnology companies,
older filings, newer filings, different writing styles, documents where p2
finds priorities, and documents where p2 finds none. Documents are never
selected after seeing whether they are unusually rich in strategic language.
Selection is reproducible, stratified and randomised.

## 32. Benchmark size is determined by positives, not filing count

Filing count is not the relevant sample size. The denominator for recall is
the number of true strategic-priority positives. Use the development corpus
to estimate prevalence, p2 recall and variance across document types, then
determine how many complete locked documents yield enough true positives
that confidence intervals cannot plausibly reverse the adoption decision.

## 33. Annotation context

The atomic label stays sentence-level, but the operator is shown enough
context to judge meaning: target sentence, previous sentence, next sentence,
and the containing paragraph where practical. The exact target is stored
separately from displayed context and contextual text is never merged into
the target label identity. This preserves reliable human judgment,
sentence-level model experiments, and later context-aware models if
justified.

## 34. Annotation consistency

Human labels are a measurement system and are tested. A frozen random subset
is blindly re-annotated without viewing the original decision. Report
priority versus non-priority agreement, agreement among sentences marked
positive in either pass, and category agreement among positives. Overall
accuracy alone is not relied on because negatives dominate. A second
knowledgeable annotator on a smaller independent subset is desirable where
feasible. Poor agreement means the definition is too unstable to support
narrow model comparisons.

## 35. Training data after recovery

The training corpus combines unambiguously recovered historical judgments,
ordinary Item 1 sentences from separate non-benchmark documents,
development-derived examples where the experimental design permits, and
active-learning additions. Locked-benchmark material is never included.

## 36. Train and test grouping

No random sentence-level split. Document-level separation at minimum.
Company overlap is reported, because annual reports repeat language across
years and leak even across separate filings. Stricter company-level
separation is tested as a robustness check where practical.

## 37. Active learning

After the initial model exists, run it over unlabeled p2-missed Item 1 text
and surface low-confidence cases, decision-boundary cases, likely positives,
examples unlike existing training data, and diverse uncertain cases. The
operator labels small batches; labels append to the immutable ledger; the
model retrains; development performance is remeasured; the loop repeats
until gains flatten or the annotation budget is reached. Bulk random
negative labeling is avoided.

## 38. Model build order

**Model 1, TF-IDF plus logistic regression.** Built first: scikit-learn is
already declared, no new package is required, training is local and free,
the implementation is transparent, and it establishes how much of the
boundary is simple lexical structure. It is the baseline every more complex
method must beat.

**Model 2, SetFit.** Tested only after the simple baseline, with a candidate
starting embedding such as `all-MiniLM-L6-v2`. It must demonstrate measured
value before its dependency is adopted.

**FinBERT-FLS.** Tested as an optional signal or upstream comparison. Its
task is forward-looking financial language detection, related to but not
identical with strategic-priority classification. It is not a mandatory hard
filter unless development evidence shows it improves the full tradeoff.

**Reserved models.** SEC-BERT, ModernBERT, longer-context transformers and
other complex architectures wait for a measured failure mode that justifies
them.

## 39. Model architecture under test

Incumbent channel: p2 continues emitting accepted high-confidence rows.
Recall channel: a learned model examines text p2 did not select and proposes
additional priorities. Combined feed: the union. The learned layer is
evaluated on incremental contribution, not on reproducing p2.

## 40. Development evaluation

On development documents compare at minimum p2, TF-IDF with logistic
regression, SetFit if warranted, FinBERT-FLS-assisted variants if warranted,
and the additive union. Measure precision, recall, F1 or F-beta as secondary
summaries, model-added true positives, model-added false positives, p2 false
negatives recovered, and false-negative classes still missed. The locked
benchmark is never used for optimisation.

## 41. Final locked evaluation

Before opening locked labels, freeze the training dataset version, model
architecture, fitted model, preprocessing, thresholds, candidate-generation
logic, p2 version, segmentation version, annotation-rule version, evaluation
code and adoption rule. Then annotate the locked benchmark and run the
comparison once.

Report separately: p2 alone with precision, recall and confidence intervals;
learned additions with number proposed, true positives, false positives,
incremental precision and incremental recall contribution; and the combined
union with precision, recall, recall gain versus p2 and confidence
intervals. The learned layer cannot hide poor precision behind p2's output.

## 42. Adoption rule

The historical 0.923 is not the formal comparator, having come from a
different evaluation population; p2 and the challenger are measured on the
same locked benchmark. Before locked annotation and results, precommit the
minimum acceptable combined precision, the minimum required recall
improvement, and the minimum acceptable incremental precision for learned
additions. Values are determined from business utility, development results,
expected review burden and benchmark uncertainty. Thresholds are never
chosen after seeing locked performance.

## 43. Stage B deferred

Stage A is strategic priority versus not strategic priority. Category
classification waits for Stage A to succeed, and is not assumed to be
ordinary nine-way multiclass: actual schema and extractor behaviour is
inspected first, and if one sentence can legitimately carry multiple
categories, Stage B is multi-label.

## 44. Corpus percentage issue

The disputed "46 versus 54 percent of documents produce nothing" correction
is not published as established fact. Multiple denominators circulate: all
collected 10-Ks, p2-eligible filings, valid Item 1 slices, documents
actually processed, and documents producing one or more rows. R3-0 measures
every numerator and denominator directly, and only then is documentation
corrected. An inferred percentage never becomes a finding.

## 45. R3-0a: annotation definition and experimental design

Purpose: freeze what is being measured before building the measurement
system. Deliverables: the strategic-priority annotation rule with its
version; positive definition; negative definition; positive, negative and
borderline examples; context-display policy; sampling protocol; development
and locked separation; benchmark-selection protocol; re-annotation
consistency protocol; and the adoption-rule template. Final numerical
adoption thresholds are not filled from locked results, and the disputed
corpus correction is not committed.

## 46. R3-0c: historical verdict recovery census

Step 1, artifact manifest: for every source file record path, filename, byte
length, timestamp metadata, SHA-256 and format or parser class.
Step 2, direct evidence parsing: recover only explicit key, sentence and
verdict mappings.
Step 3, surviving table mapping: use exact retained records where possible.
Step 4, pre-suppression replay: replay the frozen extractor only for
still-unresolved keys, never applying verdict suppression before recovery.
Step 5, conflict analysis: duplicate key mappings, multiple sentences per
key, same sentence across multiple categories, contradictory verdict
histories, relabel chains.
Step 6, census: print all required statistics.
Step 7, date and session breakdown.
Step 8, audit specimens for every parser and source class.
Step 9, reconciliation: every historical review row and key ends in a named
status: directly recovered, table recovered, replay recovered, ambiguous, or
unresolved. No disappearing records.

## 47. R3-0c implementation requirements

Core recovery methodology lives in version-controlled code with tests and a
CLI entry point so the census is reproducibly rerunnable; only generated
census files live under ignored `data/`. Tests include: direct evidence
parser specimen; historically wrong and suppressed key still recoverable;
longest-wins recovery; relabel preservation; R-key exact statement recovery;
conflicting direct evidence held as conflict; multiple possible replay
candidates held as ambiguous; source hash recorded; no guessing fallback;
and the same raw artifact reproducing the same parsed mapping.

## 48. R3-0b: SEG-v1

Deliver the deterministic segmenter, its version constant, stable segment
ids, source offsets, sentence indices, text hashes, tests on real malformed
filing specimens, and the population segmentation census. Once frozen for
annotation, SEG-v1 is not edited.

## 49. R3-0d: immutable adjudication ledger

After SEG-v1: add the permanent adjudication table and schema; increment the
schema version; route every future review through it; prevent evidence
deletion; preserve relabel history; store the exact target sentence, context
reference and immutable provenance; backfill all recoverable historical
reviews; and preserve recovery source and status. Tests prove production
deletion cannot delete adjudication evidence. `python -m biointel validate`
passes against the new schema. Backfill totals reconcile exactly to census
statuses. No new operator review before this gate passes.

## 50. R3-0e: sample selection and development annotation

Create reproducible strata; generate a randomised ordered candidate list;
freeze development document ids; freeze locked benchmark ids; exclude locked
documents from all training; annotate development documents only; measure
positive prevalence; measure p2 recall for the first time; and estimate
final locked sample requirements. Locked documents are not annotated yet.

## 51. R3-1: simple learned baseline

Build TF-IDF plus logistic regression. Train on recovered historical
judgments, representative ordinary Item 1 examples, permissible
development-derived examples, and active-learning additions. Stage A only.
Evaluate on development data only.

## 52. R3-2: stronger learned models if justified

Only if the simple model shows useful incremental recall: test SetFit with
MiniLM; optionally test FinBERT-FLS as feature or filter; compare on the
same development corpus; and measure whether complexity creates real
incremental value. No model is adopted for being newer or more
sophisticated.

## 53. R3-3: final locked benchmark

Freeze the final system, thresholds and adoption rule; annotate the locked
benchmark; run p2; run the learned addition layer; compute the union;
calculate precision, recall and confidence intervals; and apply the adoption
rule once. If it passes, adopt. If it fails, document R3 as a measured
negative result and retain p2. Either result is useful.

## 54. Manual operator workload

The system automates artifact discovery, historical recovery, joins,
deduplication, hashing, segmentation, worksheet creation, sampling, metric
computation, model training, active-learning candidate selection and final
evaluation.

The operator's manual work is limited to reviewing prepared sentence and
context units; choosing strategic priority or not; assigning categories to
positives when required; judging small active-learning batches; performing a
later blind re-annotation subset; and approving the precommitted adoption
rule. The operator is never asked to manually reconstruct historical
evidence.

## 55. Coding-session baseline of 2026-09-12

HEAD `a4e0f952e9f5d0cc9ed42d433ce010f7d4be0f6a`; branch `jason/refactor`;
160 commits; `pytest --collect-only -q` 346 tests collected; advisory suite
342 passed and 4 failed, all four in `tests/unit/test_stakes.py` from an
unset `BIOINTEL_USER_AGENT`; ruff exactly three pre-existing findings;
source tree 56 files and 25,983 lines; tests 23 files and 7,796 lines;
container Python 3.12.3 against a project requirement of 3.13 or later, so
the package was not installed and tests ran advisory under `PYTHONPATH=src`;
`data/` gitignored and absent from the clone.

These are that session's baseline facts, not permanent project constants.
The clone is never used to invent database measurements that require the
operator's local `data/`.

## 56. Repository and operating protocol

Branch of record `jason/refactor`; clone access follows the boot protocol
and the artifacts-only rule thereafter; measurements attach to frozen
versions; measured rulesets are not edited in place; human verdicts govern
table-of-record inclusion; machine output never silently enters production;
provenance remains recoverable; ambiguous cases are held rather than
guessed; negative results are documented and closed; bug fixes require code
plus locking test plus written rule; and code does not begin until the
scoped gate is approved. Nothing in this design overrides the Operating
Manual or its addenda and errata.

## 57. Documentation discipline

Throughout R3: distinguish measured facts from estimates; state no recovery
rate before the census; never state training-set size as verdict count;
state no annotation workload before the SEG-v1 census; state no benchmark
size before development prevalence; claim no model superiority before locked
evaluation; do not state that nothing was lost until recovery is measured;
and give no unsupported effort estimates. Unknowns remain unknown until
measured.

## 58. Known facts

p2 is the current high-precision production baseline; p2 true recall is
unknown; R2 failed; R2v2 failed; forward-looking language alone is
insufficient; `candidate_reviews` did not directly preserve all judged
sentence text; wrong rows could disappear from the live production table; p2
S-keys are inadequate as permanent sentence identity; historical evidence
artifacts exist locally in substantial quantity; those artifacts may
directly preserve much of the key, sentence and verdict mapping; the
historical evidence is parsed before replay is assumed necessary; and no new
annotation occurs until the adjudication schema is repaired.

## 59. Unknowns that must be measured

Direct evidence recovery rate; negative-example recovery rate;
positive-example recovery rate; replay requirement; ambiguous mapping count;
unresolved count; unique recovered sentence count; duplication rate;
recovery quality by era; same-sentence conflict frequency; exact
current-ruleset effective training-set size; true p2 recall;
strategic-priority prevalence; segments per Item 1; manual annotation
burden; required locked benchmark size; TF-IDF performance; SetFit
incremental value; FinBERT-FLS incremental value; learned-layer incremental
precision; learned-layer recall contribution; and final impact on M&A
pairing. Guesses are never substituted for these measurements.

## 60. Immediate task

Not classifier training. R3-0 historical evidence recovery and preservation
foundation: inspect the real artifact formats under `data\exports`, build
the artifact manifest and hashes, and determine how many historical
judgments map directly to the exact sentence the operator saw. Only
unresolved cases proceed to replay.

## 61. Immediate decision rule

No SetFit code. No FinBERT integration. No model acceptance testing. No new
large-scale operator annotation. First establish what historical labeled
asset exists, how much is directly recoverable, how much requires replay,
how many unique positive and negative sentence examples survive, where
conflicts exist, and how all future judgments will be preserved immutably.

## 62. One-line objective

Recover and permanently preserve the historical human-label asset, build the
first unbiased full-Item-1 evaluation substrate, and only then test whether a
learned additive extractor can recover true strategic priorities that p2
misses without materially degrading precision.

---

# Appendix A. Amendments of 2026-09-12 (operator rulings, binding)

## A1. Identifier semantics

A1.1 The source-aware identifier rule applies to all candidate ids, not only
R-keys. No semantic meaning is assigned to an `S...` or `R...` token from
lexical shape alone.

A1.2 Candidate-key counts come from authoritative fields and record forms:
the worksheet `key` column, `JUDGED <key>`, `R2-JUDGED <key>`, or another
explicitly documented candidate-key position.

A1.3 Raw occurrences and distinct authoritative candidate ids are reported
separately. An occurrence count is never presented as agreement with a
verdict count of record unless distinct authoritative ids have been measured
after deduplication.

A1.4 Bare regex matches that cannot be semantically classified are reported
as `unclassified_identifier` and contribute to no S-key or R-key recovery
count.

A1.5 A locking test proves that an R-shaped library `ref_id` and an R-shaped
candidate id remain in separate namespaces despite identical lexical form.

## A2. Annotation rule (folds into `SP-ANNOT-v1`)

A2.1 A positive does not require a proper-named object such as a named
disease, asset, modality or geography. It requires a discernible strategic
object, direction, capability, market, portfolio action or strategic domain.
"We intend to expand our commercial capabilities" can qualify; "we intend to
grow our business" does not, lacking content sufficient to establish a
meaningful strategic direction.

A2.2 `financial` positives require a deliberate strategic capital-allocation
or capital-structure direction. Generic financing need, runway language,
statements that additional capital may be required, and ordinary fundraising
possibility are negative. Prioritising acquisitions, debt reduction,
repurchases, divestitures or another identifiable capital-allocation
strategy can be positive.

A2.3 Repeated year-over-year language stays positive in each filing if it
still expresses a current strategic priority in that filing. Repetition
alone makes a statement neither false nor non-strategic. A repeat or
boilerplate indicator is preserved separately, and evaluation is protected
from leakage by document-level and company-level splitting.

## A3. Benchmark design

A3.1 Numerical stratum weights and p2-zero oversampling are not chosen
before the population is measured; R3-0b and the SEG-v1 census first report
the population by document type, year, p2-zero status and available company
characteristics.

A3.2 The benchmark may deliberately oversample p2-zero documents because
that stratum is especially informative about missed recall. If it does,
stratum-specific metrics are reported and any population-level aggregate is
computed with frozen population weights. An oversampled raw aggregate is
never presented as representative population performance.

A3.3 No large-pharma versus clinical-stage size threshold is invented now.
The reproducible filing-time and company fields that actually exist are
inspected first, the simplest defensible stratification is proposed from
available data, and it is documented before sampling.

A3.4 Filing-year bands are determined from the observed corpus distribution
so strata are not arbitrarily sparse. Bands are never chosen for symmetry.

A3.5 The final annotation budget is not set before SEG-v1 provides sentences
per Item 1 and development annotation provides prevalence. The final
benchmark is sized primarily by true positives and the resulting confidence
intervals.

A3.6 A second annotator is desirable but not required to proceed. The
minimum reliability check is the operator's blind re-annotation of a frozen
random subset. A qualified second annotator, if available, judges a smaller
independent subset and is reported separately.

## A4. Adoption rule

A4.1 The three R3-3 numerical thresholds remain intentionally unset. They
are frozen after development results establish the realistic precision and
recall tradeoff, and before locked-benchmark annotation and results.

## A5. Execution order

A5.1 Commit the design of record, the revised annotation rule, the revised
benchmark design, the PROJECT_STATUS update and supersession notes under the
docs-only gate.

A5.2 Then build R3-0c-ii from the measured artifact formats.

A5.3 R3-0c-ii remains evidence-first: direct historical evidence, then
surviving exact mappings, then pre-suppression extractor replay, then
ambiguous or unresolved.

A5.4 Preserve source SHA-256, parser version, raw evidence, recovery source,
era and session, original reviewed identity, resulting identity, and an
explicit reason code.

A5.5 Produce recovery by era and session, and deterministic audit bundles.

A5.6 No classifier work and no new manual annotation yet.

A5.7 Proceed without further design questions unless measured evidence
reveals a genuine ambiguity this design cannot resolve.
