# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_forward.py
"""Gate 1.5a: forward FDA calendar writers."""

from __future__ import annotations

from datetime import date

import pytest

from biointel import config, forward, pipeline, schema, store

TODAY = date(2026, 8, 31)


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
    companies[0].update({"IID": "7", "Name": "Acme Pharma Inc", "Ticker": "ACME"})
    companies[1].update({"IID": "8", "Name": "Bolt Bio", "Ticker": "BOLT"})
    store.write_table("companies", companies, schema.COMPANY_COLS, con=con)
    trials = []
    # trials.PrimaryCompletion is a strict YYYY-MM-DD column (schema CHECK):
    # month-only CT.gov dates were normalized at ingest, so precision is day
    for nct, pc, phase in (
        ("NCT01", "2027-03-15", "PHASE3"),
        ("NCT02", "2026-11-14", "PHASE2"),
        ("NCT03", "2024-01-10", "PHASE3"),
        ("NCT04", "", "PHASE1"),
    ):
        t = {c: "" for c in schema.TRIAL_COLS}
        t.update(
            {
                "IID": "7",
                "Company": "Acme Pharma Inc",
                "NCTId": nct,
                "Phase": phase,
                "Status": "RECRUITING",
                "Conditions": "Migraine",
                "Drugs": "acmezumab",
                "PrimaryCompletion": pc,
                "CollaboratorCount": "0",
            }
        )
        trials.append(t)
    store.write_table("trials", trials, schema.TRIAL_COLS, con=con)
    events = [
        {
            "IID": "7",
            "Name": "Acme",
            "Event": "Approval",
            "Date": "2024-03-01",
            "AppNo": "NDA1",
            "Drug": "acmezumab",
            "Outcome": "New drug",
            "Priority": "",
            "ClassCode": "",
            "SubType": "ORIG",
        }
    ]
    store.write_table("events", events, schema.EVENT_COLS, con=con)
    pipeline.build_events_table()
    yield con
    store.close()


# ---------------------------------------------------------------- dates
@pytest.mark.parametrize(
    "raw,exp",
    [
        ("2026-11-14", ("2026-11-14", "2026-11-14", "day")),
        ("2026-11", ("2026-11-01", "2026-11-30", "month")),
        ("2027", ("2027-01-01", "2027-12-31", "year")),
        ("Q4 2026", ("2026-10-01", "2026-12-31", "quarter")),
        ("the fourth quarter of 2026", ("2026-10-01", "2026-12-31", "quarter")),
        ("H2 2026", ("2026-07-01", "2026-12-31", "half")),
        ("second half of 2026", ("2026-07-01", "2026-12-31", "half")),
        ("November 14, 2026", ("2026-11-14", "2026-11-14", "day")),
        ("November 2026", ("2026-11-01", "2026-11-30", "month")),
        ("", None),
        ("soon", None),
    ],
)
def test_parse_date_range(raw, exp):
    assert forward.parse_date_range(raw) == exp


def test_business_days_before_skips_weekend():
    # 2026-09-14 is a Monday; two business days before is Thursday 09-10
    assert forward.business_days_before("2026-09-14", 2) == "2026-09-10"


# ---------------------------------------------------------------- schema
def test_forward_columns_declared_optional_with_enums():
    t = schema.TABLE_BY_PATH["silver/events_table.csv"]
    for c in schema.EVENT_FORWARD_COLS:
        assert c in t.optional
    assert "quarter" in t.enums["date_precision"]
    assert "superseded" in t.enums["status"]


# ---------------------------------------------------------------- trials writer
def test_trials_writer_only_future_rows_with_precision_and_estimate_label(env):
    r = forward.write_trials(today=TODAY)
    assert r["candidates"] == 2 and r["inserted"] == 2
    rows = [x for x in store.read_table("events_table", con=env) if x["scheduled_date"]]
    by_nct = {forward._trial_identity(x): x for x in rows}
    m = next(x for x in rows if "NCT01" in x["provenance"])
    assert m["scheduled_date"] == "2027-03-15" and m["scheduled_date_end"] == "2027-03-15"
    assert m["date_precision"] == "day" and m["date_raw"] == "2027-03-15"
    assert m["event_class"] == "clinical_readout"
    assert m["outcome_subtype"] == "estimated_primary_completion"
    assert m["confidence_tier"] == "C" and m["event_date"] == ""
    assert m["source_url"] == "https://clinicaltrials.gov/study/NCT01"
    d = next(x for x in rows if "NCT02" in x["provenance"])
    assert d["date_precision"] == "day"
    assert not any("NCT03" in x["provenance"] for x in rows)  # past
    assert len(by_nct) == 2


def test_trials_writer_rerun_refreshes_and_moved_date_supersedes(env):
    forward.write_trials(today=TODAY)
    r2 = forward.write_trials(today=TODAY)
    assert r2["inserted"] == 0 and r2["refreshed"] == 2 and r2["superseded"] == 0
    # move NCT01's primary completion
    trials = store.read_table("trials", con=env)
    for t in trials:
        if t["NCTId"] == "NCT01":
            t["PrimaryCompletion"] = "2027-06-15"
    store.write_table("trials", trials, schema.TRIAL_COLS, con=env)
    r3 = forward.write_trials(today=TODAY)
    assert r3["inserted"] == 1 and r3["superseded"] == 1
    rows = [x for x in store.read_table("events_table", con=env) if "NCT01" in x["provenance"]]
    assert sorted((x["scheduled_date"], x["status"]) for x in rows) == [
        ("2027-03-15", "superseded"),
        ("2027-06-15", ""),
    ]


def test_migrated_rows_untouched_and_events_migrate_keeps_forward_rows(env):
    forward.write_trials(today=TODAY)
    before = [x for x in store.read_table("events_table", con=env) if x["event_date"]]
    assert len(before) == 1
    r = pipeline.build_events_table()
    assert r["rows"] == 3  # 1 migrated + 2 forward kept
    after = store.read_table("events_table", con=env)
    assert sum(1 for x in after if x["scheduled_date"] and not x["event_date"]) == 2


# ---------------------------------------------------------------- adcom
# Fixture = verbatim records excerpted from the real endpoint response
# captured 2026-08-31 (https://www.fda.gov/datatables-json/advisory-committee-calendar-json),
# plus the same two upcoming records with a company name appended to prove
# entity matching. No synthetic markup.
ADCOM_JSON = r"""[
    {
        "field_start_date": "09\/16\/2026 10:00 AM EDT",
        "field_end_date": "09\/16\/2026 04:00 PM EDT",
        "title": "\u003Ca href=\u0022\/advisory-committees\/advisory-committee-calendar\/pediatric-advisory-committee-meeting-announcement-09162026\u0022 hreflang=\u0022en\u0022\u003EPediatric Advisory Committee Meeting Announcement - 09\/16\/2026\u003C\/a\u003E",
        "field_contributing_office": "",
        "field_center": "Office of the Commissioner",
        "changed": "\u003Ctime datetime=\u00222026-08-03T10:05:47-04:00\u0022\u003EMon, 08\/03\/2026 - 10:05\u003C\/time\u003E\n"
    },
    {
        "field_start_date": "09\/23\/2026 09:00 AM EDT",
        "field_end_date": "09\/23\/2026 06:00 PM EDT",
        "title": "\u003Ca href=\u0022\/advisory-committees\/advisory-committee-calendar\/september-23-2026-molecular-and-clinical-genetics-panel-medical-devices-advisory-committee-meeting\u0022 hreflang=\u0022en\u0022\u003ESeptember 23, 2026: Molecular and Clinical Genetics Panel of the Medical Devices Advisory Committee (Acme Pharma) Meeting Announcement - 09\/23\/2026\u003C\/a\u003E",
        "field_contributing_office": "",
        "field_center": "Center for Devices and Radiological Health",
        "changed": "\u003Ctime datetime=\u00222026-08-07T10:04:46-04:00\u0022\u003EFri, 08\/07\/2026 - 10:04\u003C\/time\u003E\n"
    },
    {
        "field_start_date": "07\/23\/2026 08:00 AM EDT",
        "field_end_date": "07\/24\/2026 03:50 PM EDT",
        "title": "\u003Ca href=\u0022\/advisory-committees\/advisory-committee-calendar\/july-23-24-2026-meeting-pharmacy-compounding-advisory-committee-07232026\u0022 hreflang=\u0022en\u0022\u003EJuly 23-24, 2026: Meeting of the Pharmacy Compounding Advisory Committee - 07\/23\/2026\u003C\/a\u003E",
        "field_contributing_office": "",
        "field_center": "Center for Drug Evaluation and Research",
        "changed": "\u003Ctime datetime=\u00222026-08-06T15:47:50-04:00\u0022\u003EThu, 08\/06\/2026 - 15:47\u003C\/time\u003E\n"
    },
    {
        "field_start_date": "05\/16\/2024 08:30 AM EDT",
        "field_end_date": "05\/16\/2024 04:30 PM EDT",
        "title": "\u003Ca href=\u0022\/advisory-committees\/advisory-committee-calendar\/postponed-vaccines-and-related-biological-products-advisory-committee-may-16-2024-meeting\u0022 hreflang=\u0022en\u0022\u003EPOSTPONED - Vaccines and Related Biological Products Advisory Committee May 16, 2024 Meeting Announcement - 05\/16\/2024\u003C\/a\u003E",
        "field_contributing_office": "",
        "field_center": "Center for Biologics Evaluation and Research",
        "changed": "\u003Ctime datetime=\u00222024-05-13T13:23:32-04:00\u0022\u003EMon, 05\/13\/2024 - 13:23\u003C\/time\u003E\n"
    },
    {
        "field_start_date": "",
        "field_end_date": "",
        "title": "\u003Ca href=\u0022\/advisory-committees\/advisory-committee-calendar\/november-9-10-2016-microbiology-devices-panel-medical-devices-advisory-committee-meeting\u0022 hreflang=\u0022en\u0022\u003ENovember 9-10, 2016: Microbiology Devices Panel of the Medical Devices Advisory Committee Meeting Announcement -\u003C\/a\u003E",
        "field_contributing_office": "",
        "field_center": "Center for Drug Evaluation and Research",
        "changed": "\u003Ctime datetime=\u00222024-03-07T19:57:08-05:00\u0022\u003EThu, 03\/07\/2024 - 19:57\u003C\/time\u003E\n"
    }
]"""


def test_parse_adcom_json_real_records():
    recs = forward.parse_adcom_json(ADCOM_JSON)
    assert len(recs) == 5
    ped = next(r for r in recs if "09162026" in r["url"])
    assert ped["start"] == "2026-09-16" and ped["end"] == "2026-09-16"
    assert ped["url"] == (
        "https://www.fda.gov/advisory-committees/advisory-committee-calendar/"
        "pediatric-advisory-committee-meeting-announcement-09162026"
    )
    assert ped["title"].startswith("Pediatric Advisory Committee Meeting Announcement")
    assert ped["center"] == "Office of the Commissioner"
    pcac = next(r for r in recs if "07232026" in r["url"])
    assert pcac["start"] == "2026-07-23" and pcac["end"] == "2026-07-24"  # multi-day
    post = next(r for r in recs if "postponed" in r["url"])
    assert post["cancelled"] is True
    blank = next(r for r in recs if "november-9-10-2016" in r["url"])
    assert blank["start"] == "2016-11-09" and blank["end"] == "2016-11-10"  # from title


def test_adcom_writer_forward_only_two_rows_per_meeting_with_entity_match(env):
    r = forward.write_adcom(text=ADCOM_JSON, today=TODAY)
    assert r["records"] == 5 and r["meetings"] == 2 and r["inserted"] == 4
    rows = [
        x
        for x in store.read_table("events_table", con=env)
        if x["event_class"] == "regulatory_meeting"
    ]
    assert len(rows) == 4
    meet = next(
        x for x in rows if x["outcome_subtype"] == "meeting" and "09162026" in x["source_url"]
    )
    assert meet["scheduled_date"] == "2026-09-16" and meet["confidence_tier"] == "A"
    assert meet["date_precision"] == "day" and meet["event_date"] == ""
    assert meet["entity_key"] == ""  # no company named
    brief = next(
        x
        for x in rows
        if x["outcome_subtype"] == "briefing_documents" and "09162026" in x["source_url"]
    )
    assert brief["scheduled_date"] == "2026-09-14" and brief["confidence_tier"] == "B"  # Wed -> Mon
    mcg = next(
        x
        for x in rows
        if x["outcome_subtype"] == "meeting" and "september-23-2026" in x["source_url"]
    )
    assert mcg["entity_key"] == "7"  # Acme Pharma named in the title
    assert "center=Center for Devices and Radiological Health" in mcg["provenance"]
    r2 = forward.write_adcom(text=ADCOM_JSON, today=TODAY)
    assert r2["inserted"] == 0 and r2["refreshed"] == 4
