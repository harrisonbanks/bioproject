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


def cli(argv: list[str]) -> int:
    if argv and argv[0] == "probe":
        return probe()
    if argv and argv[0] == "probe-calls":
        return probe_calls()
    print("usage: priorities probe|probe-calls   (F2; extraction stages land as captures are read)")
    return 1
