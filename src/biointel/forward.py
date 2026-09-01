# C:\Users\JB\Documents\dev\bioindustry\src\biointel\forward.py
"""Forward FDA calendar writers (gate 1.5a; Ontology v5 §3.6; FDA Catalyst
design). Forward rows in `events_table` carry scheduled_date (start),
scheduled_date_end, date_precision, date_raw (verbatim timing language),
status and confidence_tier; event_date stays blank until the event is
realized.

Writers at 1.5a:
  * trials — a pure database transform: every future PrimaryCompletion date
    in the `trials` table becomes a `clinical_readout` forward row with
    outcome_subtype "estimated_primary_completion" (never "results
    expected": primary completion is the end of primary-endpoint data
    collection, not a readout). Confidence tier C.
  * adcom — the official FDA Advisory Committee Calendar is served by the
    JSON endpoint behind the calendar page (the page itself is a shell
    filled client-side; verified 2026-08-31 from the captured page and the
    browser's network log). The endpoint returns the full meeting history;
    records dated today or later become forward rows. Each such meeting
    yields two rows of class `regulatory_meeting`: the meeting itself
    (tier A, day precision) and the briefing-document release, which FDA
    posts no later than two business days before the meeting (tier B,
    derived). Postponed/cancelled records are counted, not written.

Identity and history: event_id = hash(identity | scheduled_date). A moved
date therefore inserts a new row and the old one is marked
status="superseded"; nothing is overwritten (R3.5). Re-runs update
last_verified on unchanged rows and keep first_seen.
"""

from __future__ import annotations

import calendar as _cal
import hashlib
import html as _html
import json as _json
import re
from datetime import date, datetime, timedelta, timezone

from biointel import config, library, results, schema, store
from biointel.pipeline import read_trials

ALL_COLS = schema.EVENT_TABLE_COLS + schema.EVENT_FORWARD_COLS
ADCOM_URL = "https://www.fda.gov/advisory-committees/advisory-committee-calendar"
ADCOM_JSON_URL = "https://www.fda.gov/datatables-json/advisory-committee-calendar-json"

_MONTHS = {m.lower(): i for i, m in enumerate(_cal.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(_cal.month_abbr) if m})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _eid(*parts: str) -> str:
    return "F" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _blank_row() -> dict:
    return {c: "" for c in ALL_COLS}


# ------------------------------------------------------------ date handling
def parse_date_range(raw: str) -> tuple[str, str, str] | None:
    """'2026-11' -> (2026-11-01, 2026-11-30, month); '2026-11-14' -> day;
    'Q4 2026' -> quarter; 'H2 2026' -> half; '2027' -> year;
    'November 14, 2026' -> day; 'November 2026' -> month."""
    s = (raw or "").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s, s, "day"
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        y, mo = int(m[1]), int(m[2])
        return f"{y:04d}-{mo:02d}-01", f"{y:04d}-{mo:02d}-{_cal.monthrange(y, mo)[1]:02d}", "month"
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return f"{s}-01-01", f"{s}-12-31", "year"
    m = re.fullmatch(r"[Qq]([1-4])\s*(\d{4})", s) or re.fullmatch(
        r"(?:the\s+)?(1st|2nd|3rd|4th|first|second|third|fourth)\s+quarter\s+(?:of\s+)?(\d{4})",
        s,
        re.I,
    )
    if m:
        words = {
            "1st": 1,
            "first": 1,
            "2nd": 2,
            "second": 2,
            "3rd": 3,
            "third": 3,
            "4th": 4,
            "fourth": 4,
        }
        q = int(m[1]) if m[1].isdigit() else words[m[1].lower()]
        y = int(m[2])
        start_mo = 3 * (q - 1) + 1
        end_mo = start_mo + 2
        return (
            f"{y}-{start_mo:02d}-01",
            f"{y}-{end_mo:02d}-{_cal.monthrange(y, end_mo)[1]:02d}",
            "quarter",
        )
    m = re.fullmatch(r"[Hh]([12])\s*(\d{4})", s) or re.fullmatch(
        r"(?:the\s+)?(first|second|1st|2nd)\s+half\s+(?:of\s+)?(\d{4})", s, re.I
    )
    if m:
        h = 1 if m[1].lower() in ("1", "first", "1st") else 2
        y = int(m[2])
        return (
            (f"{y}-01-01", f"{y}-06-30", "half") if h == 1 else (f"{y}-07-01", f"{y}-12-31", "half")
        )
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m[1].lower() in _MONTHS:
        y, mo, d = int(m[3]), _MONTHS[m[1].lower()], int(m[2])
        iso = f"{y:04d}-{mo:02d}-{d:02d}"
        return iso, iso, "day"
    m = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", s)
    if m and m[1].lower() in _MONTHS:
        y, mo = int(m[2]), _MONTHS[m[1].lower()]
        return f"{y:04d}-{mo:02d}-01", f"{y:04d}-{mo:02d}-{_cal.monthrange(y, mo)[1]:02d}", "month"
    return None


def business_days_before(iso: str, n: int) -> str:
    d = date.fromisoformat(iso)
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.isoformat()


# ------------------------------------------------------------ upsert
def _upsert(new_rows: list[dict], identity_of, con) -> dict:
    """Merge forward rows into events_table. identity_of(row) -> the
    date-free identity string; rows sharing an identity with a different
    scheduled_date supersede the older row. Returns counts."""
    existing = (
        store.read_table("events_table", con=con) if store.has_table("events_table", con) else []
    )
    rows = []
    for r in existing:
        full = _blank_row()
        full.update(r)
        rows.append(full)
    by_id = {r["event_id"]: r for r in rows}
    now = _now()
    inserted = refreshed = superseded = 0
    for nr in new_rows:
        if nr["event_id"] in by_id:
            by_id[nr["event_id"]]["last_verified"] = now
            if by_id[nr["event_id"]]["status"] == "superseded":
                pass  # a date that moved back keeps its history
            refreshed += 1
            continue
        ident = identity_of(nr)
        for r in rows:
            if (
                r["status"] == ""
                and not r["event_date"]
                and r["scheduled_date"]
                and identity_of(r) == ident
            ):
                r["status"] = "superseded"
                superseded += 1
        nr["first_seen"] = nr["last_verified"] = now
        rows.append(nr)
        by_id[nr["event_id"]] = nr
        inserted += 1
    store.write_table("events_table", rows, ALL_COLS, con=con)
    return {
        "inserted": inserted,
        "refreshed": refreshed,
        "superseded": superseded,
        "total": len(rows),
    }


# ------------------------------------------------------------ writer 1: trials
def _trial_identity(r: dict) -> str:
    nct = ""
    for part in (r.get("provenance") or "").split(";"):
        if part.startswith("NCTId="):
            nct = part[6:]
    return f"trials|{r.get('entity_key')}|{nct}|{r.get('outcome_subtype')}"


def write_trials(today: date | None = None) -> dict:
    today = today or date.today()
    con = store.connect()
    run = results.start("calendar", "calendar-forward trials", ["trials", "events_table"], {})
    new_rows, skipped = [], 0
    for t in read_trials():
        pr = parse_date_range(t.get("PrimaryCompletion") or "")
        if not pr:
            skipped += 1
            continue
        start, end, precision = pr
        if end < today.isoformat():
            continue
        nct = t.get("NCTId") or ""
        row = _blank_row()
        row.update(
            {
                "event_id": _eid(
                    "trials", str(t["IID"]), nct, "estimated_primary_completion", start
                ),
                "entity_key": str(t["IID"]),
                "asset": t.get("Drugs") or t.get("Interventions") or "",
                "indication": t.get("Conditions") or "",
                "event_class": "clinical_readout",
                "scheduled_date": start,
                "scheduled_date_end": end,
                "date_precision": precision,
                "date_raw": t.get("PrimaryCompletion") or "",
                "outcome_subtype": "estimated_primary_completion",
                "source_url": f"https://clinicaltrials.gov/study/{nct}" if nct else "",
                "provenance": f"table=trials;NCTId={nct};Phase={t.get('Phase') or ''};Status={t.get('Status') or ''}",
                "confidence_tier": "C",
            }
        )
        new_rows.append(row)
    counts = _upsert(new_rows, _trial_identity, con)
    for k, v in counts.items():
        run.metric("_", k, v)
    run.metric("_", "candidates", len(new_rows))
    run_id = results.finish(run)
    msg = (
        f"calendar-forward trials: {len(new_rows)} future primary-completion rows "
        f"({counts['inserted']} inserted, {counts['refreshed']} refreshed, "
        f"{counts['superseded']} superseded; {skipped} blank or unparseable dates skipped; "
        f"events_table now {counts['total']} rows) (run {run_id} recorded)"
    )
    print(msg)
    return {"status": "ok", "candidates": len(new_rows), **counts, "run_id": run_id}


# ------------------------------------------------------------ writer 2: AdCom
_ANCHOR = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<text>.*?)</a>', re.I | re.S)
_MDY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")
_CANCEL_WORDS = ("postponed", "cancelled", "canceled")


def _mdy_to_iso(s: str) -> str:
    m = _MDY.match((s or "").strip())
    return f"{m[3]}-{m[1]}-{m[2]}" if m else ""


def parse_adcom_json(text: str) -> list[dict]:
    """Records from the FDA calendar JSON endpoint. Each record carries
    field_start_date / field_end_date ('MM/DD/YYYY HH:MM AM TZ', sometimes
    blank), a title that is an HTML anchor (href = meeting page, text =
    title, possibly prefixed 'POSTPONED:' / 'UPDATED ...'), field_center
    and changed. Returns dicts: start, end, title, url, center, cancelled.
    A blank start date falls back to the date written in the title."""
    try:
        data = _json.loads(text)
    except ValueError:
        return []
    out = []
    for rec in data if isinstance(data, list) else []:
        raw_title = rec.get("title") or ""
        am = _ANCHOR.search(raw_title)
        href = am["href"] if am else ""
        title = _html.unescape(re.sub(r"<[^>]+>", " ", am["text"] if am else raw_title))
        title = re.sub(r"\s+", " ", title).strip()
        start = _mdy_to_iso(rec.get("field_start_date") or "")
        end = _mdy_to_iso(rec.get("field_end_date") or "") or start
        if not start:
            dm = _DATE_IN_TITLE.search(title)
            if dm:
                mo = _MONTHS[dm["month"].lower()]
                y = int(dm["year"])
                start = f"{y:04d}-{mo:02d}-{int(dm['d1']):02d}"
                end = f"{y:04d}-{mo:02d}-{int(dm['d2']):02d}" if dm["d2"] else start
        if not start or not href:
            continue
        if href.startswith("/"):
            href = "https://www.fda.gov" + href
        low = title.lower()
        out.append(
            {
                "start": start,
                "end": end if end >= start else start,
                "title": title,
                "url": href,
                "center": rec.get("field_center") or "",
                "cancelled": any(low.startswith(w) for w in _CANCEL_WORDS),
            }
        )
    return out


_DATE_IN_TITLE = re.compile(
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?P<d1>\d{1,2})(?:\s*[-–]\s*(?P<d2>\d{1,2}))?,?\s+(?P<year>\d{4})",
    re.I,
)


def _match_entity(title: str, companies: list[dict]) -> str:
    """Conservative name match: a company Name (>= 5 chars) occurring
    verbatim in the title; blank when none or ambiguous."""
    t = title.casefold()
    hits = []
    for c in companies:
        name = (c.get("Name") or "").casefold()
        core = re.sub(
            r"[,.]?\s+(inc|corp|corporation|plc|ltd|limited|holdings|co|sa|nv|ag|therapeutics|pharmaceuticals)\.?$",
            "",
            name,
        ).strip()
        if len(core) >= 5 and core in t:
            hits.append(str(c["IID"]))
    return hits[0] if len(hits) == 1 else ""


def _adcom_identity(r: dict) -> str:
    url = ""
    for part in (r.get("provenance") or "").split(";"):
        if part.startswith("meeting_url="):
            url = part[len("meeting_url=") :]
    return f"adcom|{url}|{r.get('outcome_subtype')}"


def _ref_fields(note: str) -> dict:
    return {
        "ref_type": "web_page",
        "url": ADCOM_JSON_URL,
        "title": "FDA Advisory Committee Calendar (data endpoint)",
        "publisher": "FDA",
        "published_at": date.today().isoformat(),
        "source_system": "calendar-forward",
        "source_key": "adcom",
        "note": note,
    }


def write_adcom(
    text: str | None = None, file: str | None = None, today: date | None = None
) -> dict:
    """Capture the calendar JSON endpoint into the library (fetched, or a
    saved response via `file`) and write meeting + briefing-release forward
    rows for meetings dated today or later. `text` is for tests only."""
    from pathlib import Path

    today = today or date.today()
    con = store.connect()
    run = results.start(
        "calendar",
        "calendar-forward adcom",
        ["events_table", "references", "captures"],
        {"url": ADCOM_JSON_URL, "file": file or ""},
    )
    doc_id = ""
    if text is None and file:
        p = Path(file)
        if not p.exists():
            results.finish(run, status="failed", note="file missing")
            print(f"calendar-forward adcom: no such file {p}")
            return {"status": "error"}
        data = p.read_bytes()
        text = data.decode("utf-8", errors="replace")
        ref_id, _ = library.upsert_reference(_ref_fields("saved response"), con)
        sha, dst, _new = library.put_bytes(data, ".json")
        library.add_capture(
            ref_id, sha, dst, "fetched_text", "calendar-forward adcom (saved response)", con
        )
        doc_id = sha
    elif text is None:
        from biointel.collectors.manual import _fetch

        got = _fetch(ADCOM_JSON_URL)
        if not got:
            results.finish(run, status="failed", note="fetch failed")
            print("calendar-forward adcom: fetch failed; nothing written")
            return {"status": "error"}
        data, _ext = got
        text = data.decode("utf-8", errors="replace")
        ref_id, _ = library.upsert_reference(
            _ref_fields("dated snapshot of the calendar endpoint"), con
        )
        sha, dst, _new = library.put_bytes(data, ".json")
        library.add_capture(ref_id, sha, dst, "fetched_text", "calendar-forward adcom", con)
        doc_id = sha
    records = parse_adcom_json(text)
    cutoff = today.isoformat()
    past = sum(1 for r in records if r["end"] < cutoff)
    cancelled = sum(1 for r in records if r["end"] >= cutoff and r["cancelled"])
    meetings = [r for r in records if r["end"] >= cutoff and not r["cancelled"]]
    companies = store.read_table("companies", con=con) if store.has_table("companies", con) else []
    new_rows = []
    for mt in meetings:
        ent = _match_entity(mt["title"], companies)
        prov = f"source=fda_adcom_calendar_json;meeting_url={mt['url']};center={mt['center']};doc_id={doc_id}"
        base = {
            "entity_key": ent,
            "asset": mt["title"][:200],
            "event_class": "regulatory_meeting",
            "source_url": mt["url"],
        }
        meet = _blank_row()
        meet.update(base)
        meet.update(
            {
                "event_id": _eid("adcom", mt["url"], "meeting", mt["start"]),
                "scheduled_date": mt["start"],
                "scheduled_date_end": mt["end"],
                "date_precision": "day",
                "date_raw": mt["title"],
                "outcome_subtype": "meeting",
                "provenance": prov,
                "confidence_tier": "A",
            }
        )
        brief = _blank_row()
        brief.update(base)
        bd = business_days_before(mt["start"], 2)
        brief.update(
            {
                "event_id": _eid("adcom", mt["url"], "briefing_documents", bd),
                "scheduled_date": bd,
                "scheduled_date_end": mt["start"],
                "date_precision": "day",
                "date_raw": "background material available no later than 2 business days before the meeting",
                "outcome_subtype": "briefing_documents",
                "provenance": prov + ";derived=meeting_minus_2_business_days",
                "confidence_tier": "B",
            }
        )
        new_rows.extend([meet, brief])
    counts = _upsert(new_rows, _adcom_identity, con)
    for k, v in counts.items():
        run.metric("_", k, v)
    run.metric("_", "records", len(records))
    run.metric("_", "meetings_forward", len(meetings))
    run_id = results.finish(run)
    msg = (
        f"calendar-forward adcom: {len(records)} records ({past} past, {cancelled} postponed/cancelled skipped) "
        f"-> {len(meetings)} upcoming meetings -> {len(new_rows)} forward rows "
        f"({counts['inserted']} inserted, {counts['refreshed']} refreshed, {counts['superseded']} superseded; "
        f"events_table now {counts['total']} rows) (run {run_id} recorded)"
    )
    print(msg)
    return {
        "status": "ok",
        "records": len(records),
        "meetings": len(meetings),
        **counts,
        "run_id": run_id,
        "doc_id": doc_id,
    }


def cli(argv: list[str]) -> int:
    which = argv[0] if argv else "all"
    if which not in ("trials", "adcom", "all"):
        print("usage: calendar-forward trials|adcom|all [--file SAVED_RESPONSE.json]")
        return 1
    file = (
        argv[argv.index("--file") + 1]
        if "--file" in argv and argv.index("--file") + 1 < len(argv)
        else None
    )
    rc = 0
    if which in ("trials", "all"):
        r = write_trials()
        rc |= 0 if r["status"] == "ok" else 1
    if which in ("adcom", "all"):
        r = write_adcom(file=file)
        rc |= 0 if r["status"] == "ok" else 1
    return rc


__all__ = ["write_trials", "write_adcom", "parse_date_range", "parse_adcom_json", "cli", "config"]
