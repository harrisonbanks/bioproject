# tests/unit/test_config_constants.py
"""Unit test for biointel.config: every module-level constant is assigned once.

Guards the defect fixed at gate 0.1: scripts/refactor/50_config_logging.py
wrote its endpoint block before its later guard assertion failed, and on
re-runs appended the nine endpoint constants twice more (and
RELATIONSHIPS_CSV was assigned twice from an earlier edit).
"""

from __future__ import annotations

import ast
from collections import Counter

from biointel import config


def _top_level_assignments() -> Counter:
    tree = ast.parse(open(config.__file__, encoding="utf-8").read())
    names = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.append(tgt.id)
    return Counter(names)


def test_each_config_constant_defined_exactly_once():
    dup = {n: k for n, k in _top_level_assignments().items() if k != 1}
    assert dup == {}, f"constants assigned more than once: {dup}"


def test_endpoint_constants_present():
    for name in (
        "SEC_TICKERS",
        "SEC_SUBS",
        "AV_QUERY",
        "FDA_DRUGSFDA",
        "FDA_CRL",
        "YAHOO_CHART",
        "CTGOV_BASE",
        "SEC_BROWSE",
        "SEC_SUBS_PAGE",
        "SEC_ARCHIVE",
        "SEC_ARCHIVE_DOC",
        "SEC_XBRL_FACTS",
        "FDA_ORANGE_BOOK",
        "CHEMBL_API",
        "WIKI_API",
        "RELATIONSHIPS_CSV",
    ):
        assert getattr(config, name)
