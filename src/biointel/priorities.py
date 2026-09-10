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
from pathlib import Path

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
    body = text[start:end]
    # Round 3 (seed 124242): an 82-char stub slice and an XBRL tag-soup
    # document both got through; both are refusals, not material.
    if len(body) < 500 or body.count("us-gaap:") + body.count("xbrli:") > 8:
        return ""
    return body


# One rule per specimen family; the guard regex must ALSO match inside the
# sentence for the category to be assigned (never a bare anchor).
PRIORITY_RULES = (
    # Akorn 10-K 2015 (03fdcee3d8f8): "We seek to acquire businesses assets
    # and products that we believe complement our existing business ..."
    ("pipeline_gap", re.compile(r"\bWe\s+(?:actively\s+)?seek\s+to\s+acquire\b[^.\u2022]{10,300}\.", re.IGNORECASE), None),
    # BMY 10-K 2019 (62ab199b8ecc): "Our four strategic priorities are to
    # ... in-licensing or acquiring investigational compounds ..."
    ("pipeline_gap", re.compile(r"\bstrategic priorities are to\b[^.\u2022]{0,500}\.", re.IGNORECASE), re.compile(r"acquir|in-licens", re.IGNORECASE)),
    # Tenax 10-K 2018 (e49b72a0ef3e): "Our principal business objective is
    # to identify, develop, and commercialize novel therapeutic products
    # for disease indications ..."
    ("therapeutic_area", re.compile(r"\bprincipal (?:business )?objective is to\b[^.\u2022]{10,300}\.", re.IGNORECASE), re.compile(r"therapeutic|disease|clinical", re.IGNORECASE)),
    # BMY 10-K 2019: "... continue to further build a leading franchise in IO ..."
    ("therapeutic_area", re.compile(r"[^.\u2022]{0,420}\bleading franchise in\b[^.\u2022]{0,420}\.", re.IGNORECASE), None),  # r6 lesson: the window must fit the real specimen (BMY sentence ~430 chars)
    # TXMD investor-day 8-K (662c4aab01a8): "... committed to advancing
    # women's health with new treatments ..."
    ("therapeutic_area", re.compile(r"[^.\u2022]{0,120}\bcommitted to advancing\s+[^.\u2022]{0,60}?health\b[^.\u2022]{0,200}\.", re.IGNORECASE), None),
    # Round 3 (seed 124242), Nomad 2019: seeking partners is structurally a
    # partnering priority whatever the disease area - fixed category.
    ("pipeline_gap", re.compile(r"seeking partners[^.\u2022]{5,240}", re.IGNORECASE), None),
)


# Round 2 (2026-09-07, miss bundle seed 35225): the corpus is dominated by
# build-side declarations — small biotechs stating what they will build,
# which the scope covers ("what it wants to buy or build"). Declaration-
# anchored families only; generic "we intend to <verb>" stays excluded (the
# misses show it is operational noise). Category is assigned by the ordered
# keyword map below; a sentence matching no category keyword yields NO row.
def _reC(pat: str):
    return re.compile(pat, re.IGNORECASE)


_CAT_MAP = (
    # p2 piece 1 (2026-09-10): commercial_infrastructure — the ninth category
    # (operator ruling 2026-09-08, decision record docs/20260908_v1_
    # Vocabulary_Gap_Commercial_Capability.md). Vocabulary written capture-
    # first from the banked specimens only; ordered FIRST because every
    # mixed-payload specimen (Brazil market-access "platform", pain-
    # management "commercial reach") was operator-held as commercial, so
    # channel payload outranks the other maps. Single-word terms boundary-
    # anchored by construction (handoff rule 2.6); no bare "sales"/
    # "commercial"/"commercializ" stems, so the Arbutus out-licensing and
    # going-concern families can never land here (amendment 2, 2026-09-10).
    ("commercial_infrastructure", _reC(
        r"commercial infrastructure|commercial capabilit|commercial reach|"
        r"commercial execution|market access|delivery network|"
        r"healthcare gateway|suitable infrastructure|value-based payment|"
        r"sales force|(?<![a-z])salesforce|(?<![a-z])payer|"
        r"(?<![a-z])channel|(?<![a-z])telehealth|(?<![a-z])distribution"
    )),
    # Dictionary sweep 2026-09-09 (operator-ordered, boundary-anchor program):
    # unanchored fragments here are INTENTIONAL stems — mid-word hits are the
    # desired medical compounds (chemotherapy/therap, inpatients/patients,
    # epidermal/derm, hypoallergenic/allerg), locked as tests below. True
    # dictionary traps found: alderman|bewilderment (derm), vindication
    # (indication) — corpus-implausible; anchoring them CHANGES matches under
    # the sealed L3-a3-p1 rules, so the match-changing anchor is banked for
    # the p2 rule-version bump with this sweep as its evidence.
    ("pipeline_gap", _reC(r"acquir|in-licens|\blicens")),
    ("pipeline_gap", _reC(r"\bpipeline\b")),
    ("platform", _reC(r"\bplatform\b|\bmodalit|\btechnolog")),
    # p2 piece 3 (2026-09-10): the two banked dictionary traps close
    # (sweep evidence 2026-09-09 above): derm is left-anchored with an
    # epiderm carve-out (alderman/bewilderment no longer fire; epidermal
    # still does), indication is left-anchored (vindication no longer
    # fires). therap/patients/allerg stay intentional stems - the oracle
    # test (chemotherapy/outpatients/hypoallergenic) is the frozen
    # baseline this edit is measured against.
    ("therapeutic_area", _reC(
        r"oncolog|immuno|(?<![a-z])derm|epiderm|cancer|\bdisease|"
        r"(?<![a-z])indication|therap|patients|"
        r"allerg|cardiovas|neuro|\brare\b|obesity|\btreat"
    )),
)


def _category_for(sentence: str) -> str | None:
    for cat, rx in _CAT_MAP:
        if rx.search(sentence):
            return cat
    return None


_DECLARATIONS = (
    # DBV 2022 / Bolt 2024: "Key elements/components of our strategy are: • ..."
    _reC(r"key (?:elements|components) of our strategy (?:is|are)(?: to)?:?\s*(?:\d+ Table of Contents )?[^.\u2022]{0,80}\u2022?[^.\u2022]{10,320}"),
    # aTYR 2016 / Arcutis 2022: "Our strategy is to focus ..."
    _reC(r"our strategy is to [^.\u2022]{10,340}\."),
    # DBV / Bolt: "Our goal is to ..."
    _reC(r"our goal is to [^.\u2022]{10,340}\."),
    # aTYR: "we aim to build a proprietary pipeline of ..."
    _reC(r"we aim to [^.\u2022]{10,300}\."),
    # Oric 2024: constrained intend-to (in-licensing / strategic partnering only)
    _reC(r"we (?:intend|plan) to (?:in-licens|acquir|licens|evaluate strategic partner)[^.\u2022]{0,300}\."),
    # Round 3 (seed 124242) - identity declarations (Immuneering 2023, Phio
    # 2021): the FLS laundry lists never carry this form.
    _reC(r"company developing [^.\u2022]{10,280}\."),
    # Omeros 2019 / BioVie 2018: purpose tail excludes FLS boilerplate.
    _reC(r"(?:committed to|focused on)[^.\u2022]{0,60}?developing and commercializing [^.\u2022]{10,240}\."),
    # Travere 2022: "our mission to address the unmet needs of patients ..."
    _reC(r"our mission[^.\u2022]{5,280}\."),
)


# p2 piece 2 (2026-09-10): sentence-start capture + negation guard, written
# capture-first against the locked specimens (handoff s3.1): Opus
# Scffcdfdcf539e686 (mid-sentence "seeking partnerships" start AND a negated
# "nor do we plan to acquire" clip, both recovered verbatim in evidence
# 20260910_p2c), Biogen S0f15a669a2338908 ("We support our mission" start
# dropped), S1e6a836 (same negation class, validator keeps routing stored
# rows garbled), S02a95e (bullet debris, refused structurally by the
# \u2022-excluding char classes above).
_SENTENCE_BREAK_RX = re.compile(r"[.!?;\u2022]")
_SENTENCE_LOOKBACK = 300  # chars; no terminator inside the window = keep the rule's own start
_NEGATION_RX = re.compile(
    r"\b(?:do|does|did)\s+not\b[^.\u2022]{0,80}\b(?:plan|intend|seek|aim|expect)\b"
    r"|\bnor\s+do\s+we\b"
    r"|\bno\s+(?:current\s+)?plans?\s+to\b"
    r"|\bnot\s+(?:currently\s+)?(?:plan|intend|seek|aim)\b",
    re.IGNORECASE,
)


def _sentence_start(body: str, start: int) -> int:
    """Start of the sentence containing position `start`: one past the last
    terminator within the lookback window, else `start` unchanged."""
    lo = max(0, start - _SENTENCE_LOOKBACK)
    last = None
    for m in _SENTENCE_BREAK_RX.finditer(body, lo, start):
        last = m
    return last.end() if last is not None else start


def _capture_sentence(body: str, m: "re.Match") -> str | None:
    """The rule match expanded to its true sentence start; None when the
    expanded sentence is negated (the Opus/S1e6a836 inversion class). If
    expansion would push the joined sentence past the 500-char cap, the
    rule's own start is kept, so expansion never truncates meaning from the
    tail (the clip class this fix exists to close)."""
    start = _sentence_start(body, m.start())
    sent = " ".join(body[start : m.end()].split())
    if len(sent) > 500:
        sent = " ".join(m.group(0).split())
    if _NEGATION_RX.search(sent):
        return None
    return sent[:500]


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
    seen: set[tuple[str, str]] = set()  # p2: (category, sentence) — expansion can equalize two rules' texts (BMY dual capture)
    for category, rule, guard in PRIORITY_RULES:
        for m in rule.finditer(body):
            sent = _capture_sentence(body, m)
            if sent is None:
                continue
            if guard and not guard.search(sent):
                continue
            if (category, sent) in seen:
                continue
            seen.add((category, sent))
            out.append(
                {"category": category, "sentence": sent, "section": section,
                 "source_type": source_type}
            )
    for rule in _DECLARATIONS:
        for m in rule.finditer(body):
            sent = _capture_sentence(body, m)
            if sent is None:
                continue
            cat = _category_for(sent)
            if cat is None or (cat, sent) in seen:
                continue
            seen.add((cat, sent))
            out.append(
                {"category": cat, "sentence": sent, "section": section,
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




# ---------------------------------------------------------------- F2 stage 3b: the miss loop (offline, zero fetches)
def sample_misses(n: int = 12, seed: int | None = None, con=None) -> int:
    """The F1 miss loop for priorities: dump the Item 1 slice of N
    10-K captures that yielded ZERO rows under the current rules, to one
    bundle the operator attaches. New rule families are written only
    against these real slices, then re-extraction runs offline against the
    shelf. Deterministic given a seed; each cycle uses a fresh seed so
    successive samples cover new ground."""
    import random as _r

    con = con or store.connect()
    seed = seed if seed is not None else int(_dt_seed())
    _by_url, by_ref = _capture_index(con)
    docs: list[tuple[str, dict]] = []
    for r in store.read_table("references", con=con):
        note = str(r.get("note") or "")
        if "source_type=10k_strategy" not in note or f"captured by {TOOL}" not in note:
            continue
        cap = by_ref.get(str(r["ref_id"]))
        if cap is not None:
            docs.append((str(r.get("title") or ""), cap))
    _r.seed(seed)
    _r.shuffle(docs)
    out: list[str] = []
    dumped = 0
    scanned = 0
    unsliceable = 0
    for title, cap in docs:
        if dumped >= n:
            break
        scanned += 1
        ext = "." + str(cap.get("ext") or "htm")
        try:
            text = normalize_text(
                library.store_path(str(cap["capture_id"]), ext).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except OSError:
            continue
        if extract_priorities(text, "10k_strategy"):
            continue  # a hit; the loop wants misses
        body = item1_slice(text)
        if not body:
            unsliceable += 1
            continue
        dumped += 1
        out.append(
            "=" * 78 + f"\nMISS {dumped}  {title}  capture {str(cap['capture_id'])[:12]}\n"
            + "=" * 78 + "\n" + body[:20000]
        )
    head = [
        (
            f"PRIORITIES MISS SAMPLE — {dumped} zero-row Item 1 slices "
            f"(seed {seed}, scanned {scanned}, unsliceable {unsliceable}). "
            "New rules are written ONLY against these; each becomes a verbatim test."
        )
    ]
    p = store.write_export("priorities_miss_bundle.txt", "\n".join(head) + "\n\n" + "\n\n".join(out) + "\n")
    runr = results.start(
        "priorities-miss-sample", "priorities sample-misses", ["references", "captures"],
        {"n": n, "seed": seed, "rule_version": RULE_VERSION_F2},
    )
    runr.metric("_", "dumped", dumped)
    runr.metric("_", "scanned", scanned)
    runr.metric("_", "unsliceable", unsliceable)
    runr.artefact(p)
    run_id = results.finish(runr, note="offline miss loop; no fetches")
    print(f"MISS-SAMPLE dumped {dumped} scanned {scanned} unsliceable {unsliceable} seed {seed} -> {p}")
    log.info(f"run {run_id} recorded")
    return 0


def _dt_seed() -> int:
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    return int(_dt.now(tz=_tz.utc).strftime("%H%M%S"))


def reextract(con=None) -> int:
    """Offline re-extraction over every collected capture of both live
    tiers under the CURRENT rules: per-tier parse rates as run metrics,
    zero fetches, minutes. The measuring stick each miss-loop cycle."""
    con = con or store.connect()
    _by_url, by_ref = _capture_index(con)
    stats = {t: {"docs": 0, "docs_with_rows": 0, "rows": 0} for t in ("10k_strategy", "investor_day")}
    for r in store.read_table("references", con=con):
        note = str(r.get("note") or "")
        if f"captured by {TOOL}" not in note:
            continue
        t = next((x for x in stats if f"source_type={x}" in note), None)
        if t is None:
            continue
        cap = by_ref.get(str(r["ref_id"]))
        if cap is None:
            continue
        ext = "." + str(cap.get("ext") or "htm")
        try:
            text = normalize_text(
                library.store_path(str(cap["capture_id"]), ext).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except OSError:
            continue
        stats[t]["docs"] += 1
        rows = extract_priorities(text, t)
        if rows:
            stats[t]["docs_with_rows"] += 1
            stats[t]["rows"] += len(rows)
    runr = results.start(
        "priorities-reextract", "priorities reextract", ["references", "captures"],
        {"rule_version": RULE_VERSION_F2},
    )
    for t, s in stats.items():
        for k, v in s.items():
            runr.metric(t, k, v)
    run_id = results.finish(runr, note="offline rule-coverage measurement; no fetches, no writes")
    print(
        "REEXTRACT "
        + " | ".join(
            f"{t}: docs {s['docs']} with_rows {s['docs_with_rows']} rows {s['rows']}"
            for t, s in stats.items()
        )
    )
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- F2 stage 4: the writer
def write(con=None) -> int:
    """Sweep the shelf under the FROZEN rules (L3-a3-p1) and replace
    stated_priorities with the extracted rows. Diagnostic of record
    (2026-09-08): the live table held 0 rows, so no legacy mapping exists;
    dossier-era categories live only in test fixtures. Key collision
    ruling: one row per (entity, stated_at, category) - the longest
    sentence wins, every runner-up goes verbatim to the overflow export so
    nothing is lost and the Q5 judging unit is untouched. write_table
    replaces the whole table, so re-running is idempotent by construction."""
    from biointel import schema as _schema

    con = con or store.connect()
    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    if store.has_table("stated_priorities", con):
        store.add_columns("stated_priorities", _schema.STATED_PRIORITY_F2_COLS, con=con)
    _by_url, by_ref = _capture_index(con)
    # latest verdict per judged key at this rule version:
    # "" = wrong-no-relabel (suppress); "cat" = relabel; absent = untouched
    verdicts: dict[str, str] = {}
    if store.has_table("candidate_reviews", con):
        for rv in sorted(
            store.read_table("candidate_reviews", con=con),
            key=lambda r: str(r["reviewed_at"]),
        ):
            if str(rv.get("rule_version")) != RULE_VERSION_F2:
                continue
            key = str(rv["candidate_id"])
            vd = str(rv["verdict"])
            nt = str(rv.get("note") or "")
            if vd == "wrong":
                m2 = re.match(r"relabel:([a-z_]+);", nt)
                verdicts[key] = m2.group(1) if m2 else ""
            elif vd in ("correct", "unsure") and key in verdicts:
                del verdicts[key]
    # candidate ids are S-keys (hash of entity|date|category): re-key
    plain: dict[str, str] = {}
    for skey, v in verdicts.items():
        plain[skey] = v
    verdicts = plain
    best: dict[tuple, dict] = {}
    overflow: list[str] = []
    stats = {t: {"docs": 0, "rows": 0} for t in ("10k_strategy", "investor_day")}
    for r in store.read_table("references", con=con):
        note = str(r.get("note") or "")
        if f"captured by {TOOL}" not in note:
            continue
        tier = next((x for x in stats if f"source_type={x}" in note), None)
        if tier is None:
            continue
        cap = by_ref.get(str(r["ref_id"]))
        if cap is None:
            continue
        m = re.search(r"cik=(\d+)", note)
        d = re.search(r"file_date=(\d{4}-\d{2}-\d{2})", note)
        if not m or not d:
            continue
        entity = f"CIK:{int(m.group(1))}"
        ext = "." + str(cap.get("ext") or "htm")
        try:
            text = normalize_text(
                library.store_path(str(cap["capture_id"]), ext).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        except OSError:
            continue
        rows = extract_priorities(text, tier)
        if not rows:
            continue
        stats[tier]["docs"] += 1
        for row in rows:
            stats[tier]["rows"] += 1
            k = (entity, d.group(1), row["category"])
            # verdict-aware (operator ruling 2026-09-09, "never throw away
            # good information / never resurrect judged lies"): a key judged
            # wrong WITHOUT a relabel is suppressed forever; a relabel
            # rewrites the category before keying.
            import hashlib as _h

            skey = "S" + _h.sha256(f"{k[0]}|{k[1]}|{k[2]}".encode()).hexdigest()[:16]
            v = verdicts.get(skey)
            if v is not None:
                if v == "":
                    stats[tier]["suppressed_judged_wrong"] = (
                        stats[tier].get("suppressed_judged_wrong", 0) + 1
                    )
                    continue
                row = dict(row)
                row["category"] = v
                k = (entity, d.group(1), v)
                stats[tier]["relabeled"] = stats[tier].get("relabeled", 0) + 1
            cand = {
                "entity_key": entity,
                "stated_at": d.group(1),
                "category": row["category"],
                "statement": row["sentence"],
                "doc_id": str(cap["capture_id"]),
                "span": row["sentence"][:500],
                "source_type": tier,
                "section": row["section"],
            }
            held = best.get(k)
            if held is None:
                best[k] = cand
            elif len(cand["statement"]) > len(held["statement"]):
                overflow.append(f"{k[0]} {k[1]} {k[2]} | {held['statement']}")
                best[k] = cand
            else:
                overflow.append(f"{k[0]} {k[1]} {k[2]} | {cand['statement']}")
    written = store.write_table("stated_priorities", list(best.values()), cols, con=con)
    p = store.write_export(
        "stated_priorities_overflow.txt",
        "\n".join(overflow) + ("\n" if overflow else ""),
    )
    runr = results.start(
        "priorities-write", "priorities write",
        ["references", "captures", "stated_priorities"],
        {"rule_version": RULE_VERSION_F2},
    )
    for t, s in stats.items():
        for k2, v in s.items():
            runr.metric(t, k2, v)
    runr.metric("_", "rows_written", written)
    runr.metric("_", "overflow", len(overflow))
    runr.artefact(p)
    run_id = results.finish(
        runr, note="frozen rules L3-a3-p1; longest-sentence-per-key ruling; overflow preserved"
    )
    print(
        "WRITE rows_written "
        + str(written)
        + " overflow "
        + str(len(overflow))
        + " | "
        + " | ".join(f"{t}: docs {s['docs']} rows {s['rows']}" for t, s in stats.items())
    )
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- F2 stage 5: blind sample, judge, precision (Q5)
# Q5 of record: unit = one extracted sentence; a row passes only if company,
# date, category and sentence are all correct; 60 per source tier, Wilson
# interval per tier, sample size a parameter. Verdict gating is implemented
# as judge-then-retire (the F1 stakes precedent, stated in docs): rows were
# written in bulk, and a judged-wrong row is deleted from the table, so
# judged-wrong rows never survive. The earnings_call tier is a recorded
# coverage hole; the two live tiers are measured.
def _row_key(r: dict) -> str:
    import hashlib as _h

    return "S" + _h.sha256(
        f"{r['entity_key']}|{str(r['stated_at'])[:10]}|{r['category']}".encode()
    ).hexdigest()[:16]


def sample(n: int = 60, tier: str | None = None, seed: int | None = None, con=None) -> int:
    """Print a seeded blind worksheet of n rows per live tier (or one tier):
    key, company, date, category, sentence, and the source document URL.
    Prints only; verdicts arrive via `priorities judge`."""
    import random as _r

    con = con or store.connect()
    seed = seed if seed is not None else _dt_seed()
    rows = store.read_table("stated_priorities", con=con)
    url_by_doc: dict[str, str] = {}
    for ref in store.read_table("references", con=con):
        note = str(ref.get("note") or "")
        if f"captured by {TOOL}" in note:
            url_by_doc[str(ref["ref_id"])] = str(ref.get("url") or "")
    cap_ref = {
        str(c["capture_id"]): str(c["ref_id"])
        for c in store.read_table("captures", con=con)
        if str(c.get("status")) == "active"
    }
    tiers = [tier] if tier else ["10k_strategy", "investor_day"]
    judged = {
        str(r["candidate_id"])
        for r in (
            store.read_table("candidate_reviews", con=con)
            if store.has_table("candidate_reviews", con)
            else []
        )
        if str(r.get("rule_version")) == RULE_VERSION_F2
    }
    proposals: dict[str, dict] = {}
    if store.has_table("review_proposals", con):
        for pr in store.read_table("review_proposals", con=con):
            if str(pr.get("prompt_version")) == F2_PROMPT_VERSION:
                proposals[str(pr["queue_id"])] = pr  # last written wins
    shown = 0
    for t in tiers:
        pool = [
            r
            for r in rows
            if str(r.get("source_type")) == t and _row_key(r) not in judged
        ]
        _r.seed(seed)
        _r.shuffle(pool)
        print(f"--- {t}: {min(n, len(pool))} of {len(pool)} unjudged rows (seed {seed}) ---")
        for r in pool[:n]:
            key = _row_key(r)
            url = url_by_doc.get(cap_ref.get(str(r["doc_id"]), ""), "(no url)")
            pr = proposals.get(key)
            tag = (
                f"  [assist {pr['model_id']}: {pr['verdict']} - {str(pr['reason'])[:70]}]"
                if pr
                else ""
            )
            print(
                f"{key}  {r['entity_key']:<12} {str(r['stated_at'])[:10]} "
                f"{r['category']:<17} {str(r['statement'])[:180]}" + tag
            )
            print(f"    doc: {url}")
            shown += 1
    print(f"WORKSHEET rows {shown}; judge with: priorities judge KEY correct|wrong|unsure [--note T]")
    return 0


def judge(key: str, verdict: str, note: str = "", relabel: str = "", reviewer: str = "operator", con=None) -> int:
    """Record one human verdict against a sampled row (rule-version scoped).
    A `wrong` verdict with a RELABEL repairs the row in place — the
    operator's category replaces the extractor's stamp, provenance in the
    review note (the M3/fix-direction precedent: human corrections repair
    data, they don't destroy it). A `wrong` without a relabel means the
    sentence is not a priority at all, and the row retires."""
    from biointel import schema as _schema

    if verdict not in _schema.REVIEW_VERDICTS:
        print(f"verdict must be one of {_schema.REVIEW_VERDICTS}")
        return 1
    if relabel and relabel not in _schema.PRIORITY_CATEGORIES:
        print(f"relabel must be one of {_schema.PRIORITY_CATEGORIES}")
        return 1
    con = con or store.connect()
    rows = store.read_table("stated_priorities", con=con)
    hit = next((r for r in rows if _row_key(r) == key), None)
    if hit is None:
        print(f"no stated_priorities row with key {key}")
        return 1
    existing = (
        store.read_table("candidate_reviews", con=con)
        if store.has_table("candidate_reviews", con)
        else []
    )
    seq = 1 + sum(1 for r in existing if str(r["candidate_id"]) == key)
    full_note = (f"relabel:{relabel};" if relabel else "") + note[:280]
    row = {
        "review_id": f"{key}-v{seq}",
        "candidate_id": key,
        "rule_version": RULE_VERSION_F2,
        "verdict": verdict,
        "reviewer": reviewer,
        "note": full_note[:300],
        "reviewed_at": library._now(),
    }
    store.append_rows(
        "candidate_reviews", [row], list(_schema.CANDIDATE_REVIEW_COLS), con=con
    )
    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    retired = relabeled = 0
    if verdict == "wrong" and relabel:
        # key includes category, so the repair is a key change: collision-checked
        clash = any(
            str(r["entity_key"]) == str(hit["entity_key"])
            and str(r["stated_at"])[:10] == str(hit["stated_at"])[:10]
            and str(r["category"]) == relabel
            for r in rows
        )
        if clash:
            print(f"RELABEL REFUSED {key}: a row already holds {relabel} for that entity/date; retiring instead")
            rows = [r for r in rows if _row_key(r) != key]
            retired = 1
        else:
            hit["category"] = relabel
            relabeled = 1
        store.write_table("stated_priorities", rows, cols, con=con)
    elif verdict == "wrong":
        rows = [r for r in rows if _row_key(r) != key]
        store.write_table("stated_priorities", rows, cols, con=con)
        retired = 1
    print(f"JUDGED {key} {verdict}; retired {retired} relabeled {relabeled}" + (f" -> {relabel}" if relabeled else ""))
    return 0


def record_restore(key: str, relabel: str, note: str = "", con=None) -> int:
    """Record a machine-restoration relabel for a key whose row was deleted
    under the old delete-only judge (operator ruling 2026-09-09: corrected
    information is never thrown away). reviewer = "draft-restore" - these
    verdicts NEVER count in precision (operator-only) and apply at the next
    verdict-aware `priorities write`, which regenerates the row from the
    shelf under the corrected label."""
    from biointel import schema as _schema

    if relabel not in _schema.PRIORITY_CATEGORIES:
        print(f"relabel must be one of {_schema.PRIORITY_CATEGORIES}")
        return 1
    con = con or store.connect()
    existing = (
        store.read_table("candidate_reviews", con=con)
        if store.has_table("candidate_reviews", con)
        else []
    )
    seq = 1 + sum(1 for r in existing if str(r["candidate_id"]) == key)
    row = {
        "review_id": f"{key}-v{seq}",
        "candidate_id": key,
        "rule_version": RULE_VERSION_F2,
        "verdict": "wrong",
        "reviewer": "draft-restore",
        "note": (f"relabel:{relabel};" + note)[:300],
        "reviewed_at": library._now(),
    }
    store.append_rows(
        "candidate_reviews", [row], list(_schema.CANDIDATE_REVIEW_COLS), con=con
    )
    print(f"RESTORE-RECORDED {key} -> {relabel}")
    return 0


def precision(con=None) -> int:
    """Per-tier precision over this rule version's verdicts, Wilson 95%."""
    from biointel.efts import _wilson

    con = con or store.connect()
    rows = {
        _row_key(r): str(r.get("source_type") or "")
        for r in store.read_table("stated_priorities", con=con)
    }
    allv = [
        r
        for r in (
            store.read_table("candidate_reviews", con=con)
            if store.has_table("candidate_reviews", con)
            else []
        )
        if str(r.get("rule_version")) == RULE_VERSION_F2
    ]
    # measurement counts HUMAN verdicts only (operator ruling 2026-09-09);
    # machine draft-acceptances and restorations are reported, never counted.
    # PATTERN verdicts (operator ruling 2026-09-09, "The judging surface")
    # are operator decisions applied cluster-wide: reported on their own
    # line, never silently mixed with row-ruled ones.
    verdicts = [r for r in allv if str(r.get("reviewer")) == "operator"]
    pattern_v = [r for r in allv if str(r.get("reviewer")) == "operator-pattern"]
    drafts = len(allv) - len(verdicts) - len(pattern_v)
    if drafts:
        print(f"DRAFT-RECORDED (not counted): {drafts} machine verdicts")
    if pattern_v:
        pc: dict[str, int] = {}
        for r in pattern_v:
            pc[str(r["verdict"])] = pc.get(str(r["verdict"]), 0) + 1
        print(
            "PATTERN-RULED (operator, cluster-wide; own bucket): "
            + " ".join(f"{k} {v}" for k, v in sorted(pc.items()))
        )
    tiers: dict[str, dict[str, int]] = {}
    tier_of: dict[str, str] = dict(rows)
    for v in verdicts:
        cid = str(v["candidate_id"])
        t = tier_of.get(cid)
        if t is None:
            # a relabel changed the row's key; attribute to its own bucket
            m2 = re.match(r"relabel:([a-z_]+);", str(v.get("note") or ""))
            t = "relabeled" if m2 else "retired"
        d = tiers.setdefault(t if t else "retired", {"correct": 0, "wrong": 0, "unsure": 0})
        d[str(v["verdict"])] = d.get(str(v["verdict"]), 0) + 1
    runr = results.start(
        "priorities-precision", "priorities precision", ["candidate_reviews"],
        {"rule_version": RULE_VERSION_F2},
    )
    for t, d in sorted(tiers.items()):
        k, w = d.get("correct", 0), d.get("wrong", 0)
        nn = k + w
        lo, hi = _wilson(k, nn) if nn else (0.0, 0.0)
        print(
            f"PRECISION {t}: {k}/{nn} correct"
            + (f" = {k / nn:.3f} (wilson {lo:.3f}-{hi:.3f})" if nn else "")
            + f"; unsure {d.get('unsure', 0)}"
        )
        for m, v in (("correct", k), ("wrong", w), ("unsure", d.get("unsure", 0))):
            runr.metric(t, m, v)
    props = {
        str(p["queue_id"]): str(p["verdict"])
        for p in (
            store.read_table("review_proposals", con=con)
            if store.has_table("review_proposals", con)
            else []
        )
        if str(p.get("prompt_version")) == F2_PROMPT_VERSION
    }
    agree = comp = 0
    for v in verdicts:
        pv = props.get(str(v["candidate_id"]))
        if pv:
            comp += 1
            agree += int(pv == str(v["verdict"]))
    if comp:
        print(f"ASSIST-AGREEMENT {agree}/{comp} = {agree / comp:.3f} (proposals vs human verdicts)")
        runr.metric("_", "assist_agree", agree)
        runr.metric("_", "assist_compared", comp)
    run_id = results.finish(runr, note=f"Q5 measurement at {RULE_VERSION_F2}")
    log.info(f"run {run_id} recorded")
    return 0


# ---------------------------------------------------------------- F2 assist: LLM-drafts, human approves (permanent, operator ruling 2026-09-08)
F2_PROMPT_VERSION = "judge_priority_v1"


def assist_sample(n: int = 60, tier: str | None = None, seed: int | None = None, con=None) -> int:
    """Draft one verdict proposal per sampled unjudged row via the M4
    machinery (configurable model, cap, ASSIST_ENABLED gate, env-only key,
    degradation on failure) and store it in review_proposals with full
    provenance, keyed by the row's S-key. The worksheet shows proposals
    beside rows; the human approves with `priorities judge`; `precision`
    reports AI-vs-human agreement. Same seed default as sample() so the
    proposal set covers the judging set."""
    import hashlib as _h
    import random as _r

    from biointel import assist as _assist
    from biointel import config as _config
    from biointel import schema as _schema

    if not getattr(_config, "ASSIST_ENABLED", False):
        print("assist disabled: set ASSIST_ENABLED = True in config to use it")
        return 1
    con = con or store.connect()
    model = getattr(_config, "ASSIST_MODEL", _assist.DEFAULT_MODEL)
    cap = int(getattr(_config, "ASSIST_CALL_CAP", _assist.DEFAULT_CAP))
    seed = seed if seed is not None else _dt_seed()
    prompt_tpl = (Path(__file__).parent / "prompts" / f"{F2_PROMPT_VERSION}.txt").read_text(
        encoding="utf-8"
    )
    names = {
        f"CIK:{int(str(c['CIK']))}": str(c["Name"])
        for c in store.read_table("companies", con=con)
        if str(c.get("CIK") or "").strip().isdigit()
    }
    cap_ref = {
        str(c["capture_id"]): c
        for c in store.read_table("captures", con=con)
        if str(c.get("status")) == "active"
    }
    existing = (
        {str(p["proposal_id"]) for p in store.read_table("review_proposals", con=con)}
        if store.has_table("review_proposals", con)
        else set()
    )
    judged = {
        str(r["candidate_id"])
        for r in (
            store.read_table("candidate_reviews", con=con)
            if store.has_table("candidate_reviews", con)
            else []
        )
        if str(r.get("rule_version")) == RULE_VERSION_F2
    }
    rows = store.read_table("stated_priorities", con=con)
    tiers = [tier] if tier else ["10k_strategy", "investor_day"]
    counters = {"proposed": 0, "cached": 0, "api_failures": 0, "malformed": 0, "no_doc": 0}
    out_rows: list[dict] = []
    for t in tiers:
        pool = [r for r in rows if str(r.get("source_type")) == t and _row_key(r) not in judged]
        _r.seed(seed)
        _r.shuffle(pool)
        for r in pool[:n]:
            if counters["proposed"] >= cap:
                break
            key = _row_key(r)
            pid = "P" + _h.sha256(f"{key}|{model}|{F2_PROMPT_VERSION}".encode()).hexdigest()[:16]
            if pid in existing:
                counters["cached"] += 1
                continue
            capr = cap_ref.get(str(r["doc_id"]))
            text = _doc_text_of(capr) if capr else None
            if text is None:
                counters["no_doc"] += 1
                continue
            sent = str(r["statement"])
            i = text.find(sent[:80])
            lo = max(0, (max(i, 0)) - 1500)
            excerpt = text[lo : (max(i, 0)) + 2500][:5000]
            prompt = prompt_tpl.format(
                company=names.get(str(r["entity_key"]), "(unknown)"),
                entity_key=r["entity_key"],
                stated_at=str(r["stated_at"])[:10],
                category=r["category"],
                sentence=sent,
                excerpt=excerpt,
            )
            reply = _assist._call_api(prompt, model, max_tokens=1000)
            if reply is None:
                counters["api_failures"] += 1
                continue
            parsed = _assist.parse_reply(reply)
            if parsed is None or parsed[0] == "abstain":
                counters["malformed"] += 1
                continue
            verdict, reason = parsed
            prow = dict.fromkeys(_schema.REVIEW_PROPOSAL_COLS, "")
            prow.update(
                {
                    "proposal_id": pid,
                    "queue_id": key,
                    "model_id": model,
                    "prompt_version": F2_PROMPT_VERSION,
                    "excerpt_hash": _h.sha256(excerpt.encode()).hexdigest()[:16],
                    "verdict": verdict,
                    "reason": reason,
                    "created_at": library._now(),
                }
            )
            out_rows.append(prow)
            counters["proposed"] += 1
    if out_rows:
        store.append_rows(
            "review_proposals", out_rows, list(_schema.REVIEW_PROPOSAL_COLS), con=con
        )
    runr = results.start(
        "priorities-assist", "priorities assist",
        ["stated_priorities", "review_proposals"],
        {"model": model, "prompt_version": F2_PROMPT_VERSION, "seed": seed, "cap": cap},
    )
    for k2, v in counters.items():
        runr.metric("_", k2, v)
    run_id = results.finish(runr, note="proposer only; human verdicts remain the measurement")
    print("F2-ASSIST model " + model + " " + " ".join(f"{k} {v}" for k, v in counters.items()))
    log.info(f"run {run_id} recorded")
    return 0


def triage(tier: str | None = None, seed: int | None = None, con=None, _counters: dict | None = None) -> int:
    """Two-model triage over the unjudged pool (operator rulings
    2026-09-09): every candidate row is proposed on by BOTH models in
    config.TRIAGE_MODELS via the M4 machinery (env-only key, degradation
    on failure, provenance in review_proposals — abstain/unsure proposals
    are STORED here, a stated deviation from assist_sample, because the
    disagreement classes need them). Where both models return the same
    decided verdict (correct|wrong) the verdict is auto-recorded with
    reviewer="draft-agree" — never counted in operator precision; consumed
    only by the verdict-aware `priorities write`, where a later operator
    verdict on the same key overrides by reviewed_at order. Disagreements
    and undecided agreements queue for the human but NEVER print here
    (judging-surface ruling 2026-09-09): the output is a pointer to
    `priorities triage-clusters`, the only human surface. Cached proposals
    are reused without an API call, so re-running resumes under the cap."""
    import hashlib as _h

    from biointel import assist as _assist
    from biointel import config as _config
    from biointel import schema as _schema

    if not getattr(_config, "ASSIST_ENABLED", False):
        print("assist disabled: set ASSIST_ENABLED = True in config to use it")
        return 1
    con = con or store.connect()
    models = list(getattr(_config, "TRIAGE_MODELS", ("claude-sonnet-5", "claude-haiku-4-5")))
    cap = int(getattr(_config, "TRIAGE_CALL_CAP", 500))
    max_tokens = int(getattr(_config, "TRIAGE_MAX_TOKENS", 1000))
    seed = seed if seed is not None else _dt_seed()
    prompt_tpl = (Path(__file__).parent / "prompts" / f"{F2_PROMPT_VERSION}.txt").read_text(
        encoding="utf-8"
    )
    names = {
        f"CIK:{int(str(c['CIK']))}": str(c["Name"])
        for c in store.read_table("companies", con=con)
        if str(c.get("CIK") or "").strip().isdigit()
    }
    cap_ref = {
        str(c["capture_id"]): c
        for c in store.read_table("captures", con=con)
        if str(c.get("status")) == "active"
    }
    proposals = (
        {str(p["proposal_id"]): p for p in store.read_table("review_proposals", con=con)}
        if store.has_table("review_proposals", con)
        else {}
    )
    reviews = (
        store.read_table("candidate_reviews", con=con)
        if store.has_table("candidate_reviews", con)
        else []
    )
    judged = {
        str(r["candidate_id"]) for r in reviews
        if str(r.get("rule_version")) == RULE_VERSION_F2
    }
    seq_base: dict[str, int] = {}
    for r in reviews:
        cid = str(r["candidate_id"])
        seq_base[cid] = seq_base.get(cid, 0) + 1
    rows = store.read_table("stated_priorities", con=con)
    # settled stays settled (operator ruling 2026-09-09): operator-relabeled
    # rows never re-enter the triage pool
    judged |= _settled_keys({_row_key(r): r for r in rows}, reviews)
    tiers = [tier] if tier else ["10k_strategy", "investor_day"]
    counters = {
        "rows_considered": 0, "calls_made": 0, "cached": 0, "agree_recorded": 0,
        "disagreements": 0, "undecided_agree": 0, "api_failures": 0,
        "malformed": 0, "no_doc": 0,
    }
    new_props: list[dict] = []
    new_reviews: list[dict] = []
    agreed: list[tuple[dict, str, dict]] = []  # (row, verdict, per-model verdicts)
    human: list[tuple[dict, dict]] = []  # (row, per-model verdict/reason)
    for t in tiers:
        pool = [r for r in rows if str(r.get("source_type")) == t and _row_key(r) not in judged]
        pool.sort(key=_row_key)  # deterministic order; resumability across runs
        for r in pool:
            if counters["calls_made"] + len(models) > cap and any(
                "P" + _h.sha256(f"{_row_key(r)}|{m}|{F2_PROMPT_VERSION}".encode()).hexdigest()[:16]
                not in proposals
                for m in models
            ):
                continue  # cap would be breached by this row's uncached calls
            key = _row_key(r)
            capr = cap_ref.get(str(r["doc_id"]))
            text = _doc_text_of(capr) if capr else None
            if text is None:
                counters["no_doc"] += 1
                continue
            counters["rows_considered"] += 1
            sent = str(r["statement"])
            i = text.find(sent[:80])
            lo = max(0, (max(i, 0)) - 1500)
            excerpt = text[lo : (max(i, 0)) + 2500][:5000]
            prompt = prompt_tpl.format(
                company=names.get(str(r["entity_key"]), "(unknown)"),
                entity_key=r["entity_key"],
                stated_at=str(r["stated_at"])[:10],
                category=r["category"],
                sentence=sent,
                excerpt=excerpt,
            )
            per_model: dict[str, tuple[str, str]] = {}
            degraded = False
            for m in models:
                pid = "P" + _h.sha256(f"{key}|{m}|{F2_PROMPT_VERSION}".encode()).hexdigest()[:16]
                held = proposals.get(pid)
                if held is not None:
                    counters["cached"] += 1
                    per_model[m] = (str(held["verdict"]), str(held.get("reason") or ""))
                    continue
                counters["calls_made"] += 1
                reply = _assist._call_api(prompt, m, max_tokens=max_tokens)
                if reply is None:
                    counters["api_failures"] += 1
                    degraded = True
                    continue
                parsed = _assist.parse_reply(reply)
                if parsed is None:
                    counters["malformed"] += 1
                    degraded = True
                    continue
                verdict, reason = parsed
                prow = dict.fromkeys(_schema.REVIEW_PROPOSAL_COLS, "")
                prow.update(
                    {
                        "proposal_id": pid,
                        "queue_id": key,
                        "model_id": m,
                        "prompt_version": F2_PROMPT_VERSION,
                        "excerpt_hash": _h.sha256(excerpt.encode()).hexdigest()[:16],
                        "verdict": verdict,
                        "reason": reason,
                        "created_at": library._now(),
                    }
                )
                new_props.append(prow)
                proposals[pid] = prow
                per_model[m] = (verdict, reason)
            if degraded or len(per_model) < len(models):
                continue  # row stays in the pool for the next run
            verdicts = {v for v, _ in per_model.values()}
            if len(verdicts) == 1 and verdicts <= {"correct", "wrong"}:
                agreed.append((r, next(iter(verdicts)), per_model))
            elif len(verdicts) == 1:
                counters["undecided_agree"] += 1
                human.append((r, per_model))
            else:
                counters["disagreements"] += 1
                human.append((r, per_model))
    for r, verdict, per_model in agreed:
        key = _row_key(r)
        seq = seq_base.get(key, 0) + 1
        seq_base[key] = seq
        note = "triage-agree " + " ".join(f"{m}:{per_model[m][0]}" for m in models)
        new_reviews.append(
            {
                "review_id": f"{key}-v{seq}",
                "candidate_id": key,
                "rule_version": RULE_VERSION_F2,
                "verdict": verdict,
                "reviewer": "draft-agree",
                "note": note[:300],
                "reviewed_at": library._now(),
            }
        )
        counters["agree_recorded"] += 1
    if new_props:
        store.append_rows(
            "review_proposals", new_props, list(_schema.REVIEW_PROPOSAL_COLS), con=con
        )
    if new_reviews:
        store.append_rows(
            "candidate_reviews", new_reviews, list(_schema.CANDIDATE_REVIEW_COLS), con=con
        )
    # The judging surface ruling (operator, 2026-09-09): triage NEVER prints
    # raw human-queue rows; the surface is triage-clusters, always.
    if human:
        print(
            f"TRIAGE-HUMAN {len(human)} rows queued -> run: priorities triage-clusters "
            "(the judging surface; raw rows never print here)"
        )
    else:
        print("TRIAGE-HUMAN 0 rows queued")
    runr = results.start(
        "priorities-triage", "priorities triage",
        ["stated_priorities", "review_proposals", "candidate_reviews"],
        {
            "models": ",".join(models), "prompt_version": F2_PROMPT_VERSION,
            "rule_version": RULE_VERSION_F2, "seed": seed, "cap": cap, "max_tokens": max_tokens,
        },
    )
    for k2, v in counters.items():
        runr.metric("_", k2, v)
    run_id = results.finish(
        runr, note="draft-agree never counts in operator precision; operator override wins by reviewed_at"
    )
    if _counters is not None:
        _counters.update(counters)
    print("TRIAGE " + " ".join(f"{k} {v}" for k, v in counters.items()))
    log.info(f"run {run_id} recorded")
    return 0


TRIAGE_MIN_CLUSTER = 3  # structural: a cluster ruling requires 3 verbatim examples (operator ruling 2026-09-09)
TRIAGE_RESIDUAL_CAP = 10  # operator ruling 2026-09-09, "The judging surface"
TRIAGE_AUDIT_CAP = 10  # operator ruling 2026-09-09, "The judging surface"

# Sentence-level validation vocabularies (operator ruling 2026-09-09, cluster
# cross-check: membership is validated against the SENTENCE, never the dissent
# reason alone). Deterministic keyword classes; provenance: the ruling plus
# the named precedents (Galera: named indication beats modality flavor;
# uniQure: dual-coverage with pipeline payload is correct; Fortress: stated
# acquisition intent is a genuine priority; Viatris: settled stays settled).
_CHANNEL_TERMS = (
    "market access", "salesforce", "sales force", "distribution", "payer",
    "commercial infrastructure", "commercial capabilities", "channel",
    "healthcare gateway", "commercial reach", "suitable infrastructure",
    # p2 additions from the banked specimens (decision record, appends
    # through 2026-09-10): bluebird delivery network / value-based payment,
    # Travere commercial execution, Phexxi telehealth channel.
    "delivery network", "value-based payment", "commercial execution",
    "telehealth",
)
_IP_TERMS = ("patent", "intellectual property", "proprietary position")
_BOILER_TERMS = (
    "insurance", "no assurance", "may be unable", "cannot be certain",
    "if appropriate opportunities", "risk factor",
)
_ACQ_TERMS = ("acquire", "acquisition", "in-licens", "in licens", "license in")
_DISEASE_TERMS = (
    "cancer", "anticancer", "oncology", "tumor", "antitumor", "myeloma",
    "leukemia", "lymphoma",
    "autoimmune", "inflammatory", "fibrosis", "cns", "neurolog", "rare disease",
    "orphan", "diabetes", "cardio", "hepat", "renal", "ophthalm", "dermat",
    "infectious", "virus", "infection", "antiviral", "respiratory",
)
_PIPELINE_TERMS = ("pipeline", "clinical", "candidate", "pivotal", "trial")
_GARBLED_TERMS = ("\u2022", " \u00f2 ")  # bullet / mojibake chars: truncation debris, never a stated priority
# Negation-clip pattern (operator ruling 2026-09-09, S1e6a836 Opus-class):
# a slicer clip inverted "unless we acquire..." into "we plan to acquire, the
# infrastructure|capability ..." — routed garbled, locked as a verbatim test.
_GARBLED_PATTERNS = (re.compile(r"acquire, the (infrastructure|capabilit)", re.IGNORECASE),)
# Precedent families promoted to deterministic rules (operator run-to-completion
# ruling 2026-09-09; specimens from that day's residual rulings, keys in tests):
_COMPETITOR_TERMS = ("competitor", "competing product", "more effective therapeutic product", "targeted by us")
_GOING_CONCERN_TERMS = ("dependent on additional public or private financings",)
_OUTLICENSE_TERMS = ("out-licens", "commercialization rights to", "to resellers")
_OUTLICENSE_RX = re.compile(r"licens\w*\s+[\w\s,\u00ae-]{0,50}?\bto\s+(such\s+)?(compan|partner|reseller)", re.IGNORECASE)
_VET_TERMS = ("veterinar", "pet parent", " pets ")
_TECH_TERMS = (
    "gene therap", "cell therap", "genome editing", "crispr", "lentiviral",
    "antibody", "peptide", "mrna", "sirna", "rnai", " rna", "oligonucleotide",
    "nanoparticle", "artificial intelligence", "ai-", "data-driven",
    "machine learning", "cannabinoid", "immunotherapy", "radioisotope",
    "microdose", "precision medicine", "platform", "modality",
    "small molecule", "novel class", "\u00ae", "\u00ab",
)


def _hit(s: str, terms: tuple[str, ...]) -> bool:
    """Vocabulary match that closes the substring-trap class for good
    (viral-in-lentiviral, rna-in-alternatives, trial-in-industrial,
    payer-in-taxpayer — 2026-09-09): single-word alphabetic terms must not
    be preceded by a letter (suffixes like plurals still match); phrases
    and symbol terms match as plain substrings."""
    for t in terms:
        if " " not in t and t.isalpha():
            if re.search(r"(?<![a-z])" + re.escape(t), s):
                return True
        elif t in s:
            return True
    return False


def _validate_cluster(sentence: str, stamp: str) -> tuple[str, str, str] | None:
    """(cluster_suffix, verdict, relabel) from the sentence itself, or None
    for residual. Ordered first-hit rules; a row joins a cluster only when
    the sentence carries the evidence the ruling depends on. The four
    2026-09-09 override classes (no-modality generic, named-modality trade
    name, dual-with-pipeline, garbled truncation) are locked as verbatim
    tests."""
    s = sentence.lower()
    if any(t in sentence for t in _GARBLED_TERMS) or any(
        rx.search(sentence) for rx in _GARBLED_PATTERNS
    ):
        return ("garbled", "wrong", "")
    # competitor-risk BEFORE acq/disease: its specimens carry "acquiring" and
    # disease names (S6990 precedent, S092bfb ruling)
    if _hit(s, _COMPETITOR_TERMS):
        return ("competitor-risk", "wrong", "")
    # going-concern financing family (S3b66/S511f/S6fbb rulings)
    if any(t in s for t in _GOING_CONCERN_TERMS):
        return ("going-concern", "wrong", "")
    # out-licensing (Arbutus) BEFORE acq: license-OUT direction is wrong,
    # development partnering (Nomad) is not detected here and stays residual
    if any(t in s for t in _OUTLICENSE_TERMS) or _OUTLICENSE_RX.search(sentence):
        return ("out-licensing", "wrong", "")
    if _hit(s, _CHANNEL_TERMS):
        # p2 piece 1 (2026-09-10): commercial_infrastructure is live, so the
        # commercial-hold-p2 unsure hold is SUPERSEDED (operator ruling
        # 2026-09-08 + go 2026-09-10). Channel payload under the new stamp is
        # correct; under any other stamp it relabels, repair-not-delete —
        # the payload-beats-stamp standing rule extended to the ninth
        # category. Out-licensing and going-concern branches stay ORDERED
        # ABOVE this one (amendment 2): their specimens never reach here.
        if stamp == "commercial_infrastructure":
            return ("commercial-correct", "correct", "")
        return ("commercial-relabel", "wrong", "commercial_infrastructure")
    if _hit(s, _IP_TERMS):
        return ("ip-protection", "wrong", "")
    if _hit(s, _BOILER_TERMS):
        return ("boilerplate", "wrong", "")
    # veterinary-generic family (S1326/S5135/S6bc5 rulings), any stamp
    if any(t in s for t in _VET_TERMS):
        return ("veterinary-generic", "wrong", "")
    if stamp == "pipeline_gap" and _hit(s, _ACQ_TERMS):
        return ("acquisition-correct", "correct", "")
    if stamp == "pipeline_gap" and _hit(s, _PIPELINE_TERMS):
        return ("pipeline-correct", "correct", "")  # uniQure precedent: pipeline payload wins
    if _hit(s, _DISEASE_TERMS):
        if stamp == "therapeutic_area":
            return ("named-indication-correct", "correct", "")
        if stamp == "platform" and not _hit(s, _PIPELINE_TERMS):
            # payload beats stamp flavor (operator standing rule 2026-09-09,
            # symmetric; specimens S13ebad/S3d729): named indication under a
            # platform stamp relabels to therapeutic_area, repair-not-delete
            return ("indication-relabel", "wrong", "therapeutic_area")
        return None
    if stamp == "platform" and _hit(s, _PIPELINE_TERMS):
        # the same standing rule, other direction (specimens S31fc9/S4651a):
        # pipeline payload under a platform stamp relabels to pipeline_gap
        return ("pipeline-relabel", "wrong", "pipeline_gap")
    if stamp != "platform" and _hit(s, _TECH_TERMS):
        return ("platform", "wrong", "platform")
    if stamp == "therapeutic_area":
        return ("generic", "wrong", "")
    return None


def _settled_keys(rows: dict[str, dict], reviews: list[dict]) -> set[str]:
    """Keys of rows created by an OPERATOR relabel: settled stays settled
    (operator ruling 2026-09-09; the Viatris row proved the gap). A relabel
    re-keys the row, so the verdict sits under the OLD key; recover the link
    by hashing each current row's (entity, date) against every other
    category and matching relabel notes."""
    import hashlib as _h

    from biointel import schema as _schema

    relabels: dict[str, str] = {}
    for v in reviews:
        if str(v.get("rule_version")) != RULE_VERSION_F2:
            continue
        if str(v.get("reviewer")) not in ("operator", "operator-pattern"):
            continue
        m = re.match(r"(?:cluster:[^;]+;)?relabel:([a-z_]+);", str(v.get("note") or ""))
        if m:
            relabels[str(v["candidate_id"])] = m.group(1)
    settled: set[str] = set()
    if not relabels:
        return settled
    for key, r in rows.items():
        ent, day = str(r["entity_key"]), str(r["stated_at"])[:10]
        for old_cat in _schema.PRIORITY_CATEGORIES:
            if old_cat == str(r["category"]):
                continue
            oldk = "S" + _h.sha256(f"{ent}|{day}|{old_cat}".encode()).hexdigest()[:16]
            if relabels.get(oldk) == str(r["category"]):
                settled.add(key)
                break
    return settled


def triage_clusters(con=None, auto: bool = False) -> int:
    """The judging surface (operator ruling 2026-09-09, BINDING): the human
    queue is never presented as bulk. This command makes no API calls; it
    reads the stored two-model proposals for every unjudged row, VALIDATES
    each disagreement row against its own sentence (_validate_cluster —
    dissent reasons never decide membership), and prints: CLUSTER blocks
    (id, count, proposed one-line ruling, exactly 3 verbatim examples) —
    each answered with ONE decision via `priorities judge-batch <csv>
    --pattern <id>` (prefilled CSVs in exports; edit to modify) — then a
    RESIDUAL capped at 10, then an AUDIT slice capped at 10, then the
    carried count. Rows settled by an operator relabel are excluded
    entirely. The caps are code, not discretion."""
    import csv as _csv
    import random as _r

    from biointel import config as _config

    con = con or store.connect()
    models = list(getattr(_config, "TRIAGE_MODELS", ("claude-sonnet-5", "claude-haiku-4-5")))
    props: dict[str, dict[str, tuple[str, str]]] = {}
    for p in (
        store.read_table("review_proposals", con=con)
        if store.has_table("review_proposals", con)
        else []
    ):
        if str(p.get("prompt_version")) != F2_PROMPT_VERSION:
            continue
        props.setdefault(str(p["queue_id"]), {})[str(p["model_id"])] = (
            str(p["verdict"]), str(p.get("reason") or "")
        )
    reviews = (
        store.read_table("candidate_reviews", con=con)
        if store.has_table("candidate_reviews", con)
        else []
    )
    judged = {
        str(r["candidate_id"]) for r in reviews
        if str(r.get("rule_version")) == RULE_VERSION_F2
        and str(r.get("reviewer")) in ("operator", "operator-pattern", "draft-agree")
    }
    agreed_keys = [
        str(r["candidate_id"]) for r in reviews
        if str(r.get("rule_version")) == RULE_VERSION_F2
        and str(r.get("reviewer")) == "draft-agree"
    ]
    rows = {_row_key(r): r for r in store.read_table("stated_priorities", con=con)}
    settled = _settled_keys(rows, reviews)
    clusters: dict[str, list[dict]] = {}
    proposed: dict[str, tuple[str, str]] = {}
    residual: list[tuple[dict, dict]] = []
    for key, r in sorted(rows.items()):
        if key in judged or key in settled:
            continue
        pm = props.get(key, {})
        if len(pm) < len(models):
            continue  # not fully proposed on yet; a later triage run covers it
        verdicts = {pm[m][0] for m in models}
        if len(verdicts) == 1 and verdicts <= {"correct", "wrong"}:
            continue  # agreed rows are the triage command's business
        hit = _validate_cluster(str(r["statement"]), str(r["category"]))
        if hit is None:
            residual.append((r, pm))
            continue
        cid = f"{r['category']}--{hit[0]}"
        clusters.setdefault(cid, []).append(r)
        proposed[cid] = (hit[1], hit[2])
    if auto:
        # run-to-completion ruling 2026-09-09: standing rulings auto-apply,
        # reviewer="operator-pattern", note citing the ruling; holds included
        applied = 0
        for cid, rs in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
            v, rl = proposed[cid]
            suffix = cid.split("--", 1)[1]
            cite = STANDING_RULINGS.get(suffix, "standing ruling")
            for r in rs:
                rcj = judge(
                    _row_key(r), v,
                    note=f"cluster:{cid};standing:{cite}",
                    relabel=rl, reviewer="operator-pattern", con=con,
                )
                if rcj == 0:
                    applied += 1
        print(f"AUTO-APPLIED {applied} rows across {len(clusters)} standing clusters; residual carried {len(residual)}")
        return applied
    # clusters below the example floor are residual, never padded rulings
    # (print-surface rule only; auto mode above applies standing rulings at any size)
    for cid in [c for c, rs in clusters.items() if len(rs) < TRIAGE_MIN_CLUSTER]:
        for r in clusters.pop(cid):
            residual.append((r, props.get(_row_key(r), {})))
    csv_paths: list[str] = []
    for cid, rs in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        v, rl = proposed[cid]
        ruling = f"{v}" + (f" --relabel {rl}" if rl else "")
        print(f"CLUSTER {cid} | {len(rs)} rows | proposed: {ruling} | approve: priorities judge-batch <csv> --pattern {cid}")
        for r in rs[:TRIAGE_MIN_CLUSTER]:
            print(f"  VERBATIM: {r['statement']}")
        pth = _config.EXPORTS / f"cluster_{cid}.csv"
        _config.EXPORTS.mkdir(parents=True, exist_ok=True)
        with open(pth, "w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow(["key", "verdict", "relabel", "note", "statement"])
            for r in rs:
                w.writerow([_row_key(r), v, rl, "", r["statement"]])
        csv_paths.append(str(pth))
    shown = residual[:TRIAGE_RESIDUAL_CAP]
    print(f"RESIDUAL {len(shown)} rows (fit no cluster):")
    for r, pm in shown:
        vv = " | ".join(f"{m}: {pm[m][0]} - {pm[m][1]}" for m in models if m in pm)
        print(f"{_row_key(r)} | {r['entity_key']} {str(r['stated_at'])[:10]} {r['category']} | {vv}")
        print(f"  VERBATIM: {r['statement']}")
    print(f"RESIDUAL-CARRIED {max(0, len(residual) - TRIAGE_RESIDUAL_CAP)} rows to the next run")
    seed = _dt_seed()
    _r.seed(seed)
    pool = [rows[k] for k in agreed_keys if k in rows]
    audit = _r.sample(pool, min(TRIAGE_AUDIT_CAP, len(pool))) if pool else []
    print(f"AUDIT {len(audit)} of {len(agreed_keys)} machine-agreed (seed {seed}):")
    for r in audit:
        pm = props.get(_row_key(r), {})
        vv = " | ".join(f"{m}: {pm[m][0]}" for m in models if m in pm)
        print(f"{_row_key(r)} | {r['entity_key']} {str(r['stated_at'])[:10]} {r['category']} | {vv}")
        print(f"  VERBATIM: {r['statement']}")
    runr = results.start(
        "priorities-triage-clusters", "priorities triage-clusters",
        ["stated_priorities", "review_proposals", "candidate_reviews"],
        {"rule_version": RULE_VERSION_F2, "seed": seed},
    )
    runr.metric("_", "clusters", len(clusters))
    runr.metric("_", "clustered_rows", sum(len(v) for v in clusters.values()))
    runr.metric("_", "residual", len(residual))
    runr.metric("_", "residual_shown", len(shown))
    runr.metric("_", "audit_shown", len(audit))
    runr.metric("_", "settled_excluded", len(settled))
    for pth in csv_paths:
        runr.artefact(pth)
    run_id = results.finish(runr, note="the judging surface: sentence-validated clusters + residual<=10 + audit<=10")
    print(
        "TRIAGE-CLUSTERS "
        + f"clusters {len(clusters)} clustered_rows {sum(len(v) for v in clusters.values())} "
        + f"residual {len(residual)} shown {len(shown)} audit {len(audit)} settled_excluded {len(settled)}"
    )
    log.info(f"run {run_id} recorded")
    return 0


# Every validator suffix maps to an operator standing ruling (run-to-completion
# ruling 2026-09-09): auto-apply cites the ruling; residual = no precedent.
STANDING_RULINGS: dict[str, str] = {
    "generic": "generic-mission wrong (2026-09-09)",
    "named-indication-correct": "Galera: named indication correct",
    "platform": "modality-no-disease relabel platform",
    "indication-relabel": "payload beats stamp flavor (Galera mirror)",
    "pipeline-relabel": "payload beats stamp flavor (pipeline)",
    "ip-protection": "IP-protection wrong (Alaunos family)",
    "boilerplate": "boilerplate/risk-factor wrong",
    "garbled": "truncation debris wrong",
    # superseded at p2 piece 1 (2026-09-10): kept so recorded verdicts citing
    # the hold keep a live citation; the validator no longer emits it.
    "commercial-hold-p2": "commercial-infrastructure hold (unsure; superseded p2)",
    "commercial-correct": "commercial_infrastructure payload correct (ruling 2026-09-08, live p2)",
    "commercial-relabel": "payload beats stamp flavor (commercial_infrastructure, ruling 2026-09-08)",
    "acquisition-correct": "Fortress/Abpro: acquisition intent correct",
    "pipeline-correct": "uniQure: pipeline payload correct",
    "competitor-risk": "S092bfb: competitor-risk wrong",
    "going-concern": "S3b66 family: going-concern wrong",
    "out-licensing": "Arbutus: license-out wrong",
    "veterinary-generic": "S1326 family: veterinary-generic wrong",
}


def triage_complete(con=None) -> int:
    """Run-to-completion (operator ruling 2026-09-09): sweeps run back-to-back
    until the pool is empty. Each cycle: one triage pass (both models, cached
    proposals free), then every validated cluster auto-applies as
    reviewer="operator-pattern" citing its standing ruling; residual rows
    (no precedent) accumulate across sweeps into ONE final surface, capped in
    print, full list exported. Prints the POOL-REMAINING gauge each pass."""
    con = con or store.connect()
    cycle = 0
    while True:
        cycle += 1
        counters: dict[str, int] = {}
        rc = triage(con=con, _counters=counters)
        if rc != 0:
            return rc
        applied = triage_clusters(con=con, auto=True)
        rows = store.read_table("stated_priorities", con=con)
        reviews = store.read_table("candidate_reviews", con=con)
        judged = {
            str(r["candidate_id"]) for r in reviews
            if str(r.get("rule_version")) == RULE_VERSION_F2
        }
        settled = _settled_keys({_row_key(r): r for r in rows}, reviews)
        remaining = sum(
            1 for r in rows
            if str(r.get("source_type")) in ("10k_strategy", "investor_day")
            and _row_key(r) not in judged and _row_key(r) not in settled
        )
        print(f"POOL-REMAINING {remaining} (cycle {cycle}, calls {counters.get('calls_made', 0)}, auto-applied {applied})")
        if counters.get("calls_made", 0) == 0 and applied == 0:
            break
    print("POOL EMPTY - run priorities triage-clusters for the accumulated final surface, then precision")
    return 0


def _doc_text_of(capr: dict) -> str | None:
    ext = "." + str(capr.get("ext") or "htm")
    try:
        return normalize_text(
            library.store_path(str(capr["capture_id"]), ext).read_text(
                encoding="utf-8", errors="replace"
            )
        )
    except OSError:
        return None


# ---------------------------------------------------------------- F2 judging interface: spreadsheet out, verdicts back (operator ruling 2026-09-08)
def worksheet(n: int = 60, tier: str | None = None, seed: int | None = None, con=None) -> int:
    """Write the blind sample as a CSV a human can actually judge in
    Excel: one row per item, the assist's draft verdict PRE-FILLED in the
    `verdict` column (blank where no proposal exists), its reason beside
    it, and the document URL. The human edits only `verdict` (and `note`
    if wanted), saves, and `priorities judge-batch` ingests the file."""
    import csv
    import random as _r

    con = con or store.connect()
    seed = seed if seed is not None else _dt_seed()
    rows = store.read_table("stated_priorities", con=con)
    names = {
        f"CIK:{int(str(c['CIK']))}": str(c["Name"])
        for c in store.read_table("companies", con=con)
        if str(c.get("CIK") or "").strip().isdigit()
    }
    url_by_doc: dict[str, str] = {}
    for ref in store.read_table("references", con=con):
        if f"captured by {TOOL}" in str(ref.get("note") or ""):
            url_by_doc[str(ref["ref_id"])] = str(ref.get("url") or "")
    cap_ref = {
        str(c["capture_id"]): str(c["ref_id"])
        for c in store.read_table("captures", con=con)
        if str(c.get("status")) == "active"
    }
    proposals: dict[str, dict] = {}
    if store.has_table("review_proposals", con):
        for pr in store.read_table("review_proposals", con=con):
            if str(pr.get("prompt_version")) == F2_PROMPT_VERSION:
                proposals[str(pr["queue_id"])] = pr
    judged = {
        str(r["candidate_id"])
        for r in (
            store.read_table("candidate_reviews", con=con)
            if store.has_table("candidate_reviews", con)
            else []
        )
        if str(r.get("rule_version")) == RULE_VERSION_F2
    }
    out_path = config.EXPORTS / "priorities_worksheet.csv"
    config.EXPORTS.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            ["key", "verdict", "ai_reason", "company", "date", "category",
             "sentence", "doc_url", "note"]
        )
        for t in [tier] if tier else ["10k_strategy", "investor_day"]:
            pool = [
                r for r in rows
                if str(r.get("source_type")) == t and _row_key(r) not in judged
            ]
            _r.seed(seed)
            _r.shuffle(pool)
            for r in pool[:n]:
                key = _row_key(r)
                pr = proposals.get(key)
                w.writerow([
                    key,
                    str(pr["verdict"]) if pr else "",
                    str(pr["reason"])[:200] if pr else "",
                    names.get(str(r["entity_key"]), str(r["entity_key"])),
                    str(r["stated_at"])[:10],
                    str(r["category"]),
                    str(r["statement"])[:400],
                    url_by_doc.get(cap_ref.get(str(r["doc_id"]), ""), ""),
                    "",
                ])
                written += 1
    print(
        f"WORKSHEET-CSV {written} rows (seed {seed}) -> {out_path}\n"
        "Open in Excel, correct the `verdict` column (correct|wrong|unsure), save, then run: "
        "priorities judge-batch"
    )
    return 0


def judge_batch(path: str | None = None, pattern: str | None = None, con=None) -> int:
    """Ingest the edited worksheet CSV: every row whose `verdict` column
    holds correct|wrong|unsure is recorded through the same judge() path
    (wrong retires the row immediately); blanks and unknown values are
    skipped and counted; already-judged keys are skipped. With --pattern
    CLUSTER_ID (operator ruling 2026-09-09, "The judging surface"), every
    verdict is a PATTERN ruling: reviewer="operator-pattern" and the note
    carries the cluster id, so provenance and precision keep pattern
    verdicts separate from row-by-row ones."""
    import csv

    con = con or store.connect()
    reviewer = "operator-pattern" if pattern else "operator"
    p = Path(path) if path else (config.EXPORTS / "priorities_worksheet.csv")
    if not p.exists():
        print(f"no worksheet at {p}")
        return 1
    judged_already = {
        str(r["candidate_id"])
        for r in (
            store.read_table("candidate_reviews", con=con)
            if store.has_table("candidate_reviews", con)
            else []
        )
        if str(r.get("rule_version")) == RULE_VERSION_F2
    }
    counters = {"recorded": 0, "retired": 0, "blank": 0, "invalid": 0, "already": 0, "unknown_key": 0}
    with open(p, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = str(row.get("key") or "").strip()
            v = str(row.get("verdict") or "").strip().lower()
            if not key:
                continue
            if not v:
                counters["blank"] += 1
                continue
            if v not in ("correct", "wrong", "unsure"):
                counters["invalid"] += 1
                continue
            if key in judged_already:
                counters["already"] += 1
                continue
            rc = judge(
                key, v,
                note=((f"cluster:{pattern};" if pattern else "") + str(row.get("note") or ""))[:300],
                relabel=str(row.get("relabel") or "").strip().lower(),
                reviewer=reviewer,
                con=con,
            )
            if rc != 0:
                counters["unknown_key"] += 1
                continue
            judged_already.add(key)
            counters["recorded"] += 1
            if v == "wrong":
                if str(row.get("relabel") or "").strip():
                    counters["relabeled"] = counters.get("relabeled", 0) + 1
                else:
                    counters["retired"] += 1
    print("JUDGE-BATCH " + " ".join(f"{k} {v}" for k, v in counters.items()))
    return 0


def cli(argv: list[str]) -> int:
    if argv and argv[0] == "probe":
        return probe()
    if argv and argv[0] == "probe-calls":
        return probe_calls()
    if argv and argv[0] == "sample-misses":
        nn = next((int(a) for a in argv[1:] if a.isdigit()), 12)
        return sample_misses(nn)
    if argv and argv[0] == "reextract":
        return reextract()
    if argv and argv[0] == "write":
        return write()
    if argv and argv[0] == "sample":
        nn = next((int(a) for a in argv[1:] if a.isdigit()), 60)
        tt = argv[argv.index("--tier") + 1] if "--tier" in argv else None
        ss = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else None
        return sample(nn, tier=tt, seed=ss)
    if argv and argv[0] == "assist":
        nn = next((int(a) for a in argv[1:] if a.isdigit()), 60)
        tt = argv[argv.index("--tier") + 1] if "--tier" in argv else None
        ss = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else None
        return assist_sample(nn, tier=tt, seed=ss)
    if argv and argv[0] == "triage":
        tt = argv[argv.index("--tier") + 1] if "--tier" in argv else None
        ss = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else None
        return triage(tier=tt, seed=ss)
    if argv and argv[0] == "judge" and len(argv) >= 3:
        nt = argv[argv.index("--note") + 1] if "--note" in argv else ""
        rl = argv[argv.index("--relabel") + 1] if "--relabel" in argv else ""
        return judge(argv[1], argv[2], note=nt, relabel=rl)
    if argv and argv[0] == "precision":
        return precision()
    if argv and argv[0] == "worksheet":
        nn = next((int(a) for a in argv[1:] if a.isdigit()), 60)
        tt = argv[argv.index("--tier") + 1] if "--tier" in argv else None
        ss = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else None
        return worksheet(nn, tier=tt, seed=ss)
    if argv and argv[0] == "record-restore" and len(argv) >= 3:
        nt = argv[argv.index("--note") + 1] if "--note" in argv else ""
        return record_restore(argv[1], argv[2], note=nt)
    if argv and argv[0] == "triage-clusters":
        return triage_clusters()
    if argv and argv[0] == "triage-complete":
        return triage_complete()
    if argv and argv[0] == "judge-batch":
        pp = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else None
        pat = argv[argv.index("--pattern") + 1] if "--pattern" in argv else None
        return judge_batch(pp, pattern=pat)
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
    print("usage: priorities probe|probe-calls|collect [...]|sample-misses [N]|reextract")
    return 1
