"""Unit tests for biointel.match.canon (pure function, no I/O)."""

from biointel.match import canon


def test_canon_uppercases_and_strips_legal_suffix():
    assert canon("Pfizer Inc.") == "PFIZER"


def test_canon_removes_apostrophes_and_descriptors():
    assert canon("Dr. Reddy's Labs") == "DR REDDYS"


def test_canon_expands_ampersand():
    assert canon("AT&T") == "AT AND T"


def test_canon_none_is_empty():
    assert canon(None) == ""


def test_canon_never_returns_empty_for_nonempty_input():
    assert canon("Inc") == "INC"
