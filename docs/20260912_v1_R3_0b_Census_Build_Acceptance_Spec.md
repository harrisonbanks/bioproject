docs/20260912_v1_R3_0b_Census_Build_Acceptance_Spec.md

# R3-0b Block A: closed acceptance specification

**Date:** 2026-09-12
**Status:** BINDING for the remainder of Block A once ratified.
**Scope:** the census build script and its PowerShell gate only. Block B has
its own specification and is out of scope here.
**Purpose:** replace incremental fault discovery with one closed checklist, so
that later revisions are judged against a fixed standard rather than against a
standard that grows each round.

## How this specification is used

1. Every requirement below is numbered and carries a severity: **BLOCKER**
   (correctness, reproducibility, evidence integrity, or gate safety),
   **RECOMMENDED** (improves the artifact without affecting those four), or
   **CLEANUP** (comments, wording, naming).
2. A revision is reviewed against the whole list in one pass.
3. Only a BLOCKER forces a new block name and hash. RECOMMENDED and CLEANUP
   items are folded into whatever revision happens next for another reason, and
   never cause churn on their own.
4. A new architectural blocker may be raised after this specification is
   ratified only when the implementation violates an invariant already stated
   here, or when inspection reveals a repository fact that could not reasonably
   have been known when this was written. In the second case the reviewer says
   explicitly why it was not foreseeable.

---

## A. Git and precondition safety

| # | Severity | Invariant |
|---|---|---|
| A1 | BLOCKER | Local HEAD equals the declared baseline before anything is deployed or read. |
| A2 | BLOCKER | The remote is fetched live and its exit code gated, then `origin/<branch>` is compared to the same baseline; a stale tracking ref may not satisfy this. |
| A3 | BLOCKER | Branch equals the declared branch. |
| A4 | BLOCKER | Zero tracked modifications at entry. |
| A5 | BLOCKER | Zero non-ignored untracked files at entry, checked before the expensive walk, with the offending paths named. |
| A6 | BLOCKER | Files this block depends on but does not change (`priorities.py`, `recovery.py`, `seg.py`, `test_seg.py`) are hash-gated as unchanged at entry. |
| A7 | BLOCKER | Every download is hash-gated before deployment, and every deployed file re-hashed after copy. |
| A8 | RECOMMENDED | The evidence file records the observed values for all of the above, not only pass or fail. |

## B. Corpus and reference identity

| # | Severity | Invariant |
|---|---|---|
| B1 | BLOCKER | Reference ids are unique across the walk; a duplicate aborts before any certification, naming the id. |
| B2 | BLOCKER | The eligible population comes from the shared iteration primitive, never from a second implementation of corpus traversal. |
| B3 | BLOCKER | Entity key, filing date and tier are recorded per reference, because Block B strata depend on them. |
| B4 | RECOMMENDED | The walk is single-pass; a separate manifest pass is not run over the same corpus. |

## C. Capture byte identity

| # | Severity | Invariant |
|---|---|---|
| C1 | BLOCKER | Capture identity is the SHA-256 of the stored bytes, never file size or mtime. |
| C2 | BLOCKER | A rebuilt row reads the capture bytes once, hashes those exact bytes, and decodes the same bytes for segmentation. |
| C3 | BLOCKER | Disagreement between the pre-read hash and the bytes actually segmented invalidates that row and blocks certification. |
| C4 | BLOCKER | A byte hash that does not equal the content-addressed `capture_id` invalidates that row and blocks certification. |
| C5 | BLOCKER | An unreadable capture is recorded as its own evidence-integrity category, distinct from an invalid Item 1 slice, and carried into the evidence for Block B's policy decision. |
| C6 | RECOMMENDED | The real I/O cost per reference is stated in the header rather than understated. |

## D. Manifest construction

| # | Severity | Invariant |
|---|---|---|
| D1 | BLOCKER | The manifest hash is computed over canonically sorted per-reference identity tuples, so store row order cannot change it. |
| D2 | BLOCKER | Each tuple carries reference id, capture id and capture content hash. |
| D3 | RECOMMENDED | A manifest change against a cached run is reported, with per-reference validation deciding what is reused. |

## E. Cache schema and versioning

| # | Severity | Invariant |
|---|---|---|
| E1 | BLOCKER | The cache carries top-level `cache_format_version` and `builder_version`, both validated on load and both printed and gated in the runner. |
| E2 | BLOCKER | Any change to row semantics, reuse rules or certification rules bumps `builder_version`, and a cache from an earlier builder is refused rather than reused. |
| E3 | BLOCKER | SEG and ITEM1_STRUCT versions are recorded, validated on load, and gated. |
| E4 | RECOMMENDED | The cache filename changes with the builder version so two semantics never share a path. |
| E5 | BLOCKER | An unreadable or malformed cache is rebuilt rather than partially trusted. |

## F. Row reuse

| # | Severity | Invariant |
|---|---|---|
| F1 | BLOCKER | Reuse requires reference id, capture id, capture content hash, entity key, filing date, tier and builder version all to match. |
| F2 | BLOCKER | A row carrying an integrity failure is never reused; it is rebuilt. |
| F3 | RECOMMENDED | `--rebuild` forces a full rebuild regardless of cache state. |

## G. Stale row handling

| # | Severity | Invariant |
|---|---|---|
| G1 | BLOCKER | Rows for references absent from the current walk are pruned before certification, with the count and examples printed. |
| G2 | BLOCKER | The final record count equals the eligible reference count, printed as an identity with a boolean. |

## H. Interruption and resume

| # | Severity | Invariant |
|---|---|---|
| H1 | BLOCKER | Rerunning the same approved block is the resume path; a prior evidence file is archived, never a reason to refuse. |
| H2 | BLOCKER | An interrupted run leaves a cache that is explicitly incomplete and can never be read as a valid population. |
| H3 | RECOMMENDED | The resume cost is described accurately, including what is still paid per reference. |

## I. Checkpoint atomicity

| # | Severity | Invariant |
|---|---|---|
| I1 | BLOCKER | Checkpoints are written to a temporary file, flushed and fsynced, then swapped in with `os.replace`. |
| I2 | BLOCKER | A failed serialization leaves the previous cache byte-identical and removes the partial temporary. |
| I3 | BLOCKER | A checkpoint is reached for every processed reference, including rows that take an early-exit branch. |
| I4 | BLOCKER | No intermediate checkpoint may write `complete: true`. |

## J. Integrity failures

| # | Severity | Invariant |
|---|---|---|
| J1 | BLOCKER | Integrity counts used for certification are computed from the final row population, not from events in the current attempt. |
| J2 | RECOMMENDED | Per-attempt event counts are also printed, separately labelled, so reuse is not mistaken for verification. |
| J3 | BLOCKER | The first N integrity failures print their reference id, capture id and hashes immediately rather than only in a summary count. |

## K. Compatibility measurement

| # | Severity | Invariant |
|---|---|---|
| K1 | BLOCKER | Compatibility against the incumbent p2 Item 1 region is measured for every readable capture, before and independently of SEG slice validity. |
| K2 | BLOCKER | A capture where SEG finds no Item 1 while p2 does is recorded as a mismatch, not skipped. |
| K3 | BLOCKER | Only an unreadable capture may carry `compatibility_available: false`. |
| K4 | BLOCKER | The first N mismatches print reference id, capture id, both region lengths and the head of each region immediately. |

## L. Final certification

| # | Severity | Invariant |
|---|---|---|
| L1 | BLOCKER | Every final invariant is computed before completion is claimed; `complete` is the conjunction of them. |
| L2 | BLOCKER | The printed `complete` value is exactly the value persisted to disk. |
| L3 | BLOCKER | A failed invariant persists `complete: false` and exits non-zero. |
| L4 | BLOCKER | Certification covers: record count identity, reference uniqueness, and zero integrity failures in the final population. |

## M. Evidence output

| # | Severity | Invariant |
|---|---|---|
| M1 | BLOCKER | The evidence file is a single encoding throughout; no second writer with different encoding. |
| M2 | BLOCKER | The final identity block prints, and the runner gates: eligible reference count, unique reference id count, reused count, new count, final record count, pruned stale count, drift count, id mismatch count, unreadable count, manifest hash, cache sha256, cache format version, builder version, SEG version, ITEM1_STRUCT version, and the three identity booleans. |
| M3 | RECOMMENDED | Every stage is timestamped and its duration printed with an hour-safe formatter. Wall-clock timestamps must remain sufficient to reconstruct elapsed duration if a wrapper formatter rolls over after 59 minutes. RECOMMENDED, not BLOCKER: this aligns the document with the ruling of record of 2026-09-12 and is not a new requirement. |
| M4 | RECOMMENDED | Output is mirrored to the console live, not only to the file. |

## N. Runtime and progress

| # | Severity | Invariant |
|---|---|---|
| N1 | BLOCKER | A progress gauge prints processed count, rate and elapsed time; ETA is printed when a denominator is known and declared unknown when it is not. |
| N2 | RECOMMENDED | The runtime disclosure is derived from this session's measured pace rather than a stale anchor. |

## O. No-commit guarantee

| # | Severity | Invariant |
|---|---|---|
| O1 | BLOCKER | Block A stages nothing, commits nothing and pushes nothing. |
| O2 | BLOCKER | After the build, tracked modifications are zero, non-ignored untracked paths are zero, and HEAD is unchanged, each gated. |
| O3 | BLOCKER | The block ends stating that R3-0b remains OPEN and R3-0d remains BLOCKED. |

---

## Status of the current implementation against this specification

The current pair is `20260912_v1_v58d_segv1_census_build.ps1`
(`0da88fa9…`) and `20260912_v8_segv1_census_build.py` (`2a0bf344…`).

Believed satisfied: A1 to A8, B1 to B4, C1 to C6, D1 to D3, E1 to E5, F1 to
F3, G1 to G2, H1 to H3, I1 to I4, J1 to J3, K1 to K4, L1 to L4, M1 to M4, N1,
O1 to O3.

Not independently verified on real data, and stated as such rather than
claimed: the walk over real captures, compatibility against real filings,
resume after a real interruption, and the true runtime. Those first execute on
the operator's machine.

N2 is currently partially satisfied: the runtime disclosure cites the measured
83-minute anchor and the 18 to 29 references per minute observed during the
interrupted v57s run, but the census build does more per reference than that
run did, so the honest statement is that the first real run measures it.
