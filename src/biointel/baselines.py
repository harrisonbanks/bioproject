# src/biointel/baselines.py
"""LEGACY (P7 amendment 2026-08-30). Rejected pairing engines, retained as the
paper's measured baselines. Not re-pointed to the DuckDB store or the reporting
layer, never re-run; kept only to diagnose a mismatch against the fingerprinted
baseline reports; removed at the cleanup gate. Its own reads use the frozen CSV
folders (config.SILVER / config.GOLD); the helpers it imports from pairs.py
(_firm_docs, _acquirer_side_iids) are live code and read the database.

Moved verbatim from pairs.py in refactor step 1. None of these is on
the shipped path: `predict` uses the MASS-exact engine in pairs.py.
Ledger (PROJECT_STATUS 0.5 / v0.67 / v0.75 / v0.79):
  evaluate_pairs    cosine similarity, HR@5 0.216
  supervised_pairs  ranker, top-10 wash, median worse
  pairs_protocol    cosine / MASS-inspired 0.222 / latent-SVD 0.143 / hybrid
  pairs_substrates  paired trials vs patents (0.055) vs targets (0.120): nulls
"""

from __future__ import annotations

import csv as _csv
import logging
import re
from collections import defaultdict
from datetime import date, timedelta

from biointel import config
from biointel.pairs import _acquirer_side_iids, _firm_docs, _sim_matrix, _size_factor, _tfidf_matrix

log = logging.getLogger(__name__)


def evaluate_pairs() -> dict:
    import numpy as np

    # verified events with acquirer resolvable to a universe IID
    events = []
    name_to_iid = {}
    from biointel import network

    with (config.SILVER / "companies.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for c in _csv.DictReader(f):
            name_to_iid[network._norm(c.get("Name", ""))] = str(c["IID"])
    with (config.SILVER / "ma_events.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for e in _csv.DictReader(f):
            if e.get("Role") != "target" or not e.get("AnnounceDate"):
                continue
            acq = network._norm(e.get("VerifiedAcquirer") or e.get("Counterparty") or "")
            aid = name_to_iid.get(acq)
            if not aid:
                aid = next(
                    (
                        v
                        for k, v in name_to_iid.items()
                        if k and acq and (k.startswith(acq + " ") or acq.startswith(k + " "))
                    ),
                    None,
                )
            if aid:
                events.append((aid, str(e["FilerIID"]), e["AnnounceDate"]))

    if not events:
        return {"status": "empty", "message": "No resolvable pairs."}

    ranks, hits10, hits25, aps = [], 0, 0, []
    by_cut = defaultdict(list)
    for aid, tid, ann in events:
        q = (
            date.fromisoformat(ann).replace(day=1) - timedelta(days=1)
        ).isoformat()  # month-end before announce
        by_cut[q[:4] + "-12-31" if False else q].append((aid, tid))
    n_eval = 0
    for cutoff, evs in sorted(by_cut.items()):
        docs = _firm_docs(cutoff)
        acq_side = _acquirer_side_iids(cutoff)
        t_ids = [i for i in docs if i not in acq_side]
        for aid, tid in evs:
            if aid not in docs or tid not in [*t_ids]:
                continue
            a_docs = {**docs}
            S = _sim_matrix(a_docs, [aid], t_ids)
            row = np.asarray(S.todense()).ravel()
            order = row.argsort()[::-1]
            pos = {t_ids[i]: r for r, i in enumerate(order, 1)}.get(tid)
            if pos is None:
                continue
            n_eval += 1
            ranks.append(pos)
            hits10 += pos <= 10
            hits25 += pos <= 25
            aps.append(1.0 / pos)
    if not ranks:
        return {"status": "empty", "message": "No evaluable events."}
    import statistics

    msg = (
        f"PAIR MODEL (MASS-style similarity), {n_eval} events "
        f"evaluated, universe-wide candidate sets\n"
        f"  median rank of true target: {statistics.median(ranks):.0f} "
        f"of ~{max(ranks)}\n"
        f"  hit@10 {hits10 / n_eval:.2f}   hit@25 {hits25 / n_eval:.2f}   "
        f"MRR {sum(aps) / n_eval:.3f}"
    )
    (config.GOLD / "pair_report.txt").write_text(msg, encoding="utf-8")
    return {"status": "ok", "message": msg}


def _pair_features(aid, tid, cutoff, sim, ctx):
    fp, rel, appetite, cat = ctx["fp"], ctx["rel"], ctx["appetite"], ctx["cat"]
    fa = fp.get((aid, cutoff[:4])) or {}
    ft = fp.get((tid, cutoff[:4])) or {}
    import math

    ra = max(fa.get("rev") or 0.0, 0.0)
    ca_ = max(ft.get("cash") or 0.0, 0.0)
    return [
        sim,
        math.log1p(ra),
        math.log1p(ca_),
        math.log1p(ra) - math.log1p(max(ft.get("rev") or 0.0, 0.0)),
        1.0 if (aid, tid) in rel or (tid, aid) in rel else 0.0,
        float(appetite.get(aid, {}).get(cutoff[:4], 0)),
        float(cat.get(tid, {}).get(cutoff[:4], 0)),
        float(ft.get("ph3") or 0.0),
    ]


def supervised_pairs() -> dict:
    """Train/test the supervised ranker; report test hit@k on FULL
    candidate sets (not sampled) for events announced 2020+."""
    import random as _r

    from sklearn.ensemble import HistGradientBoostingClassifier

    from biointel import network

    _r.seed(11)

    # ---- context tables from existing silver/gold ----
    fp = {}
    with (config.GOLD / "feature_panel.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for r in _csv.DictReader(f):
            if not r["QuarterEnd"].endswith("-12-31"):
                continue
            rev = r.get("Revenue")
            basis = r.get("TTMBasis") or ""
            mult = {"annualized-Q1": 4.0, "annualized-Q2": 2.0, "annualized-Q3": 4 / 3}.get(
                basis, 1.0
            )
            fp[(str(r["IID"]), r["QuarterEnd"][:4])] = {
                "rev": float(rev) * mult if rev else 0.0,
                "cash": float(r["CashSTI"]) if r.get("CashSTI") else 0.0,
                "ph3": float(r["TrialsPh3"]) if r.get("TrialsPh3") else 0.0,
            }
    rel = set()
    with config.RELATIONSHIPS_CSV.open(encoding="utf-8", newline="", errors="replace") as f:
        for r in _csv.DictReader(f):
            if r.get("PartnerIID"):
                rel.add((str(r["IID"]), str(r["PartnerIID"])))
    name_to_iid = {}
    with (config.SILVER / "companies.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for c in _csv.DictReader(f):
            name_to_iid[network._norm(c.get("Name", ""))] = str(c["IID"])
    events = []
    with (config.SILVER / "ma_events.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for e in _csv.DictReader(f):
            if e.get("Role") != "target" or not e.get("AnnounceDate"):
                continue
            acq = network._norm(e.get("VerifiedAcquirer") or e.get("Counterparty") or "")
            aid = name_to_iid.get(acq) or next(
                (
                    v
                    for k, v in name_to_iid.items()
                    if k and acq and (k.startswith(acq + " ") or acq.startswith(k + " "))
                ),
                None,
            )
            if aid:
                events.append((aid, str(e["FilerIID"]), e["AnnounceDate"]))
    appetite = defaultdict(lambda: defaultdict(int))
    for aid, tid, ann in events:
        for yr in range(int(ann[:4]) + 1, int(ann[:4]) + 4):
            appetite[aid][str(yr)] += 1  # trailing 3y acquisitions
    cat = defaultdict(lambda: defaultdict(int))
    with (config.SILVER / "trials.csv").open(encoding="utf-8", newline="", errors="replace") as f:
        for t in _csv.DictReader(f):
            d = (t.get("PrimaryCompletion") or "")[:4]
            if d and t.get("Status") == "COMPLETED" and "PHASE3" in (t.get("Phase") or ""):
                cat[t["IID"]][d] += 1
    ctx = {"fp": fp, "rel": rel, "appetite": appetite, "cat": cat}

    # ---- similarity matrices per cutoff year (reuse portfolio builder) --
    log.info("  building similarity by year...")
    sim_by_year = {}
    docs_by_year = {}
    years = sorted({e[2][:4] for e in events})
    for y in years:
        cutoff = f"{int(y) - 1}-12-31"
        docs_by_year[y] = _firm_docs(cutoff)

    def sim_lookup(y, aid, tid):
        docs = docs_by_year[y]
        if aid not in docs or tid not in docs:
            return 0.0
        key = y
        if key not in sim_by_year:
            ids = sorted(docs)
            from sklearn.feature_extraction.text import TfidfVectorizer

            vec = TfidfVectorizer(sublinear_tf=True, min_df=2)
            X = vec.fit_transform(docs[i] for i in ids)
            sim_by_year[key] = ({i: n for n, i in enumerate(ids)}, X)
        pos, X = sim_by_year[key]
        return float((X[pos[aid]] @ X[pos[tid]].T).toarray()[0, 0])

    # ---- training set: true pairs + 40 sampled negatives each ----
    all_iids = sorted({i for (i, y) in fp})
    Xtr, ytr, Xte_events = [], [], []
    for aid, tid, ann in events:
        y = ann[:4]
        cutoff = f"{int(y) - 1}-12-31"
        row = _pair_features(aid, tid, cutoff, sim_lookup(y, aid, tid), ctx)
        if ann < "2020-01-01":
            Xtr.append(row)
            ytr.append(1)
            for _ in range(40):
                nid = _r.choice(all_iids)
                if nid == tid or nid == aid:
                    continue
                Xtr.append(_pair_features(aid, nid, cutoff, sim_lookup(y, aid, nid), ctx))
                ytr.append(0)
        else:
            Xte_events.append((aid, tid, y, cutoff))
    if sum(ytr) < 20 or not Xte_events:
        return {
            "status": "insufficient",
            "message": f"train positives {sum(ytr)}, test events {len(Xte_events)}",
        }
    m = HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.06,
        max_iter=300,
        class_weight="balanced",
        min_samples_leaf=25,
        random_state=7,
    )
    m.fit(Xtr, ytr)

    # ---- test: FULL candidate re-ranking per 2020+ event ----
    ranks, h10, h25 = [], 0, 0
    for aid, tid, y, cutoff in Xte_events:
        docs = docs_by_year[y]
        acq_side = _acquirer_side_iids(cutoff)
        cands = [i for i in docs if i not in acq_side and i != aid]
        if tid not in cands:
            continue
        F = [_pair_features(aid, c, cutoff, sim_lookup(y, aid, c), ctx) for c in cands]
        p = m.predict_proba(F)[:, 1]
        order = sorted(range(len(cands)), key=lambda i: -p[i])
        pos = next(r for r, i in enumerate(order, 1) if cands[i] == tid)
        ranks.append(pos)
        h10 += pos <= 10
        h25 += pos <= 25
        log.info(f"    {y} event: true target rank {pos}/{len(cands)}")
    import statistics

    n = len(ranks)
    msg = (
        "SUPERVISED PAIR RANKER  train<2020 (%d pos), "
        "test 2020+ (%d events, full candidate sets)\n"
        "  median rank %.0f   hit@10 %.2f   hit@25 %.2f\n"
        "  (unsupervised baseline: hit@10 0.17, median 139)"
        % (sum(ytr), n, statistics.median(ranks), h10 / n, h25 / n)
    )
    (config.GOLD / "pair_supervised_report.txt").write_text(msg, encoding="utf-8")
    return {"status": "ok", "message": msg}


def pairs_protocol(
    mass: bool = True, negatives: int = 200, repeats: int = 20, seed: int = 7
) -> dict:
    """Field-protocol evaluation (true target vs N sampled negatives,
    HR@5/HR@10, averaged over repeats) for cosine and the MASS-inspired
    variant, on the same events as `pairs`."""
    import random as _r

    import numpy as np

    from biointel import network

    fp = {}
    with (config.GOLD / "feature_panel.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for r in _csv.DictReader(f):
            if r["QuarterEnd"].endswith("-12-31") and r.get("Revenue"):
                basis = r.get("TTMBasis") or ""
                mult = {"annualized-Q1": 4.0, "annualized-Q2": 2.0, "annualized-Q3": 4 / 3}.get(
                    basis, 1.0
                )
                try:
                    fp[(str(r["IID"]), r["QuarterEnd"][:4])] = {"rev": float(r["Revenue"]) * mult}
                except ValueError:
                    pass
    name_to_iid = {}
    with (config.SILVER / "companies.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for c in _csv.DictReader(f):
            name_to_iid[network._norm(c.get("Name", ""))] = str(c["IID"])
    events = []
    with (config.SILVER / "ma_events.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for e in _csv.DictReader(f):
            if e.get("Role") != "target" or not e.get("AnnounceDate"):
                continue
            acq = network._norm(e.get("VerifiedAcquirer") or e.get("Counterparty") or "")
            aid = name_to_iid.get(acq) or next(
                (
                    v
                    for k, v in name_to_iid.items()
                    if k and acq and (k.startswith(acq + " ") or acq.startswith(k + " "))
                ),
                None,
            )
            if aid:
                events.append((aid, str(e["FilerIID"]), e["AnnounceDate"]))
    # partner sets for the latent feature block
    partners = defaultdict(set)
    with config.RELATIONSHIPS_CSV.open(encoding="utf-8", newline="", errors="replace") as f:
        for r in _csv.DictReader(f):
            if r.get("Partner"):
                partners[str(r["IID"])].add(r["Partner"][:40].lower())

    def latent_matrix(docs, ids):
        import scipy.sparse as sp
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize

        vec = TfidfVectorizer(sublinear_tf=True, min_df=2)
        Xt = vec.fit_transform(docs[i] for i in ids)
        pvoc = sorted({p for i in ids for p in partners.get(i, ())})
        pidx = {p: j for j, p in enumerate(pvoc)}
        rowsL, colsL = [], []
        for k, i in enumerate(ids):
            for p in partners.get(i, ()):
                rowsL.append(k)
                colsL.append(pidx[p])
        P = sp.csr_matrix(([1.0] * len(rowsL), (rowsL, colsL)), shape=(len(ids), max(len(pvoc), 1)))
        X = sp.hstack([Xt, P * 2.0]).tocsr()
        k = min(64, X.shape[1] - 1, X.shape[0] - 1)
        Z = TruncatedSVD(n_components=max(k, 2), random_state=7).fit_transform(X)
        return normalize(Z)

    out_lines = []
    per_event_ranks = {}
    for label, idfp, use_size in (
        ("cosine", 1.0, False),
        ("MASS-inspired", 2.0, True),
        ("latent-SVD", None, False),
    ):
        hr5s, hr10s = [], []
        for rep in range(repeats):
            _r.seed(seed + rep)
            h5 = h10 = n = 0
            cache = {}
            for aid, tid, ann in events:
                y = ann[:4]
                cutoff = f"{int(y) - 1}-12-31"
                if cutoff not in cache:
                    docs = _firm_docs(cutoff)
                    acq_side = _acquirer_side_iids(cutoff)
                    ids = sorted(docs)
                    X = (
                        latent_matrix(docs, ids)
                        if idfp is None
                        else _tfidf_matrix(docs, ids, idf_power=idfp)
                    )
                    cache[cutoff] = (docs, acq_side, ids, {i: k for k, i in enumerate(ids)}, X)
                docs, acq_side, ids, pos, X = cache[cutoff]
                if aid not in pos or tid not in pos:
                    continue
                cands = [i for i in ids if i not in acq_side and i not in (aid, tid)]
                if len(cands) < negatives:
                    continue
                sample = _r.sample(cands, negatives) + [tid]
                sub = X[[pos[c] for c in sample]]
                if idfp is None:
                    sims = (sub @ X[pos[aid]]).ravel()
                else:
                    sims = np.asarray((X[pos[aid]] @ sub.T).todense()).ravel()
                if use_size:
                    sims = sims * np.array([_size_factor(aid, c, y, fp) for c in sample])
                rank = int((sims > sims[-1]).sum()) + 1
                if rep == 0:
                    per_event_ranks.setdefault(label, {})[(aid, tid, ann)] = (
                        sims.argsort()[::-1],
                        sample,
                    )
                n += 1
                h5 += rank <= 5
                h10 += rank <= 10
            if n:
                hr5s.append(h5 / n)
                hr10s.append(h10 / n)
        if hr5s:
            import statistics

            out_lines.append(
                "%-14s HR@5 %.3f (+/-%.3f)   HR@10 %.3f   (%d events, "
                "%d negatives, %d repeats)"
                % (
                    label,
                    statistics.mean(hr5s),
                    statistics.pstdev(hr5s),
                    statistics.mean(hr10s),
                    n,
                    negatives,
                    repeats,
                )
            )
            log.info(out_lines[-1])
    # hybrid: per-event rank-mean of MASS-inspired and latent (rep 0)
    a = per_event_ranks.get("MASS-inspired", {})
    b = per_event_ranks.get("latent-SVD", {})
    common = set(a) & set(b)
    if common:
        h5 = h10 = 0
        for key in common:
            oa, sa = a[key]
            ob, sb = b[key]
            ra = {sa[i]: r for r, i in enumerate(oa, 1)}
            rb = {sb[i]: r for r, i in enumerate(ob, 1)}
            tid = key[1]
            fused = {c: ra.get(c, 999) + rb.get(c, 999) for c in set(ra) | set(rb)}
            rank = 1 + sum(1 for c, v in fused.items() if c != tid and v < fused.get(tid, 9999))
            h5 += rank <= 5
            h10 += rank <= 10
        out_lines.append(
            "%-14s HR@5 %.3f            HR@10 %.3f   "
            "(%d events, rank-fusion, single draw)"
            % ("hybrid", h5 / len(common), h10 / len(common), len(common))
        )
        log.info(out_lines[-1])
    msg = "FIELD-PROTOCOL PAIR EVALUATION\n" + "\n".join(out_lines)
    (config.GOLD / "pair_protocol_report.txt").write_text(msg, encoding="utf-8")
    return {"status": "ok" if out_lines else "empty", "message": msg}


def _patent_docs(cutoff: str) -> dict[str, str]:
    """Firm doc = CPC subclasses of patents granted on or before cutoff,
    one token per patent-subclass row (frequency carries weight)."""
    docs = defaultdict(list)
    path = config.SILVER / "patents.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="", errors="replace") as f:
        for r in _csv.DictReader(f):
            d = (r.get("PatentDate") or "")[:10]
            if not d or d > cutoff:
                continue
            if r.get("CPCSubclass"):
                docs[str(r["IID"])].append(r["CPCSubclass"].lower())
    return {iid: " ".join(ws) for iid, ws in docs.items() if len(ws) >= 3}


def _target_docs(cutoff: str) -> dict[str, str]:
    """Firm doc = molecular targets of drugs first seen on or before
    cutoff (silver/drug_targets.csv from the ChEMBL layer). Multi-word
    target names become single atomic tokens via underscores."""
    docs = defaultdict(list)
    path = config.SILVER / "drug_targets.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="", errors="replace") as f:
        for r in _csv.DictReader(f):
            fs = (r.get("FirstSeen") or "")[:10]
            if fs and fs > cutoff:
                continue
            if r.get("TargetName"):
                docs[str(r["IID"])].append(
                    re.sub(r"[^a-z0-9]+", "_", r["TargetName"].lower()).strip("_")
                )
    return {iid: " ".join(ws) for iid, ws in docs.items() if len(ws) >= 2}


def pairs_substrates(
    negatives: int = 200, repeats: int = 20, seed: int = 7, mode: str = "patents"
) -> dict:
    import random as _r
    import statistics

    import numpy as np

    from biointel import network

    fp = {}
    with (config.GOLD / "feature_panel.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for r in _csv.DictReader(f):
            if r["QuarterEnd"].endswith("-12-31") and r.get("Revenue"):
                basis = r.get("TTMBasis") or ""
                mult = {"annualized-Q1": 4.0, "annualized-Q2": 2.0, "annualized-Q3": 4 / 3}.get(
                    basis, 1.0
                )
                try:
                    fp[(str(r["IID"]), r["QuarterEnd"][:4])] = {"rev": float(r["Revenue"]) * mult}
                except ValueError:
                    pass
    name_to_iid = {}
    with (config.SILVER / "companies.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for c in _csv.DictReader(f):
            name_to_iid[network._norm(c.get("Name", ""))] = str(c["IID"])
    events = []
    with (config.SILVER / "ma_events.csv").open(
        encoding="utf-8", newline="", errors="replace"
    ) as f:
        for e in _csv.DictReader(f):
            if e.get("Role") != "target" or not e.get("AnnounceDate"):
                continue
            acq = network._norm(e.get("VerifiedAcquirer") or e.get("Counterparty") or "")
            aid = name_to_iid.get(acq) or next(
                (
                    v
                    for k, v in name_to_iid.items()
                    if k and acq and (k.startswith(acq + " ") or acq.startswith(k + " "))
                ),
                None,
            )
            if aid:
                events.append((aid, str(e["FilerIID"]), e["AnnounceDate"]))

    alt = "targets" if mode == "targets" else "patents"
    alt_fn = _target_docs if mode == "targets" else _patent_docs
    SUBSTRATES = ("trials", alt, "fused")

    def build_docs(sub, cutoff):
        if sub == "trials":
            return _firm_docs(cutoff)
        if sub == alt:
            return alt_fn(cutoff)
        t, p = _firm_docs(cutoff), alt_fn(cutoff)
        return {i: (t.get(i, "") + " " + p.get(i, "")).strip() for i in set(t) | set(p)}

    # per-cutoff cache: common ids, per-substrate matrices, acquirer side
    cache = {}
    solo_cover = {s: 0 for s in SUBSTRATES}

    def get(cutoff):
        if cutoff in cache:
            return cache[cutoff]
        d = {s: build_docs(s, cutoff) for s in SUBSTRATES}
        common = sorted(set(d["trials"]) & set(d[alt]))
        acq_side = _acquirer_side_iids(cutoff)
        mats = {}
        for s in SUBSTRATES:
            ids = common
            for label, idfp in (("cosine", 1.0), ("MASS-inspired", 2.0)):
                if len(ids) >= 3:
                    mats[(s, label)] = _tfidf_matrix(
                        {i: d[s][i] if s != "fused" else d["fused"][i] for i in ids},
                        ids,
                        idf_power=idfp,
                    )
        entry = (d, common, {i: k for k, i in enumerate(common)}, acq_side, mats)
        cache[cutoff] = entry
        return entry

    # fixed evaluable event set: aid+tid in the COMMON pool at cutoff
    ev = []
    for aid, tid, ann in events:
        cutoff = f"{int(ann[:4]) - 1}-12-31"
        d, common, pos, acq_side, mats = get(cutoff)
        for s in SUBSTRATES:
            if aid in d[s] and tid in d[s]:
                solo_cover[s] += 1
        if (
            aid in pos
            and tid in pos
            and len([i for i in common if i not in acq_side and i not in (aid, tid)]) >= negatives
        ):
            ev.append((aid, tid, ann, cutoff))
    if not ev:
        return {
            "status": "empty",
            "message": "No events evaluable on the common substrate "
            "pool (is silver/patents.csv present?).",
        }

    scores = {(s, m): ([], []) for s in SUBSTRATES for m in ("cosine", "MASS-inspired")}
    for rep in range(repeats):
        _r.seed(seed + rep)
        hits = {k: [0, 0, 0] for k in scores}  # h5, h10, n
        for aid, tid, ann, cutoff in ev:
            d, common, pos, acq_side, mats = get(cutoff)
            cands = [i for i in common if i not in acq_side and i not in (aid, tid)]
            sample = _r.sample(cands, negatives) + [tid]
            rows = [pos[c] for c in sample]
            for (s, label), X in mats.items():
                sims = np.asarray((X[pos[aid]] @ X[rows].T).todense()).ravel()
                if label == "MASS-inspired":
                    y = ann[:4]
                    sims = sims * np.array([_size_factor(aid, c, y, fp) for c in sample])
                rank = int((sims > sims[-1]).sum()) + 1
                h = hits[(s, label)]
                h[2] += 1
                h[0] += rank <= 5
                h[1] += rank <= 10
        for k, (h5, h10, n) in hits.items():
            if n:
                scores[k][0].append(h5 / n)
                scores[k][1].append(h10 / n)

    lines = [
        "PAIRED SUBSTRATE COMPARISON [%s] (%d events common to "
        "all substrates; solo coverage trials=%d %s=%d fused=%d; "
        "%d negatives, %d repeats, shared samples)"
        % (
            mode,
            len(ev),
            solo_cover["trials"],
            alt,
            solo_cover[alt],
            solo_cover["fused"],
            negatives,
            repeats,
        )
    ]
    for s in SUBSTRATES:
        for m in ("cosine", "MASS-inspired"):
            h5s, h10s = scores[(s, m)]
            if h5s:
                lines.append(
                    "%-8s %-14s HR@5 %.3f (+/-%.3f)   HR@10 %.3f"
                    % (s, m, statistics.mean(h5s), statistics.pstdev(h5s), statistics.mean(h10s))
                )
    msg = "\n".join(lines)
    log.info(msg)
    (config.GOLD / "pair_substrate_report.txt").write_text(msg, encoding="utf-8")
    return {"status": "ok", "message": msg}
