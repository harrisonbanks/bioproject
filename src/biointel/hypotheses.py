# C:\Users\JB\Documents\dev\bioindustry\src\biointel\hypotheses.py
"""Expert-hypothesis store — what informed people believe about where the
industry is going, held to the same as-of and never-test discipline as every
other input. Decisions of record: docs/20260903_v1_Hypothesis_Store_Decisions.md.

WHY THE DATES MATTER. A hypothesis may inform only predictions made after it
was recorded, so `as_of` is the ARTIFACT date when an artifact exists (the
email, message, note, article or slide, stored in the library like any
document) and the entry date otherwise. It is never the date a recalled call
was typed in. Without that rule a call entered after a deal was rumoured is
indistinguishable from foresight, and the resulting accuracy figure is
unbounded upward.

WHY RECOLLECTED CALLS ARE KEPT BUT NOT SCORED. An undated recollection is
real information about what an expert believes and worthless as evidence of
what they predicted. It is stored, flagged `recollected`, and excluded from
every rate; attaching an artifact later upgrades it to `documented` and it
becomes scoreable. Scoring queries filter on `evidence_class`, so presence in
the table cannot contaminate a rate.

WHY THERE IS NO EXPIRY. A call with a stated horizon is scored against that
horizon, because the horizon is part of the prediction. A call without one
stays `open` until an event resolves it or the expert withdraws it. No
system-wide default exists: a fabricated one would have scored the
Tempus-Personalis sequence (about 32 months from stake to announcement) as a
miss, and the only published distribution found puts a quarter of
stake-to-deal intervals beyond 28 months (Povel & Sertsios, J Corp Fin 26,
2014, Table 2B; median 15 months, n=155, all-industry, which the authors note
likely understates the true elapsed time).

NEVER TEST EVIDENCE. Hypotheses may feed a matcher's ranking as a declared
input with equal weight until a per-expert ledger exists. They can never be
used to score whether that ranking was right (P10, P19): a hypothesis about a
deal cannot grade a prediction of the same deal.

TRACK RECORDS NEED A DENOMINATOR. Accuracy is hits over all documented calls.
Recovering only the hits from an expert's history inflates the numerator and
leaves the denominator short, so `ledger` reports counts alongside any rate
and marks a recovery as incomplete when the operator says so.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date

from biointel import schema, store

log = logging.getLogger(__name__)

TABLE = "analyst_hypotheses"


def _cols() -> list[str]:
    t = schema.TABLE_BY_PATH["silver/analyst_hypotheses.csv"]
    return list(t.columns) + list(t.optional)


def _hid(expert: str, subject: str, obj: str, as_of: str) -> str:
    raw = f"{expert}|{subject}|{obj}|{as_of}".lower()
    return "H" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:15]


def add(
    expert: str,
    subject_key: str,
    predicate: str,
    object_kind: str,
    object_value: str,
    statement: str,
    *,
    source_kind: str = "direct",
    horizon: str = "",
    confidence: str = "",
    artifact_date: str = "",
    doc_id: str = "",
    span: str = "",
    entered_by: str = "",
    con=None,
) -> dict:
    """Record one hypothesis. `evidence_class` is derived, never passed: a row
    is `documented` only when it carries BOTH an artifact date and the
    `doc_id` of a library document; anything else is `recollected`. `as_of`
    follows the same fact — artifact date when documented, entry date
    otherwise — so a recalled call can never claim an earlier vantage point
    than the day it was written down."""
    con = con or store.connect()
    today = date.today().isoformat()
    documented = bool(artifact_date and doc_id)
    as_of = artifact_date if documented else today
    row = dict.fromkeys(_cols(), "")
    row.update(
        {
            "hypothesis_id": _hid(expert, subject_key, object_value, as_of),
            "expert": expert,
            "subject_key": subject_key,
            "predicate": predicate,
            "object_kind": object_kind,
            "object_value": object_value,
            "horizon": horizon,
            "confidence": confidence,
            "statement": statement,
            "source_kind": source_kind,
            "evidence_class": "documented" if documented else "recollected",
            "as_of": as_of,
            "entered_by": entered_by or expert,
            "entered_on": today,
            "doc_id": doc_id,
            "span": span,
            "outcome": "open",
            "resolved_on": "",
            "resolution_note": "",
        }
    )
    existing = store.read_table(TABLE, con=con) if store.has_table(TABLE, con) else []
    if any(r["hypothesis_id"] == row["hypothesis_id"] for r in existing):
        return {"status": "exists", "hypothesis_id": row["hypothesis_id"]}
    store.append_rows(TABLE, [row], _cols(), con=con)
    return {
        "status": "ok",
        "hypothesis_id": row["hypothesis_id"],
        "as_of": as_of,
        "evidence_class": row["evidence_class"],
    }


def attach_artifact(hypothesis_id: str, artifact_date: str, doc_id: str, con=None) -> dict:
    """Upgrade a recollected call once its artifact turns up: the artifact
    date becomes `as_of` and the row becomes scoreable. Refuses to move a
    documented row's date, which would let a call be re-dated after the fact."""
    con = con or store.connect()
    rows = {r["hypothesis_id"]: r for r in store.read_table(TABLE, con=con)}
    r = rows.get(hypothesis_id)
    if r is None:
        return {"status": "unknown", "message": f"{hypothesis_id}: not found"}
    if str(r["evidence_class"]) == "documented":
        return {"status": "refused", "message": "already documented; as_of is not re-datable"}
    store.update_rows(
        TABLE,
        [
            {
                "hypothesis_id": hypothesis_id,
                "evidence_class": "documented",
                "as_of": artifact_date,
                "doc_id": doc_id,
            }
        ],
        con=con,
    )
    return {"status": "ok", "hypothesis_id": hypothesis_id, "as_of": artifact_date}


def resolve(hypothesis_id: str, outcome: str, note: str = "", con=None) -> dict:
    """Mark a call hit, miss or withdrawn. Resolution is by event, never by a
    clock: nothing here expires a call for age."""
    if outcome not in ("hit", "miss", "withdrawn"):
        return {"status": "error", "message": f"{outcome}: not hit|miss|withdrawn"}
    con = con or store.connect()
    n = store.update_rows(
        TABLE,
        [
            {
                "hypothesis_id": hypothesis_id,
                "outcome": outcome,
                "resolved_on": date.today().isoformat(),
                "resolution_note": note,
            }
        ],
        con=con,
    )
    if not n:
        return {"status": "unknown", "message": f"{hypothesis_id}: not found"}
    return {"status": "ok", "hypothesis_id": hypothesis_id, "outcome": outcome}


def as_of_rows(cutoff: str, con=None) -> list[dict]:
    """Every hypothesis knowable at `cutoff`. The only reader a model should
    use: it enforces the leak guard in one place rather than at each call
    site."""
    con = con or store.connect()
    if not store.has_table(TABLE, con):
        return []
    return [
        r
        for r in store.read_table(TABLE, con=con)
        if str(r.get("as_of") or "")[:10] and str(r["as_of"])[:10] <= cutoff
    ]


def ledger(con=None) -> dict:
    """Per-expert track record over DOCUMENTED calls only. Recollected calls
    are counted and never folded into a rate. A rate is reported only when the
    expert has at least one resolved documented call, and always beside its
    denominator."""
    con = con or store.connect()
    if not store.has_table(TABLE, con):
        return {"status": "empty", "message": "no hypotheses recorded", "experts": {}}
    out: dict[str, dict] = {}
    for r in store.read_table(TABLE, con=con):
        e = out.setdefault(
            str(r["expert"]),
            {
                "documented": 0,
                "recollected": 0,
                "hit": 0,
                "miss": 0,
                "open": 0,
                "withdrawn": 0,
                "rate": None,
            },
        )
        if str(r["evidence_class"]) == "recollected":
            e["recollected"] += 1
            continue
        e["documented"] += 1
        e[str(r["outcome"] or "open")] += 1
    for e in out.values():
        resolved = e["hit"] + e["miss"]
        e["resolved"] = resolved
        e["rate"] = (e["hit"] / resolved) if resolved else None
    return {"status": "ok", "experts": out}


def render_ledger(led: dict) -> str:
    if led.get("status") != "ok":
        return str(led.get("message", "no hypotheses recorded"))
    lines = [
        "EXPERT TRACK RECORD (documented calls only; recollected calls are "
        "counted, never rated; no call expires for age)"
    ]
    for name in sorted(led["experts"]):
        e = led["experts"][name]
        rate = "n/a" if e["rate"] is None else f"{e['rate']:.3f}"
        lines.append(
            f"  {name:<28} documented {e['documented']:>3}  hit {e['hit']:>3}  "
            f"miss {e['miss']:>3}  open {e['open']:>3}  withdrawn {e['withdrawn']:>3}  "
            f"rate {rate} over {e['resolved']}  (recollected {e['recollected']}, unscored)"
        )
    return "\n".join(lines)


def cli(argv: list[str]) -> int:
    sub = argv[0] if argv else ""
    if sub == "ledger":
        print(render_ledger(ledger()))
        return 0
    if sub == "list":
        cutoff = argv[1] if len(argv) > 1 else date.today().isoformat()
        rows = as_of_rows(cutoff)
        print(f"{len(rows)} hypotheses knowable as of {cutoff}")
        for r in rows:
            print(
                f"  {r['hypothesis_id']}  {r['expert']}  {r['subject_key']} "
                f"{r['predicate']} {r['object_value']}  as_of {str(r['as_of'])[:10]}  "
                f"{r['evidence_class']}  {r['outcome']}"
            )
        return 0
    if sub == "resolve" and len(argv) >= 3:
        r = resolve(argv[1], argv[2], " ".join(argv[3:]))
        print(r.get("message") or f"{r['hypothesis_id']} -> {r.get('outcome')}")
        return 0 if r["status"] == "ok" else 1
    print(
        "usage: hypothesis ledger | list [CUTOFF] | resolve ID hit|miss|withdrawn [NOTE]\n"
        "       (entry is a Python/manual-layer call: hypotheses.add(...), which derives\n"
        "        evidence_class and as_of from whether an artifact was supplied)"
    )
    return 1
