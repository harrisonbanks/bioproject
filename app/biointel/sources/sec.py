"""SEC EDGAR. Port of the CompanyLookup Power Query (SEC half)."""
from __future__ import annotations

from .. import config
from ..store import fetch_json


def ticker_to_cik(ticker: str) -> str | None:
    """Resolve a ticker to a zero-padded 10-digit CIK. Returns None if absent."""
    t = ticker.strip().upper()
    data = fetch_json(config.SEC_TICKERS, tag="sec_tickers")
    for rec in data.values():
        if str(rec.get("ticker", "")).upper() == t:
            return str(rec["cik_str"]).zfill(10)
    return None


def submissions(cik10: str) -> dict:
    return fetch_json(config.SEC_SUBS.format(cik10=cik10), tag="sec_submissions")


def company_identity(ticker: str) -> dict:
    """Ticker -> {ticker, cik, name, sic, sic_description, exchange,
    state_of_incorporation}. name is 'TICKER NOT FOUND' when unresolved."""
    cik10 = ticker_to_cik(ticker)
    if cik10 is None:
        return {"ticker": ticker.strip().upper(), "cik": "",
                "name": "TICKER NOT FOUND", "sic": "", "sic_description": "",
                "exchange": "", "state_of_incorporation": ""}
    sub = submissions(cik10)
    exch = sub.get("exchanges") or []
    return {
        "ticker": ticker.strip().upper(),
        "cik": cik10,
        "name": sub.get("name", "") or "",
        "sic": sub.get("sic", "") or "",
        "sic_description": sub.get("sicDescription", "") or "",
        "exchange": ", ".join(str(e) for e in exch if e),
        "state_of_incorporation": sub.get("stateOfIncorporationDescription", "") or "",
    }
