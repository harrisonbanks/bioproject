# C:\Users\JB\Documents\dev\bioindustry\src\biointel\assist.py
"""Gate M4: LLM judge-assist — a PROPOSER, never the verdict.

Operator rulings of record (2026-09-07): the model is CONFIGURABLE
(config.ASSIST_MODEL, default the stronger current mid-tier model,
claude-sonnet-5); the per-run cap is 200 calls (config.ASSIST_CALL_CAP);
ASSIST_ENABLED defaults to False; the API key comes from the environment
only (ANTHROPIC_API_KEY). Each call sends ONLY the disputed field, the two
values, and a bounded document excerpt — never the whole filing. Proposals
land in `review_proposals` with model id, prompt version and excerpt hash,
are displayed beside the queue worksheet, and are never auto-applied;
`stakes precision` counts human verdicts only. A malformed reply or API
failure degrades to no proposal — the queue never depends on the API.

The acceptance gate (`stakes assist-accept`) measures a model against
GROUND TRUTH the pipeline already holds: the r9-repaired disputes, where
two independent routes agreed on the true date, so the right proposal is
known ("wrong") — the number goes in the ledger per model, and the
operator compares models before trusting either (calibration against
annotated examples, the standing best practice).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path

from biointel import config, library, results, store

log = logging.getLogger(__name__)

PROMPT_VERSION = "judge_assist_v1"
_PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt"
API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_CAP = 200
_VERDICT_RE = re.compile(r"VERDICT:\s*(correct|wrong|unsure|abstain)", re.IGNORECASE)
_REASON_RE = re.compile(r"REASON:\s*(.+)", re.IGNORECASE)
EXCERPT_HEAD = 2000
EXCERPT_WINDOW = 800
EXCERPT_CAP = 6000
_FIELD_ANCHORS = {
    "as_of": re.compile(r"Date\s+of\s+Event", re.IGNORECASE),
    "percent": re.compile(
        r"Percent\s+of\s+Class|Type\s+of\s+Reporting\s+Person", re.IGNORECASE
    ),
    "direction": re.compile(r"Name\s+of\s+Issuer|Reporting\s+Person", re.IGNORECASE),
}


def _cfg(name: str, default):
    return getattr(config, name, default)


def prompt_text() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_excerpt(text: str, field: str) -> str:
    """Bounded, field-aware excerpt: the document head plus windows around
    the field's anchor phrases. Never the whole filing (GATEM M4)."""
    parts = [text[:EXCERPT_HEAD]]
    anchor = _FIELD_ANCHORS.get(field)
    if anchor:
        for m in anchor.finditer(text):
            lo = max(0, m.start() - EXCERPT_WINDOW)
            hi = min(len(text), m.end() + EXCERPT_WINDOW)
            parts.append(text[lo:hi])
    return "\n...\n".join(parts)[:EXCERPT_CAP]


def build_prompt(entry: dict, excerpt: str) -> str:
    return prompt_text().format(
        field=str(entry.get("field") or ""),
        stored_value=str(entry.get("stored_value") or ""),
        other_value=str(entry.get("other_value") or ""),
        filing_date=str(entry.get("filing_date") or "")[:10],
        excerpt=excerpt,
    )


def _call_api(prompt: str, model: str) -> str | None:
    """One Messages call; the key from the environment ONLY. Any failure
    returns None — the caller records nothing (GATEM M4 degradation rule)."""
    import requests

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        r = requests.post(
            API_URL,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            data=json.dumps(
                {
                    "model": model,
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
            timeout=60,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
    except Exception:  # noqa: BLE001 - any API failure degrades to no proposal
        return None


def parse_reply(reply: str | None) -> tuple[str, str] | None:
    """(verdict, reason) or None on anything malformed."""
    if not reply:
        return None
    v = _VERDICT_RE.search(reply)
    if not v:
        return None
    reason = _REASON_RE.search(reply)
    return v.group(1).lower(), (reason.group(1).strip() if reason else "")[:300]


def _proposal_id(queue_id: str, model: str, prompt_version: str) -> str:
    return (
        "P"
        + hashlib.sha256(f"{queue_id}|{model}|{prompt_version}".encode()).hexdigest()[:16]
    )


def _doc_text(doc_id: str, caps: dict, con) -> str | None:
    from biointel.efts import normalize_text

    cap = caps.get(doc_id)
    if not cap:
        return None
    ext = "." + str(cap.get("ext") or "htm")
    try:
        return normalize_text(
            library.store_path(str(cap["capture_id"]), ext).read_text(
                encoding="utf-8", errors="replace"
            )
        )
    except OSError:
        return None


def run_assist(n: int | None = None, model: str | None = None, con=None) -> int:
    """Propose on up to min(n, cap) OPEN queue entries that lack a proposal
    for this model+prompt version (idempotent). Writes review_proposals rows
    only; never touches equity_stakes or queue status."""
    from biointel import schema as _schema
    from biointel import stakes as _stakes

    if not _cfg("ASSIST_ENABLED", False):
        print("assist disabled: set ASSIST_ENABLED = True in config to use it")
        return 1
    con = con or store.connect()
    model = model or _cfg("ASSIST_MODEL", DEFAULT_MODEL)
    cap = int(_cfg("ASSIST_CALL_CAP", DEFAULT_CAP))
    limit = min(n or cap, cap)
    existing = (
        {str(r["proposal_id"]) for r in store.read_table("review_proposals", con=con)}
        if store.has_table("review_proposals", con)
        else set()
    )
    entries = [
        q
        for q in store.read_table("review_queue", con=con)
        if str(q["status"]) == "open"
        and _proposal_id(str(q["queue_id"]), model, PROMPT_VERSION) not in existing
    ]
    caps = _stakes._active_doc_caps(con)
    counters = {"proposed": 0, "malformed": 0, "api_failures": 0, "no_capture": 0}
    rows: list[dict] = []
    ptext = prompt_text()  # read once; a missing prompt file fails loudly here
    assert ptext
    for q in entries[:limit]:
        text = _doc_text(str(q["doc_id"]), caps, con)
        if text is None:
            counters["no_capture"] += 1
            continue
        excerpt = build_excerpt(text, str(q["field"]))
        reply = _call_api(build_prompt(q, excerpt), model)
        if reply is None:
            counters["api_failures"] += 1
            continue
        parsed = parse_reply(reply)
        if parsed is None:
            counters["malformed"] += 1
            continue
        verdict, reason = parsed
        row = dict.fromkeys(_schema.REVIEW_PROPOSAL_COLS, "")
        row.update(
            {
                "proposal_id": _proposal_id(str(q["queue_id"]), model, PROMPT_VERSION),
                "queue_id": str(q["queue_id"]),
                "model_id": model,
                "prompt_version": PROMPT_VERSION,
                "excerpt_hash": hashlib.sha256(excerpt.encode()).hexdigest()[:16],
                "verdict": verdict,
                "reason": reason,
                "created_at": library._now(),
            }
        )
        rows.append(row)
        counters["proposed"] += 1
    if rows:
        store.append_rows(
            "review_proposals", rows, list(_schema.REVIEW_PROPOSAL_COLS), con=con
        )
    runr = results.start(
        "stakes-assist",
        "stakes assist",
        ["review_queue", "captures", "review_proposals"],
        {"model": model, "prompt_version": PROMPT_VERSION, "cap": cap},
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    run_id = results.finish(
        runr, note="LLM proposals recorded with provenance; never auto-applied (M4)"
    )
    print(
        "ASSIST model "
        + model
        + " "
        + " ".join(f"{k} {v}" for k, v in counters.items())
    )
    log.info(f"run {run_id} recorded")
    return 0


def accept(n: int = 100, model: str | None = None, seed: int = 20260907, con=None) -> int:
    """Acceptance gate: run the proposer against disputes whose truth the
    pipeline already knows — the r9-repaired entries, where two independent
    routes agreed the stored value was wrong — and measure how often the
    model says "wrong". The number goes in the ledger per model; run it per
    candidate model and compare before trusting either."""
    import random as _r

    from biointel import stakes as _stakes

    if not _cfg("ASSIST_ENABLED", False):
        print("assist disabled: set ASSIST_ENABLED = True in config to use it")
        return 1
    con = con or store.connect()
    model = model or _cfg("ASSIST_MODEL", DEFAULT_MODEL)
    cap = int(_cfg("ASSIST_CALL_CAP", DEFAULT_CAP))
    n = min(n, cap)
    truth: dict[str, str] = {}
    repaired_spans = {
        (str(r["holder_key"]), str(r["issuer_key"])): str(r["as_of"])[:10]
        for r in store.read_table("equity_stakes", con=con)
        if "|| r9:" in str(r.get("span") or "")
    }
    entries = []
    for q in store.read_table("review_queue", con=con):
        if str(q["status"]) != "judged" or str(q["field"]) != "as_of":
            continue
        k = (str(q["holder_key"]), str(q["issuer_key"]))
        if k in repaired_spans and repaired_spans[k] == str(q["other_value"]):
            entries.append(q)
            truth[str(q["queue_id"])] = "wrong"  # two routes agreed: stored was wrong
    if not entries:
        print("no r9-repaired entries to measure against")
        return 1
    entries.sort(key=lambda q: str(q["queue_id"]))
    _r.seed(seed)
    picked = _r.sample(entries, min(n, len(entries)))
    caps = _stakes._active_doc_caps(con)
    counters = {"measured": 0, "agree": 0, "abstain": 0, "unusable": 0}
    for q in picked:
        text = _doc_text(str(q["doc_id"]), caps, con)
        if text is None:
            counters["unusable"] += 1
            continue
        reply = _call_api(build_prompt(q, build_excerpt(text, "as_of")), model)
        parsed = parse_reply(reply)
        if parsed is None:
            counters["unusable"] += 1
            continue
        counters["measured"] += 1
        if parsed[0] == truth[str(q["queue_id"])]:
            counters["agree"] += 1
        elif parsed[0] == "abstain":
            counters["abstain"] += 1
    runr = results.start(
        "stakes-assist-accept",
        "stakes assist-accept",
        ["review_queue", "equity_stakes", "captures"],
        {"model": model, "prompt_version": PROMPT_VERSION, "n": n, "seed": seed},
    )
    for k, v in counters.items():
        runr.metric("_", k, v)
    if counters["measured"]:
        runr.metric("_", "agreement", counters["agree"] / counters["measured"])
    run_id = results.finish(
        runr, note="acceptance vs r9 two-route ground truth; per-model, in the ledger"
    )
    rate = (
        f"{counters['agree']}/{counters['measured']} = "
        f"{counters['agree'] / counters['measured']:.3f}"
        if counters["measured"]
        else "0/0"
    )
    print(
        f"ASSIST-ACCEPT model {model} agreement {rate}; abstain {counters['abstain']}; "
        f"unusable {counters['unusable']}"
    )
    log.info(f"run {run_id} recorded")
    return 0
