"""Yahoo Finance chart API. Port of the PriceWindow Power Query.

Verified against a live pull: dataGranularity '1d', 2514 rows over 10y for
PFE, adjclose differing from close on 2513 of 2514 rows.

Structure: chart.result[0].timestamp is an epoch array;
indicators.quote[0] holds parallel open/high/low/close/volume arrays;
indicators.adjclose[0].adjclose is the adjusted series. All index-aligned.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone

from .. import config
from ..store import fetch_json


def daily_bars(ticker: str, start: date, end: date) -> list[dict]:
    """Daily OHLCV + adjusted close between two dates. [] on failure."""
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp())
    try:
        raw = fetch_json(config.YAHOO_CHART.format(ticker=ticker.strip().upper()),
                         params={"period1": p1, "period2": p2, "interval": "1d"},
                         tag="yahoo_chart")
    except Exception:
        return []

    try:
        res = raw["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        adj = res["indicators"]["adjclose"][0]["adjclose"]
    except Exception:
        return []

    rows = []
    for i, epoch in enumerate(ts):
        close = q["close"][i]
        if close is None:
            continue
        rows.append({
            "Ticker": ticker.strip().upper(),
            "Date": datetime.fromtimestamp(epoch, timezone.utc).date(),
            "Open": q["open"][i], "High": q["high"][i], "Low": q["low"][i],
            "Close": close, "AdjClose": adj[i], "Volume": q["volume"][i],
        })
    rows.sort(key=lambda r: r["Date"])
    return rows


def event_window(ticker: str, event_date: date,
                 pre: int = None, post: int = None) -> list[dict]:
    """Contiguous RelDay -pre..+post around an event.

    t0 = first trading session ON OR AFTER the event date. This is the
    standard convention: an announcement made when the market is closed,
    or after hours, is assigned to the next trading day.

    RelDay is a ROW OFFSET within the ticker's own series, not calendar
    arithmetic, so weekends and holidays need no special handling.
    """
    pre = config.WINDOW_PRE if pre is None else pre
    post = config.WINDOW_POST if post is None else post
    pad = timedelta(days=config.PRICE_PAD_DAYS)

    bars = daily_bars(ticker, event_date - pad, event_date + pad)
    if not bars:
        return []

    t0 = next((i for i, b in enumerate(bars) if b["Date"] >= event_date), None)
    if t0 is None:
        return []

    lo, hi = max(0, t0 - pre), min(len(bars) - 1, t0 + post)
    win = []
    base = bars[t0]["AdjClose"]
    for i in range(lo, hi + 1):
        b = dict(bars[i])
        b["RelDay"] = i - t0
        b["PctFromT0"] = (None if not base
                          else (b["AdjClose"] - base) / base * 100)
        win.append(b)
    return win
