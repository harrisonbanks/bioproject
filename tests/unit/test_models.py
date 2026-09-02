# tests/unit/test_models.py
"""Unit tests for the model framework (gate 0.4): registry integrity, the P2
input rule, enforcement in the harness, and the ledger run_type migration."""

from __future__ import annotations

import pytest

from biointel import config, results, schema, store
from biointel.models import registry
from biointel.models.base import Entry
from biointel.models.harness import describe, run_entry
from biointel.models.registry import EVENT_REACTION_TABLES, MA_LABEL_TABLES, PRICE_DERIVED


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "exports")
    store.close()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()


def test_registry_shape():
    assert registry.models() == ["target-screen", "acquirer-pairing", "fda-event-study"]
    names = {(e.model, e.name) for e in registry.entries()}
    assert len(names) == len(registry.entries())
    assert {e.name for e in registry.implementations("target-screen")} == {"scorecard", "fitted"}
    assert {e.name for e in registry.evaluations("target-screen")} == {
        "develop",
        "tune",
        "textsweep",
        "robust",
        "improve",
    }
    assert registry.get("acquirer-pairing", "mass-exact").name == "mass-exact"
    assert {e.name for e in registry.implementations("acquirer-pairing")} == {
        "mass-exact",
        "aspect-match",
    }
    with pytest.raises(KeyError):
        registry.get("acquirer-pairing")  # two implementations since gate L4: --impl required
    with pytest.raises(KeyError):
        registry.get("target-screen")  # two implementations: --impl required
    with pytest.raises(KeyError):
        registry.get("no-such-model")
    for cmd in registry.COMMAND_TO_ENTRY:
        m, i, ev = registry.COMMAND_TO_ENTRY[cmd]
        assert registry.get(m, i, ev).model == m


def test_declared_tables_and_columns_exist_in_schema():
    for e in registry.entries():
        for t, cols in e.inputs.items():
            if t.startswith("bronze:"):
                continue
            decl = schema.TABLE_BY_PATH.get(f"silver/{t}.csv") or schema.TABLE_BY_PATH.get(
                f"gold/{t}.csv"
            )
            assert decl is not None, (e.label, t)
            if cols is not None:
                known = set(decl.columns) | set(decl.optional)
                assert set(cols) <= known, (e.label, t, set(cols) - known)


def test_p2_fitted_ma_models_read_no_price_or_event_reaction_data():
    for e in registry.entries():
        if e.model in ("target-screen", "acquirer-pairing") and e.name in ("fitted", "mass-exact"):
            for t, cols in e.inputs.items():
                assert t not in EVENT_REACTION_TABLES, (e.label, t)
                assert cols is not None, (e.label, t, "must declare columns")
                assert not set(cols) & set(PRICE_DERIVED), (
                    e.label,
                    t,
                    set(cols) & set(PRICE_DERIVED),
                )
        if e.model == "fda-event-study":
            assert not set(e.inputs) & set(MA_LABEL_TABLES)
    # the hand scorecard declares its price-derived reads openly (P2)
    sc = registry.get("target-screen", "scorecard")
    assert {"CAR12m_mean", "MarketCap"} <= set(sc.inputs["model_panel"])
    # the robustness diagnostic declares the price columns on purpose
    rb = registry.get("target-screen", eval_name="robust")
    assert set(PRICE_DERIVED) <= set(rb.inputs["feature_panel"])


def _seed_events(n=5):
    rows = [
        {
            "IID": str(i),
            "Name": "A",
            "Event": "Approval",
            "Date": "2024-01-01",
            "AppNo": f"N{i}",
            "Drug": "",
            "Outcome": "",
            "Priority": "",
            "ClassCode": "",
            "SubType": "",
        }
        for i in range(n)
    ]
    store.write_table("events", rows, schema.EVENT_COLS)


def test_harness_enforces_declared_inputs_and_stamps_run_type(db):
    _seed_events()
    seen = {}

    def good(as_of, params):
        rows = store.read_table("events")
        seen["n"] = len(rows)
        seen["dates"] = [r["Date"] for r in rows]
        run = results.start("t", "t", ["events"])
        run.metric("_", "n", len(rows))
        return {"status": "ok", "run_id": results.finish(run)}

    e = Entry("t", "good", "evaluation", {"events": ("IID", "Date")}, good)
    r = run_entry(e)
    assert r["status"] == "ok" and seen["n"] == 5
    rec = results.load_run(r["run_id"])
    assert rec["run"]["run_type"] == "evaluation"

    def bad_column(as_of, params):
        return {"status": "ok", "x": [r["Drug"] for r in store.read_table("events")]}

    with pytest.raises(store.InputViolation, match="undeclared column 'Drug' of table 'events'"):
        run_entry(Entry("t", "badcol", "predict", {"events": ("IID", "Date")}, bad_column))

    def bad_table(as_of, params):
        return {"status": "ok", "x": store.read_table("trials")}

    with pytest.raises(store.InputViolation, match="undeclared table 'trials'"):
        run_entry(Entry("t", "badtbl", "predict", {"events": None}, bad_table))
    # enforcement is off again after a failure
    assert store.read_table("events")[0]["Drug"] == ""


def test_outputs_readable_and_added_keys_free(db):
    _seed_events(2)

    def f(as_of, params):
        rows = store.read_table("events")
        for r in rows:
            r["_engineered"] = 1
        assert rows[0]["_engineered"] == 1
        store.write_table("ma_predictions", [], schema.PRED_COLS)
        assert store.read_table("ma_predictions") == []
        return {"status": "ok"}

    e = Entry("t", "f", "predict", {"events": ("IID",)}, f, outputs=("ma_predictions",))
    assert run_entry(e)["status"] == "ok"


def test_run_type_migration_of_existing_ledger(db):
    # a runs table written before gate 0.4 (16 columns, created directly) gains run_type
    old_cols = [c for c in schema.RUN_COLS if c != "run_type"]
    cols_sql = ", ".join(f'"{c}" VARCHAR NOT NULL' for c in old_cols)
    db.execute(f"CREATE TABLE runs (_rowid BIGINT NOT NULL, {cols_sql})")
    for i, (rid, model) in enumerate([("x-fit", "fit"), ("x-pairs", "pairs")], start=1):
        vals = {c: "" for c in old_cols}
        vals.update(run_id=rid, model=model, source="historical-file", status="ok")
        db.execute(
            f"INSERT INTO runs VALUES ({i}, " + ", ".join(["?"] * len(old_cols)) + ")",
            [vals[c] for c in old_cols],
        )
    results.ensure_ledger_schema(db)
    rows = {r["run_id"]: r for r in store.read_table("runs")}
    assert rows["x-fit"]["run_type"] == "fit" and rows["x-pairs"]["run_type"] == "evaluation"
    assert store.table_columns("runs") == list(schema.RUN_COLS)
    rid = results.finish(results.start("m", "m", []), run_type_value="predict")
    assert results.load_run(rid)["run"]["run_type"] == "predict"


def test_describe_lists_everything():
    text = "\n".join(describe())
    for name in (
        "scorecard",
        "fitted",
        "mass-exact",
        "aspect-match",
        "daily-bars",
        "robust",
        "tune",
    ):
        assert name in text
