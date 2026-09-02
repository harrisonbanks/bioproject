# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_widening.py
"""Gate 2.9': universe widening — private stubs, verified-row IID resolution,
manual ma_events overrides applied at the labels rebuild."""

from __future__ import annotations

import pytest

from biointel import config, labels, manual, pipeline, schema, store


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
    companies[0].update(
        {"IID": "0", "Name": "Personalis, Inc.", "Ticker": "PSNL", "CIK": "1527753"}
    )
    companies[1].update({"IID": "1", "Name": "Tempus AI, Inc.", "Ticker": "TEM", "CIK": "1717115"})
    store.write_table("companies", companies, schema.COMPANY_COLS, con=con)
    yield con
    store.close()


def test_private_stub_gets_iid_and_private_marker(env):
    r = pipeline.add_company_stub("Deep 6 AI", description="private; acquired by Tempus 2025")
    assert r["status"] == "added" and r["iid"] == 2
    rows = pipeline.read_companies()
    stub = next(x for x in rows if x["Name"] == "Deep 6 AI")
    assert stub["Exchange"] == "private" and stub["Ticker"] == ""
    # dedup by name
    assert pipeline.add_company_stub("deep 6 ai")["status"] == "duplicate"


def test_verified_overlay_row_resolves_counterparty_iid_and_manual_deal_id(env):
    ver = [{c: "" for c in schema.VERIFIED_COLS}]
    ver[0].update(
        {
            "FilerTicker": "PSNL",
            "AnnounceDate": "2026-07-20",
            "Acquirer": "Tempus AI, Inc.",
            "Status": "announced/pending",
            "Note": "seed dossier deal",
            "Source": "8-K 2026-07-21",
        }
    )
    store.write_table("ma_events_verified", ver, schema.VERIFIED_COLS, con=env)
    manual.add_attribute(
        "PSNL|2026-07-20", "ma_events.deal_id", "TEM-PSNL-20260720", source="dossier"
    )
    events = labels.merged_events(pipeline.read_companies, lambda: [], lambda: [])
    # written exactly as the labels CLI writes it: the optional column must survive
    from biointel.labels import MA_COLS as CLI_MA_COLS  # the CLI's own import (a list)

    store.write_table("ma_events", events, [*CLI_MA_COLS, "deal_id"], con=env)
    row = next(
        e for e in store.read_table("ma_events", con=store.connect()) if e["FilerTicker"] == "PSNL"
    )
    assert row["Verified"] == "yes" and row["Role"] == "target"
    assert str(row["CounterpartyIID"]) == "1"  # Tempus resolved through the registry
    assert row["deal_id"] == "TEM-PSNL-20260720"  # 2.10's manual override survives the write
    assert str(row["AnnounceDate"])[:10] == "2026-07-20"
