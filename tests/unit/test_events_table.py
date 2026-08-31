# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_events_table.py
"""Gate 1.4: event table + forward FDA calendar view (Ontology v5 §3.6).

Covers: the schema declaration (event_date present, scheduled_date kept for
goal dates, event_class vocabulary complete incl. the v4 classes), the
events -> events_table migration mapping and its idempotence, validate_db
conformance, and the calendar view (trials + FDA past + empty forward rows,
with a forward row appearing once inserted).
"""

from __future__ import annotations

import pytest

from biointel import config, pipeline, schema, store

EVENTS_FIXTURE = [
    {
        "IID": "7",
        "Name": "Acme Pharma",
        "Event": "Approval",
        "Date": "2024-03-01",
        "AppNo": "NDA211675",
        "Drug": "Acmezumab",
        "Outcome": "New drug",
        "Priority": "PRIORITY",
        "ClassCode": "",
        "SubType": "ORIG",
    },
    {
        "IID": "7",
        "Name": "Acme Pharma",
        "Event": "Rejection",
        "Date": "2022-11-15",
        "AppNo": "NDA209999",
        "Drug": "",
        "Outcome": "Later approved",
        "Priority": "",
        "ClassCode": "Complete Response",
        "SubType": "",
    },
]

TRIALS_FIXTURE = [
    {
        "IID": "7",
        "Company": "Acme Pharma",
        "NCTId": "NCT01234567",
        "Sponsor": "Acme Pharma",
        "SponsorClass": "INDUSTRY",
        "Title": "A study",
        "Phase": "PHASE3",
        "Status": "RECRUITING",
        "StudyType": "INTERVENTIONAL",
        "Conditions": "Migraine",
        "Drugs": "Acmezumab",
        "Interventions": "Acmezumab",
        "Enrollment": "100",
        "Collaborators": "",
        "CollaboratorClasses": "",
        "CollaboratorCount": "0",
        "StartDate": "2021-05-01",
        "PrimaryCompletion": "2023-05-01",
        "CompletionDate": "2023-08-01",
        "LastUpdate": "2023-09-01",
    }
]


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
    store.write_table("events", EVENTS_FIXTURE, schema.EVENT_COLS, con=con)
    store.write_table("trials", TRIALS_FIXTURE, schema.TRIAL_COLS, con=con)
    yield con
    store.close()


# ---------------------------------------------------------------- schema
def test_event_table_declaration_carries_both_date_columns():
    assert "event_date" in schema.EVENT_TABLE_COLS
    assert "scheduled_date" in schema.EVENT_TABLE_COLS
    t = schema.TABLE_BY_PATH["silver/events_table.csv"]
    assert not t.planned
    assert t.key == ("event_id",)
    assert t.types["event_date"] == "date"
    assert t.types["scheduled_date"] == "date"


def test_event_class_vocabulary_complete_including_v4_classes():
    t = schema.TABLE_BY_PATH["silver/events_table.csv"]
    allowed = t.enums["event_class"]
    for cls in (
        "regulatory_decision",
        "reimbursement_decision",
        "regulatory_clearance_non_fda",
        "acquisition_announced",
        "acquisition_closed",
        "acquisition_terminated",
        "stake_purchase",
        "takeover_interest_reported",
    ):
        assert cls in allowed
    assert allowed == tuple(schema.EVENT_CLASSES)


# ---------------------------------------------------------------- migration
def test_migration_row_count_and_mapping(env):
    r = pipeline.build_events_table()
    assert r["status"] == "ok"
    assert r["rows"] == r["source"] == len(EVENTS_FIXTURE)
    rows = store.read_table("events_table", con=env)
    assert len(rows) == len(EVENTS_FIXTURE)
    by_ref = {pipeline._prov_get(x["provenance"], "AppNo"): x for x in rows}
    ap = by_ref["NDA211675"]
    assert ap["event_class"] == "regulatory_decision"
    assert ap["outcome_state"] == "approval"
    assert ap["outcome_subtype"] == "New drug"
    assert ap["event_date"] == "2024-03-01"
    assert ap["scheduled_date"] == ""  # realized dates never enter scheduled_date
    assert ap["asset"] == "Acmezumab"
    assert pipeline._prov_get(ap["provenance"], "SubType") == "ORIG"
    cr = by_ref["NDA209999"]
    assert cr["outcome_state"] == "crl"
    assert cr["outcome_subtype"] == "Later approved"
    assert cr["event_date"] == "2022-11-15"
    assert pipeline._prov_get(cr["provenance"], "ClassCode") == "Complete Response"


def test_migration_is_idempotent_with_deterministic_event_ids(env):
    pipeline.build_events_table()
    first = {r["event_id"] for r in store.read_table("events_table", con=env)}
    r2 = pipeline.build_events_table()
    second = {r["event_id"] for r in store.read_table("events_table", con=env)}
    assert r2["rows"] == len(EVENTS_FIXTURE)
    assert first == second


def test_migration_records_a_ledger_run(env):
    r = pipeline.build_events_table()
    runs = store.read_table("runs", con=env)
    assert any(x["run_id"] == r["run_id"] and x["command"] == "events-migrate" for x in runs)


def test_validate_db_reports_events_table_conformant(env):
    pipeline.build_events_table()
    results = {x["path"]: x for x in schema.validate_db(env)}
    assert results["events_table"]["status"] == "conformant"
    assert results["events_table"]["rows"] == len(EVENTS_FIXTURE)


# ---------------------------------------------------------------- calendar view
def test_calendar_view_serves_trials_plus_fda_plus_empty_forward(env):
    pipeline.build_events_table()
    rows = pipeline.pipeline_calendar(7)
    sources = [r["Source"] for r in rows]
    assert "CT.gov" in sources
    assert sources.count("FDA") == len(EVENTS_FIXTURE)
    assert sources.count("FDA forward") == 0
    fda = next(r for r in rows if r["Source"] == "FDA" and r["Ref"] == "NDA211675")
    assert fda["Stage"] == "FDA Approval"
    assert fda["Date"] == "2024-03-01"
    assert fda["Status"] == "ORIG"


def test_calendar_view_shows_a_forward_row_when_one_exists(env):
    pipeline.build_events_table()
    rows = store.read_table("events_table", con=env)
    fwd = {c: "" for c in schema.EVENT_TABLE_COLS}
    fwd.update(
        {
            "event_id": "Eforwardfixture01",
            "entity_key": "7",
            "asset": "Acmezumab",
            "event_class": "regulatory_decision",
            "scheduled_date": "2027-01-31",
            "provenance": "table=fixture",
            "first_seen": "2026-08-31T00:00:00Z",
            "last_verified": "2026-08-31T00:00:00Z",
        }
    )
    store.write_table("events_table", rows + [fwd], schema.EVENT_TABLE_COLS, con=env)
    cal = pipeline.pipeline_calendar(7)
    fwd_rows = [r for r in cal if r["Source"] == "FDA forward"]
    assert len(fwd_rows) == 1
    assert fwd_rows[0]["Date"] == "2027-01-31"
    assert fwd_rows[0]["Stage"] == "FDA scheduled"


def test_calendar_falls_back_to_events_before_migration(env):
    rows = pipeline.pipeline_calendar(7)
    assert any(r["Source"] == "FDA (events)" for r in rows)
    assert not any(r["Source"] == "FDA" for r in rows)
