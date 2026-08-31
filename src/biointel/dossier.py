# C:\Users\JB\Documents\dev\bioindustry\src\biointel\dossier.py
"""Deal dossier seed and loader (gate L2; Ontology v5 §3.10, P19).

The seed is the Tempus–Personalis dossier as committed rows (the
legacy-ledger pattern: content in code, checked by tests), loaded by
`dossier-seed`. Loading is propose → verify → consume, like the label
layer:

  * every row cites its source by SEC accession (stable identifier);
    the loader resolves accession -> reference -> active capture and
    stamps the capture's hash into `doc_id` at load time, so no hash is
    ever transcribed by hand;
  * every row carries a short verbatim `span`; the loader reads the
    cited capture's text (tags stripped, whitespace collapsed,
    case-folded) and verifies the span occurs in it. A row whose source
    does not resolve or whose span is not found is HELD, printed with
    the captures that do contain the span, and does not enter the store
    (P19: a fact without a resolving document does not enter);
  * `dossier-seed --report` prints the per-row verdicts without writing;
    `dossier-seed` writes the verified rows (full replace per table, so
    re-runs are idempotent) and records a ledger run (P17).

Document assignments in the seed are proposals from the Ontology §2.5
record until the report confirms them on the operator machine; a landed
NOT-FOUND is corrected by reassigning the row to a capture that does
contain the span, never by weakening the check.

The seed writes no `ma_events` row: `labels` rewrites that table
wholesale and both entities are outside the registry until gate 2.9′,
where the index row attaches (decision 2026-08-31).
"""

from __future__ import annotations

import html as _html
import re

from biointel import config, results, schema, store

DEAL_ID = "TEM-PSNL-20260720"

# SEC accessions captured at Block L2-C (library verify: 0 problems).
ACC_10Q = "0001193125-26-326090"  # Tempus 10-Q, quarter ended 2026-06-30
ACC_8K = "0000950170-23-066458"  # Personalis 8-K 2023-11-25 + Exhibit 10.1
ACC_425 = "0001193125-26-309090"  # Personalis Form 425 investor presentation

# (table, row, accession, span) — span must occur verbatim (normalized,
# whitespace-tolerant at symbol boundaries) in a capture of the cited
# accession for the row to load. Assignments corrected 2026-08-31 on the
# --report runs' evidence; rows out of the seed pending a stating source:
# the three Merck rows (voting agreement, competing_stakeholder, Merck
# stake — no captured deal document contains "Merck"; merger-agreement
# exhibit or the §9 news URLs re-admit them) and equity_value_usd (the 425
# capture does not state it; the Tempus PR, reference Rf573315b3de, is the
# §9 source and is uncaptured after a 429 — attach a copy with
# `library add <file> --for Rf573315b3de` to re-admit).
SEED: list[tuple[str, dict, str, str]] = [
    # ---- deal_terms -----------------------------------------------------
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "announce_date", "value": "2026-07-20"},
        ACC_10Q,
        "July 20, 2026",
    ),
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "price_per_share_usd", "value": "16.25"},
        ACC_10Q,
        "$16.25",
    ),
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "exchange_ratio_cap", "value": "0.3356"},
        ACC_425,  # report 2026-08-31: span occurs only in the 425 capture
        "0.3356",
    ),
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "termination_floor_tempus_price_usd", "value": "46.00"},
        ACC_10Q,
        "$46.00",
    ),
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "outside_date", "value": "2027-04-20"},
        ACC_10Q,
        "April 20, 2027",
    ),
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "prior_stake_pct", "value": "12.5"},
        ACC_10Q,
        "12.5%",
    ),
    (
        "deal_terms",
        {
            "deal_id": DEAL_ID,
            "field": "consideration",
            "value": "100% stock with cash election up to 50%",
        },
        ACC_10Q,
        "cash",
    ),
    (
        "deal_terms",
        {"deal_id": DEAL_ID, "field": "enterprise_value_net_of_stake_usd", "value": "1.5e9"},
        ACC_10Q,  # report 2026-08-31: span occurs in the 10-Q capture
        "$1.5 billion",
    ),
    # ---- deal_timeline --------------------------------------------------
    (
        "deal_timeline",
        {
            "deal_id": DEAL_ID,
            "step_date": "2023-11-25",
            "step_type": "commercial_agreement",
            "description": "Five-year Commercialization and Reference Laboratory "
            "Agreement with equity investment",
        },
        ACC_8K,
        "Commercialization and Reference Laboratory Agreement",
    ),
    (
        "deal_timeline",
        {
            "deal_id": DEAL_ID,
            "step_date": "2026-07-20",
            "step_type": "merger_agreement",
            "description": "Merger agreement: $16.25/share, stock with cash "
            "election, exchange ratio capped at 0.3356",
        },
        ACC_10Q,
        "Merger Agreement",
    ),
    # ---- deal_rationale -------------------------------------------------
    (
        "deal_rationale",
        {
            "deal_id": DEAL_ID,
            "seq": "1",
            "stated_by": "Tempus AI",
            "statement": "Extend from diagnosis and treatment selection into "
            "recurrence monitoring (MRD)",
        },
        ACC_425,
        "MRD",
    ),
    # ---- deal_aspects ---------------------------------------------------
    (
        "deal_aspects",
        {
            "deal_id": DEAL_ID,
            "aspect": "prior_commercial_relationship",
            "value": "since 2023-11; escalations pending further captures",
            "method": "stated",
            "confidence": "0.9",
        },
        ACC_8K,
        "Commercialization and Reference Laboratory Agreement",
    ),
    (
        "deal_aspects",
        {
            "deal_id": DEAL_ID,
            "aspect": "prior_equity_stake",
            "value": "12.5% held by Tempus",
            "method": "stated",
            "confidence": "0.9",
        },
        ACC_10Q,
        "12.5%",
    ),
    (
        "deal_aspects",
        {
            "deal_id": DEAL_ID,
            "aspect": "continuum_extension",
            "value": "monitoring (MRD)",
            "method": "stated",
            "confidence": "0.8",
        },
        ACC_425,
        "MRD",
    ),
    (
        "deal_aspects",
        {
            "deal_id": DEAL_ID,
            "aspect": "consideration_type",
            "value": "stock (cash election up to 50%)",
            "method": "stated",
            "confidence": "0.9",
        },
        ACC_425,  # report 2026-08-31: span occurs only in the 425 capture
        "0.3356",
    ),
    # ---- equity_stakes --------------------------------------------------
    (
        "equity_stakes",
        {
            "holder_key": "CIK:1717115",
            "issuer_key": "CIK:1527753",
            "percent": "12.5",
            "as_of": "2026-06-30",
        },
        ACC_10Q,
        "12.5%",
    ),
]

_SEED_TABLES = (
    "deal_terms",
    "deal_timeline",
    "deal_rationale",
    "deal_aspects",
    "deal_comparables",
    "equity_stakes",
    "stated_priorities",
    "assets",
)
_COLS = {
    "deal_terms": schema.DEAL_TERM_COLS,
    "deal_timeline": schema.DEAL_TIMELINE_COLS,
    "deal_rationale": schema.DEAL_RATIONALE_COLS,
    "deal_aspects": schema.DEAL_ASPECT_COLS,
    "deal_comparables": schema.DEAL_COMPARABLE_COLS,
    "equity_stakes": schema.EQUITY_STAKE_COLS,
    "stated_priorities": schema.STATED_PRIORITY_COLS,
    "assets": schema.ASSET_COLS,
}
_TEXT_EXTS = {"htm", "html", "txt"}


def span_pattern(span: str):
    """Compile a span into a whitespace-tolerant verbatim pattern: literal
    spaces match any whitespace run, and symbol boundaries ($, %, digits vs
    punctuation) tolerate optional whitespace, because tag-stripping inline
    XBRL inserts spaces there ("12.5</x>%" -> "12.5 %"). Token order and
    content stay verbatim (P19)."""
    parts = []
    for ch in normalize(span):
        if ch == " ":
            parts.append(r"\s+")
        elif ch.isalnum():
            parts.append(re.escape(ch))
        else:
            parts.append(r"\s*" + re.escape(ch) + r"\s*")
    return re.compile("".join(parts))


def normalize(text: str) -> str:
    """Tag-stripped, entity-unescaped, whitespace-collapsed, case-folded."""
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).casefold().strip()


def _refs_by_accession(con) -> dict[str, str]:
    out: dict[str, str] = {}
    if store.has_table("references", con):
        for r in store.read_table("references", con=con):
            if r["sec_accession"] and r["status"] == "active":
                out.setdefault(r["sec_accession"], r["ref_id"])
    return out


def _captures_of(ref_id: str, con) -> list[dict]:
    if not store.has_table("captures", con):
        return []
    return [
        c
        for c in store.read_table("captures", con=con)
        if c["ref_id"] == ref_id and c["status"] == "active"
    ]


def _capture_text(cap: dict) -> str | None:
    if cap["ext"].lower() not in _TEXT_EXTS:
        return None
    p = config.DATA / cap["path"]
    if not p.exists():
        return None
    return normalize(p.read_text(encoding="utf-8", errors="replace"))


def verify_seed(con) -> list[dict]:
    """Per seed row: resolve accession -> capture, check the span, and for a
    miss list every capture that does contain the span. Returns verdicts."""
    by_acc = _refs_by_accession(con)
    text_cache: dict[str, str | None] = {}
    all_caps = (
        [c for c in store.read_table("captures", con=con) if c["status"] == "active"]
        if store.has_table("captures", con)
        else []
    )

    def text_of(cap: dict) -> str | None:
        if cap["capture_id"] not in text_cache:
            text_cache[cap["capture_id"]] = _capture_text(cap)
        return text_cache[cap["capture_id"]]

    verdicts = []
    for table, row, acc, span in SEED:
        ref_id = by_acc.get(acc, "")
        doc_id, status, also = "", "", []
        needle = span_pattern(span)
        if not ref_id:
            status = "UNRESOLVED (no active reference with this accession)"
        else:
            hit = None
            for cap in _captures_of(ref_id, con):
                t = text_of(cap)
                if t is not None and needle.search(t):
                    hit = cap
                    break
            if hit is not None:
                doc_id, status = hit["capture_id"], "FOUND"
            else:
                status = "SPAN NOT FOUND in the cited accession's captures"
                for cap in all_caps:
                    t = text_of(cap)
                    if t is not None and needle.search(t):
                        also.append(cap["capture_id"][:12])
        verdicts.append(
            {
                "table": table,
                "row": row,
                "accession": acc,
                "span": span,
                "doc_id": doc_id,
                "status": status,
                "also_found_in": also,
            }
        )
    return verdicts


def _print_report(verdicts: list[dict]) -> tuple[int, int]:
    ok = held = 0
    for v in verdicts:
        keyish = (
            v["row"].get("field")
            or v["row"].get("aspect")
            or v["row"].get("step_type")
            or v["row"].get("holder_key")
            or v["row"].get("seq", "")
        )
        if v["status"] == "FOUND":
            ok += 1
            print(
                f"  FOUND  {v['table']:<15} {str(keyish):<36} {v['accession']}  "
                f"doc {v['doc_id'][:12]}  span {v['span']!r}"
            )
        else:
            held += 1
            print(
                f"  HELD   {v['table']:<15} {str(keyish):<36} {v['accession']}  "
                f"{v['status']}  span {v['span']!r}"
            )
            if v["also_found_in"]:
                head = ", ".join(v["also_found_in"][:8])
                more = len(v["also_found_in"]) - 8
                tail = f" (+{more} more)" if more > 0 else ""
                print(f"         span occurs in captures: {head}{tail}")
    print(f"dossier seed: {ok} verified, {held} held (of {len(verdicts)})")
    return ok, held


def seed(report_only: bool = False) -> dict:
    con = store.connect()
    verdicts = verify_seed(con)
    ok, held = _print_report(verdicts)
    if report_only:
        return {"status": "ok", "verified": ok, "held": held, "loaded": 0}
    run = results.start(
        "dossier",
        "dossier-seed",
        ["references", "captures"] + list(_SEED_TABLES),
        {"deal_id": DEAL_ID, "seed_rows": len(SEED)},
    )
    rows_by_table: dict[str, list[dict]] = {t: [] for t in _SEED_TABLES}
    for v in verdicts:
        if v["status"] == "FOUND":
            row = dict(v["row"])
            row["doc_id"] = v["doc_id"]
            row["span"] = v["span"]
            rows_by_table[v["table"]].append(row)
    counts = {}
    for t in _SEED_TABLES:
        counts[t] = store.write_table(t, rows_by_table[t], _COLS[t], con=con)
        run.metric("rows", t, counts[t])
    run.metric("_", "verified", ok)
    run.metric("_", "held", held)
    run_id = results.finish(
        run, status="ok" if held == 0 else "empty", note="" if held == 0 else f"{held} rows held"
    )
    loaded = sum(counts.values())
    print(
        f"dossier-seed: {loaded} rows loaded across {sum(1 for t in _SEED_TABLES if counts[t])} "
        f"tables; {held} held (run {run_id} recorded)"
    )
    return {
        "status": "ok" if held == 0 else "held",
        "verified": ok,
        "held": held,
        "loaded": loaded,
        "counts": counts,
        "run_id": run_id,
    }


def cli(argv: list[str]) -> int:
    report_only = "--report" in argv
    r = seed(report_only=report_only)
    if report_only:
        return 0
    return 0 if r["status"] == "ok" else 1
