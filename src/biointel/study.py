"""Event-study metrics around FDA action dates.

Standard market-model event study (Brown & Warner 1980/1985): expected
return is estimated from a benchmark over a window that ends BEFORE the
event window, abnormal return is actual minus expected, and CAR sums
abnormal returns over the event window. Biotech studies benchmark against
XBI (SPDR S&P Biotech) with SPY as a robustness check; reactions are
documented to be asymmetric (negative events move prices more and longer)
and size-dependent (small caps move more).

Five metrics, all computable from the existing RelDay -10..+10 windows:

  CAR         cumulative abnormal return vs benchmark over [-1,+1],
              [0,+1] and [-5,+5]
  T0Gap       overnight surprise: Open(t0)/AdjClose(t0-1) - 1, versus
              Intraday: Close(t0)/Open(t0) - 1
  AbnVolume   Volume(t0) / mean Volume over [-10,-2]
  VolShift    std of daily returns [+1,+10] / std over [-10,-1]
  Drift       post-event drift sign via 3v7-day mean crossover on the
              +window (SMA fast vs slow at RelDay +10)

Benchmark handling: XBI daily bars are fetched through the same cached
Yahoo source. If the benchmark cannot be fetched, CAR falls back to RAW
cumulative return and the row is marked Benchmark='none' -- a raw number
labelled as raw, never a silent substitute.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from biointel import config
from biointel.sources import prices

BENCHMARK = "XBI"  # SPDR S&P Biotech; SPY available as check
EST_DAYS = 120  # estimation window length (trading days), ends at RelDay -11


def _rets(bars: list[dict]) -> list[float | None]:
    """Daily simple returns from AdjClose; index i is return into bar i."""
    out: list[float | None] = [None]
    for i in range(1, len(bars)):
        a, b = bars[i - 1]["AdjClose"], bars[i]["AdjClose"]
        out.append((b - a) / a if (a and b is not None) else None)
    return out


def _ols(x: list[float], y: list[float]) -> tuple[float, float]:
    """Slope, intercept of y on x. Market model: R_i = a + b * R_m."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return 0.0, my
    b = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / sxx
    return b, my - b * mx


def event_metrics(ticker: str, event_date: date) -> dict:
    """All five metric families for one (ticker, event date).

    Returns {} when price data is unavailable for the event window.
    Benchmark field records what CAR was computed against: 'XBI' for the
    market model, 'none' for raw cumulative return fallback.
    """
    pad = timedelta(days=max(config.PRICE_PAD_DAYS, 300))
    stock = prices.daily_bars(ticker, event_date - pad, event_date + pad)
    if not stock:
        return {}
    t0 = next((i for i, b in enumerate(stock) if b["Date"] >= event_date), None)
    if t0 is None or t0 < 12 or t0 + 1 >= len(stock):
        return {}

    bench = prices.daily_bars(BENCHMARK, event_date - pad, event_date + pad)
    srets = _rets(stock)

    # ---- market model on the estimation window ------------------------
    alpha = beta = None
    brets_by_date = {}
    if bench:
        brets = _rets(bench)
        brets_by_date = {b["Date"]: r for b, r in zip(bench, brets) if r is not None}
        est_lo = max(1, t0 - 10 - EST_DAYS)
        xs, ys = [], []
        for i in range(est_lo, max(est_lo, t0 - 10)):
            sr = srets[i]
            br = brets_by_date.get(stock[i]["Date"])
            if sr is not None and br is not None:
                xs.append(br)
                ys.append(sr)
        if len(xs) >= 30:
            beta, alpha = _ols(xs, ys)

    def abn(i: int) -> float | None:
        sr = srets[i]
        if sr is None:
            return None
        if beta is None:
            return sr  # raw fallback
        br = brets_by_date.get(stock[i]["Date"])
        if br is None:
            return None
        return sr - (alpha + beta * br)

    def car(lo_rel: int, hi_rel: int) -> float | None:
        vals = []
        for rel in range(lo_rel, hi_rel + 1):
            i = t0 + rel
            if not (1 <= i < len(stock)):
                return None
            a = abn(i)
            if a is None:
                return None
            vals.append(a)
        return sum(vals) * 100.0

    # ---- T0 gap vs intraday -------------------------------------------
    prev_adj = stock[t0 - 1]["AdjClose"]
    o, c = stock[t0]["Open"], stock[t0]["Close"]
    # Open/Close are unadjusted; use unadjusted prev close for the gap so
    # both legs of the ratio live in the same price basis.
    prev_close_raw = stock[t0 - 1]["Close"]
    gap = (o / prev_close_raw - 1) * 100 if (o and prev_close_raw) else None
    intraday = (c / o - 1) * 100 if (o and c) else None

    # ---- abnormal volume ----------------------------------------------
    base_vol = [
        stock[t0 + r]["Volume"]
        for r in range(-10, -1)
        if 0 <= t0 + r < len(stock) and stock[t0 + r]["Volume"]
    ]
    abn_vol = (
        stock[t0]["Volume"] / (sum(base_vol) / len(base_vol))
        if base_vol and stock[t0]["Volume"]
        else None
    )

    # ---- volatility shift ---------------------------------------------
    def _std(vals):
        vals = [v for v in vals if v is not None]
        if len(vals) < 4:
            return None
        m = sum(vals) / len(vals)
        return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))

    pre_sd = _std([srets[t0 + r] for r in range(-10, 0) if 1 <= t0 + r < len(stock)])
    post_sd = _std([srets[t0 + r] for r in range(1, 11) if 1 <= t0 + r < len(stock)])
    vol_shift = (post_sd / pre_sd) if (pre_sd and post_sd) else None

    # ---- post-event drift: fast(3) vs slow(7) mean of AdjClose at +10 --
    post = [
        stock[t0 + r]["AdjClose"]
        for r in range(0, 11)
        if t0 + r < len(stock) and stock[t0 + r]["AdjClose"]
    ]
    drift = None
    if len(post) >= 8:
        fast = sum(post[-3:]) / 3
        slow = sum(post[-7:]) / 7
        drift = (fast / slow - 1) * 100

    return {
        "Ticker": ticker,
        "EventDate": event_date.isoformat(),
        "T0Date": stock[t0]["Date"].isoformat(),
        "Benchmark": BENCHMARK if beta is not None else "none",
        "Beta": round(beta, 3) if beta is not None else None,
        "CAR_m1_p1": _r(car(-1, 1)),
        "CAR_0_p1": _r(car(0, 1)),
        "CAR_m5_p5": _r(car(-5, 5)),
        "T0Gap": _r(gap),
        "T0Intraday": _r(intraday),
        "AbnVolume": _r(abn_vol),
        "VolShift": _r(vol_shift),
        "Drift10": _r(drift),
    }


def _r(v, nd=2):
    return None if v is None else round(v, nd)


STUDY_COLS = [
    "IID",
    "Company",
    "Ticker",
    "Event",
    "Outcome",
    "Drug",
    "AppNo",
    "EventDate",
    "T0Date",
    "Benchmark",
    "Beta",
    "CAR_m1_p1",
    "CAR_0_p1",
    "CAR_m5_p5",
    "T0Gap",
    "T0Intraday",
    "AbnVolume",
    "VolShift",
    "Drift10",
]


def run_study(events: list[dict], companies: list[dict], since: str = "2010-01-01") -> list[dict]:
    """Metrics for every event since `since` (price coverage era)."""
    tick = {str(c["IID"]): c.get("Ticker", "") for c in companies}
    name = {str(c["IID"]): c.get("Name", "") for c in companies}
    out = []
    for e in events:
        d = str(e.get("Date") or "")
        if d < since:
            continue
        t = tick.get(str(e["IID"]), "")
        if not t:
            continue
        m = event_metrics(t, date.fromisoformat(d))
        if not m:
            continue
        out.append(
            {
                "IID": int(e["IID"]),
                "Company": name.get(str(e["IID"]), ""),
                "Event": e.get("Event"),
                "Outcome": e.get("Outcome"),
                "Drug": e.get("Drug"),
                "AppNo": e.get("AppNo"),
                **m,
            }
        )
    return out


def summarize(rows: list[dict]) -> list[dict]:
    """Mean and median of each metric by outcome class."""
    import statistics as st
    from collections import defaultdict

    groups = defaultdict(list)
    for r in rows:
        key = f"{r.get('Event')}/{r.get('Outcome')}"
        groups[key].append(r)
    metrics = [
        "CAR_m1_p1",
        "CAR_0_p1",
        "CAR_m5_p5",
        "T0Gap",
        "T0Intraday",
        "AbnVolume",
        "VolShift",
        "Drift10",
    ]
    out = []
    for key, rs in sorted(groups.items()):
        row = {"OutcomeClass": key, "N": len(rs)}
        for m in metrics:
            vals = [r[m] for r in rs if r.get(m) is not None]
            row[f"{m}_mean"] = round(st.mean(vals), 2) if vals else None
            row[f"{m}_median"] = round(st.median(vals), 2) if vals else None
        out.append(row)
    return out
