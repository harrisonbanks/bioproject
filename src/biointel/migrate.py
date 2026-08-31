# src/biointel/migrate.py
"""One-time migration of the pre-migration CSV folders into the database (P16).

Behaviour (decisions 2026-08-30):
  * Refuses to run if the database file already exists (safety rule): a
    deliberate re-migration requires deleting the file by hand first.
  * Reads every declared table present under data/silver and data/gold,
    validates it against schema.py, and loads it with store.write_table,
    which enforces the same declaration as database constraints.
  * Prints one line per table: rows loaded versus rows in the CSV; they
    must be equal.
  * Renames data/silver -> data/silver_frozen_<tag> and data/gold ->
    data/gold_frozen_<tag>; legacy code reads those frozen copies, live
    code never touches them again.

A new machine does not use this command: it rebuilds from the sources,
and the first table write creates the database.
"""

from __future__ import annotations

import csv

from biointel import config, schema, store


def _csv_source(t: schema.Table):
    layer, fname = t.path.split("/", 1)
    root = config.SILVER_CSV_SRC if layer == "silver" else config.GOLD_CSV_SRC
    return root / fname


def migrate() -> dict:
    assert config.SILVER_CSV_SRC == config.DATA / "silver"
    assert config.GOLD_CSV_SRC == config.DATA / "gold"
    if config.DUCKDB.exists():
        return {
            "status": "refused",
            "message": (
                f"{config.DUCKDB} already exists; migrate makes no change. "
                "To re-migrate deliberately, delete that file by hand first."
            ),
        }
    if not config.SILVER_CSV_SRC.exists() and not config.GOLD_CSV_SRC.exists():
        return {
            "status": "empty",
            "message": (
                f"Neither {config.SILVER_CSV_SRC} nor {config.GOLD_CSV_SRC} exists; "
                "nothing to migrate (a new machine rebuilds from the sources)."
            ),
        }
    for frozen in (config.SILVER, config.GOLD):
        if frozen.exists():
            return {
                "status": "fail",
                "message": f"{frozen} already exists but the database does not; resolve by hand.",
            }

    lines: list[str] = []
    problems: list[str] = []
    loaded: list[tuple[str, int, int]] = []
    con = store.connect()
    for t in schema.TABLES:
        if t.planned:
            continue
        src = _csv_source(t)
        name = store.table_name(t.path)
        if not src.exists():
            lines.append(f"  absent    {name}")
            continue
        check = schema.validate_table(t, config.DATA)  # DATA/silver/x.csv, DATA/gold/x.csv
        if check["status"] == "violations":
            problems.append(f"{name}: " + "; ".join(check["violations"][:3]))
            lines.append(f"  VIOLATION {name} (not loaded)")
            continue
        with src.open(encoding="utf-8", newline="", errors="replace") as f:
            rd = csv.DictReader(f)
            header = list(rd.fieldnames or [])
            rows = list(rd)
        n = store.write_table(name, rows, header, con=con)
        m = len(rows)
        loaded.append((name, n, m))
        flag = "" if n == m else "   <-- COUNT MISMATCH"
        lines.append(f"  loaded    {name:<24} {n:>8,} rows (csv {m:>8,}){flag}")
    if problems:
        store.close()
        config.DUCKDB.unlink(missing_ok=True)
        return {
            "status": "fail",
            "message": "\n".join(lines)
            + "\nmigrate aborted; database removed. Violations:\n  - "
            + "\n  - ".join(problems),
        }
    con.execute(
        "INSERT INTO meta VALUES ('migrated_from', ?) ON CONFLICT DO UPDATE SET value = excluded.value",
        [f"{config.SILVER_CSV_SRC.name},{config.GOLD_CSV_SRC.name}@{config.FROZEN_TAG}"],
    )
    store.close()
    if config.SILVER_CSV_SRC.exists():
        config.SILVER_CSV_SRC.rename(config.SILVER)
    if config.GOLD_CSV_SRC.exists():
        config.GOLD_CSV_SRC.rename(config.GOLD)
    mism = [x for x in loaded if x[1] != x[2]]
    lines.append(
        f"migrate: {len(loaded)} tables loaded into {config.DUCKDB.name}; "
        f"{len(mism)} count mismatches; CSV folders renamed to "
        f"{config.SILVER.name} and {config.GOLD.name} (legacy read-only)."
    )
    return {"status": "ok" if not mism else "fail", "message": "\n".join(lines)}
