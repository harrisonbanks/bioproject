docs/20260831_v1_GATEL1_INSTALL.md

# Gate L1 — research library / file room (Ontology v5 §3.9; Implementation Plan v11 row L1)

## 1. Package
| Download | Deploys to |
|---|---|
| schema_v901.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\schema.py (replacement; v901 series avoids colliding with unknown prior download counters) |
| cli_v901.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\interfaces\cli.py (replacement) |
| pyproject_v901.toml | C:\Users\JB\Documents\dev\bioindustry\pyproject.toml (replacement; adds optional extra [zotero]) |
| library.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\library.py (new) |
| collectors_init.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\collectors\__init__.py (new) |
| manual.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\collectors\manual.py (new) |
| folder.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\collectors\folder.py (new) |
| pipeline_docs.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\collectors\pipeline_docs.py (new) |
| zotero.py | C:\Users\JB\Documents\dev\bioindustry\src\biointel\collectors\zotero.py (new) |
| test_library.py | C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_library.py (new) |
requirements.lock unchanged (pyzotero is optional; install only with: pip install -e ".[zotero]").

## 2. Implementation notes
- Files dedupe on disk by SHA-256 (one file per hash); the captures table is keyed (capture_id, ref_id) so the same bytes may serve two references without a second copy (stated deviation from §3.9's "hash is the primary key", disk-single-copy preserved).
- Pre-existing repo-wide ruff findings (improve.py E731, score.py F841, one further) are outside this gate's files and untouched (P7 discipline); the gate's ruff check targets the changed files.
- Dry-run evidence (container, 2026-08-31): pytest 76 passed; ruff clean on changed files; index idempotent on fixtures; add/no-fetch/retire/manifest/verify/site exercised through library.cli; 4 ledger runs recorded.

## 3. Verified behaviours (container)
Index twice (3 fixtures): "3 references, 3 captures, 3 links" then "0, 0, 0". File add: "created reference …; capture added". URL --no-fetch: "capture none". retire-capture: "retired 1". verify after manifest: "0 problems"; after tampering a file: 2 problems reported.

## 4. Commands added
library add <url-or-file> [--type T] [--entity K]... [--for REF] [--no-fetch] [--kind K] [--title|--published|--publisher|--url|--note|--subject|--accession|--doi ...]
library import <folder> [--type T] [--entity K]... · library index · library import-zotero [--data-dir P]
library find [--entity|--type|--text|--publisher|--since] · list · show REF · open REF · view --entity K · site
library manifest · verify · merge <folder> · dedupe [--keep A --merge B] · retire-capture ID [--reason ...]

## 5. Exit criteria — numbered, evidenced by the Block A paste
1. pytest: 76 passed. 2. ruff (changed files): All checks passed. 3. library index: 733 files seen; references ≤ 733 (multi-doc accessions attach), captures = 733 unless identical bytes, links ≤ references; second run adds 0/0/0. 4. URL add: capture added (fetched_html). 5. File add: capture added. 6. --no-fetch: reference without capture. 7. retire-capture: 1 row. 8. dedupe: 0 candidate pairs. 9. validate: 26 conformant / 0 violations / 8 absent / 5 planned. 10. manifest: files = captures on disk; verify: 0 problems. 11. ledger: ≥ 6 library runs in ledger.csv. 12. Regression: thirteen MATCH lines, REGRESSION CHECK PASSED (~2 h unattended).

## 6. After the paste
Docs (PROJECT_STATUS 0.99, plan v12 L1 DONE, handoff v18, MACHINE_RUNBOOK data layout, README) delivered with the single gate commit block; nothing is committed before the paste.
