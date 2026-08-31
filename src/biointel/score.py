# src/biointel/score.py
"""Phase M3-M5: target scoring, acquirer pairing, and the backtest.

WHY A TRANSPARENT SCORE AND NOT A FITTED CLASSIFIER. The verified label
set currently holds one acquisition (four positive firm-quarters). Any
model FITTED to that would be curve-tracing dressed as learning -- the
exact overstatement Palepu (1986) documented in early takeover models.
Until the P1 universe expansion supplies enough verified events, the
defensible instrument is a transparent additive score whose components
and weights are stated, literature-grounded, and auditable per company,
validated by whether it ranks the known acquisition highly BEFORE the
announcement (M5). When labels are plentiful, the same feature panel
feeds a fitted model with time-split evaluation at the true base rate.

TARGET SCORE (0-100, per firm-quarter, from model_panel.csv):
  De-risked asset      +25 approved drug (OrigApprovalsEver > 0)
                       +20 lead asset in Phase 3 (no approval yet)
                       +5  three or more Phase-3 trials
  Momentum             +10 original approval in trailing 12m
                       +5  positive mean CAR on trailing-12m FDA events
  Size feasibility     +15 market cap in the acquirable band
                           ($300M - $40B); unknown cap scores 0
  Strategic ties       +10 existing in-universe relationship
                       +5  five or more deal relationships
  Exit pressure        +10 runway under 24 months (USD filers only)
Companies on the acquirer side of the ledger (revenue > $10B or market
cap > $100B) are excluded from the target list.

ACQUIRER PAIRING (per top target):
  eligible acquirers = universe companies with revenue > $5B or market
  cap > $50B. Fit = 50 * therapeutic-area overlap (Jaccard on trial
  condition tokens) + 30 * prior relationship (any relationships.csv
  edge between the pair) + 20 * size headroom (acquirer cap >= 4x
  target cap, or unknown). The modal acquirer is an existing partner;
  the pairing makes that measurable.

BACKTEST (M5): score every company at a quarter end using only data as
of that date, and report where the verified acquisitions ranked. The
Vertex/Crinetics deal (announced 2026-07-06) is the live test: the
2026-06-30 ranking is entirely pre-announcement.
"""

from __future__ import annotations

import re
from collections import defaultdict

from biointel import config, store

PRED_COLS = [
    "Rank",
    "Ticker",
    "Company",
    "QuarterEnd",
    "TargetScore",
    "ScoreBreakdown",
    "Acquirer1",
    "Fit1",
    "Acquirer2",
    "Fit2",
    "Acquirer3",
    "Fit3",
    "AcqLOE1",
    "AcqLOE2",
    "AcqLOE3",
    "KnownOutcome",
]

_STOP = {
    "the",
    "of",
    "and",
    "a",
    "in",
    "with",
    "to",
    "type",
    "disease",
    "diseases",
    "disorder",
    "disorders",
    "syndrome",
    "chronic",
    "acute",
    "advanced",
    "adult",
    "pediatric",
    "healthy",
    "study",
    "patients",
    "treatment",
    "moderate",
    "severe",
    "mild",
}


def _load(table: str):
    return store.read_table(table)


def _num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def _condition_tokens() -> dict[int, set]:
    toks = defaultdict(set)
    for r in _load("trials"):
        for w in re.sub(r"[^a-z0-9 ]", " ", (r.get("Conditions") or "").lower()).split():
            if len(w) > 3 and w not in _STOP:
                toks[int(r["IID"])].add(w)
    return toks


def target_score(r: dict) -> tuple[float, str]:
    """(score, human-readable breakdown) for one model_panel row."""
    pts, why = 0.0, []

    approved = _num(r.get("OrigApprovalsEver")) or 0
    lead = _num(r.get("LeadPhase")) or 0
    ph3 = _num(r.get("TrialsPh3")) or 0
    if approved > 0:
        pts += 25
        why.append("approved drug +25")
    elif lead >= 3:
        pts += 20
        why.append("Phase-3 lead +20")
    if ph3 >= 3:
        pts += 5
        why.append("3+ Ph3 trials +5")

    if (_num(r.get("Approvals12m")) or 0) > 0:
        pts += 10
        why.append("approval in 12m +10")
    car = _num(r.get("CAR12m_mean"))
    if car is not None and car > 0:
        pts += 5
        why.append("positive event CAR +5")

    mcap = _num(r.get("MarketCap"))
    if mcap is not None and 3e8 <= mcap <= 4e10:
        pts += 15
        why.append("acquirable size +15")

    if (_num(r.get("RelInUniverse")) or 0) > 0:
        pts += 10
        why.append("in-universe partner +10")
    if (_num(r.get("RelDeal")) or 0) >= 5:
        pts += 5
        why.append("5+ deal ties +5")

    runway = _num(r.get("RunwayMonths"))
    if runway is not None and runway < 24 and (r.get("Currency") or "USD") == "USD":
        pts += 10
        why.append(f"runway {runway:.0f}m +10")

    return pts, "; ".join(why)


def _annualized_revenue(r: dict):
    rev = _num(r.get("Revenue"))
    if rev is None:
        return None
    basis = r.get("TTMBasis") or ""
    mult = {"annualized-Q1": 4.0, "annualized-Q2": 2.0, "annualized-Q3": 4 / 3}.get(basis, 1.0)
    return rev * mult


def _is_acquirer_side(r: dict) -> bool:
    rev = _annualized_revenue(r)
    mcap = _num(r.get("MarketCap"))
    return (rev is not None and rev > 1e10) or (mcap is not None and mcap > 7.5e10)


def predict(quarter: str | None = None) -> dict:
    """Ranked predictions for one quarter (default: latest with data)."""
    panel = _load("model_panel")
    if not panel:
        return {"status": "empty", "message": "model_panel.csv missing. Run: features"}
    quarters = sorted({r["QuarterEnd"] for r in panel})
    q = quarter or quarters[-1]
    rows = [r for r in panel if r["QuarterEnd"] == q]

    toks = _condition_tokens()
    rels = defaultdict(set)
    for r in _load("relationships"):
        if r.get("PartnerIID") not in ("", None):
            a, b = int(r["IID"]), int(r["PartnerIID"])
            rels[a].add(b)
            rels[b].add(a)

    acquirers = [r for r in rows if _is_acquirer_side(r)]
    targets = [r for r in rows if not _is_acquirer_side(r)]

    # SHIPPED PAIRING ENGINE (v0.81): MASS-EXACT on the trials
    # substrate (paper Eqs 6-10), adopted by pre-registered rule
    # (paired HR@5 0.318 vs 0.222). Fit = 100 x MASS-exact score
    # (size asymmetry is internal to the formula; can exceed 100). AcqLOE columns
    # are the Orange Book urgency share of each named acquirer --
    # acquirer-side context the given-acquirer protocol is structurally
    # unable to score, reported as a labeled, count-based proxy, not a
    # validated component.
    from biointel.pairs import exact_score, exact_state

    e_ids, pos, lam, norms = exact_state(q)
    try:
        from datetime import date as _date

        from biointel.sources.orangebook import loe_urgency

        loe = loe_urgency(_date.fromisoformat(q))
    except Exception:
        loe = {}

    def _fit(aid: int, tid: int) -> float:
        sa, st = str(aid), str(tid)
        if lam is None or sa not in pos or st not in pos:
            return 0.0
        return round(100 * float(exact_score(lam, norms, pos[sa], [pos[st]])[0]), 1)

    scored = []
    for t in targets:
        s, why = target_score(t)
        scored.append((s, why, t))
    scored.sort(key=lambda x: -x[0])

    out = []
    for rank, (s, why, t) in enumerate(scored, 1):
        iid = int(t["IID"])
        fits = []
        for a in acquirers:
            aid = int(a["IID"])
            fits.append(
                (_fit(aid, iid), a["Ticker"], a["Company"], (loe.get(str(aid)) or ("", "", ""))[2])
            )
        fits.sort(key=lambda x: -x[0])
        row = {
            "Rank": rank,
            "Ticker": t["Ticker"],
            "Company": t["Company"],
            "QuarterEnd": q,
            "TargetScore": s,
            "ScoreBreakdown": why,
            "KnownOutcome": (
                f"acquired by {t['Acquirer']} (announced {t['AnnounceDate']})"
                if t.get("AcquiredNext12m") == "1"
                else ""
            ),
        }
        for i in range(3):
            row[f"Acquirer{i + 1}"] = fits[i][1] if i < len(fits) else ""
            row[f"Fit{i + 1}"] = fits[i][0] if i < len(fits) else ""
            row[f"AcqLOE{i + 1}"] = fits[i][3] if i < len(fits) else ""
        out.append(row)

    store.write_table("ma_predictions", out, PRED_COLS)
    path = store.export_csv("ma_predictions", config.EXPORTS / "ma_predictions.csv")
    return {
        "status": "ok",
        "quarter": q,
        "rows": out,
        "message": f"{len(out)} targets ranked at {q} -> {path} "
        f"({len(acquirers)} acquirer-side companies)",
    }


def backtest() -> list[str]:
    """Where did verified acquisitions rank, pre-announcement?"""
    panel = _load("model_panel")
    pos_quarters = sorted(
        {
            (r["QuarterEnd"], r["Ticker"], r["Acquirer"])
            for r in panel
            if r.get("AcquiredNext12m") == "1"
        }
    )
    lines = []
    for q, tick, acq in pos_quarters:
        res = predict(q)
        if res["status"] != "ok":
            continue
        ranks = {r["Ticker"]: (r["Rank"], r["TargetScore"], len(res["rows"])) for r in res["rows"]}
        if tick in ranks:
            rk, sc, n = ranks[tick]
            lines.append(f"{q}: {tick} ranked {rk}/{n} (score {sc:.0f}) -- later acquired by {acq}")
    return lines
