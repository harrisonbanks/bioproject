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

import logging
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


def cli(argv: list[str]) -> int:
    if argv and argv[0] == "probe":
        return probe()
    print("usage: priorities probe   (F2 stage 1; later stages land after the captures are read)")
    return 1
