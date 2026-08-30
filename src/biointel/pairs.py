"""Deal-level pair model (MASS-style), the literature's certified-best
formulation: M&A as link prediction between firm portfolios rather than
standalone target scoring.

Portfolios: each firm's trial CONDITIONS+INTERVENTIONS tokens as of a
date (StartDate <= cutoff), TF-IDF weighted -- idf supplies the
rare-technology emphasis the MASS paper found essential; the
large-acquires-small asymmetry enters through one-directional
eligibility (acquirer side = annualized revenue > $2B as of the date).

Outputs:
  `pairs`   -- field-protocol evaluation: for every verified event whose
               acquirer resolves into the universe, rank the TRUE target
               among all eligible targets by similarity at the quarter
               before announcement; report median rank, hit@10/@25, mAP.
               Writes gold/pair_report.txt.
  feature   -- per (firm, year-end) max similarity to any eligible
               acquirer, cached to gold/pair_feature.csv; engineer()
               folds it into the target model as _maxSimToAcq.
"""
from __future__ import annotations
import csv as _csv
import re
from collections import defaultdict
from datetime import date

from biointel import config

_STOP = {"the", "of", "and", "with", "for", "type", "study", "phase",
         "patients", "healthy", "adult", "treatment", "disease", "chronic",
         "severe", "moderate", "advanced", "placebo", "drug", "oral",
         "injection", "solution", "tablet", "dose", "mg"}


def _firm_docs(cutoff: str) -> dict[str, str]:
    docs = defaultdict(list)
    with (config.SILVER / "trials.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for t in _csv.DictReader(f):
            sd = (t.get("StartDate") or "")[:10]
            if not sd or sd > cutoff:
                continue
            blob = f"{t.get('Conditions','')} {t.get('Interventions','')} {t.get('Drugs','')}"
            toks = [w for w in re.sub(r"[^a-z0-9 ]", " ", blob.lower()).split()
                    if len(w) > 3 and w not in _STOP]
            docs[t["IID"]].extend(toks)
    return {iid: " ".join(ws) for iid, ws in docs.items() if len(ws) >= 8}


def _acquirer_side_iids(cutoff: str) -> set[str]:
    """Annualized revenue > $2B as of cutoff (feature-panel row lookup)."""
    out = set()
    with (config.GOLD / "feature_panel.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for r in _csv.DictReader(f):
            if r["QuarterEnd"] > cutoff or not r.get("Revenue"):
                continue
            try:
                rev = float(r["Revenue"])
            except ValueError:
                continue
            basis = r.get("TTMBasis") or ""
            mult = {"annualized-Q1": 4.0, "annualized-Q2": 2.0,
                    "annualized-Q3": 4 / 3}.get(basis, 1.0)
            if rev * mult > 2e9 and \
               (date.fromisoformat(cutoff)
                - date.fromisoformat(r["QuarterEnd"])).days <= 450:
                out.add(str(r["IID"]))
    return out


def _sim_matrix(docs: dict, a_ids: list, t_ids: list):
    from sklearn.feature_extraction.text import TfidfVectorizer
    ids = a_ids + t_ids
    vec = TfidfVectorizer(sublinear_tf=True, min_df=2)
    X = vec.fit_transform(docs[i] for i in ids)
    A = X[:len(a_ids)]
    T = X[len(a_ids):]
    return (A @ T.T)          # cosine: tfidf l2-normalized by default


def build_pair_feature() -> dict:
    """(firm, year-end) -> max similarity to any eligible acquirer;
    cached; consumed by improve.engineer as _maxSimToAcq."""
    import numpy as np
    out = config.GOLD / "pair_feature.csv"
    rows = []
    for y in range(2004, date.today().year + 1):
        cutoff = f"{y}-12-31"
        docs = _firm_docs(cutoff)
        acq = sorted(_acquirer_side_iids(cutoff) & docs.keys())
        tgt = sorted(set(docs) - set(acq))
        if not acq or not tgt:
            continue
        S = _sim_matrix(docs, acq, tgt)
        mx = np.asarray(S.max(axis=0).todense()).ravel()
        for tid, v in zip(tgt, mx):
            rows.append({"IID": tid, "YearEnd": cutoff,
                         "MaxSimToAcq": f"{float(v):.4f}"})
        print(f"  pair-feature {cutoff}: {len(tgt)} targets vs "
              f"{len(acq)} acquirers", flush=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["IID", "YearEnd", "MaxSimToAcq"])
        w.writeheader(); w.writerows(rows)
    return {"status": "ok",
            "message": f"{len(rows)} (firm, year) similarities -> {out}"}


# ---------------- MASS-inspired metric + field-protocol evaluation
def _tfidf_matrix(docs, ids, idf_power=1.0):
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np
    vec = TfidfVectorizer(sublinear_tf=True, min_df=2, norm=None)
    X = vec.fit_transform(docs[i] for i in ids)
    if idf_power != 1.0:
        # strengthen rare-term emphasis (MASS modification 2 spirit):
        # re-apply idf^(p-1) then l2-normalize
        extra = np.power(vec.idf_, idf_power - 1.0)
        X = X.multiply(extra)
    from sklearn.preprocessing import normalize
    return normalize(X)


def _size_factor(aid, tid, year, fp):
    """MASS modification 1 spirit: acquirers buy smaller firms; damp
    pairs where the target is not materially smaller."""
    import math
    ra = max((fp.get((aid, year)) or {}).get("rev") or 0.0, 0.0)
    rt = max((fp.get((tid, year)) or {}).get("rev") or 0.0, 0.0)
    if ra <= 0:
        return 1.0
    ratio = (rt + 1e6) / (ra + 1e6)
    return 1.0 / (1.0 + math.log1p(9 * min(ratio, 1.5)))


# --------------------------------------------------------------------------
# Substrate comparison (pre-registered, v0.69 decision): patents vs
# trials vs fused portfolio substrates under the identical field
# protocol. PAIRED DESIGN: at each event's cutoff the candidate pool is
# the intersection of firms with docs in ALL substrates; negatives are
# sampled once per (event, repeat) and reused across every substrate and
# metric, so the six reported lines differ only in the substrate/metric,
# never in events or samples.
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# MASS-EXACT (pre-registered): the paper's exact equations (Albora,
# Straccamore & Zaccaria, PLOS One 2026, Eqs 6-10) on the trials
# substrate, paired against the incumbent MASS-inspired engine.
#   Lam~_AT = sum_l M_Al M_Tl / v_l,  v_l = sqrt(sum_f M_fl^2)   (Eq 10)
#   B_sap via empirical maxima of Lam~ (Eqs 7-8, diagonal included:
#   in the binary limit the diagonal reproduces the degree k)
#   MASS = (||M_A|| / ||M_T||) * B_sap                            (Eq 9)
# ADOPTION RULE (recorded before results): MASS-exact ships only if its
# HR@5 beats MASS-inspired by more than 2x the pooled repeat std on
# shared events and samples; otherwise the incumbent stands.
# --------------------------------------------------------------------------
def _count_matrix(docs: dict, ids: list):
    from sklearn.feature_extraction.text import CountVectorizer
    vec = CountVectorizer(min_df=2)
    M = vec.fit_transform(docs[i] for i in ids).astype(float)
    return M


def _mass_exact_scores(M, lam, row_norms, a_idx, cand_idx):
    """Eq 7-9 for one acquirer row against candidate rows.
    lam: dense ndarray of Lam~ (n x n); row_norms: ||M_f|| of raw M."""
    import numpy as np
    eps = 1e-12
    mN = lam.max()
    rowA = lam[a_idx]
    mA = rowA.max()
    out = np.empty(len(cand_idx))
    for j, c in enumerate(cand_idx):
        lamAT = lam[a_idx, c]
        mT = lam[:, c].max()
        denom = mA * (1.0 - mA / max(mN, eps))
        if denom <= eps or (mN - mT) <= eps:
            b = 0.0
        else:
            f = (lamAT * (1.0 - lamAT / max(mT, eps))
                 + (mA - lamAT)
                 * (1.0 - (mA - lamAT) / (mN - mT))) / denom
            cond = lamAT * mN / max(mA * mT, eps) >= 1.0
            b = (1.0 - f) if cond else (-1.0 + f)
        out[j] = (row_norms[a_idx] / max(row_norms[c], eps)) * b
    return out


def pairs_exact(negatives: int = 200, repeats: int = 20,
                seed: int = 7) -> dict:
    import numpy as np
    import random as _r
    import statistics
    from biointel import network
    fp = {}
    with (config.GOLD / "feature_panel.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for r in _csv.DictReader(f):
            if r["QuarterEnd"].endswith("-12-31") and r.get("Revenue"):
                basis = r.get("TTMBasis") or ""
                mult = {"annualized-Q1": 4.0, "annualized-Q2": 2.0,
                        "annualized-Q3": 4 / 3}.get(basis, 1.0)
                try:
                    fp[(str(r["IID"]), r["QuarterEnd"][:4])] = {
                        "rev": float(r["Revenue"]) * mult}
                except ValueError:
                    pass
    name_to_iid = {}
    with (config.SILVER / "companies.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for c in _csv.DictReader(f):
            name_to_iid[network._norm(c.get("Name", ""))] = str(c["IID"])
    events = []
    with (config.SILVER / "ma_events.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for e in _csv.DictReader(f):
            if e.get("Role") != "target" or not e.get("AnnounceDate"):
                continue
            acq = network._norm(e.get("VerifiedAcquirer")
                                or e.get("Counterparty") or "")
            aid = name_to_iid.get(acq) or next(
                (v for k, v in name_to_iid.items()
                 if k and acq and (k.startswith(acq + " ")
                                   or acq.startswith(k + " "))), None)
            if aid:
                events.append((aid, str(e["FilerIID"]), e["AnnounceDate"]))

    cache = {}

    def get(cutoff):
        if cutoff in cache:
            return cache[cutoff]
        docs = _firm_docs(cutoff)
        ids = sorted(docs)
        pos = {i: k for k, i in enumerate(ids)}
        acq_side = _acquirer_side_iids(cutoff)
        Xt = _tfidf_matrix(docs, ids, idf_power=2.0)      # incumbent
        M = _count_matrix(docs, ids)                      # exact-path raw
        v = np.sqrt(np.asarray(M.power(2).sum(axis=0)).ravel())
        v[v <= 0] = 1.0
        Xw = M.multiply(1.0 / np.sqrt(v))
        lam = np.asarray((Xw @ Xw.T).todense())
        row_norms = np.sqrt(np.asarray(M.power(2).sum(axis=1)).ravel())
        cache[cutoff] = (ids, pos, acq_side, Xt, lam, row_norms, M)
        return cache[cutoff]

    ev = []
    for aid, tid, ann in events:
        cutoff = f"{int(ann[:4])-1}-12-31"
        ids, pos, acq_side, *_ = get(cutoff)
        if aid in pos and tid in pos and \
           len([i for i in ids if i not in acq_side
                and i not in (aid, tid)]) >= negatives:
            ev.append((aid, tid, ann, cutoff))
    if not ev:
        return {"status": "empty", "message": "No evaluable events."}

    scores = {m: ([], []) for m in ("MASS-inspired", "MASS-exact")}
    for rep in range(repeats):
        _r.seed(seed + rep)
        hits = {m: [0, 0, 0] for m in scores}
        for aid, tid, ann, cutoff in ev:
            ids, pos, acq_side, Xt, lam, row_norms, M = get(cutoff)
            cands = [i for i in ids if i not in acq_side
                     and i not in (aid, tid)]
            sample = _r.sample(cands, negatives) + [tid]
            rows = [pos[c] for c in sample]
            y = ann[:4]
            size = np.array([_size_factor(aid, c, y, fp) for c in sample])
            sims_i = np.asarray((Xt[pos[aid]] @ Xt[rows].T)
                                .todense()).ravel() * size
            sims_e = _mass_exact_scores(M, lam, row_norms, pos[aid], rows)
            for m, sims in (("MASS-inspired", sims_i),
                            ("MASS-exact", sims_e)):
                t = sims[-1]
                # midpoint tie rank: an all-tied row scores mid-pool,
                # never a free rank 1 (guards the degenerate-acquirer
                # case of the exact formula)
                rank = float((sims > t).sum()) +                        (float((sims == t).sum()) + 1.0) / 2.0
                h = hits[m]
                h[2] += 1
                h[0] += rank <= 5
                h[1] += rank <= 10
        for m, (h5, h10, n) in hits.items():
            if n:
                scores[m][0].append(h5 / n)
                scores[m][1].append(h10 / n)

    lines = ["MASS-EXACT vs INCUMBENT (paired: %d events, %d negatives, "
             "%d repeats, shared samples)" % (len(ev), negatives, repeats)]
    for m in ("MASS-inspired", "MASS-exact"):
        h5s, h10s = scores[m]
        lines.append("%-14s HR@5 %.3f (+/-%.3f)   HR@10 %.3f"
                     % (m, statistics.mean(h5s), statistics.pstdev(h5s),
                        statistics.mean(h10s)))
    msg = "\n".join(lines)
    print(msg, flush=True)
    (config.GOLD / "pair_exact_report.txt").write_text(msg,
                                                       encoding="utf-8")
    return {"status": "ok", "message": msg}


# --------------------------------------------------------------------------
# MASS-exact as the SHIPPED ENGINE (adopted v0.81 by the pre-registered
# rule: 0.318 vs 0.222 HR@5 paired). Helpers for predict() and the
# full-universe re-rank. The _maxSimToAcq screen feature is NOT
# regenerated: the target-screen holdouts are spent and stay frozen.
# --------------------------------------------------------------------------
def exact_state(cutoff: str):
    """(ids, pos, lam, row_norms) for MASS-exact at a cutoff."""
    import numpy as np
    docs = _firm_docs(cutoff)
    ids = sorted(docs)
    if len(ids) < 3:
        return ids, {}, None, None
    M = _count_matrix(docs, ids)
    v = np.sqrt(np.asarray(M.power(2).sum(axis=0)).ravel())
    v[v <= 0] = 1.0
    Xw = M.multiply(1.0 / np.sqrt(v))
    lam = np.asarray((Xw @ Xw.T).todense())
    row_norms = np.sqrt(np.asarray(M.power(2).sum(axis=1)).ravel())
    return ids, {i: k for k, i in enumerate(ids)}, lam, row_norms


def exact_score(lam, row_norms, a_idx, cand_idx):
    return _mass_exact_scores(None, lam, row_norms, a_idx, cand_idx)


def pairs_full_exact() -> dict:
    """Full-universe re-rank with the adopted engine: for every resolved
    event, the true target's rank among ALL eligible targets by
    MASS-exact at the year-end before announcement."""
    import numpy as np
    from biointel import network
    name_to_iid = {}
    with (config.SILVER / "companies.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for c in _csv.DictReader(f):
            name_to_iid[network._norm(c.get("Name", ""))] = str(c["IID"])
    events = []
    with (config.SILVER / "ma_events.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for e in _csv.DictReader(f):
            if e.get("Role") != "target" or not e.get("AnnounceDate"):
                continue
            acq = network._norm(e.get("VerifiedAcquirer")
                                or e.get("Counterparty") or "")
            aid = name_to_iid.get(acq) or next(
                (v for k, v in name_to_iid.items()
                 if k and acq and (k.startswith(acq + " ")
                                   or acq.startswith(k + " "))), None)
            if aid:
                events.append((aid, str(e["FilerIID"]), e["AnnounceDate"]))
    cache = {}
    ranks, pool_sizes = [], []
    for aid, tid, ann in events:
        cutoff = f"{int(ann[:4])-1}-12-31"
        if cutoff not in cache:
            ids, pos, lam, norms = exact_state(cutoff)
            cache[cutoff] = (ids, pos, lam, norms,
                             _acquirer_side_iids(cutoff))
        ids, pos, lam, norms, acq_side = cache[cutoff]
        if aid not in pos or tid not in pos or lam is None:
            continue
        cands = [i for i in ids if i not in acq_side and i != aid]
        if tid not in cands or len(cands) < 20:
            continue
        rows = [pos[c] for c in cands]
        sims = exact_score(lam, norms, pos[aid], rows)
        t_j = cands.index(tid)
        tv = sims[t_j]
        rank = int((sims > tv).sum() + ((sims == tv).sum() + 1) // 2)
        ranks.append(max(rank, 1))
        pool_sizes.append(len(cands))
    if not ranks:
        return {"status": "empty", "message": "No rankable events."}
    import statistics
    r = sorted(ranks)
    msg = ("FULL-UNIVERSE RE-RANK (MASS-exact engine): %d events; "
           "median true-target rank %d / median pool %d; hit@10 %.2f; "
           "hit@25 %.2f"
           % (len(r), r[len(r) // 2], sorted(pool_sizes)[len(r) // 2],
              sum(1 for x in r if x <= 10) / len(r),
              sum(1 for x in r if x <= 25) / len(r)))
    print(msg, flush=True)
    (config.GOLD / "pair_full_exact_report.txt").write_text(
        msg, encoding="utf-8")
    return {"status": "ok", "message": msg}
