# docs/20260830_v1_GATE03_INSTALL.md

# Gate 0.3 — reporting layer (run ledger + render from record) — install runbook

Bioindustry Intelligence Platform · Implementation Plan v5 row 0.3 · 2026-08-30.
Scope approved 2026-08-30 (questions 1–4 and the scope message). Entry commit on
`jason/refactor`: `5dbf595` (gate 0.2).

## 1. Package installs
None.

## 2. New files (deploy destination on line 1 of each)
| Download | Deploys to |
|---|---|
| `results.py` | `src/biointel/results.py` |
| `legacy_ledger.py` | `src/biointel/legacy_ledger.py` |
| `test_results.py` | `tests/unit/test_results.py` |

## 3. Replaced files (full-file replacements; deploy path on line 1)
| Download | Replaces | Change |
|---|---|---|
| `schema_v004.py` | `src/biointel/schema.py` | ledger tables `runs` (16 columns), `run_params`, `run_metrics`, `run_artefacts` declared with keys and enumerations; `SCHEMA_VERSION` 0.3 |
| `store_v003.py` | `src/biointel/store.py` | `append_rows` (ledger tables grow by appending; constraints enforced on insert) |
| `cli_v003.py` | `src/biointel/interfaces/cli.py` | `report MODEL [DATE]`, `report ledger`, `report runs MODEL`, `ledger-seed` (59 commands); `predict` prints `run <id> recorded` |
| `pairs_v002.py` | `src/biointel/pairs.py` | `pairs-exact` and `pairs-full-exact` split into record + `render_exact` / `render_full_exact` |
| `fit_v002.py` | `src/biointel/fit.py` | `robust` and `improve` split into record + `render_robust` / `render_improve` |
| `improve_v002.py` | `src/biointel/improve.py` | `develop`, `develop tune`, `develop textsweep` split into record + `render_develop` / `render_tune` / `render_text_sweep`; `best_config.json` registered as an artefact |
| `score_v002.py` | `src/biointel/score.py` | `predict` records a run (metrics, `ma_predictions.csv` artefact); `render_predict` |

## 4. Surgical edits
None.

## 5. Migration commands
`python -m biointel ledger-seed`, once: inserts the seven legacy rows (six `historical-file`, one `project-status`) after checking every frozen report file against `docs/regression_baseline.txt`; refuses if legacy rows exist or any fingerprint differs; seeds nothing on failure.

## 6. Automated test command
`pytest -q tests/unit` — expected `58 passed` (46 existing + 12 results/ledger tests).

## 7. Live verification (exit criteria)
1. `ledger-seed`: seven rows; a second run refused.
2. The eight run commands (`predict`, `pairs-full-exact`, `robust`, `improve`, `pairs-exact`, `develop`, `develop tune`, `develop textsweep`) each print `run <id> recorded` (textsweep prints `No text corpus.` and records nothing on this machine).
3. All thirteen fingerprints in `docs/regression_baseline.txt` match (seven regenerated exports through the split writers, six frozen legacy files).
4. `report <model>` for each of the six recorded report models regenerates the export from the stored record; the seven fingerprints match again afterwards (byte-identity from the record).
5. `report ledger`: 7 legacy + 7 run rows (textsweep absent) = 14 rows in `data\exports\ledger.csv`; `validate`: the four ledger tables conformant; pytest 58; ruff findings unchanged.

## 8. What was verified in the dry-run (container copy of `5dbf595`, Python 3.13.13)
- Renderers produce the exact report strings for constructed records copied from the real reports (`pairs-exact`, `improve`, `tune`, `textsweep`, `develop`, `robust` rows); live record and stored record render identically for every renderer.
- End-to-end on a synthetic dataset through the CLI: `migrate`, `features`, `predict` (recorded), `robust` (recorded, export written), `ledger-seed` (7 rows) and its refusal, `report robust` (re-rendered export byte-identical), `report ledger` (9 rows, `ledger.csv`), `report runs pairs-substrate`, `validate` (ledger tables conformant).
- `pytest -q tests/unit`: 58 passed; delivered files ruff-clean and format-clean (the known findings only).
- Not verifiable in the container: the thirteen fingerprints and the `report` byte-identity on your real data. Steps 7.3–7.4 are the proof.

## 8a. Exit evidence on Jason's machine (2026-08-30/31, pasted)
- `ledger-seed`: 7 rows (6 historical-file, 1 project-status), second run refused.
- Eight run commands recorded (`textsweep`: no text corpus, nothing recorded); all thirteen fingerprints `True` after the split writers, and `True` again after `report` regenerated the six reports from their stored records.
- `report ledger`: 14 runs -> `data\exports\ledger.csv`; `report runs develop` shows the snapshot hash; `validate`: runs 14, run_params 35+, run_metrics 361+, run_artefacts 14, all conformant (23 conformant / 0 violations / 8 absent / 5 planned of 36 declared).
- pytest 58 passed; ruff findings unchanged.
- Operator error during the block (not a code defect): an invalid `Select-Object -First 1,-Last 1` in the block skipped `predict`; it was run in a follow-up block and its fingerprint matched.

## 9. Decisions applied
- Metrics are stored as text exactly as `repr()` gives them, so a renderer formatting a stored float produces the same characters as it did from the live value (this is what makes render-from-record byte-identical).
- `data_snapshot_hash` covers (table, header, row count) of the tables a run declares as inputs; two runs are comparable only when it matches (the Harrison-versus-Jason snapshot difference shows up as different hashes in `report runs`).
- `code_ref` is read from git at run time (`unknown` if git is unavailable); legacy rows carry `880da16`.
- Legacy code is untouched; its rows come from transcription with source lines quoted in `legacy_ledger.py` and checked by a unit test.

## 10. Deferred, named here
- `objective` stays blank until gate M1-O; `holdout_access` is `yes` only on the seeded holdout row.
- Paper exhibits and PROJECT_STATUS 0.5 generated from `ledger.csv`: the DOC gate after Phase 0.
- Docs (`PROJECT_STATUS.md` 0.91, Implementation Plan v6, handoff v11): delivered after your exit-criteria paste, with the commit block.
