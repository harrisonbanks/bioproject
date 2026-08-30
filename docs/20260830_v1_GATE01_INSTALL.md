# docs/20260830_v1_GATE01_INSTALL.md

# Gate 0.1 — schema as code + `validate` (install runbook)

Bioindustry Intelligence Platform · Implementation Plan v2 row 0.1 · 2026-08-30.
Scope approved 2026-08-30 (items 8–15 + additions 1–3). Entry commit on
`jason/refactor`: `53cccfa` (operating manual added).

## 1. Package installs
None. No new dependency.

## 2. New files (deploy destination on line 1 of each)
| Download | Deploys to |
|---|---|
| `schema.py` | `src/biointel/schema.py` |
| `test_schema.py` | `tests/unit/test_schema.py` |
| `test_config_constants.py` | `tests/unit/test_config_constants.py` |

## 3. Replaced files (full-file replacements of the committed versions)
| Download | Replaces | Change |
|---|---|---|
| `config_v001.py` | `src/biointel/config.py` | endpoint constants `SEC_BROWSE`…`WIKI_API` defined once (were three times); `RELATIONSHIPS_CSV` once (was twice); nothing else changed |
| `cli_v001.py` | `src/biointel/interfaces/cli.py` | help line and dispatch branch for `validate` (56th command); the unused `#!/usr/bin/env python3` shebang replaced by the deploy-path comment on line 1; nothing else changed |

## 4. Surgical edits
None (both existing files are delivered whole).

## 5. Migration commands
None. Gate 0.1 makes no data change; `validate` only reads.

## 6. Automated test command
`& "<root>\.venv\Scripts\python.exe" -m pytest -q tests/unit` — expected `37 passed`
(7 existing + 22 column-equality cases + 6 validate/schema tests + 2 config tests).

## 7. Live verification (exit criteria)
1. `validate` prints one line per declared table: `OK` (with row count), `VIOLATION` (with the violation list), `absent` (file not on this machine), or `planned` (5 tables declared by design, no writer yet); final line `validate: N conformant, M with violations, A absent, 5 planned (32 declared)`. A `VIOLATION` line is a finding to paste, not a gate failure.
2. `pytest tests/unit` → `37 passed`.
3. `ruff check src scripts tests` → the nine findings recorded in handoff §3.5, plus at most findings located in `scripts/refactor/50_config_logging.py` (pre-existing, untouched); none in `schema.py`, `config.py`, `cli.py`, `tests/`.
4. `ruff format --check src scripts tests` → at most `scripts/refactor/50_config_logging.py` listed (pre-existing, untouched).
5. Regression: `predict` and `pairs-full-exact` re-run; SHA-256 of `data\gold\ma_predictions.csv` = `04061e33a77056ae6e8519273ca73c6de0329be856e389a8a69be8cb1329530d` and of `data\gold\pair_full_exact_report.txt` = `960307e2dbb259a3b6e452e005469b3e9cb7a87618a59668654f3905db35e81b`.

## 8. What was verified in the dry-run (container, copy of `53cccfa`, Python 3.13.13, venv + pip editable install)
- `pytest -q tests/unit`: 37 passed.
- `ruff check` on the five delivered files: clean; `ruff format --check` on them: clean. Repository-wide findings unchanged from baseline (nine known + `50_config_logging.py`).
- `python -m biointel validate` on an empty `data/`: 27 absent, 5 planned, exit 0; on a fixture with one conformant table and one table carrying a duplicate key and a non-numeric score: `OK`/`VIOLATION` lines as designed, exit 1.
- `python -m biointel` help prints 50 command lines; `cli.py` dispatches 56 commands.
- Not verifiable in the container: regression hashes (no data here). Step 7.5 on your machine is the proof.

## 9. Deferred, named here per manual rule 8
- `silver/prices.csv` is declared in `config.py` but no command writes it; `PRICE_COLS` is declared in `schema.py` and no table entry exists until a writer does (documented at gate 1.4 or 2.8, whichever first needs it).
- Typed edge columns `type`, `date`, `source` on `relationships.csv`: declared as optional in `schema.py`; table change at gate 2.10.
- `scripts/refactor/50_config_logging.py` lint/format findings: refactor tooling, not touched.
- Docs (`PROJECT_STATUS.md` 0.88, Implementation Plan v3 status column, handoff v8): delivered after your exit-criteria paste, with the commit block.
