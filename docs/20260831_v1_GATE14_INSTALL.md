# docs/20260831_v1_GATE14_INSTALL.md

# Gate 1.4 — event table + forward FDA calendar view (install runbook)

Bioindustry Intelligence Platform · Implementation Plan v12 row 1.4 (F1) · 2026-08-31.
Scope approved 2026-08-31 with two amendments: (1) `event_date` (date the action
occurred, blank on forward rows) added to EVENT_TABLE_COLS; `scheduled_date` keeps
its declared meaning (goal or expected date) and is never used for realized action
dates; (2) the v4 event-class enum values are declared now so the table's vocabulary
is complete from birth, with only `regulatory_decision` populated at this gate.
Entry commit on `jason/refactor`: `79a87a0` (gate L1).

## 1. Package installs
None. No new dependency; `requirements.lock` unchanged.

## 2. New files (deploy destination on line 1 of each)
| Download | Deploys to |
|---|---|
| `test_events_table.py` | `C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_events_table.py` |

## 3. Replaced files (full-file replacements; deploy path on line 1)
| Download | Replaces | Change |
|---|---|---|
| `schema_v902.py` (replacement of L1's schema_v901) | `src\biointel\schema.py` | `SCHEMA_VERSION` 0.5; `event_date` added to `EVENT_TABLE_COLS` (position 6, before `scheduled_date`); the seven v4 event classes appended to `EVENT_CLASSES` with no outcome states (writers arrive at L2/1.6 per the plan); `events_table` un-marked as planned and declared live: key `(event_id)`, date/datetime types, `event_class` enum over the complete class vocabulary; nothing else changed |
| `pipeline_v901.py` (first whole-file replacement of the pre-L1 pipeline_v001) | `src\biointel\pipeline.py` | `read_events_table()`; `_events_table_rows()` (deterministic mapping incl. the provenance key=value carry of AppNo/SubType/ClassCode/Priority); `build_events_table()` (`events-migrate`, ledger run per P17); `pipeline_calendar()` re-pointed to a view over trials + events_table with forward rows (`Source='FDA forward'`) and an explicit `FDA (events)` fallback before migration; nothing else changed |
| `cli_v902.py` (replacement of L1's cli_v901) | `src\biointel\interfaces\cli.py` | help lines for `calendar` and `events-migrate`; `calendar` prints the forward-row count line (or the fallback note pre-migration); `events-migrate` dispatch (62nd command); nothing else changed |

## 4. Surgical edits
None (existing files delivered whole).

## 5. Migration commands
`python -m biointel events-migrate`, once. Copies every `events` row into
`events_table` (mapping: Event Approval→outcome_state `approval`, Rejection→`crl`;
Outcome→`outcome_subtype`; Date→`event_date`; Drug→`asset`; `scheduled_date`
blank; AppNo/SubType/ClassCode/Priority preserved in `provenance` as key=value
pairs). Deterministic `event_id` = hash of the events key, so a re-run replaces
the table with identical rows (safe). Expected print: one line,
`events-migrate: N events_table rows written from N events rows (run <id> recorded)`
with the two N equal. Runtime: seconds on the operator machine.

## 6. Automated test command
`& "<root>\.venv\Scripts\python.exe" -m pytest -q tests/unit` — expected `85 passed`
(76 existing + 9 gate-1.4 tests: declaration, vocabulary, mapping, idempotence,
ledger run, validate conformance, view incl. forward row and fallback).

## 7. Live verification (exit criteria)
1. `events-migrate`: written row count equals the `events` source row count exactly.
2. `validate`: `27 conformant, 0 with violations, 8 absent, 4 planned (39 declared)`
   — `events_table` moved from planned to conformant; every other line unchanged.
3. `calendar IID` (any company with FDA events): trials + FDA rows printed from the
   event table, the CSV in `data\exports\`, and the closing line
   `forward FDA calendar rows: 0 (writers arrive at gates 1.5/1.6)`.
4. pytest: 85 passed; ruff check and format --check clean on the four gate files
   (pre-existing repo-wide findings untouched, P7 discipline).
5. Ledger: the `events-migrate` run visible in `report ledger` (row count ≥ 36 runs).
6. Regression: regenerate `predict`, `pairs-full-exact`, `pairs-exact`, `develop`,
   `develop tune`, then the thirteen-hash PowerShell loop — thirteen MATCH lines,
   `REGRESSION CHECK PASSED` (~2 h unattended; `study.py`, `score.py`, the model
   declarations and every `events` reader are untouched, so no fingerprint moves).

## 8. What was verified in the dry-run (container copy of 79a87a0, 2026-08-31)
- pytest: 85 passed (whole suite).
- ruff check and format --check: clean on the four gate files.
- End-to-end through the real CLI on a two-event fixture: `events-migrate` wrote
  2/2 with a recorded run; second run idempotent (same deterministic ids);
  `calendar 7` printed the trial row, both FDA rows served from `events_table`,
  and `forward FDA calendar rows: 0`; `validate` reported `events_table` conformant
  and `4 planned (39 declared)`; help dispatches 62 commands.
- Deviation stated per rule 31: the container had Python 3.12.3 (no 3.13 build
  available in it today), so the dry-run ran on 3.12 with the same dependency set;
  no 3.13-only syntax is used and the operator machine's 3.13 run in Block A is
  the proof of record.
- Not verifiable in the container: the real row counts, the thirteen fingerprints
  and validate's 27/0/8/4 on real data. Step 7 on your machine is the proof.

## 9. Decisions applied
- Date semantics (approved 2026-08-31): realized action dates live in `event_date`
  only; `scheduled_date` is reserved for goal/expected dates; a unit test asserts
  migrated rows leave `scheduled_date` blank.
- Vocabulary-complete-from-birth (approved 2026-08-31): all fifteen event classes
  (eight from the FDA Catalyst Research §4 taxonomy + seven v4 classes) are legal
  `event_class` values now; only `regulatory_decision` has a writer at this gate.
- The `events` table and its readers are untouched (exit criterion: hashes
  unchanged); `events_table` is regenerable from `events` at any time, and the
  columns it does not model travel in `provenance`, so nothing is lost.

## 10. Deferred, named here
- Forward-row writers (EFTS 8-K mining, AdCom calendar, CT.gov primary completion):
  gates 1.5 and 1.6, as planned.
- Outcome-state vocabularies for the seven v4 classes: defined at the gate that
  writes each class (L2 for the deal/stake classes).
- L2 dependency flag from the scope stands: gate 2.10 (manual layer) is unbuilt
  and L2's exit depends on it; to be resolved at the L2 scope message.
- Docs (PROJECT_STATUS 1.00, Implementation Plan v13 with the 1.4 status column,
  handoff v19, README): delivered after your exit-criteria paste, with the commit
  block; nothing is committed before the paste.
