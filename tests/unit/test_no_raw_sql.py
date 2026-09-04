# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_no_raw_sql.py
"""P18 enforced mechanically: every table read and write goes through the
store layer. Hand-written SQL in a model or feeder is how the reserved-word
collision on `references` happened (2026-09-03). Renaming that table was
considered and cancelled — 29 call sites across 8 modules, two of them
fingerprint-protected, plus a live-database migration, to fix a problem the
store layer already closes by quoting every identifier from the schema
declaration. This test is the cheaper, stronger guard.

The allowlist below is the infrastructure tier that legitimately speaks SQL
today. It may shrink; adding to it is a design decision, not a convenience.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "biointel"
ALLOWED = {"store.py", "results.py", "schema.py", "migrate.py"}
_EXEC = re.compile(r"\.execute\(|\.executemany\(|\.sql\(")


def test_no_raw_sql_outside_the_store_tier():
    offenders = []
    for p in SRC.rglob("*.py"):
        if p.name in ALLOWED:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if _EXEC.search(line):
                offenders.append(f"{p.relative_to(SRC)}:{i}: {line.strip()}")
    assert not offenders, "raw SQL outside the store tier:\n" + "\n".join(offenders)


def test_allowlist_is_exactly_the_infrastructure_tier():
    # if this fails, the allowlist changed; record why in the constants audit
    assert ALLOWED == {"store.py", "results.py", "schema.py", "migrate.py"}
