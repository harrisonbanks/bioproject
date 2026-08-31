# src/biointel/models/adapters.py
"""Adapters: registry entries call the existing functions unchanged.

Each adapter has the signature (as_of, params) -> result dict. The harness
wraps the call in input enforcement and sets the run type the ledger
records; the functions themselves already record their runs (gate 0.3).
"""

from __future__ import annotations


def run_scorecard(as_of: str | None, params: dict) -> dict:
    from biointel.score import predict

    return predict(as_of)


def run_fitted(as_of: str | None, params: dict) -> dict:
    """The fitted screen has no persisted fit/predict path yet: `develop`
    scores it and `tune` selects its configuration, but nothing trains a
    final model and ranks with it. Which implementation drives `predict` is
    the open decision in PROJECT_STATUS 0.9; until it is taken this entry
    reports the gap rather than inventing a training step (P9)."""
    return {
        "status": "not-implemented",
        "message": (
            "target-screen/fitted has no fit/predict path yet (open decision, "
            "PROJECT_STATUS 0.9). Run its evaluations: "
            "run target-screen --eval develop | tune | textsweep | robust | improve"
        ),
    }


def run_develop(as_of: str | None, params: dict) -> dict:
    from biointel.improve import develop

    return develop()


def run_tune(as_of: str | None, params: dict) -> dict:
    from biointel.improve import tune

    return tune()


def run_textsweep(as_of: str | None, params: dict) -> dict:
    from biointel.improve import text_sweep

    return text_sweep()


def run_robust(as_of: str | None, params: dict) -> dict:
    from biointel.fit import robust

    return robust()


def run_improve(as_of: str | None, params: dict) -> dict:
    from biointel.fit import improve

    return improve()


def run_pairs_full_exact(as_of: str | None, params: dict) -> dict:
    from biointel.pairs import pairs_full_exact

    return pairs_full_exact()


def run_pairs_exact(as_of: str | None, params: dict) -> dict:
    from biointel.pairs import pairs_exact

    return pairs_exact(
        negatives=int(params.get("negatives", 200)),
        repeats=int(params.get("repeats", 20)),
        seed=int(params.get("seed", 7)),
    )


def run_daily_bars(as_of: str | None, params: dict) -> dict:
    """study-all: event study for every FDA event since 2010; writes the
    event_study and event_study_summary tables and records a run."""
    from biointel import results, store
    from biointel.pipeline import read_companies, read_events
    from biointel.study import STUDY_COLS, run_study, summarize

    run = results.start(
        "fda-event-study",
        "study-all",
        ["events", "companies"],
        {"since": "2010-01-01", "benchmark": "XBI"},
    )
    rows = run_study(read_events(), read_companies())
    if not rows:
        return {"status": "empty", "message": "No computable events. Check price connectivity."}
    store.write_table("event_study", rows, STUDY_COLS)
    summ = summarize(rows)
    store.write_table("event_study_summary", summ, list(summ[0].keys()))
    run.metric("_", "n_events", len(rows))
    for r in summ:
        g = r["OutcomeClass"]
        run.metric(g, "N", r["N"])
        for k, v in r.items():
            if k not in ("OutcomeClass", "N"):
                run.metric(g, k, v)
    run_id = results.finish(run)
    return {"status": "ok", "rows": rows, "summary": summ, "run_id": run_id}
