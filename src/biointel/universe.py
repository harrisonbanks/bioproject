"""P1a: rule-defined company universe from EDGAR.

THE RULE (stated once, applied mechanically, cited in the paper):
  A company is a universe candidate iff
    * SEC standard industrial classification 2836 (Biological Products)
      or 2834 (Pharmaceutical Preparations), per EDGAR's company index;
    * it filed at least one annual report (10-K or 20-F) dated
      2013-01-01 or later (operating company, in-window);
    * its submissions record shows a NYSE or Nasdaq listing (past or
      present -- DELISTED COMPANIES ARE KEPT; membership is dated at
      entry, and their delisting is the label, not an exclusion).
  A market-cap floor, if applied, is applied at analysis time from
  ingested data and reported as a sensitivity, never silently at
  ingestion (a floor at ingestion would re-introduce survivorship on
  size).

SOURCE ENDPOINTS.
  Candidate list: EDGAR company browse by SIC, atom output, paginated:
    https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany
        &SIC={sic}&type=10-K&owner=include&count=100&start={n}&output=atom
  Detail per CIK: data.sec.gov/submissions/CIK{cik10}.json
    (already the pipeline's standard source; carries tickers, exchanges,
    every filing form+date -- retained by EDGAR after delisting).

HONESTY FLAG: the browse-edgar atom endpoint is UNTESTED from the build
environment (sec.gov unreachable here). `universe-probe` exists for
exactly that reason: it fetches ONE page, prints the raw head and the
parse result, and the full `universe` build refuses to run until a probe
has succeeded on this machine. Patterns get fixed against real output,
never assumed -- the counterparty rewrite earned that rule.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from biointel import config
from biointel.store import fetch_json

log = logging.getLogger(__name__)

BROWSE = (
    config.SEC_BROWSE + "&SIC={sic}&type=10-K&owner=include&count=100&start={start}&output=atom"
)
SICS = ("2836", "2834")
WINDOW_START = "2001-01-01"
ANNUAL_FORMS = {"10-K", "10-K/A", "10-K405", "10-K405/A", "10-KSB", "10-KSB/A", "20-F", "20-F/A"}
FORM25 = {"25", "25/A", "25-NSE", "25-NSE/A"}  # exchange-specific
FORM15 = {"15-12B", "15-12G", "15-15D"}  # deregistration (OTC too)
DELIST_FORMS = FORM25 | FORM15
EXCH_RE = re.compile(r"(?i)nyse|nasdaq")

UNIVERSE_COLS = [
    "CIK",
    "Name",
    "Tickers",
    "Exchanges",
    "SIC",
    "FirstAnnualInWindow",
    "LastFilingDate",
    "Delisted",
    "DelistEvidence",
    "InDevSet",
    "InclusionRule",
    "EntryDate",
]

PROBE_MARKER = config.BRONZE / "sec_browse" / "PROBE_OK"


def _fetch_atom(sic: str, start: int) -> str:
    url = BROWSE.format(sic=sic, start=start)
    raw = fetch_json(url, tag="sec_browse", raw_text=True)
    return raw if isinstance(raw, str) else str(raw)


FEED_JUNK_RE = re.compile(
    r"(?i)company search|search feed|search results|"
    r"^edgar\b|webmaster"
)


def _clean_name(v: str) -> str:
    v = (v or "").strip()
    if not v or v.startswith("ARRAY(") or FEED_JUNK_RE.search(v):
        return ""
    return re.sub(r"\s*\(.*?\)\s*$", "", v).strip()


def parse_atom(xml_text: str) -> list[dict]:
    """(cik, name) entries from one browse-edgar atom page.

    REAL page shape (from the main-machine probe of 2026-08-24): the
    entry title and company-info name ATTRIBUTES are Perl serialization
    artifacts ("ARRAY(0x...)"); the data lives in child ELEMENTS --
    <cik>0001848948</cik> and <conformed-name>...</conformed-name>.
    Name may be absent from a block; the build step then fills it from
    the submissions record. Parsed per <entry> block by regex because
    the feed's declared ISO-8859-1 payload is not reliably well-formed.
    """
    out, seen = [], set()
    for block in re.split(r"(?i)<entry[ >]", xml_text)[1:]:
        cm = re.search(r"<cik>\s*0*(\d{4,10})\s*</cik>", block) or re.search(
            r"CIK=(\d{4,10})", block
        )
        if not cm:
            continue
        cik = cm.group(1).zfill(10)
        if cik in seen:
            continue
        name = ""
        for pat in (
            r"<conformed-name>([^<]{2,150})</conformed-name>",
            r"<company-name>([^<]{2,150})</company-name>",
            r'name="([^"]{2,150})"',
            r"<title>([^<]{2,150})</title>",
        ):
            m = re.search(pat, block)
            if m and _clean_name(m.group(1)):
                name = _clean_name(m.group(1))
                break
        seen.add(cik)
        out.append({"cik": cik, "name": name})
    return out


def probe() -> dict:
    """Fetch ONE page for SIC 2836 and show exactly what came back."""
    try:
        raw = _fetch_atom("2836", 0)
    except Exception as exc:
        return {
            "status": "fail",
            "message": f"FETCH FAILED: {exc}. browse-edgar unreachable "
            "or blocked; paste this output back.",
        }
    head = raw[:1800].replace("\n", " ")
    entries = parse_atom(raw)
    named = sum(1 for e in entries if e["name"])
    if len(entries) >= 20:
        PROBE_MARKER.parent.mkdir(parents=True, exist_ok=True)
        PROBE_MARKER.write_text(date.today().isoformat())
        sample = "; ".join(
            f"{e['name'] or '(name-from-submissions)'} [{e['cik']}]" for e in entries[:5]
        )
        return {
            "status": "ok",
            "message": f"PARSE OK: {len(entries)} companies on page 1 "
            f"({named} with inline names). Sample: {sample}. "
            "`universe` is now unlocked.",
        }
    return {
        "status": "fail",
        "message": "PARSE FAILED. Raw head follows -- paste this whole "
        f"output back so the parser is fixed on real data:\n{head}",
    }


def _submission_detail(cik10: str) -> dict:
    try:
        data = fetch_json(config.SEC_SUBS.format(cik10=cik10), tag="sec_submissions")
    except Exception:
        return {}
    rec = (data.get("filings") or {}).get("recent") or {}
    forms = rec.get("form", [])
    dates = rec.get("filingDate", [])
    annual = sorted(d for f, d in zip(forms, dates) if f in ANNUAL_FORMS and d >= WINDOW_START)
    last = max(dates) if dates else ""
    delist_forms = [f for f in forms if f in DELIST_FORMS]
    form25 = [f for f in delist_forms if f in FORM25]
    stale = last and (date.today() - date.fromisoformat(last)).days > 400
    return {
        "entity_name": str(data.get("name") or ""),
        "tickers": "; ".join(data.get("tickers") or []),
        "exchanges": "; ".join(x for x in (data.get("exchanges") or []) if x),
        "sic": str(data.get("sic") or ""),
        "first_annual": annual[0] if annual else "",
        "last_filing": last,
        "delisted": bool(delist_forms) and bool(stale),
        "was_exchange_listed": bool(form25),
        "delist_evidence": (
            "; ".join(sorted(set(delist_forms))[:3]) + ("; stale" if stale else "")
        ).strip("; "),
    }


def build(read_companies, max_pages_per_sic: int = 40, detail_limit: int | None = None) -> dict:
    """Full universe build. Refuses to run before a successful probe."""
    if not PROBE_MARKER.exists():
        return {
            "status": "blocked",
            "message": "Run `python -m biointel universe-probe` first; the "
            "browse-edgar parser must succeed on real output "
            "before a full build.",
        }
    dev_ciks = {str(c.get("CIK", "")).lstrip("0") for c in read_companies()}

    candidates: dict[str, dict] = {}
    for sic in SICS:
        for page in range(max_pages_per_sic):
            try:
                raw = _fetch_atom(sic, page * 100)
            except Exception:
                break
            entries = parse_atom(raw)
            if not entries:
                break
            for e in entries:
                candidates.setdefault(e["cik"], {"name": e["name"], "sic_seen": sic})
            log.info(f"  SIC {sic} page {page + 1}: {len(candidates)} unique candidates so far")
    rows, checked = [], 0
    for cik10, base in sorted(candidates.items()):
        pass_name = base["name"]
        if detail_limit is not None and checked >= detail_limit:
            break
        checked += 1
        if checked % 50 == 0:
            log.info(
                f"  screening {checked}/{len(candidates)}: {len(rows)} members admitted so far"
            )
        d = _submission_detail(cik10)
        if d and not pass_name:
            pass_name = d.get("entity_name", "")
        base["name"] = pass_name
        if not d or not d["first_annual"]:
            continue  # no in-window annual report
        listed_now = bool(EXCH_RE.search(d["exchanges"] or ""))
        was_listed = bool(d.get("was_exchange_listed"))  # Form 25 family only
        if not (listed_now or was_listed):
            continue  # never on a national exchange
        rows.append(
            {
                "CIK": cik10,
                "Name": base["name"],
                "Tickers": d["tickers"],
                "Exchanges": d["exchanges"],
                "SIC": d["sic"] or base["sic_seen"],
                "FirstAnnualInWindow": d["first_annual"],
                "LastFilingDate": d["last_filing"],
                "Delisted": "yes" if d["delisted"] else "",
                "DelistEvidence": d["delist_evidence"],
                "InDevSet": "yes" if cik10.lstrip("0") in dev_ciks else "",
                "InclusionRule": f"SIC {'/'.join(SICS)}; annual>={WINDOW_START}; "
                "NYSE/Nasdaq; delisted kept",
                "EntryDate": d["first_annual"],
            }
        )

    import csv as _csv

    path = config.SILVER / "universe.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=UNIVERSE_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    n_del = sum(1 for r in rows if r["Delisted"])
    return {
        "status": "ok",
        "message": f"{len(rows)} universe members -> {path} "
        f"({len(candidates)} SIC candidates screened, "
        f"{n_del} delisted kept, "
        f"{sum(1 for r in rows if r['InDevSet'])} in dev set).",
    }
