# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_hypotheses.py
"""Expert-hypothesis store: the as-of leak guard, the documented/recollected
split, event-only resolution, and a ledger that never rates unscored calls."""

from __future__ import annotations

from datetime import date

import pytest

from biointel import config, hypotheses, store


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(config, "BRONZE", tmp_path / "bronze")
    store.close()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()


def _add(**kw):
    base = dict(
        expert="Jane Doe",
        subject_key="CIK:1800",
        predicate="wants",
        object_kind="category",
        object_value="radiopharma",
        statement="they need a radiopharma platform before the cliff",
    )
    base.update(kw)
    return hypotheses.add(**base)


def test_recollected_call_cannot_claim_an_earlier_vantage_point(db):
    """No artifact means as_of is today, not the date the call was made.
    Without this a call entered after a deal was rumoured is
    indistinguishable from foresight."""
    r = _add()
    assert r["evidence_class"] == "recollected"
    assert r["as_of"] == date.today().isoformat()


def test_documented_call_is_dated_by_its_artifact(db):
    r = _add(artifact_date="2024-03-01", doc_id="d" * 64, source_kind="article")
    assert r["evidence_class"] == "documented"
    assert r["as_of"] == "2024-03-01"


def test_artifact_date_alone_is_not_enough(db):
    """An asserted date with no library document is still a recollection."""
    r = _add(artifact_date="2024-03-01", object_value="oncology")
    assert r["evidence_class"] == "recollected"
    assert r["as_of"] == date.today().isoformat()


def test_as_of_rows_hides_hypotheses_the_cutoff_could_not_know(db):
    _add(artifact_date="2024-03-01", doc_id="a" * 64, object_value="radiopharma")
    _add(artifact_date="2026-01-15", doc_id="b" * 64, object_value="cardiometabolic")
    assert len(hypotheses.as_of_rows("2025-12-31")) == 1
    assert len(hypotheses.as_of_rows("2026-06-30")) == 2


def test_attaching_an_artifact_upgrades_and_redates_but_only_once(db):
    r = _add()
    up = hypotheses.attach_artifact(r["hypothesis_id"], "2024-03-01", "c" * 64)
    assert up["status"] == "ok" and up["as_of"] == "2024-03-01"
    row = {x["hypothesis_id"]: x for x in store.read_table(hypotheses.TABLE)}[r["hypothesis_id"]]
    assert row["evidence_class"] == "documented"
    assert str(row["as_of"])[:10] == "2024-03-01"
    # a documented row cannot be re-dated after the fact
    again = hypotheses.attach_artifact(r["hypothesis_id"], "2023-01-01", "e" * 64)
    assert again["status"] == "refused"


def test_resolution_is_by_event_and_nothing_expires_for_age(db):
    r = _add(artifact_date="2019-01-01", doc_id="f" * 64)  # seven years old, still open
    rows = {x["hypothesis_id"]: x for x in store.read_table(hypotheses.TABLE)}
    assert rows[r["hypothesis_id"]]["outcome"] == "open"
    assert hypotheses.resolve(r["hypothesis_id"], "hit", "deal announced")["status"] == "ok"
    rows = {x["hypothesis_id"]: x for x in store.read_table(hypotheses.TABLE)}
    assert rows[r["hypothesis_id"]]["outcome"] == "hit"
    assert hypotheses.resolve(r["hypothesis_id"], "expired")["status"] == "error"


def test_ledger_never_folds_recollected_calls_into_a_rate(db):
    _add(artifact_date="2024-01-01", doc_id="1" * 64, object_value="a")
    _add(artifact_date="2024-02-01", doc_id="2" * 64, object_value="b")
    _add(object_value="c")  # recollected
    ids = [
        x["hypothesis_id"]
        for x in store.read_table(hypotheses.TABLE)
        if x["evidence_class"] == "documented"
    ]
    hypotheses.resolve(ids[0], "hit")
    hypotheses.resolve(ids[1], "miss")
    led = hypotheses.ledger()["experts"]["Jane Doe"]
    assert led["documented"] == 2 and led["recollected"] == 1
    assert led["hit"] == 1 and led["miss"] == 1
    assert led["rate"] == 0.5 and led["resolved"] == 2  # 1/2, not 1/3
    text = hypotheses.render_ledger(hypotheses.ledger())
    assert "recollected 1, unscored" in text


def test_ledger_reports_no_rate_before_anything_resolves(db):
    _add(artifact_date="2024-01-01", doc_id="9" * 64)
    assert hypotheses.ledger()["experts"]["Jane Doe"]["rate"] is None
    assert "rate n/a" in hypotheses.render_ledger(hypotheses.ledger())
