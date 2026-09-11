# docs/20260911_v51_Session_Handoff.md — paste this as the first message of the new chat
# (supersedes v49/v50 same day: boot protocol inline, complete amendment list, boot-proof standard)

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`,
branch `jason/refactor`, HEAD = the v1.28 docs commit following 68ecbc9 (verify
with the operator's pasted `git --no-pager log --oneline -1`). Windows, root
`C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`, Python 3.13, single
DuckDB store at `data\biointel.duckdb`. Suite of record: **302 passed**, ruff
exactly 3 pre-existing findings (improve.py E731, score.py F841, study.py F841).
Ruleset of record: **L3-a3-p2** (frozen 2026-09-10, measured 2026-09-11).
Schema 0.21.

## BOOT PROTOCOL (operator ruling 2026-09-10, final; execute in this order, before any design or code)

1. **Clone once, then artifacts only.** The operator opens a temporary public
   window on the repo. The session clones ONCE (`git clone`, checkout
   `jason/refactor`) as its baseline tree and reports HEAD
   (`git log --oneline -1`); the operator confirms it against his own line and
   RE-PRIVATES the repo immediately. From that confirmation forward: ZERO repo
   access — no fetch, no pull, no re-clone. Every change ships as downloadable
   artifacts (unique dated names, SHA256 hash gates, deploy-path line 1) and
   all state verification is the operator's pasted `git log` HEAD line per
   block. Mid-session repo reads are forbidden; on a deployed-hash mismatch
   the remedy is the operator attaching the current file, never a repo reopen.
2. **Read IN FULL from the clone — the COMPLETE amendment set:**
   docs/20260910_v2_Operating_Manual.md (BINDING) PLUS its access-mode
   errata (commit aa992c9 — amends manual §1: the boot clone in step 1 is
   the ruled exception to §1's no-clone text; without this errata the
   unamended §1 contradicts this protocol); Addendum A (16f84c0) + Addendum
   A errata 1 (b2371ab) + errata 2 (68ecbc9) + errata 3 (A5.8,
   fitness-for-use audits); the S5 cost-ledger errata; this handoff;
   docs/PROJECT_STATUS.md v1.28;
   docs/20260910_v1_Text_Extraction_Research_and_Roadmap.md (5848d95).
   Flag any doc divergence once instead of smoothing it.
3. **Boot-proof standard, MANDATORY before any scope earns a "go":** read in full every file
   the scoped work will modify, then report (a) the module inventory with line
   counts and each file's SHA256 from the clone, (b) `pytest --collect-only -q`
   total confirming 302, (c) per piece, exactly which functions/constants will
   change. Container test runs are advisory; the operator's pasted suite/ruff
   evidence is the proof of record (four test_stakes fixture tests fail
   in-container on the unedited baseline — documented artifact).
4. **Self-check with exact numbers** (HEAD, the v1.28 ledger, the manual rules
   bound by, the first task's name) BEFORE any design or code; then the scope
   message for the first task and NO code until the operator's "go".
5. **HEAD-guard behavior:** every block pins the expected HEAD and stops on
   mismatch. An operator docs commit moving HEAD mid-gate is routine: reissue
   the same block with the new expected HEAD and re-carry the unchanged file
   cards (files and hashes identical; new evidence filename; old block DEAD BY
   NAME).
6. Operator pastes HEAD + `pytest -q tests/unit` (302 passed) +
   `ruff check src tests` (Found 3 errors) as the environment proof of record.
7. All working conventions — naming, git, paths, delivery turn anatomy, hash
   gates, long-run disclosure — are in Operating Manual v2 and its errata;
   the reading list in step 2 is the complete amendment set.

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
