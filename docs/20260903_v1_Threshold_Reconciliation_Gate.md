# docs/20260903_v1_Threshold_Reconciliation_Gate.md

# Threshold reconciliation gate — measure the buyer/target boundary, stop asserting it

Bioindustry Intelligence Platform · 2026-09-03 · scoped, not started. Runs
after F1 closes (it needs the database and a re-run). Cause: the constants
audit (docs/20260903_v1_Constants_Audit.md, §1, §2, §2a).

## 1. The problem, exactly
"Acquirer-side" — the line that decides whether a firm is a possible buyer or
a possible target — is defined twice in running code, with different numbers,
none of them derived from anything:

| Where | Rule | Provenance |
|---|---|---|
| `pairs.py` (`mass-exact`, implementation of record) | annualized revenue > **$2B** | UNSOURCED |
| `score.py` (`scorecard`, drives `predict`) | annualized revenue > **$10B** OR market cap > **$75B** | UNSOURCED; its docstring claimed $100B until corrected 2026-09-03 |

A third pair ($5B revenue / $50B cap) appears in `score.py`'s docstring but
belongs to a pairing engine retired at v0.81; it is not live (audit §2a).

Two staleness windows exist for the same purpose: **450 days** (`pairs.py`)
and **400 days** (`features.py`), both UNSOURCED.

All are now declared once in `schema.py` with their values unchanged, so the
disagreement is visible in one place and a change is a one-line edit.

## 2. Why the numbers matter
The acquirer-side rule sets who is excluded from the candidate pool, so it
sets pool size, so it sets `chance = k / pool` in every forward test the
project reports. `pairs.py`'s companion floor — a firm needs ≥ 8 trial
tokens to be in the pool at all — does the same and is equally UNSOURCED.
These are not cosmetic constants; they are the denominators.

## 3. What this gate does instead of choosing a number
Measure the boundary from the deal record, then set it where the data puts it.

1. **Build the size distribution.** For every deal with a resolvable acquirer
   (the ~129 the pairing protocol already uses), take the acquirer's and the
   target's annualized revenue and market cap as of the year-end before
   announcement, from the feature panel — the same as-of discipline the
   protocol uses, so nothing from after the announcement is visible.
2. **Report the overlap, not just the split.** Publish the two distributions
   and the region where they overlap (firms of a size that have been on both
   sides). A single clean line may not exist; if it doesn't, that is the
   finding, and the honest output is a graded acquirer-side score rather than
   a boolean.
3. **Derive candidate rules and pre-register the choice BEFORE seeing which
   scores best**: e.g. the revenue at which the acquirer:target likelihood
   ratio crosses 1, or a fixed percentile of the acquirer distribution. The
   rule for choosing is written down first; the number falls out of it.
4. **Same treatment for the ≥ 8 token floor**: report pool size and HR@5 at
   4 / 8 / 16 as a sensitivity, and prefer eliminating the floor if the
   results are flat across it.
5. **Staleness windows**: one declared value for both modules; the choice is
   "one fiscal year plus filing lag," which is derivable from SEC filing
   deadlines rather than asserted.

## 4. Leak discipline (binding)
Choosing a threshold because it improves HR@5 on the same deals that grade the
matcher is fitting on the test set — the class already retracted once (the
6.2× ROC result). Therefore:
1. The selection rule is pre-registered before any evaluation is run.
2. The distribution work uses only pre-announcement data.
3. The evaluation after the change is a normal pre-registered run against the
   frozen protocol, reported whether it improves or not.

## 5. Deliverables
1. A measurement report (rendered from its run record, P17) with both size
   distributions, the overlap region, the derived boundary, and the pool-size
   sensitivity for the token floor.
2. One declared acquirer-side rule in `schema.py`, read by both models, with
   the prior values and the reason for the change recorded.
3. One declared staleness window.
4. Re-run of `predict`, `pairs-full-exact` and `pairs-exact`, with the
   thirteen-fingerprint baseline **re-based** and the re-basing recorded as a
   deliberate act (the outputs change by design; this is the only kind of
   fingerprint change that is legitimate).
5. Removal of the retired engine's remnant in `score.py`
   (`toks = _condition_tokens()`, computed and never used), in the same
   change that retires the docstring's superseded text.

## 6. Exit criteria
1. The measurement report exists and its numbers are reproducible from the
   run record.
2. Both models read one declared rule; no size threshold remains typed into a
   module.
3. The pre-registration is committed before the evaluation that follows it.
4. Suite green; the re-based fingerprints recorded with the commit that
   changes them.

## 7. Explicitly out of scope
The scorecard's thirteen hand-set point weights (+25 approved drug, +20
Phase-3 lead, and the rest). P2 permits a hand scorecard; the weights are
analyst-set and now annotated as such. Deriving them is a separate question
and a separate gate, and it would need its own pre-registration for the same
reason as the thresholds.
