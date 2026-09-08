# C:\Users\JB\Documents\dev\bioindustry\src\biointel\priorities.py
"""Gate F2, stage 1 only: the probe (rule 4.20 — real captures before any
rule). Scope of record: docs/20260903_v1_GATEF2_SCOPE.md.

`priorities probe` captures a small spread of each stated-priority source
type into the research library, writes ONE inspection bundle
(data/exports/priorities_probe_bundle.txt: manifest plus the normalized
text of each capture, truncated at BUNDLE_CHARS), records a ledger run, and
STOPS. The extraction rules — which sentences count as a stated priority,
how the 10-K Item 1 section is sliced away from Item 1A risk factors, how
each row is tagged by source type and section — are written only against
that bundle, never against assumed document shapes.

WHY THREE SOURCE TYPES (Q1, closed): earnings-call transcripts filed as 8-K
exhibits carry the most specific language; 10-K Item 1 sections are the only
source every company files, so excluding them leaves transcript-less buyers
with no priorities at all; investor-day decks are rare but strategic. All
three are collected, tagged, and measured per tier; the matcher's input list
is set by those measurements (L3 found accuracy at 0.625 on deal 8-Ks and
0.456 once 10-K boilerplate entered — a filtering problem, solved by
section-level guards, not a reason to skip a source).

WHAT THE PROBE TESTS THAT CANNOT BE ASSUMED: whether the EFTS query phrases
below actually surface each source type (a type returning zero hits is
printed as a coverage hole, the way the structured-format era was for F1);
how transcripts are laid out as exhibits; where Item 1 begins and ends in
real 10-Ks across eras; what an investor-day exhibit looks like when filed.
The probe query phrases are UNSOURCED guesses by construction — that is what
a probe is for — and are replaced or confirmed by what comes back.
"""

from __future__ import annotations

import json
import logging
import re
import time

import requests

from biointel import config, library, results, store
from biointel.efts import _headers, hits_of, normalize_text, search

log = logging.getLogger(__name__)

# (source_type, forms, query) — the query is a probe hypothesis, not a rule.
SOURCE_TYPES = (
    ("earnings_call", "8-K", '"earnings call" transcript'),
    ("10k_strategy", "10-K", '"business development" acquisitions'),
    ("investor_day", "8-K", '"investor day"'),
)
PROBE_WINDOWS = (("2015-01-01", "2019-12-31"), ("2022-01-01", "2026-09-03"))
PER_TYPE_CAPTURES = 3
COMPANIES_TRIED_PER_TYPE = 12
BUNDLE_CHARS = 60_000  # 10-Ks are long; Item 1 usually sits inside the first 60k
BUNDLE_NAME = "priorities_probe_bundle.txt"
TOOL = "priorities-probe"


def _member_ciks() -> list[tuple[str, str, str]]:
    from biointel.stakes import _member_ciks as _m

    return _m()


def _fetch(url: str) -> tuple[bytes, str, str] | None:
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


def _capture(hit: dict, source_type: str, con) -> tuple[str, str, str] | None:
    """Capture with honest provenance; reuse an existing active capture of
    the same URL. The note carries the source type so a later re-parse from
    the library knows which tier a document belongs to without re-searching."""
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
            "source_system": TOOL,
            "source_key": f"{hit['adsh']}:{hit['doc']}",
            "note": (
                f"captured by {TOOL};source_type={source_type};form={hit['form']}"
                f";cik={hit['cik']};file_date={hit['file_date']}"
            ),
        },
        con,
    )
    sha, dst, _new = library.put_bytes(data, ext)
    library.add_capture(ref_id, sha, dst, "fetched_html", TOOL, con)
    if hit["cik"]:
        library.add_link(ref_id, "CIK", hit["cik"], "subject", con)
    return sha, ext, ctype


def probe() -> int:
    con = store.connect()
    manifest: list[str] = []
    bundle: list[str] = []
    captured = 0
    members = _member_ciks()[:COMPANIES_TRIED_PER_TYPE]
    for source_type, forms, query in SOURCE_TYPES:
        picked: list[dict] = []
        for start, end in PROBE_WINDOWS:
            for cik, ticker, _name in members:
                if len(picked) >= PER_TYPE_CAPTURES:
                    break
                payload = search(query, forms, start, end, cik=cik)
                if payload.get("error"):
                    manifest.append(
                        f"  {source_type} cik {cik} ({ticker}): EFTS error {payload['error']}"
                    )
                    continue
                for h in hits_of(payload):
                    if h["url"] and h not in picked:
                        picked.append(h)
                        break
            if len(picked) >= PER_TYPE_CAPTURES:
                break
        if not picked:
            manifest.append(
                f"  {source_type}: 0 hits across {len(members)} companies and "
                f"{len(PROBE_WINDOWS)} windows with query {query!r} — coverage hole or wrong "
                "query; a finding either way"
            )
            continue
        for h in picked[:PER_TYPE_CAPTURES]:
            got = _capture(h, source_type, con)
            if not got:
                manifest.append(
                    f"  FETCH-FAILED {source_type} {h['form']} {h['file_date']} {h['url']}"
                )
                continue
            sha, ext, ctype = got
            captured += 1
            manifest.append(
                f"  {source_type:<14} {h['form']:<5} filed {h['file_date']}  cik {h['cik']} "
                f"({h['name'][:36]})  ext {ext} ctype {ctype}  sha {sha[:12]}"
            )
            p = library.store_path(sha, ext)
            try:
                text = normalize_text(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                text = "(unreadable as text)"
            bundle.append(
                "=" * 78 + f"\nCAPTURE {sha}  {source_type}  {h['form']}  filed {h['file_date']}"
                f"  url {h['url']}\n" + "=" * 78 + "\n" + text[:BUNDLE_CHARS]
            )
    head = [
        f"PRIORITIES PROBE — {captured} documents captured across {len(SOURCE_TYPES)} source types"
    ]
    head.extend(manifest)
    p = store.write_export(BUNDLE_NAME, "\n".join(head) + "\n\n" + "\n\n".join(bundle) + "\n")
    run = results.start(
        "priorities-probe",
        "priorities probe",
        ["companies"],
        {"types": len(SOURCE_TYPES), "per_type": PER_TYPE_CAPTURES},
    )
    run.metric("_", "captured", captured)
    run.metric("_", "manifest_lines", len(manifest))
    run.artefact(p)
    run_id = results.finish(
        run, note="rule 4.20 probe; F2 rules written only against these captures"
    )
    for line in head:
        log.info(line)
    log.info(f"bundle -> {p}")
    log.info(f"run {run_id} recorded")
    return 0 if captured else 1




# ---------------------------------------------------------------- F2 stage 2: rules (10k_strategy + investor_day tiers)
# Written ONLY against the 2026-09-07 probe bundle (4 captures; rule 4.20).
# The earnings_call tier returned 0 hits on the probe's query hypothesis and
# has NO rules yet: probe_calls() below re-probes that tier with replacement
# hypotheses, and its rules are written only against what comes back.
# Rule version for the priorities families; the analyser-side a3 agenda
# (doc-type guards, fee tiers) lands with the deal-aspects half of F2.
RULE_VERSION_F2 = "L3-a3-p1"

# 10-K slicing, from the three probe 10-Ks: the TOC and inline
# cross-references both mention "Item 1A" long before the section body
# (Akorn's own M&A paragraph cites it), so the LAST "ITEM 1A ... RISK
# FACTORS" match is the exclusion boundary, and the extraction start is the
# end of the LAST table-of-contents signature (an Item-1 mention followed
# within 90 chars by another Item line).
_ITEM1A_RF = re.compile(r"Item\s*1A\b[^A-Za-z]{0,12}Risk\s+Factors", re.IGNORECASE)


def item1_slice(text: str) -> str:
    """The Item 1 (Business) region of a 10-K, or "" when the document
    cannot be sliced — extraction refuses rather than guesses (F1 rule)."""
    ends = [m.start() for m in _ITEM1A_RF.finditer(text)]
    if not ends:
        return ""
    end = ends[-1]
    start = 0
    for m in re.finditer(r"Item\s*1\b", text[:end], re.IGNORECASE):
        if re.search(r"Item\s*\d", text[m.end() : m.end() + 90], re.IGNORECASE):
            start = m.end()
    return text[start:end]


# One rule per specimen family; the guard regex must ALSO match inside the
# sentence for the category to be assigned (never a bare anchor).
PRIORITY_RULES = (
    # Akorn 10-K 2015 (03fdcee3d8f8): "We seek to acquire businesses assets
    # and products that we believe complement our existing business ..."
    ("pipeline_gap", re.compile(r"\bWe\s+(?:actively\s+)?seek\s+to\s+acquire\b[^.]{10,300}\.", re.IGNORECASE), None),
    # BMY 10-K 2019 (62ab199b8ecc): "Our four strategic priorities are to
    # ... in-licensing or acquiring investigational compounds ..."
    ("pipeline_gap", re.compile(r"\bstrategic priorities are to\b[^.]{0,500}\.", re.IGNORECASE), re.compile(r"acquir|in-licens", re.IGNORECASE)),
    # Tenax 10-K 2018 (e49b72a0ef3e): "Our principal business objective is
    # to identify, develop, and commercialize novel therapeutic products
    # for disease indications ..."
    ("therapeutic_area", re.compile(r"\bprincipal (?:business )?objective is to\b[^.]{10,300}\.", re.IGNORECASE), re.compile(r"therapeutic|disease|clinical", re.IGNORECASE)),
    # BMY 10-K 2019: "... continue to further build a leading franchise in IO ..."
    ("therapeutic_area", re.compile(r"[^.]{0,420}\bleading franchise in\b[^.]{0,420}\.", re.IGNORECASE), None),  # r6 lesson: the window must fit the real specimen (BMY sentence ~430 chars)
    # TXMD investor-day 8-K (662c4aab01a8): "... committed to advancing
    # women's health with new treatments ..."
    ("therapeutic_area", re.compile(r"[^.]{0,120}\bcommitted to advancing\s+[^.]{0,60}?health\b[^.]{0,200}\.", re.IGNORECASE), None),
)


def extract_priorities(text: str, source_type: str) -> list[dict]:
    """Stated-priority sentences for the two tiers with probe specimens.
    10-Ks are sliced to Item 1 first (section "Item 1"); an unsliceable
    10-K yields nothing, counted by the caller. Exhibits scan whole
    (section "exhibit"). One row per distinct sentence."""
    if source_type == "10k_strategy":
        body, section = item1_slice(text), "Item 1"
        if not body:
            return []
    else:
        body, section = text, "exhibit"
    out: list[dict] = []
    seen: set[str] = set()
    for category, rule, guard in PRIORITY_RULES:
        for m in rule.finditer(body):
            sent = " ".join(m.group(0).split())[:500]
            if guard and not guard.search(sent):
                continue
            if sent in seen:
                continue
            seen.add(sent)
            out.append(
                {"category": category, "sentence": sent, "section": section,
                 "source_type": source_type}
            )
    return out


# ---------------------------------------------------------------- earnings-tier probe v2
# The stage-1 hypothesis ('"earnings call" transcript') returned 0 hits
# across 12 companies and both windows (bundle of record, 2026-09-07).
# Replacement hypotheses — UNSOURCED by construction, that is what a probe
# is for: transcripts carry an operator-led Q&A, so the phrases below are
# transcript-specific in a way the failed query was not.
CALL_QUERIES = ('"question-and-answer session"', '"prepared remarks"')
CALLS_BUNDLE = "priorities_probe_calls_bundle.txt"


def probe_calls() -> int:
    """Stage-1 re-probe of the earnings_call tier only; captures up to
    PER_TYPE_CAPTURES per replacement query, one bundle, records the run,
    STOPS. Earnings-tier rules are written only against this bundle."""
    con = store.connect()
    manifest: list[str] = []
    bundle: list[str] = []
    captured = 0
    members = _member_ciks()[:COMPANIES_TRIED_PER_TYPE]
    for query in CALL_QUERIES:
        picked: list[dict] = []
        for start, end in PROBE_WINDOWS:
            for cik, ticker, _name in members:
                if len(picked) >= PER_TYPE_CAPTURES:
                    break
                payload = search(query, "8-K", start, end, cik=cik)
                if payload.get("error"):
                    manifest.append(f"  {query!r} cik {cik} ({ticker}): EFTS error {payload['error']}")
                    continue
                for h in hits_of(payload):
                    if h["url"] and h not in picked:
                        picked.append(h)
                        break
            if len(picked) >= PER_TYPE_CAPTURES:
                break
        if not picked:
            manifest.append(
                f"  earnings_call query {query!r}: 0 hits across {len(members)} companies "
                f"and {len(PROBE_WINDOWS)} windows — hypothesis dead, a finding"
            )
            continue
        for h in picked[:PER_TYPE_CAPTURES]:
            got = _capture(h, "earnings_call", con)
            if not got:
                manifest.append(f"  FETCH-FAILED earnings_call {h['form']} {h['file_date']} {h['url']}")
                continue
            sha, ext, ctype = got
            captured += 1
            manifest.append(
                f"  earnings_call {h['form']:<5} filed {h['file_date']}  cik {h['cik']} "
                f"({h['name'][:36]})  query {query!r}  ext {ext} ctype {ctype}  sha {sha[:12]}"
            )
            p = library.store_path(sha, ext)
            try:
                text = normalize_text(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                text = "(unreadable as text)"
            bundle.append(
                "=" * 78 + f"\nCAPTURE {sha}  earnings_call  {h['form']}  filed {h['file_date']}"
                f"  query {query!r}  url {h['url']}\n" + "=" * 78 + "\n" + text[:BUNDLE_CHARS]
            )
    head = [f"PRIORITIES CALLS PROBE — {captured} captured across {len(CALL_QUERIES)} replacement queries"]
    head.extend(manifest)
    p = store.write_export(CALLS_BUNDLE, "\n".join(head) + "\n\n" + "\n\n".join(bundle) + "\n")
    run = results.start(
        "priorities-probe-calls", "priorities probe-calls", ["companies"],
        {"queries": len(CALL_QUERIES), "per_query": PER_TYPE_CAPTURES},
    )
    run.metric("_", "captured", captured)
    run.metric("_", "manifest_lines", len(manifest))
    run.artefact(p)
    run_id = results.finish(run, note="earnings-tier re-probe; hypotheses replaced on the 0-hit finding")
    for line in head:
        log.info(line)
    log.info(f"bundle -> {p}")
    log.info(f"run {run_id} recorded")
    return 0 if captured else 1




# ---------------------------------------------------------------- F2 stage 3: the collector (two live tiers)
# Operator rulings (2026-09-07): enumeration via the complete per-company
# SEC submissions JSON, never a phrase filter (D1); the FULL 10-K history
# per company, incrementally forever (D2) — every run computes the desired
# set, diffs against the library, downloads only what is missing. A new
# member gets its whole back-history; nothing is ever fetched twice.
# The investor_day tier keeps the evidenced EFTS phrase query: 8-Ks cannot
# be enumerated by form alone, the phrase IS that tier's discriminator, and
# Q1's per-tier measurement carries its bias honestly.
COLLECT_SINCE = "2015-01-01"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


def _capture_index(con) -> tuple[dict, dict]:
    """ONE pass over references and captures (the F1 2026-09-04 lesson —
    the probe's per-hit table scan is retired): url -> reference row, and
    ref_id -> active capture row."""
    by_url: dict[str, dict] = {}
    by_ref: dict[str, dict] = {}
    if store.has_table("references", con):
        for r in store.read_table("references", con=con):
            if r.get("url"):
                by_url[str(r["url"])] = r
    if store.has_table("captures", con):
        for c in store.read_table("captures", con=con):
            if str(c.get("status")) == "active":
                by_ref[str(c["ref_id"])] = c
    return by_url, by_ref


def _capture_doc(
    url: str,
    meta: dict,
    source_type: str,
    by_url: dict,
    by_ref: dict,
    con,
    prefetched: dict | None = None,
) -> tuple[str, str, str] | None:
    """Capture one document with the collector's OWN reference identity:
    the upsert carries url + a tool-scoped source_key and deliberately OMITS
    sec_accession, so the identifier ladder's accession rung can never
    attach this capture to another tool's reference (mine-pdufa shares
    accessions with 8-Ks; the sec 9 defect class, closed here the way
    headers closed it). The accession stays in note and source_key for
    provenance. Returns (sha, ext, how) or None."""
    ref = by_url.get(url)
    if ref is not None:
        cap = by_ref.get(str(ref["ref_id"]))
        if cap is not None:
            return str(cap["capture_id"]), "." + str(cap.get("ext") or "htm"), "cached"
    got = (prefetched or {}).get(url) or _fetch(url)
    if not got:
        return None
    data, ext, _ctype = got
    ref_id, _ = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "url": url,
            "title": f"{meta.get('name', '')} {meta['form']} {meta['file_date']}".strip(),
            "publisher": "SEC EDGAR",
            "published_at": meta["file_date"],
            "source_system": TOOL,
            "source_key": f"{TOOL}:{meta['adsh']}:{meta.get('doc', '')}",
            "note": (
                f"captured by {TOOL};source_type={source_type};form={meta['form']}"
                f";accession={meta['adsh']};cik={meta.get('cik', '')}"
                f";file_date={meta['file_date']}"
            ),
        },
        con,
    )
    sha, dst, _new = library.put_bytes(data, ext)
    library.add_capture(ref_id, sha, dst, "fetched_html", TOOL, con)
    if meta.get("cik"):
        library.add_link(ref_id, "CIK", str(meta["cik"]), "subject", con)
    by_url[url] = {"ref_id": ref_id, "url": url}
    by_ref[str(ref_id)] = {"ref_id": ref_id, "capture_id": sha, "ext": ext.lstrip("."), "status": "active"}
    return sha, ext, "fetched"


def _tenk_wanted(cik: str, name: str, since: str, until: str) -> list[dict]:
    """Every plain 10-K this company filed in the window, from the complete
    submissions JSON (D1). Amendments (10-K/A) are excluded: they carry
    exhibits and certifications, not a rewritten Item 1."""
    url = SUBMISSIONS_URL.format(cik10=str(cik).zfill(10))
    got = _fetch(url)
    if not got:
        return []
    try:
        sub = json.loads(got[0].decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        return []
    recent = (sub.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    accs = recent.get("accessionNumber") or []
    dates = recent.get("filingDate") or []
    docs = recent.get("primaryDocument") or []
    out: list[dict] = []
    for i, form in enumerate(forms):
        if str(form).strip() != "10-K":
            continue
        fdate = str(dates[i])[:10] if i < len(dates) else ""
        if not (since <= fdate <= until):
            continue
        acc = str(accs[i]) if i < len(accs) else ""
        doc = str(docs[i]) if i < len(docs) else ""
        if not acc or not doc:
            continue
        out.append(
            {
                "adsh": acc,
                "doc": doc,
                "form": "10-K",
                "file_date": fdate,
                "cik": str(cik),
                "name": name,
                "url": ARCHIVE_URL.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc),
            }
        )
    return out


def _investor_day_wanted(cik: str, name: str, since: str, until: str) -> list[dict]:
    """Investor-day 8-K hits via the evidenced phrase query (probe bundle
    2026-09-07); EFTS pagination kept to the first page per company — the
    tier is rare by nature and per-tier measurement carries it."""
    payload = search('"investor day"', "8-K", since, until, cik=cik)
    if payload.get("error"):
        return []
    out = []
    for h in hits_of(payload):
        if h.get("url"):
            h = dict(h)
            h["name"] = h.get("name") or name
            out.append(h)
    return out


def collect(
    tier: str | None = None,
    since: str = COLLECT_SINCE,
    until: str | None = None,
    limit: int | None = None,
) -> int:
    """F2 stage 3: incremental collection of the two live tiers across the
    member universe, with the offline-analyzer pattern inline: every
    captured document runs extract_priorities immediately and per-tier
    parse rates land as run metrics. NO stated_priorities writes — the
    writer is stage 4, after the parse rates are seen."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    con = store.connect()
    until = until or _dt.now(tz=_tz.utc).date().isoformat()
    tiers = [tier] if tier else ["10k_strategy", "investor_day"]
    by_url, by_ref = _capture_index(con)
    members = _member_ciks()
    if limit:
        members = members[:limit]
    stats = {
        t: {"wanted": 0, "cached": 0, "fetched": 0, "failed": 0, "docs_with_rows": 0, "rows": 0}
        for t in tiers
    }
    report: list[str] = []
    total = len(members) * len(tiers)
    done = 0
    for t in tiers:
        for cik, ticker, name in members:
            wanted = (
                _tenk_wanted(cik, name, since, until)
                if t == "10k_strategy"
                else _investor_day_wanted(cik, name, since, until)
            )
            stats[t]["wanted"] += len(wanted)
            missing = [w for w in wanted if w["url"] not in by_url or by_ref.get(str(by_url[w["url"]].get("ref_id"))) is None]
            prefetched = _pool_prefetch([w["url"] for w in missing])
            for w in wanted:
                got = _capture_doc(w["url"], w, t, by_url, by_ref, con, prefetched)
                if got is None:
                    stats[t]["failed"] += 1
                    report.append(f"  FETCH-FAILED {t} {w['form']} {w['file_date']} {w['url']}")
                    continue
                sha, ext, how = got
                stats[t][how] += 1
                try:
                    text = normalize_text(
                        library.store_path(sha, ext).read_text(encoding="utf-8", errors="replace")
                    )
                except OSError:
                    continue
                rows = extract_priorities(text, t)
                if rows:
                    stats[t]["docs_with_rows"] += 1
                    stats[t]["rows"] += len(rows)
            done += 1
            print(
                f"collect {t} {done}/{total} {ticker or cik}: wanted {len(wanted)} "
                f"cached {stats[t]['cached']} fetched {stats[t]['fetched']} failed {stats[t]['failed']}",
                flush=True,
            )
    head = ["PRIORITIES COLLECT " + " | ".join(
        f"{t}: wanted {s['wanted']} cached {s['cached']} fetched {s['fetched']} "
        f"failed {s['failed']} docs_with_rows {s['docs_with_rows']} rows {s['rows']}"
        for t, s in stats.items()
    )]
    p = store.write_export("priorities_collect_report.txt", "\n".join(head + report) + "\n")
    runr = results.start(
        "priorities-collect",
        "priorities collect",
        ["companies", "references", "captures"],
        {"tiers": ",".join(tiers), "since": since, "until": until, "limit": limit or 0,
         "rule_version": RULE_VERSION_F2},
    )
    for t, s in stats.items():
        for k, v in s.items():
            runr.metric(t, k, v)
    runr.artefact(p)
    run_id = results.finish(runr, note="incremental collector; parse rates inline; no table writes (writer is stage 4)")
    print(head[0])
    log.info(f"run {run_id} recorded")
    return 0


def _pool_prefetch(urls: list[str]) -> dict[str, tuple[bytes, str, str]]:
    """Parallel prefetch through the enabled pool; {} when disabled and the
    serial _fetch path carries each document unchanged."""
    if not getattr(config, "FETCH_POOL_ENABLED", False) or not urls:
        return {}
    from biointel import fetchpool

    exts = {"application/pdf": ".pdf", "text/plain": ".txt", "application/xml": ".xml", "text/xml": ".xml"}
    pool = fetchpool.FetchPool(rate=config.FETCH_POOL_RATE, workers=config.FETCH_POOL_WORKERS)
    out: dict[str, tuple[bytes, str, str]] = {}
    for res in pool.fetch_all(urls):
        if res.status == 200 and res.content is not None:
            ctype = (res.content_type or "").split(";")[0].strip().lower()
            out[res.url] = (res.content, exts.get(ctype, ".htm"), ctype)
    return out


def cli(argv: list[str]) -> int:
    if argv and argv[0] == "probe":
        return probe()
    if argv and argv[0] == "probe-calls":
        return probe_calls()
    if argv and argv[0] == "collect":
        kw: dict = {}
        if "--tier" in argv:
            kw["tier"] = argv[argv.index("--tier") + 1]
        if "--since" in argv:
            kw["since"] = argv[argv.index("--since") + 1]
        if "--until" in argv:
            kw["until"] = argv[argv.index("--until") + 1]
        if "--limit" in argv:
            kw["limit"] = int(argv[argv.index("--limit") + 1])
        return collect(**kw)
    print("usage: priorities probe|probe-calls|collect [--tier T] [--since D] [--until D] [--limit N]")
    return 1
