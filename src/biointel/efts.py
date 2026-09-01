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

import calendar as _cal
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
    rf"(?:first|second|third|fourth|last|1st|2nd|3rd|4th)\s+quarter\s+(?:of\s+)?\d{{4}}|"
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
_PDUFA_BOILERPLATE = re.compile(
    r"reauthoriz|re-authoriz|user fee programs?|set to expire|announcement that the FDA has assigned|earlier of \(i\)",
    re.I,
)
_REPORT_OBJECT = re.compile(r"\b(data|results?|readout|topline|top-line|findings)\b", re.I)
_SEGMENT_BREAK = re.compile(r"[•●○§▪]|\s[o·]\s|(?<=[.;!?])\s+(?=[A-Z\u201c\"])")
_PERIOD_LABEL = re.compile(
    r"^\s*(financial|results|highlights|earnings|ended|ending|conference)", re.I
)
_PERIOD_LEAD = re.compile(
    r"\b(as of|ended|ending|through|since|during|into|until|runway (?:into|through))(?:\s+the)?\s*$",
    re.I,
)
_PAST_AFTER = re.compile(
    r"^\s*(?:\w+\s+){0,2}(presented|announced|reported|released|published|were|was)\b", re.I
)
_AFTER_PREF = re.compile(
    r"^\s*(?:[A-Za-z]+\s+){0,3}(expected|anticipated|planned|targeted|projected)\b", re.I
)
_META_PDUFA = re.compile(
    r"clarity on|expected to be assigned|will be assigned|to be determined|date is (?:currently )?expected",
    re.I,
)


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
            "note": f"captured by mine-pdufa;form={hit['form']};cik={hit['cik']}",
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
    p = re.sub(r"^last\s+quarter", "fourth quarter", p, flags=re.I)
    p = re.sub(r"^([A-Za-z]+)\s+of\s+(\d{4})$", r"\1 \2", p)  # "August of 2026"
    p = re.sub(r"^([A-Za-z]+)\.", r"\1", p)  # "Oct. 10, 2026" -> "Oct 10, 2026"
    p = re.sub(r"^Sept\b", "Sep", p)
    return parse_date_range(p)


RULE_VERSION = "1.5b-r9"
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
            if kind == "pdufa" and _PDUFA_BOILERPLATE.search(segment):
                rec["reason"] = "boilerplate"  # PDUFA reauthorization text / contract clauses
                out.append(rec)
                continue
            if kind == "pdufa" and _META_PDUFA.search(segment):
                rec["reason"] = "meta_statement"  # about when the date will be known, not the date
                out.append(rec)
                continue
            if (
                kind == "readout"
                and rec["assertion"] == "affirmed"
                and _PAST_AFTER.match(after[:40])
            ):
                rec["assertion"] = "historical"  # "topline data presented at ..."
            if len(_DATE_PHRASE.findall(segment)) >= 4:
                rec["reason"] = (
                    "table_layout"  # timeline headers / slide fragments: attribution ambiguous
                )
                out.append(rec)
                continue
            # "expect to report ..." is a readout anchor only when what follows is data/results
            report_verb = bool(re.match(r"expect", am.group(0), re.I))
            if kind == "readout" and report_verb and not _REPORT_OBJECT.search(after[:60]):
                rec["reason"] = "not_a_readout"
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
                d_after, d_before = a_m.start(), len(before) - b_m.end()
                if (kind == "readout" and report_verb) or _AFTER_PREF.match(after[:50]):
                    use_after = (
                        True  # "expect to report ... in X", "with topline data anticipated in X"
                    )
                elif abs(d_after - d_before) <= 3:
                    rank = {"day": 5, "month": 4, "quarter": 3, "half": 2, "year": 1}
                    ra = rank.get((_range_for(a_m["d"]) or ("", "", ""))[2], 0)
                    rb = rank.get((_range_for(b_m["d"]) or ("", "", ""))[2], 0)
                    use_after = ra >= rb  # near-tie: the more specific phrase wins
                else:
                    use_after = d_after <= d_before
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
    tickers = {t for t in ticker_by_iid.values() if t}
    member_events = [e for e in events if (e["summary"].split() or [""])[0].upper() in tickers]
    member_matched = [e for e in matched if (e["summary"].split() or [""])[0].upper() in tickers]
    rc_members = len(member_matched) / len(member_events) if member_events else 0.0
    for k, v in (
        ("benchmark_events", len(events)),
        ("matched", len(matched)),
        ("unmatched", len(unmatched)),
        ("mined_exact_pdufa", len(mined)),
        ("mined_not_in_benchmark", len(reverse)),
        ("recall", rc),
        ("member_events", len(member_events)),
        ("member_matched", len(member_matched)),
        ("recall_members", rc_members),
    ):
        run_.metric("_", k, v)
    run_id = results.finish(run_)
    print(
        f"mine-pdufa recall vs benchmark snapshot: {len(matched)}/{len(events)} upcoming benchmark PDUFA events matched "
        f"= {rc:.3f}; members only {len(member_matched)}/{len(member_events)} = {rc_members:.3f}; "
        f"{len(reverse)} mined exact-date PDUFA rows not in the benchmark (run {run_id} recorded)"
    )
    for e in unmatched[:25]:
        print(f"  MISSED  {e['date']}  {e['summary']}")
        if e.get("description"):
            print(f"          benchmark note: {e['description'][:160]}")
    if len(unmatched) > 25:
        print(f"  ... {len(unmatched) - 25} more missed")
    return 0


# ---------------------------------------------------------------- evaluation tooling (1.5b-eval)
def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def cached_hits(con) -> dict[str, list[dict]]:
    """Filing documents already captured by the miner, grouped by CIK, as
    hit dicts (adsh, doc, form, file_date, url, items) — so a rule change is
    re-run against the library without EFTS queries or fetching."""
    if not store.has_table("references", con):
        return {}
    links = {}
    for lk in (
        store.read_table("reference_links", con=con)
        if store.has_table("reference_links", con)
        else []
    ):
        if lk["key_type"] == "CIK":
            links.setdefault(lk["ref_id"], lk["entity_key"])
    items_by_doc = {}
    if store.has_table("mined_candidates", con):
        for r in store.read_table("mined_candidates", con=con):
            if r.get("items"):
                items_by_doc.setdefault((r["adsh"], r["doc"]), r["items"].split(";"))
    out: dict[str, list[dict]] = {}
    for ref in store.read_table("references", con=con):
        if ref.get("source_system") != "efts" or ref.get("status") != "active":
            continue
        key = ref.get("source_key") or ""
        if ":" not in key:
            continue
        adsh, doc = key.split(":", 1)
        note = ref.get("note") or ""
        cik = links.get(ref["ref_id"], "") or next(
            (p[4:] for p in note.split(";") if p.startswith("cik=")), ""
        )
        form = next((p[5:] for p in note.split(";") if p.startswith("form=")), "")
        if not form:
            parts = (ref.get("title") or "").split()
            form = next((p for p in parts if p in ("8-K", "10-Q", "10-K", "6-K", "20-F")), "")
        out.setdefault(str(int(cik)) if cik.isdigit() else cik, []).append(
            {
                "adsh": adsh,
                "doc": doc,
                "cik": cik,
                "name": ref.get("title") or "",
                "file_date": ref.get("published_at") or "",
                "form": form,
                "file_type": "",
                "items": items_by_doc.get((adsh, doc), []),
                "url": ref.get("url") or "",
            }
        )
    return out


def _retire_stale(examined_docs: set, produced_ids: set, con) -> int:
    """Rows written by an earlier rule version from a document that the
    current rules re-examined without re-producing them are superseded
    (reason recorded in provenance), so a retired rule's rows do not
    linger. Returns the count."""
    if not store.has_table("events_table", con) or not examined_docs:
        return 0
    from biointel.forward import ALL_COLS

    rows = store.read_table("events_table", con=con)
    n = 0
    for r in rows:
        prov = r.get("provenance") or ""
        if (
            not prov.startswith("source=efts")
            or r.get("status") == "superseded"
            or r.get("event_date")
        ):
            continue
        adsh = next((p[5:] for p in prov.split(";") if p.startswith("adsh=")), "")
        doc = next((p[4:] for p in prov.split(";") if p.startswith("doc=")), "")
        if (adsh, doc) in examined_docs and r["event_id"] not in produced_ids:
            r["status"] = "superseded"
            r["provenance"] = prov + f";retired_by={RULE_VERSION}"
            n += 1
    if n:
        store.write_table("events_table", rows, ALL_COLS, con=con)
    return n


def run_cached(today: date | None = None) -> dict:
    """Re-examine every captured filing document with the current rules; no
    network. Ledger rows are written under the current RULE_VERSION and
    forward rows re-derived (idempotent)."""
    today = today or date.today()
    con = store.connect()
    by_cik = cached_hits(con)
    n_refs = (
        sum(1 for r in store.read_table("references", con=con) if r.get("source_system") == "efts")
        if store.has_table("references", con)
        else 0
    )
    companies = [c for c in read_companies() if (c.get("CIK") or "").strip()]
    examined_docs, produced_ids = set(), set()
    run_ = results.start(
        "calendar",
        "mine-pdufa run --cached",
        ["references", "captures", "events_table"],
        {"rule_version": RULE_VERSION, "docs": sum(len(v) for v in by_cik.values())},
    )
    all_rows, ledger = [], []
    stats = {
        "docs": 0,
        "missing_text": 0,
        "examined": 0,
        "candidates": 0,
        "past": 0,
        "no_year_skipped": 0,
    }
    counts = {"inserted": 0, "refreshed": 0, "superseded": 0, "total": 0}
    for n, c in enumerate(companies, 1):
        for h in by_cik.get(str(int(c["CIK"])), []):
            got = capture_document(h, con)
            if not got:
                stats["missing_text"] += 1
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
            examined_docs.add((h["adsh"], h["doc"]))
            produced_ids.update(r["event_id"] for r in rows)
        if n % 100 == 0 and (all_rows or ledger):
            if all_rows:
                c_ = _upsert(all_rows, _identity, con)
                for k in ("inserted", "refreshed", "superseded"):
                    counts[k] += c_[k]
                counts["total"] = c_["total"]
            _write_ledger(ledger, con)
            all_rows, ledger = [], []
    if all_rows:
        c_ = _upsert(all_rows, _identity, con)
        for k in ("inserted", "refreshed", "superseded"):
            counts[k] += c_[k]
        counts["total"] = c_["total"]
    n_ledger = (
        _write_ledger(ledger, con)
        if ledger
        else (
            len(store.read_table("mined_candidates", con=con))
            if store.has_table("mined_candidates", con)
            else 0
        )
    )
    stats["ledger_rows"] = n_ledger
    stats["retired"] = _retire_stale(examined_docs, produced_ids, con)
    stats["efts_references"] = n_refs
    for k, v in {**stats, **counts}.items():
        run_.metric("_", k, v)
    run_id = results.finish(run_)
    print(
        f"mine-pdufa run --cached ({RULE_VERSION}): {stats['docs']} cached documents re-examined "
        f"({stats['missing_text']} without text); {stats['examined']} windows -> ledger now {n_ledger} rows; "
        f"{stats['candidates']} accepted ({stats['past']} past, {stats['no_year_skipped']} no-year) -> "
        f"{counts['inserted']} inserted, {counts['refreshed']} refreshed, {counts['superseded']} superseded; "
        f"{stats['retired']} stale rows retired; events_table now {counts['total']} rows; "
        f"{n_refs} efts references on file (run {run_id} recorded)"
    )
    return {"status": "ok", **stats, **counts, "run_id": run_id}


def sample_ledger(n: int = 60, seed: int = 20260901, today: date | None = None) -> int:
    """Blind, seeded sample of accepted forward statements from the ledger at
    the current rule version, excluding ones already reviewed."""
    today = today or date.today()
    con = store.connect()
    if not store.has_table("mined_candidates", con):
        print("mine-pdufa sample: no ledger")
        return 1
    reviewed = (
        {r["candidate_id"] for r in store.read_table("candidate_reviews", con=con)}
        if store.has_table("candidate_reviews", con)
        else set()
    )
    pool = [
        r
        for r in store.read_table("mined_candidates", con=con)
        if r["rule_version"] == RULE_VERSION
        and r["decision"] == "accepted"
        and r["date_end"] >= today.isoformat()
        and r["candidate_id"] not in reviewed
    ]
    if not pool:
        print(f"mine-pdufa sample: no unreviewed accepted candidates at {RULE_VERSION}")
        return 1
    texts = {}
    caps = (
        {c["capture_id"]: c for c in store.read_table("captures", con=con)}
        if store.has_table("captures", con)
        else {}
    )
    pick = random.Random(seed).sample(pool, min(n, len(pool)))
    print(
        f"mine-pdufa sample: {len(pick)} of {len(pool)} unreviewed accepted candidates at {RULE_VERSION} (seed {seed}); "
        f"judge each with: mine-pdufa judge <candidate_id> correct|wrong|unsure [--note ...]"
    )
    for i, r in enumerate(pick, 1):
        cap = caps.get(r["doc_id"])
        if cap and r["doc_id"] not in texts:
            p = config.DATA / cap["path"]
            texts[r["doc_id"]] = (
                normalize_text(p.read_text(encoding="utf-8", errors="replace"))
                if p.exists()
                else ""
            )
        t = texts.get(r["doc_id"], "")
        a, b = int(r["char_start"]), int(r["char_end"])
        window = t[a:b].strip() if t else "(capture text unavailable)"
        print(
            f"\n[{i}] {r['candidate_id']}  IID {r['entity_key']}  {r['anchor_kind']}  {r['date_start']}..{r['date_end']} "
            f"({r['date_precision']}{' ' + r['date_mod'] if r['date_mod'] else ''})  phrase={r['phrase']!r}  {r['form']} {r['file_date']}"
        )
        print(
            f"    https://www.sec.gov/Archives/edgar/data/{r['entity_key']}/{r['adsh'].replace('-', '')}/{r['doc']}".replace(
                f"/data/{r['entity_key']}/", "/data/"
            )
        )
        print(f'    "{window[:420]}"')
    return 0


def judge(candidate_id: str, verdict: str, note: str = "") -> int:
    import getpass

    from biointel import schema as _schema

    if verdict not in _schema.REVIEW_VERDICTS:
        print(f"verdict must be one of {_schema.REVIEW_VERDICTS}")
        return 1
    con = store.connect()
    led = (
        {r["candidate_id"]: r for r in store.read_table("mined_candidates", con=con)}
        if store.has_table("mined_candidates", con)
        else {}
    )
    if candidate_id not in led:
        print(f"unknown candidate {candidate_id}")
        return 1
    rows = (
        store.read_table("candidate_reviews", con=con)
        if store.has_table("candidate_reviews", con)
        else []
    )
    rows = [r for r in rows if r["candidate_id"] != candidate_id]
    rows.append(
        {
            "review_id": "V"
            + hashlib.sha256(
                f"{candidate_id}|{led[candidate_id]['rule_version']}".encode()
            ).hexdigest()[:16],
            "candidate_id": candidate_id,
            "rule_version": led[candidate_id]["rule_version"],
            "verdict": verdict,
            "reviewer": getpass.getuser(),
            "note": note,
            "reviewed_at": _now(),
        }
    )
    store.write_table("candidate_reviews", rows, _schema.CANDIDATE_REVIEW_COLS, con=con)
    print(f"judged {candidate_id} {verdict}")
    return 0


def precision_from_reviews(rule_version: str | None = None) -> int:
    con = store.connect()
    rv = rule_version or RULE_VERSION
    rows = [
        r
        for r in (
            store.read_table("candidate_reviews", con=con)
            if store.has_table("candidate_reviews", con)
            else []
        )
        if r["rule_version"] == rv and r["verdict"] in ("correct", "wrong")
    ]
    k, n = sum(1 for r in rows if r["verdict"] == "correct"), len(rows)
    lo, hi = _wilson(k, n)
    run_ = results.start(
        "calendar",
        "mine-pdufa precision",
        ["candidate_reviews"],
        {"rule_version": rv, "reviews": n},
    )
    for kk, vv in (
        ("precision", k / n if n else 0.0),
        ("correct", k),
        ("total", n),
        ("ci_low", lo),
        ("ci_high", hi),
    ):
        run_.metric("_", kk, vv)
    run_id = results.finish(run_)
    print(
        f"mine-pdufa precision ({rv}): {k}/{n} = {k / n if n else 0:.3f}  95% CI [{lo:.3f}, {hi:.3f}] (run {run_id} recorded)"
    )
    return 0


def explain(ticker: str, iso_date: str, today: date | None = None, live: bool = False) -> int:
    """Why a benchmark PDUFA date is missing: not a member / no cached
    documents / date absent from the documents / seen and rejected (reason)."""
    con = store.connect()
    comps = [c for c in read_companies() if (c.get("Ticker") or "").upper() == ticker.upper()]
    if not comps:
        print(
            f"EXPLAIN {ticker} {iso_date}: NOT_A_MEMBER (no company with that ticker in the registry)"
        )
        return 0
    c = comps[0]
    iid, cik = str(c["IID"]), str(int(c["CIK"])) if (c.get("CIK") or "").strip() else ""
    docs = cached_hits(con).get(cik, []) if cik else []
    y, m, d = iso_date.split("-")
    month = _cal.month_name[int(m)]
    forms = [
        f"{month} {int(d)}, {y}",
        f"{month[:3]}. {int(d)}, {y}",
        f"{month[:3]} {int(d)}, {y}",
        f"{int(m)}/{int(d)}/{y}",
        f"{m}/{d}/{y}",
    ]
    found = []
    for h in docs:
        got = capture_document(h, con)
        if not got:
            continue
        _sha, text = got
        for f in forms:
            i = text.find(f)
            if i >= 0:
                found.append((h, f, text[max(0, i - 160) : i + 160]))
                break
    led = [
        r
        for r in (
            store.read_table("mined_candidates", con=con)
            if store.has_table("mined_candidates", con)
            else []
        )
        if r["entity_key"] == iid and r["date_start"] == iso_date
    ]
    print(
        f"EXPLAIN {ticker} {iso_date}: IID {iid} CIK {cik or '-'}; cached documents {len(docs)}; documents containing the date {len(found)}; ledger rows at that date {len(led)}"
    )
    if not cik:
        print("  -> NO_CIK: company has no CIK in the registry; EFTS per-company query impossible")
    elif not docs:
        print(
            "  -> NO_DOCUMENTS: EFTS returned no matching filings in the window, or the company filed under other forms"
        )
    elif not found:
        print(
            "  -> DATE_NOT_IN_DOCS: none of the cached documents states that date (later filing, or disclosed only in a press release not filed)"
        )
    for h, f, snip in found[:3]:
        print(f"  DOC {h['form']} {h['file_date']} {h['adsh']}:{h['doc']}  form={f!r}")
        print(f"      ...{snip}...")
    for r in led[:5]:
        print(
            f"  LEDGER {r['candidate_id']} {r['rule_version']} {r['anchor_kind']} {r['decision']} {r['reason'] or '-'} assertion={r['assertion']} phrase={r['phrase']!r}"
        )
    if found and not led:
        print(
            "  -> SEEN_NOT_EXTRACTED: the date is in a document but no ledger row carries it — anchor vocabulary or window rule gap"
        )
    if live and cik:
        today = today or date.today()
        since = date(today.year - 2, today.month, today.day).isoformat()
        probed = False
        for f in (forms[0], forms[2]):
            payload = search(f'"{f}"', "8-K,10-Q,10-K,6-K,20-F", since, today.isoformat(), cik=cik)
            hs = hits_of(payload)
            print(f"  LIVE EFTS q={f!r}: {len(hs)} filings by this company contain the date string")
            for h in hs[:4]:
                print(f"      {h['form']} {h['file_date']} {h['adsh']}:{h['doc']}")
            if hs:
                cached_keys = {(d["adsh"], d["doc"]) for d in docs}
                new = [h for h in hs if (h["adsh"], h["doc"]) not in cached_keys]
                verdict = (
                    "VOCABULARY_MISS: filing(s) exist but our query terms did not retrieve them"
                    if new
                    else "RETRIEVED_BUT_NOT_IN_TEXT: filing retrieved; date string not found in its normalized text"
                )
                print(f"  -> {verdict} ({len(new)} not in cache)")
                probed = True
                break
        if not probed:
            print(
                "  -> NOT_IN_EDGAR_FULLTEXT: no filing by this company contains the date string (disclosed outside EDGAR, or after the index lag)"
            )
    return 0


def extras(ics_path: str, today: date | None = None) -> int:
    """Mined exact-date PDUFA rows absent from the benchmark, with windows,
    for inspection (true finds vs false positives)."""
    today = today or date.today()
    con = store.connect()
    events = [
        e
        for e in parse_ics(Path(ics_path).read_text(encoding="utf-8", errors="replace"))
        if e["date"] >= today.isoformat()
    ]
    dates = {e["date"] for e in events}
    mined = [
        r
        for r in store.read_table("events_table", con=con)
        if (r.get("provenance") or "").startswith("source=efts")
        and r.get("outcome_subtype") == "pdufa_target_date"
        and r.get("status") == ""
        and r.get("date_precision") == "day"
    ]
    ex = [r for r in mined if r["scheduled_date"] not in dates]
    print(f"mine-pdufa extras: {len(ex)} exact-date PDUFA rows not in the benchmark snapshot")
    for r in ex:
        print(
            f"\n  {r['event_id']}  IID {r['entity_key']}  {r['scheduled_date']}  {r['source_url']}"
        )
        print(f'    "{r["date_raw"][:300]}"')
    return 0


def cli(argv: list[str]) -> int:
    sub = argv[0] if argv else "help"

    def _opt(flag, default=None):
        return (
            argv[argv.index(flag) + 1]
            if flag in argv and argv.index(flag) + 1 < len(argv)
            else default
        )

    if sub == "run" and "--cached" in argv:
        return 0 if run_cached()["status"] == "ok" else 1
    if sub == "run":
        lim = _opt("--limit")
        r = run(
            limit=int(lim) if lim else None,
            since=_opt("--since"),
            forms=_opt("--forms", DEFAULT_FORMS),
        )
        return 0 if r["status"] == "ok" else 1
    if sub == "sample":
        n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 60
        seed = int(_opt("--seed", "20260901"))
        return sample_ledger(n, seed)
    if sub == "judge":
        if len(argv) < 3:
            print("usage: mine-pdufa judge CANDIDATE_ID correct|wrong|unsure [--note TEXT]")
            return 1
        return judge(argv[1], argv[2], _opt("--note", "") or "")
    if sub == "precision":
        if len(argv) >= 3 and argv[1].isdigit() and argv[2].isdigit():
            return precision(int(argv[1]), int(argv[2]))  # legacy: typed count
        return precision_from_reviews(_opt("--rule"))
    if sub == "explain":
        if len(argv) < 3:
            print("usage: mine-pdufa explain TICKER YYYY-MM-DD")
            return 1
        return explain(argv[1], argv[2], live="--live" in argv)
    if sub == "extras":
        if len(argv) < 2:
            print("usage: mine-pdufa extras SNAPSHOT.ics")
            return 1
        return extras(argv[1])
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
