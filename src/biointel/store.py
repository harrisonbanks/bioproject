# src/biointel/store.py
"""Bronze layer: fetch and store raw API responses before any parsing.

Why: Power Query re-fetches on every refresh and stores only the parsed,
filtered result. Rows discarded by the filter are gone. Storing the raw
response means a filter change is a re-parse, not a re-download.

Also gives a coverage-as-of record, which matters because the openFDA CRL
dataset had publication paused in April 2026 -- today's pull may not be
reproducible later.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

import requests

from biointel import config

_last_sec_call = 0.0


def _key(url: str, params: dict | None) -> str:
    raw = url + "|" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def fetch_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    *,
    tag: str,
    cache: bool = True,
    timeout: int = 60,
    raw_text: bool = False,
):
    """GET an endpoint, storing the raw response in bronze.

    tag      -- subfolder name, e.g. 'sec_submissions', 'fda_crl'
    cache    -- if True and a stored response exists, return it without a call
    raw_text -- return the body as text instead of parsing JSON. Needed for
                HTML filings, which are documents rather than APIs.
    """
    global _last_sec_call
    folder = config.BRONZE / tag
    folder.mkdir(parents=True, exist_ok=True)
    k = _key(url, params)
    ext = "txt" if raw_text else "json"
    body_path = folder / f"{k}.{ext}"
    meta_path = folder / f"{k}.meta.json"

    if cache and body_path.exists():
        txt = body_path.read_text(encoding="utf-8", errors="replace")
        return txt if raw_text else json.loads(txt)

    if "sec.gov" in url:  # SEC limit is 10 req/sec
        gap = time.time() - _last_sec_call
        if gap < config.SEC_RATE_LIMIT:
            time.sleep(config.SEC_RATE_LIMIT - gap)
        _last_sec_call = time.time()

    hdrs = {"User-Agent": config.require("BIOINTEL_USER_AGENT")}
    if headers:
        hdrs.update(headers)

    r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    meta = {
        "url": r.url,
        "status": r.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tag": tag,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    r.raise_for_status()
    if raw_text:
        body_path.write_text(r.text, encoding="utf-8")
        return r.text
    data = r.json()
    body_path.write_text(json.dumps(data), encoding="utf-8")
    return data


def coverage_report() -> list[dict]:
    """Every stored bronze response with its URL and fetch time."""
    out = []
    for meta in sorted(config.BRONZE.rglob("*.meta.json")):
        out.append(json.loads(meta.read_text(encoding="utf-8")))
    return out


# ---------------------------------------------------------------- DuckDB tables
# Single point of access for every silver, gold and ledger table (P16).
# Values are stored as text exactly as the CSV layer held them (gate 0.2,
# decision 2026-08-30); declared types, keys and allowed values from
# schema.py are enforced as CHECK / UNIQUE constraints at write time, and
# typed reads (typed=True) cast on the way out. Row order is insertion
# order, kept by a hidden _rowid column, so a read returns rows in the
# order they were written, as a CSV did.

import csv as _csv  # noqa: E402
import re as _re  # noqa: E402
from pathlib import Path  # noqa: E402

import duckdb  # noqa: E402

from biointel import schema as _schema  # noqa: E402

_con: duckdb.DuckDBPyConnection | None = None
_con_path: Path | None = None


def table_name(path: str) -> str:
    """'silver/events.csv' -> 'events'. Table names are the file stems."""
    return Path(path).stem


_TABLES = {table_name(t.path): t for t in _schema.TABLES}


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open (or create) the one database file; cached for the process."""
    global _con, _con_path
    if path is None:
        if _con is not None:
            return _con
        p = config.DUCKDB
    else:
        p = Path(path)
        if _con is not None and _con_path == p:
            return _con
        if _con is not None:
            _con.close()
    p.parent.mkdir(parents=True, exist_ok=True)
    _con = duckdb.connect(str(p))
    _con_path = p
    _ensure_meta(_con)
    return _con


def close() -> None:
    global _con, _con_path
    if _con is not None:
        _con.close()
    _con, _con_path = None, None


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _ensure_meta(con) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS meta (key VARCHAR PRIMARY KEY, value VARCHAR)")
    con.execute(
        "INSERT INTO meta VALUES ('duckdb_version', ?) ON CONFLICT DO UPDATE SET value = excluded.value",
        [duckdb.__version__],
    )
    con.execute(
        "INSERT INTO meta VALUES ('schema_version', ?) ON CONFLICT DO UPDATE SET value = excluded.value",
        [_schema.SCHEMA_VERSION],
    )
    con.execute("INSERT OR IGNORE INTO meta VALUES ('created_at', ?)", [_now_iso()])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_sql(col: str, kind: str, allowed: tuple[str, ...] | None) -> str | None:
    c = _q(col)
    if kind == "int":
        return f"CHECK ({c} = '' OR regexp_matches({c}, '^-?[0-9]+(\\.0+)?$'))"
    if kind == "float":
        return f"CHECK ({c} = '' OR TRY_CAST({c} AS DOUBLE) IS NOT NULL)"
    if kind == "date":
        return f"CHECK ({c} = '' OR TRY_STRPTIME({c}, '%Y-%m-%d') IS NOT NULL)"
    if kind == "datetime":
        return f"CHECK ({c} = '' OR TRY_CAST({c} AS TIMESTAMP) IS NOT NULL)"
    if kind == "flag01":
        return f"CHECK ({c} IN ('0', '1'))"
    if kind == "enum" and allowed is not None:
        vals = ", ".join("'" + v.replace("'", "''") + "'" for v in allowed)
        return f"CHECK ({c} IN ({vals}))"
    return None


def _create_sql(name: str, header: list[str], t: _schema.Table | None) -> str:
    cols = ["_rowid BIGINT NOT NULL"] + [f"{_q(c)} VARCHAR NOT NULL" for c in header]
    cons: list[str] = []
    if t is not None:
        for col, kind in t.types.items():
            if col in header:
                s = _check_sql(col, kind, t.enums.get(col))
                if s:
                    cons.append(s)
        if t.key and all(k in header for k in t.key):
            cons.append("UNIQUE (" + ", ".join(_q(k) for k in t.key) + ")")
    return f"CREATE OR REPLACE TABLE {_q(name)} (" + ", ".join(cols + cons) + ")"


def has_table(name: str, con=None) -> bool:
    con = con or connect()
    r = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()
    return bool(r and r[0])


def table_columns(name: str, con=None) -> list[str]:
    """Header of a stored table, in written order (without _rowid)."""
    con = con or connect()
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
        "ORDER BY ordinal_position",
        [name],
    ).fetchall()
    return [r[0] for r in rows if r[0] != "_rowid"]


# ---------------------------------------------------------------- input enforcement (P2)
# While a registered model runs, the harness declares the tables and columns
# it may read (models/registry.py). Any read outside the declaration raises
# InputViolation naming the model, the table and the column. Outside a run
# nothing is enforced. Column access is enforced through _GuardedRow so the
# error names the exact column the code touched.


class InputViolation(RuntimeError):
    """A model read a table or column it did not declare (P2)."""


_ENFORCE: tuple[str, dict[str, tuple[str, ...] | None]] | None = None
_TRACE: dict[str, set[str]] | None = None


class _GuardedRow(dict):
    """Row whose stored columns are guarded: reading a column of the table
    that is not declared raises. Keys the model code adds to the row itself
    (engineered features such as '_wave') are not table columns and are free."""

    __slots__ = ("_allowed", "_header", "_table", "_label")

    def __init__(self, data: dict, allowed: frozenset, header: frozenset, table: str, label: str):
        super().__init__(data)
        self._allowed, self._header, self._table, self._label = allowed, header, table, label

    def _check(self, key):
        if key in self._header and key not in self._allowed:
            raise InputViolation(
                f"{self._label} read undeclared column {key!r} of table {self._table!r}"
            )

    def __getitem__(self, key):
        self._check(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._check(key)
        return super().get(key, default)

    def __contains__(self, key):
        self._check(key)
        return super().__contains__(key)


class _TracedRow(dict):
    __slots__ = ("_seen",)

    def __init__(self, data: dict, seen: set):
        super().__init__(data)
        self._seen = seen

    def __getitem__(self, key):
        self._seen.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._seen.add(key)
        return super().get(key, default)


class enforce:
    """Context manager: `with store.enforce(label, inputs): ...` where inputs
    maps table -> tuple of allowed columns, or None for every column."""

    def __init__(self, label: str, inputs: dict[str, tuple[str, ...] | None]):
        self.label, self.inputs = label, inputs

    def __enter__(self):
        global _ENFORCE
        if _ENFORCE is not None:
            raise RuntimeError(f"enforcement already active for {_ENFORCE[0]}")
        _ENFORCE = (self.label, self.inputs)
        return self

    def __exit__(self, *exc):
        global _ENFORCE
        _ENFORCE = None
        return False


class trace:
    """Context manager: records every (table, column) read; used to derive
    and audit declarations. `store.trace().seen` after the block."""

    def __init__(self):
        self.seen: dict[str, set[str]] = {}

    def __enter__(self):
        global _TRACE
        _TRACE = self.seen
        return self

    def __exit__(self, *exc):
        global _TRACE
        _TRACE = None
        return False


def _guard_rows(name: str, header: list[str], out: list[dict]) -> list[dict]:
    if _ENFORCE is not None:
        label, inputs = _ENFORCE
        if name not in inputs:
            raise InputViolation(f"{label} read undeclared table {name!r}")
        cols = inputs[name]
        if cols is not None:
            allowed = frozenset(cols)
            hdr = frozenset(header)
            return [_GuardedRow(r, allowed, hdr, name, label) for r in out]
    if _TRACE is not None:
        seen = _TRACE.setdefault(name, set())
        seen.add("__table__")
        return [_TracedRow(r, seen) for r in out]
    return out


def read_table(name: str, typed: bool = False, con=None) -> list[dict]:
    """All rows of a table as dicts keyed by the written header, in written
    order. Missing table -> []. typed=True casts int/float/date columns per
    schema.py (blank -> None); default returns text exactly as written.
    Under an active enforce() the table must be declared and column access
    is guarded (P2)."""
    con = con or connect()
    if not has_table(name, con):
        if _ENFORCE is not None and name not in _ENFORCE[1]:
            raise InputViolation(f"{_ENFORCE[0]} read undeclared table {name!r}")
        if _TRACE is not None:
            _TRACE.setdefault(name, set()).add("__table__")
        return []
    header = table_columns(name, con)
    if not header:
        return []
    sel = ", ".join(_q(c) for c in header)
    rows = con.execute(f"SELECT {sel} FROM {_q(name)} ORDER BY _rowid").fetchall()
    out = _guard_rows(name, header, [dict(zip(header, r)) for r in rows])
    if typed:
        t = _TABLES.get(name)
        if t is not None:
            for r in out:
                for col, kind in t.types.items():
                    if col in r:
                        r[col] = _cast(r[col], kind)
    return out


def _cast(v: str, kind: str):
    if v == "":
        return None
    if kind == "int":
        return int(float(v))
    if kind == "float":
        return float(v)
    if kind == "date":
        from datetime import date as _date

        return _date.fromisoformat(v)
    if kind == "flag01":
        return v == "1"
    return v


def _cell(v) -> str:
    if v is None:
        return ""
    return str(v)


def update_rows(name: str, changes: list[dict], con=None) -> int:
    """Update declared tables row-by-key, without hand-written SQL.

    `changes` is a list of dicts, each carrying the table's declared key
    columns (to match) plus the columns to set. Identifiers are taken from
    the schema declaration and quoted here, so a table or column whose name
    is a reserved word (e.g. `references`) cannot break the statement — the
    defect this function exists to prevent.

    Rules, all raising ValueError rather than silently doing nothing:
      * the table must be declared in schema.py and must declare a key;
      * every change must carry every key column;
      * every column set must be declared for the table;
      * a change may not set a key column (that is a delete plus an insert,
        not an update).
    Returns the number of rows actually changed.
    """
    con = con or connect()
    t = _TABLES.get(name)
    if t is None:
        raise ValueError(f"{name}: not a declared table")
    if not t.key:
        raise ValueError(f"{name}: no declared key; update_rows needs one")
    if not has_table(name, con):
        raise ValueError(f"{name}: table does not exist")
    declared = set(t.columns) | set(t.optional)
    stored = set(table_columns(name, con))
    keys = list(t.key)
    n = 0
    for ch in changes:
        missing = [k for k in keys if k not in ch]
        if missing:
            raise ValueError(f"{name}: change missing key column(s) {missing}")
        sets = {c: v for c, v in ch.items() if c not in keys}
        if not sets:
            continue
        bad = [c for c in sets if c not in declared]
        if bad:
            raise ValueError(f"{name}: undeclared column(s) {bad}")
        absent = [c for c in sets if c not in stored]
        if absent:
            raise ValueError(f"{name}: column(s) {absent} declared but not in the stored table")
        assign = ", ".join(f"{_q(c)} = ?" for c in sets)
        where = " AND ".join(f"{_q(k)} = ?" for k in keys)
        params = [_cell(v) for v in sets.values()] + [_cell(ch[k]) for k in keys]
        before = con.execute(
            f"SELECT count(*) FROM {_q(name)} WHERE {where}", [_cell(ch[k]) for k in keys]
        ).fetchone()[0]
        con.execute(f"UPDATE {_q(name)} SET {assign} WHERE {where}", params)
        n += int(before)
    return n


def add_columns(name: str, columns: list[str] | tuple[str, ...], con=None) -> list[str]:
    """Add declared optional columns to a stored table. Columns already
    present are skipped (idempotent); undeclared columns raise. Returns the
    columns actually added. Replaces hand-written ALTER TABLE in callers."""
    con = con or connect()
    t = _TABLES.get(name)
    if t is None:
        raise ValueError(f"{name}: not a declared table")
    if not has_table(name, con):
        raise ValueError(f"{name}: table does not exist")
    declared = set(t.columns) | set(t.optional)
    bad = [c for c in columns if c not in declared]
    if bad:
        raise ValueError(f"{name}: undeclared column(s) {bad}")
    stored = set(table_columns(name, con))
    added = []
    for c in columns:
        if c in stored:
            continue
        con.execute(f"ALTER TABLE {_q(name)} ADD COLUMN {_q(c)} VARCHAR DEFAULT ''")
        added.append(c)
    return added


def write_table(name: str, rows: list[dict], columns: list[str] | tuple[str, ...], con=None) -> int:
    """Replace a table's contents with rows (dicts; missing keys -> '',
    extra keys ignored — csv.DictWriter(extrasaction='ignore') semantics).
    Undeclared columns are rejected for declared tables; constraints from
    schema.py are enforced. Returns the row count written."""
    con = con or connect()
    header = list(columns)
    t = _TABLES.get(name)
    if t is not None:
        n = len(t.columns)
        if tuple(header[:n]) != t.columns:
            raise ValueError(
                f"{name}: header must start with the declared columns {list(t.columns)}; got {header[:n]}"
            )
        bad = [c for c in header[n:] if c not in t.optional]
        if bad:
            raise ValueError(f"{name}: undeclared columns {bad}")
    # Bulk path: the rows are handed to DuckDB as one NumPy object array per
    # column (numpy is a core dependency), registered as a temporary view and
    # copied in a single INSERT ... SELECT. No temporary file: Windows keeps a
    # file handle open after read_csv, which broke the first version of this
    # function on Jason's machine (gate 0.2, 2026-08-30).
    import numpy as _np

    n = len(rows)
    view = "_biointel_bulk"
    data = {"_rowid": _np.arange(1, n + 1, dtype=_np.int64)}
    for c in header:
        data[c] = _np.array([_cell(r.get(c)) for r in rows], dtype=object)
    sel = ", ".join(["_rowid"] + [f"CAST({_q(c)} AS VARCHAR)" for c in header])
    con.execute("BEGIN")
    try:
        con.execute(_create_sql(name, header, t))
        if n:
            con.register(view, data)
            try:
                con.execute(f"INSERT INTO {_q(name)} SELECT {sel} FROM {view}")
            finally:
                con.unregister(view)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return n


def append_rows(name: str, rows: list[dict], columns: list[str] | tuple[str, ...], con=None) -> int:
    """Append rows to a table (ledger tables only, P17). Creates the table
    with the same declaration and constraints if absent; otherwise the
    stored header must equal `columns`. Constraints (including key
    uniqueness against existing rows) are enforced by the database."""
    con = con or connect()
    header = list(columns)
    if not has_table(name, con):
        return write_table(name, rows, header, con=con)
    stored = table_columns(name, con)
    if stored != header:
        raise ValueError(f"{name}: stored header {stored} differs from {header}")
    if not rows:
        return 0
    import numpy as _np

    start = con.execute(f"SELECT COALESCE(MAX(_rowid), 0) FROM {_q(name)}").fetchone()[0]
    n = len(rows)
    data = {"_rowid": _np.arange(start + 1, start + n + 1, dtype=_np.int64)}
    for c in header:
        data[c] = _np.array([_cell(r.get(c)) for r in rows], dtype=object)
    sel = ", ".join(["_rowid"] + [f"CAST({_q(c)} AS VARCHAR)" for c in header])
    view = "_biointel_bulk"
    con.execute("BEGIN")
    try:
        con.register(view, data)
        try:
            con.execute(f"INSERT INTO {_q(name)} SELECT {sel} FROM {view}")
        finally:
            con.unregister(view)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return n


def drop_table(name: str, con=None) -> None:
    con = con or connect()
    con.execute(f"DROP TABLE IF EXISTS {_q(name)}")


def export_csv(name: str, path: Path, con=None) -> Path:
    """Write a table to a CSV file byte-identical to what csv.DictWriter
    produced from the same rows (\\r\\n line endings, minimal quoting)."""
    con = con or connect()
    header = table_columns(name, con)
    rows = read_table(name, con=con)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def write_export(filename: str, text: str) -> Path:
    """Write a report or other generated text to data/exports/ (disposable)."""
    p = config.EXPORTS / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def read_csv_rows(path: Path) -> tuple[list[str], list[dict]]:
    """Read a CSV file as (header, rows) with the csv module — used by
    migrate and by legacy comparisons only."""
    with path.open(encoding="utf-8", newline="", errors="replace") as f:
        rd = _csv.DictReader(f)
        rows = list(rd)
        return list(rd.fieldnames or []), rows


_FROZEN_RE = _re.compile(r"_frozen_\d{8}$")
