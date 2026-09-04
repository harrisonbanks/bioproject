# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_priorities.py
"""F2 stage 1: probe wiring. Network behaviour is proven by the operator's
probe paste (rule 4.20), not by fixtures."""

from __future__ import annotations

from biointel import priorities


def test_probe_covers_all_three_approved_source_types():
    types = [t for t, _f, _q in priorities.SOURCE_TYPES]
    assert types == ["earnings_call", "10k_strategy", "investor_day"]  # Q1, closed
    assert all(q for _t, _f, q in priorities.SOURCE_TYPES)


def test_probe_samples_two_eras():
    assert len(priorities.PROBE_WINDOWS) == 2
    assert priorities.PROBE_WINDOWS[0][1] < priorities.PROBE_WINDOWS[1][0]


def test_cli_usage_without_network(capsys):
    assert priorities.cli([]) == 1
    assert "priorities probe" in capsys.readouterr().out
