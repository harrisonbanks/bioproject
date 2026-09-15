docs/20260914_v1_R3_0b_Block_B_Spec_Erratum_G1_G4.md

# R3-0b Block B specification: erratum to G1 and G4

**Date:** 2026-09-14
**Amends:** `docs/20260913_v1_R3_0b_Block_B_Acceptance_Spec.md`, frozen at commit
`539fa8f833fe88e64732f179161c1f8dcd13cf7a`
(sha256 `b8e31fb20fb1b4696ef30d27ece1e68b46c92a6126e9d584c8b4608c1b319b4e`).
**Authority:** rule 4 of that specification. The frozen document is not edited;
this erratum is the binding replacement for rows G1 and G4 and adds rows G5 to
G8 and J3a and stage B1b. Every other row is unchanged.
**Status:** BINDING once committed.

## Why this erratum exists

Row G1 defined the stratum `entity_date_pair_has_p2_candidate` as an
`(entity_key, stated_at)` pair carrying at least one current-ruleset p2
candidate in the store, and G4 required a deterministic manifest over the pairs
satisfying that ruleset. The live store cannot satisfy that definition. This was
established by execution, not inference:

- Block v60m (B2, executed 2026-09-14, report sha256
  `de185dcb80e72b83a4ee1acd6cb310a3566ee9cf4feae84421b68dfa9cb3389e`) measured
  the stratum as empty: 0 / 2,890 `stated_priorities` rows carried
  `rule_version` `L3-a3-p2`. The table has no `rule_version` column; the filter
  matched nothing by construction.
- Block v60r (read-only diagnostic, executed 2026-09-14, evidence sha256
  `118719eb5cd6534531d2b4fa54e0fae9348429050f24a389c9e68ed8824322f5`, log sha256
  `788dbcddd8559f19062451d1cf48042ebe080103f066c61984c03505f58da159`) established
  from the runs ledger that the last ok `priorities-write` run,
  `20260910T195425-priorities-write` at 2026-09-10T19:54:25Z, wrote 4,742 rows
  under `rule_version` `L3-a3-p2`; that the live table holds 2,890 rows; and that
  2,232 S-keyed current-ruleset `candidate_reviews` rows with a `wrong` verdict or
  a `relabel:` note postdate that write. Its finding is
  `POST_WRITE_ADJUDICATED_PROJECTION`.
- Repository facts at `priorities.py` sha256 `088db05f164b1080f5d668388915cbcf834bb127bf83d8a76fa4bcb565af8181`:
  `write()` replaces the whole table (line 1069); `judge()` deletes a row on a
  `wrong` verdict and rekeys one on a relabel, reaching the table only through
  S-keys (`_row_key`, line 1123) and opening no run (lines 1194 to 1254).

The live `stated_priorities` table is therefore a post-adjudication projection of
the write generation, not the candidate corpus that generation emitted, and no
immutable store representation of the complete current-ruleset candidate set
exists. The mutable projection is not authoritative for this stratum.

## Replacement rows

| # | Severity | Invariant |
|---|---|---|
| G1 | BLOCKER | The stratum label is `entity_date_pair_has_p2_candidate`, defined as an `(entity_key, stated_at)` pair present in the REPLAY SET: the rows that the frozen `priorities.write()` candidate-selection path (priorities.py sha256 `088db05f164b1080f5d668388915cbcf834bb127bf83d8a76fa4bcb565af8181`, lines 1012 to 1069) would have emitted for the bound corpus, reproduced deterministically without writing any table. That path is, in order: `priorities.extract_priorities` under `RULE_VERSION_F2` per document through the shared iterator `priorities.iter_sweep_documents`; verdict-aware selection using only `candidate_reviews` rows under `RULE_VERSION_F2` whose `reviewed_at` is not later than the bound write run's `run_at` (`20260910T195425-priorities-write`, 2026-09-10T19:54:25Z), so that a key judged `wrong` without a relabel at that time is suppressed and a relabel rewrites the category before keying, exactly as `write()` did; then `priorities.pool_select`, which keeps the longest candidate per `(entity_key, stated_at, category)` key and diverts the rest to overflow. The replay set is the selected rows, not the raw extractor output and not the overflow. Reviews later than the bound write's `run_at`, which are the post-write adjudications v60r demonstrated, are excluded by construction. The mutable post-adjudication `stated_priorities` table is not authoritative for this stratum and is never used as its substrate. The report states that a pair is not a document identity. |
| G4 | BLOCKER | The p2 input has an identity of its own: the replay artifact of G5. B2 states the ruleset identifier, computes the manifest SHA-256 over the canonically sorted replayed `(entity_key, stated_at)` pairs (serialized as `entity_key + "\x1f" + stated_at + "\x1e"` in UTF-8, in sorted order), and the report carries that manifest hash together with the pair denominator `N / N replayed pairs`, so the strata are reproducible without freezing the database file. |

## Added rows

| # | Severity | Invariant |
|---|---|---|
| G5 | BLOCKER | Stage B1b, read-only, produces one replay artifact under `data\exports`, written atomically, that records: the ruleset identifier `L3-a3-p2`; the code identity (`priorities.py` sha256 `088db05f164b1080f5d668388915cbcf834bb127bf83d8a76fa4bcb565af8181`, `seg.py` sha256 `4b992b38ddca76bdd70c4c428812d2fb8fdadc7a71f3a06c08a2d9e9b24274e1`, and the commit); the corpus identity (the certified cache sha256 `02cd6568acd90ddc94fc351ff3c435bb8ca8e1b86badbdcbe73e6c7a0ed9fbda`); the REPLAY MEMBERSHIP SET itself, the canonically sorted unique `(entity_key, stated_at)` pairs that G1 classifies against, stored in full; the replayed SELECTED rows in canonical form (sorted by `(entity_key, stated_at, category, statement)`), or at minimum a candidate-level manifest SHA-256 over that canonical form; the replayed selected row count; the verdict cutoff used (`2026-09-10T19:54:25Z`) and the number of current-ruleset reviews at or before it that were applied as suppressions and as relabels; the distinct pair count; the pair manifest SHA-256 of G4 computed over the stored set; and `complete` true only when G6 and G8 are satisfied. B2 reads the stored pair set, independently recomputes its manifest, requires it to equal the recorded one, and classifies each of the 6,992 references against that exact set; it never reconstructs membership from counts or hashes. |
| G6 | BLOCKER | Corpus identity is per reference, not a count. B1b walks the shared iterator and requires that the set of `ref_id` values it yields equals exactly the set of `ref_id` values in the certified cache, with no missing, extra or duplicate reference, and that for every reference the iterator's `capture_id`, `entity_key` and `filing_date` equal the certified row's; any disagreement is named and blocks `complete`. Where the replay reads stored capture bytes, the current SHA-256 must equal the certified `capture_sha256 == capture_id` before extraction. The artifact's own SHA-256 is printed by the payload, independently recomputed by the runner, and hash-gated by the B2 runner before B2 reads it, exactly as the B1 artifact is. |
| G7 | RECOMMENDED | B1b also reports, as diagnostic cross-checks and not as inputs: the replayed selected row count against the bound write run's recorded `rows_written` (4,742), with any difference stated; and how the replay set relates to the live projection, replayed pairs present in `stated_priorities` and projection pairs absent from the replay. |
| G8 | BLOCKER | Determinism is established by repetition, not asserted. B1b performs the replay twice, as two independent passes over the same identity-gated corpus, canonicalizes each pass's candidate rows and pair set, computes a candidate-level manifest SHA-256 and the pair manifest for each, and requires the two passes to agree on candidate count, pair count, pair manifest and candidate manifest before `complete` is true; both passes' manifests are recorded in the artifact and printed in evidence. A disagreement is a demonstrated nondeterminism and blocks the B2 rerun until explained. |
| J3a | BLOCKER | Stage B1b is treated exactly as B1 and B2 under J1, J2, J3 and J5: it fetches live and gates the base, requires a clean tree at entry and exit, stages nothing, commits nothing, pushes nothing, gates HEAD unchanged at exit, ships as a hash-gated payload, and writes an unhandled traceback into its evidence with a distinct exit code. This row exists because J3 names only B1 and B2, which were the stages that existed when the frozen specification was written. |

## Stage ordering after this erratum

B1 (CLOSED) → B1b replay (read-only, new) → B2 rerun consuming the certified
cache, the B1 artifact and the B1b artifact, each hash-gated → B3 closeout.

The B2 rerun changes section 6 of the report only. Sections 1 to 5 and 7 of the
v60m report, and the freeze assessment `B2_ASSESSMENT: NO_DEFECT_FOUND`, rest on
rows and on the B1 artifact and are unaffected; G3 keeps segmentation
independent of the strata.

## Review discipline

Rows K1 to K3 apply to B1b and to the B2 rerun unchanged. B1b's cost is two
replay passes; determinism is the reason for the second. No other row of the
frozen specification is reopened by this erratum.
