# src/biointel/improve.py
"""Model improvement under a leakage-proof protocol.

PROTOCOL (the legitimate version of "randomize the test sets"):
  * DEVELOPMENT on pre-2023 data only, evaluated by PURGED, EMBARGOED
    walk-forward with multiple origins (2016..2021): train up to each
    origin, PURGE the 4 quarters after the origin (their 12-month labels
    overlap the test window -- de Prado's purging), test the next year.
    Pooled out-of-fold AUC-PR across origins = the development score.
  * The 2023+ HOLDOUT is untouched during development and evaluated
    exactly once, by `improve holdout`, when iteration stops.
  Plain shuffle-CV is forbidden here: 12-month forward labels overlap
  across adjacent quarters and companies share M&A waves, so shuffling
  leaks the future into training.

IMPROVEMENTS over the baseline logistic:
  * Engineered fundamentals (all leak-free, no price inputs): deltas and
    trends (cash trajectory, burn acceleration, trial-start momentum,
    R&D intensity), company age, financing-deal intensity, cash rank
    within quarter (cross-sectional, fundamentals-based).
  * Model class: histogram gradient boosting (sklearn) beside the
    logistic -- the imbalanced-M&A literature finds nonlinear models add
    value when signal is spread across correlated features.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta

from biointel import config, results, store
from biointel.fit import FEATURES, _auc_pr, _auc_roc, _events_for_robust, _n

log = logging.getLogger(__name__)

DEV_END = "2022-12-31"  # development world ends here
ORIGINS = ["2016-12-31", "2017-12-31", "2018-12-31", "2019-12-31", "2020-12-31", "2021-12-31"]
PURGE_Q = 4  # quarters purged after each origin

BASE_FUND = [
    n for n, _ in FEATURES if n not in ("logMarketCap", "Drawdown52w", "CAR12m", "Drift12m")
]


def _quarters_after(q, k):
    d = date.fromisoformat(q)
    for _ in range(k):
        d = (d + timedelta(days=95)).replace(day=1) - timedelta(days=1)
    return d.isoformat()


def _load_panel():
    rows = store.read_table("feature_panel")
    rows = [
        r
        for r in rows
        if (r.get("Currency") or "USD") == "USD"
        and (_n(r.get("CashSTI")) is not None or (_n(r.get("TrialsTotal")) or 0) > 0)
    ]
    rows.sort(key=lambda r: (r["IID"], r["QuarterEnd"]))
    return rows


TA_TOKENS = {
    "_taOnco": (
        "cancer",
        "tumor",
        "oncology",
        "carcinoma",
        "lymphoma",
        "leukemia",
        "melanoma",
        "myeloma",
    ),
    "_taNeuro": (
        "alzheimer",
        "parkinson",
        "epilepsy",
        "neuro",
        "sclerosis",
        "migraine",
        "depression",
    ),
    "_taImmune": ("arthritis", "psoriasis", "lupus", "crohn", "colitis", "immune", "inflammat"),
    "_taRare": ("orphan", "rare", "duchenne", "fabry", "gaucher", "amyloid", "atrophy"),
    "_taCardio": ("cardio", "heart", "hypertension", "lipid", "cholesterol", "thromb"),
}


def _activist_dates():
    """(iid -> sorted SC 13D dates) from each company's own submissions
    record -- activist stakes are a documented takeover precursor.
    Extracted once and cached in table activist_13d; rebuilt only if
    the cache is absent."""
    out = defaultdict(list)
    cached = store.read_table("activist_13d")
    if cached:
        for r in cached:
            out[r["IID"]].append(r["Date"])
        return out
    from biointel.labels import _submissions

    comps = store.read_table("companies")
    for i, c in enumerate(comps, 1):
        if i % 100 == 0:
            log.info(f"  activist scan {i}/{len(comps)}")
        cik = str(c.get("CIK", "")).zfill(10)
        if not cik.strip("0"):
            continue
        try:
            rec = (_submissions(cik).get("filings") or {}).get("recent") or {}
        except Exception:
            continue
        for f_, d_ in zip(rec.get("form", []), rec.get("filingDate", [])):
            fu = f_.upper()
            if (
                fu in ("SC 13D", "SCHEDULE 13D")
                or fu.startswith("SC 13D/")
                or fu.startswith("SCHEDULE 13D/")
            ):
                out[c["IID"]].append(d_)
    for v in out.values():
        v.sort()
    store.write_table(
        "activist_13d",
        [{"IID": iid, "Date": d} for iid, ds in out.items() for d in ds],
        ["IID", "Date"],
    )
    return out


def engineer(rows):
    """Add leak-free engineered features per (company, quarter): uses only
    the company's OWN PAST rows and same-quarter cross-sections."""
    by_iid = defaultdict(list)
    for r in rows:
        by_iid[r["IID"]].append(r)
    # cross-sectional cash rank per quarter (fundamentals, not price)
    by_q = defaultdict(list)
    for r in rows:
        c = _n(r.get("CashSTI"))
        if c is not None:
            by_q[r["QuarterEnd"]].append(c)
    for q in by_q:
        by_q[q].sort()

    def rank(q, v):
        arr = by_q.get(q) or []
        if not arr or v is None:
            return 0.5
        import bisect

        return bisect.bisect_left(arr, v) / len(arr)

    # M&A-wave clock: universe acquisitions announced in the trailing
    # year before each quarter -- other companies' PUBLIC announcements,
    # strictly past, leak-free.
    ev_dates = sorted(d for _, d in _events_for_robust(strict=False))
    import bisect as _bi

    def wave(q):
        lo = (date.fromisoformat(q) - timedelta(days=365)).isoformat()
        return _bi.bisect_right(ev_dates, q) - _bi.bisect_right(ev_dates, lo)

    # therapeutic-area exposure from trials STARTED on or before each
    # quarter (no lookahead into later trials)
    trials_by_iid = defaultdict(list)
    for t in store.read_table("trials"):
        sd = (t.get("StartDate") or "")[:10]
        if not sd:
            continue
        low = (t.get("Conditions") or "").lower()
        vec = tuple(1.0 if any(k in low for k in kws) else 0.0 for kws in TA_TOKENS.values())
        if any(vec):
            trials_by_iid[t["IID"]].append((sd, vec))
    for v in trials_by_iid.values():
        v.sort()

    def ta_vec(iid, q):
        out = [0.0] * len(TA_TOKENS)
        for sd, vec in trials_by_iid.get(iid, []):
            if sd > q:
                break
            out = [max(a, b) for a, b in zip(out, vec)]
        return out

    # trial-outcome catalysts (silver reparse, dates = PrimaryCompletion
    # falling back to CompletionDate; termination timing approximated by
    # the same fields -- documented approximation)
    p3done = defaultdict(list)
    termd = defaultdict(list)
    for t in store.read_table("trials"):
        d = (t.get("PrimaryCompletion") or t.get("CompletionDate") or "")[:10]
        if not d:
            continue
        st = t.get("Status") or ""
        if st == "COMPLETED" and "PHASE3" in (t.get("Phase") or ""):
            p3done[t["IID"]].append(d)
        elif st == "TERMINATED":
            termd[t["IID"]].append(d)
    for v in p3done.values():
        v.sort()
    for v in termd.values():
        v.sort()
    import bisect as _bi3

    def _cnt(ds, q, days):
        lo = (date.fromisoformat(q) - timedelta(days=days)).isoformat()
        return float(_bi3.bisect_right(ds, q) - _bi3.bisect_right(ds, lo))

    pairf = defaultdict(list)
    for r0 in store.read_table("pair_feature"):
        pairf[r0["IID"]].append((r0["YearEnd"], float(r0["MaxSimToAcq"])))
    for v in pairf.values():
        v.sort()

    def max_sim(iid, q):
        best = 0.0
        for ye, v in pairf.get(iid, []):
            if ye <= q:
                best = v
            else:
                break
        return best

    act = _activist_dates()
    import bisect as _bi2

    def act_counts(iid, q):
        ds = act.get(iid) or []
        lo24 = (date.fromisoformat(q) - timedelta(days=730)).isoformat()
        lo12 = (date.fromisoformat(q) - timedelta(days=365)).isoformat()
        c24 = _bi2.bisect_right(ds, q) - _bi2.bisect_right(ds, lo24)
        c12 = _bi2.bisect_right(ds, q) - _bi2.bisect_right(ds, lo12)
        return float(c24), 1.0 if c12 else 0.0

    for iid, seq in by_iid.items():
        for i, r in enumerate(seq):
            prev = seq[i - 1] if i >= 1 else None
            prev4 = seq[i - 4] if i >= 4 else None
            c0 = _n(r.get("CashSTI"))
            r["_dCash1"] = (
                (c0 - _n(prev.get("CashSTI"))) / abs(_n(prev.get("CashSTI")) or 1)
                if prev and c0 is not None and _n(prev.get("CashSTI"))
                else 0.0
            )
            r["_dCash4"] = (
                (c0 - _n(prev4.get("CashSTI"))) / abs(_n(prev4.get("CashSTI")) or 1)
                if prev4 and c0 is not None and _n(prev4.get("CashSTI"))
                else 0.0
            )
            t0 = _n(r.get("TrialsStarted12m")) or 0.0
            r["_dStarts"] = (t0 - (_n(prev4.get("TrialsStarted12m")) or 0.0)) if prev4 else 0.0
            rnd, ta = _n(r.get("RnD")), _n(r.get("TotalAssets"))
            r["_rndInt"] = (rnd / ta) if (rnd and ta) else 0.0
            r["_age"] = i / 4.0
            r["_finDeals"] = min((_n(r.get("RelDeal")) or 0.0), 60.0)
            r["_cashRank"] = rank(r["QuarterEnd"], c0)
            rw = _n(r.get("RunwayMonths"))
            r["_lowRunway"] = 1.0 if (rw is not None and rw < 18) else 0.0
            r["_wave"] = float(wave(r["QuarterEnd"]))
            r["_act13D24m"], r["_act13D12m"] = act_counts(iid, r["QuarterEnd"])
            q_ = r["QuarterEnd"]
            r["_maxSimToAcq"] = max_sim(iid, q_)
            r["_p3done12m"] = _cnt(p3done.get(iid, []), q_, 365)
            r["_p3done6m"] = _cnt(p3done.get(iid, []), q_, 182)
            r["_term12m"] = _cnt(termd.get(iid, []), q_, 365)
            for name, val in zip(TA_TOKENS, ta_vec(iid, r["QuarterEnd"])):
                r[name] = val
    return rows


ENGINEERED = [
    "_dCash1",
    "_dCash4",
    "_dStarts",
    "_rndInt",
    "_age",
    "_finDeals",
    "_cashRank",
    "_lowRunway",
    "_wave",
    "_taOnco",
    "_taNeuro",
    "_taImmune",
    "_taRare",
    "_taCardio",
    "_act13D24m",
    "_act13D12m",
    "_p3done12m",
    "_p3done6m",
    "_term12m",
    "_maxSimToAcq",
]


def _xy(rows, events, feats, lo, hi):
    tgt = {}
    for iid, d in events:
        if iid not in tgt or d < tgt[iid]:
            tgt[iid] = d
    fmap = dict(FEATURES)
    X, y = [], []
    for r in rows:
        q = r["QuarterEnd"]
        if not (lo < q <= hi):
            continue
        a = tgt.get(str(r["IID"]))
        if a and q >= a:
            continue
        h12 = (date.fromisoformat(q) + timedelta(days=365)).isoformat()
        yy = 1 if (a and q < a <= h12) else 0
        vec = []
        for n in feats:
            vec.append(fmap[n](r) if n in fmap else float(r.get(n) or 0.0))
        X.append(vec)
        y.append(yy)
    return X, y


def _models():
    out = []
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        out.append(
            (
                "logistic",
                lambda: make_pipeline(
                    StandardScaler(),
                    LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5),
                ),
            )
        )
        out.append(
            (
                "hist-gbm",
                lambda: HistGradientBoostingClassifier(
                    # CONVENTIONAL hyperparameters for a small tabular
                    # problem; no tuning record exists. The purged
                    # walk-forward makes them defensible, not derived.
                    max_depth=3,
                    learning_rate=0.06,
                    max_iter=300,
                    class_weight="balanced",
                    min_samples_leaf=40,
                    l2_regularization=1.0,
                    random_state=7,
                ),
            )
        )
    except ImportError:
        pass
    return out


def develop() -> dict:
    """Purged walk-forward development scores; holdout untouched."""
    rows = engineer(_load_panel())
    events = _events_for_robust(strict=False)
    specs = [("fundamentals", BASE_FUND), ("fund+engineered", BASE_FUND + ENGINEERED)]
    D, row_doc = (None, None)
    try:
        D, row_doc = _text_assets(rows)
    except Exception as exc:
        log.info(f"  (text assets unavailable: {type(exc).__name__})")
    if D is not None and row_doc and any(i >= 0 for i in row_doc):
        tscores = _text_scores_oof(rows, events, None, D, row_doc)
        for r, ts in zip(rows, tscores):
            r["_textScore"] = ts
        specs.append(("fund+eng+text", BASE_FUND + ENGINEERED + ["_textScore"]))
        cov = sum(1 for i in row_doc if i >= 0) / len(row_doc)
        log.info(f"  text coverage: {cov:.1%} of firm-quarters have a usable 10-K document")
    run = results.start(
        "develop",
        "develop",
        _DEV_INPUTS,
        {
            "origins_first": ORIGINS[0],
            "origins_last": ORIGINS[-1],
            "purge_q": PURGE_Q,
            "dev_end": DEV_END,
            "specs": ";".join(n for n, _ in specs),
        },
    )
    models = _models()
    for mname, mk in models + [("ensemble", None)]:
        for sname, feats in specs:
            if mname == "ensemble":
                pool_s, pool_y = [], []
                for o in ORIGINS:
                    te_lo = _quarters_after(o, PURGE_Q)
                    te_hi = min(_quarters_after(o, PURGE_Q + 4), DEV_END)
                    Xtr, ytr = _xy(rows, events, feats, "0000", o)
                    Xte, yte = _xy(rows, events, feats, te_lo, te_hi)
                    # UNSOURCED stability floors (constants audit
                    # 2026-09-03): origins with too few positives are
                    # skipped; the skip count is not currently reported.
                    if sum(ytr) < 10 or sum(yte) < 3:
                        continue
                    ranks = []
                    for _, mk2 in models:
                        m = mk2()
                        m.fit(Xtr, ytr)
                        p = list(map(float, m.predict_proba(Xte)[:, 1]))
                        order = sorted(range(len(p)), key=lambda i: p[i])
                        rk = [0.0] * len(p)
                        for pos_i, i in enumerate(order):
                            rk[i] = pos_i / max(len(p) - 1, 1)
                        ranks.append(rk)
                    pool_s += [sum(r[i] for r in ranks) / len(ranks) for i in range(len(yte))]
                    pool_y += yte
                if pool_y and sum(pool_y):
                    g = f"{mname}|{sname}"
                    run.metric(g, "n", len(pool_y))
                    run.metric(g, "pos", sum(pool_y))
                    run.metric(g, "aucpr", _auc_pr(pool_s, pool_y))
                    run.metric(g, "roc", _auc_roc(pool_s, pool_y))
                    log.info(_dev_row(mname, sname, results.Metrics(run.record()), g))
                continue
            pool_s, pool_y = [], []
            for o in ORIGINS:
                te_lo = _quarters_after(o, PURGE_Q)
                te_hi = _quarters_after(o, PURGE_Q + 4)
                if te_hi > DEV_END:
                    te_hi = DEV_END
                Xtr, ytr = _xy(rows, events, feats, "0000", o)
                Xte, yte = _xy(rows, events, feats, te_lo, te_hi)
                if sum(ytr) < 10 or sum(yte) < 3:
                    continue
                m = mk()
                m.fit(Xtr, ytr)
                p = m.predict_proba(Xte)[:, 1]
                pool_s += list(map(float, p))
                pool_y += yte
            g = f"{mname}|{sname}"
            if not pool_y or not sum(pool_y):
                run.metric(g, "insufficient", 1)
                continue
            run.metric(g, "n", len(pool_y))
            run.metric(g, "pos", sum(pool_y))
            run.metric(g, "aucpr", _auc_pr(pool_s, pool_y))
            run.metric(g, "roc", _auc_roc(pool_s, pool_y))
            log.info(_dev_row(mname, sname, results.Metrics(run.record()), g))
    report, run_id = results.record_and_export(run, "development_report.txt")
    log.info(f"run {run_id} recorded")
    return {"status": "ok", "message": report, "run_id": run_id}


_DEV_INPUTS = [
    "feature_panel",
    "ma_events",
    "ma_events_universe",
    "companies",
    "trials",
    "pair_feature",
    "activist_13d",
]


def _dev_row(mname: str, sname: str, m, g: str) -> str:
    if m.has(g, "insufficient"):
        return f"{mname:<10}{sname:<18}INSUFFICIENT"
    n, pos, ap = m.i(g, "n"), m.i(g, "pos"), m.f(g, "aucpr")
    br = pos / n
    return (
        f"{mname:<10}{sname:<18}n={n:<7}"
        f"pos={pos:<5}AUC-PR {ap:.3f}  "
        f"lift {ap / br:.1f}x  ROC {m.f(g, 'roc'):.3f}"
    )


def render_develop(rec: dict) -> str:
    """Report text of develop from its record (byte-identical to the file)."""
    m = results.Metrics(rec)
    lines = [
        "PURGED WALK-FORWARD DEVELOPMENT (holdout 2023+ untouched)",
        f"origins {m.p('origins_first')[:4]}..{m.p('origins_last')[:4]}, "
        f"purge {int(m.p('purge_q'))}q, pooled out-of-fold AUC-PR",
    ]
    for g in m.groups():
        mname, sname = g.split("|", 1)
        lines.append(_dev_row(mname, sname, m, g))
    return "\n".join(lines)


def text_sweep() -> dict:
    """Shrinkage sweep for the text scorer (dev window only): the
    converged low-alpha reader overfit ~550 positives; test whether a
    properly shrunk text signal exists."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    rows = engineer(_load_panel())
    events = _events_for_robust(strict=False)
    D, row_doc = _text_assets(rows)
    if D is None:
        return {"status": "empty", "message": "No text corpus."}
    feats = BASE_FUND + ENGINEERED + ["_textScore"]
    run = results.start("textsweep", "develop textsweep", _DEV_INPUTS, {"purge_q": PURGE_Q})
    best_ap = None
    for alpha in (1e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2):
        ts = _text_scores_oof(rows, events, None, D, row_doc, alpha=alpha)
        for r, t in zip(rows, ts):
            r["_textScore"] = t
        pool_s, pool_y = [], []
        for o in ORIGINS:
            te_lo = _quarters_after(o, PURGE_Q)
            te_hi = min(_quarters_after(o, PURGE_Q + 4), DEV_END)
            Xtr, ytr = _xy(rows, events, feats, "0000", o)
            Xte, yte = _xy(rows, events, feats, te_lo, te_hi)
            if sum(ytr) < 10 or sum(yte) < 3:
                continue
            m = HistGradientBoostingClassifier(
                max_depth=3,
                learning_rate=0.03,
                max_iter=300,
                class_weight="balanced",
                min_samples_leaf=25,
                l2_regularization=1.0,
                random_state=7,
            )
            m.fit(Xtr, ytr)
            pool_s += list(map(float, m.predict_proba(Xte)[:, 1]))
            pool_y += yte
        if not sum(pool_y):
            continue
        ap = _auc_pr(pool_s, pool_y)
        g = repr(float(alpha))
        run.metric(g, "alpha", float(alpha))
        run.metric(g, "n", len(pool_y))
        run.metric(g, "pos", sum(pool_y))
        run.metric(g, "aucpr", ap)
        best_ap = ap if best_ap is None or ap > best_ap else best_ap
        log.info(_sweep_row(results.Metrics(run.record()), g))
    if best_ap is not None:
        run.metric("_", "best_aucpr", best_ap)
    report, run_id = results.record_and_export(run, "text_sweep_report.txt")
    log.info(f"run {run_id} recorded")
    return {"status": "ok", "message": report, "run_id": run_id}


def _sweep_row(m, g: str) -> str:
    alpha, n, pos, ap = m.f(g, "alpha"), m.i(g, "n"), m.i(g, "pos"), m.f(g, "aucpr")
    br = pos / n
    return f"  alpha={alpha:<8} AUC-PR {ap:.4f}  lift {ap / br:.2f}x"


def render_text_sweep(rec: dict) -> str:
    """Report text of develop textsweep from its record (byte-identical to the file)."""
    m = results.Metrics(rec)
    lines = ["TEXT SHRINKAGE SWEEP (hist-gbm fund+eng+text, dev pooled OOF)"]
    for g in m.groups():
        if g == "_":
            continue
        lines.append(_sweep_row(m, g))
    return "\n".join(lines)


def tune() -> dict:
    """Small GBM grid on the winning spec, development window only.
    Best configuration is persisted to gold/best_config.json and used by
    `holdout` when model_name == 'tuned'."""
    import json

    from sklearn.ensemble import HistGradientBoostingClassifier

    rows = engineer(_load_panel())
    events = _events_for_robust(strict=False)
    feats = BASE_FUND + ENGINEERED
    grid = [(d, lr, leaf) for d in (2, 3, 4) for lr in (0.03, 0.06, 0.1) for leaf in (25, 40, 60)]
    best = None
    run = results.start(
        "tune",
        "develop tune",
        _DEV_INPUTS,
        {
            "purge_q": PURGE_Q,
            "grid_depth": "2;3;4",
            "grid_lr": "0.03;0.06;0.1",
            "grid_leaf": "25;40;60",
            "max_iter": 300,
            "l2_regularization": 1.0,
            "random_state": 7,
        },
    )
    for d, lr, leaf in grid:
        pool_s, pool_y = [], []
        for o in ORIGINS:
            te_lo = _quarters_after(o, PURGE_Q)
            te_hi = min(_quarters_after(o, PURGE_Q + 4), DEV_END)
            Xtr, ytr = _xy(rows, events, feats, "0000", o)
            Xte, yte = _xy(rows, events, feats, te_lo, te_hi)
            if sum(ytr) < 10 or sum(yte) < 3:
                continue
            m = HistGradientBoostingClassifier(
                max_depth=d,
                learning_rate=lr,
                max_iter=300,
                class_weight="balanced",
                min_samples_leaf=leaf,
                l2_regularization=1.0,
                random_state=7,
            )
            m.fit(Xtr, ytr)
            pool_s += list(map(float, m.predict_proba(Xte)[:, 1]))
            pool_y += yte
        if not sum(pool_y):
            continue
        ap = _auc_pr(pool_s, pool_y)
        g = f"{d}|{lr!r}|{leaf}"
        run.metric(g, "depth", d)
        run.metric(g, "lr", float(lr))
        run.metric(g, "leaf", leaf)
        run.metric(g, "n", len(pool_y))
        run.metric(g, "pos", sum(pool_y))
        run.metric(g, "aucpr", ap)
        log.info(_tune_row(results.Metrics(run.record()), g))
        if best is None or ap > best[0]:
            best = (ap, {"max_depth": d, "learning_rate": lr, "min_samples_leaf": leaf})
    if best:
        p = store.write_export(
            "best_config.json",
            json.dumps(
                {
                    "model": "hist-gbm",
                    "spec": "fund+engineered",
                    "params": best[1],
                    "dev_aucpr": best[0],
                },
                indent=1,
            ),
        )
        run.artefact(p)
        run.metric("best", "depth", best[1]["max_depth"])
        run.metric("best", "lr", float(best[1]["learning_rate"]))
        run.metric("best", "leaf", best[1]["min_samples_leaf"])
        run.metric("best", "aucpr", best[0])
        log.info(_tune_best(results.Metrics(run.record())))
    report, run_id = results.record_and_export(run, "tuning_report.txt")
    log.info(f"run {run_id} recorded")
    return {"status": "ok", "message": report, "run_id": run_id}


def _tune_row(m, g: str) -> str:
    d, lr, leaf = m.i(g, "depth"), m.f(g, "lr"), m.i(g, "leaf")
    n, pos, ap = m.i(g, "n"), m.i(g, "pos"), m.f(g, "aucpr")
    br = pos / n
    return f"  depth={d} lr={lr:<5} leaf={leaf:<3} AUC-PR {ap:.4f}  lift {ap / br:.2f}x"


def _tune_best(m) -> str:
    cfg = {
        "max_depth": m.i("best", "depth"),
        "learning_rate": m.f("best", "lr"),
        "min_samples_leaf": m.i("best", "leaf"),
    }
    return (
        f"BEST -> {cfg} (dev AUC-PR {m.f('best', 'aucpr'):.4f}), persisted to gold/best_config.json"
    )


def render_tune(rec: dict) -> str:
    """Report text of develop tune from its record (byte-identical to the file)."""
    m = results.Metrics(rec)
    lines = ["GBM TUNING (fund+engineered, purged walk-forward, dev only)"]
    for g in m.groups():
        if g == "best":
            continue
        lines.append(_tune_row(m, g))
    if m.has("best", "aucpr"):
        lines.append(_tune_best(m))
    return "\n".join(lines)


def holdout(model_name: str, spec_name: str) -> dict:
    """LEGACY (P7 amendment 2026-08-30): ONE-SHOT final evaluation on 2023+
    of the chosen configuration. Both pre-registered accesses are SPENT (P10);
    never run again without a new-protocol decision. Kept for baseline
    diagnosis only. Shares engineer()/_load_panel() with live code, so an
    execution under a new protocol would read the live tables; its own
    reads (best_config.json) and its report stay on the frozen CSV folder.
    """
    rows = engineer(_load_panel())
    events = _events_for_robust(strict=False)
    feats = dict(
        [
            ("fundamentals", BASE_FUND),
            ("fund+engineered", BASE_FUND + ENGINEERED),
            ("fund+eng+text", BASE_FUND + ENGINEERED + ["_textScore"]),
        ]
    )[spec_name]
    if "text" in spec_name:
        D, row_doc = _text_assets(rows)
        if D is not None:
            ts = _text_scores_oof(rows, events, None, D, row_doc)
            for r, t in zip(rows, ts):
                r["_textScore"] = t
            feats = feats if "_textScore" in feats else feats + ["_textScore"]
    if model_name == "tuned":
        import json

        cfg = json.loads((config.GOLD / "best_config.json").read_text(encoding="utf-8"))
        from sklearn.ensemble import HistGradientBoostingClassifier

        mk = lambda: HistGradientBoostingClassifier(
            max_iter=300,
            class_weight="balanced",
            l2_regularization=1.0,
            random_state=7,
            **cfg["params"],
        )
    else:
        mk = dict(_models())[model_name]
    Xtr, ytr = _xy(rows, events, feats, "0000", DEV_END)
    Xte, yte = _xy(rows, events, feats, DEV_END, "9999")
    m = mk()
    m.fit(Xtr, ytr)
    p = list(map(float, m.predict_proba(Xte)[:, 1]))
    br = sum(yte) / len(yte)
    ap = _auc_pr(p, yte)
    msg = (
        f"FINAL HOLDOUT (2023+, evaluated once): {model_name} / "
        f"{spec_name}\n  n={len(yte)} pos={sum(yte)} "
        f"AUC-PR {ap:.3f}  lift {ap / br:.1f}x  "
        f"ROC {_auc_roc(p, yte):.3f}"
    )
    (config.GOLD / "holdout_report.txt").write_text(msg, encoding="utf-8")  # LEGACY path
    return {"status": "ok", "message": msg}


# ------------------------------------------------- 10-K text scorer
def _text_index():
    """(cik10 -> sorted [(filed, year)]) for stored Item-1 files, dates
    recovered from the cached submissions records."""
    import re as _re

    from biointel.labels import _filings_reaching
    from biointel.pipeline import TENK_DIR

    idx = defaultdict(list)
    files = {}
    for p in TENK_DIR.glob("*.txt"):
        if p.stat().st_size < 1500:
            continue
        m = _re.match(r"(\d{10})_(\d{4})\.txt", p.name)
        if m:
            files[(m.group(1), m.group(2))] = p
    by_cik = defaultdict(set)
    for cik, yr in files:
        by_cik[cik].add(yr)
    for cik, yrs in by_cik.items():
        try:
            quads = _filings_reaching(cik, "2013-01-01")
        except Exception:
            continue
        for f_, d_, acc, doc in quads:
            if f_ in ("10-K", "20-F") and d_[:4] in yrs:
                idx[cik].append((d_, d_[:4]))
    for v in idx.values():
        v.sort()
    return idx, files


def _text_assets(rows):
    """(doc_matrix, row_doc_index) for the panel rows: each row maps to
    the latest 10-K filed <= its quarter end (within 450 days), or -1."""

    from sklearn.feature_extraction.text import HashingVectorizer

    idx, files = _text_index()
    if not files:
        return None, None
    cik_by_iid = {}
    for c in store.read_table("companies"):
        cik_by_iid[str(c["IID"])] = str(c.get("CIK", "")).zfill(10)
    keys = sorted(files)
    key_pos = {k: i for i, k in enumerate(keys)}
    texts = (files[k].read_text(encoding="utf-8", errors="replace") for k in keys)
    vec = HashingVectorizer(
        n_features=2**18, ngram_range=(1, 2), stop_words="english", alternate_sign=False, norm="l2"
    )
    D = vec.transform(texts)
    row_doc = []
    for r in rows:
        cik = cik_by_iid.get(str(r["IID"]), "")
        q = r["QuarterEnd"]
        pick = -1
        for filed, yr in reversed(idx.get(cik, [])):
            if filed <= q:
                if (date.fromisoformat(q) - date.fromisoformat(filed)).days <= 450 and (
                    cik,
                    yr,
                ) in key_pos:
                    pick = key_pos[(cik, yr)]
                break
        row_doc.append(pick)
    return D, row_doc


def _text_scores_oof(rows, events, feats_unused, D, row_doc, alpha=1e-5):
    """Out-of-fold text score per row via the same purged walk-forward
    origins; rows without a usable document score 0.5 (uninformative)."""
    from sklearn.linear_model import SGDClassifier

    scores = [0.5] * len(rows)
    tgt = {}
    for iid, d in events:
        if iid not in tgt or d < tgt[iid]:
            tgt[iid] = d

    def label(r):
        a = tgt.get(str(r["IID"]))
        q = r["QuarterEnd"]
        if a and q >= a:
            return None
        h12 = (date.fromisoformat(q) + timedelta(days=365)).isoformat()
        return 1 if (a and q < a <= h12) else 0

    for o in ORIGINS + [DEV_END]:
        te_lo = _quarters_after(o, PURGE_Q) if o != DEV_END else DEV_END
        te_hi = min(_quarters_after(o, PURGE_Q + 4), DEV_END) if o != DEV_END else "9999"
        tr_i, tr_y, te_i = [], [], []
        for i, r in enumerate(rows):
            if row_doc[i] < 0:
                continue
            y = label(r)
            if y is None:
                continue
            q = r["QuarterEnd"]
            if q <= o:
                tr_i.append(i)
                tr_y.append(y)
            elif te_lo < q <= te_hi or (o == DEV_END and q > DEV_END):
                te_i.append(i)
        if sum(tr_y) < 10 or not te_i:
            continue
        m = SGDClassifier(
            loss="log_loss",
            class_weight="balanced",
            alpha=alpha,
            max_iter=80,
            tol=1e-4,
            early_stopping=False,
            random_state=7,
        )
        m.fit(D[[row_doc[i] for i in tr_i]], tr_y)
        p = m.predict_proba(D[[row_doc[i] for i in te_i]])[:, 1]
        for i, pi in zip(te_i, p):
            scores[i] = float(pi)
    return scores
