"""Alpha Vantage OVERVIEW. Port of the CompanyLookup Power Query (AV half).

Free tier is 25 calls/day. Failure strings are kept identical to the M query
so downstream behaviour is unchanged.
"""

from __future__ import annotations

from biointel import config
from biointel.store import fetch_json


def description(ticker: str) -> str:
    try:
        av = fetch_json(
            config.AV_QUERY,
            params={
                "function": "OVERVIEW",
                "symbol": ticker.strip().upper(),
                "apikey": config.require("BIOINTEL_ALPHA_VANTAGE_KEY"),
            },
            tag="alphavantage_overview",
        )
    except Exception:
        return "UNAVAILABLE - check the API key"

    if av is None:
        return "UNAVAILABLE - check the API key"
    if av.get("Note") is not None or av.get("Information") is not None:
        return "RATE LIMIT - 25 lookups used today"
    raw = av.get("Description")
    if raw is None or raw in ("None", ""):
        return "NOT PROVIDED"
    return str(raw)
