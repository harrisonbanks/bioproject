# C:\Users\JB\Documents\dev\bioindustry\src\biointel\analyser.py
"""Gate L3: the deal analyser.

For a deal (an `ma_events` row with a deal_id), the analyser
  1. COLLECTS the deal's paper trail: EFTS full-text queries scoped to each
     party's CIK around the announcement window (merger vocabulary), every
     hit document captured into the library (rule 4.20);
  2. EXTRACTS span-grounded proposals over the normalized captures —
     deal_terms (price per share, exchange ratio, termination fee, outside
     date, consideration form), deal_timeline (agreement date, expected
     close), deal_rationale (stated-rationale sentences) — each proposal
     carrying capture doc_id + the verbatim span, exactly the seed
     dossier's grounding contract (dossier.span_pattern verifies);
  3. QUEUES proposals for review (candidate_reviews reused; ids "A<hash>",
     rule version L3-a1) and prints them; `dossier-analyse ... --consume`
     writes verified-against-capture proposals into the dossier tables,
     never overwriting a seed row (seed wins on key collision);
  4. COMPARES its own proposals field by field against the hand-built seed
     for TEM-PSNL-20260720 — the yardstick: agreement recorded per field.

Design lineage: 1.5b's offset grounding; dossier.py's propose->verify->
consume; the label-QA human spot-check via judge/precision.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, timedelta

from biointel import results, store
from biointel.dossier import DEAL_ID as SEED_DEAL_ID
from biointel.dossier import SEED, normalize, span_pattern
from biointel.efts import _range_for as range_for
from biointel.efts import capture_document, hits_of, search
from biointel.pipeline import read_companies

log = logging.getLogger(__name__)

RULE_VERSION = "L3-a2"
DEAL_FORMS = "8-K,425,DEFM14A,PREM14A,S-4,6-K,10-Q,10-K"
QUERY = '"Agreement and Plan of Merger" OR "merger agreement"'

_MONEY = r"\$\s*([\d,]+(?:\.\d+)?)"
_DATE = r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})"
_PAR_VALUE = re.compile(r"par value", re.I)
_RULES = (
    (
        "deal_terms",
        "announce_date",
        re.compile(
            r"on\s+" + _DATE + r"\s*,.{0,120}?entered into an agreement and plan of merger", re.I
        ),
    ),
    (
        "deal_terms",
        "prior_stake_pct",
        re.compile(r"held (?:approximately )?([\d.]+)\s*%\s+of", re.I),
    ),
    (
        "deal_terms",
        "enterprise_value_usd",
        re.compile(
            r"enterprise value of (?:approximately )?" + _MONEY + r"\s*(billion|million)", re.I
        ),
    ),
    (
        "deal_terms",
        "price_per_share_usd",
        re.compile(_MONEY + r"\s+(?:per share|in cash[^.]{0,40}per share|for each share)", re.I),
    ),
    (
        "deal_terms",
        "exchange_ratio_cap",
        re.compile(r"(?:exchange ratio[^.]{0,80}?|)(0\.\d{3,4})\s*(?:shares?|of a share)", re.I),
    ),
    (
        "deal_terms",
        "termination_fee_usd",
        re.compile(r"termination fee[^.]{0,60}?" + _MONEY + r"\s*(million|billion)?", re.I),
    ),
    (
        "deal_terms",
        "outside_date",
        re.compile(r"(?:outside date|end date)[^.]{0,120}?" + _DATE, re.I),
    ),
    (
        "deal_timeline",
        "merger_agreement",
        re.compile(r"agreement and plan of merger.{0,120}?dated as of\s+" + _DATE, re.I),
    ),
    (
        "deal_timeline",
        "expected_close",
        re.compile(
            r"(?:expected|anticipated) to (?:close|be completed)[^.]{0,80}?(?:in|by)\s+"
            r"((?:the\s+)?(?:first|second|third|fourth)\s+(?:quarter|half)\s+of\s+\d{4}|"
            + _DATE
            + r"|\d{4})",
            re.I,
        ),
    ),
)
_RATIONALE = re.compile(
    r"[^.]{0,240}\b(strategic rationale|complementary|combination (?:will|is expected)|"
    r"accelerat\w+ (?:our|the)|expands? (?:our|the) (?:reach|platform|capabilit))\b[^.]{0,240}\.",
    re.I,
)
_CONSIDERATION = (
    ("all cash", re.compile(r"all[- ]cash (?:transaction|offer|merger)", re.I)),
    ("all stock", re.compile(r"all[- ]stock (?:transaction|merger)", re.I)),
    ("stock with cash election", re.compile(r"cash election", re.I)),
)


def _deal_row(deal_id: str) -> dict | None:
    for r in store.read_table("ma_events", con=store.connect()):
        if r.get("deal_id") == deal_id:
            return r
    return None


def collect(deal_id: str, window_before: int = 30, window_after: int = 150) -> dict:
    """The deal's paper trail into the library: per-party EFTS full-text
    queries over the announcement window; every hit captured once."""
    ev = _deal_row(deal_id)
    if not ev:
        return {"status": "no_such_deal", "docs": 0}
    con = store.connect()
    comps = {str(c["IID"]): c for c in read_companies()}
    parties = [comps.get(str(ev.get("FilerIID"))), comps.get(str(ev.get("CounterpartyIID")))]
    ann = date.fromisoformat(str(ev["AnnounceDate"])[:10])
    start = (ann - timedelta(days=window_before)).isoformat()
    end = (ann + timedelta(days=window_after)).isoformat()
    run_ = results.start(
        "dossier",
        f"dossier-analyse collect {deal_id}",
        ["references", "captures"],
        {"deal_id": deal_id, "window": f"{start}..{end}", "rule_version": RULE_VERSION},
    )
    stats = {"queries": 0, "hits": 0, "docs": 0, "fetch_failed": 0}
    seen = set()
    for p in parties:
        if not p or not (p.get("CIK") or "").strip():
            continue
        payload = search(QUERY, DEAL_FORMS, start, end, cik=p["CIK"])
        stats["queries"] += 1
        for h in hits_of(payload):
            key = (h["adsh"], h["doc"])
            if key in seen:
                continue
            seen.add(key)
            stats["hits"] += 1
            got = capture_document(h, con)
            if got:
                stats["docs"] += 1
            else:
                stats["fetch_failed"] += 1
    for k, v in stats.items():
        run_.metric("_", k, v)
    run_id = results.finish(run_)
    print(
        f"dossier-analyse collect {deal_id}: {stats['queries']} queries, {stats['hits']} documents, "
        f"{stats['docs']} captured ({stats['fetch_failed']} fetch failures) over {start}..{end} "
        f"(run {run_id} recorded)"
    )
    return {"status": "ok", **stats, "run_id": run_id}


def _deal_captures(deal_id: str, con) -> list[tuple[dict, str]]:
    """(capture, normalized text) for the deal's parties only: references
    linked to either party's CIK (reference_links, or the capture note's
    cik=), text extensions, within the announcement lookback. Each file is
    read and normalized exactly once; progress printed every 25."""
    from biointel import config

    ev = _deal_row(deal_id)
    if not ev:
        return []
    comps = {str(c["IID"]): c for c in read_companies()}
    party_ciks = set()
    for iid in (str(ev.get("FilerIID")), str(ev.get("CounterpartyIID"))):
        c = comps.get(iid)
        if c and (c.get("CIK") or "").strip():
            k = str(c["CIK"]).strip()
            party_ciks.update({k, k.lstrip("0"), k.zfill(10)})
    ann = str(ev["AnnounceDate"])[:10]
    lo = (date.fromisoformat(ann) - timedelta(days=1100)).isoformat()  # includes history docs
    ref_cik = {}
    if store.has_table("reference_links", con):
        for lk in store.read_table("reference_links", con=con):
            if lk["key_type"] == "CIK":
                ref_cik.setdefault(lk["ref_id"], set()).add(str(lk["entity_key"]).strip())
    refs = {}
    for r in store.read_table("references", con=con):
        if r["status"] != "active" or not r.get("sec_accession"):
            continue
        note = r.get("note") or ""
        note_cik = next((x[4:].strip() for x in note.split(";") if x.startswith("cik=")), "")
        ciks = ref_cik.get(r["ref_id"], set()) | (
            {note_cik, note_cik.lstrip("0")} if note_cik else set()
        )
        if ciks & party_ciks and (r.get("published_at") or "") >= lo:
            refs[r["ref_id"]] = r
    out, n = [], 0
    for c in store.read_table("captures", con=con):
        if c["ref_id"] not in refs or c["status"] != "active":
            continue
        if c["ext"].lower().lstrip(".") not in ("htm", "html", "txt"):
            continue
        path = config.DATA / c["path"]
        if not path.exists():
            continue
        out.append((c, normalize(path.read_text(encoding="utf-8", errors="replace"))))
        n += 1
        if n % 25 == 0:
            print(f"  ... {n} party captures normalized")
    return out


def propose(deal_id: str) -> tuple[list[dict], dict[str, str]]:
    """Span-grounded proposals from the deal's captures, plus the normalized
    text per capture id (read once; span verification reuses it). Every
    proposal: table, row fields, doc_id, verbatim span, char offset, id."""
    con = store.connect()
    caps = _deal_captures(deal_id, con)
    texts = {c["capture_id"]: t for c, t in caps}
    props: dict[tuple, dict] = {}

    def add(table: str, fields: dict, cap: dict, span: str, pos: int):
        if table == "deal_rationale":
            key = (table, re.sub(r"\W+", "", fields["statement"].casefold()))
        else:
            key = (table, tuple(sorted(fields.items())))
        if key in props:
            return
        pid = (
            "A"
            + hashlib.sha256(
                f"{deal_id}|{table}|{sorted(fields.items())}|{RULE_VERSION}".encode()
            ).hexdigest()[:16]
        )
        props[key] = {
            "proposal_id": pid,
            "deal_id": deal_id,
            "table": table,
            "fields": fields,
            "doc_id": cap["capture_id"],
            "span": span,
            "pos": pos,
        }

    for cap, text in caps:
        for table, field, rx in _RULES:
            for m in list(rx.finditer(text))[
                :4
            ]:  # every statement, bounded; add() dedups, conflicts held
                raw = m.group(1)
                if field == "price_per_share_usd" and _PAR_VALUE.search(
                    text[max(0, m.start() - 40) : m.end() + 20]
                ):
                    continue  # "$0.0001 per share" par-value boilerplate
                if field == "announce_date":
                    rng = range_for(raw)
                    if rng:
                        add(
                            table,
                            {"deal_id": deal_id, "field": field, "value": rng[0]},
                            cap,
                            raw,
                            m.start(1),
                        )
                    continue
                if field == "enterprise_value_usd":
                    mult = {"million": 1e6, "billion": 1e9}[m.group(2).lower()]
                    add(
                        table,
                        {
                            "deal_id": deal_id,
                            "field": field,
                            "value": f"{float(raw.replace(',', '')) * mult:g}",
                        },
                        cap,
                        m.group(0)[:120],
                        m.start(),
                    )
                    continue
                if field == "outside_date" and re.search(
                    r"exten(?:d|sion)", text[max(0, m.start() - 120) : m.end() + 40], re.I
                ):
                    rng = range_for(raw)
                    if rng:
                        add(
                            table,
                            {"deal_id": deal_id, "field": "outside_date_extended", "value": rng[0]},
                            cap,
                            raw,
                            m.start(1),
                        )
                    continue
                if table == "deal_terms" and field == "price_per_share_usd":
                    add(
                        table,
                        {"deal_id": deal_id, "field": field, "value": raw.replace(",", "")},
                        cap,
                        m.group(0)[:120],
                        m.start(),
                    )
                elif table == "deal_terms" and field == "outside_date":
                    rng = range_for(raw)
                    if rng:
                        add(
                            table,
                            {"deal_id": deal_id, "field": field, "value": rng[0]},
                            cap,
                            raw,
                            m.start(1),
                        )
                elif table == "deal_terms" and field == "termination_fee_usd":
                    mult = {"million": 1e6, "billion": 1e9}.get((m.group(2) or "").lower(), 1)
                    add(
                        table,
                        {
                            "deal_id": deal_id,
                            "field": field,
                            "value": f"{float(raw.replace(',', '')) * mult:g}",
                        },
                        cap,
                        m.group(0)[:120],
                        m.start(),
                    )
                elif table == "deal_terms":
                    add(
                        table,
                        {"deal_id": deal_id, "field": field, "value": raw},
                        cap,
                        raw,
                        m.start(1),
                    )
                elif table == "deal_timeline" and field == "merger_agreement":
                    rng = range_for(m.group(1))
                    if rng:
                        add(
                            table,
                            {
                                "deal_id": deal_id,
                                "step_date": rng[0],
                                "step_type": "merger_agreement",
                                "description": "Agreement and Plan of Merger (analyser)",
                            },
                            cap,
                            m.group(1),
                            m.start(1),
                        )
                elif table == "deal_timeline" and field == "expected_close":
                    rng = range_for(re.sub(r"^the\s+", "", m.group(1), flags=re.I))
                    if rng:
                        add(
                            table,
                            {
                                "deal_id": deal_id,
                                "step_date": rng[0],
                                "step_type": "expected_close",
                                "description": f"Expected close: {m.group(1)} (analyser)",
                            },
                            cap,
                            m.group(1)[:80],
                            m.start(1),
                        )
        for name, rx in _CONSIDERATION:
            m = rx.search(text)
            if m:
                add(
                    "deal_terms",
                    {"deal_id": deal_id, "field": "consideration_form", "value": name},
                    cap,
                    m.group(0)[:80],
                    m.start(),
                )
                break
        taken = 0
        for m in _RATIONALE.finditer(text):
            if taken >= 3:
                break
            sent = m.group(0).strip()
            seq = 100 + len([p for p in props.values() if p["table"] == "deal_rationale"])
            before = len(props)
            add(
                "deal_rationale",
                {
                    "deal_id": deal_id,
                    "seq": str(seq),
                    "stated_by": "(filing)",
                    "statement": sent[:400],
                },
                cap,
                m.group(1),
                m.start(1),
            )
            taken += len(props) - before
    return list(props.values()), texts


def _span_ok(p: dict, texts: dict[str, str]) -> bool:
    text = texts.get(p["doc_id"], "")
    return bool(text and span_pattern(p["span"]).search(text))


def compare_with_seed(props: list[dict]) -> list[str]:
    """Field-by-field yardstick against the hand-built seed dossier."""
    lines = []
    seed_terms = {row["field"]: row["value"] for t, row, _a, _s in SEED if t == "deal_terms"}
    got_terms = {
        p["fields"]["field"]: p["fields"]["value"] for p in props if p["table"] == "deal_terms"
    }
    for f, want in sorted(seed_terms.items()):
        have = got_terms.get(f)
        if have is None:
            alt = {"consideration": "consideration_form"}.get(f)
            have = got_terms.get(alt) if alt else None
        verdict = (
            "MATCH"
            if (have is not None and str(have) in str(want)) or (have and str(want) in str(have))
            else ("FOUND-DIFF" if have is not None else "NOT-PROPOSED")
        )
        lines.append(f"  SEED {f:38s} want={want!r:45s} analyser={have!r} {verdict}")
    extra = sorted(set(got_terms) - set(seed_terms) - {"consideration_form", "termination_fee_usd"})
    for f in extra:
        lines.append(f"  EXTRA {f:37s} analyser={got_terms[f]!r} (no seed row)")
    return lines


def analyse(deal_id: str, consume: bool = False) -> int:
    con = store.connect()
    props, texts = propose(deal_id)
    run_ = results.start(
        "dossier",
        f"dossier-analyse {deal_id}",
        ["captures", "deal_terms", "deal_timeline", "deal_rationale"],
        {"deal_id": deal_id, "rule_version": RULE_VERSION, "consume": str(consume)},
    )
    ok = [p for p in props if _span_ok(p, texts)]
    by_key: dict[tuple, set] = {}
    for p in ok:
        if p["table"] == "deal_terms":
            by_key.setdefault((p["fields"]["field"],), set()).add(p["fields"]["value"])
    conflicted = {f for (f,), vals in by_key.items() if len(vals) > 1}
    print(
        f"dossier-analyse {deal_id} ({RULE_VERSION}): {len(props)} proposals, {len(ok)} span-verified; "
        f"judge each with: mine-pdufa judge <proposal_id> correct|wrong|unsure"
    )
    for p in ok:
        tag = (
            " CONFLICT" if p["table"] == "deal_terms" and p["fields"]["field"] in conflicted else ""
        )
        print(
            f"  [{p['proposal_id']}] {p['table']}  {p['fields']}  span={p['span'][:80]!r}  doc={p['doc_id'][:12]}{tag}"
        )
    if conflicted:
        print(f"  CONFLICTED fields held for judgement (not consumed): {sorted(conflicted)}")
    dropped = len(props) - len(ok)
    if dropped:
        print(f"  ({dropped} proposals failed span verification and are not shown)")
    if deal_id == SEED_DEAL_ID:
        print("YARDSTICK vs hand-built seed:")
        for line in compare_with_seed(ok):
            print(line)
    written = 0
    if consume:
        verdicts: dict[str, str] = {}
        if store.has_table("candidate_reviews", con):
            for r in store.read_table("candidate_reviews", con=con):
                if r.get("rule_version") == RULE_VERSION:
                    verdicts[r["candidate_id"]] = r["verdict"]
        correct_by_field: dict[str, list] = {}
        for q in ok:
            if q["table"] == "deal_terms" and verdicts.get(q["proposal_id"]) == "correct":
                correct_by_field.setdefault(q["fields"]["field"], []).append(q["fields"]["value"])
        for p in ok:
            table = p["table"]
            v = verdicts.get(p["proposal_id"], "")
            if v in ("wrong", "unsure"):
                continue  # human verdicts are binding
            if table == "deal_terms" and p["fields"]["field"] in conflicted:
                wins = set(correct_by_field.get(p["fields"]["field"], []))
                if not (v == "correct" and wins == {p["fields"]["value"]}):
                    continue  # a conflicted field consumes only its uniquely judged-correct value
            rows = store.read_table(table, con=con) if store.has_table(table, con) else []
            keycols = {
                "deal_terms": ("deal_id", "field"),
                "deal_timeline": ("deal_id", "step_date", "step_type"),
                "deal_rationale": ("deal_id", "seq"),
            }[table]
            key = tuple(str(p["fields"].get(k, "")) for k in keycols)
            if any(tuple(str(r.get(k, "")) for k in keycols) == key for r in rows):
                continue  # seed (or a prior consume) wins on key collision
            row = dict(p["fields"])
            row["doc_id"] = p["doc_id"]
            row["span"] = p["span"]
            cols = {
                t.path.split("/")[-1][:-4]: t.columns
                for t in __import__("biointel.schema", fromlist=["TABLES"]).TABLES
            }
            store.write_table(table, rows + [row], cols[table], con=con)
            written += 1
    for k, v in (("proposals", len(props)), ("span_verified", len(ok)), ("written", written)):
        run_.metric("_", k, v)
    run_id = results.finish(run_)
    if consume:
        print(
            f"consumed: {written} new rows written (seed rows never overwritten) (run {run_id} recorded)"
        )
    else:
        print(
            f"(review pass; nothing written; --consume writes span-verified rows) (run {run_id} recorded)"
        )
    return 0


def cli(argv: list[str]) -> int:
    if not argv:
        print("dossier-analyse DEAL_ID [--collect] [--consume]")
        return 1
    deal_id = argv[0]
    if "--collect" in argv:
        r = collect(deal_id)
        if r["status"] != "ok":
            print(f"no ma_events row carries deal_id {deal_id}")
            return 1
    return analyse(deal_id, consume="--consume" in argv)
