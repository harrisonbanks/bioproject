# docs/20260910_v48_Session_Handoff.md — paste this as the first message of the new chat

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`,
branch `jason/refactor`, HEAD = the close-out commit following `5848d95` (verify
with `git --no-pager log --oneline -1` pasted by the operator). Windows, root
`C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`, Python 3.13, single
DuckDB store at `data\biointel.duckdb`. Suite of record: **290 passed**, ruff
exactly 3 pre-existing findings (improve.py E731, score.py F841, study.py F841).

**FIRST ACTIONS, in order:** (1) confirm this handoff read in full; (2) operator
pastes HEAD + `pytest -q tests/unit` (290) + `ruff check src tests` (3) as the
environment proof of record; (3) read docs/PROJECT_STATUS.md v1.27 and
docs/20260910_v1_Text_Extraction_Research_and_Roadmap.md (operator-commissioned,
5848d95); (4) report the self-check with exact numbers BEFORE any design or code.

## 0. STATE: THE F2 CORPUS IS FULLY JUDGED (2026-09-10)

Zero unjudged stated-priorities rows. Final ledger (evidence
20260910_v48aj_final_35_evidence.txt): 2,873 machine draft verdicts (never
counted); PATTERN-RULED 1,546 (correct 458 / wrong 1,053 / unsure 35); operator
tiers 10k_strategy 51/55 = 0.927, investor_day 28/28 = 1.000;
ASSIST-AGREEMENT 108/203 = 0.532; settled-excluded 167. Roughly 87% of the
corpus settled by machinery citing operator rulings, with provenance on every
verdict (reviewer = operator | operator-pattern | draft-agree | draft-restore).

## 1. THE PRECEDENT TABLE (rulings of record; specimen = verbatim test or key)

| Ruling | Specimen(s) | Operator rationale (one line) | Enforced at |
|---|---|---|---|
| Galera: named indication beats modality flavor | Verastem cancer sentence (verbatim test) | a named disease makes the TA stamp correct regardless of modality color | `_validate_cluster` disease→named-indication-correct + contamination test |
| Payload beats stamp flavor, SYMMETRIC | S13ebad (Fabry), S3d729 (frataxin), S31fc9, S4651a | one rule both directions: indication payload→therapeutic_area, pipeline payload→pipeline_gap; repair-not-delete | indication-relabel / pipeline-relabel branches + `test_payload_beats_stamp_flavor_symmetric_rule` |
| uniQure: pipeline payload is correct | Sienna sentence (verbatim test), S09db92 | dual-coverage whose main point is pipeline stays correct | pipeline-correct branch + test |
| Fortress/Abpro: acquisition intent is correct; main-clause test | S1ba1d (criteria-list → wrong), S7d162 (explicit main clause → correct) | "we intend to acquire a business" as main clause is a genuine priority; criteria tails are not | acquisition-correct branch; Abpro test applied at residual level |
| Lumos: discovering-acquiring verb chain + named TAs | S0fa320, S4aa8a3, S6604d6, S99c5df, S8f61ee | the acquiring verb makes pipeline_gap fair even with named TAs; mechanism is flavor, the chain is pipeline | acquisition-correct branch (verb) + residual rulings |
| Arbutus: license-OUT is wrong | S24bdd2, S21ad3b, S2b7bd2, S317e5a, S65f03c, S6df53f, S497ad9, S8763f1, S78d4cf + tail eight | out-direction licensing is never a pipeline priority | out-licensing branch (`_OUTLICENSE_TERMS`/`_RX`) + family test |
| Nomad: seeking-partners-to-DEVELOP is correct | S0a5cf4, S5bc77f; boundary specimen S7ae804 (both flavors, develop wins) | development partnering counts, out-licensing doesn't | kept HUMAN by design (validator test asserts None on the Nomad shape) |
| Attribution beats Nomad (and everything else) | Sa4d0c5/Sc9e9bd/Sd944f8 (Sesen text on Carisma CIK) | a proven company mismatch defeats any content reading; company is a Q5 field | human-ruled; nine-row evidence pile on the p2 docket |
| TScan: HR/personnel sentences are wrong | S290aa2 | staffing is not a strategic priority category | residual precedent |
| TCR2: regulatory-milestone statements are wrong | S72d8cd, S9c94eb | a filing milestone is not a pipeline priority | residual precedent |
| Competitor-risk disclosures are wrong | S092bfb, S69904 | risk-factor text about competitors is not the filer's priority | competitor-risk branch (ordered before acq/disease) + test |
| Going-concern financing is wrong | S3b6649, S511f6c, S6fbb1d, Se5903e | financing dependence is a disclosure, not a priority | going-concern branch + test |
| Veterinary-generic is wrong | S1326e5, S51357, S6bc50e, Se44567 | out-of-scope vertical, generic missions | veterinary branch + test |
| IP-protection is wrong (Alaunos family) | S1d1690, S5a5814 + clusters | protecting IP is not a stated pipeline/TA/platform priority | ip-protection branch |
| Garbled/truncation debris is wrong | bullet-char rows; negation clip S1e6a83 (verbatim test); misquote pair Sa0aafb/Sde5e86 (Sonnet text-vs-filing diffs banked) | slicer artifacts are never priorities; every specimen feeds p2 | garbled branch + `_GARBLED_PATTERNS` + p2 pile |
| Commercial-infrastructure HOLD (unsure) | specimen list in docs/20260908_v1_Vocabulary_Gap_Commercial_Capability.md (through 2026-09-10) | real channel/access/salesforce language waits for the p2 enum | channel branch → unsure; specimens append-only |
| Settled stays settled | Viatris (test) | operator relabels never re-enter any pool | `_settled_keys` in triage + clusters + test |
| The judging surface | — | the human never receives bulk: clusters (one decision each) + residual<=10 + audit<=10, caps in code; triage prints only the pointer | `triage_clusters` caps, pointer contract test |
| Three-zero-override delegation | this session's rounds | when three consecutive rounds produce zero overrides on a class, propose delegating that class | process rule for the assistant |

Standing-ruling auto-apply (`triage-complete`): every validator suffix maps to a
ruling above (STANDING_RULINGS); auto-applied verdicts are reviewer=
"operator-pattern" with `standing:<citation>` in the note. Residual = no
precedent = human, always.

## 2. Process rulings of record (BINDING; do not relitigate)

1. **Access mode: staged files, permanently.** Operator's machine is the sole
   source of truth; version pinning via pasted HEAD per block; ask in one line
   for any unattached file needed, then stop. (The public-repo window during
   this session was temporary.)
2. **Paths:** evidence and ALL generated outputs → `data\exports\`; docs →
   `docs\` (YYYYMMDD_vN_Name.md); source only in `src\biointel\`, tests only in
   `tests\unit\`; NOTHING at repo root.
3. **Delivery discipline:** every deliverable turn = one plain sentence + file
   cards + ONE block, same message; blocks name their file dependencies at top
   and hard-stop on Test-Path failure ("FILES MISSING - DO NOT PROCEED");
   download names unique per regeneration (YYYYMMDD_vN_...) — Downloads name
   collisions silently serve stale files; SHA256 hash gates on every deploy;
   commits self-gated on exact strings; no commits without pasted proof.
4. **Superseded-block kill rule:** a replacement declares the old block DEAD BY
   NAME, changes the evidence filename and an expected value; ONE live block at
   a time.
5. **Encoding:** every Python-running block sets `$env:PYTHONIOENCODING =
   "utf-8"`; evidence files arrive UTF-16 — convert before grepping.
6. **Vocabulary hygiene:** any keyword vocabulary gets a dictionary sweep before
   delivery; single-word terms are boundary-anchored by construction (`_hit`).
   Extraction-side (`_CAT_MAP`) anchoring is a MATCH-CHANGING edit banked for
   p2 with the stem-compound oracle test as its frozen-behavior baseline.
7. **Expected-value discipline:** test counts come from `pytest --collect-only`
   arithmetic, never mental addition (two gate failures this session were my
   wrong expected counts: 286-vs-285, 291-vs-290).
8. **API key:** environment-only, never pasted into chat (one rotation was
   required this session after a paste); cost anchor: ~500 calls ≈ 38-40 min.
9. **LLM analysis is proposer-only.** Operator holds every verdict of record;
   machine verdicts (draft-agree) are never counted in precision; pattern
   verdicts are their own bucket, never mixed with row-ruled ones.

## 3. Open queue, in order

1. **p2 (L3-a3-p2) opening bundle:** `commercial_infrastructure` enters the
   enum with the banked specimen list; negation guard + sentence-start capture
   (locked specimens: Opus Scffcdfdcf539e686, Biogen S0f15a669a2338908, plus
   S1e6a836 negation clip, S02a95e bullet debris, misquote pair
   Sa0aafb/Sde5e86 with quoted diffs); extraction-side boundary anchoring
   against the stem-compound oracle; overflow rows become a table; the feed
   remeasures fresh. Operator roadmap: docs/20260910_v1_Text_Extraction_
   Research_and_Roadmap.md (R1-R5, commit 5848d95).
2. **Attribution/successor-name evidence pile (p2):** S0dfdb3, S11c5f2,
   S2d1114, S69de99, S6fc257, Sa0e08f, Sb1c5cc, Sb945a9, Sc90440,
   Sa4d0c5/Sc9e9bd/Sd944f8, S9fadedf.
3. **From v47, untouched:** 52 deferred F-era stakes verdicts + 707 open M3
   entries (operator judges whenever); F1-era stakes retire path repair
   (line ~2703); successor-name stamping via aliases; GUI build order.
4. Harrison remains blocked pending merge/key-rotation/repo-visibility.

## 4. Session end ritual

Update PROJECT_STATUS (+1 version), write the next handoff (+1 version), commit
both with pasted proof, and remind the operator to run `manual export` —
lineage pairs and verdicts live only in the database.
