# docs/20260903_v1_GATEL4P_INSTALL.md

# Gate L4-P — aspect-match parameter elimination (install runbook)

2026-09-03. Entry: commit 1f3b2c7 (UNSOURCED correction recorded). Cause: an
audit of invented numbers found two constants in `aspects.py` that were
chosen by the assistant with no source — a 0.05 Jaccard cut for
therapeutic-area overlap and a single 5-year patent-cliff horizon.

## 1. What changes
| Download | Deploys to | Change |
|---|---|---|
| `aspects_v3.py` | `src\biointel\aspects.py` | `TA_JACCARD_MIN` deleted: therapeutic_area_overlap returns its raw Jaccard value as the aspect's strength; `pair_aspects` values are floats in [0,1] and `pair_score` is their equal-weight sum (the equal-weight prior is unchanged). `LOE_HORIZON_YEARS` deleted, replaced by `LOE_HORIZONS = (3, 5, 7, 10)`: `build_ctx`, `_loe` and `forward` take a horizon, and `paired` runs the whole evaluation at each horizon, recording HR@5/HR@10 per horizon and applying the pre-registered mark at each. MASS-exact does not read the LOE table, so it is scored once and its scores are horizon-invariant; samples are seeded identically across horizons and engines so the comparison stays paired. Coverage still counts an aspect as present when its strength exceeds zero |
| `test_aspects_v2.py` | `tests\unit\test_aspects.py` | +2 tests and updated contracts: `test_l4p_no_invented_constants_remain` asserts neither constant exists and that `LOE_HORIZONS` holds more than one value (a single value would be a choice); `test_l4p_overlap_is_continuous_not_thresholded` asserts a weak overlap scores above zero and below a strong one; existing tests updated for float strengths and horizon-named engines |
| `20260903_v112_PROJECT_STATUS.md` | `docs\PROJECT_STATUS.md` | v1.12: the gate, the refusal to re-tune, and the research direction for v2 |
| `20260903_v24_Implementation_Plan.md` | `docs\` (new file) | v24 header; supersedes v23 |
| `20260902_v1_Data_Feeder_Roadmap.md` | `docs\` (replacement) | amendment recording the elimination rule and the temporal-graph direction for v2 |

## 2. What does NOT change
1. The L4 results of record (paired HR@5 0.108, NOT ADOPTED, commit 3f3c7a0).
   They are not re-run here. Re-running under new scoring is a v2 evaluation
   and belongs to the v2 pre-registration, after F1 and F2.
2. The equal-weight prior across aspects (standing decision).
3. `mass-exact`, the implementation of record — it never contained either
   constant.
4. The collector, the library, the parser, and every stake row already
   written. Nothing is re-fetched.

## 3. Exit criteria
1. pytest 191; ruff clean on both gate files.
2. `git --no-pager diff --stat <entry> -- src/biointel/pairs.py
   src/biointel/labels.py src/biointel/forward.py src/biointel/analyser.py`
   empty.
3. Thirteen fingerprints MATCH under the settled loop (five-command
   regeneration set; legacy six from `data\gold_frozen_20260830\`, everything
   else from `data\exports\`; fixed-list routing, no fallback). `aspect-match`
   sits in no report path, so no baseline should move.
4. Evidence to one file, rule 4.21.

## 4. Dry-run evidence (container mirror, 2026-09-03)
191 passed; ruff check and format clean; no dead code; the Jaccard constant
is absent from the module (grep returns nothing); model files pairs/labels/
forward/analyser untouched. Not verifiable in the container: the fingerprints
and any live run — the block is the proof.
