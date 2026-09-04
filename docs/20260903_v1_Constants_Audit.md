# docs/20260903_v1_Constants_Audit.md  (v2: +§1a re-derivation)

# Numeric constants audit — every parameter in the codebase, its effect, its provenance

Bioindustry Intelligence Platform · 2026-09-03 · read-only audit of the tree
at commit eab75eb (mirror). Ordered by consequence: whether the number sits
inside a model whose results are of record, and whether it changes what
those results say.

Provenance classes used below:
- **sourced** — cites a paper, a regulator's limit, or a measurement on this project's own data.
- **conventional** — a widely used default in the relevant field, not derived here.
- **structural** — follows arithmetically from another declared choice.
- **protocol** — a pre-registered evaluation setting recorded in the run ledger.
- **UNSOURCED** — chosen by whoever wrote the line, no stated basis.
- **operational** — a rate limit, page cap, or buffer size; affects cost, not results.

The rule adopted 2026-09-03 (PROJECT_STATUS 1.11): no numeric constant enters
a rule without a source line; absent one, the parameter is eliminated or
reported as a sensitivity. Everything marked UNSOURCED below is in breach of
that rule and is listed with a recommended disposition.

---

## 1. `pairs.py` — `mass-exact`, the acquirer-pairing implementation OF RECORD

The HR@5 0.335 benchmark that every rival is judged against comes from this
file. Constants here shape the candidate pool and therefore every chance
baseline the project reports.

| Line | Value | What it does | Provenance | Disposition |
|---|---|---|---|---|
| 75 | `>= 8` tokens | A firm needs at least 8 trial-vocabulary tokens as of the cutoff to be in the candidate pool at all | **UNSOURCED** | Highest priority. Defines pool size, hence `chance = k/pool` in every forward test. Report pool size and HR@5 at 4/8/16 as a sensitivity, or eliminate by admitting any firm with ≥1 trial |
| 72 | `len(w) > 3` | Tokens of 3 or fewer characters are dropped | **UNSOURCED** (common stop-word heuristic) | Low effect; document as conventional |
| 92 | `> 2e9` revenue | Annualized revenue above $2B classifies a firm as acquirer-side (excluded from the target pool) | **UNSOURCED** — a rule of record in prose, no derivation | Sensitivity at $1B/$2B/$5B; the scorecard uses different cut-offs (see §2), so the two models disagree about who is a buyer |
| 93 | `<= 450 days` | Revenue lookup ignores feature-panel rows older than 450 days | **UNSOURCED** | Document as "one fiscal year plus reporting lag"; make explicit |
| 88 | `4.0, 2.0, 4/3` | Annualization multipliers for Q1/Q2/Q3 TTM bases | **structural** (12/3, 12/6, 12/9) | None |
| 103, 138, 187 | `min_df=2` | A term must appear in at least two firms' documents to count | **conventional** (scikit-learn TF-IDF practice) | Document |
| 159 | `+ 1e6` | Smoothing added to revenue in the size-ratio damping | **UNSOURCED** | Document as numerical smoothing; effect is negligible for revenues in the millions or above, material below |
| 219 | `negatives=200, repeats=20, seed=7` | Paired-protocol sampling | **protocol** (pre-registered v0.69, in the ledger) | None |
| 164–181 | MASS formula, Eqs 6–10 | The scoring function itself | **sourced** — Straccamore & Zaccaria, PLOS One 2026 | None |
| 229 | `-12-31` year-end | Cutoff is the fiscal year-end preceding announcement | **protocol** | None |

### 1a. Independent re-derivation of the MASS engine (2026-09-03)
Implemented Eqs 6–10 from the paper text (Albora, Straccamore & Zaccaria,
arXiv 2404.07179 / PLoS One 21(2):e0341010) in plain Python with a
different structure, without reference to `pairs.py`, and compared against
`_mass_exact_scores` on a 12-firm random weighted corpus: 110 non-degenerate
pairs, maximum absolute difference 7.4e-15. **The engine matches the published
formula.**

**Unpublished convention found.** Eq 8 divides by zero when
max(Λ) − max(Λ^(T)) = 0 (the candidate holds the pool's largest column
maximum) or when max(Λ_(A))·(1 − max(Λ_(A))/max(Λ)) = 0 (the acquirer holds
the global maximum). The paper does not address either case. The code
assigns those pairs a score of **0** (`pairs.py`, the `denom <= eps or
(mN - mT) <= eps` guard). On the test corpus this fired on 22 of 132 pairs.
It is a deterministic penalty on the most central firms in a pool, chosen by
the implementer, not by the paper. Provenance: **UNSOURCED convention.**
Disposition: document at the code line; record the count of degenerate pairs
as a run metric in every pairing evaluation so its frequency in the live
pool is known rather than assumed; consider whether 0 is the right value
(the paper's limit as the denominator → 0 is not 0).

## 2. `score.py` — `scorecard`, hand-built target rating and pairing fit

P2 and P7 declare this a hand scorecard: "transparent, auditable rating — to
be measured, not assumed." Hand-set weights are permitted; they are still
unsourced numbers whose sum is a ranking.

| Item | Value | Provenance | Disposition |
|---|---|---|---|
| Approved drug | +25 | **UNSOURCED** | Document as analyst-set; the measured yardstick (M5 backtest rank of known acquisitions) is the only justification, and it must be cited at the weight |
| Phase-3 lead | +20 | **UNSOURCED** | same |
| ≥3 Phase-3 trials | +5 | **UNSOURCED** | same |
| Approval in trailing 12m | +10 | **UNSOURCED** | same |
| Positive mean CAR | +5 | **UNSOURCED** | same; note this reads a price-derived feature, which P2 permits for a hand scorecard |
| Market cap in band | +15, band $300M–$40B | **UNSOURCED** | Band edges are the sharpest cut in the file; sensitivity at ±50% |
| Existing relationship | +10 | **UNSOURCED** | same |
| ≥5 deal relationships | +5 | **UNSOURCED** | same |
| Runway < 24 months | +10 | **UNSOURCED** (24 months is a common "going concern" horizon) | Document as conventional |
| Acquirer-side exclusion | revenue > $10B or cap > $100B | **UNSOURCED** — and **inconsistent with §1** (`mass-exact` uses $2B revenue) | Reconcile: two models of record disagree on who is a buyer |
| Pairing eligibility | revenue > $5B or cap > $50B | **UNSOURCED** — third distinct buyer threshold in the codebase | Reconcile with the above |
| Pairing fit weights | 50 overlap / 30 relationship / 20 headroom | **UNSOURCED** | Document as analyst-set |
| Size headroom | acquirer cap ≥ 4× target cap | **UNSOURCED** | Document |

### 2a. Corrections to §2 (2026-09-03, found while annotating)
The first pass of this audit read `score.py`'s docstring as if it described
running code. Two of its claims are false, and the audit repeated them:

1. **Market cap threshold.** The docstring said acquirer-side exclusion at
   cap > $100B; the code has always used **$75B** (`7.5e10`). The code is what
   runs. Docstring corrected in place.
2. **The pairing fit.** The docstring described a hand-weighted fit
   (50 × overlap + 30 × relationship + 20 × size headroom) with eligibility at
   $5B revenue or $50B cap. **That engine has not run since v0.81**;
   `predict` pairs with MASS-exact × 100. So §2's "$5B/$50B" row and the
   "50/30/20" weights were describing dead text, not live constants — there
   are **two** buyer-threshold definitions in running code, not three
   ($2B revenue in pairs.py; $10B revenue or $75B cap in score.py).
   Docstring marked as superseded, with the live behaviour stated.
3. **Corroborating remnant.** `score.py` still computes
   `toks = _condition_tokens()` and never uses it — one of the three
   long-standing ruff findings. It is the retired engine's Jaccard input,
   scanning the whole trials table on every `predict` for nothing. Left in
   place (it is a model of record); removal belongs to the same
   pre-registered change that reconciles the thresholds.

**Lesson recorded:** an audit that reads docstrings inherits their errors.
Provenance claims must be checked against the executing line.

### 2b. Docstring sweep across the remaining modules (2026-09-03)
After §2a showed that an audit reading docstrings inherits their errors,
every claim in `pairs.py`, `study.py`, `improve.py` and `features.py` was
checked against the executing line. Four more false claims, all corrected in
place:

1. **`pairs.py`: "TF-IDF weighted — idf supplies the rare-technology
   emphasis."** The adopted engine uses RAW COUNTS; rarity comes from the
   paper's own Eq 10 (each technology column divided by its norm). TF-IDF is
   used only by `_sim_matrix`, which feeds the retired cosine baseline.
2. **`pairs.py`: "Writes gold/pair_report.txt."** It does not. That file is
   written by `baselines.evaluate_pairs`, the LEGACY `pairs` command, which
   now refuses to run.
3. **`study.py`: "with SPY as a robustness check."** No SPY path exists;
   `schema.BENCHMARKS` allows only `("XBI", "none")`. The claim also appeared
   in the comment beside `BENCHMARK`.
4. **`study.py`: "Five metrics."** Decorative count: CAR is three windows and
   Beta is recorded alongside.

`improve.py` and `features.py` check out: the purge derivation, the origins,
the holdout rule and the 400-day window all match the code.

**Pattern, not coincidence.** All six false claims found in this audit
(§2a plus these four) describe a RETIRED engine as if it were live. The
docstrings were written for the pre-v0.81 architecture and were never updated
when MASS-exact replaced the hand-weighted pairing. Disposition: docstrings
are part of the deliverable of any gate that supersedes an engine, and a
claim in a docstring is not evidence of anything until checked against the
executing line.

## 3. `improve.py` — `fitted`, the target-screen implementation (validated 2.2× lift)

| Line | Value | What it does | Provenance | Disposition |
|---|---|---|---|---|
| 36 | `DEV_END = 2022-12-31` | Development world ends; 2023+ is holdout | **protocol** (holdout ledger, both accesses spent) | None |
| 38 | `ORIGINS` 2016–2021 | Six walk-forward origins | **protocol** | None |
| 39 | `PURGE_Q = 4` | Purge four quarters after each origin | **structural** — 12-month forward labels overlap the next four quarters | None; the docstring states the derivation |
| 394, 422 | `PURGE_Q + 4` | Test window is the four quarters after the purge | **structural** | None |
| 397, 425 | `sum(ytr) < 10 or sum(yte) < 3` | Skip an origin with too few positives | **UNSOURCED** | Document as a stability floor; report how many origins it skipped |
| 335 | `C=0.5`, `max_iter=2000` | Logistic regression regularisation | **conventional** (scikit-learn defaults are C=1.0, max_iter=100; 0.5 is a modest choice) | Record whether chosen on the walk-forward or by hand; if by hand, state it |
| 343–349 | `max_depth=3`, `learning_rate=0.06`, `max_iter=300`, `min_samples_leaf=40`, `l2=1.0`, `random_state=7` | Gradient-boosting hyperparameters | **conventional** for a small tabular problem; no tuning record | Same disposition. The walk-forward makes them defensible but not derived |
| 266–268 | 365, 182 days | Trailing-12-month and 6-month event counts | **structural** (calendar) | None |
| 234–235 | 24, 12 | Trailing windows in months | **structural** | None |

## 4. `study.py` — `daily-bars`, the FDA event study

| Line | Value | Provenance | Disposition |
|---|---|---|---|
| 37 | `EST_DAYS = 120` | **conventional** — market-model estimation windows of 100–250 trading days are standard since Brown & Warner (1980, 1985), cited in the docstring | Document the citation at the constant |
| config 87–88 | `WINDOW_PRE = 10`, `WINDOW_POST = 10` | **conventional** — ±10-day event windows are standard | Document |
| 37 | ends at RelDay −11 | **structural** — estimation window must end before the event window begins | None |
| 159–160 | fast(3) vs slow(7) SMA for drift | **UNSOURCED** — a moving-average pair with no basis; not a standard event-study statistic | Eliminate or replace with post-event CAR, which is standard |
| 67 | `max(PRICE_PAD_DAYS, 300)` | **structural** — must cover EST_DAYS + windows in calendar days | None |
| config 89 | `PRICE_PAD_DAYS = 90` | **operational** | None |
| 171 | `CAR(-5, +5)` | **conventional** | Document |

## 5. `features.py` — feature panel

| Line | Value | Provenance | Disposition |
|---|---|---|---|
| 12, 196, 204 | ≤ 400 days | Financials older than 400 days are ignored | **UNSOURCED** — plausibly "one year plus a reporting lag" but not stated; differs from the 450 in `pairs.py` for the same purpose | Reconcile with §1 line 93 and document |
| 247, 296 | 365 days | Trailing 12 months | **structural** | None |
| 286 | 730 days | Trailing 24 months | **structural** | None |
| 118 | quarter-end dates | **structural** | None |
| 363 | 365 days | 52-week price window | **structural** | None |

## 6. `aspects.py` — `aspect-match` (NOT ADOPTED; corrected at gate L4-P)

| Value | Status |
|---|---|
| `TA_JACCARD_MIN = 0.05` | **UNSOURCED — ELIMINATED** at L4-P (`7b2967d`); overlap is now a continuous strength |
| `LOE_HORIZON_YEARS = 5` | **UNSOURCED — ELIMINATED** at L4-P; reported as a sensitivity across `LOE_HORIZONS = (3, 5, 7, 10)` |
| `LOE_HORIZONS = (3, 5, 7, 10)` | the sensitivity grid itself; bracket chosen to span industry commentary's three-to-five-year framing on both sides; **conventional**, not selected on results |
| `>= 8` tokens (inherited via `pairs._firm_docs`) | **UNSOURCED** — same as §1 line 75; the pool definition rides in the run note verbatim so chance is recomputable |
| `> $2B`, `<= 450 days` (inherited via `pairs._acquirer_side_iids`) | **UNSOURCED** — same as §1 |

## 7. `stakes.py` — F1 feeder (not a model)

| Value | Provenance | Disposition |
|---|---|---|
| `ERAS` four windows | **UNSOURCED** probe spread; the fourth era's start (2025-01-01) is **sourced** to the SEC structured-format mandate, confirmed by capture | None; affects specimen selection only |
| `PER_ERA_CAPTURES = 3`, `COMPANIES_TRIED_PER_ERA = 12` | **operational** | Labelled arbitrary in code |
| `MAX_PAGES_PER_MEMBER = 30` | **operational**; capped members are counted in the run metrics | None |
| `BUNDLE_CHARS = 40_000` | **operational** | None |
| `PLAUSIBLE_SICS` | **sourced** — SEC SIC codes for pharma/bio/device/diagnostics | None |
| Blind sample `n = 60` | **conventional**; Wilson half-width ±0.077 at p=0.90, computed in the record; anchored to the miner's 56/60 | Documented in the parser development record |
| `_QUALIFIED`, `_CAPPED`, `_NONE_WORD` patterns | **sourced** — each written from a verbatim capture, locked in tests | None |

## 8. `efts.py` — PDUFA miner

| Value | Provenance | Disposition |
|---|---|---|
| `_WINDOW = 160` chars | **measured** — the rule set was tuned across ten rule versions with blind precision at each (r9 0.933 [0.841, 0.974]) | None |
| `DEFAULT_FORMS` | **sourced** — SEC form types | None |

## 9. `universe.py` — membership rule of record

| Value | Provenance | Disposition |
|---|---|---|
| `SICS = ("2836", "2834")` | **sourced** — SEC industry classification, cited in the paper | None |
| `ANNUAL_FORMS`, `FORM25`, `FORM15` | **sourced** — SEC form types | None |
| `max_pages_per_sic = 40` | **operational**; if a SIC has more than 4,000 filers the list truncates silently — verify against EDGAR's count | Add a truncation check |
| 2001 start | **protocol** | None |

## 10. `config.py`

| Value | Provenance |
|---|---|
| `SEC_RATE_LIMIT = 0.11` s | **sourced** — SEC fair-access limit of 10 requests/second |
| `WINDOW_PRE/POST = 10` | **conventional** (see §4) |
| `PRICE_PAD_DAYS = 90` | **operational** |
| `chembl.PACE = 0.35` s | **operational** (politeness, no key) |

---

## Summary

**UNSOURCED constants inside models whose results are of record:**

1. `pairs.py` `>= 8` tokens — defines every candidate pool and every chance baseline. **First to address.**
2. `pairs.py` `> $2B` revenue — defines who is a buyer.
3. `pairs.py` `<= 450 days` staleness.
4. `score.py` — thirteen hand-set weights and two cut-off bands.
5. `study.py` fast(3)/slow(7) drift statistic — non-standard, no basis.
6. `improve.py` positive-count floors (10 / 3) and untracked hyperparameter provenance.
7. `pairs.py` zero-score convention on Eq 8's undefined case — an implementer's choice the paper never specified (§1a).

**Annotation pass completed 2026-09-03** (no behaviour change): every
constant above is now marked with its provenance class at its point of
definition, and the size thresholds and staleness windows are declared once
in `schema.py` (`PAIRS_ACQUIRER_SIDE_REVENUE`, `SCORE_ACQUIRER_SIDE_REVENUE`,
`SCORE_ACQUIRER_SIDE_MARKETCAP`, `SCORE_TARGET_CAP_BAND`,
`PAIRS_FINANCIALS_STALENESS_DAYS`, `FEATURES_FINANCIALS_STALENESS_DAYS`) so
the disagreement is visible in one place. **Values are unchanged**: unifying
them changes what `predict` and the pairing reports output, which is a
pre-registered change requiring a re-run and a fresh fingerprint baseline.

**Inconsistencies between models of record:** three different definitions of "acquirer-side" (`$2B` revenue in `pairs.py`; `$10B` revenue or `$100B` cap for exclusion and `$5B`/`$50B` for pairing in `score.py`), and two different financial-staleness windows (450 days in `pairs.py`, 400 in `features.py`) for the same purpose.

**Sourced or conventional and needing only a citation at the definition:** the MASS formula, the event-study windows, the purge/embargo structure, SEC limits and form types, SIC codes, the blind-sample size.

**Recommended gate (audit-only, no re-runs, no re-tuning):** annotate every constant above at its definition with its provenance class; reconcile the three buyer thresholds and the two staleness windows into single declared values with the discrepancy recorded; report `>= 8` and `> $2B` as sensitivities in the next pairing evaluation; replace the drift SMA with post-event CAR. Results of record are not re-run — any re-run is a pre-registered evaluation of its own.
