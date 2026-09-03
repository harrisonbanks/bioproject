# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_store.py
"""Unit tests for the DuckDB store layer, validate_db and migrate (gate 0.2).

Every test uses its own database file under tmp_path; config paths are
redirected with monkeypatch so nothing touches data/.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from biointel import config, schema, store


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(config, "SNAPSHOTS", tmp_path / "snapshots")
    monkeypatch.setattr(config, "SILVER_CSV_SRC", tmp_path / "silver")
    monkeypatch.setattr(config, "GOLD_CSV_SRC", tmp_path / "gold")
    monkeypatch.setattr(config, "SILVER", tmp_path / f"silver_frozen_{config.FROZEN_TAG}")
    monkeypatch.setattr(config, "GOLD", tmp_path / f"gold_frozen_{config.FROZEN_TAG}")
    store.close()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()


def _events(n=50):
    return [
        {
            "IID": str(i % 7),
            "Name": 'Acme "Q", Inc\nline2' if i % 5 == 0 else "Acme",
            "Event": "Approval" if i % 3 else "Rejection",
            "Date": "2024-01-15",
            "AppNo": f"N{i:06d}",
            "Drug": "x",
            "Outcome": "New drug" if i % 3 else "Never approved",
            "Priority": None,
            "ClassCode": 12.5 if i % 4 == 0 else "",
            "SubType": "",
        }
        for i in range(n)
    ]


def _csv_roundtrip(rows, cols):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue(), list(csv.DictReader(io.StringIO(buf.getvalue())))


def test_write_read_identical_to_csv_layer(db):
    rows = _events()
    n = store.write_table("events", rows, schema.EVENT_COLS)
    text, ref = _csv_roundtrip(rows, schema.EVENT_COLS)
    assert n == len(rows)
    assert store.read_table("events") == ref
    assert store.table_columns("events") == list(schema.EVENT_COLS)


def test_export_csv_reproduces_bytes(db, tmp_path):
    rows = _events()
    store.write_table("events", rows, schema.EVENT_COLS)
    text, _ = _csv_roundtrip(rows, schema.EVENT_COLS)
    p = store.export_csv("events", tmp_path / "out" / "events.csv")
    assert p.read_bytes() == text.encode("utf-8")


def test_constraints_reject_and_roll_back(db):
    rows = _events()
    store.write_table("events", rows, schema.EVENT_COLS)
    with pytest.raises(Exception):
        store.write_table("events", [{**rows[0], "IID": "x"}], schema.EVENT_COLS)
    with pytest.raises(Exception):
        store.write_table("events", [rows[0], rows[0]], schema.EVENT_COLS)
    with pytest.raises(Exception):
        store.write_table("events", [{**rows[0], "Event": "Withdrawal"}], schema.EVENT_COLS)
    assert store.read_table("events") == _csv_roundtrip(rows, schema.EVENT_COLS)[1]


def test_undeclared_and_optional_columns(db):
    with pytest.raises(ValueError):
        store.write_table("relationships", [], list(schema.REL_COLS) + ["Rogue"])
    cols = list(schema.REL_COLS) + list(schema.REL_TYPED_COLS)
    store.write_table("relationships", [], cols)
    assert store.table_columns("relationships") == cols
    assert store.read_table("relationships") == []
    assert store.read_table("no_such_table") == []
    assert not store.has_table("no_such_table")


def test_typed_read_casts_per_schema(db):
    store.write_table("events", _events(3), schema.EVENT_COLS)
    r = store.read_table("events", typed=True)[0]
    assert r["IID"] == 0 and str(r["Date"]) == "2024-01-15" and r["Priority"] == ""


def test_validate_db_matches_csv_path(db):
    rows = _events()
    store.write_table("events", rows, schema.EVENT_COLS)
    res = {r["path"]: r for r in schema.validate_db(db)}
    assert res["events"]["status"] == "conformant" and res["events"]["rows"] == len(rows)
    assert res["companies"]["status"] == "absent"
    assert res["manual_notes"]["status"] == "absent"  # live since 2.10
    assert res["benchmarks"]["status"] == "planned"


def test_meta_table(db):
    keys = {k for (k,) in db.execute("SELECT key FROM meta").fetchall()}
    assert {"duckdb_version", "schema_version", "created_at"} <= keys


def _write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def test_migrate_loads_counts_renames_and_refuses(db, tmp_path):
    from biointel.migrate import migrate

    store.close()
    config.DUCKDB.unlink(missing_ok=True)
    ev = _events(20)
    _write_csv(tmp_path / "silver" / "events.csv", schema.EVENT_COLS, ev)
    _write_csv(
        tmp_path / "gold" / "pair_feature.csv",
        schema.PAIR_FEATURE_COLS,
        [{"IID": "1", "YearEnd": "2020-12-31", "MaxSimToAcq": "0.1234"}],
    )
    (tmp_path / "gold" / "old_report.txt").write_text("legacy", encoding="utf-8")
    r = migrate()
    assert r["status"] == "ok", r["message"]
    assert "events" in r["message"] and "20 rows (csv       20)" in r["message"]
    assert not (tmp_path / "silver").exists() and config.SILVER.exists()
    assert (config.GOLD / "old_report.txt").read_text() == "legacy"
    store.connect(config.DUCKDB)
    assert store.read_table("events") == _csv_roundtrip(ev, schema.EVENT_COLS)[1]
    assert len(store.read_table("pair_feature")) == 1
    store.close()
    r2 = migrate()
    assert r2["status"] == "refused"


def test_migrate_aborts_on_violation_and_removes_db(db, tmp_path):
    from biointel.migrate import migrate

    store.close()
    config.DUCKDB.unlink(missing_ok=True)
    bad = _events(3)
    bad[1]["Event"] = "Withdrawal"
    _write_csv(tmp_path / "silver" / "events.csv", schema.EVENT_COLS, bad)
    r = migrate()
    assert r["status"] == "fail" and "Withdrawal" in r["message"]
    assert not config.DUCKDB.exists()
    assert (tmp_path / "silver").exists()  # nothing renamed


# ---- store extension gate (2026-09-03): row updates and column adds ----
def test_update_rows_matches_by_declared_key_on_a_reserved_word_table(db):
    """`references` is a DuckDB reserved word. Identifiers come from the
    schema declaration and are quoted here, so the collision that produced a
    hand-written-SQL bug cannot recur."""
    rows = []
    for i in (1, 2, 3):
        r = dict.fromkeys(schema.REFERENCE_COLS, "")
        r.update(
            {
                "ref_id": f"R{i}",
                "ref_type": "sec_filing",
                "url": f"u{i}",
                "note": "before",
                "status": "active",
            }
        )
        rows.append(r)
    store.write_table("references", rows, schema.REFERENCE_COLS)

    n = store.update_rows("references", [{"ref_id": "R2", "note": "after"}])
    assert n == 1
    got = {r["ref_id"]: r["note"] for r in store.read_table("references")}
    assert got == {"R1": "before", "R2": "after", "R3": "before"}


def test_update_rows_refuses_bad_input(db):
    r = dict.fromkeys(schema.REFERENCE_COLS, "")
    r.update({"ref_id": "R1", "ref_type": "sec_filing", "status": "active"})
    store.write_table("references", [r], schema.REFERENCE_COLS)

    with pytest.raises(ValueError):
        store.update_rows("references", [{"note": "no key given"}])
    with pytest.raises(ValueError):
        store.update_rows("references", [{"ref_id": "R1", "not_a_column": "x"}])
    with pytest.raises(ValueError):
        store.update_rows("no_such_table", [{"ref_id": "R1", "note": "x"}])
    # a change touching no non-key column is a no-op, not an error
    assert store.update_rows("references", [{"ref_id": "R1"}]) == 0
    # an unmatched key changes nothing
    assert store.update_rows("references", [{"ref_id": "MISSING", "note": "x"}]) == 0


def test_add_columns_is_idempotent_and_rejects_undeclared(db):
    base = list(schema.EQUITY_STAKE_COLS)
    row = dict.fromkeys(base, "")
    row.update(
        {"holder_key": "CIK:1", "issuer_key": "CIK:2", "percent": "5", "as_of": "2020-01-01"}
    )
    store.write_table("equity_stakes", [row], base)

    optional = list(schema.EQUITY_STAKE_F1_COLS)
    added = store.add_columns("equity_stakes", base + optional)
    assert added == optional  # only the missing ones
    assert store.add_columns("equity_stakes", base + optional) == []  # idempotent
    with pytest.raises(ValueError):
        store.add_columns("equity_stakes", ["invented_column"])
