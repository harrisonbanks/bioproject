# docs/20260831_v2_GATE15A_INSTALL.md

# Gate 1.5a — forward FDA calendar: CT.gov primary completion + FDA AdCom (install runbook)

Bioindustry Intelligence Platform · Implementation Plan v16 row 1.5 (first half) ·
2026-08-31. Scope approved 2026-08-31 (cut B): 1.5a = schema additions + two
deterministic writers; 1.5b = SEC EDGAR full-text miner + FDA Tracker discovery
and recall benchmark. Entry commit on `jason/refactor`: bd03981.

## 1. Package installs
None.

## 2. New files (deploy destination on line 1)
| Download | Deploys to |
|---|---|
| `forward_v002.py` | `src\biointel\forward.py` (v002 supersedes the v001 delivered earlier today: AdCom writer rebuilt on the JSON endpoint after the live page proved to be a client-side shell) |
| `test_forward_v002.py` | `tests\unit\test_forward.py` (fixture = verbatim records from the real endpoint response captured 2026-08-31) |

## 3. Replaced files (full-file replacements; deploy path on line 1)
| Download | Replaces | Change |
|---|---|---|
| `schema_v905.py` (replacement of 2.10's v904) | `src\biointel\schema.py` | SCHEMA_VERSION 0.8; `events_table` gains optional forward columns `scheduled_date_end`, `date_precision` (day/month/quarter/half/year), `date_raw`, `status` (blank/superseded), `confidence_tier` (A FDA page / B SEC filing / C CT.gov estimate / D aggregator-only), with enums; existing 4,282 rows stay conformant; nothing else changed |
| `pipeline_v902.py` (replacement of 1.4's v901) | `src\biointel\pipeline.py` | `events-migrate` now preserves forward rows and writes the full column set (a re-run can no longer erase the calendar); nothing else changed |
| `cli_v906.py` (replacement of 2.10's v904; supersedes today's v905) | `src\biointel\interfaces\cli.py` | `calendar-forward [trials\|adcom\|all] [--file RESPONSE.json]` (65th command); `calendar` summary line reads `forward FDA calendar rows: N`; nothing else changed |
| `library_v003.py` (replacement of L1's v002) | `src\biointel\library.py` | `manifest()` no longer lists the manifest file itself (the L1 defect that produced `ALTERED manifest-sha256.txt` on every re-run); nothing else changed |
| `test_library_v002.py` (replacement of L1's test file) | `tests\unit\test_library.py` | one regression test appended for the manifest fix |

## 4. Surgical edits
None.

## 5. Migration commands
`calendar-forward trials` — pure database transform: every future `PrimaryCompletion`
in `trials` becomes a `clinical_readout` forward row, outcome_subtype
`estimated_primary_completion` (never "results expected"), tier C, source_url the
CT.gov study page. Deterministic ids; re-runs refresh `last_verified`; a moved date
inserts a new row and marks the prior one `superseded`. Runtime: seconds to a
minute over 129,978 trials.
`calendar-forward adcom` — fetches the official calendar's data endpoint,
`https://www.fda.gov/datatables-json/advisory-committee-calendar-json` (the
calendar page itself is a shell filled client-side — verified 2026-08-31 from the
captured page and the browser network log), captures the JSON response into the
research library as a dated snapshot, and writes two forward rows per meeting
dated today or later: the meeting (tier A, day precision) and the briefing-document
release (tier B, derived: meeting minus 2 business days, FDA's stated rule). The
endpoint returns the full history back to 2016; past and postponed/cancelled
records are counted, not written. If the endpoint refuses automated access, save
the response from the browser's Network panel and run
`calendar-forward adcom --file <saved.json>`. Company attribution is a conservative
verbatim name match on the meeting title; unmatched meetings carry a blank
entity_key (entity resolution is L3/2.9′).

## 6. Automated test command
`pytest -q tests/unit` — expected `122 passed` (103 prior + 18 gate-1.5a tests + 1 manifest regression test:
date-range parser, business-day arithmetic, schema declaration, trials writer
mapping, refresh + supersession, migrate-preserves-forward-rows, AdCom parser,
AdCom writer with entity match and idempotence).

## 7. Live verification (exit criteria)
1. pytest 121; ruff clean on gate files.
2. `calendar-forward trials`: N future primary-completion rows inserted (N is your
   data's count; the criterion is inserted = candidates on first run, and
   refreshed = candidates on an immediate second run).
3. `calendar-forward adcom`: records parsed in the hundreds, upcoming meetings ≥ 1
   and 2× that many rows inserted (fetched or via `--file`); `library manifest`
   then `library verify: 0 problems`.
4. `calendar IID` for a company with a future trial shows `forward FDA calendar
   rows: k` with k ≥ 1.
5. `validate`: `38 conformant, 0 with violations, 8 absent, 1 planned (47 declared)`
   with `events_table` rows = 4,282 + forward rows.
6. Thirteen fingerprints MATCH (events_table is not a model input; by construction).

## 8. Dry-run evidence (container, 2026-08-31)
pytest 121; ruff clean; real-CLI fixture run: migrate → trials 1 inserted / then
1 refreshed → adcom via saved copy 2 meetings → 4 rows with a library capture →
fetch-failure path graceful (exit 1, nothing written) → `calendar 7` shows
`forward FDA calendar rows: 1` → events-migrate re-run kept the forward rows →
library verify 0 → validate `1 planned (47 declared)`. fda.gov is unreachable from
the container, so the live fetch is proved on your machine (step 7.3).

## 9. Decisions applied / known limits
- Primary completion ≠ readout, encoded in the row label and class.
- Date ranges + raw language retained; supersession keeps history.
- Known limit: `trials.PrimaryCompletion` is stored as a strict YYYY-MM-DD, so
  CT.gov month-only dates were normalized at ingest and their precision is
  recorded as `day`; keeping the raw CT.gov form (and its estimated/actual type)
  is a trials-collector change for a later gate — the parser already handles
  month/quarter/half forms for when it lands and for 1.5b.
- AdCom parser is built and tested against the real endpoint response; any
  endpoint change surfaces as `0 records`, never as silent rows.
- Testing standard adopted 2026-08-31: a parser for an external page or API is
  delivered only after a real capture exists, and its fixture is that capture (or
  an excerpt); dry-run notes state "logic verified" vs "live shape verified".

## 10. Deferred, named here
- 1.5b: EDGAR full-text miner (efts.sec.gov), FDA Tracker terms check → discovery
  feed and recall benchmark, precision spot-check, tier B rows.
- Trials collector: retain raw CT.gov date form and type.
- Docs (PROJECT_STATUS 1.04, plan v17 with 1.5a DONE, handoff v23, README) with the
  single gate commit after the exit paste.
