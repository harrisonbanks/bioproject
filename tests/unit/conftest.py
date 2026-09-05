# C:\Users\JB\Documents\dev\bioindustry\tests\unit\conftest.py
"""No unit test may touch the live database. Found 2026-09-04: a test without
a database fixture called code that now reads the registry, and on the
operator machine it opened data\\biointel.duckdb and read 1,379 real
companies, changing the test's outcome between machines. This autouse
fixture points config at a per-test temp directory before every test, so a
test that forgets its fixture gets an empty scratch database, never the real
one. Tests that declare their own `db` fixture override these paths again;
that is fine."""

from __future__ import annotations

import pytest

from biointel import config, store


@pytest.fixture(autouse=True)
def _never_the_live_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path / "scratch")
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "scratch" / "unit.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "scratch" / "exports")
    monkeypatch.setattr(config, "BRONZE", tmp_path / "scratch" / "bronze")
    (tmp_path / "scratch").mkdir(exist_ok=True)
    store.close()
    yield
    store.close()
