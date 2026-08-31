# tests/unit/test_results.py
"""Unit tests for the run ledger (results.py), renderers and ledger-seed (gate 0.3)."""

from __future__ import annotations

import pytest

from biointel import config, legacy_ledger, results, schema, store
from biointel.fit import render_improve, render_robust
from biointel.improve import render_develop, render_text_sweep, render_tune
from biointel.pairs import render_exact
from biointel.score import render_predict


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(config, "GOLD", tmp_path / "gold_frozen")
    store.close()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()


def _full_exact_run():
    run = results.start("pairs-full-exact", "pairs-full-exact", ["trials", "ma_events"])
    run.metric("_", "n_events", 124)
    run.metric("_", "median_rank", 80)
    run.metric("_", "median_pool", 862)
    run.metric("_", "hit10", 0.2661290322580645)
    run.metric("_", "hit25", 0.3870967741935484)
    return run


def test_record_round_trip_and_render_identity(db):
    run = _full_exact_run()
    text, run_id = results.record_and_export(run, "pair_full_exact_report.txt")
    rec = results.load_run(run_id)
    assert results.render("pairs-full-exact", rec) == text
    assert text == (
        "FULL-UNIVERSE RE-RANK (MASS-exact engine): 124 events; "
        "median true-target rank 80 / median pool 862; hit@10 0.27; hit@25 0.39"
    )
    assert (config.EXPORTS / "pair_full_exact_report.txt").read_text(encoding="utf-8") == text
    assert rec["run"]["status"] == "ok" and rec["run"]["source"] == "run"
    assert rec["run"]["inputs"] == "trials;ma_events"
    assert len(rec["artefacts"]) == 1 and len(rec["artefacts"][0]["sha256"]) == 64
    for r in schema.validate_db(db):
        if r["path"] in ("runs", "run_params", "run_metrics", "run_artefacts"):
            assert r["status"] == "conformant", r


def test_ledger_tables_append_not_replace(db):
    id1 = results.finish(_full_exact_run())
    id2 = results.finish(_full_exact_run())
    assert id1 != id2
    assert len(store.read_table("runs")) == 2
    assert len(store.read_table("run_metrics")) == 10
    with pytest.raises(ValueError):
        store.append_rows("runs", [], ["wrong"])


def test_find_run_and_views(db):
    results.finish(_full_exact_run())
    run_id = results.find_run("pairs-full-exact")
    assert run_id is not None
    assert results.find_run("pairs-full-exact", "1999-01-01") is None
    rows = results.ledger_rows()
    assert rows[0]["headline"] == "hit10=0.2661290322580645" and rows[0]["n_metrics"] == 5
    p = results.write_ledger_csv()
    assert p.exists() and "hit10=" in p.read_text(encoding="utf-8")


def _rec(model, params, metrics):
    run = results.start(model, model, [], params)
    for g, n, v in metrics:
        run.metric(g, n, v)
    return run


@pytest.mark.parametrize(
    "render,model,params,metrics,expected",
    [
        (
            render_exact,
            "pairs-exact",
            {"negatives": 200, "repeats": 20, "seed": 7},
            [
                ("_", "n_events", 129),
                ("MASS-inspired", "hr5_mean", 0.22403100775193798),
                ("MASS-inspired", "hr5_sd", 0.011),
                ("MASS-inspired", "hr10_mean", 0.297),
                ("MASS-exact", "hr5_mean", 0.334),
                ("MASS-exact", "hr5_sd", 0.012),
                ("MASS-exact", "hr10_mean", 0.412),
            ],
            "MASS-EXACT vs INCUMBENT (paired: 129 events, 200 negatives, 20 repeats, shared samples)\n"
            "MASS-inspired  HR@5 0.224 (+/-0.011)   HR@10 0.297\n"
            "MASS-exact     HR@5 0.334 (+/-0.012)   HR@10 0.412",
        ),
        (
            render_improve,
            "improve",
            {"train_end": "2019-12-31", "val_end": "2022-12-31"},
            [
                ("_header", "n_train", 30027),
                ("_header", "pos_train", 611),
                ("_header", "n_val", 11402),
                ("_header", "pos_val", 381),
                ("logistic-v2", "aucpr", 0.0534),
                ("logistic-v2", "roc", 0.652),
                ("gradboost-v2", "aucpr", 0.0491),
                ("gradboost-v2", "roc", 0.633),
            ],
            "IMPROVE (validation window 2019-12-31..2022-12-31; holdout 2023+ LOCKED)\n"
            "train 30027 (+611)  val 11402 (+381)  val base rate 0.0334\n"
            "logistic-v2     AUC-PR 0.053  lift 1.6x  ROC 0.652\n"
            "gradboost-v2    AUC-PR 0.049  lift 1.5x  ROC 0.633",
        ),
        (
            render_tune,
            "tune",
            {"purge_q": 4},
            [
                ("2|0.03|25", "depth", 2),
                ("2|0.03|25", "lr", 0.03),
                ("2|0.03|25", "leaf", 25),
                ("2|0.03|25", "n", 18345),
                ("2|0.03|25", "pos", 551),
                ("2|0.03|25", "aucpr", 0.05446),
                ("best", "depth", 4),
                ("best", "lr", 0.1),
                ("best", "leaf", 25),
                ("best", "aucpr", 0.0561),
            ],
            "GBM TUNING (fund+engineered, purged walk-forward, dev only)\n"
            "  depth=2 lr=0.03  leaf=25  AUC-PR 0.0545  lift 1.81x\n"
            "BEST -> {'max_depth': 4, 'learning_rate': 0.1, 'min_samples_leaf': 25} "
            "(dev AUC-PR 0.0561), persisted to gold/best_config.json",
        ),
        (
            render_text_sweep,
            "textsweep",
            {"purge_q": 4},
            [
                ("1e-05", "alpha", 1e-05),
                ("1e-05", "n", 1000),
                ("1e-05", "pos", 30),
                ("1e-05", "aucpr", 0.0512),
                ("_", "best_aucpr", 0.0512),
            ],
            "TEXT SHRINKAGE SWEEP (hist-gbm fund+eng+text, dev pooled OOF)\n"
            "  alpha=1e-05    AUC-PR 0.0512  lift 1.71x",
        ),
        (
            render_develop,
            "develop",
            {"origins_first": "2016-12-31", "origins_last": "2021-12-31", "purge_q": 4},
            [
                ("logistic|fundamentals", "n", 18345),
                ("logistic|fundamentals", "pos", 551),
                ("logistic|fundamentals", "aucpr", 0.0453),
                ("logistic|fundamentals", "roc", 0.664),
                ("hist-gbm|fund+eng+text", "insufficient", 1),
            ],
            "PURGED WALK-FORWARD DEVELOPMENT (holdout 2023+ untouched)\n"
            "origins 2016..2021, purge 4q, pooled out-of-fold AUC-PR\n"
            "logistic  fundamentals      n=18345  pos=551  AUC-PR 0.045  lift 1.5x  ROC 0.664\n"
            "hist-gbm  fund+eng+text     INSUFFICIENT",
        ),
        (
            render_predict,
            "predict",
            {"quarter": "2026-06-30"},
            [("_", "n_ranked", 1357), ("_", "n_acquirer_side", 22), ("_", "quarter", "2026-06-30")],
            None,
        ),
    ],
)
def test_renderers_from_live_and_stored_records_agree(db, render, model, params, metrics, expected):
    run = _rec(model, params, metrics)
    live = render(run.record())
    run_id = results.finish(run)
    stored = render(results.load_run(run_id))
    assert live == stored
    if expected is not None:
        assert live == expected
    else:
        assert live.startswith("1357 targets ranked at 2026-06-30 -> ")


def test_render_robust_from_record(db):
    run = _rec(
        "robust",
        {"split": "2021-12-31"},
        [
            ("_header", "n_events_all", 443),
            ("_header", "n_events_strict", 320),
            ("_header", "pos_cov_n", 1496),
            ("_header", "pos_cov_with_price", 28),
            ("_header", "neg_cov_n", 75832),
            ("_header", "neg_cov_with_price", 25100),
            ("baseline", "n_tr", 37580),
            ("baseline", "p_tr", 807),
            ("baseline", "n_te", 16292),
            ("baseline", "p_te", 639),
            ("baseline", "insufficient", 0),
            ("baseline", "aucpr", 0.257),
            ("baseline", "lift", 6.6),
            ("baseline", "roc", 0.924),
            ("baseline", "p10", 0.8),
            ("baseline", "lastq", "2025-06-30"),
            ("covered-only", "n_tr", 12602),
            ("covered-only", "p_tr", 8),
            ("covered-only", "n_te", 10492),
            ("covered-only", "p_te", 18),
            ("covered-only", "insufficient", 1),
        ],
    )
    text = render_robust(run.record())
    lines = text.split("\n")
    assert lines[0] == "ROBUSTNESS SUITE  (events: 443 all, 320 machine-corroborated strict)"
    assert lines[1].startswith(
        "price coverage: positives 1.9% (1496) vs negatives 33.1% (75832) -- "
    )
    assert (
        lines[3]
        == "baseline       37580(807)    16292(639)   0.257    6.6x   0.924  0.80  2025-06-30"
    )
    assert lines[4] == "covered-only   12602(8)  10492(18)   INSUFFICIENT"
    run_id = results.finish(run)
    assert render_robust(results.load_run(run_id)) == text


def test_legacy_transcriptions_match_their_source_lines():
    for e in legacy_ledger.LEGACY_RUNS:
        for g, n, v, line in e["metrics"]:
            forms = (
                {str(v)} | {f"{v:.{k}f}" for k in (1, 2, 3, 4)}
                if isinstance(v, float)
                else {str(v)}
            )
            assert any(f in line for f in forms), (e["model"], g, n, v, line)


def test_ledger_seed_refuses_on_mismatch_then_seeds(db, tmp_path, monkeypatch):
    gold = config.GOLD
    gold.mkdir(parents=True, exist_ok=True)
    fps = {}
    for e in legacy_ledger.LEGACY_RUNS:
        if e["file"]:
            p = gold / e["file"]
            p.write_text("\n".join(m[3] for m in e["metrics"]), encoding="utf-8")
            fps[e["file"]] = results.file_sha256(p)
    bad = dict(fps)
    bad["pair_report.txt"] = "0" * 64
    monkeypatch.setattr(legacy_ledger, "baseline_fingerprints", lambda: bad)
    r = legacy_ledger.seed()
    assert r["status"] == "fail" and "pair_report.txt" in r["message"]
    assert not store.has_table("runs")
    monkeypatch.setattr(legacy_ledger, "baseline_fingerprints", lambda: fps)
    r = legacy_ledger.seed()
    assert r["status"] == "ok", r["message"]
    runs = store.read_table("runs")
    assert len(runs) == 7
    assert sum(1 for x in runs if x["source"] == "historical-file") == 6
    assert sum(1 for x in runs if x["source"] == "project-status") == 1
    assert all(x["code_ref"] == "880da16" for x in runs)
    assert [x for x in runs if x["model"] == "holdout"][0]["holdout_access"] == "yes"
    assert legacy_ledger.seed()["status"] == "refused"
