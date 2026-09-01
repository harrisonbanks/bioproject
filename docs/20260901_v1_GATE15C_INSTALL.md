# docs/20260901_v1_GATE15C_INSTALL.md

# Gate 1.5c — realized events, delays and outcome states from the candidate ledger (install runbook)

Bioindustry Intelligence Platform · 2026-09-01 · entry commit 85a37b2 (1.5b-eval DONE).

## Files
| Download | Deploys to | Change |
|---|---|---|
| `efts_v011.py` | `src\biointel\efts.py` | RULE_VERSION 1.5c-r10: readout contract-clause guard ("exercisable until", "following the public announcement", "earlier of (i)"); cash-runway guard (proceeds/cash…fund operations into/through) with an expectation-verb exception so "expected in mid-2026" survives; `1H:2026`/`H1:2026` colon halves. Writers over `mined_candidates`: `write_realized` (historical readout statements → `clinical_readout`/`topline_readout_disclosed` dated by the disclosing filing, `outcome_state` mapped conservatively — met_primary / not_met / safety_stop / unspecified; past exact-day PDUFA targets → `regulatory_decision` rows; actual FDA outcomes join from Drugs@FDA at their own gate, never guessed); `write_delays` (negated guidance → `delay_timing`/`review_delay` rows; live forward rows for the withdrawn range superseded with `withdrawn_by=` recorded). CLI: `mine-pdufa write-realized` runs both. |
| `test_efts_v011.py` | `tests\unit\test_efts.py` | +7: the four r10 rule cases (Karyopharm warrant clause, runway reject/keep pair from the judged samples, colon half) and an end-to-end writer test (realized + delay + supersession + idempotence) on a composite of real windows |

## Order of operations on the machine
1. Install, pytest (157).
2. `mine-pdufa run --cached` (~27 min): the ledger gains r10 rows; retired-rule forward rows supersede.
3. `mine-pdufa write-realized`: realized + delay rows from the r10 ledger; distribution printed.
4. `mine-pdufa sample 60 --seed 505`: fresh blind sample at r10 for the ≥60-verdict measurement.
5. `mine-pdufa recall <ics>`: r10 recall.
6. All output to one file per rule 4.21; judging, precision of record, regression, docs and commit follow in the closing block.

## Exit criteria
Realized rows > 0 with the outcome-state distribution printed; delay rows > 0 with their superseded counterparts marked; r10 precision (≥60 decisive verdicts, Wilson interval) and recall recorded; pytest 157; validate 40 conformant / 0 / 8 absent / 1 planned (49 declared); thirteen fingerprints MATCH.

## Excluded (unchanged from the scope message)
Anchored year-less phrases stay held; asset/drug-name resolution is L3; IR press-release polling is its own future gate; the event-study model's declared inputs are unchanged.
