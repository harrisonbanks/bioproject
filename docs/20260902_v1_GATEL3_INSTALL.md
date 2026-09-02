# docs/20260902_v1_GATEL3_INSTALL.md

# Gate L3 — the deal analyser (install runbook)

Bioindustry Intelligence Platform · 2026-09-02 · entry commit 8e301a9 (2.9′ DONE).

## Files
| Download | Deploys to | Change |
|---|---|---|
| `analyser_v001.py` | `src\biointel\analyser.py` | new module (rule version L3-a1): `collect` (per-party EFTS full-text queries over the announcement window, merger vocabulary, forms 8-K/425/DEFM14A/PREM14A/S-4/6-K/10-Q/10-K, every hit captured); `propose` (span-grounded proposals over normalized captures — price per share, exchange ratio, termination fee, outside date, consideration form, agreement date, expected close, rationale sentences — each with capture id + verbatim span, verified by dossier.span_pattern); yardstick `compare_with_seed` (field-by-field vs the hand-built TEM-PSNL dossier); `analyse [--consume]` (review pass prints proposals with judge-able ids; consume writes span-verified rows, seed rows never overwritten, idempotent) |
| `cli_v912.py` (supersedes v911) | `src\biointel\interfaces\cli.py` | `dossier-analyse DEAL_ID [--collect] [--consume]` (67th command) |
| `efts_v014.py` (supersedes v013) | `src\biointel\efts.py` | `judge` accepts L3 proposal ids (A-prefixed; rule version L3-a1) so the review queue covers analyser output |
| `test_analyser.py` | `tests\unit\test_analyser.py` | new (+2): proposals from verbatim Tempus 10-Q prose all span-verify and match the seed yardstick; consume never overwrites a seed row and is idempotent |

## Order of operations (Block L3-A)
1. Install; pytest 163.
2. `dossier-analyse TEM-PSNL-20260720 --collect` — the paper trail into the library (the parties' CIKs over 2026-06-20..2026-12-17; expect the 8-K with the merger agreement, the 425s and the proxy when filed).
3. `dossier-analyse TEM-PSNL-20260720` — review pass: proposals with spans, the seed-yardstick table (MATCH / FOUND-DIFF / NOT-PROPOSED per field), nothing written.
4. Judge the proposals (`mine-pdufa judge A... correct|wrong`); `--consume` writes span-verified rows (seed wins on collisions).
5. Batch probe (L3-B): run on 5–10 verified historical deals for field coverage and spot-check precision.

## Exit criteria
TEM-PSNL re-derived with the field-level agreement table recorded; batch coverage and spot-check precision recorded; every consumed row span-grounded; pytest 163; fingerprints MATCH (post-widening baseline); evidence per rule 4.21.
