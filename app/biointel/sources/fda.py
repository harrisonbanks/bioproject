"""openFDA. Port of the Events Power Query.

Two endpoints, because drugsfda carries no rejections (a search on
submission_status:"CR" returns zero records):
  drugsfda.json   -> approvals
  transparency/crl.json -> rejections

Both are keyed on a free-text company name. Verification uses exact
equality of the canonicalized name, so another company's records cannot
enter the result.
"""
from __future__ import annotations
from datetime import date, datetime

from .. import config
from ..match import canon
from ..store import fetch_json

COLUMNS = ["Event", "Date", "AppNo", "Drug", "Outcome",
           "Priority", "ClassCode", "SubType"]


def _get(url: str, search: str, tag: str):
    try:
        return fetch_json(url, params={"search": search, "limit": "1000"}, tag=tag)
    except Exception:
        return None


def rejections(key: str) -> list[dict]:
    """CRLs for a canonicalized company name."""
    if not key:
        return []
    data = _get(config.FDA_CRL, f'company_name:"{key}"', "fda_crl")
    rows = []
    for r in (data or {}).get("results", []) or []:
        if canon(r.get("company_name")) != key:
            continue
        try:
            d = datetime.strptime(r["letter_date"], "%m/%d/%Y").date()
        except Exception:
            continue
        apps = r.get("application_number") or []
        appno = "; ".join(str(a) for a in apps)
        appno = appno.split("/")[0].strip() or None      # drop "/Original n"
        st = r.get("approval_status")
        outcome = ("Never approved" if st == "Unapproved"
                   else "Later approved" if st == "Approved"
                   else (str(st) if st else None))
        rows.append({"Event": "Rejection", "Date": d, "AppNo": appno,
                     "Drug": None, "Outcome": outcome, "Priority": None,
                     "ClassCode": r.get("letter_type"), "SubType": None})
    return rows


def approvals(key: str) -> list[dict]:
    """Approvals for a canonicalized company name.

    Keeps submission_status == 'AP' and (SubType == 'ORIG' or
    ClassCode == 'EFFICACY'). Discards LABELING and MANUF (CMC), which are
    administrative filings, not market events.
    """
    if not key:
        return []
    data = _get(config.FDA_DRUGSFDA, f'sponsor_name:"{key}"', "fda_drugsfda")
    rows = []
    for app in (data or {}).get("results", []) or []:
        if canon(app.get("sponsor_name")) != key:
            continue
        prods = app.get("products") or []
        drug = prods[0].get("brand_name") if prods else None
        for sub in app.get("submissions", []) or []:
            if sub.get("submission_status") != "AP":
                continue
            raw_date = sub.get("submission_status_date")
            if not raw_date:
                continue
            subtype = sub.get("submission_type")
            classcode = sub.get("submission_class_code")
            if not (subtype == "ORIG" or classcode == "EFFICACY"):
                continue
            try:
                d = datetime.strptime(str(raw_date), "%Y%m%d").date()
            except Exception:
                continue
            rows.append({
                "Event": "Approval", "Date": d,
                "AppNo": app.get("application_number"),
                "Drug": drug,
                "Outcome": "New drug" if subtype == "ORIG" else "New indication",
                "Priority": sub.get("review_priority"),
                "ClassCode": classcode, "SubType": subtype,
            })
    return rows


# Drugs@FDA sponsor strings abbreviate corporate descriptors. Generate
# search variants from the SEC registrant name so mid-caps match without
# hand-curated aliases: "ALNYLAM PHARMACEUTICALS, INC." is filed by FDA
# as "ALNYLAM PHARMS INC"; "ACADIA PHARMACEUTICALS INC" as "ACADIA
# PHARMS INC". Verification stays exact-canonical per variant.
_ABBREV = [("PHARMACEUTICALS", "PHARMS"), ("PHARMACEUTICAL", "PHARM"),
           ("LABORATORIES", "LABS"), ("THERAPEUTICS", "THERAP"),
           ("BIOSCIENCES", "BIOSCI"), ("TECHNOLOGIES", "TECHS")]
_SUFFIX = (" INC", " CORP", " CO", " LTD", " PLC", " HOLDINGS", " GROUP")


def name_variants(name: str) -> list[str]:
    base = canon(name)
    if not base:
        return []
    out = [base]
    for long, short in _ABBREV:
        if long in base:
            out.append(base.replace(long, short))
    more = []
    for v in out:
        stripped = v
        for suf in _SUFFIX:
            if stripped.endswith(suf):
                stripped = stripped[: -len(suf)].strip()
        if stripped and stripped != v:
            more.append(stripped)
        first = v.split()[0]
        if len(first) >= 6:                      # distinctive single token
            more.append(first)
    return list(dict.fromkeys(out + more))


def events_for(iid: int, name: str, aliases: list[str] | None = None) -> list[dict]:
    """All FDA events for one company. Deduped on (Event, Date, AppNo),
    matching Table.Distinct in the M query.

    aliases -- extra FDA sponsor names to search, because FDA uses trade
    names where SEC uses legal registrant names (JANSSEN vs JOHNSON &
    JOHNSON). Each alias is searched separately and results are unioned.
    Verification still requires exact canonical equality against the alias
    that was searched, so contamination remains impossible.
    """
    keys = name_variants(name) + [canon(a) for a in (aliases or [])]
    keys = [k for k in dict.fromkeys(keys) if k]      # dedupe, drop blanks
    rows = []
    for k in keys:
        rows += rejections(k) + approvals(k)
    seen, out = set(), []
    for r in rows:
        k = (r["Event"], r["Date"], r["AppNo"])
        if k in seen:
            continue
        seen.add(k)
        out.append({"IID": iid, "Name": name, **r})
    out.sort(key=lambda r: r["Date"], reverse=True)
    return out
