# docs/20260901_v2_GATE15B_INSTALL.md

# Gate 1.5b — SEC EDGAR full-text miner + benchmark (install runbook)

Bioindustry Intelligence Platform · Implementation Plan v17 row 1.5 (second
half) · 2026-09-01. Entry commit on `jason/refactor`: 7f683ab. Built under
rule 4.20: adapter against the real EFTS response schema (capture
R292a19696cc), extractor against real filing prose (Harmony Biosciences 8-K
EX-99.1, capture R5c676d2ba8d), `ciks` filter proven by the Tempus probe
(R3f1fdfd15a0).

## 1. Package installs
None (`requests` already a dependency).

## 2. New files (deploy destination on line 1)
| Download | Deploys to |
|---|---|
| `efts_v005.py` | `src\biointel\efts.py` (v005 supersedes today's v001–v004: candidate ledger, examine(), bounded segments, assertion status, anchored year-less phrases, 6-K/20-F forms) |
| `test_efts_v005.py` | `tests\unit\test_efts.py` (fixtures: real EFTS hit, real HRMY/Merck/Tenax/Alto/Roivant/Aquestive windows from the run samples, real ICS excerpt) |

## 3. Replaced files
| Download | Replaces | Change |
|---|---|---|
| `cli_v907.py` (replacement of 1.5a's v906) | `src\biointel\interfaces\cli.py` | `mine-pdufa run|sample|precision|recall` (66th command); nothing else changed |
| `schema_v906.py` (replacement of 1.5a's v905) | `src\biointel\schema.py` | SCHEMA_VERSION 0.9; `mined_candidates` ledger table (key candidate_id; offsets, TimeML-style value/precision/`date_mod`, `anchored`, ConText-style `assertion`, `outcome_words`, `rule_version`, `decision`/`reason`); 48 declared |

## 4. Surgical edits
None. Schema adds one table: validate becomes 39 conformant / 0 / 8 absent / 1 planned (48 declared) once `mine-pdufa run` has written the ledger.

## 5. Commands
- `mine-pdufa run [--limit N] [--since YYYY-MM-DD]` — per universe company with
  a CIK: one EFTS query (`"PDUFA" OR "target action date" OR "topline data" OR
  "top-line data"`, forms 8-K/10-Q/10-K, last 365 days by default, `ciks`
  filter), newest 12 matching documents captured into the library (once; re-runs
  read the stored copy), rule-based extraction of PDUFA target dates and readout
  guidance with date ranges + precision + raw window, forward rows tier B
  (`regulatory_decision`/`pdufa_target_date`, `clinical_readout`/`guided_readout`),
  `source_url` the filing document, provenance with accession, document, phrase
  and capture hash. Past-dated candidates and no-year phrases are counted, not
  written. Polite: SEC_RATE_LIMIT between calls, backoff on 429/5xx.
- `mine-pdufa sample [N]` — a seeded random sample of mined rows with their raw
  windows for human precision judgement; `mine-pdufa precision C T` records the
  verdict as a ledger run.
- `mine-pdufa recall SNAPSHOT.ics` — recall of mined exact-date PDUFA rows against
  an operator-captured benchmark snapshot (FDA Tracker's public Google Calendar,
  one explicit capture per measurement — their terms forbid systematic
  collection, so no scheduled pulls, no redistribution; aggregate numbers only).

## 6. Automated test command
`pytest -q tests/unit` — expected `138 passed` (122 prior + 16 miner tests: real-schema
flattening, real-prose extraction incl. early/mid → year precision and
no-year skip, tier-B rows with provenance, idempotent upsert, ICS parsing, recall).

## 7. Live verification (exit criteria)
1. pytest 128; ruff clean.
2. First pass `mine-pdufa run --limit 40`: queries = companies, documents mined
   > 0, forward rows > 0; second identical run: 0 inserted, N refreshed.
3. `mine-pdufa sample 10` judged by the operator; `mine-pdufa precision C 10`
   recorded (the number is the finding, whatever it is).
4. Benchmark: one operator capture of the FDA Tracker public ICS into the
   library; `mine-pdufa recall <capture path>` recorded (the number is the
   finding); missed events listed for the next iteration of the extractor.
5. Full run (`mine-pdufa run`, no limit) after the sample is acceptable;
   runtime to be taken from the first-pass timestamps.
6. validate 38/0/8/1; thirteen fingerprints MATCH.

## 8. Dry-run evidence (container, 2026-09-01)
pytest 128 with fixtures excerpted from the three real captures; ruff clean;
CLI paths exercised with network blocked (query error counted, run recorded;
sample with no rows; precision recorded). Live shape: response schema and
prose verified against real captures; the live fetch loop is proved by your
first pass.

## 8a. Design basis (research 2026-09-01, cited in PROJECT_STATUS 1.05)
TimeML/TIMEX3 normalization (value + precision + modifier; year-less
expressions anchored to the document date and flagged); NegEx/ConText
assertion status (affirmed/negated/historical/hypothetical) so nothing
examined is discarded; Dolphin et al. 2026 grounded 8-K event extraction
(verbatim-quote grounding, dedicated quality pass, item codes too coarse);
event-study outcome categories (met / not met / safety stop) for realized
readouts at 1.5c. The ledger makes every rule change diffable by
`rule_version` and turns precision/recall into per-version published numbers.

## 9. Decisions applied / known limits
- Aggregators never a source; FDA Tracker benchmark-only under their terms.
- early/mid/late YYYY → year precision, raw phrase retained; no-year quarters
  skipped, never inferred; `asset` left blank (entity/asset resolution is L3).
- Identity for supersession is per (company, kind, accession, window); cross-
  filing supersession of a moved PDUFA date is a later refinement (the rows
  coexist, both with provenance).
- Recall matching is by exact date plus a conservative company-name overlap;
  misses are listed so name aliases can be added deliberately.

## 10. Deferred
- Cross-filing supersession; asset extraction; IR/RSS polling if recall is short;
  docs (PROJECT_STATUS 1.05, plan v18 with 1.5b DONE, handoff v24, README) with
  the gate commit after the exit paste.
