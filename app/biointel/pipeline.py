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
from .sources import sec, alphavantage, fda, prices, trials, financials, deals, counterparty
from . import network

COMPANY_COLS = ["IID", "Name", "Ticker", "Created", "Description",
                "CIK", "SIC", "SICDescription", "Exchange", "StateOfIncorporation",
                "FDAAliases", "CTGovName"]
EVENT_COLS   = ["IID", "Name", "Event", "Date", "AppNo", "Drug",
                "Outcome", "Priority", "ClassCode", "SubType"]
PRICE_COLS   = ["IID", "Ticker", "Date", "Open", "High", "Low",
                "Close", "AdjClose", "Volume"]
TRIAL_COLS   = ["IID", "Company", "NCTId", "Sponsor", "SponsorClass", "Title",
                "Phase", "Status", "StudyType", "Conditions", "Drugs",
                "Interventions", "Enrollment", "Collaborators",
                "CollaboratorClasses", "CollaboratorCount", "StartDate",
                "PrimaryCompletion", "CompletionDate", "LastUpdate"]


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
        "FDAAliases": "", "CTGovName": "",
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


# ------------------------------------------------------------------- trials
def read_trials() -> list[dict]:
    return _read(config.TRIALS_CSV, TRIAL_COLS)


def _trial_search_name(company: dict) -> str:
    """What to send to CT.gov as the lead sponsor.

    Uses CTGovName if set, else the first distinctive word of the SEC name.
    AREA[LeadSponsorName] is substring-tolerant, so a distinctive token is
    usually enough -- unlike the FDA join, which needs exact equality.
    """
    override = str(company.get("CTGovName") or "").strip()
    if override:
        return override
    from .match import canon
    k = canon(company.get("Name"))
    return k.split()[0] if k else ""


def get_trials(iid: int) -> dict:
    """Pull every trial where this company is lead sponsor. Dedup on NCTId."""
    companies = read_companies()
    hit = next((c for c in companies if str(c.get("IID")) == str(iid)), None)
    if hit is None:
        return {"status": "no_such_iid", "added": 0,
                "message": f"IID {iid} is not in companies.csv."}

    term = _trial_search_name(hit)
    if not term:
        return {"status": "no_search_term", "added": 0,
                "message": f"IID {iid}: no usable sponsor name."}

    fresh = trials.trials_for(term)
    existing = read_trials()
    seen = {(str(r["IID"]), r["NCTId"]) for r in existing}

    added = 0
    for r in fresh:
        k = (str(iid), r["NCTId"])
        if k in seen:
            continue
        seen.add(k)
        existing.append({"IID": iid, "Company": hit["Name"], **r})
        added += 1

    existing.sort(key=lambda r: (int(r["IID"]), str(r.get("StartDate") or "")))
    _write(config.TRIALS_CSV, TRIAL_COLS, existing)
    return {"status": "ok", "added": added, "found": len(fresh),
            "total": len(existing), "term": term,
            "message": f"{hit['Name']}: searched '{term}', "
                       f"found {len(fresh)}, added {added}."}


def get_all_trials() -> dict:
    out = [get_trials(int(c["IID"])) for c in read_companies()]
    return {"companies": len(out),
            "added": sum(r.get("added", 0) for r in out), "detail": out}


def pipeline_calendar(iid: int) -> list[dict]:
    """Every candidate for one company, trials and FDA actions merged,
    in date order. This is the drug pipeline calendar."""
    rows = []
    for t in read_trials():
        if str(t["IID"]) != str(iid):
            continue
        rows.append({
            "Date": t.get("StartDate") or "",
            "Stage": t.get("Phase") or t.get("StudyType") or "TRIAL",
            "Drug": t.get("Drugs") or t.get("Interventions") or "",
            "Detail": t.get("Conditions") or "",
            "Status": t.get("Status") or "",
            "Ref": t.get("NCTId") or "",
            "Source": "CT.gov",
        })
    for e in read_events():
        if str(e["IID"]) != str(iid):
            continue
        rows.append({
            "Date": e.get("Date") or "",
            "Stage": "FDA " + str(e.get("Event") or ""),
            "Drug": e.get("Drug") or "",
            "Detail": e.get("Outcome") or "",
            "Status": e.get("SubType") or "",
            "Ref": e.get("AppNo") or "",
            "Source": "FDA",
        })
    rows.sort(key=lambda r: r["Date"], reverse=True)
    return rows


# --------------------------------------------------------------- financials
FIN_COLS  = ["IID", "Company", "CIK", "PeriodEnd", "Currency", "Form", "FY", "FP",
             "Cash", "ShortTermInvestments", "Revenue", "RnD", "OpEx",
             "OperatingIncome", "NetIncome", "TotalAssets", "TotalLiabilities",
             "Equity", "LongTermDebt", "NetCashOperating", "SharesOutstanding",
             "Accession", "Filed"]
SNAP_COLS = ["IID", "Company", "Ticker", "CIK", "CashAsOf", "Cash",
             "ShortTermInvestments", "TotalCash", "Revenue", "RnD",
             "LongTermDebt", "SharesOutstanding", "NetCashOperating",
             "OCFAsOf", "TTMMethod", "BurnAnnual", "RunwayMonths", "Periods"]


def read_financials() -> list[dict]:
    return _read(config.FINANCIALS_CSV, FIN_COLS)


def get_financials(iid: int) -> dict:
    """SEC CompanyFacts for one company. Keyed on CIK -- no name matching."""
    companies = read_companies()
    hit = next((c for c in companies if str(c.get("IID")) == str(iid)), None)
    if hit is None:
        return {"status": "no_such_iid", "added": 0,
                "message": f"IID {iid} is not in companies.csv."}

    cik = str(hit.get("CIK") or "").strip()
    if not cik:
        return {"status": "no_cik", "added": 0,
                "message": f"IID {iid} ({hit.get('Ticker')}): no CIK. "
                           f"Migrated rows have it blank; re-add or fill it in."}

    rows = financials.financial_series(cik)
    existing = read_financials()
    seen = {(str(r["IID"]), r["PeriodEnd"]) for r in existing}

    added = 0
    for r in rows:
        k = (str(iid), r["PeriodEnd"])
        if k in seen:
            continue
        seen.add(k)
        existing.append({
            "IID": iid, "Company": hit["Name"], "CIK": cik,
            "PeriodEnd": r["PeriodEnd"], "Currency": r.get("Currency", "USD"),
            "Form": r.get("_form"),
            "FY": r.get("_fy"), "FP": r.get("_fp"),
            "Accession": r.get("_accn"), "Filed": r.get("_filed"),
            **{k2: r.get(k2) for k2 in
               ["Cash", "ShortTermInvestments", "Revenue", "RnD", "OpEx",
                "OperatingIncome", "NetIncome", "TotalAssets",
                "TotalLiabilities", "Equity", "LongTermDebt",
                "NetCashOperating", "SharesOutstanding"]},
        })
        added += 1

    existing.sort(key=lambda r: (int(r["IID"]), str(r["PeriodEnd"])))
    _write(config.FINANCIALS_CSV, FIN_COLS, existing)
    return {"status": "ok", "added": added, "periods": len(rows),
            "message": f"{hit['Name']}: {len(rows)} periods, added {added}."}


def get_all_financials() -> dict:
    out = [get_financials(int(c["IID"])) for c in read_companies()]
    return {"companies": len(out),
            "added": sum(r.get("added", 0) for r in out), "detail": out}


def build_snapshot() -> list[dict]:
    """One row per company: latest cash position, burn, and runway.

    Runway is months of cash at current burn. Crude -- assumes constant
    burn, ignores financing already raised -- but it is the standard
    first-pass read on whether a company must raise, license, or sell.
    """
    rows = []
    for c in read_companies():
        cik = str(c.get("CIK") or "").strip()
        if not cik:
            continue
        snap = financials.latest_snapshot(cik)
        if not snap:
            continue
        rows.append({"IID": int(c["IID"]), "Company": c["Name"],
                     "Ticker": c["Ticker"], "CIK": cik, **snap})
    rows.sort(key=lambda r: (r.get("RunwayMonths") is None,
                             r.get("RunwayMonths") or 0))
    _write(config.SNAPSHOT_CSV, SNAP_COLS, rows)
    return rows


def backfill_identity() -> dict:
    """Fill CIK/SIC/Exchange for rows that lack them.

    Rows migrated from the Excel workbook have these blank. Financials are
    keyed on CIK, so this must run before `fin-all`.
    """
    companies = read_companies()
    filled, failed = 0, []
    for c in companies:
        if str(c.get("CIK") or "").strip():
            continue
        t = str(c.get("Ticker") or "").strip().upper()
        if not t:
            continue
        ident = sec.company_identity(t)
        if not ident.get("cik"):
            failed.append(t)
            continue
        c["CIK"] = ident["cik"]
        c["SIC"] = ident["sic"]
        c["SICDescription"] = ident["sic_description"]
        c["Exchange"] = ident["exchange"]
        c["StateOfIncorporation"] = ident["state_of_incorporation"]
        filled += 1

    cols = list(COMPANY_COLS)
    for extra in ("FDAAliases", "CTGovName"):
        if extra not in cols and any(extra in c for c in companies):
            cols.append(extra)
    _write(config.COMPANIES_CSV, cols, companies)
    return {"filled": filled, "failed": failed,
            "message": f"Filled CIK for {filled} companies."
                       + (f" Failed: {', '.join(failed)}" if failed else "")}


# ------------------------------------------------------------------ network
PARTNER_COLS = ["IID", "Ticker", "Company", "Collaborator", "CollaboratorKey",
                "Type", "CTGovClass", "Trials", "Phases", "TherapyAreas",
                "FirstTrial", "LastTrial"]
PSUM_COLS = ["IID", "Ticker", "Company", "TotalPartners",
             "Industry (unclassified)", "CRO", "CDMO/Manufacturing",
             "Diagnostics/Lab", "Device/Delivery", "Imaging", "Academic",
             "Foundation/Nonprofit", "Government", "Network", "Other"]


def build_partners() -> dict:
    """Partnership network from trial collaborators.

    Reads trials.csv, writes partners.csv (one row per company-collaborator
    pair) and partner_summary.csv (one row per company, counts by type).
    No API calls -- derived entirely from data already downloaded.
    """
    trials_rows = read_trials()
    companies = read_companies()
    if not trials_rows:
        return {"status": "no_trials", "edges": 0,
                "message": "trials.csv is empty. Run: python cli.py trials-all"}

    has_field = any("Collaborators" in r for r in trials_rows[:5])
    if not has_field:
        return {"status": "no_collaborator_field", "edges": 0,
                "message": "trials.csv has no Collaborators column. It was "
                           "pulled before the field was captured. Delete "
                           "data/silver/trials.csv and re-run trials-all."}

    net = network.build_network(trials_rows, companies)
    _write(config.PARTNERS_CSV, PARTNER_COLS, net["edges"])
    _write(config.PARTNER_SUMMARY_CSV, PSUM_COLS, net["summary"])
    return {"status": "ok", "edges": len(net["edges"]),
            "companies": len(net["summary"]),
            "message": f"{len(net['edges'])} partnerships across "
                       f"{len([s for s in net['summary'] if s['TotalPartners']])} companies."}


# ------------------------------------------------------- relationships (N2)
REL_COLS = ["IID", "Ticker", "Company", "Partner", "PartnerKey", "PartnerIID",
            "PartnerType", "RelKind", "AgreementType", "Count",
            "FirstDate", "LastDate", "TherapyAreas", "Evidence"]


def build_relationships() -> dict:
    """N2: merge trial collaborations and deal counterparties into one table.

    One row per (company, canonical partner, relationship kind, agreement
    type). Canonicalization reuses network._norm so "Sanofi-Aventis US LLC"
    and "Sanofi" collapse to one partner. PartnerIID is set when the partner
    is itself a universe company -- these in-universe pairs are the direct
    input to M&A pairing (the modal acquirer is an existing partner), and
    the Merger/Acquisition rows name acquirers for the label set.
    Derived purely from silver tables; no API calls.
    """
    companies = read_companies()
    # canonical key -> IID for in-universe partner matching (names + tickers)
    key_to_iid: dict[str, int] = {}
    for co in companies:
        for nm in (co.get("Name", ""), co.get("Ticker", "")):
            k = network._norm(nm)
            if k and k not in key_to_iid:
                key_to_iid[k] = int(co["IID"])
    co_by_iid = {int(c["IID"]): c for c in companies}

    rows: dict[tuple, dict] = {}

    def upsert(iid, partner_raw, key, rel_kind, agr_type, count, first, last,
               areas, evidence, ptype):
        k = (iid, key, rel_kind, agr_type)
        r = rows.get(k)
        if r is None:
            co = co_by_iid.get(iid, {})
            rows[k] = {
                "IID": iid, "Ticker": co.get("Ticker", ""),
                "Company": co.get("Name", ""), "Partner": partner_raw,
                "PartnerKey": key,
                "PartnerIID": key_to_iid.get(key, ""),
                "PartnerType": ptype, "RelKind": rel_kind,
                "AgreementType": agr_type, "Count": count,
                "FirstDate": first or "", "LastDate": last or "",
                "TherapyAreas": areas or "", "Evidence": evidence or "",
            }
            return
        r["Count"] = int(r["Count"]) + count
        if len(partner_raw) > len(r["Partner"]):
            r["Partner"] = partner_raw          # keep the fullest name seen
        if first and (not r["FirstDate"] or first < r["FirstDate"]):
            r["FirstDate"] = first
        if last and (not r["LastDate"] or last > r["LastDate"]):
            r["LastDate"] = last
        if evidence and len(r["Evidence"]) < 120:
            r["Evidence"] = (r["Evidence"] + "; " + evidence).strip("; ")

    # ---- trial collaborations (partners.csv) --------------------------
    n_trial = 0
    if config.PARTNERS_CSV.exists():
        for e in _read(config.PARTNERS_CSV, PARTNER_COLS):
            upsert(int(e["IID"]), e["Collaborator"],
                   e["CollaboratorKey"] or network._norm(e["Collaborator"]),
                   "Trial collaboration", "",
                   int(e["Trials"] or 1), e.get("FirstTrial"),
                   e.get("LastTrial"), e.get("TherapyAreas"), "",
                   e.get("Type") or "")
            n_trial += 1

    # ---- deal counterparties (deal_counterparties.csv) ----------------
    n_deal = 0
    if config.COUNTERPARTY_CSV.exists():
        for d in _read(config.COUNTERPARTY_CSV, CP_COLS):
            nm = d["Counterparty"]
            upsert(int(d["IID"]), nm, network._norm(nm),
                   "Deal", d.get("AgreementType") or "Other", 1,
                   d.get("FilingDate"), d.get("FilingDate"), "",
                   d.get("Accession", ""), network.classify(nm))
            n_deal += 1

    if not rows:
        return {"status": "empty", "message":
                "No partners.csv or deal_counterparties.csv. Run "
                "partners and cparty-all first."}

    out = sorted(rows.values(),
                 key=lambda r: (r["IID"], r["RelKind"], -int(r["Count"])))
    _write(config.RELATIONSHIPS_CSV, REL_COLS, out)
    in_uni = [r for r in out if r["PartnerIID"] != ""
              and int(r["PartnerIID"]) != int(r["IID"])]
    ma = [r for r in out if r["AgreementType"] == "Merger/Acquisition"]
    return {"status": "ok", "rows": len(out),
            "message": f"{len(out)} relationships ({n_trial} trial edges + "
                       f"{n_deal} deal rows merged) -> relationships.csv. "
                       f"In-universe pairs: {len(in_uni)}. "
                       f"Merger/Acquisition rows (label candidates): {len(ma)}."}


# -------------------------------------------------------------------- deals
DEAL_COLS = ["IID", "Company", "Ticker", "CIK", "FilingDate", "ReportDate",
             "Item", "EventType", "Form", "Accession", "AllItems",
             "AcceptedAt", "PrimaryDoc", "FilingURL", "IndexURL"]


def read_deals() -> list[dict]:
    return _read(config.DEALS_CSV, DEAL_COLS)


def get_deals(iid: int) -> dict:
    """8-K material agreements for one company. Keyed on CIK.

    Captures Items 1.01 (agreement entered), 1.02 (terminated) and 2.01
    (acquisition/disposition completed). These cover agreements of any
    type -- licensing, manufacturing, supply, service, financing -- so the
    result reaches non-drug and financial counterparties, not only pharma.
    """
    companies = read_companies()
    hit = next((c for c in companies if str(c.get("IID")) == str(iid)), None)
    if hit is None:
        return {"status": "no_such_iid", "added": 0,
                "message": f"IID {iid} is not in companies.csv."}
    cik = str(hit.get("CIK") or "").strip()
    if not cik:
        return {"status": "no_cik", "added": 0,
                "message": f"IID {iid} ({hit.get('Ticker')}): no CIK. "
                           f"Run: python cli.py backfill"}

    rows = deals.deal_filings(cik)
    existing = read_deals()
    seen = {(str(r["IID"]), r["Accession"], r["Item"]) for r in existing}

    added = 0
    for r in rows:
        k = (str(iid), r["Accession"], r["Item"])
        if k in seen:
            continue
        seen.add(k)
        existing.append({"IID": iid, "Company": hit["Name"],
                         "Ticker": hit.get("Ticker", ""), "CIK": cik, **r})
        added += 1

    existing.sort(key=lambda r: (int(r["IID"]), str(r["FilingDate"])), reverse=False)
    _write(config.DEALS_CSV, DEAL_COLS, existing)
    return {"status": "ok", "added": added, "found": len(rows),
            "message": f"{hit['Name']}: {len(rows)} deal filings, added {added}."}


def get_all_deals() -> dict:
    out = [get_deals(int(c["IID"])) for c in read_companies()]
    return {"companies": len(out),
            "added": sum(r.get("added", 0) for r in out), "detail": out}


# ----------------------------------------------------------- counterparties
CP_COLS = ["IID", "Company", "Ticker", "FilingDate", "Item", "EventType",
           "AgreementType", "Counterparty", "Method", "Accession", "FilingURL"]


def read_counterparties() -> list[dict]:
    return _read(config.COUNTERPARTY_CSV, CP_COLS)


def get_counterparties(iid: int, limit: int | None = None) -> dict:
    """Parse counterparty names out of a company's 8-K deal filings.

    SEC guidance requires Item 1.01 filings to carry a brief description of
    the agreement's material terms -- incorporation by reference alone does
    not satisfy it -- so the body names the other party. The exhibit table
    is more regular still: "<Type> Agreement, dated <date>, by and between
    A and B".

    One HTTP fetch per filing, cached in bronze, so a re-run is free.
    """
    companies = read_companies()
    hit = next((c for c in companies if str(c.get("IID")) == str(iid)), None)
    if hit is None:
        return {"status": "no_such_iid", "added": 0,
                "message": f"IID {iid} is not in companies.csv."}

    filings = [d for d in read_deals() if str(d["IID"]) == str(iid)]
    if not filings:
        return {"status": "no_deals", "added": 0,
                "message": f"No deal filings for IID {iid}. Run: python cli.py deals {iid}"}

    filings.sort(key=lambda r: str(r["FilingDate"]), reverse=True)
    if limit:
        filings = filings[:limit]

    existing = read_counterparties()
    seen = {(str(r["IID"]), r["Accession"], r["Counterparty"].lower())
            for r in existing}

    added, parsed, empty = 0, 0, 0
    for f in filings:
        url = f.get("FilingURL") or ""
        if not url or not url.lower().endswith((".htm", ".html", ".txt")):
            continue
        text = counterparty.fetch_text(url)
        if not text:
            continue
        parsed += 1
        found = counterparty.extract(text, hit["Name"])
        if not found:
            empty += 1
            continue
        for r in found:
            k = (str(iid), f["Accession"], r["Counterparty"].lower())
            if k in seen:
                continue
            seen.add(k)
            existing.append({
                "IID": int(iid), "Company": hit["Name"],
                "Ticker": hit.get("Ticker", ""),
                "FilingDate": f.get("FilingDate"), "Item": f.get("Item"),
                "EventType": f.get("EventType"),
                "AgreementType": r["AgreementType"],
                "Counterparty": r["Counterparty"], "Method": r["Method"],
                "Accession": f.get("Accession"), "FilingURL": url,
            })
            added += 1

    existing.sort(key=lambda r: (int(r["IID"]), str(r["FilingDate"])))
    _write(config.COUNTERPARTY_CSV, CP_COLS, existing)
    rate = f"{100*(parsed-empty)/parsed:.0f}%" if parsed else "n/a"
    return {"status": "ok", "added": added, "parsed": parsed,
            "message": f"{hit['Name']}: {parsed} filings read, {added} "
                       f"counterparties, {rate} hit rate."}


def get_all_counterparties(limit: int | None = None) -> dict:
    out = [get_counterparties(int(c["IID"]), limit) for c in read_companies()]
    return {"companies": len(out),
            "added": sum(r.get("added", 0) for r in out), "detail": out}


# ------------------------------------------------------ universe ingest
def ingest_universe(limit: int = 50) -> dict:
    """Ingest the next `limit` not-yet-added universe members.

    Per member: registry row (identity from universe.csv + submissions),
    then financials (CompanyFacts), clinical trials (CT.gov by name),
    FDA events (openFDA with name variants), and deal filings (8-K
    index). Prices are fetched lazily by study/features, not here.
    Resume-safe: members already in companies.csv (by CIK) are skipped,
    so repeated runs walk through the universe in tranches. Delisted
    members may lack a ticker; price-dependent features stay blank for
    them by design -- their LABELS need no prices.
    """
    import csv as _csv
    upath = config.SILVER / "universe.csv"
    if not upath.exists():
        return {"status": "empty", "message": "Run `universe` first."}
    with upath.open(encoding="utf-8") as f:
        members = list(_csv.DictReader(f))

    companies = read_companies()
    have = {str(c.get("CIK", "")).lstrip("0") for c in companies}
    next_iid = max((int(c["IID"]) for c in companies), default=-1) + 1

    todo = [m for m in members if str(m["CIK"]).lstrip("0") not in have]
    if not todo:
        return {"status": "ok", "message": "Universe fully ingested."}
    batch = todo[:limit]

    done = 0
    for m in batch:
        cik10 = str(m["CIK"]).zfill(10)
        ticker = (m.get("Tickers") or "").split(";")[0].strip()
        row = {
            "IID": next_iid, "Name": m["Name"], "Ticker": ticker,
            "Created": date.today().isoformat(), "Description": "",
            "CIK": cik10, "SIC": m.get("SIC", ""), "SICDescription": "",
            "Exchange": (m.get("Exchanges") or "").split(";")[0].strip(),
            "StateOfIncorporation": "", "FDAAliases": "", "CTGovName": "",
        }
        companies.append(row)
        _write(config.COMPANIES_CSV, COMPANY_COLS, companies)
        iid = next_iid
        next_iid += 1
        parts = []
        for fn, label in ((get_financials, "fin"), (get_trials, "trials"),
                          (get_events, "events"), (get_deals, "deals")):
            try:
                r = fn(iid)
                parts.append(f"{label}:{'ok' if r.get('status') != 'error' else 'err'}")
            except Exception as exc:
                parts.append(f"{label}:EXC({type(exc).__name__})")
        done += 1
        print(f"  [{done}/{len(batch)}] {m['Name'][:38]:<40} "
              f"{'DELISTED ' if m.get('Delisted') else ''}{' '.join(parts)}",
              flush=True)

    remaining = len(todo) - len(batch)
    return {"status": "ok",
            "message": f"Ingested {done} members ({remaining} remaining). "
                       f"Re-run `ingest` for the next tranche."}


# ---------------------------------------------------- CRSP integration
def crsp_import(path_str: str) -> dict:
    """Load a CRSP daily export and write silver/crsp_prices.csv keyed to
    universe tickers: Date, Ticker, AdjPrice, SharesOut(thousands->raw).
    The features builder prefers this file over Yahoo when present, which
    removes the delisting-survivorship channel at the source."""
    import csv as _c
    from pathlib import Path
    src = Path(path_str)
    if not src.exists():
        return {"status": "error", "message": f"File not found: {src}"}
    with (config.SILVER / "companies.csv").open(encoding="utf-8") as f:
        tickers = {(-r or "") for r in []}  # placeholder
    with (config.SILVER / "companies.csv").open(encoding="utf-8") as f:
        known = {c["Ticker"].upper() for c in _c.DictReader(f) if c.get("Ticker")}
    out = config.SILVER / "crsp_prices.csv"
    n_in = n_keep = 0
    with src.open(encoding="utf-8", errors="replace") as f, \
         out.open("w", newline="", encoding="utf-8") as g:
        rd = _c.DictReader(f)
        cols = {c.lower(): c for c in (rd.fieldnames or [])}
        def col(*names):
            for n in names:
                if n in cols:
                    return cols[n]
            return None
        c_date = col("date", "caldt")
        c_tick = col("ticker", "htick", "tsymbol")
        c_prc = col("prc", "price")
        c_shr = col("shrout", "shr")
        if not (c_date and c_tick and c_prc):
            return {"status": "error",
                    "message": f"Unrecognized columns: {rd.fieldnames}. "
                               "Export must include date, TICKER, PRC "
                               "(SHROUT optional)."}
        w = _c.writer(g)
        w.writerow(["Date", "Ticker", "AdjPrice", "SharesOut"])
        for r in rd:
            n_in += 1
            t = (r.get(c_tick) or "").strip().upper()
            if not t or t not in known:
                continue
            try:
                p = abs(float(r.get(c_prc) or 0))
            except ValueError:
                continue
            if not p:
                continue
            d = (r.get(c_date) or "").strip()
            if "/" in d:                      # mm/dd/yyyy -> iso
                m, dd, y = d.split("/")
                d = f"{int(y):04d}-{int(m):02d}-{int(dd):02d}"
            sh = ""
            if c_shr and r.get(c_shr):
                try:
                    sh = str(int(float(r[c_shr]) * 1000))  # thousands
                except ValueError:
                    sh = ""
            w.writerow([d, t, f"{p:.4f}", sh])
            n_keep += 1
    return {"status": "ok",
            "message": f"CRSP import: {n_keep} rows kept of {n_in} "
                       f"({len(known)} universe tickers matched against) "
                       f"-> {out}. Re-run `features` to rebuild price "
                       "features survivorship-free, then `develop`."}


# ---------------------------------------------------- 10-K text (Phase D)
import re
TENK_DIR = config.BRONZE / "tenk_text"

_D = r"[.:\-\u2013\u2014\u00b7]?"          # ., :, -, en/em dash, mid-dot
ITEM1_START = re.compile(
    r"(?is)item\s*1\s*" + _D + r"\s*business|"
    r"item\s*4\s*" + _D + r"\s*information\s+on\s+the\s+compan")
ITEM_NEXT = re.compile(
    r"(?is)item\s*1A\s*" + _D + r"\s*risk\s*factors|"
    r"item\s*2\s*" + _D + r"\s*propert|"
    r"item\s*4A\s*" + _D + r"|item\s*5\s*" + _D + r"\s*operat|"
    r"item\s*3\s*" + _D + r"\s*key\s+information")


def extract_item1(text: str, cap: int = 60000) -> str:
    """Item 1 (Business) slice from a 10-K's stripped text. The first
    Item-1 hit is usually the table of contents; take the LAST start
    match before the first next-item match that follows it."""
    starts = [m.start() for m in ITEM1_START.finditer(text[:400000])]
    if not starts:
        return ""
    for s in reversed(starts):
        m = ITEM_NEXT.search(text, s + 200)
        if m and m.start() - s > 2000:
            return text[s:m.start()][:cap]
    return text[starts[-1]:starts[-1] + cap]


def text_ingest(limit: int = 100) -> dict:
    """Fetch Item-1 text for the next `limit` (company, fiscal-year)
    pairs not yet stored. One file per CIK-year under bronze/tenk_text."""
    import csv as _csv
    from .sources.counterparty import fetch_text
    from .labels import _submissions, _filings_reaching
    TENK_DIR.mkdir(parents=True, exist_ok=True)
    with config.COMPANIES_CSV.open(encoding="utf-8") as f:
        comps = list(_csv.DictReader(f))
    done = fetched = skipped = 0
    for c in comps:
        if fetched >= limit:
            break
        cik10 = str(c.get("CIK", "")).zfill(10)
        if not cik10.strip("0"):
            continue
        try:
            quads = _filings_reaching(cik10, "2013-01-01")
        except Exception:
            continue
        by_year = {}
        for f_, d_, acc, doc in quads:
            if f_ in ("10-K", "10-K405", "10-KSB", "20-F") and doc and d_ >= "2001-01-01":
                by_year.setdefault(d_[:4], (d_, acc, doc))
        for yr, (d_, acc, doc) in sorted(by_year.items()):
            out = TENK_DIR / f"{cik10}_{yr}.txt"
            if out.exists():
                done += 1
                continue
            if fetched >= limit:
                break
            url = (f"https://www.sec.gov/Archives/edgar/data/"
                   f"{int(cik10)}/{acc.replace('-', '')}/{doc}")
            raw = fetch_text(url)
            fetched += 1
            if fetched % 20 == 0:
                print(f"  text-ingest: {fetched} fetched this tranche "
                      f"({done} already stored, {skipped} unparsable)",
                      flush=True)
            item1 = extract_item1(raw or "")
            if len(item1) < 1500:
                skipped += 1
                out.write_text("", encoding="utf-8")   # tombstone
                continue
            out.write_text(item1, encoding="utf-8")
    total = len(list(TENK_DIR.glob("*.txt")))
    return {"status": "ok",
            "message": f"text-ingest tranche: {fetched} fetched, "
                       f"{skipped} unparsable, {done} pre-existing skips; "
                       f"{total} CIK-year files stored. Re-run for the "
                       f"next tranche."}
