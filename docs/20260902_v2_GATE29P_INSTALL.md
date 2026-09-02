# docs/20260902_v2_GATE29P_INSTALL.md

# Gate 2.9′ — universe widening: Tempus and Personalis as members (install runbook)

Bioindustry Intelligence Platform · 2026-09-01 · entry commit 1b79134 (1.5c DONE).

## The rule (of record; full text in universe.py's docstring, cited in the paper)
Beyond the SIC 2834/2836 core, a diagnostics, tools or data company is admitted
as a member when it is a plausible party to biopharma M&A or FDA-adjacent events;
admission is by instance under the rule — `add TICKER` (listed, any SIC)
or `add --stub NAME [--cik C]` (private; Exchange="private" marks the
stub) — dated by the registry's Created column. First instances: Tempus AI (TEM)
and Personalis (PSNL). Membership changes are never silent: the frozen protocol
re-runs and before/after HR is recorded, and the live regression baselines are
re-hashed explicitly in the gate commit.

## Files
| Download | Deploys to | Change |
|---|---|---|
| `pipeline_v29p.py` | `src\biointel\pipeline.py` | `add_company_stub` (private stubs; IID like any member, Exchange="private") |
| `labels_v29p.py` | `src\biointel\labels.py` | standalone verified-overlay rows resolve CounterpartyIID through the registry; `apply_manual_overrides` — manual attributes `ma_events.<Column>` with entity_key `FilerTicker|AnnounceDate` applied at every labels rebuild (2.10's general override, now live) |
| `universe_v29p.py` | `src\biointel\universe.py` | widening rule recorded in the docstring of record |
| `cli_v911.py` (supersedes v909/v910) | `src\biointel\interfaces\cli.py` | `add --stub NAME [--cik C]`; labels write carries [*MA_COLS, "deal_id"] (two defects fixed on round-trip evidence: optional column dropped; list/tuple concatenation) |
| `efts_v013.py` | `src\biointel\efts.py` | `mine-pdufa run --only T1,T2` (targeted mining for new members) |
| `test_efts_v013.py` | `tests\unit\test_efts.py` | +1 (--only filter) |
| `test_widening_v3.py` | `tests\unit\test_widening.py` | stub semantics; verified-row IID resolution; manual deal_id surviving the CLI's own write, read back from the table |

## Order of operations (Block 29P-A)
1. Install; pytest 161.
2. Pre-change proof: full regression, thirteen MATCH; the pre-widening HR line is in the pairs-full-exact output.
3. `add TEM PSNL` (SEC identity fills name/CIK/SIC; description may read UNAVAILABLE without an Alpha Vantage key — cosmetic).
4. The verified overlay gains the deal row (PSNL | 2026-07-20 | Tempus AI, Inc.) and the manual layer holds `ma_events.deal_id` for it; `labels` rebuilds ma_events — the index row attaches with both IIDs and the deal_id (closing the L2 deferral).
5. `mine-pdufa run --only TEM,PSNL` proves the miners cover the new members (documents captured; any statements ledgered).
6. Frozen protocol re-runs (`predict`, `pairs-full-exact`); before/after HR recorded.
7. Close block: docs with the measured numbers, explicit re-hash of the seven live baselines (the six legacy frozen files are untouched), commit, push.

## Exit criteria
Both members resolvable by ticker and CIK; ma_events index row present with deal_id and both IIDs; targeted mine captured documents; before/after HR@5 recorded; pytest 161; thirteen MATCH pre-change; live baselines re-hashed explicitly in the commit; evidence per rule 4.21.


## Exit evidence (recorded 2026-09-02, files gate29p_a/b/c.txt)
pytest 161. Pre-change: thirteen MATCH, PRE_PROBLEMS 0. TEM IID 1379, PSNL IID 1380.
INDEX_ROW 1380 PSNL 2026-07-20 counterparty Tempus AI, Inc. 1379 deal_id TEM-PSNL-20260720 verified yes.
Targeted mine: 2 companies, 2 queries, 0 hits (diagnostics filings carry no PDUFA/readout language — finding).
Measured effect: 1,357→1,359 ranked; pool 862→863; median rank 80, hit@10 0.27, hit@25 0.39 unchanged.
validate 41/0/7/1 of 49. Seven live baselines re-hashed explicitly in the gate commit.
