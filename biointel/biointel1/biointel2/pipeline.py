"""Silver layer: the three Excel workflows, as functions.

  add_company(ticker)   <- CompanyLookup query + AddCompany macro
  get_events(iid)       <- Events query + GetEvents macro
  price_window(...)     <- PriceWindow query
"""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path

from . import config
from .sources import sec, alphavantage, fda, prices

COMPANY_COLS = ["IID", "Name", "Ticker", "Created", "Description",
                "CIK", "SIC", "SICDescription", "Exchange", "StateOfIncorporation",
                "FDAAliases"]
EVENT_COLS   = ["IID", "Name", "Event", "Date", "AppNo", "Drug",
                "Outcome", "Priority", "ClassCode", "SubType"]
PRICE_COLS   = ["IID", "Ticker", "Date", "Open", "High", "Low",
                "Close", "AdjClose", "Volume"]


# ---------------------------------------------------------------- csv helpers
def _read(path: Path, cols: list[str]) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_companies() -> list[dict]:
    return _read(config.COMPANIES_CSV, COMPANY_COLS)


def read_events() -> list[dict]:
    return _read(config.EVENTS_CSV, EVENT_COLS)


# ---------------------------------------------------------------- add_company
def add_company(ticker: str) -> dict:
    """Port of AddCompany. Dedups on ticker; IID = max existing + 1, from 0."""
    t = ticker.strip().upper()
    rows = read_companies()

    for r in rows:
        if str(r.get("Ticker", "")).strip().upper() == t:
            return {"status": "duplicate", "iid": int(r["IID"]),
                    "message": f"{t} is already IID {r['IID']}."}

    ident = sec.company_identity(t)
    if not ident["name"] or ident["name"] == "TICKER NOT FOUND":
        return {"status": "not_found",
                "message": f"{t} was not found at SEC. Nothing added."}

    desc = alphavantage.description(t)
    next_iid = max((int(r["IID"]) for r in rows if str(r.get("IID", "")).strip().isdigit()),
                   default=-1) + 1

    rows.append({
        "IID": next_iid, "Name": ident["name"], "Ticker": t,
        "Created": date.today().isoformat(), "Description": desc,
        "CIK": ident["cik"], "SIC": ident["sic"],
        "SICDescription": ident["sic_description"],
        "Exchange": ident["exchange"],
        "StateOfIncorporation": ident["state_of_incorporation"],
        "FDAAliases": "",
    })
    _write(config.COMPANIES_CSV, COMPANY_COLS, rows)
    return {"status": "added", "iid": next_iid, "name": ident["name"],
            "message": f"Added {ident['name']} ({t}) as IID {next_iid}."}


# ----------------------------------------------------------------- get_events
def get_events(iid: int) -> dict:
    """Port of GetEvents. Appends to events.csv, deduping on
    (IID, Event, Date, AppNo)."""
    companies = read_companies()
    hit = next((c for c in companies if str(c.get("IID")) == str(iid)), None)
    if hit is None:
        return {"status": "no_such_iid", "added": 0, "skipped": 0,
                "message": f"IID {iid} is not in companies.csv."}

    aliases = [a.strip() for a in str(hit.get("FDAAliases") or "").split(";") if a.strip()]
    fresh = fda.events_for(int(iid), hit["Name"], aliases)
    existing = read_events()
    seen = {(str(r["IID"]), r["Event"], str(r["Date"]), str(r["AppNo"]))
            for r in existing}

    added = 0
    for r in fresh:
        k = (str(r["IID"]), r["Event"], r["Date"].isoformat(), str(r["AppNo"]))
        if k in seen:
            continue
        seen.add(k)
        existing.append({**r, "Date": r["Date"].isoformat()})
        added += 1

    existing.sort(key=lambda r: (int(r["IID"]), str(r["Date"])), reverse=False)
    _write(config.EVENTS_CSV, EVENT_COLS, existing)
    return {"status": "ok", "added": added, "skipped": len(fresh) - added,
            "total": len(existing),
            "message": f"{hit['Name']}: added {added}, skipped {len(fresh)-added}."}


def get_all_events() -> dict:
    """Every company in companies.csv. Replaces 13 button presses."""
    out = []
    for c in read_companies():
        out.append(get_events(int(c["IID"])))
    return {"companies": len(out),
            "added": sum(r.get("added", 0) for r in out), "detail": out}


# --------------------------------------------------------------- price_window
def price_window(appno: str, event_date: str | date,
                 pre: int = None, post: int = None) -> list[dict]:
    """Port of PriceWindow. Selects one event by AppNo + Date."""
    d = date.fromisoformat(str(event_date)) if not isinstance(event_date, date) else event_date
    ev = next((e for e in read_events()
               if str(e["AppNo"]).strip() == str(appno).strip()
               and str(e["Date"]) == d.isoformat()), None)
    if ev is None:
        return []

    co = next((c for c in read_companies() if str(c["IID"]) == str(ev["IID"])), None)
    if co is None:
        return []

    win = prices.event_window(co["Ticker"], d, pre, post)
    for row in win:
        row["IID"] = int(ev["IID"])
        row["Drug"] = ev.get("Drug")
        row["Event"] = ev.get("Event")
        row["AppNo"] = ev.get("AppNo")
    return win
