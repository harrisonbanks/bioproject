# docs/20260830_v1_GATE02_INSTALL.md

# Gate 0.2 — storage migration to DuckDB (install runbook)

Bioindustry Intelligence Platform · Implementation Plan v4 row 0.2 · 2026-08-30.
Scope approved 2026-08-30 (questions 1–5 and the scope message). Entry commit on
`jason/refactor`: `ffbbf20` (thirteen-file regression baseline).

## 1. Package installs
`pip install -e ".[dev]"` once: adds `duckdb>=1.3,<2` (declared as a core dependency in
`pyproject.toml`). The block regenerates `requirements.lock` (UTF-8) afterwards.

## 2. New files (deploy destination on line 1 of each)
| Download | Deploys to |
|---|---|
| `migrate.py` | `src/biointel/migrate.py` |
| `test_store.py` | `tests/unit/test_store.py` |

## 3. Replaced files (full-file replacements; deploy path on line 1)
| Download | Replaces | Change |
|---|---|---|
| `store_v002.py` (v001 superseded: its temporary-CSV bulk path failed on Windows, WinError 32, because DuckDB keeps the file open after `read_csv`) | `src/biointel/store.py` | DuckDB store layer added below the bronze helpers: `connect`, `close`, `read_table`, `write_table`, `has_table`, `table_columns`, `export_csv`, `write_export`, `read_csv_rows`, `table_name` |
| `config_v002.py` | `src/biointel/config.py` | P16 paths: `DUCKDB`, `EXPORTS`, `SNAPSHOTS`, `SILVER_CSV_SRC`, `GOLD_CSV_SRC`, `FROZEN_TAG`; `SILVER`/`GOLD` now the frozen legacy folders; only `bronze`, `exports`, `snapshots` auto-created |
| `schema_v003.py` | `src/biointel/schema.py` | `SCHEMA_VERSION`; `validate_rows` shared checker; `validate_db`; `model_panel` label flags declared blank-or-0/1 (the writer emits blank when a quarter has no label row) |
| `cli_v002.py` | `src/biointel/interfaces/cli.py` | table writes through the store; `calendar`/`window` exports to `data\exports\`; `freeze` copies the database file to `data\snapshots\<date>\`; `migrate` (57th command); `validate` checks the database; help text updated |
| `pipeline_v001.py` | `src/biointel/pipeline.py` | `_read`/`_write` are table-name helpers over the store; every `config.*_CSV` site re-pointed |
| `labels_v001.py` | `src/biointel/labels.py` | every CSV site re-pointed (`ma_events_universe`, `qa_worklist`, `universe`, `ma_events_verified`) |
| `features_v001.py` | `src/biointel/features.py` | `_load(table)` over the store |
| `score_v001.py` | `src/biointel/score.py` | reads via store; writes table `ma_predictions` and exports `data\exports\ma_predictions.csv` |
| `universe_v001.py` | `src/biointel/universe.py` | writes table `universe` |
| `pairs_v001.py` | `src/biointel/pairs.py` | reads via store; `pair_feature` table; reports to `data\exports\` |
| `improve_v001.py` | `src/biointel/improve.py` | live parts via store (`activist_13d` table, `pair_feature`, `trials`, `companies`); reports and `best_config.json` to `data\exports\`; `holdout` marked LEGACY |
| `fit_v001.py` | `src/biointel/fit.py` | `robust`, `improve`, `_events_for_robust` via store; reports to `data\exports\`; gen-1 `fit` marked LEGACY on the frozen folder |
| `baselines_v001.py` | `src/biointel/baselines.py` | LEGACY banner only; code unchanged; reads the frozen folders |
| `chembl_v001.py` | `src/biointel/sources/chembl.py` | reads via store; writes table `drug_targets` |
| `orangebook_v001.py` | `src/biointel/sources/orangebook.py` | reads `events` via store |
| `patents_v001.py` | `src/biointel/sources/patents.py` | reads via store; writes table `patents`; SQL to `data\exports\` |
| `pyproject_v001.toml` | `pyproject.toml` | `duckdb>=1.3,<2` core dependency; version 0.90 |

## 4. Surgical edits
None.

## 5. Migration commands
`python -m biointel migrate`, once. It refuses if `data\biointel.duckdb` exists; loads every declared table present under `data\silver\` and `data\gold\` after validating it; prints `loaded <table> <n> rows (csv <m>)` per table (n must equal m); renames the folders to `data\silver_frozen_20260830\` and `data\gold_frozen_20260830\`. Close any file open from `data\gold\` before running (Windows cannot rename a folder with an open file).

## 6. Automated test command
`pytest -q tests/unit` — expected `46 passed` (37 existing + 9 store/migrate tests).

## 7. Live verification (exit criteria)
1. `migrate`: every present table loaded with equal counts; 0 mismatches; folders renamed.
2. `validate`: every loaded table conformant (`OK`) in the database.
3. `pytest`: 46 passed; `ruff check`: the nine known findings only; `ruff format --check`: only `scripts/refactor/50_config_logging.py`.
4. Regression: `data\exports\` deleted, then `predict`, `pairs-full-exact`, `robust`, `improve`, `pairs-exact`, `develop`, `develop tune` re-run; the seven files in `data\exports\` and the six legacy files in `data\gold_frozen_20260830\` match all thirteen fingerprints in `docs/regression_baseline.txt` (`text_sweep_report.txt` stays absent).
5. `python -m biointel` help prints 51 command lines; `cli.py` dispatches 57 commands.

## 8. What was verified in the dry-run (container copy of `ffbbf20`, Python 3.13.13, venv + pip, duckdb 1.5.5)
- Store fidelity: 130,000-row write 0.6 s, read 0.5 s; rows identical to a `csv.DictWriter`/`DictReader` round trip including quotes, embedded newlines, `None` and float cells; `export_csv` byte-identical to the csv module's output.
- Constraints: type, allowed-value and key violations rejected by DuckDB; a failed write leaves the previous contents intact.
- End-to-end on a synthetic four-company dataset through the real CLI: `migrate` (12 tables, counts equal, folders renamed), second `migrate` refused, `features`, `predict` (writes table and export), `robust`, legacy `pairs` (frozen CSVs), `freeze` (snapshot file), `validate` all conformant.
- `pytest -q tests/unit`: 46 passed; delivered files ruff-clean and format-clean.
- Not verifiable in the container: the thirteen fingerprints (no real data). Step 7.4 on your machine is the proof.

## 8a. Exit evidence on Jason's machine (2026-08-30, pasted)
- `migrate`: 19 tables loaded, every count equal to its CSV (largest: trials 129,978; feature_panel/label_panel/model_panel 91,014), folders renamed; second `migrate` refused.
- `validate` on the database: 19 conformant, 0 violations, 8 absent, 5 planned.
- `pytest`: 46 passed; `ruff check`: nine known findings; `ruff format --check`: only `50_config_logging.py`.
- Regression: all thirteen fingerprints `True` (seven regenerated into `data\exports\`, six legacy files unchanged in `data\gold_frozen_20260830\`); `text_sweep_report.txt` absent as expected.
- Defect found and fixed during the gate: the v001 bulk-insert path used a temporary CSV that Windows could not delete (WinError 32); v002 hands NumPy object arrays to DuckDB directly (no file). Lesson recorded: a Linux dry-run does not prove Windows file-handle behaviour; anything that writes temporary files needs a Windows paste before it counts.

## 9. Decisions applied and their consequences
- Values are stored as text (exactly as CSV held them); declared types, allowed values and keys are enforced as database constraints on every write; typed reads (`read_table(name, typed=True)`) cast per `schema.py` and are for new code and per-module convergence (P18).
- Because the database refuses a nonconformant write where the CSV layer silently wrote it, a command can now fail where it used to succeed with bad data; that is intended. Two declarations were relaxed to match what the writers actually emit (`ma_events.S5_CeasedFiling` blank at gate 0.1; `model_panel` label flags blank when the label join misses).
- Legacy code (`baselines.py`, `improve.holdout`, `fit.fit`) reads the frozen CSV folders; the helpers it imports from `pairs.py` (`_firm_docs`, `_acquirer_side_iids`) and `improve.engineer`/`_load_panel` are live code and read the database; stated in each LEGACY banner.

## 10. Deferred, named here
- `scripts/refactor/_regress.py` still hashes `data\gold\...`; it is refactor tooling and is not updated; the run block hashes the new locations directly.
- `PROJECT_STATUS.md`, Design Principles v4 (P18), Implementation Plan v5, handoff v10: delivered after your exit-criteria paste, with the commit block.
