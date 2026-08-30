"""Unit tests for biointel.config.require (fail-fast settings)."""

import pytest

from biointel import config


def test_require_raises_naming_the_missing_variable(monkeypatch):
    monkeypatch.delenv("BIOINTEL_TEST_UNSET", raising=False)
    with pytest.raises(RuntimeError, match="BIOINTEL_TEST_UNSET"):
        config.require("BIOINTEL_TEST_UNSET")


def test_require_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("BIOINTEL_TEST_SET", "value")
    assert config.require("BIOINTEL_TEST_SET") == "value"
