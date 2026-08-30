"""Phase M4 (fitted): logistic target-prediction model on the panel.

Replaces the checklist as the primary instrument now that the label set
holds hundreds of verified acquisitions. Design follows the imbalanced
-M&A evaluation literature: time-split validation (train on quarters up
to the split date, test strictly after), AUC-PR and precision@k as the
headline metrics (plain accuracy and AUC-ROC flatter models that miss
the minority class), class-weighted loss at the true base rate, and the
full coefficient vector printed for interpretability.

Pure standard library on purpose: the pipeline has no third-party
runtime dependencies and a 2-class logistic via gradient descent on a
few dozen standardized features neither needs nor benefits from more.
The transparent checklist score remains in `predict` as the baseline
comparator the paper reports against.
"""

from __future__ import annotations

import csv as _csv
import logging
import math

from biointel import config

log = logging.getLogger(__name__)

SPLIT = "2021-12-31"  # train <= SPLIT < test

FEATURES = [
    ("logCashSTI", lambda r: _log1p(_n(r["CashSTI"]))),
    ("logRevenue", lambda r: _log1p(_n(r["Revenue"]))),
    ("logMarketCap", lambda r: _log1p(_n(r["MarketCap"]))),
    ("Runway", lambda r: min(_n(r["RunwayMonths"]) or 60.0, 120.0)),
    ("HasApproved", lambda r: _n(r["HasApprovedDrug"]) or 0.0),
    ("LeadPhase", lambda r: _n(r["LeadPhase"]) or 0.0),
    ("TrialsPh3", lambda r: min(_n(r["TrialsPh3"]) or 0.0, 30.0)),
    ("Started12m", lambda r: min(_n(r["TrialsStarted12m"]) or 0.0, 30.0)),
    ("Approvals12m", lambda r: _n(r["Approvals12m"]) or 0.0),
    ("Rejections12m", lambda r: _n(r["Rejections12m"]) or 0.0),
    ("CAR12m", lambda r: _n(r["CAR12m_mean"]) or 0.0),
    ("Drift12m", lambda r: _n(r["Drift12m_mean"]) or 0.0),
    ("Drawdown52w", lambda r: _n(r["Drawdown52w"]) or 0.0),
    ("RelDeal", lambda r: min(_n(r["RelDeal"]) or 0.0, 60.0)),
    ("RelInUniverse", lambda r: min(_n(r["RelInUniverse"]) or 0.0, 20.0)),
]


def _n(v):
    try:
        return float(v) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _log1p(v):
    return math.log1p(max(v, 0.0)) if v is not None else 0.0


def _sigmoid(z):
    if z < -35:
        return 0.0
    if z > 35:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def _standardize(X, mu=None, sd=None):
    n, d = len(X), len(X[0])
    if mu is None:
        mu = [sum(x[j] for x in X) / n for j in range(d)]
        sd = [
            math.sqrt(sum((x[j] - mu[j]) ** 2 for x in X) / max(n - 1, 1)) or 1.0 for j in range(d)
        ]
    Z = [[(x[j] - mu[j]) / sd[j] for j in range(d)] for x in X]
    return Z, mu, sd


def _fit_logistic(X, y, iters=400, lr=0.5, l2=1e-3):
    """Class-weighted logistic regression via batch gradient descent.

    Uses numpy when available: on Windows/CPython 3.13 the pure-Python
    hot loop hard-crashed the interpreter (0xC0000409) mid-iteration on
    the full 35k-row panel -- localized via checkpoint harness on
    2026-08-25. Vectorizing removes the interpreter-bound loop entirely
    and is ~100x faster; the pure path remains as fallback so the module
    still runs without the dependency."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        Xa = np.asarray(X, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        n, d = Xa.shape
        pos = float(ya.sum())
        w_pos = (n - pos) / max(pos, 1.0)
        wt = np.where(ya > 0, w_pos, 1.0)
        w = np.zeros(d)
        b = 0.0
        for _ in range(iters):
            z = Xa @ w + b
            pz = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
            err = wt * (pz - ya)
            b -= lr / n * float(err.sum())
            w -= lr / n * (Xa.T @ err + l2 * w * n)
        return list(map(float, w)), float(b)
    return _fit_logistic_py(X, y, iters, lr, l2)


def _fit_logistic_py(X, y, iters=400, lr=0.5, l2=1e-3):
    """Pure-python fallback (original implementation)."""
    n, d = len(X), len(X[0])
    pos = sum(y)
    w_pos = (n - pos) / max(pos, 1)
    w = [0.0] * d
    b = 0.0
    for it in range(iters):
        gb = 0.0
        gw = [0.0] * d
        for xi, yi in zip(X, y):
            p = _sigmoid(b + sum(wj * xj for wj, xj in zip(w, xi)))
            wt = w_pos if yi else 1.0
            err = wt * (p - yi)
            gb += err
            for j in range(d):
                gw[j] += err * xi[j]
        scale = lr / n
        b -= scale * gb
        for j in range(d):
            w[j] -= scale * (gw[j] + l2 * w[j] * n)
    return w, b


def _auc_pr(scores, labels):
    """Average precision (area under the precision-recall curve)."""
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = fp = 0
    pos = sum(labels)
    if pos == 0:
        return 0.0
    ap = 0.0
    prev_recall = 0.0
    for i in order:
        if labels[i]:
            tp += 1
            recall = tp / pos
            ap += (recall - prev_recall) * (tp / (tp + fp))
            prev_recall = recall
        else:
            fp += 1
    return ap


def _auc_roc(scores, labels):
    pairs = sorted(zip(scores, labels))
    pos = sum(labels)
    neg = len(labels) - pos
    if not pos or not neg:
        return 0.5
    rank_sum = 0.0
    for rank, (s, l) in enumerate(pairs, 1):
        if l:
            rank_sum += rank
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def fit(censor_lead_days: int = 0) -> dict:
    path = config.GOLD / "model_panel.csv"
    if not path.exists():
        return {"status": "empty", "message": "Run `features` first."}
    with path.open(encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))

    # risk-set censoring: once a company's acquisition is ANNOUNCED, its
    # later quarters are public-knowledge pending-deal states, not
    # prediction opportunities -- the company exits the risk set.
    announce_by_iid = {}
    epath = config.SILVER / "ma_events.csv"
    if epath.exists():
        with epath.open(encoding="utf-8") as f:
            for e in _csv.DictReader(f):
                if e.get("Role") == "target" and e.get("AnnounceDate"):
                    iid = str(e["FilerIID"])
                    d = e["AnnounceDate"]
                    if iid not in announce_by_iid or d < announce_by_iid[iid]:
                        announce_by_iid[iid] = d
    if censor_lead_days:
        from datetime import date as _d
        from datetime import timedelta as _td

        announce_by_iid = {
            k: (_d.fromisoformat(v) - _td(days=censor_lead_days)).isoformat()
            for k, v in announce_by_iid.items()
        }

    usable = [
        r
        for r in rows
        if (r.get("Currency") or "USD") == "USD"
        and (_n(r.get("CashSTI")) is not None or (_n(r.get("TrialsTotal")) or 0) > 0)
        and not (
            str(r["IID"]) in announce_by_iid and r["QuarterEnd"] >= announce_by_iid[str(r["IID"])]
        )
    ]
    train = [r for r in usable if r["QuarterEnd"] <= SPLIT]
    test = [r for r in usable if r["QuarterEnd"] > SPLIT]

    def matrix(rs):
        X = [[f(r) for _, f in FEATURES] for r in rs]
        y = [1 if r.get("AcquiredNext12m") == "1" else 0 for r in rs]
        return X, y

    Xtr, ytr = matrix(train)
    Xte, yte = matrix(test)
    n_pos_tr, n_pos_te = sum(ytr), sum(yte)
    if n_pos_tr < 10:
        return {
            "status": "insufficient",
            "message": f"Only {n_pos_tr} positive train firm-quarters "
            f"(need >= 10). Panel not label-complete yet -- "
            f"run labels/features after full rebuild.",
        }

    Ztr, mu, sd = _standardize(Xtr)
    Zte, _, _ = _standardize(Xte, mu, sd)
    w, b = _fit_logistic(Ztr, ytr)

    def _score(Z):
        try:
            import numpy as np

            Za = np.asarray(Z, dtype=np.float64)
            zz = np.clip(Za @ np.asarray(w) + b, -35, 35)
            return list(map(float, 1.0 / (1.0 + np.exp(-zz))))
        except ImportError:
            return [_sigmoid(b + sum(wj * xj for wj, xj in zip(w, z))) for z in Z]

    str_ = _score(Ztr)
    ste = _score(Zte)

    # precision@k on the latest MATURE test quarter: the 12-month label
    # window must have fully elapsed, or missing future deals read as
    # false negatives by construction.
    from datetime import date, timedelta

    mature_cut = (date.today() - timedelta(days=365)).isoformat()
    mature_qs = [r["QuarterEnd"] for r in test if r["QuarterEnd"] <= mature_cut]
    last_q = max(mature_qs) if mature_qs else max(r["QuarterEnd"] for r in test)
    idx_last = [i for i, r in enumerate(test) if r["QuarterEnd"] == last_q]

    def prec_at(k, idx, scores, labels):
        top = sorted(idx, key=lambda i: -scores[i])[:k]
        return sum(labels[i] for i in top) / max(len(top), 1)

    # test-period top-20 across all quarters (dedup by company, best quarter)
    best = {}
    for i, r in enumerate(test):
        t = r["Ticker"] or r["Company"]
        if t not in best or ste[i] > ste[best[t]]:
            best[t] = i
    ranked = sorted(best.values(), key=lambda i: -ste[i])[:20]

    lines = []
    lines.append(
        f"TRAIN <= {SPLIT}: {len(train)} firm-quarters, "
        f"{n_pos_tr} positives ({100 * n_pos_tr / len(train):.2f}%)"
    )
    lines.append(
        f"TEST  >  {SPLIT}: {len(test)} firm-quarters, "
        f"{n_pos_te} positives ({100 * n_pos_te / max(len(test), 1):.2f}%)"
    )
    br = n_pos_te / max(len(test), 1)
    ap_te = _auc_pr(ste, yte)
    lines.append(
        f"AUC-PR  train {_auc_pr(str_, ytr):.3f}   "
        f"test {ap_te:.3f}   (base rate {br:.4f}, "
        f"lift {ap_te / br if br else 0:.1f}x over random)"
    )
    lines.append(f"AUC-ROC train {_auc_roc(str_, ytr):.3f}   test {_auc_roc(ste, yte):.3f}")
    lines.append(
        f"precision@10 / @25, latest MATURE quarter ({last_q}): "
        f"{prec_at(10, idx_last, ste, yte):.2f} / "
        f"{prec_at(25, idx_last, ste, yte):.2f}"
    )
    lines.append("")
    lines.append("coefficients (standardized):")
    for (name, _), wj in sorted(zip(FEATURES, w), key=lambda t: -abs(t[1])):
        lines.append(f"  {name:<14} {wj:+.3f}")
    lines.append("")
    lines.append("top-20 test-period companies (best quarter each):")
    for i in ranked:
        r = test[i]
        hit = " <== ACQUIRED" if yte[i] else ""
        lines.append(
            f"  {ste[i]:.3f}  {r['Ticker'] or '':<6} {r['Company'][:40]:<42} {r['QuarterEnd']}{hit}"
        )

    report = "\n".join(lines)
    (config.GOLD / "fit_report.txt").write_text(report, encoding="utf-8")
    with (config.GOLD / "fit_scores.csv").open("w", newline="", encoding="utf-8") as f:
        wcsv = _csv.writer(f)
        wcsv.writerow(["Ticker", "Company", "QuarterEnd", "Score", "AcquiredNext12m"])
        for i, r in enumerate(test):
            wcsv.writerow([r["Ticker"], r["Company"], r["QuarterEnd"], f"{ste[i]:.4f}", yte[i]])
    return {"status": "ok", "message": report}


def _events_for_robust(strict: bool):
    """Target events (iid, announce) from ma_events.csv; strict keeps only
    machine-corroborated ones (EDGAR-strong, wiki, or dev-verified)."""
    import csv as _c

    ev = []
    with (config.SILVER / "ma_events.csv").open(encoding="utf-8") as f:
        for e in _c.DictReader(f):
            if e.get("Role") == "target" and e.get("AnnounceDate"):
                ev.append((str(e["FilerIID"]), e["AnnounceDate"], e.get("Verified", "")))
    if not strict:
        return [(i, d) for i, d, _ in ev]
    corro = {}
    upath = config.SILVER / "ma_events_universe.csv"
    if upath.exists():
        with upath.open(encoding="utf-8") as f:
            for h in _c.DictReader(f):
                corro[
                    (
                        str(h["CIK"]).lstrip("0"),
                        str(h.get("AgreementDate") or h["AnnounceDate"])[:4],
                    )
                ] = h.get("Corroboration") or ""
    cik_by_iid = {}
    with (config.SILVER / "companies.csv").open(encoding="utf-8") as f:
        for c in _c.DictReader(f):
            cik_by_iid[str(c["IID"])] = str(c.get("CIK", "")).lstrip("0")
    keep = []
    for iid, d, verified in ev:
        c = corro.get((cik_by_iid.get(iid, ""), d[:4]), "")
        if verified == "yes" or c.startswith(("strong", "wiki:page")):
            keep.append((iid, d))
    return keep


def _evaluate(feat_rows, events, split, feature_names, require_price=False):
    from datetime import date as _d
    from datetime import timedelta as _td

    tgt = {}
    for iid, d in events:
        if iid not in tgt or d < tgt[iid]:
            tgt[iid] = d
    fidx = [i for i, (n, _) in enumerate(FEATURES) if n in feature_names]
    X, y, meta = [], [], []
    for r in feat_rows:
        if (r.get("Currency") or "USD") != "USD":
            continue
        if _n(r.get("CashSTI")) is None and (_n(r.get("TrialsTotal")) or 0) <= 0:
            continue
        if require_price and not (r.get("PriceQ") or "").strip():
            continue
        iid, q = str(r["IID"]), r["QuarterEnd"]
        a = tgt.get(iid)
        if a and q >= a:
            continue  # censored at announcement
        h12 = (_d.fromisoformat(q) + _td(days=365)).isoformat()
        yy = 1 if (a and q < a <= h12) else 0
        X.append([FEATURES[i][1](r) for i in fidx])
        y.append(yy)
        meta.append((q,))
    tr = [i for i, m in enumerate(meta) if m[0] <= split]
    te = [i for i, m in enumerate(meta) if m[0] > split]
    Xtr, ytr = [X[i] for i in tr], [y[i] for i in tr]
    Xte, yte = [X[i] for i in te], [y[i] for i in te]
    if sum(ytr) < 10 or sum(yte) < 5:
        return {
            "n_tr": len(tr),
            "p_tr": sum(ytr),
            "n_te": len(te),
            "p_te": sum(yte),
            "insufficient": True,
        }
    Ztr, mu, sd = _standardize(Xtr)
    Zte, _, _ = _standardize(Xte, mu, sd)
    w, b = _fit_logistic(Ztr, ytr)
    try:
        import numpy as np

        ste = list(
            map(float, 1.0 / (1.0 + np.exp(-np.clip(np.asarray(Zte) @ np.asarray(w) + b, -35, 35))))
        )
    except ImportError:
        ste = [_sigmoid(b + sum(wj * xj for wj, xj in zip(w, z))) for z in Zte]
    br = sum(yte) / len(yte)
    ap = _auc_pr(ste, yte)
    from datetime import date as _d2
    from datetime import timedelta as _td2

    mature = (_d2.today() - _td2(days=365)).isoformat()
    mq = [meta[te[i]][0] for i in range(len(te)) if meta[te[i]][0] <= mature]
    lastq = max(mq) if mq else max(meta[te[i]][0] for i in range(len(te)))
    idx = [i for i in range(len(te)) if meta[te[i]][0] == lastq]
    top10 = sorted(idx, key=lambda i: -ste[i])[:10]
    return {
        "n_tr": len(tr),
        "p_tr": sum(ytr),
        "n_te": len(te),
        "p_te": sum(yte),
        "aucpr": ap,
        "lift": ap / br if br else 0,
        "roc": _auc_roc(ste, yte),
        "p10": sum(yte[i] for i in top10) / max(len(top10), 1),
        "lastq": lastq,
        "insufficient": False,
    }


def robust() -> dict:
    import csv as _c

    fpath = config.GOLD / "feature_panel.csv"
    if not fpath.exists():
        return {"status": "empty", "message": "Run features first."}
    with fpath.open(encoding="utf-8") as f:
        feat = list(_c.DictReader(f))
    allf = [n for n, _ in FEATURES]
    noprice = [n for n in allf if n not in ("logMarketCap", "Drawdown52w")]
    priceonly = ["logMarketCap", "Drawdown52w", "CAR12m", "Drift12m"]
    fundamentals = [n for n in allf if n not in priceonly]
    ev_all = _events_for_robust(strict=False)
    ev_strict = _events_for_robust(strict=True)
    scen = [
        ("baseline", ev_all, SPLIT, allf),
        ("strict-labels", ev_strict, SPLIT, allf),
        ("split-2019", ev_all, "2019-12-31", allf),
        ("split-2020", ev_all, "2020-12-31", allf),
        ("no-price", ev_all, SPLIT, noprice),
        ("price-only", ev_all, SPLIT, priceonly),
        ("covered-only", ev_all, SPLIT, allf),
        ("fundamentals", ev_all, SPLIT, fundamentals),
        ("fundamentals-strict", ev_strict, SPLIT, fundamentals),
    ]
    lines = [
        f"ROBUSTNESS SUITE  (events: {len(ev_all)} all, "
        f"{len(ev_strict)} machine-corroborated strict)",
        f"{'scenario':<15}{'train(+)':<14}{'test(+)':<13}"
        f"{'AUC-PR':<9}{'lift':<7}{'ROC':<7}{'P@10':<6}mature-q",
    ]
    # leakage diagnostic: does price MISSINGNESS correlate with the label?
    tgt = {}
    for iid, d in ev_all:
        if iid not in tgt or d < tgt[iid]:
            tgt[iid] = d
    from datetime import date as _dd
    from datetime import timedelta as _tt

    pos_cov = [0, 0]
    neg_cov = [0, 0]
    for r in feat:
        iid, q = str(r["IID"]), r["QuarterEnd"]
        a = tgt.get(iid)
        if a and q >= a:
            continue
        yy = 1 if (a and q < a <= (_dd.fromisoformat(q) + _tt(days=365)).isoformat()) else 0
        has = 1 if (r.get("PriceQ") or "").strip() else 0
        (pos_cov if yy else neg_cov)[has] += 1
    pc = pos_cov[1] / max(sum(pos_cov), 1)
    nc = neg_cov[1] / max(sum(neg_cov), 1)
    diag = (
        f"price coverage: positives {pc:.1%} ({sum(pos_cov)}) vs "
        f"negatives {nc:.1%} ({sum(neg_cov)}) -- "
        + ("MISSINGNESS-LEAK LIKELY" if abs(pc - nc) > 0.15 else "no material coverage gap")
    )
    lines.insert(1, diag)
    log.info(diag)

    for name, ev, split, feats in scen:
        r = _evaluate(feat, ev, split, feats, require_price=(name == "covered-only"))
        if r["insufficient"]:
            lines.append(
                f"{name:<15}{r['n_tr']}({r['p_tr']})  {r['n_te']}({r['p_te']})   INSUFFICIENT"
            )
            log.info(lines[-1])
            continue
        lines.append(
            f"{name:<15}{r['n_tr']}({r['p_tr']})".ljust(29)
            + f"{r['n_te']}({r['p_te']})".ljust(13)
            + f"{r['aucpr']:.3f}".ljust(9)
            + f"{r['lift']:.1f}x".ljust(7)
            + f"{r['roc']:.3f}".ljust(7)
            + f"{r['p10']:.2f}".ljust(6)
            + r["lastq"]
        )
        log.info(lines[-1])
    report = "\n".join(lines)
    (config.GOLD / "robustness_report.txt").write_text(report, encoding="utf-8")
    return {"status": "ok", "message": report}


TRAIN_END = "2019-12-31"
VAL_END = "2022-12-31"

V2_EXTRA = [
    ("dCash4q", lambda r: _n(r.get("dCash4q")) or 1.0),
    ("dShares4q", lambda r: min(_n(r.get("dShares4q")) or 1.0, 4.0)),
    ("RnDIntensity", lambda r: min(_n(r.get("RnDIntensity")) or 0.0, 2.0)),
    ("CashToAssets", lambda r: min(_n(r.get("CashToAssets")) or 0.0, 1.0)),
    ("AgeYears", lambda r: min(_n(r.get("AgeYears")) or 0.0, 40.0)),
    ("Ph3Started24m", lambda r: min(_n(r.get("Ph3Started24m")) or 0.0, 15.0)),
    ("FirstApprovalRecent24m", lambda r: _n(r.get("FirstApprovalRecent24m")) or 0.0),
    ("HotTA", lambda r: _n(r.get("HotTA")) or 0.0),
    ("FDAEventsEver", lambda r: min(_n(r.get("FDAEventsEver")) or 0.0, 60.0)),
]
PRICE_NAMES = ("logMarketCap", "Drawdown52w", "CAR12m", "Drift12m")


def _panel_xy(feat_rows, events, feats, lo, hi):
    from datetime import date as _d
    from datetime import timedelta as _td

    tgt = {}
    for iid, d in events:
        if iid not in tgt or d < tgt[iid]:
            tgt[iid] = d
    X, y = [], []
    for r in feat_rows:
        q = r["QuarterEnd"]
        if not (lo < q <= hi):
            continue
        if (r.get("Currency") or "USD") != "USD":
            continue
        if _n(r.get("CashSTI")) is None and (_n(r.get("TrialsTotal")) or 0) <= 0:
            continue
        a = tgt.get(str(r["IID"]))
        if a and q >= a:
            continue
        h12 = (_d.fromisoformat(q) + _td(days=365)).isoformat()
        y.append(1 if (a and q < a <= h12) else 0)
        X.append([f(r) for _, f in feats])
    return X, y


def improve() -> dict:
    """Iterate HERE: logistic vs gradient boosting on fundamentals-v2,
    scored on the VALIDATION window only. The 2023+ holdout is locked --
    `final` evaluates it exactly once, when iteration stops."""
    import csv as _c

    with (config.GOLD / "feature_panel.csv").open(encoding="utf-8") as f:
        feat = list(_c.DictReader(f))
    fund = [(n, f) for n, f in FEATURES if n not in PRICE_NAMES]
    fund_v2 = fund + V2_EXTRA
    ev = _events_for_robust(strict=False)

    Xtr, ytr = _panel_xy(feat, ev, fund_v2, "0000", TRAIN_END)
    Xva, yva = _panel_xy(feat, ev, fund_v2, TRAIN_END, VAL_END)
    if sum(ytr) < 10 or sum(yva) < 5:
        return {
            "status": "insufficient",
            "message": f"train +{sum(ytr)} / val +{sum(yva)}: rebuild features first.",
        }
    lines = [
        f"IMPROVE (validation window {TRAIN_END}..{VAL_END}; holdout 2023+ LOCKED)",
        f"train {len(Xtr)} (+{sum(ytr)})  val {len(Xva)} (+{sum(yva)})  "
        f"val base rate {sum(yva) / len(yva):.4f}",
    ]

    Ztr, mu, sd = _standardize(Xtr)
    Zva, _, _ = _standardize(Xva, mu, sd)
    w, b = _fit_logistic(Ztr, ytr)
    try:
        import numpy as np

        sva = list(
            map(float, 1.0 / (1.0 + np.exp(-np.clip(np.asarray(Zva) @ np.asarray(w) + b, -35, 35))))
        )
    except ImportError:
        sva = [_sigmoid(b + sum(wj * xj for wj, xj in zip(w, z))) for z in Zva]
    br = sum(yva) / len(yva)
    ap = _auc_pr(sva, yva)
    lines.append(
        f"logistic-v2     AUC-PR {ap:.3f}  lift {ap / br:.1f}x  ROC {_auc_roc(sva, yva):.3f}"
    )

    try:
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier

        gb = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.06, max_depth=4, class_weight="balanced", random_state=7
        )
        gb.fit(np.asarray(Xtr), np.asarray(ytr))
        sgb = list(map(float, gb.predict_proba(np.asarray(Xva))[:, 1]))
        apg = _auc_pr(sgb, yva)
        lines.append(
            f"gradboost-v2    AUC-PR {apg:.3f}  lift {apg / br:.1f}x  ROC {_auc_roc(sgb, yva):.3f}"
        )
    except ImportError:
        lines.append("gradboost-v2    (pip install scikit-learn to enable)")

    report = "\n".join(lines)
    (config.GOLD / "improve_report.txt").write_text(report, encoding="utf-8")
    return {"status": "ok", "message": report}
