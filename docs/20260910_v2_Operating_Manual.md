# docs/20260910_v2_Operating_Manual.md

# Bioindustry Platform — Operating Manual (v2, unified)
Merges the review-chat manual (v1, this file's predecessor) and the
build-chat manual (20260910_v1_Project_Operating_Manual.md), superseding
both. Distilled from the full 2026-09-07..10 record: every practice,
every failure with root cause and standing guard. BINDING on all future
sessions. The WHAT (methodology, P1-P21, precedent table) lives in
20260903_v6_Design_Principles.md and the newest handoff; this manual is
the HOW. Conflicts resolve to the newer operator ruling, recorded here
as errata.

## 0. Roles and the two-chat pattern
- The OPERATOR holds every verdict, scope approval, and commit gate.
  Machines propose; the operator decides.
- The BUILDER session writes code, runs gates, produces evidence. A
  REVIEWER session cross-checks surfaces, rulings, and close-out docs
  against the precedent record — the builder never grades its own
  judgment calls. The split caught contaminated clusters, an Opus-class
  landmine, and a near-reversal of an operator ruling; use it on
  judgment-heavy gates.
- The operator's machine is the SOLE source of truth.

## 1. Sources and access — POLICY, not circumstance
- MODE OF RECORD (operator ruling, final, 2026-09-10): BOOT CLONE, THEN
  ARTIFACTS ONLY. At boot the operator opens a temporary public window;
  the session clones ONCE for its baseline tree; the operator re-privates
  the repo immediately; the session confirms the clone's HEAD against the
  operator's pasted `git log` line.
- Thereafter ZERO repo access — no fetch, no pull, no re-clone: all
  changes flow as delivered artifacts (dated names, hash gates); all
  state verification via pasted HEAD per block. The baseline clone exists
  for accuracy and fidelity of the starting tree; artifacts exist for the
  integrity of every change after it. MID-SESSION repo reads remain
  forbidden — that, not the boot clone, was the root cause on record.
- HEAD pinned per block (`git --no-pager log --oneline -1` verified
  against expectation) replaces clone freshness.
- Every landed file asserted (Test-Path / hash) before dependence.

## 2. The delivery pipeline (turn anatomy)
1. A deliverable turn contains EXACTLY: one plain sentence saying what
   the operator should do, the file cards, one PowerShell block — SAME
   message. A turn that cannot carry its files is invalid; reissue
   whole. Never reference files "from earlier."
2. Gate loop per unit of work: scope message -> operator "go" -> build
   -> container diligence on a replica of the exact inputs
   (monkeypatched seams stated as such) -> deliver -> operator runs ->
   pasted/attached proof -> commit. Never code before go; never commit
   before proof.
3. Blocks:
   - Open with `# DEPENDS ON EXACTLY N FILES: ...` (or "0 DOWNLOAD
     FILES"); first executable act is Test-Path on every dependency,
     hard-stopping with "FILES MISSING - DO NOT PROCEED" to console AND
     evidence.
   - Every command's output to ONE evidence file via `*>> $out`;
     `# expected:` with EXACT values after every command (format-only
     for discovery runs); BLOCK START/END timestamps; unique evidence
     filename per block.
   - `$env:PYTHONIOENCODING = "utf-8"` in every Python-running block
     (a model-written U+2011 crashed cp1252 printing mid-run; writes
     survived, output died).
   - Commits self-gated on `$ok` from exact evidence strings; the
     else-branch prints "GATE FAILED ... NOT committing".
   - EVERYTHING consequential sits INSIDE the gate. (v48af failure:
     precision/cluster lines outside the if/else ran after a failed
     gate and printed a misleading surface.)
4. ONE live block at a time. A superseding delivery declares the old
   block DEAD BY NAME, changes the evidence filename, AND changes at
   least one expected value so the stale block cannot pass its own
   gate. (v48m ran instead of v48n; the new code silently stayed
   undeployed.)
5. Never assert client-side state that evidence cannot verify ("the
   files are already in your Downloads") — assert it in the block.
   (v48o claimed a download that Test-Path disproved.)
6. Never hand the operator diagnostics to run or open decisions when a
   sane default exists: embed diagnostics in the block, take the
   default, state it in one line. Decision points that do reach the
   operator carry a recommendation.

## 3. Naming, nomenclature, paths
1. Download filenames: `YYYYMMDD_vN_name.ext`, vN incremented on EVERY
   regeneration, names never reused for different content. Root cause
   of the worst time sink: a bare `priorities.py` delivery collided
   with a stale same-named Download; Windows saved the fresh file as
   `priorities (1).py`; Copy-Item silently deployed the stale original;
   three deploy rounds burned before hashes isolated it.
2. Code files keep functional names at the DEPLOY path; the dated name
   is the download name only. Line 1 of every delivered code file = its
   Windows deploy path (where comments permit; else runbook only).
3. Tracked docs keep their original filename forever (the vocab-gap
   record stays 20260908_v1_... even at content v4); the download name
   carries the content version.
4. Evidence: `data\exports\YYYYMMDD_<blockid>_<purpose>_evidence.txt`,
   block ids sequential. Evidence arrives UTF-16 — convert before
   grepping.
5. PATHS: evidence and ALL generated outputs -> `data\exports\`; docs
   -> `docs\`; source -> `src\biointel\`; tests -> `tests\unit\`;
   NOTHING at repo root, ever.

## 4. Hash discipline (the delivery-integrity ladder)
1. Every delivered file's SHA256 is computed in-container and stated
   with the delivery; the block verifies the DOWNLOAD hash before
   copying and the DEPLOYED hash after, both against the stated value,
   with "if it differs, STOP and paste."
2. The ladder pinpoints any failure in one paste: Test-Path False =
   never arrived; download-hash mismatch = stale/wrong download;
   deployed-hash mismatch after good download = copy failure. Different
   fixes; never guess without the ladder.
3. Stale surfaces are the cousin hazard: regenerated cluster/worksheet
   CSVs — `Remove-Item data\exports\cluster_*.csv` before every
   regeneration; never batch-apply a prior round's CSV.

## 5. Long runs, limits, and cost — DISCLOSURE AND CONSENT (operator-ordered)
Before ANY run projected past ~2 minutes, the delivery states duration
and what silence means; before ANY run past ~30 minutes or ~500 API
calls (or ~$5), the assistant MUST present and ASK:
1. Call count and rows (e.g., "2,400 rows x 2 models = 4,800 calls").
2. Cost estimate WITH its anchor (ledger anchors: ~700 Haiku rows =
   $3-4; Sonnet materially costlier; the Console usage page is the live
   source — recommend checking before multi-thousand-call runs).
3. Runtime from MEASURED pace, never vibes (measured: 500 calls =
   38-40 min = ~13 rows/min; full-shelf offline sweeps = ~70 min on the
   operator's machine). State: window stays open, key set in that
   window, safe to interrupt (proposals cached, resumable).
4. Rate limits throttle, never corrupt; API failures degrade to the
   pool and are counted.
5. TOKEN CAPS AND EVERY INHERITED LIMIT are disclosed in the scope, not
   discovered in wreckage. Origin failure: M4's 200-token reply cap was
   silently reused for F2's longer replies, truncating stored reasons
   to "The s" and blanking 20 verdicts — nobody had told the operator
   the cap existed. Standing: judge/triage calls run max_tokens=1000
   (f216973); ANY change to per-call limits is stated explicitly.
6. LONG LOOPS PRINT A GAUGE (done/total or POOL-REMAINING per cycle);
   the loop-completion arithmetic (corpus / cap = rounds) is surfaced
   at loop START — six manual 500-call tranches of empty ceremony
   happened because it wasn't. A successful run the operator cannot
   see into is still a defect (the 8-hour silent collector).
7. API keys: environment-only, per-window, never in chat or evidence
   (blocks test IsNullOrEmpty, print "key present" only). A key in
   chat is compromised by definition — rotate immediately (happened
   once).

## 6. Chat/context limits (the other token budget)
1. Long sessions consume the assistant's context; older tool outputs
   get dropped. Normal and safe ONLY because committed docs — never
   scrollback — are the memory of record. Verbatim material that
   matters (specimens, diffs, rulings) goes into committed docs
   immediately.
2. Evidence is read by extraction (counters, the rows needed), never
   wholesale. The close-out handoff is written while the ledger is
   still reconstructible.
3. On very long sessions the assistant proactively flags: "context is
   deep; commit anything uncommitted now; a fresh session booting from
   the handoff will be sharper." The operator decides.
4. Attachment hygiene: attach evidence only after BLOCK END exists; a
   file without it is a mid-write copy (two false alarms). The
   assistant verifies completeness (BLOCK END + counters) before acting
   and names a wrong/stale attachment plainly (happened twice).

## 7. Verification rules
1. Expected test counts from `pytest --collect-only -q` arithmetic,
   never mental addition (four wrong expectations across both chats;
   two failed gates — the gates refusing was correct, the expectations
   were the defect).
2. Container runs are ADVISORY: documented fixture/network artifacts
   make some tests fail or hang in-container; the operator's pasted
   suite/ruff evidence is the proof of record. Known-good container
   batches still run before every delivery; in-container ruff always.
3. Container edits land via str_replace or whole-span rewrites and are
   verified BY A SEPARATE PROCESS reading the disk before any success
   claim (heredoc edits twice printed success on asserts the UNEDITED
   file satisfied).
4. Fix the CLASS, not the instance. The substring saga: `viral` inside
   "lentiviral" was instance-patched; `rna` inside "alternatives" then
   shipped and mis-clustered a row. Standing: every keyword vocabulary
   is dictionary-swept before delivery; single-word terms are
   boundary-anchored IN THE MATCHER; traps locked as regression tests.
5. Rule versions FREEZE before measurement; extraction-changing fixes
   belong to the next version with fresh measurement (extraction-side
   anchoring was correctly banked for p2 with an oracle test).
6. Divergences are reported in one line with cause, never smoothed:
   collision-guard refusals, correct-then-wrong verdict histories, the
   2,863/2,873 and 9-vs-13 figures — all named, one errata-committed.
7. When the operator disputes a session-verified claim, re-verify
   against evidence; neither the prior verification nor the correction
   is automatically true (both directions bit; both held when applied).
8. Every bug fix is a TRIPLE: code + locking test (verbatim specimen
   where applicable) + written rule here. Missing a leg = not fixed.

## 8. The judging machinery — practices of record
1. Proposer-only, always. Provenance classes never mix: operator /
   operator-pattern / draft-agree / draft-restore. Precision counts
   operator verdicts only; machine verdicts reported, never counted
   (early survivor-artifact 1.000s and a circular 85/85 self-agreement
   were rebuilt out).
2. THE OPERATOR NEVER JUDGES BULK. Surface = clusters (one decision
   each, count + exactly 3 VERBATIM examples), residual <=10 verbatim,
   audit <=10; caps in code with an explicit carried count; `triage`
   prints only a pointer to `triage-clusters`. Verbatim always;
   paraphrase never (paraphrased tie-break sheets made judgment
   impossible once).
3. Cluster membership validated against the SENTENCE by deterministic
   checks, never the dissent reason (reason-keyed clustering
   contaminated three clusters and nearly reversed the operator's
   Viatris ruling).
4. SETTLED STAYS SETTLED: operator-ruled rows (including relabel
   re-keys via _settled_keys) are excluded from every pool, in code.
5. REPAIR-NOT-DELETE: wrong-with-correction repairs in place with
   provenance; deletion only for non-priorities; verdicts append-only,
   latest-by-reviewed_at wins; the verdict-aware writer suppresses
   judged-wrong keys forever and applies relabels at write time — ten
   wrongly-deleted rows were restored under recorded reasons.
6. Standing rulings auto-apply ONLY after explicit operator delegation,
   always with `standing:<citation>` provenance; residual = no
   precedent = human, without exception.
7. Every precedent is enforced TWICE: a validator branch AND a verbatim
   specimen test (synthetic branch tests stated as such when full text
   is unavailable). The precedent table lives in the newest handoff.
8. TOLLGATES exist for verdicts, commits, and destructive actions —
   never for repetitive read-only/idempotent passes; those loop to
   completion in one block with the gauge printing. THE OPERATOR IS
   NEVER THE SCHEDULER.
9. THREE-ZERO-OVERRIDE DELEGATION: when three consecutive rounds
   produce zero overrides on a decision class, the assistant PROPOSES
   delegating that class with provenance. Ceremony the evidence has
   emptied is a cost, not a courtesy. Forecasts require gauges: never
   "one more round" without a printed number.

## 9. Documents and records
- PROJECT_STATUS versions per session-block; handoff per session; both
  committed with pasted proof; handoffs encode POLICIES plus the
  precedent table.
- Operator findings become DECISION RECORDS (own dated doc, committed;
  the commercial_infrastructure record is the template: finding,
  ruling, timing constraint, specimen list growing by append).
- Superseded rulings recorded as superseded, never deleted.
- Session close ritual: docs commit -> `manual export` (verdicts live
  only in the database) -> clean `git status --porcelain`.
- Session boot ritual: paste newest handoff; environment proof (HEAD,
  suite count, ruff 3) pasted before any design or code; self-check
  with exact numbers.

## 10. Communication rules (operator temperament, binding)
1. Every task-bearing message opens with ONE plain sentence saying what
   to do; detail after; answer the question asked, then stop.
2. PLAIN ENGLISH on first use of any technical concept ("cap cost
   what?" cost a full turn); when told "speak plainly," strip jargon
   and shorten.
3. Settled stays settled; no relitigating; no invented problems. One
   real caveat beats three hypothetical ones — but arithmetic that
   predicts grind (rounds x cap x minutes) IS decision-changing and
   surfaces EARLY.
4. When the operator is frustrated: fix the thing. Own errors in one
   line with the mechanism, then move. No narration, no long apology,
   no defending a session he's criticizing.
5. Never hand homework; embed diagnostics; recommend on every decision
   point (see §2.6).

## 11. Failure catalog of record (both chats, unified)
| # | Failure | Root cause | Guard |
|---|---|---|---|
| 1 | Token-cap truncation ("The s", 20 blank verdicts) | inherited 200-token cap, undisclosed | §5.5 disclosure; max_tokens=1000; ask on change |
| 2 | 8-hour collector ran silent | no progress print | §5.6 gauges; duration disclosure |
| 3 | Phantom container edits (2x success on unedited file) | in-process asserts about persistence | §7.3 separate-process disk verification |
| 4 | 3 failed deploys on stale Downloads | bare filenames collided; Copy-Item silent | §3.1 dated names; §4 hash ladder |
| 5 | Repo-access chaos | handoff encoded circumstance not policy | §1 policy-only rules |
| 6 | Bulk surfaces (120 / 87 / 206 raw rows) | "disagreements only" read literally | §8.2 clusters + code caps + pointer |
| 7 | Paraphrased tie-break sheet | summarizing for brevity | §8.2 verbatim always |
| 8 | Mislabeled-but-real rows deleted | wrong precedent template copied | §8.5 repair-not-delete; verdict-aware write; restores |
| 9 | rna-in-"alternatives" shipped after viral-in-"lentiviral" was instance-patched | substring matching; class not killed on first instance | §7.4 boundary anchors + dictionary sweep + trap tests |
| 10 | Operator ran superseded v48m | two live blocks in scrollback | §2.4 dead-by-name + changed gates |
| 11 | Evidence at repo root; _mirror at root | no path law | §3.5 |
| 12 | cp1252 print crash mid-run | console encoding | §2.3 PYTHONIOENCODING |
| 13 | Operator hand-fired six+ tranches | tollgates on idempotent passes; loop arithmetic never surfaced | §8.8 tollgate doctrine; §5.6 arithmetic at loop start |
| 14 | Four wrong expected test counts; two failed gates | mental arithmetic | §7.1 collect-only counts |
| 15 | Survivor-artifact 1.000s; circular 85/85 agreement | retired rows untracked; drafts counted | §8.1 operator-only precision, buckets |
| 16 | Blocks referencing unattached files | files and block in separate turns | §2.1 same-turn law; §2.3 Test-Path |
| 17 | No pool gauge for days | never built | §5.6 POOL-REMAINING |
| 18 | Diagnostics/decisions handed to operator | reflex to ask | §2.6 defaults + embedded diagnostics |
| 19 | API key in chat text | habit | §5.7 env-only; immediate rotation |
| 20 | Spend shape undisclosed | cap sized for a 120-row world, never re-surfaced at 40x | §5.1-2 cost disclosure + ask |
| 21 | Uniform confirm rounds ground on | no delegation trigger | §8.9 three-zero-override |
| 22 | Post-gate lines ran after GATE FAILED (v48af) | commands outside if/else | §2.3 everything inside the gate |
| 23 | False "already downloaded" claim (v48o) | asserting client state | §2.5 assert in-block only |
| 24 | Mid-write / wrong evidence attachments (x3) | attach before BLOCK END; similar names | §6.4 completeness check |
| 25 | Stale cluster CSVs nearly batch-applied | old surfaces left behind | §4.3 Remove-Item pre-regeneration |
| 26 | Jargon confusion ("cap cost what?") | undefined terms | §10.2 plain English on first use |

## 12. What worked and must not regress
Self-gated commits on exact evidence strings; pasted-proof-before-
commit; scope->go gates; container replica diligence with stated seams;
the hash ladder; dated versioned filenames; capture-first rules, frozen
versions, specimens as tests; the precedent table enforced twice;
provenance on every verdict and precision that never mixes machine,
pattern, and row buckets; append-only verdicts and repair-not-delete;
resumable cached proposals; the POOL-REMAINING gauge; decision records;
honest one-line divergence reporting and errata commits for even one
wrong number; the reviewer/builder split. These carried a 4,602-row
corpus from 120 rows of homework to fully judged in two days with an
auditable trail at every step.

## 13. Meta-rule
A mistake is closed only when its triple exists (code + test + written
rule) AND its catalog entry above names it. Sessions extend this manual
by errata/append commits, never silent divergence; a new failure class
gets its catalog entry in the same gate that fixes it.
