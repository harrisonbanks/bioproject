# docs/20260831_v1_GATEL2_INSTALL.md

# Gate L2 — dossier schema + span-verified seed (install runbook)

Bioindustry Intelligence Platform · Implementation Plan v14 row L2 · 2026-08-31.
Scope approved 2026-08-31; seed via the verified-overlay pattern (decision of
2026-08-31); 2.10 follows immediately after this gate. Entry commit on
`jason/refactor`: deb2121 (decision docs). Sources captured at Block L2-C
(manifest 740; verify 0 problems); the Tempus PR reference stands without a
capture (403) and no seed row cites it.

## 1. Package installs
None. No new dependency.

## 2. New files (deploy destination on line 1 of each)
| Download | Deploys to |
|---|---|
| `dossier.py` | `src\biointel\dossier.py` |
| `test_dossier.py` | `tests\unit\test_dossier.py` |

## 3. Replaced files (full-file replacements; deploy path on line 1)
| Download | Replaces | Change |
|---|---|---|
| `schema_v903.py` (replacement of 1.4's v902) | `src\biointel\schema.py` | SCHEMA_VERSION 0.6; eight tables declared live (five dossier tables per §3.10 as key–value/typed rows, each with `doc_id` + `span`; `equity_stakes`, `stated_priorities`, `assets` with the continuum-step enum); `ASPECTS` vocabulary (15 values) as the `deal_aspects.aspect` enum; the four v4 relationship type names declared (table change stays at 2.10); `ma_events` gains optional `deal_id`; nothing else changed |
| `cli_v903.py` (replacement of 1.4's v902) | `src\biointel\interfaces\cli.py` | `dossier-seed [--report]` help line and dispatch (63rd command); nothing else changed |

## 4. Surgical edits
None. `pipeline.py` is untouched at this gate.

## 5. Migration commands
Two-step by design (propose → verify → consume):
1. `python -m biointel dossier-seed --report` — resolves each seed row's SEC
   accession to its library capture, stamps no data, and prints FOUND/HELD per
   row; a HELD line lists every capture that does contain the span. Document
   assignments are proposals from Ontology §2.5/§9 until this report confirms
   them; a HELD row is fixed by reassignment on the report's evidence, never by
   weakening the check.
2. `python -m biointel dossier-seed` — loads the verified rows (full replace per
   table, idempotent; doc_ids stamped from the library at load time, no hash
   ever hand-transcribed), creates the three unseeded tables empty, records a
   ledger run; exit 1 with the held rows named if any row is held.
The seed writes no `ma_events` row (decision 2026-08-31): `labels` rewrites that
table wholesale and both entities are outside the registry until 2.9′, where the
index row attaches; the dossier tables carry `deal_id` `TEM-PSNL-20260720`
self-sufficiently.

## 6. Automated test command
`& "<root>\.venv\Scripts\python.exe" -m pytest -q tests/unit` — expected `94 passed`
(85 existing + 9 gate-L2 tests: declarations and vocabulary, normalizer,
full-seed verification, load + ledger + conformance, idempotence, held-row
refusal, report-writes-nothing).

## 7. Live verification (exit criteria)
1. pytest 94; ruff check and format --check clean on the four gate files.
2. `dossier-seed --report`: 20 rows listed; target `20 verified, 0 held`; any
   HELD line is a finding to paste (with its also-found-in captures) for
   reassignment before loading.
3. `dossier-seed`: `20 rows loaded across 5 tables; 0 held (run <id> recorded)`.
4. `validate`: `35 conformant, 0 with violations, 8 absent, 4 planned (47 declared)`
   — the eight new tables conformant (three of them empty).
5. Every loaded row carries a 64-character `doc_id` resolving to an active
   capture and its span (spot-check via the report lines).
6. Regression: the thirteen-hash loop — thirteen MATCH, PROBLEMS 0 (~2 h;
   no model, reader, or export path is touched by this gate).

## 8. What was verified in the dry-run (container, 2026-08-31, Python 3.12 as at 1.4 — operator 3.13 run is the proof of record)
- pytest 94 passed; ruff clean on the four gate files.
- End-to-end through the real CLI on a three-document fixture library keyed by
  the real accessions: `--report` 20/20 FOUND with full doc_ids; load 20 rows /
  5 tables with a recorded run; re-run idempotent (same rows, same doc_ids);
  `validate` `... 4 planned (47 declared)` with all eight tables conformant;
  held-row path exercised (8-K-only library: 10-Q/425 rows held, nothing loaded
  from them).
- Not verifiable in the container: span presence in the real filings (the
  container cannot reach sec.gov). Step 7.2 on your machine is exactly the
  instrument for that.

## 9. Decisions applied
- P19 made mechanical: a row enters only when its accession resolves to an
  active capture AND its verbatim span (whitespace-normalized, case-folded,
  tag-stripped) occurs in that capture's text; doc_id is stamped from the
  library at load time.
- Verified-overlay seed (decision 2026-08-31); manual layer (2.10) is the next
  gate and becomes the general correction path; timeline rows whose sources are
  not yet captured (Personalis investor PRs, news pieces) enter when their URLs
  are captured — seed is extended, report re-run, load re-run.
- Order of record after the membership result (MEMBERSHIP_MATCHES 0):
  L1 → 1.4 → L2 → 2.10 → 1.5 → 2.9′ → L3 → L4 (plan §4 conditional triggered:
  2.9′ precedes L3 for the lead example); recorded in the gate-close docs.

## 10. Deferred, named here
- Remaining §9 sources (Ambry/Paige PRs, Personalis investor PRs, news): each
  unlocks named timeline/comparables rows; captured whenever the operator
  supplies URLs, at any point, no gate required.
- Tempus PR capture: print-to-PDF then `library add <file> --for <ref>`.
- Docs (PROJECT_STATUS 1.02, plan v15 with L2 status + amended order, handoff
  v21, README) delivered with the single gate commit block after the exit paste.
