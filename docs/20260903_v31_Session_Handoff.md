# docs/20260903_v31_Session_Handoff.md

# Session handoff v31 — F1 in flight; everything buildable without the database is committed

Bioindustry Intelligence Platform · 2026-09-03 (evening) · supersedes v30. Read with
PROJECT_STATUS 1.14, Design Principles v6 (P1–P21), Implementation Plan v25,
Ontology v5, Data-Feeder Roadmap (amended), Constants Audit v2, F2 scope,
Hypothesis-Store Decisions, Stakes Parser Development Record.

## 1. Where the repository stands
Branch `jason/refactor`, HEAD `058d729`. 217 unit tests green. Commits this
session: fea4bfd (F1 code, tests, 13 probe fixtures, parser development
record) · 3754eb6 + 1f3b2c7 (UNSOURCED-constants correction, code and
PROJECT_STATUS) · 7b2967d (gate L4-P) · b7f6cb5 (roadmap amendment) ·
eab75eb (capture-note persistence and backfill) · ef17094 + c7f0b43
(constants audit v1, v2) · 26c5d07 (LEGACY command guard) · 8449877 (F2
scope) · 4a7c3e3 (docs v30 / 1.13 / hypothesis decisions) · 5e92aa3 (blind
sample links the captured document) · 15c5ebc (store extension) · 1c9cb47
(expert-hypothesis store) · 3399234 (annotation pass + threshold
reconciliation scope) · fd00d64 (docstring sweep) · 058d729 (F2 probe code +
raw-SQL guard; references rename cancelled).

Known pre-existing ruff findings outside gate files (improve.py E731,
score.py and study.py F841) remain deliberate human-review items.

## 2. F1 — the only work in flight
1. **Collector running** (`stakes run`), ~45% of 1,379 members, ~23k rows at
   last check, fetch failures flat at 1,082 since member 350. Safe to
   interrupt; re-running resumes for free (documents cached, rows dedup on
   key holder/issuer/as_of).
2. **Parser at rule F1-r6.** Coverage on the live library, measured five
   times with the offline analyzer: 0.881 → 0.959 → 0.975 → 0.987 → 0.992;
   XML failures 101 → 0. Sixteen probe captures are committed fixtures; 24
   verbatim layouts locked as tests. Two data-corrupting bugs were caught by
   that loop (a false 5% on exit filings; dropping exit rows entirely) —
   both recorded in the development record.
3. **Exit filings write percent 0** with the phrase verbatim in the span
   (decision of record): the amendment chain must carry the true dated fact.
   "Up to N%" is a blocker cap and stays unwritten.
4. **The r6 re-parse of record is re-running `stakes run`** after the
   collector finishes. No re-download; only the searches repeat. It also
   backfills capture notes with the search CIK list, after which any future
   rule version can re-parse from the library with no network at all.
5. **Then, in order**: `stakes sample 60` → operator judges each row against
   its filing URL (`judge F<id> correct|wrong|unsure`; four fields, all or
   nothing) → `stakes precision` (Wilson CI at F1-r6, judged-wrong rows
   retired) → stub-list decision (proposed 13D owners passing the SIC test;
   never auto-added) → thirteen fingerprints → docs → commit.

## 2a. Built ahead of the database, proofs owed at F1 close
1. **Store extension** (`update_rows`, `add_columns`): identifiers from
   schema.py, quoted; feeders contain no raw SQL. Fingerprint proof owed.
2. **Constants annotation pass**: every constant marked with its provenance
   class; thresholds centralized in schema.py with values unchanged; six
   false docstring claims corrected (all described the pre-v0.81 engine as
   live). Fingerprint proof owed. The threshold reconciliation gate — measure
   the buyer/target boundary, don't assert it — is scoped and waits for the
   database.
3. **Expert-hypothesis store**: table at schema 0.12, entry with derived
   evidence class, artifact-dated as_of, event-only resolution, per-expert
   ledger. Not wired into any model yet (aspect-match v2 owns that). A CLI
   entry form is deferred until a few rows exist by hand.
4. **Raw-SQL guard test**: SQL outside store/results/schema/migrate fails the
   suite. The `references` rename was sized and cancelled under P9.
5. **F2 probe code**: written, not run; needs the network and the database.
6. **Design Principles v6** drafted with P20 (sourced constants) and P21 (the
   store tier speaks SQL) — the operator's document; committed on approval.

## 3. Closed this session
1. **Gate L4-P** (7b2967d): the two unsourced constants in `aspect-match`
   eliminated, not re-tuned. Therapeutic-area overlap contributes its raw
   Jaccard strength (no threshold); the LOE horizon is a reported
   sensitivity across `LOE_HORIZONS = (3, 5, 7, 10)` with the pre-registered
   mark applied at each. Aspect score is now an equal-weight sum of
   strengths. L4 results of record stand and are NOT re-run; the re-run
   belongs to the v2 pre-registration.
2. **Constants audit v2** (c7f0b43): every numeric parameter in the codebase
   classified sourced / conventional / structural / protocol / UNSOURCED /
   operational, with dispositions. The MASS engine was independently
   re-derived from the paper and matches to 7e-15; one unpublished
   convention found (score 0 on Eq 8's undefined case).
3. **LEGACY guard** (26c5d07): five commands that would have overwritten
   frozen baseline files now refuse.
4. **F2 scope** (8449877): five decisions closed; build blocked on F1 close
   and an explicit go.

## 4. Open queue
1. F1 close (§2).
2. Immediately after F1 close, in this order unless the operator rules
   otherwise: the thirteen-fingerprint proof (covers L4-P, store extension,
   annotation pass); F2 probe (`priorities probe`, attach the bundle);
   threshold reconciliation measurement.
3. Post-F1 gates, order undecided: `store` extension (`update_rows`,
   `add_columns`, identifiers from schema.py — closes the raw-SQL path);
   `references` table rename (migration, after the store gate); constants
   remediation (annotate every constant, reconcile the three buyer
   thresholds and two staleness windows, sensitivity-report the `>= 8` pool
   floor, replace the drift SMA); hypothesis store (decisions recorded, two
   questions open); F2 (scoped).
4. aspect-match v2, blocked on F1 + F2, direction of record: temporal-graph
   link prediction over the dated edges the feeders supply, replacing
   hand-set aspect rules; own pre-registration; same benchmark, same
   exclusion.
5. Harrison unblock: merge, key rotation, repo visibility, USB snapshot.

## 5. Operating rules added or reinforced today
1. No numeric constant without a source line; absent one the parameter is
   eliminated or reported as a sensitivity (PROJECT_STATUS 1.11).
2. No hand-written SQL: every table read and write through `store` (P18).
   A reserved-word collision on `references` was the symptom of bypassing it.
3. Every delivered file carries a unique dated download name, and every
   document block ends with a `Select-String` verify line before the commit.
   Two stale-copy commits were caught and repaired this session.
4. Specimens go into tests verbatim, never abbreviated (an abbreviated
   parenthetical let a miss family survive an extra rule round).
5. Analysis tooling ships with any long-running step, not after it.
6. The five-command regeneration set, the legacy-six directory
   (`data\gold_frozen_20260830\`) and the exports directory are settled
   facts read from the record, never re-derived.
