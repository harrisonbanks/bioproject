docs/20260913_v1_R3_0b_Census_and_Closeout_Record.md

# R3-0b Census and Closeout Record: SEG-v1 FROZEN

**Date of record:** 2026-09-15
**Closeout commit:** the commit that adds this file (Block B stage B3, block v60z); it
carries this record and `docs/PROJECT_STATUS.md` v1.35 and nothing else.
**Governing documents:** `docs/20260912_v1_R3_0b_Census_Build_Acceptance_Spec.md`
(frozen at `de8191fc9b3028f62e47eb526934c4a8c4e03599`, sha256
`9a9b77c1397c9ccde8545a2a060d372777cce3b7834f6b503ca88349ca145b7d`);
`docs/20260913_v1_R3_0b_Block_B_Acceptance_Spec.md` (frozen at
`539fa8f833fe88e64732f179161c1f8dcd13cf7a`, sha256
`b8e31fb20fb1b4696ef30d27ece1e68b46c92a6126e9d584c8b4608c1b319b4e`);
`docs/20260914_v1_R3_0b_Block_B_Spec_Erratum_G1_G4.md` (committed at
`a4ab24beef36e6e8899b02346c7dc7fd8cea5fb0`, sha256
`4cb4f870534bec752a85c794b5a61c39012b85eea96a2d980efebf9bb0408b50`).

## 1. Decision

R3-0b is CLOSED. SEG-v1 is FROZEN. R3-0d is UNBLOCKED.

The frozen implementation is `src/biointel/seg.py` at sha256
`4b992b38ddca76bdd70c4c428812d2fb8fdadc7a71f3a06c08a2d9e9b24274e1`, as
committed at `81bdfe23e4a2d9defcc76689b89e31473ead0dd0`, over the Item 1
substrate `ITEM1_STRUCT-v1`. This closeout commit does not touch that file; the
module docstring's conditional status text ("a CANDIDATE implementation until
the R3-0b census closes", "becomes frozen on successful R3-0b census closeout")
is satisfied by this record, and leaving the file byte-identical preserves the
implementation hash that every certified artifact below binds to. Any material
change to the boundary rules, the coordinate contract or the identity
serialization is SEG-v2, never an edit to this file.

## 2. Implementation commits versus this closeout commit (I3)

| Commit | Role |
|---|---|
| `a7e4e510b3165da043bf391e505ee0cc2c92e5a1` | SEG-v1 implementation: `seg_normalize`, `seg_item1_slice`, `segment_item1`, the verbatim offset invariant, fail-closed paragraph containment, the ratified bullet limitation (Option A) |
| `81bdfe23e4a2d9defcc76689b89e31473ead0dd0` | Compatibility repair: `compatibility()` no longer re-normalizes the SEG side (`_compare_norm`); the checker had destroyed evidence the substrate preserved |
| `de8191fc9b3028f62e47eb526934c4a8c4e03599` | Block A acceptance specification frozen |
| `539fa8f833fe88e64732f179161c1f8dcd13cf7a` | Block B acceptance specification frozen |
| `a4ab24beef36e6e8899b02346c7dc7fd8cea5fb0` | Block B G1/G4 erratum under rule 4 |
| this commit | Closeout: this record and PROJECT_STATUS v1.35; freezes SEG-v1; no code |

The measured behaviour below was produced by the first two commits. The closeout
commit records it and changes nothing that produced it.

## 3. Certified artifacts (all under `data\exports`, gitignored, gated by hash between stages)

| Artifact | SHA-256 | Produced by |
|---|---|---|
| `segv1_census_BUILD-v5.jsonl` (Block A cache, `CENSUS-CACHE-v3`, `BUILD-v5`, `complete: true`) | `02cd6568acd90ddc94fc351ff3c435bb8ca8e1b86badbdcbe73e6c7a0ed9fbda` | v60c (3,726 rows, stopped) resumed by v60d |
| `segv1_lengths_BUILD-v5.json` (B1 exact lengths, `histogram_complete: true`) | `a3483fcdf596346855b3ed89d26c69faacfaa50ce29f7af25a112d7d5c288c81` | v60j |
| `segv1_p2_replay_L3-a3-p2.json` (B1b replay set, `P2-REPLAY-v1`, `complete: true`) | `0f58ff75aaf2aa9c3bdfdf0d9b09b8e98ddc1818578ccf114138f6dcb8760e9a` | v60v |
| `segv1_census_report_BUILD-v5.md` (B2 as first executed; section 6 superseded) | `de185dcb80e72b83a4ee1acd6cb310a3566ee9cf4feae84421b68dfa9cb3389e` | v60m |
| `segv1_census_report_BUILD-v5_rerun.md` (B2 rerun under the erratum; the report of record) | `810733e18100655609fa88be4cb61bfd50c481fb27376ad6eb27adac6cfadd24` | v60w |

Replay identity: pair manifest
`e9c550ed71e69a51bab2beaa65fc1dcdbfdfd799245a4dcaba8e8d7cd4b6356e`, candidate
manifest `e3d38b059ab780f5b756e798ce08868c95e9ce66878d958209d510cb63d941b3`,
both reproduced by two independent passes and recomputed by the reviewer and by
B2 from the stored set.

## 4. Population (rows of the certified cache)

- 6,992 references over 6,991 distinct captures; the shared capture
  `87c6b2c3e03db031b0d08f06ab7a4324247b5bc769ab9aee1f00762eb0f7f00c` is carried
  by `R7216cddb47e66cf9` and `Rbf66a5d43768be3b` and is reported by reference.
- Tiers: `10k_strategy` 6,500 / 6,992; `investor_day` 492 / 6,992.
- Population authority: `priorities.iter_sweep_documents` (Block A B2); every
  reference byte-verified against `capture_sha256 == capture_id`; zero integrity
  failures, zero unreadable captures, zero drift, zero id mismatches.

## 5. Compatibility with the incumbent (E)

- Available 6,992 / 6,992; match 6,992 / 6,992; mismatch 0 / 6,992.
- References where SEG found no Item 1 while p2 did: 0 / 6,992.

## 6. Item 1 slices and the absent population (D)

- Valid slices 5,956 / 6,992; absent 1,036 / 6,992.
- `10k_strategy`: valid 5,945 / 6,500; absent 555 / 6,500. All 555 are also
  absent for p2 (`p2_len == 0`), and the incumbent's own rules refuse every one
  of them today: 408 region under the 500-character floor (an incumbent-style
  Item 1 heading present in 408 / 408), 112 XBRL tag soup, 35 no `Item 1A`
  terminator.
- `investor_day`: valid 11 / 492; absent 481 / 492, all `no_item1a_terminator`,
  all also absent for p2.
- Byte identity re-verified on every absent capture: 0 failures / 1,036.
  References the incumbent would slice now despite an absent row: 0 / 1,036.
- Appendix A of the report of record lists all 1,036 with category, `p2_len`
  and `p2_also_absent`.

## 7. SEG-v1 quality measurements (F)

- Total segments 8,074,351 over 5,956 valid slices; per valid slice mean
  1,355.7, median 1,094 (nearest-rank).
- Exact segment length over 8,074,351 segments (B1, nearest-rank, no
  interpolation): mean 145.73, median 132, p25 42, p75 212, p90 297, p95 362,
  p99 535, min 1, max 6,291.
- Ten largest (length, reference): 6291 `R0e3ab2c1f2bfd797`; 5570
  `R46a41e1876c45432`; 5553 `R8dc91b1273d214c0`; 5183 `R59de0e6a5059fcdc`; 5072
  `Rb5269249c27cbd4b`; 4811 `R3f7289a66d63012d`; 4763 `Rcf8068d2f01ad68b`; 4617
  `R2f785c18020a26c6`; 4487 `R5e0b46963f1fa6bc`; 4471 `Re298e9513f09b6ac`.
- Coverage-gap slices 0 / 5,956; segmentation errors 0 / 6,992; zero-segment
  slices 0 / 5,956; offset-invariant failures 0 / 6,992.
- Bullet-merge proxy: 49,101 / 8,074,351 segments (0.61%); references with at
  least one 3,006 / 5,956 valid slices (50.5%). A heuristic proxy for the
  ratified Option A limitation, not an error rate.
- B1 reproduced the certified total exactly: 5,956 / 5,956 valid slices
  re-segmented from byte-verified captures, 0 count mismatches, 0 errors.

## 8. p2 strata under the G1/G4 erratum (G)

- Stratum `entity_date_pair_has_p2_candidate`: an `(entity_key, stated_at)` pair
  present in the REPLAY SET, the rows the frozen `priorities.write()` selection
  path would have emitted for the bound corpus under `L3-a3-p2`: extraction
  through the shared iterator, verdict-aware selection with the review ledger
  bounded at the bound write run `20260910T195425-priorities-write`
  (2026-09-10T19:54:25Z), then `pool_select`. A pair is not a document identity.
- Replay set: 4,742 selected rows, equal to the bound write's recorded
  `rows_written` 4,742 (difference 0); 2,200 overflow rows; 3,598 / 3,598
  replayed pairs; 0 current-ruleset reviews existed at the cutoff, so the
  write-time corpus was extraction plus `pool_select` with no suppression or
  relabel.
- References in stratum 3,650 / 6,992 (3,522 / 6,500 `10k_strategy`; 128 / 492
  `investor_day`); not in stratum 3,342 / 6,992. Distinct reference pairs 6,863
  over 6,992 references, of which 3,598 / 6,863 are in the replay set; 0 / 3,598
  replay pairs are carried by no census reference. In-stratum references with a
  valid slice 3,521 / 3,650.
- Diagnostic only: the mutable `stated_priorities` projection holds 2,492 pairs
  over 2,890 rows; all 2,492 are in the replay set; 1,106 / 3,598 replay pairs
  are absent from it. The projection is not a substrate.

## 9. Why the erratum exists (rule 4 record)

The first B2 execution (v60m) measured the stratum as empty, 0 / 2,890
`stated_priorities` rows under `rule_version` `L3-a3-p2`, because that table
carries no `rule_version` column. The read-only diagnostic v60r established from
the runs ledger that the last ok `priorities-write` run wrote 4,742 rows under
`L3-a3-p2`, that the live table holds 2,890, and that 2,232 S-keyed
current-ruleset `wrong` or `relabel:` reviews postdate the write; finding
`POST_WRITE_ADJUDICATED_PROJECTION`. The frozen G1 definition was therefore
unmeasurable as written, the erratum redefined the substrate as the
deterministic replay of the write-time selection path, B1b produced it in two
agreeing passes, and B2 was rerun. Sections 1 to 5 and 7 of the report are
identical between the two executions.

## 10. Freeze assessment (H1 to H3)

All ten invariant checks pass in the report of record: zero offset-invariant
failures; zero coverage gaps; zero segmentation errors; zero zero-segment
slices; 6,992 / 6,992 compatibility agreement; zero SEG-only Item 1 absence;
every absent slice shared with p2; the B1 recomputation reproduces the certified
segment total; zero absent-slice byte-identity failures; the incumbent refuses
every absent reference today. `B2_ASSESSMENT: NO_DEFECT_FOUND`. No measurement
violates a stated SEG-v1 invariant or reveals a demonstrated defect; the bullet
proxy is the ratified limitation, measured. On that evidence SEG-v1 is frozen.

## 11. Runtimes of record (I5)

| Stage | Wall clock | Source |
|---|---|---|
| Block A first run (v60c), 3,726 rows then a transient `os.replace` denial | 5h39m10s (00:43:30 to 06:22:40) | v60c evidence |
| Block A resume (v60d), 3,266 new rows | 7h37m51s | v60d log |
| B1 exact lengths (v60j), 5,956 slices at a flat 7.7 per minute | 12h54m46s | v60j log |
| B1b replay (v60v), two passes | 2h49m39s | v60v log |
| B2 (v60m) / B2 rerun (v60w) | 23 s / 22 s | v60m, v60w logs |

The Block B specification row I5 cites "5h35m" for the first Block A run; the
evidence timestamps give 5h39m10s and govern.

## 12. Evidence register (Downloads files cited by name and SHA-256)

| Block | File | SHA-256 |
|---|---|---|
| v59t compat repair | `20260912_v59t_compat_repair_evidence_20260912_225403.txt` | `0b7b60080fcf18e6a604aa2faa073b12a9ebcab77d040f03e30aadd4c9b6af96` |
| v59u compat verify | `20260912_v59u_compat_verify_evidence_20260912_230300.txt` | `7dcc1e7b5927b350257281d939533a01c63c0e8fe4f826826e015e941b67a000` |
| v59w Block A spec | `20260912_v59w_acceptance_spec_evidence_20260912_232432.txt` | `0b05f2f396b83e03f60a84a7749b863a349ada12edcced0bc392cb1023ff7927` |
| v60c census (stopped) | `20260913_v60c_census_evidence_20260913_004329.txt` / log | `88766ba11ad9e313e59d453795f8fb8934f98e2dde3ac70022028a435c1565c7` / `3a5f2799eff5f7df727196cd559cdf5e409fcc0774bdfb28d93b1987c7332cf0` |
| v60d census (certified) | `20260913_v60d_census_evidence_20260913_103708.txt` / log | `e8967245459d8453e089d11fd305ce02b3af9537ec47065e56dfd5644c9a0895` / `37c7168c18290578ca224532fc1e50bbcce55105aa6b810f4a9f9ac982cf725f` |
| v60g Block B spec | `20260913_v60g_block_b_spec_evidence_20260913_222034.txt` | `8cf8406552efa6735d27114bc424bb6abd4325df1428985de1caaa6f26f517f2` |
| v60j B1 | `20260913_v60j_b1_evidence_20260913_225235.txt` / log | `62cf17f3afad7f7cb89473be1856f8558de4eb2ea2c1fe28f6f53910340957f3` / `d1ecb7c4f0319b85e257934418fcde0598be9aa4b2250dea0faf849539f41153` |
| v60m B2 (first) | `20260914_v60m_b2_evidence_20260914_134227.txt` / log | `8774b13f3745948e9318853028a9e9d8b5fb5ff400cc7f99385b69f4a422922f` / `fc77392606c8e6c7726bbc179791677040b64318e69b78b16ac3b2922155aec0` |
| v60r diagnostic | `20260914_v60r_diag_evidence_20260914_180450.txt` / log | `118719eb5cd6534531d2b4fa54e0fae9348429050f24a389c9e68ed8824322f5` / `788dbcddd8559f19062451d1cf48042ebe080103f066c61984c03505f58da159` |
| v60u erratum commit | `20260914_v60u_block_b_erratum_evidence_20260914_224344.txt` | `eb335fe3bec85a05ed23e36bde2d95b5e70a16c0dda99fe43726c380e593fc8c` |
| v60v B1b | `20260914_v60v_b1b_evidence_20260914_225846.txt` / log | `fa6f65860815e28477628ad33fb663d1c4e2b5890bd56d6a5cae3d1454d30e76` / `dc7242f1296ec77125e5c04ef209d7b79b5091c42f3a893466a0f9c45a5bf5eb` |
| v60w B2 rerun | `20260915_v60w_b2_evidence_20260915_020121.txt` / log | `2586ce2696fb4724c3ea95bae8595230e2e1a48d49daedd4f26ea021fcca5be0` / `07aa9871673c1b09580ce4162431dbf74804cf83c8ad040c179e8547a01342a4` |

Known descriptive errata inside cited evidence files (blocks already run; files
untouched by rule): the errata-manifest line "Boot protocol Step 0 push N/A Block
A commits nothing" appears in the v60j, v60v and v60w evidence, carried from the
Block A runner; each of those blocks commits nothing, so the statement is true
of the block and mislabels only the stage name. The v60v payload's own
500-reference progress gauge printed only when the 500th reference yielded
candidates; the iterator's gauge every 250 is the complete one.

## 13. Blocks retired by name during R3-0b (never reused)

v59b, v59c, v59d, v59e, v59g, v59h, v59i, v59j, v59k, v59l, v59o, v59p, v59s,
v59v, v59x, v59y, v59z, v60a, v60b, v60e, v60f, v60h, v60i, v60k, v60l, v60n,
v60o, v60p, v60q, v60s, v60t. Ran and passed: v59m, v59q, v59r, v59t, v59u,
v59w, v60c/v60d, v60g, v60j, v60m, v60r, v60u, v60v, v60w, and this block.

## 14. Rulings of record made during R3-0b

- The handoff's "bare `<` deletion" root cause was disproven by execution; the
  substrate never lost the text, the compatibility checker did (v59q, v59r,
  v59u). The tag-allowlist direction was abandoned.
- Checkpoint resilience: an atomic `os.replace` can fail transiently on the
  operator's machine (`PermissionError [WinError 5]`); checkpoints retry with a
  bounded backoff, every long-run payload writes an unhandled traceback into its
  log with a distinct exit code, and an interrupted run with an intact
  incomplete cache is resumed by rerunning the same approved block.
- Evidence provenance: a cited evidence file is permanent provenance; descriptive
  errors are corrected before a run by reissuing the block, never by editing an
  emitted file; after a run they are recorded here.
- `stated_priorities` is a mutable post-adjudication projection and is never a
  substrate for a current-ruleset candidate population; the replay artifact is.

## 15. What this unblocks, and what is held

R3-0d (immutable adjudication ledger) is UNBLOCKED by R3-0b. Its implementation
is held, by operator decision recorded here, until an independent parser
benchmark and a substrate decision determine whether persistence binds to
`ITEM1_STRUCT-v1` / SEG-v1 or to a successor substrate: R3-0d persists segment
identities, and that decision is cheaper before adjudications are tied to them.
The benchmark is an architecture decision gate inserted before R3-0d begins,
not a renumbering. The formal gate order of record is unchanged: R3-0d, R3-0e,
R3-1, R3-2, R3-3.
