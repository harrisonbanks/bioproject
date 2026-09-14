docs/20260913_v1_R3_0b_Block_B_Acceptance_Spec.md

# R3-0b Block B: closed acceptance specification

**Date:** 2026-09-13
**Status:** BINDING for Block B once committed. Block A is CLOSED and CERTIFIED
under `docs/20260912_v1_R3_0b_Census_Build_Acceptance_Spec.md` at commit
`de8191fc9b3028f62e47eb526934c4a8c4e03599`; nothing here reopens it.
**Scope:** the Block B analysis stages and the R3-0b closeout commit. Block B
is the decision point that may freeze SEG-v1 and unblock R3-0d, so its
acceptance criteria exist before its results are seen.
**Purpose:** the same purpose as Block A's specification: one closed checklist,
reviewed in one pass, so that results are judged against a fixed standard.

## How this specification is used

1. Every requirement is numbered and carries a severity: **BLOCKER**
   (correctness, reproducibility, evidence integrity, or gate safety),
   **RECOMMENDED** (improves the artifact without affecting those four), or
   **CLEANUP** (comments, wording, naming).
2. A revision is reviewed against the whole list in one pass.
3. Only a BLOCKER forces a new block name and hash. RECOMMENDED and CLEANUP
   items are folded into whatever revision happens next for another reason.
4. A new blocker may be raised after this specification is committed only when
   the implementation violates an invariant already stated here, or when
   inspection reveals a repository or data fact that could not reasonably have
   been known when this was written. In the second case the reviewer says
   explicitly why it was not foreseeable.
5. Block B runs in three stages, each its own block: B1 exact length pass
   (read-only), B2 census report (read-only), B3 closeout commit. B1 and B2
   commit nothing. B3 is the only commit, and it happens only after B2 passes.

---

## A. Input identity

| # | Severity | Invariant |
|---|---|---|
| A1 | BLOCKER | The Block A cache consumed by every Block B stage is `data\exports\segv1_census_BUILD-v5.jsonl` with SHA-256 `02cd6568acd90ddc94fc351ff3c435bb8ca8e1b86badbdcbe73e6c7a0ed9fbda`, hash-gated in the runner before any read. |
| A2 | BLOCKER | The cache header reads `row_count` 6992, `complete` true, `builder_version` `BUILD-v5`, `cache_format_version` `CENSUS-CACHE-v3`, `seg_commit` `81bdfe23e4a2d9defcc76689b89e31473ead0dd0`, `seg_py_sha256` `4b992b38ddca76bdd70c4c428812d2fb8fdadc7a71f3a06c08a2d9e9b24274e1`; each is printed and gated. |
| A3 | BLOCKER | The deployed `src\biointel\seg.py` hashes to `4b992b38ddca76bdd70c4c428812d2fb8fdadc7a71f3a06c08a2d9e9b24274e1` at entry to every stage; a different SEG implementation may not analyse or close this census. |
| A4 | BLOCKER | Every Block B artifact records the input cache hash it was computed from, and every report figure is traceable to that hash. |

## B. Rows are authoritative

| # | Severity | Invariant |
|---|---|---|
| B1 | BLOCKER | Every full-population figure is recomputed from the 6,992 cache rows. Attempt-scoped Block A counters (`compatibility_match`, `slices_absent`, `no_slice`, and the `counters` object in the header) are never used for a full-population claim. |
| B2 | BLOCKER | Every reported count carries its denominator and the population it is over (references, captures, valid slices, or segments), stated explicitly. |
| B3 | BLOCKER | Reference identity is `ref_id`; the shared-capture pair (6,992 references over 6,991 captures) is reported by reference and never collapsed by capture. |

## C. Exact length statistics

| # | Severity | Invariant |
|---|---|---|
| C1 | BLOCKER | Because the certified cache carries `histogram_complete: false`, B1 does not use the cache header histogram to construct full-population percentiles. It recomputes exact segment lengths for every final-cache reference with `slice_valid` true, using the stored capture bytes and the bound SEG implementation, from scratch. Before segmenting any reference, B1 reads the current stored bytes and requires `SHA256(current stored bytes) == row.capture_sha256 == row.capture_id`; a reference failing that equality is not segmented, is named, and blocks `histogram_complete: true`. A segment-count equality is not a substitute for this byte identity. The header histogram may serve only as a diagnostic cross-check, never as an input to the exact distribution. |
| C2 | BLOCKER | B1 reports the number of valid-slice references re-segmented, asserts each recomputed segment count equals that row's cached `segment_count`, asserts the recomputed total equals the cache's authoritative `total_segments`, and derives the complete histogram and every percentile solely from the recomputed lengths. |
| C3 | BLOCKER | B1 writes one artifact under `data\exports` bound to the cache hash, checkpointed atomically, with `histogram_complete: true` only after the full recomputation in C1 and the assertions in C2 have succeeded for every valid-slice reference. |
| C4 | RECOMMENDED | B1 prints a progress gauge with processed count, rate, elapsed and ETA; the runtime is stated from Block A's measured per-reference cost, not guessed. |
| C5 | BLOCKER | B1 prints the SHA-256 of its final artifact in its evidence. The B2 runner hash-gates that exact approved B1 artifact before B2 reads it, and B2 records the artifact hash it consumed in the report, so the B1 to B2 handoff carries a chain of custody. |
| C6 | RECOMMENDED | B1 and the report state the percentile convention used for p25, p75, p90, p95 and p99 (nearest-rank, or a named interpolation rule), because an exact histogram does not by itself determine a percentile value across conventions. |

## D. Absent-slice characterization

| # | Severity | Invariant |
|---|---|---|
| D1 | BLOCKER | All 1,036 references with no SEG Item 1 slice are characterized with mutually exclusive, exhaustive reason categories, each with a count, a denominator and at least one named example reference. |
| D2 | BLOCKER | The 555 `10k_strategy` absences are reported separately from the 481 `investor_day` absences, and the 10-K population is characterized before any freeze decision. |
| D3 | BLOCKER | For every absent slice the report states whether p2 also found no Item 1 for that reference, computed from the row's `p2_len`, so shared absence is distinguished from SEG-only absence. |
| D4 | RECOMMENDED | Reason categories are derived from the capture bytes and the incumbent's own boundary rules (no Item 1 heading, region under the 500-character floor, no Item 1A terminator, form type without an Item 1), not assumed. |

## E. Compatibility

| # | Severity | Invariant |
|---|---|---|
| E1 | BLOCKER | The report states compatibility available, matched and mismatched over 6,992 references from rows, and names every mismatched reference; the expected values from the certified cache are 6,992, 6,992 and 0. |
| E2 | BLOCKER | The report states the count of references where SEG found no Item 1 while p2 did, from rows; the expected value is 0. |
| E3 | BLOCKER | A nonzero mismatch count is a measurement to report, not a stop; only a demonstrated evidence-integrity defect is a blocker. |

## F. SEG quality measurements

| # | Severity | Invariant |
|---|---|---|
| F1 | BLOCKER | The report gives: valid and absent slices by tier; total segments; segments per valid slice mean and median; exact length mean, median, p25, p75, p90, p95, p99, min, max, and the ten largest with their reference ids; coverage-gap slices; segmentation errors; zero-segment slices. |
| F2 | BLOCKER | The bullet-merge proxy is reported as proxy segments over all segments and as references with at least one proxy over valid slices, and is labelled a heuristic proxy, never an error rate. |
| F3 | BLOCKER | Every figure states which population it is over and whether it comes from rows, from B1, or from the store. |

## G. p2 strata

| # | Severity | Invariant |
|---|---|---|
| G1 | BLOCKER | The strata label is `entity_date_pair_has_p2_candidate`, defined as an `(entity_key, stated_at)` pair carrying at least one current-ruleset p2 candidate in the store, and the report states that this pair is not a document identity. |
| G2 | BLOCKER | The report gives the number of references in each stratum with the reference denominator, and the number of distinct pairs with the pair denominator, and never presents a pair count as a document count. |
| G3 | BLOCKER | Segmentation never depends on this classification; the strata are reported over an already-segmented population. |
| G4 | BLOCKER | The store-derived p2 input has an identity of its own: B2 states the exact p2 ruleset identifier it used, computes a deterministic manifest SHA-256 over the canonically sorted `(entity_key, stated_at)` pairs that satisfy that ruleset, and the report carries that manifest hash together with the pair denominator, so the strata are reproducible without freezing the database file. |

## H. Freeze criterion

| # | Severity | Invariant |
|---|---|---|
| H1 | BLOCKER | SEG-v1 may be frozen only if Block B finds no evidence that the 555 ten-K absences, the compatibility results, the coverage-gap count, the segmentation-error count or any other measurement constitutes a correctness defect requiring a SEG-v1 change. |
| H2 | BLOCKER | A large or surprising measurement is not by itself a blocker; it blocks only if it violates a stated invariant of SEG-v1 (the verbatim offset invariant, fail-closed paragraph containment, the ratified bullet limitation, the compatibility contract) or reveals a demonstrated defect. |
| H3 | BLOCKER | The freeze decision is written into the closeout record with the specific measurements it rests on. |

## I. Closeout

| # | Severity | Invariant |
|---|---|---|
| I1 | BLOCKER | B3 runs only after B2 has passed review against this specification. |
| I2 | BLOCKER | B3 commits: the census and closeout record `docs/20260913_v1_R3_0b_Census_and_Closeout_Record.md`; `docs/PROJECT_STATUS.md` at v1.35 marking R3-0b CLOSED, SEG-v1 FROZEN and R3-0d UNBLOCKED; and candidate-to-frozen wording in `src\biointel\seg.py` and `tests\unit\test_seg.py` only if the committed text requires it. |
| I3 | BLOCKER | The closeout record distinguishes the implementation commits that produced the measured behaviour (`a7e4e51` SEG-v1, `81bdfe23` compatibility repair) from the closeout commit that freezes it, and names the certified cache hash. |
| I4 | BLOCKER | If B3 touches code, the full suite and Ruff on the changed files run and are gated; if B3 is docs-only, the docs-only gate applies. |
| I5 | RECOMMENDED | The closeout record carries the measured runtimes of record: 5h35m for the first 3,726 rows and 7h37m51s for the resume. |

## J. Git and no-commit safety

| # | Severity | Invariant |
|---|---|---|
| J1 | BLOCKER | Every stage fetches the remote live, gates the exit code, and requires local HEAD and refreshed origin to equal the declared base before anything is deployed or read. |
| J2 | BLOCKER | Every stage requires zero tracked modifications, zero staged paths and zero non-ignored untracked files at entry and at exit, with the offending paths named on a stop. |
| J3 | BLOCKER | B1 and B2 stage nothing, commit nothing and push nothing; HEAD is gated unchanged at exit. |
| J4 | BLOCKER | B3 stages exactly its declared paths, gates the commit's changed-path set against that declaration, pushes in the same block, and gates local HEAD equal to refreshed origin. |
| J5 | BLOCKER | Every payload ships as a hash-gated file, is re-hashed after deployment, records its evidence to one file in one encoding, and writes an unhandled traceback into that evidence with a distinct exit code. |

## K. Review discipline

| # | Severity | Invariant |
|---|---|---|
| K1 | BLOCKER | Each stage receives one closed blocker list; findings are classified BLOCKER, RECOMMENDED or CLEANUP, and only a BLOCKER forces a new block name. |
| K2 | BLOCKER | No new blocker after this specification is committed except under rule 4 above. |
| K3 | BLOCKER | Block A is not rerun on the basis of any Block B finding unless the finding is a demonstrated Block A integrity defect; `histogram_complete: false` is not such a finding and is resolved by C1. |
