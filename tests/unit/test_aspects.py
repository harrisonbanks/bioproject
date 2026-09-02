# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_aspects.py
"""Gate L4 tests: aspect presence rules on fixture rows, the Tempus-sequence
exclusion, midpoint tie ranking, and both evaluations end to end through the
registry harness with per-aspect coverage recorded as ledger metrics."""

from __future__ import annotations

import pytest

from biointel import aspects, config, results, schema, store
from biointel.models.harness import run_command


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(config, "BRONZE", tmp_path / "bronze")
    store.close()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()


def _co(iid, name, ticker, cik):
    return {
        "IID": str(iid),
        "Name": name,
        "Ticker": ticker,
        "Created": "2020-01-01",
        "Description": "",
        "CIK": cik,
        "SIC": "2836",
        "SICDescription": "",
        "Exchange": "NASDAQ",
        "StateOfIncorporation": "",
        "FDAAliases": "",
        "CTGovName": "",
    }


def _trial(iid, blob, start="2018-01-01"):
    base = dict.fromkeys(schema.TRIAL_COLS, "")
    base.update(
        {
            "IID": str(iid),
            "NCTId": f"NCT{iid}{abs(hash(blob)) % 10_000}",
            "Conditions": blob,
            "Interventions": "",
            "Drugs": "",
            "StartDate": start,
        }
    )
    return base


def _seed_world(extra_events=()):
    """Buyer 1 (large, related to 2), candidates 2/3/4; one 2023 deal 1->2."""
    tok_a = "oncology melanoma checkpoint inhibitor biomarker immunotherapy tumor antigen"
    tok_b = "oncology melanoma checkpoint inhibitor biomarker immunotherapy tumor antigen"
    tok_c = "cardiology valve stent perfusion arrhythmia catheter imaging ablation"
    tok_d = "neurology synapse dopamine cognition receptor plasticity axon myelin"
    store.write_table(
        "companies",
        [
            _co(1, "BigPharma Inc", "BIG", "1000001"),
            _co(2, "TargetBio Inc", "TGB", "1000002"),
            _co(3, "CardioCo Inc", "CRD", "1000003"),
            _co(4, "NeuroCo Inc", "NRC", "1000004"),
        ],
        schema.COMPANY_COLS,
    )
    store.write_table(
        "trials",
        [_trial(1, tok_a), _trial(2, tok_b), _trial(3, tok_c), _trial(4, tok_d)],
        schema.TRIAL_COLS,
    )
    fp_cols = schema.TABLE_BY_PATH["gold/feature_panel.csv"].columns
    fp = []
    for iid, rev in (("1", "9e9"), ("2", "1e8")):
        row = dict.fromkeys(fp_cols, "")
        row.update({"IID": iid, "QuarterEnd": "2022-12-31", "Revenue": rev, "TTMBasis": ""})
        fp.append(row)
    store.write_table("feature_panel", fp, fp_cols)
    rel = dict.fromkeys(schema.REL_COLS, "")
    rel.update(
        {
            "IID": "1",
            "Ticker": "BIG",
            "Company": "BigPharma Inc",
            "Partner": "TargetBio Inc",
            "PartnerKey": "targetbio",
            "PartnerIID": "2",
            "PartnerType": "Industry",
            "RelKind": "Deal",
            "AgreementType": "License",
            "Count": "1",
            "FirstDate": "2021-05-01",
            "LastDate": "2021-05-01",
        }
    )
    store.write_table("relationships", [rel], schema.REL_COLS)
    store.write_table(
        "equity_stakes",
        [
            {
                "holder_key": "CIK:0001000001",
                "issuer_key": "CIK:1000002",
                "percent": "12.5",
                "as_of": "2022-06-30",
                "doc_id": "d" * 64,
                "span": "12.5%",
            },
            {
                "holder_key": "CIK:9999999",
                "issuer_key": "CIK:1000002",
                "percent": "9.0",
                "as_of": "2022-06-30",
                "doc_id": "d" * 64,
                "span": "9.0%",
            },
        ],
        schema.EQUITY_STAKE_COLS,
    )
    store.write_table(
        "stated_priorities",
        [
            {
                "entity_key": "CIK:1000001",
                "stated_at": "2022-08-01",
                "category": "mrd",
                "statement": "s",
                "doc_id": "d" * 64,
                "span": "mrd",
            }
        ],
        schema.STATED_PRIORITY_COLS,
    )
    store.write_table(
        "assets",
        [
            {
                "entity_key": "CIK:1000001",
                "product": "Dx",
                "category": "diagnostics",
                "continuum_step": "diagnosis",
                "modality": "",
                "indications": "",
                "regulatory_status": "",
                "reimbursement_status": "",
                "doc_id": "d" * 64,
                "span": "x",
            },
            {
                "entity_key": "CIK:1000002",
                "product": "MRD",
                "category": "mrd",
                "continuum_step": "monitoring",
                "modality": "",
                "indications": "",
                "regulatory_status": "",
                "reimbursement_status": "",
                "doc_id": "d" * 64,
                "span": "x",
            },
        ],
        schema.ASSET_COLS,
    )
    ma = [dict.fromkeys([*schema.MA_COLS, "deal_id"], "") for _ in range(1 + len(extra_events))]
    ma[0].update(
        {
            "FilerIID": "2",
            "Filer": "TargetBio Inc",
            "FilerTicker": "TGB",
            "Role": "target",
            "Counterparty": "BigPharma Inc",
            "CounterpartyIID": "1",
            "AnnounceDate": "2023-06-01",
            "Status": "announced",
            "Confidence": "3",
            "Verified": "yes",
            "VerifiedAcquirer": "BigPharma Inc",
        }
    )
    for row, ex in zip(ma[1:], extra_events):
        row.update(ex)
    store.write_table("ma_events", ma, [*schema.MA_COLS, "deal_id"])
    store.write_table("events", [], schema.EVENT_COLS)


def test_presence_rules_and_coverage(db, monkeypatch):
    _seed_world()
    monkeypatch.setattr(aspects, "_loe", lambda cutoff: {"1": (3, 2, 0.67)})
    ctx = aspects.build_ctx("2022-12-31")
    got = aspects.pair_aspects("1", "2", ctx)
    for a in (
        "therapeutic_area_overlap",
        "prior_commercial_relationship",
        "patent_cliff_pressure",
        "buyer_financing_capacity",
        "prior_equity_stake",
        "competing_stakeholder",
        "buyer_stated_priority_match",
        "continuum_extension",
    ):
        assert got[a] == (True, True), a
    far = aspects.pair_aspects("1", "3", ctx)
    assert far["therapeutic_area_overlap"] == (True, False)
    assert far["prior_commercial_relationship"] == (True, False)
    assert far["prior_equity_stake"] == (True, False)
    assert far["competing_stakeholder"] == (True, False)  # no stake rows on IID 3
    assert aspects.pair_score("1", "2", ctx) == 8
    # Orange Book zip absent: patent_cliff_pressure not evaluable, never a silent zero
    monkeypatch.setattr(aspects, "_loe", lambda cutoff: None)
    ctx2 = aspects.build_ctx("2022-12-31")
    assert aspects.pair_aspects("1", "2", ctx2)["patent_cliff_pressure"] == (False, False)


def test_undated_relationship_edge_does_not_count(db, monkeypatch):
    _seed_world()
    rows = store.read_table("relationships")
    rows[0]["FirstDate"] = ""
    store.write_table("relationships", rows, schema.REL_COLS)
    monkeypatch.setattr(aspects, "_loe", lambda cutoff: None)
    ctx = aspects.build_ctx("2022-12-31")
    assert aspects.pair_aspects("1", "2", ctx)["prior_commercial_relationship"] == (True, False)


def test_tempus_sequence_exclusion(db):
    _seed_world(
        extra_events=[
            {
                "FilerIID": "3",
                "Filer": "CardioCo Inc",
                "FilerTicker": "PSNL",
                "Role": "target",
                "Counterparty": "Tempus AI, Inc.",
                "AnnounceDate": "2026-07-20",
                "Verified": "yes",
                "VerifiedAcquirer": "Tempus AI, Inc.",
            },
            {
                "FilerIID": "4",
                "Filer": "Personalis",
                "FilerTicker": "XX",
                "Role": "target",
                "Counterparty": "BigPharma Inc",
                "AnnounceDate": "2026-01-01",
                "Verified": "yes",
                "VerifiedAcquirer": "BigPharma Inc",
            },
        ]
    )
    events, excluded = aspects.resolved_events()
    assert [(a, t) for a, t, _ in events] == [("1", "2")]
    assert len(excluded) == 2


def test_midpoint_rank_guards_ties():
    assert aspects._midpoint_rank([3, 2, 2, 0, 2], 2) == 1 + 2.0  # 1 above, 3 tied
    assert aspects._midpoint_rank([0, 0, 0, 0], 0) == 2.5  # all tied: mid-pool, no free rank 1


def test_paired_end_to_end_records_coverage_and_passmark(db, monkeypatch):
    _seed_world()
    monkeypatch.setattr(aspects, "_loe", lambda cutoff: {"1": (3, 2, 0.67)})
    r = run_command("pairs-aspect", params={"negatives": 2, "repeats": 3, "seed": 7})
    assert r["status"] == "ok"
    rec = results.load_run(r["run_id"])
    m = results.Metrics(rec)
    assert m.i("_", "n_events") == 1
    assert m.f("aspect-match", "hr5_mean") == 1.0  # true target scores 8, negatives lower
    assert m.i("passmark", "adopted") in (0, 1)
    for a in aspects.ASPECT_ORDER + aspects.NOT_EVALUABLE:
        assert m.i(a, "evaluable_pairs") >= 0  # coverage is a queryable run metric
    assert m.i("consideration_type", "evaluable_pairs") == 0
    assert "Tempus-sequence deals excluded" in rec["run"]["note"]
    assert (config.EXPORTS / "pair_aspect_report.txt").exists()
    assert rec["run"]["run_type"] == "evaluation"


def test_forward_end_to_end_hits_chance_and_note(db, monkeypatch):
    _seed_world()
    monkeypatch.setattr(aspects, "_loe", lambda cutoff: {"1": (3, 2, 0.67)})
    r = run_command("pairs-aspect forward", params={"k_primary": 2, "ks": "2"})
    assert r["status"] == "ok"
    rec = results.load_run(r["run_id"])
    m = results.Metrics(rec)
    assert m.i("_", "hits2") == 1  # 2022 year-end proposes TGB; deal lands 2023
    assert 0.0 < m.f("_", "expected_hits2") < 1.0
    assert m.i("_", "evaluable_deals") == 1
    note = rec["run"]["note"]
    assert "candidate pool per buyer-year" in note and "chance = k/pool" in note
    assert "Ambry Genetics" in note
    assert (config.EXPORTS / "pair_aspect_forward_report.txt").exists()
    assert rec["run"]["run_type"] == "predict"
