# docs/20260911_v49_Session_Handoff.md — paste this as the first message of the new chat

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`,
branch `jason/refactor`, HEAD = the v1.28 docs commit following 68ecbc9 (verify
with the operator's pasted `git --no-pager log --oneline -1`). Windows, root
`C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`, Python 3.13, single
DuckDB store at `data\biointel.duckdb`. Suite of record: **302 passed**, ruff
exactly 3 pre-existing findings (improve.py E731, score.py F841, study.py F841).
Ruleset of record: **L3-a3-p2** (frozen 2026-09-10, measured 2026-09-11).
Schema 0.21.

**FIRST ACTIONS, in order:** (1) confirm this handoff read in full; (2) operator
pastes HEAD + `pytest -q tests/unit` (302) + `ruff check src tests` (3); (3) read
docs/PROJECT_STATUS.md v1.28, docs/20260910_v1_Text_Extraction_Research_and_
Roadmap.md (5848d95), docs/20260910_v2_Operating_Manual.md + Addendum A
(16f84c0) + its errata 1-2 (68ecbc9) + the S5 cost-ledger errata; (4) report the
self-check with exact numbers BEFORE any design or code.

## 0. STATE: p2 COMPLETE END TO END (2026-09-11)

Table of record 4,742 rows written at p2; commercial_infrastructure first yield
119; pre-pass settled 4,331 free (27 standing clusters); sweep 758 calls, 0
failures, 297 agreement-settled; 82 surfaced; operator verdicts 10 + 67 (batch)
+ 5 free look-alikes; amendment-1 EXIT-CHECK PASS (all 60 carry-forward p1-wrong
keys hold p2 verdicts; pool empty). Measurement: 10k_strategy 12/13 = 0.923
(wilson 0.667-0.986); PATTERN-RULED 2,185/2,151; ASSIST-AGREEMENT 14/77 = 0.182
(disagreement-selected, NOT comparable to p1's 0.532); 297 drafts uncounted.
Full ledger and errata (2,207-vs-2,221 overflow) in PROJECT_STATUS v1.28.

## 1. THE PRECEDENT TABLE (rulings of record; specimen = verbatim test or key)

Rows 1-19 of the v48 table carry forward UNCHANGED except where marked; read
docs/20260910_v48_Session_Handoff.md §1 for their full text. Deltas and
additions of 2026-09-10/11:

| Ruling | Specimen(s) | Operator rationale (one line) | Enforced at |
|---|---|---|---|
| commercial_infrastructure LANDED (supersedes the HOLD row) | banked list in the vocabulary-gap record; Brazil/Mylan S124cac + batch S3402b7/S75578f/S9332133/Sa5221e | the ninth category exists; channel payload under it is correct, under any other stamp it relabels | _CAT_MAP first entry; commercial-correct / commercial-relabel branches + verbatim tests (7f4222d) |
| Sentence-start capture | Opus Scffcdfdcf539e686, Biogen S0f15a669a2338908 (verbatim from p2c recovery) | captures begin at the true sentence start, never the rule anchor | _capture_sentence + locked tests (941e79a) |
| Negation guard | Opus "nor do we plan to acquire" (verbatim); S1e6a836 (synthetic, stated as such) | a negated declaration is never a priority; refuse at extraction | _NEGATION_RX + tests (941e79a) |
| Bullet debris refused structurally | S02a95e (verbatim) | captures cannot span bullet markers | \u2022-excluding char classes (941e79a) |
| Dictionary traps closed | alderman/bewilderment (derm), vindication (indication) | anchor the two banked traps; oracle compounds keep firing | _CAT_MAP anchors + trap test (99a756e) |
| right-of-first-negotiation | Knight S0cf266 (verbatim) | ROFN/ROFR is deal history, not a priority | validator branch + STANDING_RULINGS (c4e432a) |
| license-full-rights-to | Achaogen S0e5e5a (verbatim) | licensing own rights OUT is not pipeline_gap | validator branch (c4e432a) |
| granted-exclusive-license | Knight text (verbatim) | granted-exclusive-license is out-licensing history | validator branch (c4e432a) |
| provide-technology-to | AGTC S1101127 (verbatim) | providing own technology to another party is out-licensing | validator branch (c4e432a) |
| historical-relationship-statement | Prime/Beam S1ad2856 (verbatim) | a dated historical relationship statement is not a stated priority | validator branch (c4e432a) |
| Generic capability mission | S05b9c (S0e8c87 family) | capability language naming no technology is not platform | residual precedent (batch 2026-09-11) |
| Attribution rulings reapplied at p2 | S2d1114 (AgeX-on-Serina), S454c8c (AVROBIO-on-Tectonic), Sb1c5cc/Sb885899/Sb945a9 (Zeltiq-on-Allergan) | proven company mismatch defeats any content reading | batch verdicts; successor-alias work still queued |
| Batch tail families | IT/ops, historical/merger/formation, regulatory milestone, SPAC, risk-factor, generic/CEO/veterinary/debris | precedent families applied wholesale at corpus end | batch note (p2n evidence) |
| False-misquote class RESOLVED | Sa0aafbb/Sde5e86 | extracted text was genuine; boilerplate variants + sent[:80] excerpt localization misled the judge | _locate_sentence full-sentence anchor (0b0f619) |
| Corpus-end tail collapse | the 67-row worksheet (p2l) | at a singleton-heavy tail, waive the 10-cap once, print the full surface, rule as one batch | precedent (also ended p1) |
| Batch refuse-wholesale | p2n script | batch verdicts apply only when pool count and every key prefix match uniquely; otherwise nothing records | 20260911_v1_p2_batch_rulings.py pattern |

## 2. Process rulings of record (BINDING; do not relitigate)

Rulings 1-9 of v48 §2 carry forward unchanged (boot-clone access mode; paths;
delivery discipline; superseded-block kill rule; PYTHONIOENCODING + UTF-16
evidence; vocabulary hygiene; collect-only expected counts; environment-only
API key; proposer-only LLM). Additions of 2026-09-10/11:

10. **Addendum A + errata 1-2 are BINDING both roles** (machine register;
    fault-first cause assignment; no self-grading; numbered failure
    accounting; fix-forward with a codified fix in the same message).
11. **ASSIST_ENABLED is process-scoped:** the repo default stays False; an
    approved sweep flips it inside its own block's python process only
    (p2i failure of record: a sweep block that forgets this makes zero calls).
12. **Long scripts ship as files:** anything beyond ~40 lines never pastes
    into PowerShell — PSReadLine mangles long pastes (p2m failure of record);
    deliver a hash-gated .py download run by a short block.
13. **Progress reads come only from code-printed counters** (POOL-REMAINING,
    rows_written, gauge lines); never ad-hoc console arithmetic with an
    assumed denominator (the 106.8% incident: JUDGED lines counted against
    a docs-count grabbed by a loose regex).
14. **Proposals are version-scoped:** review_proposals carries rule_version
    (optional column); version-blank rows are p1-era and excluded from every
    cache lookup and judging surface; proposal ids hash prompt AND rule
    version (_proposal_pid).
15. **Cost anchors are measured, in the S5 ledger errata:** Sonnet ~$5.24/1k
    calls, Haiku ~$1.51/1k, blended ~$3.37/1k at this workload (Console
    daily rows Sep 9-10); replace the extrapolated Sep-11 row when the
    Console populates.
16. **Version bumps orphan by design:** RULE_VERSION_F2 bumps empty the
    judged/settled filters; carry-forward runs through triage with standing
    rulings auto-applying, and the exit criterion is zero prior-wrong keys
    lacking a current-version verdict (amendment 1, proven at p2).

## 3. Open queue, in order

1. **R2 (roadmap 5848d95):** section-scan + LLM inference with verbatim span
   citations, deterministic validators, existing triage surface; own scope →
   go → build; acceptance = blind head-to-head (~120 docs, ~240-360 calls,
   ~$3-5) against the frozen p2 baseline; full corpus only after its own §5
   ASK (~14-21k calls, ~$70-150 Haiku-anchored, resumable).
2. **Console Sep-11 row:** when populated, replace the extrapolated $2.56
   sweep figure in the S5 ledger errata with the measured number.
3. **From v47/v48, untouched:** F1-era stakes retire-path repair BEFORE the
   52 deferred stakes verdicts; 707 open M3 entries; successor-name stamping
   via aliases; GUI build order.
4. Harrison remains blocked pending merge/key-rotation/repo-visibility.

## 4. Session end ritual

Update PROJECT_STATUS (+1 version), write the next handoff (+1 version), commit
both with pasted proof, and remind the operator to run `manual export` —
lineage pairs and verdicts live only in the database.
