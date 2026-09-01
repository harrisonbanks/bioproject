# C:\Users\JB\Documents\dev\bioindustry\src\biointel\efts.py
"""SEC EDGAR full-text miner for forward FDA events (gate 1.5b).

Source of record for PDUFA target action dates and company readout guidance
is the sponsor's own SEC disclosure. EDGAR full-text search (EFTS) finds
the filings; the filing documents are captured into the research library
(dated, hashed) and mined with rules; every row carries the document URL,
the accession, the capture hash and the verbatim window it was read from.

Verified 2026-08-31/09-01 against real captures (rule 4.20):
  * endpoint https://efts.sec.gov/LATEST/search-index, GET with q, forms,
    dateRange=custom, startdt, enddt, ciks (filters per company — probed),
    from (paging); JSON hits carry _id "<accession>:<document>" and _source
    {adsh, ciks, display_names, file_date, form, root_forms, file_type,
    file_description, sics, items, period_ending, ...};
  * real prose (Harmony Biosciences 8-K EX-99.1, 2026-08-04): exact PDUFA
    dates ("target PDUFA date of April 1, 2027"), year-only PDUFA dates
    ("anticipated PDUFA date in 2028"), guidance in quarter/half/year and
    early/mid/late forms, and quarter-without-year ("expected in Q4").

Rules: a fuzzy timing statement is a range plus its raw language; early/
mid/late YYYY is year precision (no invented sub-year range); a quarter or
half with no year is counted and skipped, never inferred; rows are tier B.
Aggregators are never a source; FDA Tracker's public calendar (their terms
forbid systematic collection) is used only as an operator-triggered
benchmark snapshot for recall measurement.
"""

from __future__ import annotations

import hashlib
import html as _html
import random
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from biointel import config, library, results, store
from biointel.forward import _blank_row, _upsert, parse_date_range
from biointel.pipeline import read_companies

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
DEFAULT_FORMS = "8-K,10-Q,10-K,6-K,20-F"
DEFAULT_QUERY = '"PDUFA" OR "target action date" OR "topline data" OR "top-line data"'
_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sept?\.?|Oct\.?|Nov\.?|Dec\.?)"
)
_DATE_PHRASE = re.compile(
    rf"(?P<d>{_MONTH}\s+\d{{1,2}},?\s+\d{{4}}|{_MONTH}\s+(?:of\s+)?\d{{4}}|[Qq][1-4]\s*\d{{4}}|[1-4]Q\s*\d{{4}}|"
    rf"(?:first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter\s+(?:of\s+)?\d{{4}}|"
    rf"[12]H\s*\d{{4}}|H[12]\s*\d{{4}}|(?:first|second)\s+half\s+(?:of\s+)?\d{{4}}|"
    rf"(?:early|mid|late)[-\s]\d{{4}}|\b(?:20\d{{2}})\b)",
    re.I,
)
_NO_YEAR = re.compile(
    r"\b(?:[Qq][1-4]|[12]H|(?:first|second|third|fourth)\s+quarter|(?:first|second)\s+half)\b(?!\s*(?:of\s+)?\d{4})"
)
_PDUFA_ANCHOR = re.compile(r"(PDUFA|target action date|goal date|action date)", re.I)
_GUIDE_ANCHOR = re.compile(
    r"(topline|top-line)\s+(?:data|results)|data\s+(?:are\s+|is\s+)?expected|results\s+(?:are\s+)?expected|expect(?:s|ed)?\s+to\s+(?:report|announce)",
    re.I,
)
_WINDOW = 160
_PAST_TENSE = re.compile(
    r"\b(announced|reported|presented|released|published|disclosed|delivered|achieved|completed|had|based on)\b(?:\s+\w+){0,3}\s*$",
    re.I,
)
_NEGATION = re.compile(r"\b(no longer|not|never|do not|does not|did not|won't|will not)\b", re.I)
_PDUFA_CONTEXT = re.compile(r"\b(date|dates|goal|action|target|set|assigned|scheduled)\b", re.I)
_SEGMENT_BREAK = re.compile(r"[•●○§▪]|\s[o·]\s|(?<=[.;!?])\s+(?=[A-Z\u201c\"])")
_PERIOD_LABEL = re.compile(
    r"^\s*(financial|results|highlights|earnings|ended|ending|conference)", re.I
)
_PERIOD_LEAD = re.compile(r"\b(as of|ended|ending|through|since|during)\s*$", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_text(raw: str) -> str:
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    t = t.replace("\u200b", " ").replace("\u00a0", " ").replace("\u2011", "-")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- adapter
def _headers() -> dict:
    return {"User-Agent": config.require("BIOINTEL_USER_AGENT"), "Accept": "application/json"}


def search(
    q: str, forms: str, start: str, end: str, cik: str | None = None, page_from: int = 0
) -> dict:
    """One EFTS page. Polite: SEC_RATE_LIMIT between calls, backoff on 429/5xx."""
    params = {
        "q": q,
        "forms": forms,
        "dateRange": "custom",
        "startdt": start,
        "enddt": end,
        "from": str(page_from),
    }
    if cik:
        params["ciks"] = str(int(cik)).zfill(10)
    url = EFTS_URL + "?" + "&".join(f"{k}={quote(v, safe='')}" for k, v in params.items())
    for attempt in range(4):
        time.sleep(config.SEC_RATE_LIMIT * (1 + attempt))
        r = requests.get(url, headers=_headers(), timeout=60)
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                return {"hits": {"hits": [], "total": {"value": 0}}}
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2.0 * (attempt + 1))
            continue
        return {"hits": {"hits": [], "total": {"value": 0}}, "error": r.status_code}
    return {"hits": {"hits": [], "total": {"value": 0}}, "error": "retries"}


def hits_of(payload: dict) -> list[dict]:
    """Flatten EFTS hits to {adsh, doc, cik, name, file_date, form, url}."""
    out = []
    for h in payload.get("hits", {}).get("hits", []) or []:
        _id = h.get("_id") or ""
        src = h.get("_source") or {}
        if ":" not in _id:
            continue
        adsh, doc = _id.split(":", 1)
        ciks = src.get("ciks") or []
        cik = str(int(ciks[0])) if ciks else ""
        names = src.get("display_names") or []
        out.append(
            {
                "adsh": adsh,
                "doc": doc,
                "cik": cik,
                "name": names[0] if names else "",
                "file_date": src.get("file_date") or "",
                "form": src.get("form") or (src.get("root_forms") or [""])[0],
                "file_type": src.get("file_type") or "",
                "items": src.get("items") or [],
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{doc}"
                if cik
                else "",
            }
        )
    return out


def _fetch_with_backoff(url: str) -> tuple[bytes, str] | None:
    """Filing document fetch that never raises: timeouts, connection resets
    and 5xx responses are retried with backoff (5 s, 15 s, 45 s) and then
    reported as a failed fetch, so one bad response cannot abort a run."""
    hdrs = {"User-Agent": config.require("BIOINTEL_USER_AGENT")}
    for attempt, pause in enumerate((0, 5, 15, 45)):
        if pause:
            time.sleep(pause)
        time.sleep(config.SEC_RATE_LIMIT)
        try:
            r = requests.get(url, headers=hdrs, timeout=60)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            ext = (
                ".pdf"
                if ctype == "application/pdf"
                else ".txt"
                if ctype == "text/plain"
                else ".htm"
            )
            return r.content, ext
        if r.status_code in (429, 500, 502, 503, 504):
            continue
        return None  # 4xx other than 429: not retryable
    return None


def capture_document(hit: dict, con) -> tuple[str, str] | None:
    """Fetch the filing document once into the library; returns (sha, text).
    Already-captured documents (same URL) are read from the store."""
    if not hit["url"]:
        return None
    for r in store.read_table("references", con=con) if store.has_table("references", con) else []:
        if r["url"] == hit["url"]:
            caps = [
                c
                for c in store.read_table("captures", con=con)
                if c["ref_id"] == r["ref_id"] and c["status"] == "active"
            ]
            if caps:
                p = config.DATA / caps[0]["path"]
                if p.exists():
                    return caps[0]["capture_id"], normalize_text(
                        p.read_text(encoding="utf-8", errors="replace")
                    )
    got = _fetch_with_backoff(hit["url"])
    if not got:
        return None
    data, ext = got
    ref_id, _ = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": hit["adsh"],
            "url": hit["url"],
            "title": f"{hit['name']} {hit['form']} {hit['file_type']} {hit['file_date']}".strip(),
            "publisher": "SEC EDGAR",
            "published_at": hit["file_date"],
            "source_system": "efts",
            "source_key": f"{hit['adsh']}:{hit['doc']}",
            "note": "captured by mine-pdufa",
        },
        con,
    )
    sha, dst, _new = library.put_bytes(data, ext if ext != ".bin" else ".htm")
    library.add_capture(ref_id, sha, dst, "fetched_html", "mine-pdufa", con)
    if hit["cik"]:
        library.add_link(ref_id, "CIK", hit["cik"], "subject", con)
    return sha, normalize_text(data.decode("utf-8", errors="replace"))


# ---------------------------------------------------------------- extractor
def _range_for(phrase: str) -> tuple[str, str, str] | None:
    p = phrase.strip()
    m = re.fullmatch(r"(early|mid|late)[-\s](\d{4})", p, re.I)
    if m:  # year precision, raw language retained
        y = m[2]
        return f"{y}-01-01", f"{y}-12-31", "year"
    m = re.fullmatch(r"([12])H\s*(\d{4})", p, re.I)  # filings write "1H 2027"
    if m:
        p = f"H{m[1]} {m[2]}"
    m = re.fullmatch(r"([1-4])Q\s*(\d{4})", p, re.I)  # and "3Q 2026"
    if m:
        p = f"Q{m[1]} {m[2]}"
    p = re.sub(r"^([A-Za-z]+)\s+of\s+(\d{4})$", r"\1 \2", p)  # "August of 2026"
    p = re.sub(r"^([A-Za-z]+)\.", r"\1", p)  # "Oct. 10, 2026" -> "Oct 10, 2026"
    p = re.sub(r"^Sept\b", "Sep", p)
    return parse_date_range(p)


RULE_VERSION = "1.5b-r7"
_HYPOTHETICAL = re.compile(r"\b(if|assuming|subject to|contingent on|should)\b", re.I)
_APPROX = re.compile(r"\b(approximately|around|about|roughly)\s*$", re.I)
_OUTCOME_WORDS = re.compile(
    r"\b(met (?:its |the )?primary endpoint|did not meet|failed to meet|missed|statistically significant|"
    r"positive|negative|superior|non-inferior|discontinu\w+|terminat\w+|clinical hold|safety)\b",
    re.I,
)


def _usable_phrase(m, seg: str, dist: int) -> bool:
    if _PERIOD_LABEL.match(seg[m.end() : m.end() + 14]) or _PERIOD_LEAD.search(
        seg[: m.start()][-12:]
    ):
        return False  # "First Quarter 2026 Financial Highlights", "as of March 31, 2026"
    if re.fullmatch(r"20\d{2}", m["d"]) and dist > 30:
        return False  # a bare year far from the anchor is not a date statement
    return True


def examine(text: str, file_date: str = "") -> list[dict]:
    """Every anchor window in the normalized text becomes a candidate record,
    accepted or rejected with a reason, carrying exact grounding (character
    offsets), the TimeML-style value/precision/modifier, an anchored flag for
    year-less expressions (anchored to the filing year, never silently), the
    ConText-style assertion status, and any outcome words. Nothing examined is
    discarded; downstream writers choose what to consume."""
    out, seen = [], set()
    for kind, anchor in (("pdufa", _PDUFA_ANCHOR), ("readout", _GUIDE_ANCHOR)):
        for am in anchor.finditer(text):
            lo, hi = max(0, am.start() - _WINDOW), min(len(text), am.end() + _WINDOW)
            before_raw, after_raw = text[lo : am.start()], text[am.end() : hi]
            # the sentence-break lookahead needs the character after the gap, which
            # is the anchor's first character when the break sits at the boundary
            probe = before_raw + text[am.start() : am.start() + 1]
            b_breaks = [m for m in _SEGMENT_BREAK.finditer(probe) if m.end() <= len(before_raw)]
            before = before_raw[b_breaks[-1].end() :] if b_breaks else before_raw
            a_break = _SEGMENT_BREAK.search(after_raw)
            after = after_raw[: a_break.start()] if a_break else after_raw
            seg_start, seg_end = am.start() - len(before), am.end() + len(after)
            segment = text[seg_start:seg_end]
            rec = {
                "kind": kind,
                "anchor_text": am.group(0),
                "anchor_start": am.start(),
                "char_start": seg_start,
                "char_end": seg_end,
                "window": segment.strip(),
                "phrase": "",
                "phrase_start": -1,
                "start": "",
                "end": "",
                "precision": "",
                "date_mod": "",
                "anchored": 0,
                "assertion": "affirmed",
                "outcome_words": ";".join(
                    sorted({m.group(0).lower() for m in _OUTCOME_WORDS.finditer(segment)})
                ),
                "decision": "rejected",
                "reason": "",
            }
            lead = before[-40:]
            if kind == "readout" and _PAST_TENSE.search(lead):
                rec["assertion"] = "historical"
            elif kind == "readout" and _NEGATION.search(lead):
                rec["assertion"] = "negated"
            elif _HYPOTHETICAL.search(lead):
                rec["assertion"] = "hypothetical"
            if kind == "pdufa" and not _PDUFA_CONTEXT.search(segment):
                rec["reason"] = "no_date_context"
                out.append(rec)
                continue
            a_list = [
                m for m in _DATE_PHRASE.finditer(after) if _usable_phrase(m, after, m.start())
            ]
            b_list = [
                m
                for m in _DATE_PHRASE.finditer(before)
                if _usable_phrase(m, before, len(before) - m.end())
            ]
            a_m = a_list[0] if a_list else None
            b_m = b_list[-1] if b_list else None
            if a_m and b_m:
                use_after = a_m.start() <= (len(before) - b_m.end())
            else:
                use_after = a_m is not None
            dm = a_m if use_after else b_m
            if not dm:
                ny = _NO_YEAR.search(after)
                if ny and file_date[:4].isdigit():
                    rng = _range_for(
                        f"{ny.group(0)} {file_date[:4]}"
                    )  # anchored to filing year, flagged
                    if rng:
                        rec.update(
                            {
                                "phrase": ny.group(0),
                                "phrase_start": am.end() + ny.start(),
                                "start": rng[0],
                                "end": rng[1],
                                "precision": rng[2],
                                "anchored": 1,
                            }
                        )
                    rec["reason"] = "no_year_anchored"
                else:
                    rec["reason"] = (
                        rec["assertion"]
                        if rec["assertion"] != "affirmed"
                        else ("no_year" if ny else "no_date")
                    )
                out.append(rec)
                continue
            phrase = dm["d"]
            rng = _range_for(phrase)
            if not rng:
                rec.update({"phrase": phrase, "reason": "unparseable_date"})
                out.append(rec)
                continue
            pstart = (am.end() + dm.start()) if use_after else (seg_start + dm.start())
            prefix = text[max(0, pstart - 16) : pstart]
            mod = re.match(r"(early|mid|late)", phrase, re.I)
            rec.update(
                {
                    "phrase": phrase,
                    "phrase_start": pstart,
                    "start": rng[0],
                    "end": rng[1],
                    "precision": rng[2],
                    "date_mod": mod.group(1).lower()
                    if mod
                    else ("approx" if _APPROX.search(prefix) else ""),
                }
            )
            if rec["assertion"] != "affirmed":
                rec["reason"] = rec["assertion"]
                out.append(rec)
                continue
            key = (kind, rng[0], rng[1])
            if key in seen:
                rec["reason"] = "duplicate_in_document"
                out.append(rec)
                continue
            seen.add(key)
            rec["decision"] = "accepted"
            out.append(rec)
    return out


def extract(text: str, file_date: str = "") -> tuple[list[dict], int]:
    """Accepted candidates (forward-writer input) plus the count of year-less
    expressions anchored-but-not-accepted; `examine` is the full ledger."""
    recs = examine(text, file_date)
    accepted = [r for r in recs if r["decision"] == "accepted"]
    return accepted, sum(1 for r in recs if r["reason"] in ("no_year_anchored", "no_year"))


# ---------------------------------------------------------------- writer
def _identity(r: dict) -> str:
    """One event per (company, kind, date range): the same PDUFA date restated
    in a later filing refreshes the row instead of duplicating it. A different
    range for the same company and kind is a different candidate (asset
    resolution is L3), so no supersession is inferred across ranges here."""
    return f"mine|{r.get('entity_key')}|{r.get('outcome_subtype')}|{r.get('scheduled_date')}|{r.get('scheduled_date_end')}"


def _rows_from(
    cands: list[dict], hit: dict, iid: str, sha: str, today: date
) -> tuple[list[dict], int]:
    rows, past, seen_ids = [], 0, set()
    for c in cands:
        if c["end"] < today.isoformat():
            past += 1
            continue
        kind = c["kind"]
        eid = (
            "M" + hashlib.sha256(f"{iid}|{kind}|{c['start']}|{c['end']}".encode()).hexdigest()[:16]
        )
        if eid in seen_ids:  # same company/kind/range restated in the same document
            continue
        seen_ids.add(eid)
        row = _blank_row()
        prov = f"source=efts;adsh={hit['adsh']};doc={hit['doc']};form={hit['form']};file_date={hit['file_date']};phrase={c['phrase']};doc_id={sha}"
        row.update(
            {
                "event_id": "M"
                + hashlib.sha256(f"{iid}|{kind}|{c['start']}|{c['end']}".encode()).hexdigest()[:16],
                "entity_key": iid,
                "asset": "",
                "event_class": "regulatory_decision" if kind == "pdufa" else "clinical_readout",
                "scheduled_date": c["start"],
                "scheduled_date_end": c["end"],
                "date_precision": c["precision"],
                "date_raw": c["window"][:300],
                "outcome_subtype": "pdufa_target_date" if kind == "pdufa" else "guided_readout",
                "source_url": hit["url"],
                "provenance": prov,
                "confidence_tier": "B",
            }
        )
        rows.append(row)
    return rows, past


def _ledger_rows(recs: list[dict], hit: dict, iid: str, sha: str, today: date) -> list[dict]:
    from biointel import schema as _schema

    now = _now()
    rows = []
    for r in recs:
        decision, reason = r["decision"], r["reason"]
        if decision == "accepted" and r["end"] and r["end"] < today.isoformat():
            decision, reason = "rejected", "past"  # realized statements are 1.5c's input
        cid = hashlib.sha256(
            f"{hit['adsh']}|{hit['doc']}|{r['kind']}|{r['anchor_start']}|{RULE_VERSION}".encode()
        ).hexdigest()[:16]
        row = {c: "" for c in _schema.MINED_CANDIDATE_COLS}
        row.update(
            {
                "candidate_id": "C" + cid,
                "entity_key": iid,
                "adsh": hit["adsh"],
                "doc": hit["doc"],
                "form": hit["form"],
                "file_date": hit["file_date"],
                "items": ";".join(hit.get("items") or []),
                "doc_id": sha,
                "char_start": str(r["char_start"]),
                "char_end": str(r["char_end"]),
                "anchor_kind": r["kind"],
                "anchor_text": r["anchor_text"],
                "phrase": r["phrase"],
                "phrase_start": str(r["phrase_start"]),
                "date_start": r["start"],
                "date_end": r["end"],
                "date_precision": r["precision"],
                "date_mod": r["date_mod"],
                "anchored": str(r["anchored"]),
                "assertion": r["assertion"],
                "outcome_words": r["outcome_words"],
                "rule_version": RULE_VERSION,
                "decision": decision,
                "reason": reason,
                "mined_at": now,
            }
        )
        rows.append(row)
    return rows


def _write_ledger(rows: list[dict], con) -> int:
    """Upsert by candidate_id (document + offset + rule version); rows from
    earlier rule versions are kept, so runs are diffable across versions."""
    from biointel import schema as _schema

    existing = (
        store.read_table("mined_candidates", con=con)
        if store.has_table("mined_candidates", con)
        else []
    )
    by_id = {r["candidate_id"]: r for r in existing}
    for r in rows:
        by_id[r["candidate_id"]] = r
    return store.write_table(
        "mined_candidates", list(by_id.values()), _schema.MINED_CANDIDATE_COLS, con=con
    )


def run(
    limit: int | None = None,
    since: str | None = None,
    forms: str = DEFAULT_FORMS,
    query: str = DEFAULT_QUERY,
    docs_per_company: int = 20,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    since = since or date(today.year - 1, today.month, today.day).isoformat()
    con = store.connect()
    companies = [c for c in read_companies() if (c.get("CIK") or "").strip()]
    if limit:
        companies = companies[:limit]
    run_ = results.start(
        "calendar",
        "mine-pdufa run",
        ["companies", "events_table", "references", "captures"],
        {"since": since, "forms": forms, "query": query, "companies": len(companies)},
    )
    all_rows, ledger = [], []
    stats = {
        "queries": 0,
        "hits": 0,
        "docs": 0,
        "fetch_failed": 0,
        "examined": 0,
        "candidates": 0,
        "past": 0,
        "no_year_skipped": 0,
        "errors": 0,
    }
    zero = {"inserted": 0, "refreshed": 0, "superseded": 0, "total": 0}
    counts, flushed_ledger = dict(zero), 0

    def _flush():
        nonlocal all_rows, ledger, counts, flushed_ledger
        if all_rows:
            c_ = _upsert(all_rows, _identity, con)
            counts = {k: counts.get(k, 0) + c_[k] for k in ("inserted", "refreshed", "superseded")}
            counts["total"] = c_["total"]
        if ledger:
            flushed_ledger = _write_ledger(ledger, con)
        all_rows, ledger = [], []

    for n_done, c in enumerate(companies, 1):
        try:
            payload = search(query, forms, since, today.isoformat(), cik=c["CIK"])
        except requests.RequestException:
            payload = {"error": "exception"}
        stats["queries"] += 1
        if n_done % 50 == 0:
            _flush()
        if payload.get("error"):
            stats["errors"] += 1
            continue
        hits = hits_of(payload)
        stats["hits"] += len(hits)
        hits.sort(key=lambda h: h["file_date"], reverse=True)
        for h in hits[:docs_per_company]:
            got = capture_document(h, con)
            if not got:
                stats["fetch_failed"] += 1
                continue
            stats["docs"] += 1
            sha, text = got
            recs = examine(text, h["file_date"])
            cands = [r for r in recs if r["decision"] == "accepted"]
            stats["examined"] += len(recs)
            stats["candidates"] += len(cands)
            stats["no_year_skipped"] += sum(
                1 for r in recs if r["reason"] in ("no_year_anchored", "no_year")
            )
            ledger.extend(_ledger_rows(recs, h, str(c["IID"]), sha, today))
            rows, past = _rows_from(cands, h, str(c["IID"]), sha, today)
            stats["past"] += past
            all_rows.extend(rows)
    _flush()
    if not counts.get("total") and store.has_table("events_table", con):
        counts["total"] = len(store.read_table("events_table", con=con))
    stats["ledger_rows"] = flushed_ledger
    stats["forward_rows"] = counts["inserted"] + counts["refreshed"]
    for k, v in {**stats, **counts}.items():
        run_.metric("_", k, v)
    run_id = results.finish(run_)
    msg = (
        f"mine-pdufa: {len(companies)} companies, {stats['queries']} queries, {stats['hits']} hits, "
        f"{stats['docs']} documents mined ({stats['fetch_failed']} fetch failures, {stats['errors']} query errors); "
        f"{stats['examined']} windows examined -> ledger {stats['ledger_rows']} rows ({RULE_VERSION}); "
        f"{stats['candidates']} accepted ({stats['past']} past, {stats['no_year_skipped']} no-year) -> "
        f"{stats['forward_rows']} forward rows ({counts['inserted']} inserted, {counts['refreshed']} refreshed, "
        f"{counts['superseded']} superseded; events_table now {counts['total']} rows) (run {run_id} recorded)"
    )
    print(msg)
    return {"status": "ok", **stats, **counts, "rows": stats["forward_rows"], "run_id": run_id}


# ---------------------------------------------------------------- precision sample
def sample(n: int = 20, seed: int = 20260901) -> int:
    con = store.connect()
    rows = [
        r
        for r in store.read_table("events_table", con=con)
        if (r.get("provenance") or "").startswith("source=efts")
        and not r.get("event_date")
        and r.get("status") == ""
    ]
    if not rows:
        print("mine-pdufa sample: no mined rows")
        return 1
    rnd = random.Random(seed)
    pick = rnd.sample(rows, min(n, len(rows)))
    print(
        f"mine-pdufa sample: {len(pick)} of {len(rows)} mined forward rows (seed {seed}); mark each CORRECT or WRONG"
    )
    for i, r in enumerate(pick, 1):
        print(
            f"\n[{i}] {r['event_id']}  IID {r['entity_key']}  {r['outcome_subtype']}  {r['scheduled_date']}..{r['scheduled_date_end']} ({r['date_precision']})"
        )
        print(f"    {r['source_url']}")
        print(f'    "{r["date_raw"]}"')
    return 0


def precision(correct: int, total: int) -> int:
    run_ = results.start(
        "calendar", "mine-pdufa precision", ["events_table"], {"correct": correct, "total": total}
    )
    p = correct / total if total else 0.0
    run_.metric("_", "precision", p)
    run_.metric("_", "correct", correct)
    run_.metric("_", "total", total)
    run_id = results.finish(run_)
    print(f"mine-pdufa precision: {correct}/{total} = {p:.3f} (run {run_id} recorded)")
    return 0


# ---------------------------------------------------------------- recall vs a benchmark snapshot (ICS)
def parse_ics(text: str) -> list[dict]:
    """VEVENT -> {date, summary, description}. Folded lines are unfolded."""
    text = re.sub(r"\r?\n[ \t]", "", text)
    out = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.S):
        d = re.search(r"DTSTART(?:;VALUE=DATE)?:(\d{8})", block)
        s = re.search(r"SUMMARY:(.*)", block)
        desc = re.search(r"DESCRIPTION:(.*)", block)
        if not d:
            continue
        out.append(
            {
                "date": f"{d[1][:4]}-{d[1][4:6]}-{d[1][6:8]}",
                "summary": (s[1].strip() if s else ""),
                "description": (desc[1].strip().replace("\\,", ",") if desc else ""),
            }
        )
    return out


def _name_key(s: str) -> str:
    s = re.sub(
        r"\bPDUFA\b|\bDE\b|\bINC\b|\bCORP\b|\bLTD\b|\bPLC\b|\bHOLDINGS?\b|[^A-Za-z0-9 ]",
        " ",
        s.upper(),
    )
    return " ".join(s.split())


def recall(ics_path: str, today: date | None = None) -> int:
    today = today or date.today()
    con = store.connect()
    p = Path(ics_path)
    if not p.exists():
        print(f"mine-pdufa recall: no such file {p}")
        return 1
    events = [
        e
        for e in parse_ics(p.read_text(encoding="utf-8", errors="replace"))
        if e["date"] >= today.isoformat()
    ]
    mined = [
        r
        for r in store.read_table("events_table", con=con)
        if (r.get("provenance") or "").startswith("source=efts")
        and r.get("outcome_subtype") == "pdufa_target_date"
        and r.get("status") == ""
        and r.get("date_precision") == "day"
    ]
    comps = read_companies()
    ticker_by_iid = {str(c["IID"]): (c.get("Ticker") or "").upper() for c in comps}
    name_by_iid = {str(c["IID"]): _name_key(c.get("Name") or "") for c in comps}
    matched, unmatched = [], []
    for e in events:
        parts = e["summary"].split()
        bench_ticker = parts[0].upper() if parts else ""
        bench = _name_key(e["summary"])
        hit = None
        for r in mined:
            if r["scheduled_date"] != e["date"]:
                continue
            tk = ticker_by_iid.get(r["entity_key"], "")
            nm = name_by_iid.get(r["entity_key"], "")
            if (tk and tk == bench_ticker) or (nm and nm in bench):
                hit = r
                break
        (matched if hit else unmatched).append(e)
    reverse = [r for r in mined if not any(e["date"] == r["scheduled_date"] for e in events)]
    run_ = results.start(
        "calendar",
        "mine-pdufa recall",
        ["events_table"],
        {"ics": str(p), "benchmark_events": len(events)},
    )
    rc = len(matched) / len(events) if events else 0.0
    for k, v in (
        ("benchmark_events", len(events)),
        ("matched", len(matched)),
        ("unmatched", len(unmatched)),
        ("mined_exact_pdufa", len(mined)),
        ("mined_not_in_benchmark", len(reverse)),
        ("recall", rc),
    ):
        run_.metric("_", k, v)
    run_id = results.finish(run_)
    print(
        f"mine-pdufa recall vs benchmark snapshot: {len(matched)}/{len(events)} upcoming benchmark PDUFA events matched "
        f"= {rc:.3f}; {len(reverse)} mined exact-date PDUFA rows not in the benchmark (run {run_id} recorded)"
    )
    for e in unmatched[:25]:
        print(f"  MISSED  {e['date']}  {e['summary']}")
    if len(unmatched) > 25:
        print(f"  ... {len(unmatched) - 25} more missed")
    return 0


def cli(argv: list[str]) -> int:
    sub = argv[0] if argv else "help"

    def _opt(flag, default=None):
        return (
            argv[argv.index(flag) + 1]
            if flag in argv and argv.index(flag) + 1 < len(argv)
            else default
        )

    if sub == "run":
        lim = _opt("--limit")
        r = run(
            limit=int(lim) if lim else None,
            since=_opt("--since"),
            forms=_opt("--forms", DEFAULT_FORMS),
        )
        return 0 if r["status"] == "ok" else 1
    if sub == "sample":
        return sample(int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 20)
    if sub == "precision":
        if len(argv) < 3:
            print("usage: mine-pdufa precision CORRECT TOTAL")
            return 1
        return precision(int(argv[1]), int(argv[2]))
    if sub == "recall":
        if len(argv) < 2:
            print("usage: mine-pdufa recall PATH_TO_SNAPSHOT.ics")
            return 1
        return recall(argv[1])
    print(
        "mine-pdufa: run [--limit N] [--since YYYY-MM-DD] [--forms F] | sample [N] | precision CORRECT TOTAL | recall SNAPSHOT.ics"
    )
    return 1


__all__ = [
    "search",
    "hits_of",
    "extract",
    "run",
    "sample",
    "precision",
    "recall",
    "parse_ics",
    "normalize_text",
]
