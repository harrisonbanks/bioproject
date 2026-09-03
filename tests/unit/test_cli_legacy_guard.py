# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_cli_legacy_guard.py
"""P7 amendment: LEGACY commands never re-run. Their reports are frozen
baseline files; the CLI must refuse before any legacy module is imported."""

from __future__ import annotations

import sys

import pytest

from biointel.interfaces import cli


@pytest.mark.parametrize("cmd", sorted(cli._LEGACY_COMMANDS))
def test_legacy_commands_refuse_without_importing_legacy_code(cmd, capsys, monkeypatch):
    # if the guard is bypassed these imports would run; make them fail loudly
    monkeypatch.setitem(sys.modules, "biointel.baselines", None)
    rc = cli.main(["biointel", cmd])
    out = capsys.readouterr().out
    assert rc == 2
    assert "LEGACY" in out and cli._LEGACY_COMMANDS[cmd] in out


def test_live_commands_are_not_guarded():
    for live in ("predict", "pairs-exact", "pairs-full-exact", "pairs-aspect", "stakes"):
        assert live not in cli._LEGACY_COMMANDS
