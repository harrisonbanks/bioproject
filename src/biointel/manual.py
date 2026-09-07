# C:\Users\JB\Documents\dev\bioindustry\src\biointel\manual.py
"""Manual layer (gate 2.10; Ontology v5 §3.7, P5): hand-entered entities,
attribute overrides and notes.

Store of record: the database only (ruling 2026-08-31). Nothing here is
committed to git; machines reconcile through the hashed snapshot. Because a
rebuild-from-bronze recreates only machine tables, `manual export` writes
every hand-entered table — the manual trio plus the eight dossier tables —
to a local JSON file under data\\manual\\, and `manual load` re-applies it
idempotently. Export before a rebuild, load after; the export file is
rebuild insurance and snapshot cargo, never a git artifact.

Precedence (P5): a manual attribute always outranks the machine value for
the same entity and field, visibly. No existing reader is switched at this
gate; consumers opt in via `merged_rows()` at their own gates (L3 review
queue first). Validation refuses attribute rows that target an undeclared
table or column, so typos cannot create phantom fields.
"""

from __future__ import annotations

import getpass
import json
from datetime import datetime, timezone
from pathlib import Path

from biointel import config, results, schema, store

MANUAL_TABLES = ("manual_entities", "manual_attributes", "manual_notes")
DOSSIER_TABLES = (
    "deal_terms",
    "deal_timeline",
    "deal_rationale",
    "deal_aspects",
    "deal_comparables",
    "equity_stakes",
    "stated_priorities",
    "assets",
)
HAND_TABLES = MANUAL_TABLES + ("entity_lineage",) + DOSSIER_TABLES
_COLS = {
    "manual_entities": schema.MANUAL_ENTITY_COLS,
    "manual_attributes": schema.MANUAL_ATTRIBUTE_COLS,
    "manual_notes": schema.MANUAL_NOTE_COLS,
    "entity_lineage": schema.ENTITY_LINEAGE_COLS,
    "deal_terms": schema.DEAL_TERM_COLS,
    "deal_timeline": schema.DEAL_TIMELINE_COLS,
    "deal_rationale": schema.DEAL_RATIONALE_COLS,
    "deal_aspects": schema.DEAL_ASPECT_COLS,
    "deal_comparables": schema.DEAL_COMPARABLE_COLS,
    "equity_stakes": schema.EQUITY_STAKE_COLS,
    "stated_priorities": schema.STATED_PRIORITY_COLS,
    "assets": schema.ASSET_COLS,
}
_EXPORT_DEFAULT = "manual/hand_data.json"

# machine tables whose columns a manual attribute may override; the manual
# `attribute` field is written as "table.Column" and validated against this.
_OVERRIDABLE = (
    "companies",
    "universe",
    "events",
    "events_table",
    "relationships",
    "partners",
    "financials",
    "ma_events",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp(row: dict) -> dict:
    if not row.get("entered_by"):
        row["entered_by"] = getpass.getuser()
    if not row.get("entered_on"):
        row["entered_on"] = _now()
    return row


def _table_cols(name: str) -> tuple[str, ...] | None:
    for t in schema.TABLES:
        if t.path.endswith("/" + name + ".csv"):
            return t.columns + tuple(t.optional)
    return None


def validate_attribute_target(attribute: str) -> str:
    """'table.Column' -> error text or '' when the target is declared."""
    if "." not in attribute:
        return "attribute must be 'table.Column' (e.g. companies.Tickers)"
    table, col = attribute.split(".", 1)
    if table not in _OVERRIDABLE:
        return f"table '{table}' is not overridable (allowed: {', '.join(_OVERRIDABLE)})"
    cols = _table_cols(table)
    if cols is None:
        return f"table '{table}' is not declared in the schema"
    if col not in cols:
        return f"column '{col}' is not declared on '{table}'"
    return ""


def _append(table: str, row: dict, con) -> None:
    rows = store.read_table(table, con=con) if store.has_table(table, con) else []
    rows = [r for r in rows if not _same_key(table, r, row)]
    rows.append(row)
    store.write_table(table, rows, _COLS[table], con=con)


def _same_key(table: str, a: dict, b: dict) -> bool:
    keys = {
        "manual_entities": ("entity_key",),
        "manual_attributes": ("entity_key", "attribute"),
        "manual_notes": ("note_id",),
        "entity_lineage": ("predecessor_cik",),
    }[table]
    return all(a.get(k) == b.get(k) for k in keys)


def add_entity(entity_key: str, name: str, **fields) -> dict:
    con = store.connect()
    row = {c: "" for c in schema.MANUAL_ENTITY_COLS}
    row.update({"entity_key": entity_key, "name": name})
    row.update({k: v for k, v in fields.items() if k in row and v is not None})
    _append("manual_entities", _stamp(row), con)
    return row


def add_attribute(entity_key: str, attribute: str, value: str, **fields) -> dict:
    err = validate_attribute_target(attribute)
    if err:
        raise ValueError(err)
    con = store.connect()
    row = {c: "" for c in schema.MANUAL_ATTRIBUTE_COLS}
    row.update({"entity_key": entity_key, "attribute": attribute, "value": value})
    row.update({k: v for k, v in fields.items() if k in row and v is not None})
    _append("manual_attributes", _stamp(row), con)
    return row


def add_lineage(predecessor_cik: str, successor_cik: str, **fields) -> dict:
    """Record that predecessor_cik is a historical entity whose lineage
    continues as successor_cik (rename, redomiciliation or merger). Hand-
    entered only, one primary source per pair; refuses self-mappings and
    non-numeric CIKs."""
    p, sc = str(predecessor_cik).strip(), str(successor_cik).strip()
    if not (p.isdigit() and sc.isdigit()):
        raise ValueError("lineage CIKs must be numeric")
    if str(int(p)) == str(int(sc)):
        raise ValueError("lineage cannot map a CIK to itself")
    con = store.connect()
    row = {c: "" for c in schema.ENTITY_LINEAGE_COLS}
    row.update({"predecessor_cik": str(int(p)), "successor_cik": str(int(sc))})
    row.update({k: v for k, v in fields.items() if k in row and v is not None})
    _append("entity_lineage", _stamp(row), con)
    return row


def add_note(entity_key: str, text: str, **fields) -> dict:
    con = store.connect()
    row = {c: "" for c in schema.MANUAL_NOTE_COLS}
    n = (
        len(store.read_table("manual_notes", con=con))
        if store.has_table("manual_notes", con)
        else 0
    )
    row.update(
        {"note_id": f"N{n + 1:06d}", "entity_key": entity_key, "text": text, "date": _now()[:10]}
    )
    row.update({k: v for k, v in fields.items() if k in row and v is not None})
    _append("manual_notes", _stamp(row), con)
    return row


def sweep() -> list[str]:
    """Re-validate every stored attribute target (schema may have moved)."""
    con = store.connect()
    problems = []
    if store.has_table("manual_attributes", con):
        for r in store.read_table("manual_attributes", con=con):
            err = validate_attribute_target(r["attribute"])
            if err:
                problems.append(f"{r['entity_key']} {r['attribute']}: {err}")
    return problems


def merged_rows(table: str, key_col: str = "IID") -> tuple[list[dict], list[dict]]:
    """Machine rows with manual overrides applied; returns (rows, applied).
    An override targets 'table.Column' and matches rows whose key_col equals
    the manual entity_key. Visible by construction: `applied` lists every
    override used. Consumers opt in at their own gates; nothing calls this
    at 2.10."""
    con = store.connect()
    rows = (
        [dict(r) for r in store.read_table(table, con=con)] if store.has_table(table, con) else []
    )
    applied = []
    if not store.has_table("manual_attributes", con):
        return rows, applied
    overrides = [
        r
        for r in store.read_table("manual_attributes", con=con)
        if r["attribute"].startswith(table + ".")
    ]
    for o in overrides:
        col = o["attribute"].split(".", 1)[1]
        for r in rows:
            if str(r.get(key_col)) == str(o["entity_key"]):
                r[col] = o["value"]
                applied.append(
                    {
                        "entity_key": o["entity_key"],
                        "column": col,
                        "value": o["value"],
                        "source": o.get("source", ""),
                    }
                )
    return rows, applied


def export(path: str | None = None) -> dict:
    con = store.connect()
    out = {}
    for t in HAND_TABLES:
        out[t] = store.read_table(t, con=con) if store.has_table(t, con) else []
    dst = config.DATA / (path or _EXPORT_DEFAULT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    n = sum(len(v) for v in out.values())
    print(f"manual export: {n} rows across {sum(1 for v in out.values() if v)} tables -> {dst}")
    return {"rows": n, "path": str(dst)}


def load(path: str | None = None) -> dict:
    src = Path(path) if path else config.DATA / _EXPORT_DEFAULT
    if not src.exists():
        print(f"manual load: no export file at {src}")
        return {"status": "missing", "rows": 0}
    data = json.loads(src.read_text(encoding="utf-8"))
    con = store.connect()
    run = results.start("manual", "manual load", list(HAND_TABLES), {"file": str(src)})
    total = 0
    for t in HAND_TABLES:
        rows = data.get(t, [])
        store.write_table(t, rows, _COLS[t], con=con)
        run.metric("rows", t, len(rows))
        total += len(rows)
    run_id = results.finish(run)
    print(
        f"manual load: {total} rows across {sum(1 for t in HAND_TABLES if data.get(t))} "
        f"tables from {src} (run {run_id} recorded)"
    )
    return {"status": "ok", "rows": total, "run_id": run_id}


def _list(which: str | None) -> int:
    con = store.connect()
    tables = [which] if which else list(MANUAL_TABLES)
    for t in tables:
        rows = store.read_table(t, con=con) if store.has_table(t, con) else []
        print(f"{t}: {len(rows)} rows")
        for r in rows[:20]:
            keyish = r.get("attribute") or r.get("note_id") or ""
            print(
                f"  {r.get('entity_key', ''):<14} {keyish:<28} "
                f"{str(r.get('value') or r.get('name') or r.get('text') or '')[:48]:<48} "
                f"{r.get('entered_on', '')[:10]} {r.get('source', '')[:24]}"
            )
        if len(rows) > 20:
            print(f"  ... {len(rows) - 20} more")
    return 0


def _arg(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


def cli(argv: list[str]) -> int:
    if not argv:
        print(
            "manual: add-entity | add-attribute | add-note | add-lineage | list | validate | export | load"
        )
        return 1
    sub, rest = argv[0], argv[1:]
    if sub == "add-entity":
        if len(rest) < 2:
            print(
                "usage: manual add-entity ENTITY_KEY NAME [--cik C] [--ticker T] [--type T] [--source S] [--note N]"
            )
            return 1
        row = add_entity(
            rest[0],
            rest[1],
            cik=_arg(rest, "--cik"),
            ticker=_arg(rest, "--ticker"),
            type=_arg(rest, "--type"),
            source=_arg(rest, "--source"),
            note=_arg(rest, "--note"),
        )
        print(f"manual entity {row['entity_key']} recorded")
        return 0
    if sub == "add-lineage":
        if len(rest) < 2:
            print(
                "usage: manual add-lineage PREDECESSOR_CIK SUCCESSOR_CIK [--date YYYY-MM-DD] [--source S] [--note N]"
            )
            return 1
        try:
            row = add_lineage(
                rest[0],
                rest[1],
                effective_date=_arg(rest, "--date"),
                source=_arg(rest, "--source"),
                note=_arg(rest, "--note"),
            )
        except ValueError as e:
            print(str(e))
            return 1
        print(f"lineage {row['predecessor_cik']} -> {row['successor_cik']} recorded")
        return 0
    if sub == "add-attribute":
        if len(rest) < 3:
            print(
                "usage: manual add-attribute ENTITY_KEY table.Column VALUE [--source S] [--note N]"
            )
            return 1
        try:
            row = add_attribute(
                rest[0], rest[1], rest[2], source=_arg(rest, "--source"), note=_arg(rest, "--note")
            )
        except ValueError as e:
            print(f"refused: {e}")
            return 1
        print(f"manual attribute {row['entity_key']} {row['attribute']} = {row['value']} recorded")
        return 0
    if sub == "add-note":
        if len(rest) < 2:
            print("usage: manual add-note ENTITY_KEY TEXT [--source S]")
            return 1
        row = add_note(rest[0], rest[1], source_url=_arg(rest, "--source"))
        print(f"manual note {row['note_id']} recorded")
        return 0
    if sub == "list":
        return _list(rest[0] if rest else None)
    if sub == "validate":
        problems = sweep()
        for p in problems:
            print(f"  PROBLEM {p}")
        print(f"manual validate: {len(problems)} problems")
        return 0 if not problems else 1
    if sub == "export":
        export(rest[0] if rest else None)
        return 0
    if sub == "load":
        r = load(rest[0] if rest else None)
        return 0 if r["status"] == "ok" else 1
    print(f"unknown manual subcommand: {sub}")
    return 1
