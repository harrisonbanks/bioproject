# src/biointel/results.py
"""Run ledger and report rendering (P17, gate 0.3).

Every model run writes one `runs` row plus key-value rows in `run_params`,
`run_metrics` and `run_artefacts` (MLflow's record structure, kept in the
same DuckDB file as the data, P16). Every human-readable report is
rendered from its record by the same `render_*` function that produced
the file at run time, so `report <model> <date>` regenerates the text
byte for byte from the stored numbers.

Metric values are stored as text exactly as `repr()` gives them (floats
round-trip through `float()` unchanged), so a renderer formatting a
stored value produces the same characters as it did from the live value.
"""

from __future__ import annotations

import getpass
import hashlib
import importlib
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from biointel import config, schema, store

# model -> (module, render function) for `report` and record_and_export.
RENDERERS = {
    "pairs-full-exact": ("biointel.pairs", "render_full_exact"),
    "pairs-exact": ("biointel.pairs", "render_exact"),
    "robust": ("biointel.fit", "render_robust"),
    "improve": ("biointel.fit", "render_improve"),
    "develop": ("biointel.improve", "render_develop"),
    "tune": ("biointel.improve", "render_tune"),
    "textsweep": ("biointel.improve", "render_text_sweep"),
    "predict": ("biointel.score", "render_predict"),
}
# model -> (group, name) of the headline metric shown in the ledger views.
HEADLINE = {
    "pairs-full-exact": ("_", "hit10"),
    "pairs-exact": ("MASS-exact", "hr5_mean"),
    "robust": ("baseline", "aucpr"),
    "improve": ("gradboost-v2", "aucpr"),
    "develop": ("hist-gbm|fund+engineered", "aucpr"),
    "tune": ("best", "aucpr"),
    "textsweep": ("_", "best_aucpr"),
    "predict": ("_", "n_ranked"),
    # legacy rows (ledger-seed)
    "fit": ("test", "aucpr"),
    "holdout": ("holdout", "aucpr"),
    "pairs": ("_", "hit10"),
    "pairs-fit": ("test", "hit10"),
    "pairs-protocol": ("MASS-inspired", "hr5_mean"),
    "pairs-substrate": ("substrate", "hr5_mean"),
}


# ---------------------------------------------------------------- helpers
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def code_ref() -> str:
    """Git commit of the working tree, or 'unknown'."""
    try:
        out = subprocess.run(
            ["git", "-C", str(config.ROOT), "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def env_hash() -> str:
    """SHA-256 of requirements.lock (the exact installed environment), or 'unknown'."""
    p = config.ROOT / "requirements.lock"
    if not p.exists():
        return "unknown"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def data_snapshot_hash(tables: list[str], con=None) -> str:
    """SHA-256 over (table, header, row count) of the tables a run read,
    so two runs are comparable only when this value matches."""
    con = con or store.connect()
    h = hashlib.sha256()
    for t in tables:
        if store.has_table(t, con):
            hdr = ",".join(store.table_columns(t, con))
            n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
        else:
            hdr, n = "", 0
        h.update(f"{t}|{hdr}|{n}\n".encode())
    return h.hexdigest()


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def package_version() -> str:
    try:
        from importlib.metadata import version

        return version("biointel")
    except Exception:
        return "unknown"


def _fmt(v) -> str:
    """Text form stored in the ledger: repr for floats (round-trips), str otherwise."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return repr(v)
    if v is None:
        return ""
    return str(v)


# ---------------------------------------------------------------- run type (gate 0.4)
_RUN_TYPE: str = ""


class run_type:
    """Context manager the harness uses to stamp the runs it triggers."""

    def __init__(self, value: str):
        self.value = value

    def __enter__(self):
        global _RUN_TYPE
        self._prev = _RUN_TYPE
        _RUN_TYPE = self.value
        return self

    def __exit__(self, *exc):
        global _RUN_TYPE
        _RUN_TYPE = self._prev
        return False


LEGACY_RUN_TYPES = {"fit": "fit", "holdout": "evaluation"}  # other legacy models: evaluation


def ensure_ledger_schema(con=None) -> None:
    """Add columns introduced after the ledger was first written. Gate 0.4:
    `run_type` on runs (existing rows: legacy rows by model, others blank)."""
    con = con or store.connect()
    if not store.has_table("runs", con):
        return
    cols = store.table_columns("runs", con)
    if "run_type" not in cols:
        con.execute("ALTER TABLE runs ADD COLUMN run_type VARCHAR DEFAULT ''")
        con.execute(
            "UPDATE runs SET run_type = CASE WHEN model = 'fit' THEN 'fit' "
            "WHEN source <> 'run' THEN 'evaluation' ELSE '' END"
        )


# ---------------------------------------------------------------- record
class Run:
    """An in-progress run: collects params, metrics and artefacts, then `finish`."""

    def __init__(self, model: str, command: str, inputs: list[str], params: dict | None = None):
        self.model = model
        self.command = command
        self.inputs = list(inputs)
        self.params: dict = dict(params or {})
        self.metrics: list[tuple[str, str, str]] = []  # (group, name, value-as-text)
        self.artefacts: list[Path] = []
        self.started = _now()
        self._t0 = time.monotonic()

    def metric(self, group: str, name: str, value) -> None:
        self.metrics.append((group, name, _fmt(value)))

    def artefact(self, path: Path) -> None:
        self.artefacts.append(Path(path))

    def record(self) -> dict:
        """The record a renderer consumes (same shape as `load_run`)."""
        return {
            "run": {"model": self.model, "command": self.command},
            "params": {k: _fmt(v) for k, v in self.params.items()},
            "metrics": [{"group": g, "name": n, "value": v} for g, n, v in self.metrics],
        }


def start(model: str, command: str, inputs: list[str], params: dict | None = None) -> Run:
    return Run(model, command, inputs, params)


def finish(
    run: Run,
    status: str = "ok",
    note: str = "",
    source: str = "run",
    run_at: datetime | None = None,
    code: str | None = None,
    con=None,
    run_type_value: str | None = None,
) -> str:
    """Write the run's rows to the four ledger tables; returns the run_id."""
    con = con or store.connect()
    ensure_ledger_schema(con)
    started = run_at or run.started
    run_id = _new_run_id(run.model, started, con)
    row = {
        "run_id": run_id,
        "model": run.model,
        "version": package_version(),
        "command": run.command,
        "run_at": _iso(started),
        "duration_s": _fmt(round(time.monotonic() - run._t0, 3)) if source == "run" else "",
        "status": status,
        "operator": _operator(),
        "code_ref": code if code is not None else code_ref(),
        "env_hash": env_hash() if source == "run" else "",
        "data_snapshot_hash": data_snapshot_hash(run.inputs, con) if source == "run" else "",
        "inputs": ";".join(run.inputs),
        "objective": "",
        "holdout_access": "yes" if run.model == "holdout" else "",
        "source": source,
        "note": note,
        "run_type": run_type_value if run_type_value is not None else _RUN_TYPE,
    }
    store.append_rows("runs", [row], schema.RUN_COLS, con=con)
    store.append_rows(
        "run_params",
        [{"run_id": run_id, "name": k, "value": _fmt(v)} for k, v in run.params.items()],
        schema.RUN_PARAM_COLS,
        con=con,
    )
    store.append_rows(
        "run_metrics",
        [{"run_id": run_id, "group": g, "name": n, "value": v} for g, n, v in run.metrics],
        schema.RUN_METRIC_COLS,
        con=con,
    )
    store.append_rows(
        "run_artefacts",
        [
            {"run_id": run_id, "path": _rel(p), "sha256": file_sha256(p) if p.exists() else ""}
            for p in run.artefacts
        ],
        schema.RUN_ARTEFACT_COLS,
        con=con,
    )
    return run_id


def record_and_export(run: Run, filename: str, status: str = "ok") -> tuple[str, str]:
    """Render the run's record with the model's renderer, write the report to
    data/exports/<filename>, register it as an artefact, and finish the run.
    Returns (text, run_id). The text equals `render(model, load_run(run_id))`."""
    text = render(run.model, run.record())
    p = store.write_export(filename, text)
    run.artefact(p)
    run_id = finish(run, status=status)
    return text, run_id


def _operator() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(config.DATA.resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


def _new_run_id(model: str, started: datetime, con) -> str:
    base = f"{started.astimezone(timezone.utc):%Y%m%dT%H%M%S}-{model}"
    if not store.has_table("runs", con):
        return base
    n = con.execute("SELECT count(*) FROM runs WHERE run_id LIKE ?", [base + "%"]).fetchone()[0]
    return base if n == 0 else f"{base}-{n + 1}"


# ---------------------------------------------------------------- read back
def load_run(run_id: str, con=None) -> dict:
    con = con or store.connect()
    runs = [r for r in store.read_table("runs", con=con) if r["run_id"] == run_id]
    if not runs:
        raise KeyError(f"no run {run_id}")
    params = {
        r["name"]: r["value"]
        for r in store.read_table("run_params", con=con)
        if r["run_id"] == run_id
    }
    metrics = [
        {"group": r["group"], "name": r["name"], "value": r["value"]}
        for r in store.read_table("run_metrics", con=con)
        if r["run_id"] == run_id
    ]
    artefacts = [r for r in store.read_table("run_artefacts", con=con) if r["run_id"] == run_id]
    return {"run": runs[0], "params": params, "metrics": metrics, "artefacts": artefacts}


def find_run(model: str, date: str | None = None, con=None) -> str | None:
    """run_id of the latest run of `model` on `date` (YYYY-MM-DD, UTC; today if None)."""
    con = con or store.connect()
    d = date or _now().date().isoformat()
    hits = [
        r
        for r in store.read_table("runs", con=con)
        if r["model"] == model and r["run_at"][:10] == d
    ]
    return hits[-1]["run_id"] if hits else None


def render(model: str, rec: dict) -> str:
    if model not in RENDERERS:
        raise KeyError(f"no renderer for model {model!r}")
    mod, fn = RENDERERS[model]
    return getattr(importlib.import_module(mod), fn)(rec)


class Metrics:
    """Ordered view over a record's metric rows for renderers."""

    def __init__(self, rec: dict):
        self.rows = rec["metrics"]
        self.params = rec.get("params", {})

    def groups(self) -> list[str]:
        seen: list[str] = []
        for r in self.rows:
            if r["group"] not in seen:
                seen.append(r["group"])
        return seen

    def get(self, group: str, name: str, default=None):
        for r in self.rows:
            if r["group"] == group and r["name"] == name:
                return r["value"]
        return default

    def f(self, group: str, name: str) -> float:
        return float(self.get(group, name))

    def i(self, group: str, name: str) -> int:
        return int(float(self.get(group, name)))

    def s(self, group: str, name: str) -> str:
        return str(self.get(group, name, ""))

    def has(self, group: str, name: str) -> bool:
        return self.get(group, name) is not None

    def p(self, name: str, default=None):
        return self.params.get(name, default)


# ---------------------------------------------------------------- views
def headline(run_id: str, model: str, con=None) -> str:
    key = HEADLINE.get(model)
    if not key:
        return ""
    rec = load_run(run_id, con)
    m = Metrics(rec)
    v = m.get(*key)
    return "" if v is None else f"{key[1]}={v}"


def ledger_rows(con=None) -> list[dict]:
    """One row per run with its headline metric and metric count; the
    generated table PROJECT_STATUS and the paper exhibits are built from."""
    con = con or store.connect()
    out = []
    metrics = store.read_table("run_metrics", con=con)
    by_run: dict[str, list[dict]] = {}
    for r in metrics:
        by_run.setdefault(r["run_id"], []).append(r)
    for r in store.read_table("runs", con=con):
        key = HEADLINE.get(r["model"])
        rows = by_run.get(r["run_id"], [])
        hv = ""
        if key:
            for x in rows:
                if x["group"] == key[0] and x["name"] == key[1]:
                    hv = x["value"]
                    break
        elif rows:
            hv = f"{rows[0]['group']}/{rows[0]['name']}={rows[0]['value']}"
        out.append(
            {
                **r,
                "headline": (f"{key[1]}={hv}" if key and hv != "" else hv),
                "n_metrics": len(rows),
            }
        )
    return out


LEDGER_COLS = list(schema.RUN_COLS) + ["headline", "n_metrics"]


def write_ledger_csv(con=None) -> Path:
    import csv

    rows = ledger_rows(con)
    p = config.EXPORTS / "ledger.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return p
