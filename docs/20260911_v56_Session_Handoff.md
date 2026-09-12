# docs/20260911_v56_Session_Handoff.md — paste this as the first message of the new chat
# (supersedes v51-v55; v55 is unchanged and still correct, this adds S2.8 and states HEAD is a4b57ab as of this file's writing)

**Project:** Bioindustry Intelligence Platform. Repo `harrisonbanks/bioproject`,
branch `jason/refactor`. HEAD is whatever the operator's pasted
`git --no-pager log --oneline -1` prints at boot, confirmed against origin
(Step 0) — never trust a hardcoded hash in any handoff over that paste,
including this one. As of this handoff's own commit, HEAD was **a4b57ab**
(docs: Manual S2.8 errata); treat that as a floor, not the answer.

Windows, root `C:\Users\JB\Documents\dev\bioindustry`, venv `.venv`,
Python 3.13, single DuckDB store at `data\biointel.duckdb`. Suite of
record: **346 passed**, ruff exactly 3 pre-existing findings (improve.py
E731, score.py F841, study.py F841). Ruleset of record: **L3-a3-p2**
(frozen 2026-09-10). Schema 0.22 (unchanged since gate R2-1; R2v2 added no
schema version).

## BOOT PROTOCOL (unchanged from v51-v55 except the reading list)

0. **Step 0 (08bc8ba):** operator confirms origin HEAD equals the pasted
   `git log` HEAD before opening the window; a differing clone is
   remedied by attachments, never a re-clone.
1. Clone once, then artifacts only (v51 step 1, unchanged).
2. Read IN FULL from the clone, in this order: docs/20260910_v2_Operating_Manual.md
   plus aa992c9 (access mode); Addendum A (16f84c0) + errata 1 (b2371ab) +
   2 (68ecbc9) + 3 (A5.8); the S5 cost-ledger errata (pointer fixed at
   08bc8ba); Manual S3.6 docs-only commit gate (f929dea); the Step 0 push
   errata (08bc8ba); the block-discipline errata E1-E6 (ca63d90);
   the S2.7 no-directory-delete errata (6f74f86);
   the S2.8 cross-check-before-shipping errata (a4b57ab);
   docs/20260911_v1_R2_Trial_Record.md (83cac01, R2 v1 close);
   docs/20260911_v1_R2v2_Stance_First_Extraction_Decision_Record.md
   (b6b19ba, R2v2 scope basis);
   docs/20260911_v1_R2_Negative_Result_and_R3_Basis.md (R2v2 close, the
   R3 scope basis); this handoff; docs/PROJECT_STATUS.md v1.30; the
   roadmap (5848d95), noting the trial record and the negative-result
   record both supersede its R2 call estimates.
3. Boot-proof standard (v51 step 3): module inventory with line counts
   and full 64-character SHA256 per file, `pytest --collect-only -q`
   confirming 346, per-piece function list; container runs advisory; four
   test_stakes fixture tests fail in-container on the unedited baseline
   (documented).
4. Self-check with exact numbers, then the scope message; NO code until
   go.
5. HEAD-guard, evidence-file, and dead-by-name rules unchanged (rulings
   19-20, restated below).
6. Operator pastes HEAD + `pytest -q tests\unit` (346 passed) + `ruff
   check src tests` (Found 3 errors).
7. Block discipline (E1-E6, ca63d90): every block is dry-run on a
   replica carrying prior blocks' side effects (live data folder,
   untracked files); no inline Python in PowerShell (script files under
   `data\scripts\`, gitignored); code writing paths derives them from
   config.DATA/config.EXPORTS with a redirect-isolation test; blocks
   print HEAD, tracked changes, untracked files, and live snapshot count
   before gating and as the stop message; clean-tree gates count tracked
   changes only; the operator attaches the evidence file, never a
   console paste, when a block stops.
8. **No directory deletes (S2.8, 6f74f86):** a block never issues
   Remove-Item against a directory. Deletions target individually named
   files only, listed in the block's evidence, with the operator's
   explicit go on that named list before the delete runs.
9. **Mandatory cross-check before shipping (S2.8, a4b57ab):** before
   presenting any new file, download, or block name to the operator, the
   assistant checks it against every name already used this session —
   as a prior download, a prior block letter, or a prior commit. A
   collision means the next unused name/letter is used instead, before
   anything else about the artifact is finalized. Any figure, hash, or
   HEAD reference in the new artifact is recomputed against current
   state, never copied from an earlier value in the same session.

## 0. STATE: R2v2 CLOSED AS A MEASURED NEGATIVE RESULT (2026-09-11)

Four free judging rounds on the one paid trial (291 calls, ~$0.44 Haiku):
held-out precision 10/59=0.169, 23/59=0.390, 30/60=0.500 (fit-set), then
21/43=0.488 held-out (deciding, Wilson 0.346-0.632, below p2's 0.667
floor). Recall regression 14 of 33 p2 rows on the 76 held-out documents.
Root cause: the remaining errors are declared-intent sentences about
routine operations, indistinguishable from true priorities by form — a
judgment boundary, not a pattern. stated_priorities_r2 (1,871 rows)
retained under extractor-version provenance, excluded from the matcher.
Full record: docs/20260911_v1_R2_Negative_Result_and_R3_Basis.md.

## 1. Precedent table

Rows of v48 §1 and v51 §1 carry forward UNCHANGED. Additions:

| Ruling | Specimen(s) | Operator rationale (one line) | Enforced at |
|---|---|---|---|
| Description/operations is not declared strategy | the ~110 wrong R2v2 rows across four rounds (fixtures r2v2_verdicts_20260911.csv, _round3_, _round4_) | grammatically declared intent about routine operations (financing, expenses, compliance, hedges, regulatory path) is not a stated priority; the boundary needs judgment, not a pattern | R2_Negative_Result record; binding on any future extraction redesign |
| r2 verdicts never touch the baseline | r2_judge / judge-batch --r2 | verdicts on R-keys go to candidate_reviews only; neither priorities table is written by judging | priorities.r2_judge + test (a3044dc) |
| Tagged judging rounds isolate a measurement | judge-batch --r2 --tag / r2-compare --tag | a compare with a tag counts only that round's verdicts, so a later free-branch round cannot be measured against an earlier round's judgments | priorities.py tag param + test (30357e6) |

## 2. Process rulings of record (BINDING; do not relitigate)

Rulings 1-23 of v51 §2 carry forward unchanged. Additions of 2026-09-11:

24. **Stopping rules are set before the measurement, not after.** The
    R2v2 four-round stop (Wilson lower bound below p2's floor closes the
    line) was ruled before round 4 ran; the result was accepted without
    relitigating the threshold.
25. **A branch round's fit-set validation never substitutes for the held-
    out measurement.** Every branch round pinned corrects-kept and
    wrongs-refused on its own fixture before the next worksheet was drawn
    from the stored survivors; the held-out number always came from rows
    the branches were not tuned on.
26. **A negative result is closed with a decision record, not silently
    abandoned.** stated_priorities_r2 stays in the schema (audit trail)
    but is excluded from any matcher; the record states which modules
    were checked to confirm exclusion.
27. **The verdict ledger is the R3 basis, counted exactly, not estimated.**
    10,040 review rows, 5,673 distinct keys, 4,951 current-ruleset
    verdicts (240 R + 4,711 S) — measured via
    data\scripts\20260911_v1_verdict_ledger_count.py, not approximated.
28. **No block deletes a directory (Manual S2.7).** Deletions target
    individually named files only, listed in the block's evidence with
    the operator's explicit go on that named list. Failure of record:
    block v51u issued Remove-Item on the scripts\ folder immediately
    after relocating one known file, without listing its other 18
    tracked contents; the operator's declined confirmation prompt, not
    this rule, is what prevented the deletion.
29. **Every new named artifact is cross-checked against every name
    already used this session before it ships (Manual S2.8).** Four
    incidents in one session shared this single missing step: v51d
    (download name reused, stale file silently hashed), v51g (two blocks
    named identically, wrong one ran, capped a paid trial early), the
    v54 handoff (same filename issued twice in-session with different
    content), and the v51z block letter (reused across two attempts).
    None required new information to catch — each was checkable against
    artifacts already produced earlier in the same conversation. The
    check is: does this name collide with anything already used, and is
    every hash/figure/HEAD reference in this artifact recomputed against
    current state rather than copied forward. Skipping this check, not
    lacking information, was the failure every time.
30. **Block-letter sequences exhaust and roll over cleanly.** v51a
    through v51z used all 26 letters in one session; the next block
    became v52a, not a reused or awkwardly-suffixed v51 name.

## 3. Open queue, in order

1. **R3 (decision record §6):** a classifier trained on the verdict
   ledger (4,951 current-ruleset labeled sentences, or the full 10,040
   across rule versions if that measures better). Zero new API calls to
   build. Scope -> review -> go, same discipline as R2v2. Its own
   acceptance test needed before any claim of improvement over p2.
2. **Gold set** of 5-10 fully annotated Item 1 sections: neither p2 nor
   R2v2 recall has been measured against ground truth, only against each
   other. Queued, not started.
3. Console Sep-11 row: replace the extrapolated sweep and trial figures.
4. From v47/v48, untouched: F1-era stakes retire-path repair BEFORE the
   52 deferred stakes verdicts; 707 open M3 entries; successor-name
   stamping via aliases; GUI build order.
5. Harrison remains blocked pending merge/key-rotation/repo-visibility.
6. `scripts\` folder (18 git-tracked files, unused, from the 2026-08-29
   src-layout migration): queued for review per
   docs/20260911_v1_Manual_Errata_S2_And_Scripts_Note.md. Options on
   record: archive (git mv to docs/archive/), delete with the file list
   in evidence, or confirm continued use.

## 4. Session end ritual

Update PROJECT_STATUS (+1 version), write the next handoff (+1 version,
CHECKED against every handoff filename already issued per ruling 29),
commit both under S3.6 with push, and remind the operator to run `manual
export` (the real command is `python -m biointel manual export` — a
top-level `manual` subcommand, not a `priorities` subcommand; verified
2026-09-11 after an earlier session incorrectly guessed the syntax):
lineage pairs and verdicts (including all R-key and S-key reviews) live
only in the database.
