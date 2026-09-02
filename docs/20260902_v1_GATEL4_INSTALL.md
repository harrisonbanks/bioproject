# docs/20260902_v1_GATEL4_INSTALL.md

# Gate L4 — aspect-match + forward hit/false-alarm test (install runbook)

Bioindustry Intelligence Platform · 2026-09-02 · entry commit 3124814 (L3 DONE).
Scope and Q1–Q4 approved 2026-09-02 with three binding additions: per-aspect
coverage as run metrics; the pool definition recomputable from the run note
alone; the untouched-surface proof (fingerprint loop + empty diff on the five
prior-gate model files). Pass mark pre-registered and binding: adoption only if
paired HR@5 exceeds 0.334 by more than 2× the pooled repeat standard deviation
on shared events and shared samples; anything weaker ships as a recorded
finding and mass-exact remains the implementation of record.

## 1. Package installs
None. No new dependency.

## 2. Files
| Download | Deploys to | Change |
|---|---|---|
| `aspects.py` | `src\biointel\aspects.py` | new module (gate L4): analyst-stated presence rules for the v1 aspect set (constants TA_JACCARD_MIN 0.05, LOE_HORIZON_YEARS 5, equal weights); `build_ctx`/`pair_aspects`/`pair_score`; `resolved_events` with the Tempus-sequence exclusion (Ambry, Deep 6, Paige, Personalis — the rules' source, P19); `paired` (aspect-match beside MASS-exact on identical events and shared sampled negatives, midpoint tie rank, pass-mark verdict recorded, per-aspect coverage as run metrics); `forward` (§5.6: per buyer-year top-k proposals from information dated ≤ year-end; hits@5/10/25 vs analytical chance k/pool; false alarms; degenerate all-tied buyer-years propose nothing); reports `pair_aspect_report.txt` / `pair_aspect_forward_report.txt` written to exports and registered as run artefacts; adapters `run_paired`/`run_forward`. `consideration_type` recorded as not-evaluable (a consummated-deal property, not a pre-announcement pair attribute); undated relationship edges never count as-of; a missing Orange Book zip yields coverage 0, never a silent zero |
| `test_aspects.py` | `tests\unit\test_aspects.py` | new (+6): all eight presence rules and coverage on fixture rows; undated-edge rejection; Tempus exclusion; midpoint-tie guard (all-tied pool proposes nothing); paired end-to-end through the harness with coverage metrics, pass-mark metric, exclusion note and report file asserted; forward end-to-end with hit counted, 0 < chance < 1, pool-definition note asserted |
| `registry_v003.py` (supersedes 0.4-fix v002) | `src\biointel\models\registry.py` | built from the deployed file with three insertions only (every prior entry carried forward by construction): `ASPECT_MATCH_INPUTS` (explicit columns; `bronze:orangebook` declared for the record like `bronze:prices`); entries `acquirer-pairing/aspect-match` [predict] and `aspect-paired` [evaluation]; `COMMAND_TO_ENTRY` rows `pairs-aspect` and `pairs-aspect forward`. Behaviour change, documented: `run acquirer-pairing` without `--impl` now names both implementations (two exist since L4); `pairs-full-exact` is unaffected (explicit impl in its command mapping) |
| `cli_v913.py` (supersedes v912) | `src\biointel\interfaces\cli.py` | help line + `pairs-aspect [forward]` dispatch through the harness (68th command); nothing else changed |
| `test_models_v901.py` (first replacement of the 0.4 file) | `tests\unit\test_models.py` | two assertions updated for the two-implementation registry: `registry.get("acquirer-pairing")` now expects KeyError (like target-screen) with explicit-name gets asserted, and `aspect-match` added to the describe-list names; nothing else changed |

## 3. Order of operations (Block L4-A)
1. Install the five files; pytest 171.
2. `pairs-aspect` — the paired protocol beside mass-exact (200 negatives, 20
   repeats, seed 7, shared samples; Tempus-sequence deals excluded and counted
   in the metrics); the report prints both engines' HR@5/HR@10, the pass-mark
   verdict line, and the per-aspect coverage table.
3. `pairs-aspect forward` — the §5.6 forward test (k=10 primary; 5 and 25
   beside); the report prints hits vs chance, false alarms, degenerate
   buyer-years, median pool; the run note carries the pool definition verbatim
   and the four excluded deal names.
4. Untouched-surface proof (binding): the full thirteen-fingerprint loop
   against `docs/regression_baseline.txt`, and the empty-diff check of §5.
5. Evidence to one file per rule 4.21; docs and the gate commit follow the
   paste in the closing block.

## 4. Exit criteria
1. pytest 171; ruff check and format --check clean on the five gate files.
2. `pairs-aspect`: run recorded with groups `aspect-match`, `MASS-exact`,
   `passmark` (benchmark_hr5 0.334, pooled_sd, adopted 0/1) and one coverage
   group per aspect (`evaluable_pairs`, `present_pairs`), including
   `consideration_type` at 0; report file in `data\exports\`.
3. `pairs-aspect forward`: run recorded with hits5/10/25, expected_hits5/10/25,
   false_alarms10, buyer_years, degenerate_buyer_years, evaluable_deals,
   median_pool, and the per-aspect coverage groups; the run note contains the
   pool definition and the four excluded deal names.
4. Thirteen fingerprints MATCH against `docs/regression_baseline.txt`.
5. `git --no-pager diff --stat 3124814 -- src/biointel/pairs.py
   src/biointel/labels.py src/biointel/forward.py src/biointel/efts.py
   src/biointel/analyser.py` — expected output empty.
6. `predict` composition unchanged (no gate action touches it).
If 4 or 5 fails, the gate does not close, regardless of the aspect-match
numbers (binding addition 2026-09-02).

## 5. Dry-run evidence (container mirror, Python 3.13.7, 2026-09-02)
- Mirror at 3124814; pytest 165 green and the three known pre-existing ruff
  findings (improve.py E731, score.py/study.py F841) confirmed before any
  change (handoff §5 item 6; outside this gate's files, untouched).
- After the gate files: pytest 171 passed (165 prior + 6 aspects tests); ruff
  check and format --check clean on all five gate files.
- Untouched-surface diff against 3124814 over pairs.py / labels.py /
  forward.py / efts.py / analyser.py: empty in the mirror; the only tracked
  changes are cli.py (+10), models/registry.py (+35), test_models.py (+18/−2).
- `models` lists both implementations and both evaluations under
  acquirer-pairing with their declared inputs; the help text carries the
  pairs-aspect line; the harness routes both new commands under enforcement
  (proven by the end-to-end tests, which run through `run_command`).
- Logic verified on fixtures (no external parser in this gate, so rule 4.20
  requires no capture): all eight presence rules fire and abstain correctly;
  the Tempus exclusion removes both an acquirer-side and a filer-side match;
  an all-tied candidate pool proposes nothing (midpoint rank); the paired run
  records the pass-mark and coverage metrics and writes its report; the
  forward run counts the fixture's one hit with 0 < chance < 1 and carries
  the pool-definition note.
- Not verifiable in the container: your row counts, runtimes, the two live
  reports' numbers, and the thirteen fingerprints — Block L4-A is the proof.

## 6. Deferred, named here
- `report pairs-aspect [DATE]` render-from-record requires a RENDERERS entry
  in results.py, outside this gate's touch list; the reports are written at
  run time and registered as artefacts (P17 satisfied); the RENDERERS entry
  lands at the next gate that touches results.py for its own reason (P9/P18).
- Aspect weights beyond the equal-weight prior: a later gate under its own
  pre-registration, evaluated on deals not used to set the weights (approved
  Q4).
- Analyser aspect-extraction rules (the a3 agenda) to populate deal_aspects /
  stated_priorities / assets beyond the seed: their own gates; coverage
  metrics make today's sparsity a queryable fact of every run.
- Docs (PROJECT_STATUS 1.10, plan v23 with L4 status, handoff v29, README)
  delivered with the single gate commit block after the exit paste.
