docs/20260912_v1_Document_Processing_and_Evidence_Architecture.md

# Document Processing and Evidence Architecture Improvement Plan

**Date:** 2026-09-12
**Status:** ARCHITECTURE OF RECORD for the long-term system. Operator-issued.
**Purpose:** Define the long-term document-processing, provenance, adjudication,
dataset, and production-state architecture for the Bioindustry Intelligence
Platform.
**Relationship to R3:** Extends docs/20260912_v1_R3_Recovery_Benchmark_and_Learned_Extraction_Design.md.
It does not replace R3-0c and does not require a platform rewrite before
recovery is complete. The R3 design governs the current experiment; this
document governs the longer-term system. On any conflict about the current
experiment, the R3 design controls.
**Subordinate to:** docs/20260910_v2_Operating_Manual.md, Addendum A and its
errata, and the boot protocol.

---

## 1. Executive summary

The platform should move toward a strict separation between five different
kinds of information: source evidence (what the source actually published);
document structure (how that evidence was parsed into elements, sections and
stable annotation units); machine proposals (what a rule, model or other
extractor proposed); human adjudication (what a reviewer judged about a
specific piece of evidence); and production state (what the platform currently
chooses to expose as an accepted priority, match, score or downstream feature).
These layers must have independent identities and lifecycles.

Governing principle:

> No derived state may be the sole surviving representation of its inputs, and
> no interpretation may destroy or overwrite the evidence from which it was
> derived.

The immediate R3 work already corrects the most serious historical violation.
R3-0c recovers the historical human-label asset; SEG-v1 will create durable
sentence identity; R3-0d will create the immutable adjudication ledger. The
architecture then goes further by making candidate proposals immutable,
representing selection separately from proposal generation, treating production
tables as rebuildable projections, introducing typed identifier namespaces,
linking transformations to structured processing runs, and representing every
training, development and locked dataset with an immutable manifest.

Target shape: source bytes, parsed elements, sections, stable segments,
candidate proposals, human adjudication events and dataset manifests are
immutable and historical; candidate selections, current judgments,
`stated_priorities`, training examples, benchmark outputs, buyer-target
features and downstream hypotheses are derived and rebuildable projections.
The architecture is reached incrementally. The current platform is not
discarded.

## 2. Problem this architecture solves

Historically a human judgment could affect production state without
guaranteeing that the exact evidence judged remained attached to the judgment:
a candidate existed, a human judged it wrong, and the production row
disappeared. The judgment survived; the direct sentence-to-verdict
relationship did not always survive in the primary structured store. The source
filing and contemporaneous worksheets preserved much of the missing
relationship, which materially improved recoverability, but recovery should
never have been necessary.

The architecture instead guarantees a chain from source sentence to candidate
proposal to human judgment to current production projection, in which deleting
or changing the final projection has no effect on the first three layers.

## 3. Research basis

W3C PROV separates entities, activities and agents so a derived object can be
traced to what produced it. OpenLineage distinguishes a reusable job from a
particular run and associates a run with repository, path, branch and commit.
Event sourcing preserves immutable append-only events rather than only current
state, and is recommended selectively where auditability and historical
reconstruction justify the complexity; human adjudication is exactly that case.
Modern document-processing systems preserve element-level structure with
deterministic identifiers derived from content and location. Dataset versioning
is treated as a reproducibility requirement. Large-scale table formats such as
Iceberg illustrate that state changes should create identifiable snapshots
rather than destroying prior state; the principle applies even though the
implementation here is far simpler.

## 4. Core architectural invariants

4.1 **Source immutability.** Admitted source bytes are immutable; a second
download producing different bytes is a new source blob.

4.2 **Transformation immutability.** A parser, section extractor, segmenter or
candidate extractor produces a new derived representation; changing the
implementation does not retroactively change previously measured outputs, and a
semantically different implementation receives a new version.

4.3 **Human judgment immutability.** A judgment is an event. It may be
superseded, corrected, revoked or compensated by a later event. It is never
deleted or rewritten in place.

4.4 **Proposal immutability.** A candidate the extractor produced remains part
of the record even if another candidate wins, it is suppressed, it is judged
wrong, a later extractor would not produce it, its category changes, or the
production table excludes it.

4.5 **Selection is not proposal generation.** Generation answers what the
extractor proposed; selection answers which proposals currently advance. They
are separate representations.

4.6 **Production state is derived.** `stated_priorities` and similar tables are
projections and must be rebuildable; dropping one must not destroy the
information needed to reconstruct it.

4.7 **Evidence precedes interpretation.** No interpretation may destroy the
evidence it came from: not extraction, selection, human judgment, model
prediction, category assignment, deal matching or production suppression.

4.8 **Stable target identity.** Human review attaches to a stable document
segment, not merely to an extractor-specific candidate id.

4.9 **Explicit provenance.** Every material derived object traces to source
evidence, transformation version, run, code version and relevant configuration.

4.10 **Ambiguity is data.** Identity that cannot be established uniquely is
`ambiguous`; identity that cannot be established at all is `unresolved`. Never
guess to obtain full coverage.

## 5. Target processing architecture

Source document, source blob, document elements, section, segment, candidate
proposal, candidate selection, adjudication event, current projection, dataset.
Each layer answers a different question: which filing this is; which exact
bytes were captured; which structural pieces were parsed; what constitutes Item
1; which stable annotation unit exists; what an extractor found interesting;
which proposals a policy advanced; what a human determined; what the system
currently treats as accepted; and which exact evidence and labels an experiment
used.

## 6. Source document and source blob layer

`source_document` carries document id, source system, source native id, CIK,
accession number, form type, filing date, publication date, source URL and
creation time; for SEC filings the accession number is the natural external
identifier. `source_blob` carries blob id, document id, filename, content type,
byte length, SHA-256, capture time, storage path and capture run id. Identity
form `blob:sha256:<digest>`. The SHA-256 is authoritative; filename and
timestamps are metadata.

## 7. Parsed document elements

`document_element` carries element id, blob id, parser version, element index,
element type, start and end offsets, page number, parent element id, text and
text hash, plus the creating run. Types include heading, paragraph, list item,
table, table row, caption, footer and other text. The purpose is not to
duplicate a commercial document AI stack but to retain enough structure to
answer where exactly a piece of text came from. Deterministic element identity
combines blob id, parser version, location and text hash.

## 8. Versioned section extraction

`document_section` carries section id, document id, blob id, section type,
extractor version, offsets, text hash and creating run; for example
`section_type = ITEM_1`, `extractor_version = ITEM1-v3`. A material change to
the section extractor creates a new version rather than silently redefining
historical rows, so `ITEM1-v2` and `ITEM1-v3` outputs remain comparable.

## 9. SEG-v1 and stable annotation identity

`segment` carries segment id, section id, segmentation version, sentence index,
offsets, verbatim text, text hash and creating run. Identity semantics: section
identity plus segmentation version plus offsets or index plus text hash. Human
labels attach to `segment_id`; candidate ids identify machine proposals rather
than the evidence unit. Once a benchmark uses SEG-v1 it is never modified in
place; a material change becomes SEG-v2.

## 10. Candidate proposals

`candidate_proposal` carries candidate id, segment id, extractor name,
extractor version, rule version, category, score, reason code, payload,
creating run and creation time. Every emitted candidate survives. A proposal
records what the machine proposed; it does not mean the proposal is correct,
selected, human-accepted or in production.

## 11. Candidate selection

`candidate_selection` carries selection id, candidate id, selection policy,
policy version, selected flag, rank, selection reason and creating run.
Policies are named and versioned, for example `p2-longest-wins-v1`. This
removes the need for overflow to mean discarded information: losing candidates
remain proposals and selection simply records which advanced.

## 12. Human adjudication as an event stream

`adjudication_event` carries event id, event type, segment id, candidate id,
original candidate id and category, resulting candidate id and category,
verdict, reviewer, review time, annotation rule version, target text and its
hash, display context and its hash, note, superseded event id and creating run.
Event types include `PRIORITY_ACCEPTED`, `PRIORITY_REJECTED`,
`CATEGORY_RELABELED`, `JUDGMENT_CORRECTED`, `JUDGMENT_REVOKED`. A later event
supersedes an earlier one; the earlier event remains, and current state is
calculated from the stream.

## 13. Preserve exactly what the reviewer saw

Every judgment retains both the target segment and the displayed context, which
may include the containing paragraph, neighbouring segments, the section
heading, the candidate category and the extractor explanation. Context never
becomes part of `segment_id`; it records the review conditions so later
apparent inconsistencies can be investigated.

## 14. Binary truth and category truth are separate

"Wrong under category X" does not mean "this sentence is globally not a
strategic priority." Stage A records `segment_id` and `is_priority`; Stage B
records `segment_id`, category and validity, or a category list if categories
prove multi-label. This prevents category-specific rejection from being
converted into sentence-level negative truth.

## 15. Production state as projections

Current candidate judgments, current priority labels, `stated_priorities`,
current category assignments and training examples are derived. The
authoritative chain is source, segment, proposal, adjudication. The acceptance
test for the architecture: can `stated_priorities` be deleted and reproduced
exactly from preserved historical records under a specified projection version?

## 16. Projection versioning

Projection logic changes semantics and is versioned, for example
`SP-PROJECTION-v1`, which defines eligible proposals, how the latest
adjudication is calculated, how relabels are handled, how selection policies
interact, which categories are emitted and how duplicates are handled. Each
production row records its projection version; a policy change produces
`SP-PROJECTION-v2`.

## 17. Typed identifier namespaces

The R-key and library-reference collision proved lexical shape is not identity.
Identifiers carry explicit namespaces: `doc:sec:<accession>`,
`blob:sha256:<digest>`, `section:item1:<id>`, `seg:SEG-v1:<id>`,
`cand:p2:<id>`, `cand:r2:<id>`, `cand:model:<id>`, `ref:<id>`,
`judgment:<id>`, `run:<uuid>`, `dataset:SP-DEV-v1`. Historical identifiers stay
unchanged and are wrapped with `legacy_id_type` and `legacy_id_value`. The
permanent rule: identity semantics come from namespace plus value, never value
shape alone.

## 18. Processing runs as first-class provenance

`processing_run` carries run id, job name and version, start and end times,
status, commit SHA, branch, configuration hash, input and output manifest
hashes, environment fingerprint and command. Jobs include `ITEM1_EXTRACTION`,
`SEGMENTATION`, `P2_EXTRACTION`, `RECOVERY_CENSUS`, `DATASET_BUILD`,
`MODEL_TRAIN`, `MODEL_EVALUATE`. Every derived record carries
`created_by_run_id`, so the system can answer which source, which code, at what
commit, with what configuration, during which run.

## 19. Input and output manifests

A run identifies exactly which files it processed, not merely how many. Input
manifests carry document ids and blob hashes; output manifests carry candidate
ids, segment ids and output hashes. This distinguishes same code with different
inputs from different code with the same inputs, and makes reruns auditable.

## 20. Provenance graph

`provenance_edge` carries derived type and id, relationship, source type and
id, and run id. DuckDB tables suffice; no graph database is required. The model
mirrors W3C PROV's entities and generating activities.

## 21. Evidence files become renders, not primary storage

Historical text evidence files were extremely valuable and are what is
currently saving the label asset, and they continue to exist. Going forward
they are generated from structured records rather than being the only surviving
evidence of what happened: audit output, human review artifact and forensic
backup, with the structured record as the primary representation.

## 22. Recovery evidence remains first-class

Recovered mappings permanently record that they were recovered. Recovered
records are never made indistinguishable from natively recorded future
judgments. Fields include recovery status, recovery source, recovery parser
version, recovery confidence, recovery reason and `evidence_sources[]`, each
entry carrying role, file, SHA-256 and raw reference, so the system permanently
knows that a judgment was reconstructed from two contemporaneous artifacts.

## 23. Dataset manifests

Every material dataset is an immutable named object, for example `SP-TRAIN-v1`,
`SP-DEV-v1`, `SP-LOCKED-v1`, `SP-ACTIVE-v3`. The manifest carries dataset id and
role, creation time, segment version, annotation rule version, source manifest
hash, selection seed, document ids, segment ids, judgment event ids, creating
run and its own hash. A dataset is never defined as a query without preserving
the rows that query returned.

## 24. Training dataset construction

Training sets are projections: adjudication events, resolved sentence truth,
eligibility rules, dataset manifest. `SP-TRAIN-v3` always means exactly the same
examples; a correction creates `SP-TRAIN-v4` rather than altering v3.

## 25. Development and locked benchmarks

Development datasets may support model comparison, threshold tuning, feature
engineering, active learning and error analysis. Locked datasets are excluded
from training, threshold selection, active learning, error inspection and
architecture selection, and their manifest identities are frozen before final
evaluation, including document ids, segment ids, SEG version, annotation
version, judgment event ids and sampling seed.

## 26. Prevent company and year leakage

Filings repeat language across years, so a sentence-random split is not the
primary design. Document-separated splits are the minimum, company overlap is
reported, and company-separated splits are tested where practical. The most
realistic eventual design is prospective: train on information available
through date T and evaluate on events after T.

## 27. Active-learning dataset versions

Each round produces an immutable annotation batch and dataset version, for
example `AL-R1`, recording selection model and version, selection criterion,
source pool, selected segment ids, seed and human judgments; the training
corpus evolves as `SP-TRAIN-v1` plus `AL-R1` equals `SP-TRAIN-v2`.

## 28. Model registry integration

`model_version` carries model id and type, training dataset id, development
dataset id, feature version, threshold, commit SHA, training run id and model
artifact hash, so a model name denotes specific code trained on a specific
dataset and tuned on another rather than merely a file.

## 29. Candidate selection for learned models

The learned model also proposes first: a proposal carries segment id,
extractor, score and possibly no category, and thresholding becomes a selection
policy. Thresholds can then change without rerunning or deleting raw
predictions.

## 30. p2 and learned-channel integration

p2 proposals feed p2 selection and the accepted p2 channel; learned proposals
feed model selection and the incremental channel; the two combine into one
projection while remaining analytically separable, so p2 precision and recall,
incremental precision and recall contribution, and union precision and recall
are all reportable without conflation.

## 31. Current-state rebuild test

Export and hash the production projection, recreate it in an isolated test
database, rebuild it entirely from immutable upstream records, and compare row
for row and hash for hash where deterministic. A projection that cannot be
reconstructed from preserved evidence is an architectural defect.

## 32. Human-review transaction rule

Append the adjudication event and derive the projection in one transaction, or
append and commit the event and rebuild the projection later. Never delete a
production row and then attempt to write review evidence; the durable evidence
write is authoritative.

## 33. Correction semantics

Never update an adjudication event because a reviewer made a mistake: the
original event plus a correcting event, with an effective-state resolver
deciding which controls, following the event-sourcing principle that history
stays immutable while compensating events represent change.

## 34. Recommended package layout

Conceptual separation matters more than a single refactor: `ingest/`,
`documents/` (parse, sections, segmentation), `priorities/` (proposals,
deterministic, selection, replay, projection), `adjudication/` (events,
resolve, review), `recovery/` (artifacts, parsers, resolver, census),
`provenance/` (runs, manifests, lineage, identifiers), `datasets/` (manifests,
build, sampling, splits), `models/`, `evaluation/`. Parse, segment, propose,
select, judge, project, train and evaluate should not be one monolithic
lifecycle.

## 35. Data storage technology

Keep infrastructure simple at the current corpus size: DuckDB for structured
analytical state, raw files on local storage, Parquet where large immutable
tabular artifacts benefit, JSON and CSV for interchange, SHA-256 manifests for
immutability, Git for code and documentation. Do not adopt Spark, Kafka, Delta
Lake, Iceberg, a graph database or a dedicated event-store product without a
measured need.

## 36. What remains from the existing platform

Bronze captures, DuckDB, schema-as-code, deterministic extraction, rule
versioning, the model registry, the run ledger, source provenance, human
review, conservative production acceptance, negative-result documentation, test
discipline, branch and hash gating, p2 as the high-precision incumbent, R3
evidence-first recovery, SEG-v1, and development and locked benchmark
separation. The project is not fundamentally misdesigned; the historical defect
was excessive lifecycle coupling among candidate, human judgment and production
state.

## 37. What R3-0c does now

R3-0c is not broadened into a platform rewrite. Its purpose remains to
establish exactly what historical human-label asset exists and to recover it
without modifying production state: parse contemporaneous evidence first, use
surviving table mappings second, use pre-suppression replay only for unresolved
cases, preserve ambiguity, preserve raw evidence, preserve source hashes,
preserve recovery provenance, and produce the full census. The result becomes
an input to the improved architecture.

## 38. R3-0d as the migration point

R3-0d formalises: the exact judged segment is permanently stored or referenced;
displayed review context is permanently stored or referenced; adjudication
history is append-only; original reviewed and resulting identities are
separate; current state is resolved from adjudication history; production
deletion cannot delete review evidence; recovered historical evidence retains
recovery provenance; future candidate proposals are not destroyed by selection;
selection and proposal generation are separate concepts; every new semantic
identifier has an explicit namespace; every new derived record is attributable
to a processing run; and future corpora use immutable manifests. Some land in
R3-0d itself; the rest are recorded as mandatory follow-on work so the gate
stays bounded. See §57 for the operator's scope ruling on exactly where that
line falls.

## 39. Candidate proposal migration

After R3-0d, introduce a non-destructive proposal store so extractor output
flows to proposals, then selection, then projection. Historical keys are not
rewritten; future candidates use the new model.

## 40. Overflow migration

Overflow becomes explicit selection state: `selected = false` with
`selection_reason = LONGEST_WINS_LOSER`. Historical overflow files remain
recovery evidence. No candidate text disappears.

## 41. Typed-id migration

Historical S and R keys are not rewritten. Fields `identifier_namespace` and
`identifier_value` are introduced, so the same value can be an `R2_CANDIDATE`
or a `REFERENCE` without collision, and new rendered ids use `cand:r2:` and
`ref:` prefixes.

## 42. Run-lineage migration

Review the existing run ledger before building parallel infrastructure; the end
state is that a run identifies job, run id, commit SHA, code version,
configuration, input and output manifests, times and status. Extend rather than
duplicate.

## 43. Dataset-manifest migration

Before R3-1 training, create immutable manifests for at least
`SP-HISTORICAL-RECOVERED-v1`, `SP-DEV-v1`, `SP-TRAIN-v1` and `SP-LOCKED-v1`,
referencing stable segment ids and adjudication events.

## 44. Evaluation architecture

Three forms of validity: extraction validity, measured against fully annotated
Item 1 documents; generalization validity, across filings, companies and years;
and business validity, whether extracted priorities improve downstream M&A
hypothesis quality, eventually tested prospectively. Extraction accuracy and
M&A predictive value are separate scientific questions.

## 45. Schema evolution policy

Any change altering the semantic meaning of stored data is versioned:
`ITEM1-v2` to `ITEM1-v3`, `SEG-v1` to `SEG-v2`, `SP-ANNOT-v1` to
`SP-ANNOT-v2`, `P2-SELECTION-v1` to `P2-SELECTION-v2`, `SP-PROJECTION-v1` to
`SP-PROJECTION-v2`, `SP-TRAIN-v1` to `SP-TRAIN-v2`. A version string is never
silently reused after semantics change.

## 46. Required automated invariants

Locking tests for: source bytes never overwritten; deterministic source hashes;
section outputs attributed to blob and extractor version; SEG-v1 stable
identity; proposal creation never deletes previous proposals; selection never
deletes proposal evidence; rejection never deletes the target segment; relabel
never rewrites the original reviewed category; correction never deletes the
original adjudication event; the production table rebuilds from upstream
evidence; candidate and reference id namespaces cannot collide semantically;
direct historical recovery retains all evidence-source hashes; ambiguous
recovery cannot enter training automatically; locked benchmark ids cannot enter
training manifests; dataset manifests are immutable; model records reference
immutable training manifests; projection versions reproduce deterministic
results on fixed inputs.

## 47. Recovery and disaster-readiness

Periodically prove that important state is reconstructable: can
`stated_priorities` be rebuilt; can current judgments be rebuilt; can every
human-reviewed target be reconstructed; can exact source bytes be identified
for every benchmark example; can the input manifest be reproduced for every
production model; can the commit SHA and configuration be reproduced for every
measured extractor run. Any "no" is a provenance gap.

## 48. Documentation policy

Every major subsystem distinguishes evidence, interpretation, current state,
history, version and provenance, using consistent terminology across schema,
CLI, reports, documentation and review tools.

## 49. Evidence versus logs

A log line such as `JUDGED S123 wrong` is diagnostic evidence. A structured
adjudication event carrying event id, segment id, candidate id, verdict,
reviewer, time, annotation version and target hash is durable system state.
Prefer the structured representation and render logs from it.

## 50. Error-handling philosophy

Malformed evidence is rejected explicitly; ambiguous identity is retained as
ambiguity; unexpected source changes create new versions; inconsistent hashes
stop processing; provenance is recorded before downstream state is accepted; no
best-guess repair silently enters production.

## 51. Migration sequence

Phase 1 finish R3-0c. Phase 2 SEG-v1. Phase 3 R3-0d immutable adjudication and
backfill. Phase 4 proposal and selection separation. Phase 5 typed identities
and structured lineage. Phase 6 immutable dataset manifests. Phase 7 R3 learned
extraction. Phase 8 projection rebuildability. Phase 9 downstream M&A
validation.

## 52. What not to do

Do not rewrite the repository, abandon DuckDB, migrate to a distributed stack
without need, discard historical candidate ids, reinterpret historical
judgments without preserving original actions, force unresolved recovery
mappings to resolve, fold candidate generation and selection back together, use
production state as training truth without adjudication lineage, create
training datasets from mutable queries without manifests, expose model output
directly as accepted priorities, tune against the locked benchmark, or silently
change segmentation or annotation semantics.

## 53. Definition of architectural success

For any accepted strategic priority the system can answer "show me exactly why
this row exists" by reconstructing: current priority row, projection version,
effective adjudication event, candidate proposal, stable segment, Item 1
section, exact source blob; with parallel provenance from proposal to
processing run to extractor version to commit SHA to configuration; and, where
used in ML, from segment and judgment to dataset manifest to training run to
model artifact. No forensic reconstruction from miscellaneous text files should
be required.

## 54. Final architectural model

Immutable source documents, source blobs, versioned parsed elements, versioned
sections, stable segments and immutable machine proposals feed versioned
selection and append-only adjudication; projections produce current accepted
priorities, category assignments, training examples, analytical features and
buyer-target hypotheses. Every arrow is attributable to a versioned
transformation; every durable object has identity; every human decision
survives; every production table is rebuildable; every experiment identifies its
dataset; every published metric identifies its denominator; every ambiguity
remains visible.

## 55. Governing system principle

> Preserve evidence first, preserve decisions second, derive current state
> third. Never allow current state to become the only surviving record of either
> the evidence or the decision that produced it.

## 56. Immediate implication for the R3 program

The R3 sequence remains valid: R3-0c historical evidence recovery, R3-0b
SEG-v1, R3-0d immutable adjudication ledger, R3-0e development and locked
corpus, R3-1 onward the learned recall channel. The change this document
introduces is that R3-0d is the beginning of a broader architectural migration
rather than a patch to `candidate_reviews`. The platform does not restart; it
makes the historical lesson permanent in the architecture.

---

## 57. R3-0d scope ruling (operator, 2026-09-12, binding)

Full `stated_priorities` rebuildability is deferred to architecture phase 8.
R3-0d must instead guarantee rebuildability of the effective adjudication state
from the immutable adjudication ledger and preserved evidence alone. It must
preserve stable segment identity, exact judged evidence and context, original
and resulting identities, append-only correction history, recovery provenance,
and sufficient proposal references for later projection reconstruction. It must
not require proposal and selection separation to be completed in the same gate.
Phase 8 remains responsible for proving that `stated_priorities` itself is a
disposable, exactly reconstructable projection.

Consequences of record:

1. R3-0d's acceptance test is an adjudication-state rebuild: reconstruct the
   effective judgment for every ledger subject from the event stream and
   preserved evidence, and compare against the resolver's state.
2. The §31 production rebuild test moves to phase 8 and is named as a deferred
   item in the R3-0d runbook.
3. The proposal-reference field is the hinge on the forward constraint and is
   populated at backfill time from what recovery establishes, so phase 8 does
   not require a second recovery exercise.

## 58. Interim R3-0c recovery measurement (Levels 1 to 2 only)

Block v57k, 2026-09-12, evidence
`data\exports\20260912_v57k_r30cii_gate_evidence.txt`, HEAD `5eae6b6`.

Interim R3-0c recovery measurement, Levels 1 to 2 only: 4,834 distinct
authoritative reviewed candidate IDs were established. Of these, 2,936 mappings
were recovered through direct historical evidence or surviving exact table
mappings, 1,869 remained unresolved, and 29 were held ambiguous. The 2,936
recovered mappings correspond to 2,308 unique recovered sentence texts. Level 3
extractor replay had not yet run, so 2,936 is a lower bound on final
recoverability and 1,869 is an upper bound on the final unresolved population.

Among mappings currently carrying both sentence evidence and a verdict, there
are 2,277 positive and 677 negative verdict observations. These counts do not
use `recovered_total` as their denominator: verdict-bearing ambiguous mappings
are included, while recovered `unsure` verdicts belong to neither class. The
exact decomposition is deferred to the Level 3 replay census, which will report
each class with its own explicit denominator.

300 distinct authoritative R candidate IDs were measured. No claim is made that
this population equals the disjoint union of the `R2-JUDGED` and worksheet
populations until exact authority-form set overlaps are measured. The same
set-overlap discipline applies to S candidate IDs.

Further measured figures: recovery by source was 2,193 `table_direct`, 548
`judging_evidence_direct`, 118 `worksheet_direct` and 77 `cluster_direct`;
unresolved reasons were 1,779 no-sentence-evidence, 90 no-verdict-evidence and
29 conflicting-sentence-evidence; 423 sentences appeared under multiple
reviewed keys, 19 carried conflicting verdicts and 14 appeared under multiple
categories; 2,492 identifier shape matches were reported as
`unclassified_identifier` and counted toward no recovery total; 176 artifacts
totalling 19,659,684 bytes were consumed, each hashed into
`20260912_v1_r3_recovery_source_manifest.csv`, with sixteen audit bundles in
`20260912_v1_r3_recovery_audit_bundles.json`. Recovery is concentrated by era:
`p2h` holds 3,851 of the 4,834 keys and accounts for 1,639 of the unresolved.

## 59. Level 3 replay gate, required scope

1. Operate only on the unresolved Level 1 and 2 remainder.
2. Reconstruct pre-suppression candidate pools.
3. Reproduce historical longest-wins and overflow identity behaviour.
4. Never overwrite a direct recovery.
5. Attach the historical verdict only after identity is established.
6. Hold ambiguous multi-candidate mappings as ambiguous.
7. Report exactly how many of the 1,869 unresolved become recovered, ambiguous
   or remain unresolved.
8. Rerun the full reconciliation to 4,834 authoritative keys.
9. Report the new unique-sentence count, positive and negative counts with
   explicit denominators, and recovery by era and session.
10. Separately report how many of the 1,639 unresolved `p2h` keys Level 3
    resolves.
11. Report exact authority-form set overlaps for R and S candidate ids.
12. Fix the class-count denominators so `unsure` and verdict-bearing ambiguous
    mappings are exposed separately.
