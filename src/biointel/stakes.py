# C:\Users\JB\Documents\dev\bioindustry\src\biointel\stakes.py
"""Gate F1: equity stakes from SEC 13D/13G (Data-Feeder Roadmap §F1).

STAGE 1 ONLY — the probe (rule 4.20: real captures before any parser).
`stakes probe` fetches a small spread of SC 13D / SC 13D/A / SC 13G /
SC 13G/A filings about universe members across four filing eras into the
research library (honest provenance: source_system/tool "stakes-probe"),
writes ONE inspection bundle (data/exports/stakes_probe_bundle.txt: a
manifest line plus the full normalized text of every captured document,
each truncated at BUNDLE_CHARS), records a ledger run, and STOPS. The
extraction rules, the collector at scale, and the measurement loop are
written only after the operator attaches that bundle and the captures
have been read — never against guessed document shapes.

ERAS (why four): cover-page conventions drifted over two decades and the
SEC mandated a structured (XML) 13D/G format for filings from late 2024,
so the parser must be written against at least one real specimen of each
convention it will meet. The probe records each document's served
content type and extension for exactly that reason.

Decisions of record (2026-09-02, Q1–Q5 approved): collection is
per-member EFTS on the universe registry (Q1); the equity_stakes table
gains seven optional columns at SCHEMA_VERSION 0.11 (Q2 — lands with the
parser stage, not the probe); stake rows are stored for every owner,
registry stubs only from an operator-approved list (Q3); the amendment
chain is written faithfully including exits, the matcher's "ever held"
shortcut is a documented defect for aspect-match v2 (Q4); precision is
measured on a blind sample of 60 rows, a row passing only when owner,
subject, percent and event date all match the filing (Q5). Standing
design basis: record to the analyst's standard, not to what today's
code consumes.
"""

from __future__ import annotations

import logging
import re as _re
import time

import requests

from biointel import config, library, results, store
from biointel.efts import _headers, hits_of, normalize_text, search

log = logging.getLogger(__name__)

STAKE_FORMS = "SC 13D,SC 13D/A,SC 13G,SC 13G/A"
# The structured-filing era renamed the submission types; whether these names
# return hits is exactly what the era-4 probe verifies against real captures.
STRUCTURED_FORMS = "SCHEDULE 13D,SCHEDULE 13D/A,SCHEDULE 13G,SCHEDULE 13G/A"
# Every 13D/13G cover page carries this phrase; EFTS requires a query term,
# and this one selects nothing beyond the form filter's own population.
PROBE_QUERY = '"beneficially owned"'
ERAS = (
    ("2003-01-01", "2008-12-31"),
    ("2012-01-01", "2016-12-31"),
    ("2020-01-01", "2023-12-31"),
    ("2025-01-01", "2026-09-02"),
)
PER_ERA_CAPTURES = 3
COMPANIES_TRIED_PER_ERA = 12
BUNDLE_CHARS = 40_000
BUNDLE_NAME = "stakes_probe_bundle.txt"


def _member_ciks() -> list[tuple[str, str, str]]:
    """(cik, ticker, name) for every registry company with a CIK, IID order —
    deterministic, no hand-picked names in code."""
    out = []
    for c in sorted(store.read_table("companies"), key=lambda r: int(r["IID"])):
        cik = str(c.get("CIK") or "").strip()
        if cik:
            out.append((cik, str(c.get("Ticker") or ""), str(c.get("Name") or "")))
    return out


def _fetch(url: str) -> tuple[bytes, str, str] | None:
    """Backoff fetch returning (bytes, ext, content_type); the served content
    type is evidence the parser stage needs (the structured era serves XML)."""
    for attempt, pause in enumerate((0, 5, 15, 45)):
        if pause:
            time.sleep(pause)
        time.sleep(config.SEC_RATE_LIMIT)
        try:
            r = requests.get(url, headers=_headers(), timeout=60)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            ext = {
                "application/pdf": ".pdf",
                "text/plain": ".txt",
                "application/xml": ".xml",
                "text/xml": ".xml",
            }.get(ctype, ".htm")
            return r.content, ext, ctype
        if r.status_code in (429, 500, 502, 503, 504):
            continue
        return None
    return None


def _capture(hit: dict, con) -> tuple[str, str, str] | None:
    """Capture one filing into the library with stakes-probe provenance;
    returns (capture_sha, ext, content_type). Re-captures nothing: an
    existing active capture of the same URL is reused."""
    if not hit["url"]:
        return None
    if store.has_table("references", con):
        for r in store.read_table("references", con=con):
            if r["url"] == hit["url"]:
                for c in store.read_table("captures", con=con):
                    if c["ref_id"] == r["ref_id"] and c["status"] == "active":
                        return c["capture_id"], "." + str(c.get("ext") or "htm"), "cached"
    got = _fetch(hit["url"])
    if not got:
        return None
    data, ext, ctype = got
    ref_id, _ = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": hit["adsh"],
            "url": hit["url"],
            "title": f"{hit['name']} {hit['form']} {hit['file_date']}".strip(),
            "publisher": "SEC EDGAR",
            "published_at": hit["file_date"],
            "source_system": "stakes-probe",
            "source_key": f"{hit['adsh']}:{hit['doc']}",
            "note": f"captured by stakes-probe;form={hit['form']};cik={hit['cik']}",
        },
        con,
    )
    sha, dst, _new = library.put_bytes(data, ext)
    library.add_capture(ref_id, sha, dst, "fetched_html", "stakes-probe", con)
    if hit["cik"]:
        library.add_link(ref_id, "CIK", hit["cik"], "subject", con)
    return sha, ext, ctype


def probe() -> int:
    """Capture up to PER_ERA_CAPTURES filings per era, preferring distinct
    forms within an era so amendments and originals both appear; bundle
    every captured document's text into one attachable file; record the
    run; stop."""
    con = store.connect()
    manifest: list[str] = []
    bundle: list[str] = []
    captured = 0
    for start, end in ERAS:
        era_hits: list[dict] = []
        form_lists = [STAKE_FORMS]
        if end >= "2025-01-01":
            form_lists.append(STRUCTURED_FORMS)  # era-4 finding: old names returned nothing
        for forms in form_lists:
            for cik, ticker, name in _member_ciks()[:COMPANIES_TRIED_PER_ERA]:
                payload = search(PROBE_QUERY, forms, start, end, cik=cik)
                hits = [h for h in hits_of(payload) if h["url"]]
                if payload.get("error"):
                    manifest.append(
                        f"  era {start[:4]}-{end[:4]} cik {cik} ({ticker}): "
                        f"EFTS error {payload['error']}"
                    )
                era_hits.extend(hits)
                if len({h["form"] for h in era_hits}) >= PER_ERA_CAPTURES:
                    break
            if era_hits:
                break
        if not era_hits:
            manifest.append(
                f"  era {start[:4]}-{end[:4]}: 0 hits across {COMPANIES_TRIED_PER_ERA} "
                f"companies and {len(form_lists)} form-name sets — coverage hole, a finding"
            )
        # prefer one hit per distinct form, then fill by date order
        picked: list[dict] = []
        for form in (
            "SC 13D",
            "SC 13G",
            "SC 13D/A",
            "SC 13G/A",
            "SCHEDULE 13D",
            "SCHEDULE 13G",
            "SCHEDULE 13D/A",
            "SCHEDULE 13G/A",
        ):
            for h in era_hits:
                if h["form"] == form and len(picked) < PER_ERA_CAPTURES:
                    picked.append(h)
                    break
        for h in era_hits:
            if h not in picked and len(picked) < PER_ERA_CAPTURES:
                picked.append(h)
        for h in picked:
            got = _capture(h, con)
            if not got:
                manifest.append(f"  FETCH-FAILED {h['form']} {h['file_date']} {h['url']}")
                continue
            sha, ext, ctype = got
            captured += 1
            line = (
                f"  {h['form']:<9} filed {h['file_date']}  about-cik {h['cik']} "
                f"({h['name'][:40]})  ext {ext} ctype {ctype}  sha {sha[:12]}"
            )
            manifest.append(line)
            p = library.store_path(sha, ext)
            try:
                text = normalize_text(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                text = "(unreadable as text; binary capture — inspect in the library)"
            bundle.append(
                "=" * 78 + f"\nCAPTURE {sha}  {h['form']}  filed {h['file_date']}  "
                f"url {h['url']}\n" + "=" * 78 + "\n" + text[:BUNDLE_CHARS]
            )
    head = [
        f"STAKES PROBE — {captured} filings captured across {len(ERAS)} eras "
        f"(forms {STAKE_FORMS}; query {PROBE_QUERY})"
    ]
    head.extend(manifest)
    out_text = "\n".join(head) + "\n\n" + "\n\n".join(bundle) + "\n"
    p = store.write_export(BUNDLE_NAME, out_text)
    run = results.start(
        "stakes-probe",
        "stakes probe",
        ["companies"],
        {"forms": STAKE_FORMS, "eras": len(ERAS), "per_era": PER_ERA_CAPTURES},
    )
    run.metric("_", "captured", captured)
    run.metric("_", "manifest_lines", len(manifest))
    run.artefact(p)
    run_id = results.finish(run, note="rule 4.20 probe; parser written only against these captures")
    for line in head:
        log.info(line)
    log.info(f"bundle -> {p}")
    log.info(f"run {run_id} recorded")
    return 0 if captured else 1


def cli(argv: list[str]) -> int:
    sub = argv[0] if argv else ""
    if sub == "probe":
        return probe()
    if sub == "run":
        return run(argv[1] if len(argv) > 1 else "2001-01-01")
    if sub == "sample":
        return sample(int(argv[1]) if len(argv) > 1 else 60)
    if sub == "precision":
        return precision()
    print("usage: stakes probe|run [SINCE]|sample [N]|precision")
    return 1


# ---------------------------------------------------------------- cover-page parser (HTML eras)
# Rules written against the nine probe captures (rule 4.20); every pattern
# below exists because a specific capture required it, named in tests.
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_TEXT = _re.compile(rf"({_MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})")
_EVENT_BEFORE = _re.compile(
    rf"(({_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})\s*\(Date of Event Which Requires Filing",
    _re.IGNORECASE,
)
_EVENT_AFTER = _re.compile(
    rf"Date of Event Which Requires Filing of this Statement\s*:?\s*(({_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})",
    _re.IGNORECASE,
)
_ISSUER = _re.compile(r"([A-Za-z0-9&.,'()\- ]{3,80}?)\s*\(Name of Issuer\)", _re.IGNORECASE)
_ISSUER_AFTER = _re.compile(r"Name of issuer\s*:\s*(.{3,80}?)\s+Title of Class", _re.IGNORECASE)
_CUSIP_BEFORE = _re.compile(r"([0-9A-Z][0-9A-Za-z ]{5,14}?)\s*\(CUSIP Number\)", _re.IGNORECASE)
_CUSIP_AFTER = _re.compile(r"CUSIP Number\s*:\s*([0-9][0-9A-Za-z]{5,8})\b", _re.IGNORECASE)
_OWNER = _re.compile(
    r"Names?\s+of\s+Reporting\s+Persons?\b[.:]?\s*(?:\d{1,2}\s*[.:]?\s+)?"
    r"(?:S\.S\.\s+or\s+)?(?:I\.?R\.?S\.?\s+Identification\s+Nos?\.?\s+of\s+above\s+persons?"
    r"\s*(?:\(entities only\)|\[entities only\])?[.:]?\s*)?"
    r"(.{3,90}?)\s*(?:I\.R\.S\.|S\.S\.|###|\d{2}-\d{7}|-\s*\d{2}-|\d\s*\.?\s*Check\b|2\s+CHECK\b)",
    _re.IGNORECASE | _re.DOTALL,
)
_SHARES = _re.compile(
    r"Aggregate\s+Amount\s+Beneficially\s+Owned\s+by\s+Each\s+Reporting\s+Person"
    r".{0,300}?([0-9]{1,3}(?:,[0-9]{3})+)",
    _re.IGNORECASE | _re.DOTALL,
)
_PERCENT = _re.compile(
    r"Percent\s+of\s+Class\s+Represented\s+by\s+Amount\s+in\s+Row"
    r".{0,120}?\b([0-9]{1,2}(?:\.[0-9]{1,4})?)\s*%",
    _re.IGNORECASE | _re.DOTALL,
)
# r3 miss family: row 11 is often printed WITHOUT a "%" sign ("ROW 9 0.00",
# "ROW (9) 9.99", "-0-"). The window stops at the next row label so a blank
# row 11 never steals row 12's text.
# r6: the label is "Percent of Class Represented by" with an optional
# "Amount in/of Row (N)" tail (one specimen prints the value inside the
# label); the window is the next 400 characters, cut at the next row
# marker when one appears — explanations longer than the window no longer
# defeat the match.
_PERCENT_LABEL = _re.compile(
    r"Percent\s+of\s+Class\s+Represented\s+by\s+(?:Amount\s+(?:in|of)\s+)?(?:Row|Line|Item)?",
    _re.IGNORECASE,
)
_ROW_END = _re.compile(r"Type\s+of\s+Reporting|CUSIP\s+No|Item\s*1\b", _re.IGNORECASE)
_RULE_RUNS = _re.compile(r"[-_.=*~]{3,}")  # r5: dashed/dotted rule lines between rows
_CAPPED = _re.compile(r"\bup\s+to\b", _re.IGNORECASE)  # blocker caps are not holdings
_NONE_WORD = _re.compile(r"\bnone\b", _re.IGNORECASE)
_PCT_NUM = _re.compile(
    r"([0-9]{1,3}(?:\.[0-9]{1,10})?)\s*%|(-0-)|\b([0-9]{1,2}\.[0-9]{1,10})\b|\b(0\.00|0)\b"
)
# Item-4 style (old bank-holding 13Gs, the dominant miss family): no row
# table at all — "Percent of Class: 4.868%" / "Amount Beneficially Owned: N".
_QUALIFIED = _re.compile(
    r"(less\s+than|not\s+more\s+than|in\s+excess\s+of|under)\s*$|"
    r"(less\s+than|not\s+more\s+than|in\s+excess\s+of)\s+[0-9]",
    _re.IGNORECASE,
)
_PERCENT_ITEM = _re.compile(
    r"Percent\s+of\s+Class\s*:?\s*([0-9]{1,2}(?:\.[0-9]{1,4})?)\s*%", _re.IGNORECASE
)
_SHARES_ITEM = _re.compile(
    r"Amount\s+Beneficially\s+Owned\s*:?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})", _re.IGNORECASE
)
_ITEM4 = _re.compile(
    r"Item\s*4[.:]?\s*Purpose of Transaction(.*?)(?:Item\s*[5-9][.:]|SIGNATURE\b)",
    _re.IGNORECASE | _re.DOTALL,
)


def _iso(date_text: str) -> str:
    from datetime import datetime

    for fmt in ("%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(date_text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _percent_of(text: str) -> tuple[str | None, str]:
    """Row-11 percent with its evidence span, or (None, "") when the page
    states none — nothing is invented.

    Qualified statements ("Less than 5%", "Less than 1%") are EXIT filings:
    the holder reports falling below the threshold, which is a true dated
    fact the amendment chain must carry (decision of record), so they are
    written as 0 with the phrase kept verbatim in the span — never as the
    qualified number, which would record a holding the filing denies.
    "-0-" is likewise 0.
    """
    text = _RULE_RUNS.sub(" ", text)  # r5: rule lines between rows
    windows = []
    m = _PERCENT_LABEL.search(text)
    if m:
        tail = text[m.end() : m.end() + 400]
        cut = _ROW_END.search(tail)
        window = tail[: cut.start()] if cut else tail
        windows.append((window, m.group(0) + window))
    mi = _PERCENT_ITEM.search(text)
    if mi:
        windows.append((mi.group(0), mi.group(0)))
    for window, whole in windows:
        span = " ".join(whole.split())[:200]
        head = window[:80]
        if _CAPPED.search(head):
            return None, ""  # "Up to 9.99%" is a blocker cap, not a holding
        if _QUALIFIED.search(head):
            return "0", span
        pct_marked = [mm.group(1) for mm in _PCT_NUM.finditer(window) if mm.group(1)]
        if pct_marked:
            val = pct_marked[0]  # r5: the first %-marked number is the value;
            # explanatory parentheticals that follow carry other numbers
        else:
            if _NONE_WORD.search(head):
                return "0", span  # "NONE": the holder states no holding
            nums = [g for mm in _PCT_NUM.finditer(window) for g in mm.groups() if g]
            if not nums:
                continue
            if "-0-" in nums:
                return "0", span
            val = nums[-1]
            if val in ("9", "10", "11", "12") and len(nums) > 1:
                val = nums[-2]  # a leading row index is not the value
        try:
            f = float(val)
        except ValueError:
            continue
        if 0 <= f <= 100:
            return val, span
    return None, ""


def parse_cover(text: str) -> dict:
    """First-reporting-person cover-page extraction for the HTML eras
    (2001 up to the structured-format change). One row per filing, taken
    from the lead filer: in every probe capture the parent/lead entity is
    the first cover-page block (the analyst's fact, per the approved
    design). Returns {} when the load-bearing fields (owner and percent)
    are both absent — a not-a-cover-page guard, never a fabricated row."""
    out: dict = {}
    m = _ISSUER.search(text)
    if m:
        raw = " ".join(m.group(1).split())
        # amendment headers precede the name: keep only text after the last ")"
        out["issuer_name"] = raw.rsplit(")", 1)[-1].strip() or raw
    else:
        m = _ISSUER_AFTER.search(text)
        if m:
            out["issuer_name"] = " ".join(m.group(1).split())
    m = _EVENT_BEFORE.search(text) or _EVENT_AFTER.search(text)
    if m:
        out["event_date"] = _iso(m.group(1))
        out["event_span"] = " ".join(m.group(0).split())[:200]
    m = _CUSIP_BEFORE.search(text) or _CUSIP_AFTER.search(text)
    if m:
        out["cusip"] = m.group(1).replace(" ", "")
    m = _OWNER.search(text)
    if m:
        name = " ".join(m.group(1).split()).strip(" ,:;-")
        if name.endswith(".") and not _re.search(
            r"[A-Z]\.[A-Z]?\.$|Inc\.$|Ltd\.$|Co\.$|Corp\.$", name
        ):
            name = name[:-1]
        name = name.strip(" ,:;-")
        name = name.rstrip("( ").strip()  # 62d58af: trailing "(" before I.R.S. number
        out["owner_name"] = name
    m = _SHARES.search(text) or _SHARES_ITEM.search(text)
    if m:
        out["shares"] = m.group(1).replace(",", "")
        out["shares_span"] = " ".join(m.group(0).split())[:200]
    pct, pct_span = _percent_of(text)
    if pct is not None:
        out["percent"] = pct
        out["percent_span"] = pct_span
    m = _ITEM4.search(text)
    if m:
        out["item4_text"] = " ".join(m.group(1).split())[:20000]
    if "owner_name" not in out and "percent" not in out:
        return {}
    return out


# ---------------------------------------------------------------- structured-era (XML) parser
# r1 probe rules; r2 miss-analysis patterns (Item-4 style, wide row gap, row
# digit in owner label); r3 bare-number percents, "-0-", qualified exits as 0;
# r4 structured 13D tag set (percentOfClass, aggregateAmountOwned, issuerCIK,
# issuerCUSIP, dateOfEvent, reportingPersonCIK).
RULE_VERSION = "F1-r6"  # r6: window no longer needs a row terminator; value may precede "in Row"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_structured(xml_text: str) -> dict:
    """Structured-era parser, written against the three raw probe XMLs.
    Variances the captures forced: the CUSIP lives at issuerCusips/
    issuerCusipNumber (X0202) or flat issuerCusip (the 2025 BlackRock
    filing, which also omits schemaVersion); the owner CIK comes from
    headerData filerCredentials/cik — a field the HTML era never prints.
    First reportingPersonName is the lead filer (one row per filing, the
    approved rule). Unknown structured layouts return {} and are counted,
    never guessed."""
    import xml.etree.ElementTree as _ET

    try:
        root = _ET.fromstring(xml_text)
    except _ET.ParseError:
        return {}
    vals: dict[str, list[str]] = {}
    for el in root.iter():
        name = _local(el.tag)
        if el.text and el.text.strip():
            vals.setdefault(name, []).append(el.text.strip())

    def first(*names: str) -> str:
        for n in names:
            if vals.get(n):
                return vals[n][0]
        return ""

    out: dict = {}
    owner = first("reportingPersonName", "filingPersonName", "signatureReportingPerson")
    if owner:
        out["owner_name"] = owner
    cik = first("reportingPersonCIK", "cik")
    if cik:
        out["owner_cik"] = str(int(cik))
    icik = first("issuerCik", "issuerCIK")
    if icik:
        out["issuer_cik"] = str(int(icik))
    iname = first("issuerName")
    if iname:
        out["issuer_name"] = iname
    cusip = first("issuerCusipNumber", "issuerCusip", "issuerCUSIP")
    if cusip:
        out["cusip"] = cusip.replace(" ", "")
    ev = first("eventDateRequiresFilingThisStatement", "dateOfEvent")
    if ev and len(ev.split("/")) == 3:
        m, d, y = ev.split("/")
        out["event_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
        out["event_span"] = f"eventDateRequiresFilingThisStatement {ev}"
    shares = first(
        "reportingPersonBeneficiallyOwnedAggregateNumberOfShares",
        "amountBeneficiallyOwned",
        "aggregateAmountOwned",
    )
    if shares:
        out["shares"] = shares.replace(",", "")
    pct = first("classPercent", "percentOfClass")
    if pct:
        out["percent"] = pct
        out["percent_span"] = f"classPercent {pct}"
    item4 = first("purposeOfTransaction", "transactionPurpose")
    if item4:
        out["item4_text"] = item4[:20000]
    if "owner_name" not in out and "percent" not in out:
        return {}
    return out


# ---------------------------------------------------------------- collector
PLAUSIBLE_SICS = {
    "2833",
    "2834",
    "2835",
    "2836",
    "3826",
    "3841",
    "3842",
    "3843",
    "3844",
    "3845",
    "3851",
    "8071",
    "8731",
}
MAX_PAGES_PER_MEMBER = 30  # 300 filings per member per form set; capped members counted


def _hits_full(payload: dict) -> list[dict]:
    """Like efts.hits_of but keeps ALL associated CIKs and display names —
    the 13D/G owner is the associated entity that is not the subject."""
    out = []
    for h in payload.get("hits", {}).get("hits", []) or []:
        _id = h.get("_id") or ""
        src = h.get("_source") or {}
        if ":" not in _id:
            continue
        adsh, doc = _id.split(":", 1)
        ciks = [str(int(c)) for c in (src.get("ciks") or []) if str(c).strip().isdigit()]
        out.append(
            {
                "adsh": adsh,
                "doc": doc,
                "ciks": ciks,
                "names": src.get("display_names") or [],
                "cik": ciks[0] if ciks else "",
                "name": (src.get("display_names") or [""])[0],
                "file_date": src.get("file_date") or "",
                "form": src.get("form") or (src.get("root_forms") or [""])[0],
                "file_type": src.get("file_type") or "",
                "items": [],
                "url": f"https://www.sec.gov/Archives/edgar/data/{ciks[0]}/{adsh.replace('-', '')}/{doc}"
                if ciks
                else "",
            }
        )
    return out


def _owner_cik_from_hit(hit: dict, subject_cik: str, parsed: dict) -> str:
    """XML gives the owner CIK directly; for the HTML eras the owner is the
    hit-metadata CIK that is not the subject we queried. Ambiguity falls
    back to a name key, counted in the run metrics."""
    if parsed.get("owner_cik"):
        return parsed["owner_cik"]
    others = [c for c in hit.get("ciks", []) if c != str(int(subject_cik))]
    if len(others) == 1:
        return others[0]
    return ""


def _row_from(hit: dict, parsed: dict, subject_cik: str) -> dict | None:
    pct = parsed.get("percent", "")
    try:
        float(pct)
    except (TypeError, ValueError):
        return None
    owner_cik = _owner_cik_from_hit(hit, subject_cik, parsed)
    if owner_cik:
        holder = f"CIK:{owner_cik}"
    elif parsed.get("owner_name"):
        from biointel import network

        holder = f"NAME:{network._norm(parsed['owner_name'])}"
    else:
        return None
    as_of = parsed.get("event_date") or hit["file_date"]
    if not as_of:
        return None
    span = parsed.get("percent_span") or parsed.get("shares_span") or parsed.get("event_span") or ""
    return {
        "holder_key": holder,
        "issuer_key": f"CIK:{int(subject_cik)}",
        "percent": pct,
        "as_of": as_of,
        "doc_id": hit["sha"],
        "span": span[:500],
        "form": hit["form"],
        "filing_date": hit["file_date"],
        "shares": parsed.get("shares", ""),
        "owner_name": parsed.get("owner_name", ""),
        "accession": hit["adsh"],
        "cusip": parsed.get("cusip", ""),
        "item4_text": parsed.get("item4_text", ""),
    }


def _collect_member(cik: str, since: str, until: str, con, counters) -> list[dict]:
    from biointel import schema as _schema  # noqa: F401  (columns via ALL_STAKE_COLS)

    rows: list[dict] = []
    for forms in (STAKE_FORMS, STRUCTURED_FORMS):
        page = 0
        while page < MAX_PAGES_PER_MEMBER:
            payload = search(PROBE_QUERY, forms, since, until, cik=cik, page_from=page * 10)
            hits = [h for h in _hits_full(payload) if h["url"]]
            if payload.get("error"):
                counters["efts_errors"] += 1
                break
            for h in hits:
                got = _capture(h, con)
                if not got:
                    counters["fetch_failures"] += 1
                    continue
                sha, ext, _ctype = got
                h["sha"] = sha
                p = library.store_path(sha, ext)
                try:
                    raw = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    counters["fetch_failures"] += 1
                    continue
                parsed = (
                    parse_structured(raw) if ext == ".xml" else parse_cover(normalize_text(raw))
                )
                if not parsed:
                    counters["parse_failures_xml" if ext == ".xml" else "parse_failures_html"] += 1
                    continue
                row = _row_from(h, parsed, cik)
                if row is None:
                    counters["row_rejects"] += 1
                    continue
                if row["holder_key"].startswith("NAME:"):
                    counters["name_fallback"] += 1
                rows.append(row)
            total = ((payload.get("hits") or {}).get("total") or {}).get("value", 0)
            page += 1
            if page * 10 >= int(total or 0):
                break
        else:
            counters["capped_members"] += 1
    return rows


ALL_STAKE_COLS = None  # set at import bottom from schema (base + optional)


def run(since: str = "2001-01-01") -> int:
    """F1 collector: per-member EFTS across both form-name eras, captures
    into the library, parses per format, writes equity_stakes rows
    idempotently (key holder/issuer/as_of; existing keys skipped), flushes
    per member so interruption loses nothing, emits the proposed-stub list
    for operator approval (Q3 — never an auto-add), records the run."""
    from datetime import date as _date

    from biointel import schema as _schema

    con = store.connect()
    until = _date.today().isoformat()
    cols = list(_schema.EQUITY_STAKE_COLS) + list(
        _schema.TABLE_BY_PATH["silver/equity_stakes.csv"].optional
    )
    existing = set()
    if store.has_table("equity_stakes", con):
        stored = store.table_columns("equity_stakes", con)
        if stored != cols and len(stored) < len(cols):
            # widen the stored header once with the new optional columns
            for c in cols[len(stored) :]:
                con.execute(f"ALTER TABLE equity_stakes ADD COLUMN \"{c}\" VARCHAR DEFAULT ''")
        for r in store.read_table("equity_stakes", con=con):
            existing.add((r["holder_key"], r["issuer_key"], str(r["as_of"])[:10]))
    counters = {
        "filings_seen": 0,
        "rows_written": 0,
        "rows_skipped_existing": 0,
        "fetch_failures": 0,
        "parse_failures_html": 0,
        "parse_failures_xml": 0,
        "row_rejects": 0,
        "name_fallback": 0,
        "efts_errors": 0,
        "capped_members": 0,
        "members_done": 0,
    }
    member_ciks = {str(int(c)) for c, _t, _n in _member_ciks()}
    for cik, _ticker, _name in _member_ciks():
        rows = _collect_member(cik, since, until, con, counters)
        counters["filings_seen"] += len(rows)
        fresh = []
        for r in rows:
            k = (r["holder_key"], r["issuer_key"], str(r["as_of"])[:10])
            if k in existing:
                counters["rows_skipped_existing"] += 1
                continue
            existing.add(k)
            fresh.append(r)
        if fresh:
            store.append_rows("equity_stakes", fresh, cols, con=con)
            counters["rows_written"] += len(fresh)
        counters["members_done"] += 1
        if counters["members_done"] % 25 == 0:
            log.info(
                f"{counters['members_done']} members; rows {counters['rows_written']}; "
                f"failures f/h/x {counters['fetch_failures']}/"
                f"{counters['parse_failures_html']}/{counters['parse_failures_xml']}"
            )
    # Proposals derive from the WHOLE table so idempotent re-runs never erase
    # the list; owners already in the registry are not proposed again.
    thirteen_d_owners: dict[str, str] = {}
    for r in store.read_table("equity_stakes", con=con):
        if "13D" in str(r.get("form") or "") and str(r["holder_key"]).startswith("CIK:"):
            ocik = str(r["holder_key"])[4:]
            if ocik not in member_ciks:
                thirteen_d_owners.setdefault(ocik, str(r.get("owner_name") or ""))
    stub_lines = _proposed_stubs(thirteen_d_owners)
    p = store.write_export("stakes_proposed_stubs.txt", "\n".join(stub_lines) + "\n")
    runr = results.start(
        "stakes-run", "stakes run", ["companies"], {"since": since, "rule_version": RULE_VERSION}
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    runr.metric("_", "proposed_stubs", max(0, len(stub_lines) - 1))
    runr.artefact(p)
    run_id = results.finish(
        runr,
        note=(
            f"rule {RULE_VERSION}; one row per filing (lead filer); as_of = cover-page event "
            "date, else filing date; exits written at stated percent (Q4); stubs proposed, "
            "never auto-added (Q3)"
        ),
    )
    log.info(f"rows written {counters['rows_written']}; proposed stubs -> {p}")
    log.info(f"run {run_id} recorded")
    return 0


def _proposed_stubs(owners: dict[str, str]) -> list[str]:
    """Plausible-party test (approved Q3): the 13D owner's own EDGAR SIC in
    pharma/bio/device/diagnostics ranges. One submissions fetch per distinct
    13D owner; failures are listed as UNKNOWN-SIC, never dropped silently."""
    lines = [
        "PROPOSED STUBS (13D owners passing the plausible-party SIC test; add via "
        "`add --stub NAME --cik N` on your approval — nothing is auto-added)"
    ]
    for cik, name in sorted(owners.items()):
        sic = _owner_sic(cik)
        if sic is None:
            lines.append(
                f"  UNKNOWN-SIC cik {cik} {name} (submissions fetch failed; judge manually)"
            )
        elif sic in PLAUSIBLE_SICS:
            lines.append(f"  cik {cik} sic {sic} {name}")
    return lines


def _owner_sic(cik: str) -> str | None:
    import json

    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    got = _fetch(url)
    if not got:
        return None
    try:
        return str(json.loads(got[0].decode("utf-8", errors="replace")).get("sic") or "")
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------- measurement (Q5)
def sample(n: int = 60, seed: int = 20260903) -> int:
    """Blind sample of parsed rows for judging: id F+doc_id[:12] (judge
    accepts F-prefixed ids at this rule version); a row is correct only if
    owner, subject, percent and event date all match the filing (Q5)."""
    import random as _r

    rows = [r for r in store.read_table("equity_stakes") if r.get("doc_id")]
    if not rows:
        print("no parsed rows to sample")
        return 1
    _r.seed(seed)
    picked = _r.sample(rows, min(n, len(rows)))
    print(
        f"STAKES BLIND SAMPLE ({len(picked)} rows, rule {RULE_VERSION}). For each: open the "
        "filing URL, check owner, subject, percent, event date; then "
        "`judge F<id> correct|wrong|unsure`. A row passes only if ALL FOUR match."
    )
    for r in picked:
        acc = str(r.get("accession") or "").replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{str(r['issuer_key'])[4:]}/{acc}/"
            if acc
            else ""
        )
        print(
            f"F{str(r['doc_id'])[:12]}  {r.get('owner_name') or r['holder_key']} -> "
            f"{r['issuer_key']}  {r['percent']}%  as_of {str(r['as_of'])[:10]}  "
            f"{r.get('form', '')}  {url}"
        )
    return 0


def precision() -> int:
    """Wilson-CI precision over judged F-rows at this rule version; rows
    judged wrong are retired from equity_stakes (Q5), counted in the run."""
    from biointel.efts import _wilson

    con = store.connect()
    verdicts: dict[str, str] = {}
    if store.has_table("candidate_reviews", con):
        for r in store.read_table("candidate_reviews", con=con):
            if r.get("rule_version") == RULE_VERSION and str(r["candidate_id"]).startswith("F"):
                verdicts[str(r["candidate_id"])[1:]] = r["verdict"]
    judged = {k: v for k, v in verdicts.items() if v in ("correct", "wrong")}
    if not judged:
        print("no F-prefixed verdicts at rule " + RULE_VERSION)
        return 1
    k = sum(1 for v in judged.values() if v == "correct")
    nn = len(judged)
    lo, hi = _wilson(k, nn)
    retired = 0
    if any(v == "wrong" for v in judged.values()):
        rows = store.read_table("equity_stakes", con=con)
        keep = [r for r in rows if judged.get(str(r.get("doc_id"))[:12]) != "wrong"]
        retired = len(rows) - len(keep)
        if retired:
            cols = store.table_columns("equity_stakes", con)
            store.write_table("equity_stakes", keep, cols, con=con)
    runr = results.start(
        "stakes-precision", "stakes precision", ["equity_stakes"], {"rule_version": RULE_VERSION}
    )
    runr.metric("_", "correct", k)
    runr.metric("_", "judged", nn)
    runr.metric("_", "precision", k / nn)
    runr.metric("_", "wilson_lo", lo)
    runr.metric("_", "wilson_hi", hi)
    runr.metric("_", "retired_wrong_rows", retired)
    run_id = results.finish(
        runr, note=f"four-field pass rule (Q5); {retired} judged-wrong rows retired"
    )
    print(f"precision {k}/{nn} = {k / nn:.3f} [{lo:.3f}, {hi:.3f}]; retired {retired}")
    log.info(f"run {run_id} recorded")
    return 0
