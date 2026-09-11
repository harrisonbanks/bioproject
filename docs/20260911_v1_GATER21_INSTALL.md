# docs/20260911_v2_GATER21_INSTALL.md

# Gate R2-1 install runbook: holistic extractor, validators, storage, tests

Scope of record: operator "go" 2026-09-11 with four amendments (Wilson-bound
acceptance; p2-only recall regression in the verdict; cross-chunk dedup
stated; M4 1.000 citation dropped) and two reviewer flags (no
review_proposals write for candidates; Haiku default rests on cost alone).
Pieces 1, 2, 3, 5 of the R2 scope. Piece 4 (trial + compare) is gate R2-2.
Expected HEAD before install: f929dea.

## 1. Package installs
None. No new dependency.

## 2. New files (download name -> deploy path)
1. 20260911_v2_extract_priority_v1.txt -> src\biointel\prompts\extract_priority_v1.txt
   (no deploy-path line inside: the file is prompt text; path lives here)
2. 20260911_v2_GATER21_INSTALL.md -> docs\20260911_v1_GATER21_INSTALL.md

## 3. Replaced files (full-file replacements of the f929dea versions; the
## block refuses if the deployed file's hash is not the f929dea hash)
1. 20260911_v2_priorities.py -> src\biointel\priorities.py
   Adds, before `def cli`: R2_PROMPT_VERSION, R2_EXTRACTOR_VERSION,
   R2_CHUNK_CHARS (20,000), R2_CHUNK_OVERLAP (1,000), R2_MAX_CANDIDATES (12),
   _R2_LINE_RX, _chunk_item1, _r2_prompt, _parse_r2_reply, _r2_validate,
   _r2_dedup, extract_priorities_llm. No existing symbol changes;
   RULE_VERSION_F2 stays L3-a3-p2.
2. 20260911_v2_schema.py -> src\biointel\schema.py
   SCHEMA_VERSION 0.21 -> 0.22; STATED_PRIORITY_R2_COLS; Table
   silver/stated_priorities_r2.csv (key entity_key, stated_at, category,
   statement, extractor_version; category enum = PRIORITY_CATEGORIES).
3. 20260911_v2_config.py -> src\biointel\config.py
   Appends R2_ENABLED = False, R2_MODEL = "claude-haiku-4-5",
   R2_CALL_CAP = 400, R2_MAX_TOKENS = 1500.
4. 20260911_v2_test_priorities.py -> tests\unit\test_priorities.py
   Appends 13 tests (43 -> 56 in the file): chunker, reply parser
   (well-formed, malformed, NONE, empty, cap), validator on the locked
   specimens (Opus negation, Knight ROFN, S02a95e bullet debris, Akorn
   pass, unknown category, paraphrased span), dedup, end-to-end
   extract_priorities_llm with a fake `call` (stated seam: no API), and
   config/schema declarations.

## 4. Surgical edits
None. Every touched file ships whole.

## 5. Migration
None. store._ensure_meta rewrites meta.schema_version to 0.22 on the next
connect; the new table is created on first write (gate R2-2).

## 6. Design decisions folded in
1. Dedup key: (category, whitespace-normalized lower-cased sentence), first
   occurrence wins, applied to raw candidates across chunks and again to
   survivors after relabel (p2's own key).
2. Validator order: category enum -> verbatim locate (body.find must hit;
   _locate_sentence's truncated fallbacks are not accepted for R2 spans)
   -> _NEGATION_RX -> _validate_cluster (wrong refuses; wrong-with-relabel
   rewrites the category; any other result passes).
3. Candidates are not written to review_proposals. stated_priorities_r2
   holds every survivor with extractor_version, model_id, chunk_index.
4. Every degraded call (None) is counted in api_failures and records nothing.

## 7. Verification in container (advisory, Python 3.12.3)
ruff: exactly 3 pre-existing findings. collect-only: 315. Suite: 311 passed,
4 failed (the four documented test_stakes fixture failures on the unedited
baseline). Disk verification by a separate process confirmed each new
symbol exists exactly once and the p2 symbols are unchanged.

## 8. Exit criteria (operator's machine, evidence 20260911_v51e_r21_install_evidence.txt)
1. AT-HEAD hashes of the four replaced files equal their f929dea hashes.
2. Every DOWNLOAD and DEPLOYED hash equals its card hash.
3. `pytest --collect-only -q tests\unit` reports 315.
4. `pytest -q tests\unit` reports 315 passed.
5. `ruff check src tests` reports Found 3 errors.
6. Commit lands; push succeeds; ORIGIN MATCH: True.

## 9. Deferred to gate R2-2
r2_trial, r2_compare, cli branches r2-trial and r2-compare, Wilson-bound
acceptance printout, p2-only regression per category, the 120-doc trial
(<= 400 calls, <= $0.60 Haiku / <= $2.10 Sonnet at the S5 anchors), and its
section-5 disclosure before the first call.
