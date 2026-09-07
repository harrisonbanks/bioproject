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

import hashlib
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


def _ts() -> str:
    """Local wall-clock stamp for progress lines, so 'is it alive' is
    answered by the line itself (operator, 2026-09-05)."""
    from datetime import datetime as _dt

    return _dt.now().strftime("%Y-%m-%d %H:%M:%S")


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


def _ext_for(ctype: str) -> str:
    return {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "application/xml": ".xml",
        "text/xml": ".xml",
    }.get(ctype, ".htm")


def _prefetch(urls: list[str]) -> dict[str, tuple[bytes, str, str]]:
    """Fetch many URLs through the parallel pool when it is enabled; return
    url -> (bytes, ext, content_type) for the successes. When the pool is
    disabled (the default until fetch-probe passes) returns {} and callers
    fall back to the serial fetcher unchanged."""
    if not config.FETCH_POOL_ENABLED or not urls:
        return {}
    from biointel import fetchpool

    pool = fetchpool.FetchPool(rate=config.FETCH_POOL_RATE, workers=config.FETCH_POOL_WORKERS)
    out: dict[str, tuple[bytes, str, str]] = {}
    for res in pool.fetch_all(urls):
        if res.status == 200 and res.content is not None:
            out[res.url] = (res.content, _ext_for(res.content_type), res.content_type)
    if pool.stats.backoffs:
        log.warning(
            f"{_ts()}  fetch pool backed off {pool.stats.backoffs}x; rate ended at "
            f"{pool.stats.rate_end}/s"
        )
    return out


def _hit_note(hit: dict) -> str:
    """Reference note carrying the search metadata a later re-parse needs."""
    return (
        f"captured by stakes-probe;form={hit['form']};cik={hit['cik']}"
        f";ciks={'|'.join(hit.get('ciks') or [])};file_date={hit['file_date']}"
    )


# Pending note repairs, keyed by ref_id, flushed through the store layer at
# the end of a pass. Nothing here writes SQL: P18 requires every table read
# and write to go through `store`, and hand-written SQL against a table whose
# name is a reserved word is exactly the kind of breakage that rule prevents.
_PENDING_NOTES: dict[str, str] = {}


def _backfill_note(ref_row: dict, hit: dict) -> bool:
    """Queue the search CIK list onto a pre-existing reference note. Returns
    True when a repair was queued. Idempotent: a note already carrying
    `ciks=` is left untouched, so re-runs queue nothing."""
    note = str(ref_row.get("note") or "")
    if "ciks=" in note or not (hit.get("ciks") or []):
        return False
    new_note = _hit_note(hit)
    _PENDING_NOTES[str(ref_row["ref_id"])] = new_note
    ref_row["note"] = new_note  # the index row now matches what flush will write
    return True


def flush_note_backfill(con=None) -> int:
    """Apply queued note repairs through `store.update_rows` (P18). Row-level
    update by declared key; no table or column name is written into SQL here,
    so the reserved-word collision on `references` cannot recur. Returns the
    number of rows changed."""
    if not _PENDING_NOTES:
        return 0
    con = con or store.connect()
    changes = [{"ref_id": rid, "note": note} for rid, note in _PENDING_NOTES.items()]
    changed = store.update_rows("references", changes, con=con)
    _PENDING_NOTES.clear()
    return changed


# URL -> (reference row, capture_id, ext) for every active capture, built
# ONCE per pass. Defect fixed 2026-09-04: the previous lookup re-read the
# whole references and captures tables for every hit — cheap on the first
# pass when the tables were empty, but with ~25k rows each and ~37k hits the
# r6 re-parse ground for hours on my scan instead of on SEC's rate limit.
_CAPTURE_INDEX: dict[str, tuple[dict, str, str]] | None = None


def _build_capture_index(con) -> dict[str, tuple[dict, str, str]]:
    idx: dict[str, tuple[dict, str, str]] = {}
    if not (store.has_table("references", con) and store.has_table("captures", con)):
        return idx
    active: dict[str, tuple[str, str]] = {}
    for c in store.read_table("captures", con=con):
        if c["status"] != "active":
            continue
        rid = str(c["ref_id"])
        # a document capture always wins over a header capture on the same
        # reference (legacy state before the 2026-09-05 fix)
        if rid in active and str(c.get("kind") or "") == HEADER_KIND:
            continue
        active[rid] = (str(c["capture_id"]), "." + str(c.get("ext") or "htm"))
    for r in store.read_table("references", con=con):
        hit = active.get(str(r["ref_id"]))
        if hit and r.get("url"):
            idx[str(r["url"])] = (r, hit[0], hit[1])
    return idx


def reset_capture_index() -> None:
    global _CAPTURE_INDEX
    _CAPTURE_INDEX = None


HEADER_KIND = "sec_header"  # capture kind for complete-submission headers
HEADER_SOURCE = "stakes-header"


def _capture(
    hit: dict, con, header: bool = False, prefetched: dict | None = None
) -> tuple[str, str, str] | None:
    """Capture one filing into the library with stakes-probe provenance;
    returns (capture_sha, ext, content_type). Re-captures nothing: an
    existing active capture of the same URL is reused via the per-pass
    index.

    header=True captures the complete-submission file for its SGML header.
    Defect fixed 2026-09-05: the library's identifier ladder matches on
    accession before URL, so a header capture carrying the filing's
    accession ATTACHED ITSELF to the filing's reference - the header URL was
    never recorded, the cache never hit, every run re-fetched every header,
    and the filing's reference ended up with two captures that later code
    could confuse. Header captures now get their own reference (distinct
    source system, accession kept out of the identifier field) and a
    distinct capture kind."""
    global _CAPTURE_INDEX
    if not hit["url"]:
        return None
    if _CAPTURE_INDEX is None:
        _CAPTURE_INDEX = _build_capture_index(con)
    cached = _CAPTURE_INDEX.get(hit["url"])
    if cached:
        ref_row, capture_id, ext = cached
        # Backfill: captures taken before the note carried the search CIK
        # list are enriched in place, so the library becomes self-sufficient
        # for every future rule version.
        _backfill_note(ref_row, hit)
        return capture_id, ext, "cached"
    got = (prefetched or {}).get(hit["url"]) or _fetch(hit["url"])
    if not got:
        return None
    data, ext, ctype = got
    fields = {
        "ref_type": "sec_filing",
        "url": hit["url"],
        "title": f"{hit['name']} {hit['form']} {hit['file_date']}".strip(),
        "publisher": "SEC EDGAR",
        "published_at": hit["file_date"],
        # The search result's full CIK list is persisted because the owner
        # of a 13D/13G is identified by that metadata, not by the document
        # text, for the HTML eras.
        "note": _hit_note(hit),
    }
    if header:
        fields["source_system"] = HEADER_SOURCE
        fields["source_key"] = f"{hit['adsh']}:hdr"
        fields["title"] = f"{hit['adsh']} submission header"
    else:
        fields["sec_accession"] = hit["adsh"]
        fields["source_system"] = "stakes-probe"
        fields["source_key"] = f"{hit['adsh']}:{hit['doc']}"
    ref_id, _ = library.upsert_reference(fields, con)
    sha, dst, _new = library.put_bytes(data, ext)
    library.add_capture(
        ref_id, sha, dst, HEADER_KIND if header else "fetched_html", "stakes-probe", con
    )
    if hit["cik"]:
        library.add_link(ref_id, "CIK", hit["cik"], "subject", con)
    if _CAPTURE_INDEX is not None:
        _CAPTURE_INDEX[hit["url"]] = ({"ref_id": ref_id, "note": _hit_note(hit)}, sha, ext)
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
    flush_note_backfill(con)
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


def rebuild(con=None) -> int:
    """Re-derive EVERY stake row from the library with the current rules and
    the current orientation logic. No network: the search metadata each row
    needs (the CIK list, the form, the filing date) rides in the reference
    note, which is why that backfill mattered. Replaces the table wholesale;
    the prior and new row counts, the orientation split, and per-format parse
    failures are recorded as run metrics. Written 2026-09-04 to repair the
    inverted rows the subject assumption produced."""
    from biointel import schema as _schema

    reset_capture_index()
    reset_name_index()
    con = con or store.connect()
    cols = list(_schema.EQUITY_STAKE_COLS) + list(
        _schema.TABLE_BY_PATH["silver/equity_stakes.csv"].optional
    )
    log.info(f"{_ts()}  rebuild: reading tables")
    before = (
        len(store.read_table("equity_stakes", con=con))
        if store.has_table("equity_stakes", con)
        else 0
    )
    caps: dict[str, dict] = {}
    for c in store.read_table("captures", con=con):
        if c["status"] != "active" or str(c.get("kind") or "") == HEADER_KIND:
            continue
        caps[str(c["ref_id"])] = c
    log.info(f"{_ts()}  {before} rows before; {len(caps)} active captures; starting re-parse")
    counters = {
        "references_seen": 0,
        "rows_rebuilt": 0,
        "no_note_metadata": 0,
        "parse_failures_html": 0,
        "parse_failures_xml": 0,
        "row_rejects": 0,
        "orient_subject": 0,
        "orient_filer": 0,
        "orient_unresolved": 0,
        "dupes_dropped": 0,
    }
    rows: list[dict] = []
    seen: set[tuple] = set()
    note_re = _re.compile(r"form=([^;]*);cik=([^;]*);ciks=([^;]*);file_date=([^;]*)")
    for ref in store.read_table("references", con=con):
        if str(ref.get("source_system") or "") != "stakes-probe":
            continue
        cap = caps.get(str(ref["ref_id"]))
        if not cap:
            continue
        counters["references_seen"] += 1
        if counters["references_seen"] % 5000 == 0:
            log.info(f"{_ts()}  {counters['references_seen']} references re-parsed")
        m = note_re.search(str(ref.get("note") or ""))
        if not m:
            counters["no_note_metadata"] += 1
            continue
        form, member_cik, ciks, file_date = m.groups()
        if not member_cik.strip():
            counters["no_note_metadata"] += 1
            continue
        sha = str(cap["capture_id"])
        ext = "." + str(cap.get("ext") or "htm")
        try:
            raw = library.store_path(sha, ext).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parsed = parse_structured(raw) if ext == ".xml" else parse_cover(normalize_text(raw))
        if not parsed:
            counters["parse_failures_xml" if ext == ".xml" else "parse_failures_html"] += 1
            continue
        hit = {
            "sha": sha,
            "form": form,
            "file_date": file_date,
            "adsh": str(ref.get("sec_accession") or ""),
            "ciks": [c for c in ciks.split("|") if c],
        }
        row = _row_from(hit, parsed, member_cik)
        if row is None:
            counters["row_rejects"] += 1
            continue
        counters[f"orient_{row.pop('_orientation')}"] += 1
        key = (row["holder_key"], row["issuer_key"], str(row["as_of"])[:10])
        if key in seen:
            counters["dupes_dropped"] += 1
            continue
        seen.add(key)
        rows.append(row)
    store.write_table("equity_stakes", rows, cols, con=con)
    counters["rows_rebuilt"] = len(rows)
    runr = results.start(
        "stakes-rebuild",
        "stakes rebuild",
        ["references", "captures"],
        {"rule_version": RULE_VERSION},
    )
    runr.metric("_", "rows_before", before)
    for k, v in counters.items():
        runr.metric("_", k, v)
    run_id = results.finish(
        runr,
        note=(
            f"full rebuild from the library at rule {RULE_VERSION}; orientation from the "
            "document (subject/filer/unresolved counted); replaces the r1+r6 table"
        ),
    )
    log.info(
        f"rebuilt {len(rows)} rows (was {before}); orientation subject/filer/unresolved = "
        f"{counters['orient_subject']}/{counters['orient_filer']}/{counters['orient_unresolved']}; "
        f"parse failures h/x {counters['parse_failures_html']}/{counters['parse_failures_xml']}; "
        f"no note metadata {counters['no_note_metadata']}"
    )
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- direction verification (SEC header)
# EDGAR's complete-submission file opens with an SGML header that states, as
# structured fields, who FILED the document and which SUBJECT COMPANY it is
# about - SEC's own statement of holder and issuer, independent of anything
# this module parses from the cover page. Checking every row against it
# verifies holder, issuer and direction for the whole table, not a sample.
# Percent and event date are not in the header; they remain for the two-route
# check and the human on disagreements.
_HDR_BLOCK = _re.compile(
    r"(SUBJECT COMPANY|FILED BY|FILER):\s*(.*?)(?=\n(?:SUBJECT COMPANY|FILED BY|FILER):|</SEC-HEADER>|$)",
    _re.S,
)
_HDR_CIK = _re.compile(r"CENTRAL INDEX KEY:\s*(\d+)")
_HDR_NAME = _re.compile(r"COMPANY CONFORMED NAME:\s*(.+)")


HEADER_BYTES = 65_536  # the SGML header ends within the first few KB of a submission


def _read_head(path) -> str:
    """The SEC header sits at the top of the complete-submission file; the
    rest is every exhibit in the filing, often megabytes. Read only the head.
    (2026-09-05: reading whole files made 500 cached headers take ten
    minutes - slower than fetching them.)"""
    with open(path, "rb") as fh:
        return fh.read(HEADER_BYTES).decode("utf-8", errors="replace")


def _submission_url(cik: str, adsh: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{adsh}.txt"


def parse_header(text: str) -> dict:
    """SGML header -> {'subject': [(cik, name)...], 'filed_by': [(cik, name)...]}.
    Written against real captures (probe first, rule 4.20)."""
    head = text.split("</SEC-HEADER>", 1)[0] if "</SEC-HEADER>" in text else text[:20000]
    out = {"subject": [], "filed_by": []}
    for kind, body in _HDR_BLOCK.findall(head):
        cik = _HDR_CIK.search(body)
        name = _HDR_NAME.search(body)
        pair = (str(int(cik.group(1))) if cik else "", name.group(1).strip() if name else "")
        if not pair[0]:
            continue
        out["subject" if kind == "SUBJECT COMPANY" else "filed_by"].append(pair)
    return out


def verify_direction(limit: int | None = None, probe: bool = False, con=None) -> int:
    """Fetch each row's submission header (cached in the library), compare
    holder/issuer to SEC's FILED BY / SUBJECT COMPANY, record match /
    mismatch / no_header per row as run metrics, list mismatches to an
    export for inspection. --probe captures three headers and prints them
    raw, then stops."""
    con = con or store.connect()
    reset_capture_index()
    log.info(f"{_ts()}  verify-direction: reading equity_stakes")
    rows = store.read_table("equity_stakes", con=con)
    log.info(f"{_ts()}  {len(rows)} rows; building capture index")
    global _CAPTURE_INDEX
    _CAPTURE_INDEX = _build_capture_index(con)  # the one-time build, stamped here
    log.info(f"{_ts()}  index built; starting header loop")
    by_acc: dict[str, list[dict]] = {}
    for r in rows:
        acc = str(r.get("accession") or "")
        if acc:
            by_acc.setdefault(acc, []).append(r)
    accs = list(by_acc)
    if probe:
        accs = accs[:3]
    elif limit:
        accs = accs[:limit]
    counters = {
        "accessions": len(accs),
        "headers_fetched": 0,
        "headers_cached": 0,
        "no_header": 0,
        "rows_match": 0,
        "rows_mismatch": 0,
        "rows_no_header": 0,
    }
    mismatches: list[str] = []
    import time as _time

    timing = {"lookup": 0.0, "fetch": 0.0, "read": 0.0, "parse": 0.0}
    cache_hits = 0
    for i, acc in enumerate(accs, 1):
        r0 = by_acc[acc][0]
        cik_for_path = str(r0["issuer_key"])[4:] if str(r0["issuer_key"]).startswith("CIK:") else ""
        alt = str(r0["holder_key"])[4:] if str(r0["holder_key"]).startswith("CIK:") else ""
        text = None
        for c in (cik_for_path, alt):
            if not c:
                continue
            hit = {
                "url": _submission_url(c, acc),
                "adsh": acc,
                "doc": f"{acc}.txt",
                "cik": c,
                "ciks": [c],
                "name": "",
                "form": str(r0.get("form") or ""),
                "file_date": str(r0.get("filing_date") or ""),
            }
            t0 = _time.perf_counter()
            got = _capture(hit, con, header=True)
            t1 = _time.perf_counter()
            if got:
                sha, ext, ctype = got
                cached = ctype == "cached"
                cache_hits += cached
                counters["headers_cached" if cached else "headers_fetched"] += 1
                timing["lookup" if cached else "fetch"] += t1 - t0
                try:
                    text = _read_head(library.store_path(sha, ext))
                except OSError:
                    text = None
                timing["read"] += _time.perf_counter() - t1
                break
            timing["fetch"] += t1 - t0  # a miss that had to try the network
        if text is None:
            counters["no_header"] += 1
            counters["rows_no_header"] += len(by_acc[acc])
            continue
        if probe:
            print("=" * 70 + f"\n{acc}\n" + text.split("</SEC-HEADER>", 1)[0][:3000])
            continue
        t2 = _time.perf_counter()
        hdr = parse_header(text)
        timing["parse"] += _time.perf_counter() - t2
        subj = {c for c, _n in hdr["subject"]}
        filers = {c for c, _n in hdr["filed_by"]}
        for r in by_acc[acc]:
            h = str(r["holder_key"])[4:] if str(r["holder_key"]).startswith("CIK:") else ""
            iss = str(r["issuer_key"])[4:] if str(r["issuer_key"]).startswith("CIK:") else ""
            ok = bool(subj) and iss in subj and (not filers or h in filers)
            if ok:
                counters["rows_match"] += 1
            else:
                counters["rows_mismatch"] += 1
                mismatches.append(
                    f"{acc}  row holder {r['holder_key']} issuer {r['issuer_key']} | SEC subject "
                    f"{sorted(subj)} filed_by {sorted(filers)}  ({str(r.get('owner_name') or '')[:40]})"
                )
        if i % 500 == 0 or (i <= 1000 and i % 100 == 0):
            log.info(
                f"{_ts()}  {i}/{len(accs)} headers; match {counters['rows_match']} "
                f"mismatch {counters['rows_mismatch']}; cache hits {cache_hits}; "
                f"secs lookup {timing['lookup']:.1f} fetch {timing['fetch']:.1f} "
                f"read {timing['read']:.1f} parse {timing['parse']:.1f}"
            )
    flush_note_backfill(con)
    if probe:
        return 0
    p = store.write_export("stakes_direction_mismatches.txt", "\n".join(mismatches) + "\n")
    runr = results.start(
        "stakes-verify-direction",
        "stakes verify-direction",
        ["equity_stakes", "references", "captures"],
        {"rule_version": RULE_VERSION},
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    runr.artefact(p)
    run_id = results.finish(
        runr,
        note="holder/issuer/direction checked against SEC SGML header FILED BY / SUBJECT COMPANY",
    )
    log.info(
        f"rows match {counters['rows_match']} mismatch {counters['rows_mismatch']} no_header {counters['rows_no_header']}; mismatches -> {p}"
    )
    log.info(f"run {run_id} recorded")
    return 0


def _fix_decision(holder_cik: str, issuer_cik: str, subj: set, filers: set) -> tuple[str, dict]:
    """Per-row ruling against a parsed header, as one pure function so the
    rule is unit-testable without a database.

    Returns (action, fields):
      "match"      — row agrees with the header; nothing to do.
      "fix"        — the row's holder is SEC's SUBJECT (the inversion class
                     the 2026-09-06 classification confirmed as genuine,
                     434 rows); fields carries the corrected keys, holder
                     from FILED BY and issuer from SUBJECT COMPANY.
      "ambiguous"  — inverted, but the header lists several subjects or
                     filers, so no single correction is stated; left for
                     inspection.
      "benign"     — disagrees without inversion (filer-of-record holder,
                     issuer-CIK-only, NAME holders): classified 2026-09-06
                     as not defects; untouched.
    """
    ok = bool(subj) and issuer_cik in subj and (not filers or holder_cik in filers)
    if ok:
        return "match", {}
    if holder_cik and holder_cik in subj:
        if len(subj) == 1 and len(filers) == 1 and subj != filers:
            # subj == filers is an issuer-agent self-filing (SEC lists one
            # CIK as both parties); "fixing" it would write holder == issuer,
            # a self-stake. Unarbitrable, like the NAME rows: left alone.
            return "fix", {
                "holder_key": f"CIK:{next(iter(filers))}",
                "issuer_key": f"CIK:{next(iter(subj))}",
            }
        return "ambiguous", {}
    return "benign", {}


def fix_direction(con=None) -> int:
    """Re-orient the header-contradicted rows from SEC's own SGML header
    (FILED BY / SUBJECT COMPANY), the authority verify-direction checked
    against. Ruling of record 2026-09-06: fix only the rows whose holder
    equals SEC's SUBJECT (the genuine inversions); leave the classified
    benign rows (filer-of-record holders, issuer-CIK-only disagreements,
    NAME holders the header cannot arbitrate) untouched. No network: only
    headers already cached in the library are read; a row whose header is
    not cached is counted and left. The table is replaced wholesale (the
    corrected columns are the declared key, which update_rows refuses by
    design); the residual mismatch export is rewritten from the corrected
    table so it becomes the new state of record."""
    from biointel import schema as _schema

    con = con or store.connect()
    reset_capture_index()
    log.info(f"{_ts()}  fix-direction: reading equity_stakes")
    rows = store.read_table("equity_stakes", con=con)
    log.info(f"{_ts()}  {len(rows)} rows; building capture index")
    idx = _build_capture_index(con)
    log.info(f"{_ts()}  index built; reading cached headers")
    by_acc: dict[str, list[dict]] = {}
    for r in rows:
        acc = str(r.get("accession") or "")
        if acc:
            by_acc.setdefault(acc, []).append(r)
    headers: dict[str, dict] = {}
    no_header_accs = 0
    for acc, group in by_acc.items():
        text = None
        r0 = group[0]
        for key in ("issuer_key", "holder_key"):
            c = str(r0[key])[4:] if str(r0[key]).startswith("CIK:") else ""
            hit = idx.get(_submission_url(c, acc)) if c else None
            if hit:
                _ref, sha, ext = hit
                try:
                    text = _read_head(library.store_path(sha, ext))
                except OSError:
                    text = None
                if text is not None:
                    break
        if text is None:
            no_header_accs += 1
            continue
        hdr = parse_header(text)
        headers[acc] = {
            "subj": {c for c, _n in hdr["subject"]},
            "filers": {c for c, _n in hdr["filed_by"]},
        }
    log.info(
        f"{_ts()}  {len(headers)} headers read from cache; {no_header_accs} accessions without one; deciding rows"
    )
    counters = {
        "rows_total": len(rows),
        "rows_no_accession": sum(1 for r in rows if not str(r.get("accession") or "")),
        "rows_no_header": 0,
        "rows_match": 0,
        "rows_fixed": 0,
        "rows_ambiguous": 0,
        "rows_benign": 0,
        "dupes_dropped": 0,
    }
    kept: list[dict] = []
    seen: set[tuple] = set()
    residual: list[str] = []
    for r in rows:
        acc = str(r.get("accession") or "")
        hdr = headers.get(acc)
        row = dict(r)
        if hdr is None:
            if acc:
                counters["rows_no_header"] += 1
        else:
            h = str(r["holder_key"])[4:] if str(r["holder_key"]).startswith("CIK:") else ""
            iss = str(r["issuer_key"])[4:] if str(r["issuer_key"]).startswith("CIK:") else ""
            action, fields = _fix_decision(h, iss, hdr["subj"], hdr["filers"])
            if action == "fix":
                row.update(fields)
                counters["rows_fixed"] += 1
            elif action == "match":
                counters["rows_match"] += 1
            else:
                counters[f"rows_{action}"] += 1
                residual.append(
                    f"{acc}  row holder {r['holder_key']} issuer {r['issuer_key']} | SEC subject "
                    f"{sorted(hdr['subj'])} filed_by {sorted(hdr['filers'])}  "
                    f"({str(r.get('owner_name') or '')[:40]})"
                )
        key = (row["holder_key"], row["issuer_key"], str(row["as_of"])[:10])
        if key in seen:
            counters["dupes_dropped"] += 1
            continue
        seen.add(key)
        kept.append(row)
    cols = list(_schema.EQUITY_STAKE_COLS) + list(
        _schema.TABLE_BY_PATH["silver/equity_stakes.csv"].optional
    )
    store.write_table("equity_stakes", kept, cols, con=con)
    p = store.write_export("stakes_direction_mismatches.txt", "\n".join(residual) + "\n")
    runr = results.start(
        "stakes-fix-direction",
        "stakes fix-direction",
        ["equity_stakes", "references", "captures"],
        {"rule_version": RULE_VERSION},
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    runr.metric("_", "rows_after", len(kept))
    runr.artefact(p)
    run_id = results.finish(
        runr,
        note=(
            "header-contradicted rows re-oriented from SEC SGML header (FILED BY / "
            "SUBJECT COMPANY, cached, no network); benign classes of 2026-09-06 untouched"
        ),
    )
    log.info(
        f"{_ts()}  rows {len(kept)} (was {len(rows)}); fixed {counters['rows_fixed']} "
        f"ambiguous {counters['rows_ambiguous']} benign {counters['rows_benign']} "
        f"no_header {counters['rows_no_header']} dupes_dropped {counters['dupes_dropped']}; "
        f"residual mismatches -> {p}"
    )
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- M1 ingest-time header check
def _header_fields(row: dict, con) -> tuple[set, set] | None:
    """Acquire the row's submission header (cached-first, the verify-direction
    path) and return ({subject CIKs}, {filed-by CIKs}), or None when no header
    can be read. Shared by the M1 write-time check and the M3 judge's
    direction correction."""
    acc = str(row.get("accession") or "")
    if not acc:
        return None
    text = None
    for key in ("issuer_key", "holder_key"):
        c = str(row[key])[4:] if str(row[key]).startswith("CIK:") else ""
        if not c:
            continue
        hit = {
            "url": _submission_url(c, acc),
            "adsh": acc,
            "doc": f"{acc}.txt",
            "cik": c,
            "ciks": [c],
            "name": "",
            "form": str(row.get("form") or ""),
            "file_date": str(row.get("filing_date") or ""),
        }
        got = _capture(hit, con, header=True)
        if got:
            try:
                text = _read_head(library.store_path(got[0], got[1]))
            except OSError:
                text = None
            if text is not None:
                break
    if text is None:
        return None
    hdr = parse_header(text)
    return {c for c, _n in hdr["subject"]}, {c for c, _n in hdr["filed_by"]}


def _header_check(row: dict, con) -> str:
    """One row's write-time ruling against SEC's SGML header, for gate M1.
    Rules via the EXISTING parse_header + _fix_decision, unchanged (scope of
    record 2026-09-07). Returns the action: "match", "fix", "ambiguous",
    "benign", or "no_header" (no accession, no CIK path, or the header could
    not be read)."""
    fields = _header_fields(row, con)
    if fields is None:
        return "no_header"
    subj, filers = fields
    h = str(row["holder_key"])[4:] if str(row["holder_key"]).startswith("CIK:") else ""
    iss = str(row["issuer_key"])[4:] if str(row["issuer_key"]).startswith("CIK:") else ""
    action, _fields = _fix_decision(h, iss, subj, filers)
    return action


def check_probe(since: str, until: str) -> int:
    """M1 probe (rule 4.20, no-write): run the ingest path over [since,
    until] and print, for every row it WOULD write, the header ruling from
    _header_check — one line per row, exact counts at the end. Writes no
    stake rows and records no run (the verify-direction --probe precedent);
    documents and headers not yet in the library are captured there as the
    normal cache path does. Existing-key rows are NOT skipped: a replayed
    month must still produce decisions, or the probe proves nothing. The
    pasted output is the evidence that gates the M1 wiring."""
    reset_capture_index()
    reset_name_index()
    con = store.connect()
    counters = {
        "filings_seen": 0,
        "fetch_failures": 0,
        "parse_failures_html": 0,
        "parse_failures_xml": 0,
        "row_rejects": 0,
        "name_fallback": 0,
        "orient_subject": 0,
        "orient_filer": 0,
        "orient_unresolved": 0,
        "efts_errors": 0,
        "capped_members": 0,
        "members_done": 0,
    }
    decisions = {"match": 0, "fix": 0, "ambiguous": 0, "benign": 0, "no_header": 0}
    seen: set[tuple] = set()
    for cik, _ticker, _name in _member_ciks():
        rows = _collect_member(cik, since, until, con, counters)
        counters["filings_seen"] += len(rows)
        for r in rows:
            k = (r["holder_key"], r["issuer_key"], str(r["as_of"])[:10])
            if k in seen:
                continue
            seen.add(k)
            action = _header_check(r, con)
            decisions[action] += 1
            print(
                f"{action.upper():<9} {r['accession']}  {r['holder_key']} -> "
                f"{r['issuer_key']}  {r.get('form', '')}  "
                f"({str(r.get('owner_name') or '')[:40]})"
            )
        counters["members_done"] += 1
        if counters["members_done"] % 25 == 0:
            log.info(
                f"{_ts()}  {counters['members_done']} members; decided {sum(decisions.values())}; "
                f"non-match {sum(decisions.values()) - decisions['match']}"
            )
    flush_note_backfill(con)
    print(
        "CHECK-PROBE "
        + " ".join(f"{k} {v}" for k, v in decisions.items())
        + f"; rows_decided {sum(decisions.values())}; filings_seen {counters['filings_seen']}; "
        f"parse_failures h/x {counters['parse_failures_html']}/{counters['parse_failures_xml']}; "
        f"row_rejects {counters['row_rejects']}; efts_errors {counters['efts_errors']}"
    )
    return 0


_SUBMISSION_MARKERS = ("<SEC-DOCUMENT>", "-----BEGIN PRIVACY-ENHANCED MESSAGE-----", "<SEC-HEADER>")


def _looks_like_submission(path) -> bool:
    try:
        head = _read_head(path)[:4000]
    except OSError:
        return False
    return any(m in head for m in _SUBMISSION_MARKERS)


def repair_headers(con=None) -> int:
    """One-time repair for header captures that attached to filing references
    (before the 2026-09-05 fix): each filing reference with more than one
    active capture has its header capture moved to a proper header reference
    (source stakes-header, URL = the submission .txt) and re-kinded
    sec_header. No network. Counts recorded; idempotent (nothing to move on
    a second pass)."""

    from biointel import schema as _schema

    con = con or store.connect()
    log.info(f"{_ts()}  repair-headers: reading tables")
    refs = {str(r["ref_id"]): r for r in store.read_table("references", con=con)}
    by_ref: dict[str, list[dict]] = {}
    for c in store.read_table("captures", con=con):
        if c["status"] == "active":
            by_ref.setdefault(str(c["ref_id"]), []).append(c)
    multi = {rid: cs for rid, cs in by_ref.items() if len(cs) > 1}
    log.info(f"{_ts()}  {len(multi)} references with more than one active capture")
    moved = 0
    unresolved = 0
    repoint: dict[str, str] = {}
    new_refs: list[dict] = []
    existing_ids = set(refs)
    for n, (rid, cs) in enumerate(multi.items(), 1):
        if n % 500 == 0:
            log.info(f"{_ts()}  {n}/{len(multi)} references examined; {moved} headers queued")
        ref = refs.get(rid)
        if not ref:
            continue
        acc = str(ref.get("sec_accession") or "")
        headers = [
            c
            for c in cs
            if str(c.get("kind") or "") == HEADER_KIND
            or _looks_like_submission(
                library.store_path(str(c["capture_id"]), "." + str(c.get("ext") or "htm"))
            )
        ]
        docs = [c for c in cs if c not in headers]
        if not headers or not docs:
            unresolved += 1
            continue
        m = _re.search(r"/edgar/data/(\d+)/", str(ref.get("url") or ""))
        url = _submission_url(m.group(1), acc) if (m and acc) else ""
        for h in headers:
            fields = {
                "ref_type": "sec_filing",
                "url": url,
                "title": f"{acc} submission header",
                "publisher": "SEC EDGAR",
                "published_at": str(ref.get("published_at") or ""),
                "source_system": HEADER_SOURCE,
                "source_key": f"{acc}:hdr",
                "note": f"moved from {rid} by repair-headers 2026-09-05",
            }
            # Built in memory and appended in ONE write below: calling the
            # library's upsert per header re-reads the whole references table
            # each time (7,235 x ~72k rows ~ 45 min of scanning, 2026-09-05).
            row = dict.fromkeys(_schema.REFERENCE_COLS, "")
            row.update({k: str(v) for k, v in fields.items() if k in row and v})
            row["ref_id"] = library._ref_id(fields)
            while row["ref_id"] in existing_ids:
                row["ref_id"] = (
                    "R" + hashlib.sha256((row["ref_id"] + acc).encode()).hexdigest()[:16]
                )
            existing_ids.add(row["ref_id"])
            row["accessed_at"] = library._now()
            row["added_by"] = library.ADDED_BY_DEFAULT
            row["status"] = "active"
            new_refs.append(row)
            repoint[str(h["capture_id"])] = row["ref_id"]
            moved += 1
    log.info(
        f"{_ts()}  examined all; writing {len(new_refs)} header references and re-pointing captures"
    )
    if new_refs:
        store.append_rows("references", new_refs, list(_schema.REFERENCE_COLS), con=con)
    if repoint:
        rows = store.read_table("captures", con=con)
        cols = store.table_columns("captures", con)
        for c in rows:
            nr = repoint.get(str(c["capture_id"]))
            if nr:
                c["ref_id"] = nr
                c["kind"] = HEADER_KIND
        store.write_table("captures", rows, cols, con=con)
    log.info(f"{_ts()}  writes done")
    runr = results.start(
        "stakes-repair-headers", "stakes repair-headers", ["references", "captures"], {}
    )
    runr.metric("_", "references_with_multiple_captures", len(multi))
    runr.metric("_", "headers_moved", moved)
    runr.metric("_", "unresolved", unresolved)
    run_id = results.finish(
        runr, note="header captures separated from filing references (identifier-ladder defect)"
    )
    log.info(f"{_ts()}  moved {moved} header captures; {unresolved} references left for inspection")
    log.info(f"run {run_id} recorded")
    reset_capture_index()
    return 0


# ---------------------------------------------------------------- second-route cross-check (percent, date)
# SEC's header verifies holder, issuer and direction. Percent and event date
# are not in the header, so they are checked by a SECOND extraction route
# that shares no anchor with the parser: the parser reads forward from the
# "Percent of Class" label; route B reads BACKWARD from the row that follows
# it ("Type of Reporting Person") and takes the nearest percentage. For the
# date, route B takes the month-name date nearest to "Date of Event" rather
# than a label-then-capture pattern. Agreement confirms the field;
# disagreement goes to a human. This does not replace the human - it
# decides which rows need one.
_TYPE_ROW = _re.compile(r"Type\s+of\s+Reporting\s+Person", _re.IGNORECASE)
_PCT_TOKEN = _re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,10})?)\s*%")
_DATE_OF_EVENT = _re.compile(r"Date\s+of\s+Event", _re.IGNORECASE)


def route_b_percent(text: str) -> str | None:
    """Nearest percentage before the FIRST 'Type of Reporting Person' row."""
    text = _RULE_RUNS.sub(" ", text)
    m = _TYPE_ROW.search(text)
    if not m:
        return None
    window = text[max(0, m.start() - 400) : m.start()]
    if _re.search(r"(less\s+than|up\s+to|not\s+more\s+than)\s+\d", window, _re.IGNORECASE):
        return "0" if _re.search(r"less\s+than\s+\d", window, _re.IGNORECASE) else None
    hits = _PCT_TOKEN.findall(window)
    return hits[-1] if hits else None


def route_b_event_date(text: str) -> str | None:
    """Month-name date nearest (either side) to 'Date of Event'."""
    m = _DATE_OF_EVENT.search(text)
    if not m:
        return None
    best, best_dist = None, None
    for d in _DATE_TEXT.finditer(text):
        dist = min(abs(d.start() - m.start()), abs(d.end() - m.start()))
        if dist > 250:
            continue
        if best_dist is None or dist < best_dist:
            best, best_dist = d.group(0), dist
    return _iso(best) if best else None


def _pct_equal(a: str | None, b: str | None) -> bool:
    try:
        return a is not None and b is not None and abs(float(a) - float(b)) < 0.005
    except ValueError:
        return False


def _active_doc_caps(con) -> dict[str, dict]:
    """capture_id -> capture row for every active DOCUMENT capture (headers
    excluded). Shared by crosscheck and the run-integrated check (M2)."""
    caps: dict[str, dict] = {}
    for c in store.read_table("captures", con=con):
        if c["status"] == "active" and str(c.get("kind") or "") != HEADER_KIND:
            caps[str(c["capture_id"])] = c
    return caps


def _crosscheck_rows(
    rows: list[dict], caps: dict[str, dict]
) -> tuple[dict, list[str], list[dict]]:
    """Route-B check of percent and event date over the given rows. M2 queue
    rule of record (2026-09-07, codifying the 2026-09-06 family ruling):
    only VALUE-vs-VALUE conflicts queue — route-B silence is a coverage gap,
    counted in route_b_no_pct / route_b_no_date and never exported. Lines
    carry the filing date so a full export can be restricted to a window.
    Also returns one structured conflict dict per disputed FIELD (a row can
    conflict on both), which the M3 standing queue consumes."""
    counters = {
        "rows": len(rows),
        "xml_skipped": 0,
        "unreadable": 0,
        "agree_both": 0,
        "pct_disagree": 0,
        "date_disagree": 0,
        "route_b_no_pct": 0,
        "route_b_no_date": 0,
    }
    out: list[str] = []
    conflicts: list[dict] = []
    for i, r in enumerate(rows, 1):
        if i % 5000 == 0:
            log.info(f"{_ts()}  {i}/{len(rows)} rows; agree {counters['agree_both']}")
        cap = caps.get(str(r["doc_id"]))
        if not cap:
            counters["unreadable"] += 1
            continue
        ext = "." + str(cap.get("ext") or "htm")
        if ext == ".xml":
            counters["xml_skipped"] += 1
            continue
        try:
            text = normalize_text(
                library.store_path(str(cap["capture_id"]), ext).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except OSError:
            counters["unreadable"] += 1
            continue
        b_pct = route_b_percent(text)
        b_date = route_b_event_date(text)
        pct_ok = _pct_equal(str(r["percent"]), b_pct)
        stored_date = str(r["as_of"])[:10]
        date_ok = b_date == stored_date
        if b_pct is None:
            counters["route_b_no_pct"] += 1
        if b_date is None:
            counters["route_b_no_date"] += 1
        pct_conflict = b_pct is not None and not pct_ok
        date_conflict = b_date is not None and not date_ok
        if not pct_conflict and not date_conflict:
            if pct_ok and date_ok:
                counters["agree_both"] += 1
            continue  # silence-only rows never queue (coverage gap, not evidence)
        if pct_conflict:
            counters["pct_disagree"] += 1
        if date_conflict:
            counters["date_disagree"] += 1
        for field, stored, other, hit_ in (
            ("percent", str(r["percent"]), b_pct, pct_conflict),
            ("as_of", stored_date, b_date, date_conflict),
        ):
            if hit_:
                conflicts.append(
                    {
                        "field": field,
                        "stored_value": stored,
                        "other_value": str(other),
                        "doc_id": str(r["doc_id"]),
                        "accession": str(r.get("accession") or ""),
                        "holder_key": str(r["holder_key"]),
                        "issuer_key": str(r["issuer_key"]),
                        "as_of": str(r["as_of"])[:10],
                        "filing_date": str(r.get("filing_date") or "")[:10],
                    }
                )
        out.append(
            f"F{str(r['doc_id'])[:12]}  filed {str(r.get('filing_date') or '')[:10]}  "
            f"stored pct {r['percent']} routeB {b_pct}  | stored as_of "
            f"{stored_date} routeB {b_date}  | {r['holder_key']} -> {r['issuer_key']} {r.get('form')}"
        )
    return counters, out, conflicts


def crosscheck(
    limit: int | None = None, con=None, since: str | None = None, until: str | None = None
) -> int:
    """Run route B over every stake row (or a window / the first N), compare
    with the stored percent and as_of, record agreement counts as run
    metrics, export VALUE-vs-VALUE disagreements for the human (M2 rule;
    route-B silences are counted, never queued). --since / --until filter by
    filing_date, so an update run's check can be replayed and compared
    against the full run restricted to the same window. Structured-era rows
    are skipped: their fields are copied from XML tags, not parsed, and need
    no second route."""
    con = con or store.connect()
    log.info(f"{_ts()}  crosscheck: reading tables")
    rows = store.read_table("equity_stakes", con=con)
    if since:
        rows = [r for r in rows if str(r.get("filing_date") or "")[:10] >= since]
    if until:
        rows = [r for r in rows if str(r.get("filing_date") or "")[:10] <= until]
    caps = _active_doc_caps(con)
    if limit:
        rows = rows[:limit]
    counters, out, _conflicts = _crosscheck_rows(rows, caps)
    name = (
        f"stakes_crosscheck_disagreements_{since or 'start'}_{until or 'end'}.txt"
        if (since or until)
        else "stakes_crosscheck_disagreements.txt"
    )
    p = store.write_export(name, "\n".join(out) + "\n")
    runr = results.start(
        "stakes-crosscheck",
        "stakes crosscheck",
        ["equity_stakes", "captures"],
        {"rule_version": RULE_VERSION, "since": since or "", "until": until or ""},
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    runr.artefact(p)
    run_id = results.finish(
        runr,
        note=(
            "second-route check of percent and event date; value-vs-value conflicts to the "
            "human, route-B silences counted as coverage gaps (M2 rule)"
        ),
    )
    log.info(
        f"{_ts()}  agree {counters['agree_both']} / checked {len(rows) - counters['xml_skipped'] - counters['unreadable']}; "
        f"pct disagree {counters['pct_disagree']} date disagree {counters['date_disagree']}; "
        f"route B silent pct {counters['route_b_no_pct']} date {counters['route_b_no_date']}; -> {p}"
    )
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- M3 standing judge queue
# Scope approved 2026-09-07; operator ruling: NO EXPIRY — nothing is ever
# discarded; an unsure row stays excluded and re-judgeable forever. Queue rows
# flip open -> judged and are never deleted; verdicts are append-only in
# candidate_reviews, stamped as_of the verdict date (no backdating what the
# system knew).


def _queue_id(source: str, doc_id: str, field: str) -> str:
    return "Q" + hashlib.sha256(f"{source}|{doc_id}|{field}".encode()).hexdigest()[:16]


def _m1_queue_entries(rows: list[dict]) -> list[dict]:
    """One direction-dispute entry per row whose M1 `disputed` value is an
    action class (fix|ambiguous|benign). M2 field names in `disputed` belong
    to the crosscheck source and are not re-queued here."""
    out = []
    for r in rows:
        d = str(r.get("disputed") or "")
        if d not in ("fix", "ambiguous", "benign"):
            continue
        out.append(
            {
                "queue_id": _queue_id("m1_header", str(r["doc_id"]), "direction"),
                "source": "m1_header",
                "field": "direction",
                "doc_id": str(r["doc_id"]),
                "accession": str(r.get("accession") or ""),
                "holder_key": str(r["holder_key"]),
                "issuer_key": str(r["issuer_key"]),
                "as_of": str(r["as_of"])[:10],
                "filing_date": str(r.get("filing_date") or "")[:10],
                "stored_value": f"{r['holder_key']}->{r['issuer_key']}",
                "other_value": d,
                "status": "open",
            }
        )
    return out


def _enqueue(entries: list[dict], con) -> int:
    """Append the entries not already queued (any status — a judged dispute
    never re-queues; no expiry). Returns the number queued. Marking rows
    disputed is _mark_disputes' job, deliberately OUTSIDE the id dedup:
    distinct rows sharing one document and field collapse to one queue
    entry, but every conflicted row must be excluded (the 27-row gap the
    2026-09-07 live build exposed)."""
    from biointel import schema as _schema

    existing = (
        {str(q["queue_id"]) for q in store.read_table("review_queue", con=con)}
        if store.has_table("review_queue", con)
        else set()
    )
    now = library._now()
    fresh = []
    for e in entries:
        if e["queue_id"] in existing:
            continue
        existing.add(e["queue_id"])
        row = dict.fromkeys(_schema.REVIEW_QUEUE_COLS, "")
        row.update(e)
        row["queued_at"] = now
        fresh.append(row)
    if fresh:
        store.append_rows("review_queue", fresh, list(_schema.REVIEW_QUEUE_COLS), con=con)
    return len(fresh)


def _mark_disputes(conflicts: list[dict], rows: list[dict], con) -> int:
    """Set `disputed` to the conflicted field on EVERY M2-conflicted row
    whose disputed is currently blank — never overwriting an M1 action, and
    idempotent (already-marked rows are skipped, so a rebuild marks 0).
    Applied per row regardless of queue-id collisions."""
    current = {
        (str(r["holder_key"]), str(r["issuer_key"]), str(r["as_of"])[:10]): str(
            r.get("disputed") or ""
        )
        for r in rows
    }
    marks = []
    for c in conflicts:
        key = (c["holder_key"], c["issuer_key"], c["as_of"])
        if current.get(key, "") == "":
            current[key] = c["field"]
            marks.append(
                {
                    "holder_key": c["holder_key"],
                    "issuer_key": c["issuer_key"],
                    "as_of": c["as_of"],
                    "disputed": c["field"],
                }
            )
    return store.update_rows("equity_stakes", marks, con=con) if marks else 0


def queue(since: str | None = None, until: str | None = None, con=None) -> int:
    """Build/refresh the standing judge queue from both dispute sources:
    M1 `disputed` rows (direction) and M2 value-vs-value crosscheck
    conflicts (percent / as_of; the check is re-run over the window from
    cached captures — exports are never read back, P16). Idempotent: a
    dispute already queued or judged never re-queues. Newly queued M2
    conflicts get the row's `disputed` set to the field, excluding it from
    enforced model reads until judged. Prints every open entry (the
    worksheet flow), then counts."""
    con = con or store.connect()
    log.info(f"{_ts()}  queue: reading equity_stakes")
    # The live table gains `disputed` at the first M-era `stakes run`; a
    # queue run may come first, so the declared column is added here too
    # (idempotent) before any dispute is marked.
    if store.has_table("equity_stakes", con):
        store.add_columns("equity_stakes", ["disputed"], con=con)
    rows = store.read_table("equity_stakes", con=con)
    if since:
        rows = [r for r in rows if str(r.get("filing_date") or "")[:10] >= since]
    if until:
        rows = [r for r in rows if str(r.get("filing_date") or "")[:10] <= until]
    entries = _m1_queue_entries(rows)
    log.info(f"{_ts()}  {len(entries)} M1 disputes; running route-B over {len(rows)} rows")
    _c, _lines, conflicts = _crosscheck_rows(rows, _active_doc_caps(con))
    for c in conflicts:
        c["queue_id"] = _queue_id("m2_crosscheck", c["doc_id"], c["field"])
        c["source"] = "m2_crosscheck"
        c["status"] = "open"
        entries.append(c)
    queued = _enqueue(entries, con)
    marked = _mark_disputes(conflicts, rows, con)
    open_rows = [
        q for q in store.read_table("review_queue", con=con) if str(q["status"]) == "open"
    ]
    for q in open_rows:
        print(
            f"{q['queue_id']}  {q['source']:<13} {q['field']:<9} "
            f"stored {q['stored_value']} | other {q['other_value']}  "
            f"{q['holder_key']} -> {q['issuer_key']}  as_of {str(q['as_of'])[:10]}"
        )
    runr = results.start(
        "stakes-queue",
        "stakes queue",
        ["equity_stakes", "captures", "review_queue"],
        {"rule_version": RULE_VERSION, "since": since or "", "until": until or ""},
    )
    runr.metric("_", "queued_new", queued)
    runr.metric("_", "disputes_marked", marked)
    runr.metric("_", "open_total", len(open_rows))
    run_id = results.finish(
        runr, note="standing judge queue refreshed (M3); no expiry per operator ruling"
    )
    print(f"QUEUE queued_new {queued} disputes_marked {marked} open_total {len(open_rows)}")
    log.info(f"run {run_id} recorded")
    return 0


def _rewrite_stake_row(key: tuple, mutate, con) -> bool:
    """Wholesale read-modify-write of one equity_stakes row identified by its
    declared key (holder_key, issuer_key, as_of[:10]) — the only lawful path
    when a correction changes key columns (update_rows refuses those by
    design; the fix_direction precedent). Returns True when a row matched."""
    rows = store.read_table("equity_stakes", con=con)
    cols = store.table_columns("equity_stakes", con)
    hit = False
    for r in rows:
        if (str(r["holder_key"]), str(r["issuer_key"]), str(r["as_of"])[:10]) == key:
            mutate(r)
            hit = True
    if hit:
        store.write_table("equity_stakes", rows, cols, con=con)
    return hit


def judge_queue(qid: str, verdict: str, note: str = "", reviewer: str = "", con=None) -> int:
    """Record a verdict on one queue entry, append-only, stamped as_of now.
    correct  -> the stored value stands: clear the row's `disputed`.
    wrong    -> correct the row (direction from the cached SGML header via
                _fix_decision; percent/as_of from the route-B value on the
                queue entry), record the correction, clear `disputed`.
    unsure   -> the row stays excluded with the reason; re-judgeable forever
                (no expiry, operator ruling 2026-09-07).
    A judged entry can be judged again; nothing is ever deleted."""
    from biointel import schema as _schema

    if verdict not in ("correct", "wrong", "unsure"):
        print("verdict must be correct|wrong|unsure")
        return 1
    con = con or store.connect()
    q = next(
        (r for r in store.read_table("review_queue", con=con) if str(r["queue_id"]) == qid),
        None,
    )
    if q is None:
        print(f"{qid}: not in review_queue")
        return 1
    key = (str(q["holder_key"]), str(q["issuer_key"]), str(q["as_of"])[:10])
    correction = ""
    if verdict == "correct":
        _rewrite_stake_row(key, lambda r: r.update({"disputed": ""}), con)
    elif verdict == "wrong":
        if str(q["field"]) == "direction":
            fields = _header_fields(
                {
                    "accession": q["accession"],
                    "holder_key": q["holder_key"],
                    "issuer_key": q["issuer_key"],
                    "form": "",
                    "filing_date": q["filing_date"],
                },
                con,
            )
            if fields is None:
                print(f"{qid}: header unavailable; correction refused, entry left open")
                return 1
            subj, filers = fields
            h = str(q["holder_key"])[4:] if str(q["holder_key"]).startswith("CIK:") else ""
            iss = str(q["issuer_key"])[4:] if str(q["issuer_key"]).startswith("CIK:") else ""
            action, fix = _fix_decision(h, iss, subj, filers)
            if action != "fix":
                print(
                    f"{qid}: header rules {action}, not a single correction; "
                    "entry left open - judge with unsure or correct instead"
                )
                return 1
            correction = f"{fix['holder_key']}->{fix['issuer_key']}"
            _rewrite_stake_row(key, lambda r: r.update({**fix, "disputed": ""}), con)
        else:
            field = str(q["field"])
            newval = str(q["other_value"])
            correction = f"{field}={newval}"
            _rewrite_stake_row(key, lambda r: r.update({field: newval, "disputed": ""}), con)
    now = library._now()
    # review_id must be unique per verdict even when two verdicts on the same
    # entry land within one clock second (caught in the M3 replica run): a
    # deterministic per-entry sequence number, never the timestamp.
    cand = f"M{qid[1:]}"
    prior = (
        sum(
            1
            for r in store.read_table("candidate_reviews", con=con)
            if str(r["candidate_id"]) == cand
        )
        if store.has_table("candidate_reviews", con)
        else 0
    )
    review = dict.fromkeys(_schema.CANDIDATE_REVIEW_COLS, "")
    review.update(
        {
            "review_id": f"{qid}-v{prior + 1}",
            "candidate_id": cand,
            "rule_version": RULE_VERSION,
            "verdict": verdict,
            "reviewer": reviewer or library.ADDED_BY_DEFAULT,
            "reviewed_at": now,
        }
    )
    if "note" in review:
        review["note"] = (note + (f" | corrected {correction}" if correction else "")).strip()
    store.append_rows("candidate_reviews", [review], list(_schema.CANDIDATE_REVIEW_COLS), con=con)
    store.update_rows("review_queue", [{"queue_id": qid, "status": "judged"}], con=con)
    runr = results.start(
        "stakes-judge-queue",
        "stakes judge-queue",
        ["review_queue", "equity_stakes", "candidate_reviews"],
        {"rule_version": RULE_VERSION, "queue_id": qid, "verdict": verdict},
    )
    runr.metric("_", "corrected", 1 if correction else 0)
    run_id = results.finish(
        runr, note=f"{verdict} on {qid}" + (f"; corrected {correction}" if correction else "")
    )
    print(f"JUDGED {qid} {verdict}" + (f" corrected {correction}" if correction else ""))
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- r9 specimens (rule 4.20)
def r9_specimens(n: int = 3, seed: int = 20260907, con=None) -> int:
    """Read-only step 1 of gate r9: dump the date-relevant text of N real
    documents drawn deterministically from the OPEN as_of queue entries (the
    route-A event-date miss family, confirmed 60/60 on 2026-09-06), to one
    attachable export. No rule is written until these are read (rule 4.20;
    specimens go into tests verbatim, never abbreviated). No network: cached
    captures only."""
    import random as _r

    con = con or store.connect()
    entries = [
        q
        for q in store.read_table("review_queue", con=con)
        if str(q["status"]) == "open"
        and str(q["field"]) == "as_of"
        and str(q["source"]) == "m2_crosscheck"
    ]
    if not entries:
        print("no open as_of queue entries; nothing to sample")
        return 1
    entries.sort(key=lambda q: str(q["queue_id"]))
    _r.seed(seed)
    picked = _r.sample(entries, min(n, len(entries)))
    caps = _active_doc_caps(con)
    out: list[str] = [
        f"R9 SPECIMENS ({len(picked)} of {len(entries)} open as_of entries, seed {seed}). "
        "Rules are written ONLY against these excerpts; each becomes a verbatim test."
    ]
    dumped = 0
    for i, q in enumerate(picked, 1):
        cap = caps.get(str(q["doc_id"]))
        header = (
            f"==== SPECIMEN {i}  {q['queue_id']}  doc F{str(q['doc_id'])[:12]}  "
            f"accession {q['accession']}  filed {str(q['filing_date'])[:10]}  "
            f"stored as_of {str(q['as_of'])[:10]}  routeB {q['other_value']} ===="
        )
        if not cap:
            out.append(header + "\n(no active document capture; skipped)")
            continue
        ext = "." + str(cap.get("ext") or "htm")
        try:
            text = normalize_text(
                library.store_path(str(cap["capture_id"]), ext).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except OSError:
            out.append(header + "\n(capture unreadable; skipped)")
            continue
        parts = [header, "--- head (first 4000 chars) ---", text[:4000]]
        for m in _re.finditer(r"Date\s+of\s+Event", text, _re.IGNORECASE):
            lo, hi = max(0, m.start() - 1200), min(len(text), m.end() + 1200)
            parts.append(f"--- window around 'Date of Event' at {m.start()} ---")
            parts.append(text[lo:hi])
        out.append("\n".join(parts)[:24000])
        dumped += 1
    p = store.write_export("r9_specimens.txt", "\n\n".join(out) + "\n")
    runr = results.start(
        "stakes-r9-specimens",
        "stakes r9-specimens",
        ["review_queue", "captures"],
        {"rule_version": RULE_VERSION, "n": n, "seed": seed},
    )
    runr.metric("_", "open_as_of_entries", len(entries))
    runr.metric("_", "specimens_dumped", dumped)
    runr.artefact(p)
    run_id = results.finish(runr, note="rule 4.20: specimens before any r9 regex; read-only")
    print(f"R9-SPECIMENS dumped {dumped} of {len(picked)} picked; open as_of {len(entries)} -> {p}")
    log.info(f"run {run_id} recorded")
    return 0


def r9_repair(con=None) -> int:
    """Gate r9 repair, no network: for every row excluded as an `as_of`
    dispute, re-read its cached document under the r9 rules and, ONLY where
    the r9 extraction and route B independently agree on the same event date
    (the two-route standard the F1 archaeology used), rewrite the row's
    as_of, append the event evidence to its span, clear `disputed`, and flip
    the matching open queue entry to judged. Row-driven, so id-collision
    sibling rows repair too. Everything else stays queued for the human:
    routes disagreeing, no extraction, unreadable captures, and repairs
    whose target key already exists (an amendment already sits at that
    event date — a key collision the database would refuse wholesale)."""
    con = con or store.connect()
    log.info(f"{_ts()}  r9-repair: reading tables")
    rows = store.read_table("equity_stakes", con=con)
    cols = store.table_columns("equity_stakes", con)
    caps = _active_doc_caps(con)
    existing_keys = {
        (str(r["holder_key"]), str(r["issuer_key"]), str(r["as_of"])[:10]) for r in rows
    }
    counters = {
        "rows_disputed_as_of": 0,
        "repaired": 0,
        "routes_disagree": 0,
        "no_extraction": 0,
        "key_collision": 0,
        "unreadable": 0,
        "entries_closed": 0,
    }
    repaired_keys: dict[tuple, str] = {}
    lines: list[str] = []
    for r in rows:
        if str(r.get("disputed") or "") != "as_of":
            continue
        counters["rows_disputed_as_of"] += 1
        cap = caps.get(str(r["doc_id"]))
        if not cap:
            counters["unreadable"] += 1
            continue
        ext = "." + str(cap.get("ext") or "htm")
        try:
            text = normalize_text(
                library.store_path(str(cap["capture_id"]), ext).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except OSError:
            counters["unreadable"] += 1
            continue
        flat = _RULE_RUNS.sub(" ", text)
        m = _EVENT_BEFORE.search(flat) or _EVENT_AFTER.search(flat)
        r9_date = _iso(m.group(1)) if m else ""
        b_date = route_b_event_date(text)
        if not r9_date:
            counters["no_extraction"] += 1
            continue
        if not b_date or r9_date != b_date:
            counters["routes_disagree"] += 1
            continue
        old_key = (str(r["holder_key"]), str(r["issuer_key"]), str(r["as_of"])[:10])
        new_key = (old_key[0], old_key[1], r9_date)
        if new_key in existing_keys:
            counters["key_collision"] += 1
            continue
        existing_keys.discard(old_key)
        existing_keys.add(new_key)
        span_add = " || r9: " + " ".join(m.group(0).split())
        r["span"] = (str(r.get("span") or "") + span_add)[:500]
        r["as_of"] = r9_date
        r["disputed"] = ""
        counters["repaired"] += 1
        repaired_keys[old_key] = r9_date
        lines.append(
            f"{old_key[0]} -> {old_key[1]}  as_of {old_key[2]} => {r9_date}  "
            f"doc F{str(r['doc_id'])[:12]}"
        )
    if counters["repaired"]:
        store.write_table("equity_stakes", rows, cols, con=con)
        flips = []
        for q in store.read_table("review_queue", con=con):
            if (
                str(q["status"]) == "open"
                and str(q["field"]) == "as_of"
                and (str(q["holder_key"]), str(q["issuer_key"]), str(q["as_of"])[:10])
                in repaired_keys
            ):
                flips.append({"queue_id": str(q["queue_id"]), "status": "judged"})
        counters["entries_closed"] = (
            store.update_rows("review_queue", flips, con=con) if flips else 0
        )
    p = store.write_export("r9_repaired.txt", "\n".join(lines) + "\n")
    runr = results.start(
        "stakes-r9-repair",
        "stakes r9-repair",
        ["equity_stakes", "captures", "review_queue"],
        {"rule_version": RULE_VERSION},
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    runr.artefact(p)
    run_id = results.finish(
        runr,
        note=(
            "machine repair on two-route agreement only (r9 extraction == route B); "
            "no candidate_reviews rows written (the fix-direction precedent); "
            "disagreements stay queued for the human"
        ),
    )
    print(
        "R9-REPAIR "
        + " ".join(f"{k} {v}" for k, v in counters.items())
        + f"; -> {p}"
    )
    log.info(f"run {run_id} recorded")
    return 0


def _partition_lineage(
    owners: dict[str, str], lineage: dict[str, str]
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Split proposed owners into (propose, historical): an owner CIK with an
    entity_lineage entry is a historical name of a registry member's lineage
    and must never be proposed as a new company (F1 step 4 ruling,
    2026-09-06)."""
    propose = {c: n for c, n in owners.items() if c not in lineage}
    historical = {c: (n, lineage[c]) for c, n in owners.items() if c in lineage}
    return propose, historical


def stubs(con=None) -> int:
    """Regenerate the proposed-stub list from the table as it stands. The
    first list (2026-09-04) was built from inverted rows and named buyers'
    TARGETS as if they were owners; it is void. This reads the corrected
    table: distinct 13D owners keyed by CIK that are not registry members,
    passed through the plausible-party SIC test (one submissions fetch per
    owner, cached by the library). Nothing is auto-added."""
    con = con or store.connect()
    reset_capture_index()
    member_ciks = {str(int(c)) for c, _t, _n in _member_ciks()}
    owners: dict[str, str] = {}
    for r in store.read_table("equity_stakes", con=con):
        if "13D" in str(r.get("form") or "") and str(r["holder_key"]).startswith("CIK:"):
            ocik = str(r["holder_key"])[4:]
            if ocik not in member_ciks:
                owners.setdefault(ocik, str(r.get("owner_name") or ""))
    lineage = (
        {
            str(x["predecessor_cik"]): str(x["successor_cik"])
            for x in store.read_table("entity_lineage", con=con)
        }
        if store.has_table("entity_lineage", con)
        else {}
    )
    owners, historical = _partition_lineage(owners, lineage)
    log.info(
        f"{_ts()}  {len(owners)} distinct non-member 13D owners "
        f"({len(historical)} historical names set aside via lineage); fetching SIC codes"
    )
    lines = _proposed_stubs(owners)
    if historical:
        lines.append(
            "HISTORICAL (predecessor of a registry member per entity_lineage; not proposed)"
        )
        for cik, (name, succ) in sorted(historical.items()):
            lines.append(f"  cik {cik} {name} -> historical name of CIK {succ}")
    p = store.write_export("stakes_proposed_stubs.txt", "\n".join(lines) + "\n")
    runr = results.start(
        "stakes-stubs",
        "stakes stubs",
        ["equity_stakes", "companies"],
        {"rule_version": RULE_VERSION},
    )
    runr.metric("_", "distinct_13d_owners", len(owners))
    runr.metric("_", "proposed", max(0, len(lines) - 1))
    runr.artefact(p)
    run_id = results.finish(
        runr, note="stub proposals from the direction-corrected table; the 2026-09-04 list is void"
    )
    log.info(f"{_ts()}  {max(0, len(lines) - 1)} proposed -> {p}")
    log.info(f"run {run_id} recorded")
    return 0


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
    if sub == "rebuild":
        return rebuild()
    if sub == "repair-headers":
        return repair_headers()
    if sub == "stubs":
        return stubs()
    if sub == "crosscheck":
        lim = next((int(a) for a in argv[1:] if a.isdigit()), None)
        since = argv[argv.index("--since") + 1] if "--since" in argv else None
        until = argv[argv.index("--until") + 1] if "--until" in argv else None
        return crosscheck(limit=lim, since=since, until=until)
    if sub == "verify-direction":
        probe_mode = "--probe" in argv
        lim = next((int(a) for a in argv[1:] if a.isdigit()), None)
        return verify_direction(limit=lim, probe=probe_mode)
    if sub == "fix-direction":
        return fix_direction()
    if sub == "r9-repair":
        return r9_repair()
    if sub == "r9-specimens":
        return r9_specimens(int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 3)
    if sub == "queue":
        since = argv[argv.index("--since") + 1] if "--since" in argv else None
        until = argv[argv.index("--until") + 1] if "--until" in argv else None
        return queue(since=since, until=until)
    if sub == "judge-queue":
        if len(argv) < 3:
            print("usage: stakes judge-queue QID correct|wrong|unsure [--note TEXT]")
            return 1
        note = argv[argv.index("--note") + 1] if "--note" in argv else ""
        return judge_queue(argv[1], argv[2], note=note)
    if sub == "check-probe":
        if len(argv) < 3:
            print("usage: stakes check-probe SINCE UNTIL")
            return 1
        return check_probe(argv[1], argv[2])
    print(
        "usage: stakes probe|run [SINCE]|rebuild|verify-direction [--probe|N]|fix-direction|"
        "check-probe SINCE UNTIL|crosscheck [N] [--since D] [--until D]|"
        "queue [--since D] [--until D]|judge-queue QID VERDICT [--note T]|r9-specimens [N]|r9-repair|"
        "sample [N]|precision"
    )
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
# r9 (2026-09-07, specimen 0000932471-24-000840): a label-first cover page
# prints "(Date of Event Which Requires Filing of this Statement) September
# 30, 2024" — the closing paren sits between label and date.
_EVENT_AFTER = _re.compile(
    rf"Date of Event Which Requires Filing of this Statement\s*\)?\s*:?\s*(({_MONTHS})\s+\d{{1,2}},?\s+\d{{4}})",
    _re.IGNORECASE,
)
_ISSUER = _re.compile(r"([A-Za-z0-9&.,'()\- ]{3,80}?)\s*\(Name of Issuer\)", _re.IGNORECASE)
_ISSUER_AFTER = _re.compile(r"Name of issuer\s*:\s*(.{3,80}?)\s+Title of Class", _re.IGNORECASE)
_CUSIP_BEFORE = _re.compile(r"([0-9A-Z][0-9A-Za-z ]{5,14}?)\s*\(CUSIP Number\)", _re.IGNORECASE)
_CUSIP_AFTER = _re.compile(r"CUSIP Number\s*:\s*([0-9][0-9A-Za-z]{5,8})\b", _re.IGNORECASE)
# r7 (2026-09-04, from live-table specimens): a comma may follow "Person"
# before "S.S. or"; "IRS"/"EIN"/"I.D."/"Employer Identification" appear
# without dots and must stop the name; the next row's marker may be printed
# as "(2) Check" or "2) Check".
_OWNER = _re.compile(
    r"Names?\s+of\s+Reporting\s+Persons?\b(?:\s*\(s\))?[.:,]?\s*(?:\d{1,2}\s*[.:)]?\s+)?"
    r"(?:S\.?S\.?\s+or\s+)?[/,]?\s*(?:I\.?R\.?S\.?\s+Identification\s+Nos?\.?\s+of\s+above\s+persons?"
    r"\s*(?:\(entities only\)|\[entities only\])?[.:]?\s*)?"
    r"(.{3,90}?)\s*(?:I\.R\.S\.|IRS\b|S\.?S\.\s+or|EIN\b|I\.D\.|Tax\s+I\.?D|"
    r"Employer\s+Identification|###|\d{2}-\d{7}|-\s*\d{2}-|\(?\d\)?\s*\.?\s*Check\b)",
    _re.IGNORECASE | _re.DOTALL,
)
_NAME_JUNK = _re.compile(
    r"^(s\.?s\.?\s*or|or|ein|none|#|\d+|i\.?r\.?s\.?)$|^[\W\d]*$", _re.IGNORECASE
)
_NAME_TRAIL = _re.compile(
    r"\s*(IRS\s+Identification\s+No\.?|EIN\s*#?|I\.D\.\s*#?|Tax\s+I\.?D\.?|#|None|"
    r"\(\s*[“\"]?Parent[”\"]?\s*\)|I\.R\.S\.\s+Employer\s+Identification\s+Number)\s*$",
    _re.IGNORECASE,
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
    # r9 (2026-09-07): four of five queue specimens (0001306550-23-009534,
    # 0000950133-01-000483, 0000919574-03-000317, 0000834237-20-006711) print
    # a dashed rule line BETWEEN the date and "(Date of Event ...)" — the r5
    # rule-run flattening was never applied to the event-date search, so
    # route A fell back to the filing date on ~5,400 rows. Search the
    # flattened text.
    flat = _RULE_RUNS.sub(" ", text)
    m = _EVENT_BEFORE.search(flat) or _EVENT_AFTER.search(flat)
    if m:
        out["event_date"] = _iso(m.group(1))
        out["event_span"] = " ".join(m.group(0).split())[:200]
    m = _CUSIP_BEFORE.search(text) or _CUSIP_AFTER.search(text)
    if m:
        out["cusip"] = m.group(1).replace(" ", "")
    m = _OWNER.search(_RULE_RUNS.sub(" ", text))  # r7: rule lines between rows
    if m:
        name = " ".join(m.group(1).split()).strip(" ,:;-")
        if name.endswith(".") and not _re.search(
            r"[A-Z]\.[A-Z]?\.$|Inc\.$|Ltd\.$|Co\.$|Corp\.$", name
        ):
            name = name[:-1]
        name = name.strip(" ,:;-")
        name = name.rstrip("( ").strip()  # 62d58af: trailing "(" before I.R.S. number
        for _ in range(3):  # r7: strip stacked trailing label residue
            name = _NAME_TRAIL.sub("", name).strip(" ,:;-")
        if _NAME_JUNK.match(name) or len(name) < 3:
            name = ""  # a label fragment is not a name: leave it empty, never junk
        if name:
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
RULE_VERSION = (
    "F1-r9"  # r9: event dates read through rule runs and label-first parens (2026-09-07)
)


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


_NAME_INDEX: dict[str, str] | None = None  # normalized company name -> cik


def _name_index(con=None) -> dict[str, str]:
    global _NAME_INDEX
    if _NAME_INDEX is None:
        from biointel import network

        idx: dict[str, str] = {}
        for co in store.read_table("companies", con=con):
            cik = str(co.get("CIK") or "").strip()
            if cik:
                idx[network._norm(str(co.get("Name") or ""))] = str(int(cik))
        _NAME_INDEX = idx
    return _NAME_INDEX


def reset_name_index() -> None:
    global _NAME_INDEX
    _NAME_INDEX = None


def _member_name(cik: str) -> str:
    """Normalized registry name for a member CIK, or ''."""
    for name, c in _name_index().items():
        if c == cik:
            return name
    return ""


def _registry_name_of(cik: str) -> str:
    return _member_name(cik)


def orient(hit: dict, parsed: dict, member_cik: str) -> tuple[str, str, str]:
    """Decide who is the SUBJECT (issuer) and who is the OWNER (holder) of a
    filing from the DOCUMENT and the two parties SEC associates with it —
    never from which company we happened to search by.

    Defect history (2026-09-04). First version: the searched member was
    assumed to be the subject, inverting every filing where the member was
    the filer (11,302 of 41,121 rows). Second version: fixed that but still
    trusted the reference note's "member", which recorded SEC's first-listed
    CIK rather than the searched one; when that was a non-member fund the
    name test had nothing to compare against and fell through to the old
    assumption. This version needs no "member": the parties are the CIKs
    SEC lists; the document names the issuer; whichever party carries that
    name is the subject and the other is the owner.

    Returns (holder_key, issuer_key, orientation) where orientation is
    "subject" (the document's issuer identified among the parties or by the
    XML), "filer" (the document's issuer is not the party we started from),
    or "unresolved" (the document names no issuer we can place; the
    historical fallback applies and is counted)."""
    from biointel import network

    parties = [c for c in hit.get("ciks", []) if c]
    doc_issuer = parsed.get("issuer_cik") or ""
    doc_owner = parsed.get("owner_cik") or ""
    issuer_name = network._norm(parsed.get("issuer_name") or "")

    def _label(owner: str) -> str:
        # "filer": a registry member is the OWNER (member holds a stake in
        # someone); "subject": the member is the one being held.
        return "filer" if _registry_name_of(owner) else "subject"

    # Structured era: the XML states both sides outright.
    if doc_issuer:
        owner = doc_owner or next((c for c in parties if c != doc_issuer), "")
        if owner:
            return f"CIK:{owner}", f"CIK:{doc_issuer}", _label(owner)
        return "", "", "unresolved"

    def _same(a: str, b: str) -> bool:
        # registry name vs parsed document text: the parsed string may carry
        # spillover ("Verastem, Inc. Common Stock"), so containment counts
        return bool(a) and bool(b) and (a == b or a in b or b in a)

    # HTML era: place the document's issuer name among the parties.
    if issuer_name:
        by_name = _name_index().get(issuer_name, "")
        for c in parties:
            if c == by_name or _same(_registry_name_of(c), issuer_name):
                owner = doc_owner or next((o for o in parties if o != c), "")
                if owner:
                    return f"CIK:{owner}", f"CIK:{c}", _label(owner)
        # r8 (2026-09-06): a name-index hit that is NOT among SEC's parties is
        # not evidence either. _norm strips legal suffixes, so a predecessor's
        # name ("Allergan, Inc.") resolves to its successor's registry CIK
        # ("Allergan plc"), and trusting that hit wrote the successor as
        # issuer and the true subject as holder — 261 of the 434 inverted
        # rows the SEC-header check caught. The parties SEC lists are the
        # only CIKs a filing can be about; an off-party name match falls
        # through, like an unmatched one (the 2026-09-04 BlackRock lesson).

    # The reporting person's name is a second, independent document field.
    # With exactly one registry party M: if the reporting person IS M, M is
    # the owner (filer); otherwise M is being held (subject).
    members = [c for c in parties if _registry_name_of(c)]
    owner_name = network._norm(parsed.get("owner_name") or "")
    if len(members) == 1 and len(parties) == 2 and owner_name:
        m = members[0]
        other = next(o for o in parties if o != m)
        if _same(_registry_name_of(m), owner_name):
            return f"CIK:{m}", f"CIK:{other}", "filer"
        return f"CIK:{doc_owner or other}", f"CIK:{m}", "subject"

    # No usable issuer in the document: historical fallback, counted.
    member = str(int(member_cik)) if str(member_cik).strip() else ""
    if member and member not in parties:
        # r8: the searched member is not among the filing's parties (a
        # successor CIK reached via name collision, or stale search
        # metadata). Assuming it as issuer fabricates a party SEC never
        # listed; the row is refused instead.
        return "", "", "unresolved"
    others = [c for c in parties if c != member]
    if doc_owner and member and doc_owner != member:
        return f"CIK:{doc_owner}", f"CIK:{member}", "unresolved"
    if member and len(others) == 1:
        return f"CIK:{others[0]}", f"CIK:{member}", "unresolved"
    if parsed.get("owner_name") and member:
        return f"NAME:{network._norm(parsed['owner_name'])}", f"CIK:{member}", "unresolved"
    return "", "", "unresolved"


def _row_from(hit: dict, parsed: dict, subject_cik: str) -> dict | None:
    pct = parsed.get("percent", "")
    try:
        float(pct)
    except (TypeError, ValueError):
        return None
    holder, issuer, orientation = orient(hit, parsed, subject_cik)
    if not holder:
        return None
    as_of = parsed.get("event_date") or hit["file_date"]
    if not as_of:
        return None
    span = parsed.get("percent_span") or parsed.get("shares_span") or parsed.get("event_span") or ""
    return {
        "holder_key": holder,
        "issuer_key": issuer,
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
        "_orientation": orientation,
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
            global _CAPTURE_INDEX
            if _CAPTURE_INDEX is None:
                _CAPTURE_INDEX = _build_capture_index(con)
            uncached = [h["url"] for h in hits if h["url"] not in _CAPTURE_INDEX]
            prefetched = _prefetch(uncached)
            for h in hits:
                got = _capture(h, con, prefetched=prefetched)
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
                counters[f"orient_{row.pop('_orientation')}"] += 1
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

    reset_capture_index()
    reset_name_index()
    con = store.connect()
    until = _date.today().isoformat()
    cols = list(_schema.EQUITY_STAKE_COLS) + list(
        _schema.TABLE_BY_PATH["silver/equity_stakes.csv"].optional
    )
    existing = set()
    if store.has_table("equity_stakes", con):
        # widen the stored header with any declared optional columns it lacks
        store.add_columns("equity_stakes", cols, con=con)
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
        "orient_subject": 0,
        "orient_filer": 0,
        "orient_unresolved": 0,
        "efts_errors": 0,
        "capped_members": 0,
        "members_done": 0,
        "check_match": 0,
        "check_fix": 0,
        "check_ambiguous": 0,
        "check_benign": 0,
        "check_no_header": 0,
    }
    member_ciks = {str(int(c)) for c, _t, _n in _member_ciks()}
    run_stamp = time.strftime("%Y%m%dT%H%M%S")
    written_rows: list[dict] = []
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
            # M1 (scope of record 2026-09-07): every new row is checked against
            # SEC's SGML header at write time via the existing parse_header +
            # _fix_decision, unchanged. Agreeing rows write as today; disagreeing
            # rows write with `disputed` set to the action, which excludes them
            # from every enforced model read until judged (M3). A row whose
            # header cannot be acquired writes clean and is counted — the scope
            # marks disagreement, not absence (probe: no_header 0 of 849).
            action = _header_check(r, con)
            counters[f"check_{action}"] += 1
            r["disputed"] = "" if action in ("match", "no_header") else action
            fresh.append(r)
        if fresh:
            store.append_rows("equity_stakes", fresh, cols, con=con)
            counters["rows_written"] += len(fresh)
            written_rows.extend(fresh)
        counters["members_done"] += 1
        if counters["members_done"] % 25 == 0:
            log.info(
                f"{_ts()}  {counters['members_done']} members; rows {counters['rows_written']}; "
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
    counters["notes_backfilled"] = flush_note_backfill(con)
    # M2 (scope of record 2026-09-07): every update run ends by crosschecking
    # EXACTLY the rows it wrote this pass — defects are caught at row one,
    # value-vs-value conflicts go to the export, silences are counted.
    xc_counters: dict = {}
    xc_path = None
    queued_new = 0
    if written_rows:
        log.info(f"{_ts()}  M2 crosscheck over {len(written_rows)} fresh rows")
        xc_counters, xc_lines, xc_conflicts = _crosscheck_rows(
            written_rows, _active_doc_caps(con)
        )
        xc_path = store.write_export(
            f"stakes_run_crosscheck_{run_stamp}.txt", "\n".join(xc_lines) + "\n"
        )
        # M3: this pass's disputes join the standing queue immediately —
        # M1-disputed fresh rows (direction) and M2 conflicts (field values).
        entries = _m1_queue_entries(written_rows)
        for c in xc_conflicts:
            c["queue_id"] = _queue_id("m2_crosscheck", c["doc_id"], c["field"])
            c["source"] = "m2_crosscheck"
            c["status"] = "open"
            entries.append(c)
        queued_new = _enqueue(entries, con)
        _mark_disputes(xc_conflicts, written_rows, con)
    stub_lines = _proposed_stubs(thirteen_d_owners)
    p = store.write_export("stakes_proposed_stubs.txt", "\n".join(stub_lines) + "\n")
    runr = results.start(
        "stakes-run", "stakes run", ["companies"], {"since": since, "rule_version": RULE_VERSION}
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    for k, v in xc_counters.items():
        runr.metric("_", f"xc_{k}", v)
    runr.metric("_", "queued_new", queued_new)
    if xc_path is not None:
        runr.artefact(xc_path)
    runr.metric("_", "proposed_stubs", max(0, len(stub_lines) - 1))
    runr.artefact(p)
    run_id = results.finish(
        runr,
        note=(
            f"rule {RULE_VERSION}; one row per filing (lead filer); as_of = cover-page event "
            "date, else filing date; exits written at stated percent (Q4); stubs proposed, "
            "never auto-added (Q3); M1 header check at write time (disputed rows excluded "
            "from enforced model reads until judged); M2 crosscheck over this run's fresh "
            "rows (value-vs-value conflicts exported, silences counted)"
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

    con = store.connect()
    rows = [r for r in store.read_table("equity_stakes", con=con) if r.get("doc_id")]
    if not rows:
        print("no parsed rows to sample")
        return 1
    _r.seed(seed)
    picked = _r.sample(rows, min(n, len(rows)))
    urls = _doc_urls({str(r["doc_id"]) for r in picked}, con)
    missing = sum(1 for r in picked if not urls.get(str(r["doc_id"])))
    print(
        f"STAKES BLIND SAMPLE ({len(picked)} rows, rule {RULE_VERSION}, seed {seed}). "
        "For each: open the filing URL and check FIVE things - the holder CIK is the "
        "filer, the issuer CIK is the subject (direction), the owner name, the percent, "
        "the event date; then `judge F<id> correct|wrong|unsure`. A row passes only if "
        "ALL FIVE match."
    )
    print(
        "Rows must have been parsed at this rule version: re-run `stakes run` after any "
        "rule change, or the verdicts are filed against rules that did not produce them."
    )
    if missing:
        print(f"WARNING: {missing} of {len(picked)} rows have no resolvable document URL.")
    for r in picked:
        print(
            f"F{str(r['doc_id'])[:12]}  holder {r['holder_key']} ({r.get('owner_name') or '?'}) "
            f"-> issuer {r['issuer_key']}  {r['percent']}%  as_of {str(r['as_of'])[:10]}  "
            f"{r.get('form', '')}  {urls.get(str(r['doc_id']), '(no url)')}"
        )
    return 0


def _doc_urls(doc_ids: set[str], con) -> dict[str, str]:
    """capture_id -> the exact document URL it was fetched from. The captured
    URL is the document itself; an accession directory listing is a fallback
    only, because EDGAR indexes a filing under the filer's CIK, which for a
    13D/13G is the OWNER, not the subject we key rows on."""
    if not store.has_table("captures", con) or not store.has_table("references", con):
        return {}
    ref_of = {
        str(c["capture_id"]): str(c["ref_id"])
        for c in store.read_table("captures", con=con)
        if str(c["capture_id"]) in doc_ids
    }
    if not ref_of:
        return {}
    wanted = set(ref_of.values())
    url_of = {
        str(r["ref_id"]): str(r.get("url") or "")
        for r in store.read_table("references", con=con)
        if str(r["ref_id"]) in wanted
    }
    return {d: url_of.get(ref, "") for d, ref in ref_of.items() if url_of.get(ref)}


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
    # M3: M-prefixed verdicts (queue judgements) are measured separately —
    # their wrong rows are CORRECTED in place at judge time, never retired.
    # A later verdict on the same queue entry supersedes (append-only log,
    # last write counts for the measurement).
    m_verdicts: dict[str, str] = {}
    if store.has_table("candidate_reviews", con):
        for r in sorted(
            store.read_table("candidate_reviews", con=con),
            key=lambda x: str(x.get("reviewed_at") or ""),
        ):
            if r.get("rule_version") == RULE_VERSION and str(r["candidate_id"]).startswith(
                "M"
            ):
                m_verdicts[str(r["candidate_id"])] = str(r["verdict"])
    m_judged = {k: v for k, v in m_verdicts.items() if v in ("correct", "wrong")}
    if not judged and not m_judged:
        print("no F- or M-prefixed verdicts at rule " + RULE_VERSION)
        return 1
    if not judged:
        mk = sum(1 for v in m_judged.values() if v == "correct")
        print(
            f"M-era precision {mk}/{len(m_judged)}; no F-prefixed verdicts at rule "
            + RULE_VERSION
        )
        return 0
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
    mk = sum(1 for v in m_judged.values() if v == "correct")
    runr.metric("_", "m_correct", mk)
    runr.metric("_", "m_judged", len(m_judged))
    runr.metric("_", "m_unsure", sum(1 for v in m_verdicts.values() if v == "unsure"))
    run_id = results.finish(
        runr, note=f"four-field pass rule (Q5); {retired} judged-wrong rows retired"
    )
    print(f"precision {k}/{nn} = {k / nn:.3f} [{lo:.3f}, {hi:.3f}]; retired {retired}")
    log.info(f"run {run_id} recorded")
    return 0
