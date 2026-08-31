# src/biointel/legacy_ledger.py
"""Ledger rows for the legacy reports that are never run again (P7, P17).

Each entry transcribes the numbers from one report file exactly as they
appear in it (the `line` field quotes the source line so the transcription
can be checked mechanically: tests/unit/test_results.py asserts every
metric value appears in its quoted line). `ledger-seed` inserts the rows
once; it refuses if legacy rows already exist, and refuses to seed any
`historical-file` entry whose file on disk does not match the fingerprint
recorded in docs/regression_baseline.txt.

Sources:
  historical-file  the report file, frozen under data/gold_frozen_<tag>/,
                   produced on Harrison's machine (code commit 880da16 or
                   earlier; the refactor kept behaviour byte-identical)
  project-status   PROJECT_STATUS.md 0.5 / changelog, where no file exists
"""

from __future__ import annotations

from datetime import datetime, timezone

from biointel import config, results, store

LEGACY_CODE_REF = "880da16"

# (group, name, value, source line)
LEGACY_RUNS = [
    {
        "model": "fit",
        "command": "fit",
        "run_at": "2026-08-25T00:00:00Z",
        "file": "fit_report.txt",
        "source": "historical-file",
        "note": "gen-1 logistic screen (LEGACY); price-inclusive spec, retracted as a headline result (leakage), kept as the measured baseline",
        "params": {"split": "2021-12-31"},
        "metrics": [
            (
                "train",
                "n",
                34732,
                "TRAIN <= 2021-12-31: 34732 firm-quarters, 546 positives (1.57%)",
            ),
            (
                "train",
                "pos",
                546,
                "TRAIN <= 2021-12-31: 34732 firm-quarters, 546 positives (1.57%)",
            ),
            ("test", "n", 15138, "TEST  >  2021-12-31: 15138 firm-quarters, 459 positives (3.03%)"),
            ("test", "pos", 459, "TEST  >  2021-12-31: 15138 firm-quarters, 459 positives (3.03%)"),
            (
                "train",
                "aucpr",
                0.085,
                "AUC-PR  train 0.085   test 0.204   (base rate 0.0303, lift 6.7x over random)",
            ),
            (
                "test",
                "aucpr",
                0.204,
                "AUC-PR  train 0.085   test 0.204   (base rate 0.0303, lift 6.7x over random)",
            ),
            (
                "test",
                "base_rate",
                0.0303,
                "AUC-PR  train 0.085   test 0.204   (base rate 0.0303, lift 6.7x over random)",
            ),
            (
                "test",
                "lift",
                6.7,
                "AUC-PR  train 0.085   test 0.204   (base rate 0.0303, lift 6.7x over random)",
            ),
            ("train", "roc", 0.872, "AUC-ROC train 0.872   test 0.915"),
            ("test", "roc", 0.915, "AUC-ROC train 0.872   test 0.915"),
            (
                "test",
                "p10",
                0.70,
                "precision@10 / @25, latest MATURE quarter (2025-06-30): 0.70 / 0.60",
            ),
            (
                "test",
                "p25",
                0.60,
                "precision@10 / @25, latest MATURE quarter (2025-06-30): 0.70 / 0.60",
            ),
        ],
    },
    {
        "model": "holdout",
        "command": "holdout tuned fund+eng+text",
        "run_at": "2026-08-25T00:00:00Z",
        "file": "holdout_report.txt",
        "source": "historical-file",
        "note": "second and final pre-registered holdout access (P10); gen-2 tuned hist-gbm, fund+eng+text",
        "params": {"model": "tuned", "spec": "fund+eng+text", "window": "2023+"},
        "metrics": [
            ("holdout", "n", 12471, "n=12471 pos=454 AUC-PR 0.079  lift 2.2x  ROC 0.720"),
            ("holdout", "pos", 454, "n=12471 pos=454 AUC-PR 0.079  lift 2.2x  ROC 0.720"),
            ("holdout", "aucpr", 0.079, "n=12471 pos=454 AUC-PR 0.079  lift 2.2x  ROC 0.720"),
            ("holdout", "lift", 2.2, "n=12471 pos=454 AUC-PR 0.079  lift 2.2x  ROC 0.720"),
            ("holdout", "roc", 0.720, "n=12471 pos=454 AUC-PR 0.079  lift 2.2x  ROC 0.720"),
        ],
    },
    {
        "model": "pairs",
        "command": "pairs",
        "run_at": "2026-08-25T00:00:00Z",
        "file": "pair_report.txt",
        "source": "historical-file",
        "note": "cosine-similarity pairing engine (LEGACY, rejected)",
        "params": {},
        "metrics": [
            (
                "_",
                "n_events",
                127,
                "PAIR MODEL (MASS-style similarity), 127 events evaluated, universe-wide candidate sets",
            ),
            ("_", "median_rank", 139, "median rank of true target: 139 of ~956"),
            ("_", "median_pool", 956, "median rank of true target: 139 of ~956"),
            ("_", "hit10", 0.17, "hit@10 0.17   hit@25 0.21   MRR 0.068"),
            ("_", "hit25", 0.21, "hit@10 0.17   hit@25 0.21   MRR 0.068"),
            ("_", "mrr", 0.068, "hit@10 0.17   hit@25 0.21   MRR 0.068"),
        ],
    },
    {
        "model": "pairs-fit",
        "command": "pairs-fit",
        "run_at": "2026-08-25T00:00:00Z",
        "file": "pair_supervised_report.txt",
        "source": "historical-file",
        "note": "supervised pair ranker (LEGACY, rejected: top-10 wash, median worse)",
        "params": {"train_before": "2020", "test_from": "2020"},
        "metrics": [
            (
                "train",
                "pos",
                97,
                "SUPERVISED PAIR RANKER  train<2020 (97 pos), test 2020+ (86 events, full candidate sets)",
            ),
            (
                "test",
                "n_events",
                86,
                "SUPERVISED PAIR RANKER  train<2020 (97 pos), test 2020+ (86 events, full candidate sets)",
            ),
            ("test", "median_rank", 221, "median rank 221   hit@10 0.21   hit@25 0.22"),
            ("test", "hit10", 0.21, "median rank 221   hit@10 0.21   hit@25 0.22"),
            ("test", "hit25", 0.22, "median rank 221   hit@10 0.21   hit@25 0.22"),
            ("baseline", "hit10", 0.17, "(unsupervised baseline: hit@10 0.17, median 139)"),
            ("baseline", "median_rank", 139, "(unsupervised baseline: hit@10 0.17, median 139)"),
        ],
    },
    {
        "model": "pairs-protocol",
        "command": "pairs-protocol",
        "run_at": "2026-08-26T00:00:00Z",
        "file": "pair_protocol_report.txt",
        "source": "historical-file",
        "note": "field-protocol pairing evaluation (LEGACY engines); MASS-inspired 0.222 was the incumbent that MASS-exact (0.310/0.334) replaced",
        "params": {"negatives": 200, "repeats": 20, "n_events": 129},
        "metrics": [
            (
                "cosine",
                "hr5_mean",
                0.216,
                "cosine         HR@5 0.216 (+/-0.010)   HR@10 0.261   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "cosine",
                "hr5_sd",
                0.010,
                "cosine         HR@5 0.216 (+/-0.010)   HR@10 0.261   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "cosine",
                "hr10_mean",
                0.261,
                "cosine         HR@5 0.216 (+/-0.010)   HR@10 0.261   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "MASS-inspired",
                "hr5_mean",
                0.222,
                "MASS-inspired  HR@5 0.222 (+/-0.010)   HR@10 0.284   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "MASS-inspired",
                "hr5_sd",
                0.010,
                "MASS-inspired  HR@5 0.222 (+/-0.010)   HR@10 0.284   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "MASS-inspired",
                "hr10_mean",
                0.284,
                "MASS-inspired  HR@5 0.222 (+/-0.010)   HR@10 0.284   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "latent-SVD",
                "hr5_mean",
                0.143,
                "latent-SVD     HR@5 0.143 (+/-0.012)   HR@10 0.208   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "latent-SVD",
                "hr5_sd",
                0.012,
                "latent-SVD     HR@5 0.143 (+/-0.012)   HR@10 0.208   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "latent-SVD",
                "hr10_mean",
                0.208,
                "latent-SVD     HR@5 0.143 (+/-0.012)   HR@10 0.208   (129 events, 200 negatives, 20 repeats)",
            ),
            (
                "hybrid",
                "hr5_mean",
                0.186,
                "hybrid         HR@5 0.186            HR@10 0.287   (129 events, rank-fusion, single draw)",
            ),
            (
                "hybrid",
                "hr10_mean",
                0.287,
                "hybrid         HR@5 0.186            HR@10 0.287   (129 events, rank-fusion, single draw)",
            ),
        ],
    },
    {
        "model": "pairs-substrate",
        "command": "pairs-substrate targets",
        "run_at": "2026-08-26T00:00:00Z",
        "file": "pair_substrate_report.txt",
        "source": "historical-file",
        "note": "paired substrate comparison, ChEMBL molecular targets (LEGACY); targets REJECTED by the pre-registered rule",
        "params": {"mode": "targets", "negatives": 200, "repeats": 20, "n_events_common": 67},
        "metrics": [
            (
                "substrate",
                "hr5_mean",
                0.120,
                "targets  MASS-inspired  HR@5 0.120 (+/-0.009)   HR@10 0.179",
            ),
            (
                "substrate",
                "trials_hr5_mean",
                0.206,
                "trials   MASS-inspired  HR@5 0.206 (+/-0.013)   HR@10 0.271",
            ),
            (
                "trials|cosine",
                "hr5_mean",
                0.181,
                "trials   cosine         HR@5 0.181 (+/-0.014)   HR@10 0.213",
            ),
            (
                "trials|cosine",
                "hr10_mean",
                0.213,
                "trials   cosine         HR@5 0.181 (+/-0.014)   HR@10 0.213",
            ),
            (
                "trials|MASS-inspired",
                "hr5_mean",
                0.206,
                "trials   MASS-inspired  HR@5 0.206 (+/-0.013)   HR@10 0.271",
            ),
            (
                "trials|MASS-inspired",
                "hr10_mean",
                0.271,
                "trials   MASS-inspired  HR@5 0.206 (+/-0.013)   HR@10 0.271",
            ),
            (
                "targets|cosine",
                "hr5_mean",
                0.137,
                "targets  cosine         HR@5 0.137 (+/-0.011)   HR@10 0.193",
            ),
            (
                "targets|cosine",
                "hr10_mean",
                0.193,
                "targets  cosine         HR@5 0.137 (+/-0.011)   HR@10 0.193",
            ),
            (
                "targets|MASS-inspired",
                "hr5_mean",
                0.120,
                "targets  MASS-inspired  HR@5 0.120 (+/-0.009)   HR@10 0.179",
            ),
            (
                "targets|MASS-inspired",
                "hr10_mean",
                0.179,
                "targets  MASS-inspired  HR@5 0.120 (+/-0.009)   HR@10 0.179",
            ),
            (
                "fused|cosine",
                "hr5_mean",
                0.173,
                "fused    cosine         HR@5 0.173 (+/-0.011)   HR@10 0.214",
            ),
            (
                "fused|cosine",
                "hr10_mean",
                0.214,
                "fused    cosine         HR@5 0.173 (+/-0.011)   HR@10 0.214",
            ),
            (
                "fused|MASS-inspired",
                "hr5_mean",
                0.205,
                "fused    MASS-inspired  HR@5 0.205 (+/-0.014)   HR@10 0.266",
            ),
            (
                "fused|MASS-inspired",
                "hr10_mean",
                0.266,
                "fused    MASS-inspired  HR@5 0.205 (+/-0.014)   HR@10 0.266",
            ),
        ],
    },
    {
        "model": "pairs-substrate",
        "command": "pairs-substrate patents",
        "run_at": "2026-08-26T00:00:00Z",
        "file": None,
        "source": "project-status",
        "note": "paired substrate comparison, BigQuery patent CPC (LEGACY); patents REJECTED; report file overwritten by the targets run, numbers from PROJECT_STATUS.md 0.5 (v0.75)",
        "params": {"mode": "patents", "negatives": 200, "repeats": 20, "n_events_common": 42},
        "metrics": [
            (
                "substrate",
                "hr5_mean",
                0.055,
                "patents run (42 common events) trials 0.237 vs patents 0.055 vs fused 0.220 -- patents REJECTED",
            ),
            (
                "substrate",
                "trials_hr5_mean",
                0.237,
                "patents run (42 common events) trials 0.237 vs patents 0.055 vs fused 0.220 -- patents REJECTED",
            ),
            (
                "trials|MASS-inspired",
                "hr5_mean",
                0.237,
                "patents run (42 common events) trials 0.237 vs patents 0.055 vs fused 0.220 -- patents REJECTED",
            ),
            (
                "patents|MASS-inspired",
                "hr5_mean",
                0.055,
                "patents run (42 common events) trials 0.237 vs patents 0.055 vs fused 0.220 -- patents REJECTED",
            ),
            (
                "fused|MASS-inspired",
                "hr5_mean",
                0.220,
                "patents run (42 common events) trials 0.237 vs patents 0.055 vs fused 0.220 -- patents REJECTED",
            ),
        ],
    },
]


def baseline_fingerprints() -> dict[str, str]:
    p = config.ROOT / "docs" / "regression_baseline.txt"
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[0]] = parts[1].lower()
    return out


def seed() -> dict:
    con = store.connect()
    existing = [r for r in store.read_table("runs", con=con) if r["source"] != "run"]
    if existing:
        return {
            "status": "refused",
            "message": f"{len(existing)} legacy rows already in the ledger; ledger-seed makes no change.",
        }
    fp = baseline_fingerprints()
    # check every file first so a failure seeds nothing
    for e in LEGACY_RUNS:
        if not e["file"]:
            continue
        p = config.GOLD / e["file"]
        if not p.exists():
            return {"status": "fail", "message": f"{p} is absent; nothing seeded."}
        got = results.file_sha256(p)
        want = fp.get(e["file"], "")
        if got != want:
            return {
                "status": "fail",
                "message": f"{p} does not match docs/regression_baseline.txt "
                f"({got[:12]}... vs {want[:12]}...); nothing seeded.",
            }
    lines = []
    for e in LEGACY_RUNS:
        run = results.start(e["model"], e["command"], [], e["params"])
        for g, n, v, _line in e["metrics"]:
            run.metric(g, n, v)
        if e["file"]:
            run.artefact(config.GOLD / e["file"])
        run_at = datetime.fromisoformat(e["run_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        run_id = results.finish(
            run,
            status="ok",
            note=e["note"],
            source=e["source"],
            run_at=run_at,
            code=LEGACY_CODE_REF,
            con=con,
        )
        lines.append(f"  seeded  {run_id:<32} {e['source']:<16} {len(e['metrics'])} metrics")
    lines.append(f"ledger-seed: {len(LEGACY_RUNS)} legacy rows inserted.")
    return {"status": "ok", "message": "\n".join(lines)}
