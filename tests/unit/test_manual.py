# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_manual.py
"""Gate 2.10: manual layer — DB-only store, precedence, export/load."""

from __future__ import annotations

import pytest

from biointel import config, manual, schema, store


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "bronze").mkdir(parents=True)
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(config, "BRONZE", data / "bronze")
    monkeypatch.setattr(config, "DUCKDB", data / "biointel.duckdb")
    monkeypatch.setattr(config, "EXPORTS", data / "exports")
    store.close()
    con = store.connect(config.DUCKDB)
    companies = [{c: "" for c in schema.COMPANY_COLS} for _ in range(2)]
    companies[0].update({"IID": "7", "Name": "Acme Pharma", "Ticker": "ACME"})
    companies[1].update({"IID": "8", "Name": "Bolt Bio", "Ticker": "BOLT"})
    store.write_table("companies", companies, schema.COMPANY_COLS, con=con)
    yield con
    store.close()


def test_manual_tables_declared_live():
    for path in (
        "silver/manual_entities.csv",
        "silver/manual_attributes.csv",
        "silver/manual_notes.csv",
    ):
        assert not schema.TABLE_BY_PATH[path].planned


def test_add_attribute_refuses_undeclared_targets(env):
    with pytest.raises(ValueError):
        manual.add_attribute("7", "companies.NoSuchColumn", "x")
    with pytest.raises(ValueError):
        manual.add_attribute("7", "not_a_table.Name", "x")
    with pytest.raises(ValueError):
        manual.add_attribute("7", "no-dot-form", "x")


def test_add_attribute_upserts_and_stamps_provenance(env):
    manual.add_attribute("7", "companies.Ticker", "ACME.X", source="issuer site")
    manual.add_attribute("7", "companies.Ticker", "ACME.Y", source="correction")
    rows = store.read_table("manual_attributes", con=env)
    assert len(rows) == 1
    assert rows[0]["value"] == "ACME.Y"
    assert rows[0]["entered_by"] and rows[0]["entered_on"]
    assert rows[0]["source"] == "correction"


def test_merged_rows_apply_manual_over_machine_visibly(env):
    manual.add_attribute("7", "companies.Ticker", "ACME.NEW", source="s")
    rows, applied = manual.merged_rows("companies")
    by_iid = {r["IID"]: r for r in rows}
    assert by_iid["7"]["Ticker"] == "ACME.NEW"  # manual wins
    assert by_iid["8"]["Ticker"] == "BOLT"  # untouched
    assert applied == [{"entity_key": "7", "column": "Ticker", "value": "ACME.NEW", "source": "s"}]


def test_entities_and_notes_round(env):
    manual.add_entity("PRIV:DEEP6", "Deep 6 AI", type="private", source="press")
    manual.add_note("PRIV:DEEP6", "acquired by Tempus per FY2025 annual report")
    ents = store.read_table("manual_entities", con=env)
    notes = store.read_table("manual_notes", con=env)
    assert ents[0]["entity_key"] == "PRIV:DEEP6" and ents[0]["name"] == "Deep 6 AI"
    assert notes[0]["note_id"] == "N000001" and notes[0]["entity_key"] == "PRIV:DEEP6"


def test_sweep_flags_targets_orphaned_by_schema_moves(env):
    manual.add_attribute("7", "companies.Ticker", "X")
    assert manual.sweep() == []
    con = env
    rows = store.read_table("manual_attributes", con=con)
    rows[0]["attribute"] = "companies.GoneColumn"
    store.write_table("manual_attributes", rows, schema.MANUAL_ATTRIBUTE_COLS, con=con)
    problems = manual.sweep()
    assert len(problems) == 1 and "GoneColumn" in problems[0]


def test_export_load_round_trip_covers_manual_and_dossier_tables(env):
    manual.add_attribute("7", "companies.Ticker", "ACME.NEW", source="s")
    manual.add_entity("PRIV:DEEP6", "Deep 6 AI")
    dt = [{c: "" for c in schema.DEAL_TERM_COLS}]
    dt[0].update(
        {
            "deal_id": "TEM-PSNL-20260720",
            "field": "price_per_share_usd",
            "value": "16.25",
            "doc_id": "a" * 64,
            "span": "$16.25",
        }
    )
    store.write_table("deal_terms", dt, schema.DEAL_TERM_COLS, con=env)
    r = manual.export()
    assert r["rows"] == 3
    # wipe the hand tables (a rebuild-from-bronze does exactly this)
    for t in manual.HAND_TABLES:
        store.write_table(t, [], manual._COLS[t], con=env)
    assert store.read_table("deal_terms", con=env) == []
    r2 = manual.load()
    assert r2["status"] == "ok" and r2["rows"] == 3
    assert store.read_table("deal_terms", con=env)[0]["value"] == "16.25"
    assert store.read_table("manual_attributes", con=env)[0]["value"] == "ACME.NEW"
    # idempotent
    r3 = manual.load()
    assert r3["rows"] == 3
    runs = store.read_table("runs", con=env)
    assert sum(1 for x in runs if x["command"] == "manual load") == 2


def test_load_without_export_file_is_a_clean_miss(env):
    r = manual.load()
    assert r["status"] == "missing" and r["rows"] == 0
