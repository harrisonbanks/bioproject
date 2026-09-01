# docs/20260901_v1_GATE15B_EVAL_INSTALL.md

# Gate 1.5b-eval — measured improvement loop for the EFTS miner (install runbook)

Bioindustry Intelligence Platform · 2026-09-01 · entry commit afb064c (1.5b DONE).
Purpose: iterate the extractor on evidence until a fresh blind sample holds
precision and recall stops moving — best model, however many iterations.

## Files
| Download | Deploys to | Change |
|---|---|---|
| `schema_v907.py` | `src\biointel\schema.py` | SCHEMA_VERSION 0.10; `candidate_reviews` table (review_id; candidate_id, rule_version, verdict correct/wrong/unsure, reviewer, note, reviewed_at) — 49 declared |
| `efts_v008.py` | `src\biointel\efts.py` | `run --cached` (re-examine every captured filing with the current rules, no network); ledger-level `sample [N] [--seed S]` excluding reviewed rows; `judge ID verdict [--note]`; `precision` from stored verdicts with a Wilson 95% interval per rule version; `explain TICKER DATE` (NOT_A_MEMBER / NO_CIK / NO_DOCUMENTS / DATE_NOT_IN_DOCS / SEEN_NOT_EXTRACTED, with document snippets and ledger rows); `extras SNAPSHOT.ics` (mined exact dates absent from the benchmark, with windows); capture notes now record form and CIK |
| `test_efts_v008.py` | `tests\unit\test_efts.py` | +1 end-to-end eval-loop test (cached re-run, sample, judge, precision CI, explain paths) |

## Loop (repeat per rule version)
1. `mine-pdufa run --cached` — minutes; ledger rows written under the current RULE_VERSION; forward rows re-derived idempotently.
2. `mine-pdufa sample 60 --seed <S>` — blind draw; judge each row with `mine-pdufa judge <id> correct|wrong|unsure [--note ...]`; use a new seed per version.
3. `mine-pdufa precision` — k/n with 95% CI, recorded as a ledger run for the version.
4. `mine-pdufa recall <ics capture>` and `mine-pdufa extras <ics capture>`; for each MISSED line, `mine-pdufa explain TICKER DATE`.
5. Classify every miss and extra; turn each into a rule (with a unit test from the real window) or a coverage change; bump RULE_VERSION; go to 1.

## Exit criteria
precision from ≥60 stored verdicts on the final version with its interval; recall re-measured; each of the misses classified; each extra classified; pytest at the stated count; validate 40/0/8/1 of 49 after the first judged row; thirteen fingerprints MATCH.

## Dry-run (container)
pytest 141 (whole suite); ruff clean; eval loop exercised end to end on a real-prose fixture with stored captures (cached re-run equals the network run's windows; sample → judge → precision CI; explain paths).
