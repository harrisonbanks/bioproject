# docs/20260831_v1_GATE04_INSTALL.md

# Gate 0.4 — model framework (registry, declared inputs, enforcing harness) — install runbook

Bioindustry Intelligence Platform · Implementation Plan v6 row 0.4 · 2026-08-31.
Scope approved 2026-08-31 (questions 1–3 and the scope message). Entry commit on
`jason/refactor`: `29b8701` (gate 0.3).

## 1. Package installs
None.

## 2. New files (deploy destination on line 1 of each)
| Download | Deploys to |
|---|---|
| `models__init__.py` | `src/biointel/models/__init__.py` |
| `base.py` | `src/biointel/models/base.py` |
| `registry.py` | `src/biointel/models/registry.py` |
| `adapters.py` | `src/biointel/models/adapters.py` |
| `harness.py` | `src/biointel/models/harness.py` |
| `test_models.py` | `tests/unit/test_models.py` |

## 3. Replaced files (full-file replacements; deploy path on line 1)
| Download | Replaces | Change |
|---|---|---|
| `store_v004.py` | `src/biointel/store.py` | `InputViolation`, `enforce(label, inputs)` context (table and column guard), `trace()` (records reads; used to derive declarations) |
| `schema_v005.py` | `src/biointel/schema.py` | `run_type` column on `runs` (last column; blank allowed for rows recorded before this gate); `SCHEMA_VERSION` 0.4 |
| `results_v002.py` | `src/biointel/results.py` | `run_type` context stamped on every run; `ensure_ledger_schema` adds the column to an existing ledger (legacy rows: `fit`→fit, others→evaluation) |
| `legacy_ledger_v002.py` | `src/biointel/legacy_ledger.py` | seeded rows carry `run_type` |
| `cli_v004.py` | `src/biointel/interfaces/cli.py` | `models`, `run MODEL [--impl N] [--eval N] [--as-of D]` (61 commands); `predict`, `robust`, `improve`, `develop`, `develop tune`, `develop textsweep`, `pairs-exact`, `pairs-full-exact`, `study-all` routed through the harness (every run now under input enforcement) |

## 4. Surgical edits
None.

## 5. Migration commands
None to type: the first run after install adds `run_type` to the existing `runs` table automatically (DuckDB `ALTER TABLE ADD COLUMN`; existing rows are back-filled).

## 6. Automated test command
`pytest -q tests/unit` — expected `65 passed` (58 existing + 7 framework tests).

## 7. Live verification (exit criteria)
1. `models` lists 3 models, 5 implementations (`scorecard`, `fitted`, `mass-exact`, `daily-bars` plus the evaluations of `target-screen`) with their declared inputs.
2. Every routed command runs to completion under enforcement (no `InputViolation`), records a run, and the thirteen fingerprints are `True`.
3. `run target-screen --impl scorecard`, `run acquirer-pairing`, `run target-screen --eval robust` each record a run whose `run_type` is `predict`/`predict`/`evaluation`; `run target-screen --impl fitted` reports the open decision and records nothing; `run target-screen` without `--impl` names both implementations.
4. `report ledger`: previous 14 rows plus today's runs; `validate`: `runs` conformant with the new column; pytest 65; ruff findings unchanged.

## 8. What was verified in the dry-run (container copy of `29b8701`)
- Declarations were derived by tracing every read on a 40-company fixture for each routed command and cross-checked against the column literals in `score.py`, `fit.py`, `improve.py`, `pairs.py`, `study.py`; the trace showed no price-derived read in `develop`/`tune`/`improve`/`pairs*`, and the two price-derived reads of the scorecard (`CAR12m_mean`, `MarketCap`) and the deliberate ones of `robust`.
- Enforcement: undeclared table and undeclared column each stop the run with an error naming model, table and column; enforcement is released after a failure; keys a model adds to a row (engineered features) are not guarded; a model may read back the tables it writes.
- End-to-end on the fixture with a pre-0.4 ledger: `models`, all routed commands, `run` in its four forms, `report ledger` (15 runs), `validate` conformant; `run_type` back-filled on the old rows.
- `pytest`: 65 passed; delivered files ruff-clean and format-clean.
- Not verifiable in the container: real-data branches the fixture does not exercise. If a real run raises `InputViolation`, the read is either legitimate (the declaration is corrected, one line) or a genuine leak (reported); either way the run stops rather than recording. The block's expected outputs name this possibility.

## 8a. Exit evidence on Jason's machine (2026-08-31, pasted)
- `models`: 3 models, 5 implementations, 6 evaluations with declared inputs.
- Every routed command ran under enforcement; the thirteen fingerprints `True`; `run` in its four forms behaved as specified; `report ledger` 24 runs; `validate` 23 conformant with `runs` carrying `run_type`; pytest 65; ruff unchanged.
- Enforcement caught one real-data branch the fixture had not exercised: `improve.engineer` reads `trials.CompletionDate` when `PrimaryCompletion` is blank; `develop`, `tune`, `textsweep` stopped with `InputViolation` and recorded nothing; the read is a trial date (legitimate), so `registry_v002.py` added it to the declaration and the three commands then reproduced their fingerprints. This is the intended behaviour: a declaration gap stops a run; nothing is recorded until the declaration is true.

## 9. Decisions applied
- Three models named by their question; implementations under a model; evaluations as `run_type=evaluation`; "M1/M2" labels retired from new code and documents (2026-08-31).
- P2 mechanics: fitted M&A implementations (`fitted`, `mass-exact`) declare no price-derived column and no `event_study` table (unit test); the hand-written `scorecard` declares its two price-derived reads openly, as P2 permits; `robust` declares the price columns because measuring the leak is its purpose.
- `target-screen/fitted` is registered with `run_type=fit` but has no fit/predict path: `develop` scores it and `tune` selects its configuration, nothing trains a final model and ranks with it; `run` reports this instead of inventing a training step (P9). Which implementation drives `predict` remains the open decision in PROJECT_STATUS 0.9.
- `fda-event-study` declares `bronze:prices`, which the store does not mediate; enforced once prices become a table (gate 1.4/2.8).

## 10. Deferred, named here
- `objective` per implementation: gate M1-O.
- Existing ledger rows recorded before this gate keep `run_type` blank (except legacy rows, back-filled by model).
- Docs (`PROJECT_STATUS.md` 0.92, Implementation Plan v7, handoff v12): delivered after your exit-criteria paste, with the commit block.
