# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_schema.py
"""Unit tests for biointel.schema (gate 0.1).

1. Every column constant a module writes with must equal the schema's
   declared column list for that table, so the two cannot drift.
2. `validate_table` reports a conformant fixture as conformant and a
   deliberately malformed fixture with the exact violations.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from biointel import features, labels, pipeline, schema, score, study, universe
from biointel.sources import chembl

# (module constant, schema constant) pairs; one per table-writing constant.
COLUMN_CONSTANTS = [
    (pipeline.COMPANY_COLS, schema.COMPANY_COLS),
    (pipeline.EVENT_COLS, schema.EVENT_COLS),
    (pipeline.PRICE_COLS, schema.PRICE_COLS),
    (pipeline.TRIAL_COLS, schema.TRIAL_COLS),
    (pipeline.FIN_COLS, schema.FIN_COLS),
    (pipeline.SNAP_COLS, schema.SNAP_COLS),
    (pipeline.PARTNER_COLS, schema.PARTNER_COLS),
    (pipeline.PSUM_COLS, schema.PSUM_COLS),
    (pipeline.REL_COLS, schema.REL_COLS),
    (pipeline.DEAL_COLS, schema.DEAL_COLS),
    (pipeline.CP_COLS, schema.CP_COLS),
    (universe.UNIVERSE_COLS, schema.UNIVERSE_COLS),
    (labels.MA_COLS, schema.MA_COLS),
    (labels.PANEL_COLS, schema.PANEL_COLS),
    (labels.VERIFIED_COLS, schema.VERIFIED_COLS),
    (labels.HARVEST_COLS, schema.HARVEST_COLS),
    (labels.QA_COLS, schema.QA_COLS),
    (features.FEATURE_COLS, schema.FEATURE_COLS),
    (features.MODEL_COLS, schema.MODEL_COLS),
    (study.STUDY_COLS, schema.STUDY_COLS),
    (score.PRED_COLS, schema.PRED_COLS),
    (chembl.OUT_COLS, schema.DRUG_TARGET_COLS),
]


@pytest.mark.parametrize("module_cols,schema_cols", COLUMN_CONSTANTS)
def test_module_columns_equal_schema(module_cols, schema_cols):
    assert list(module_cols) == list(schema_cols)


def test_every_declared_table_path_is_unique_and_in_data_layer():
    paths = [t.path for t in schema.TABLES]
    assert len(paths) == len(set(paths))
    assert all(p.startswith(("silver/", "gold/")) for p in paths)


def test_study_summary_columns_match_summarize_output():
    rows = [{"Event": "Approval", "Outcome": "New drug", **{m: 1.0 for m in schema._STUDY_METRICS}}]
    out = study.summarize(rows)
    assert tuple(out[0].keys()) == schema.STUDY_SUMMARY_COLS


def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_validate_conformant_fixture(tmp_path):
    t = schema.TABLE_BY_PATH["silver/events.csv"]
    _write(
        tmp_path / t.path,
        list(t.columns),
        [
            [
                "0",
                "Acme Inc",
                "Approval",
                "2024-01-15",
                "N021234",
                "Drug",
                "New drug",
                "P",
                "",
                "ORIG",
            ],
            [
                "0",
                "Acme Inc",
                "Rejection",
                "2024-03-01",
                "N021235",
                "",
                "Never approved",
                "",
                "",
                "",
            ],
        ],
    )
    r = schema.validate_table(t, tmp_path)
    assert r["status"] == "conformant"
    assert r["rows"] == 2


def test_validate_reports_each_violation_kind(tmp_path):
    t = schema.TABLE_BY_PATH["silver/events.csv"]
    _write(
        tmp_path / t.path,
        list(t.columns) + ["Rogue"],
        [
            ["0", "Acme Inc", "Approval", "2024-01-15", "N1", "", "New drug", "", "", "ORIG", ""],
            ["0", "Acme Inc", "Approval", "2024-01-15", "N1", "", "New drug", "", "", "ORIG", ""],
            ["x", "Acme Inc", "Withdrawal", "15/01/2024", "N2", "", "", "", "", "", ""],
        ],
    )
    r = schema.validate_table(t, tmp_path)
    assert r["status"] == "violations"
    text = "\n".join(r["violations"])
    assert "undeclared columns ['Rogue']" in text
    assert "duplicate row" in text
    assert "column IID (int)" in text
    assert "column Date (date)" in text
    assert "column Event (enum)" in text


def test_validate_header_mismatch_and_optional_columns(tmp_path):
    t = schema.TABLE_BY_PATH["silver/relationships.csv"]
    _write(tmp_path / t.path, list(t.columns) + list(t.optional), [])
    assert schema.validate_table(t, tmp_path)["status"] == "conformant"
    _write(tmp_path / t.path, list(t.columns)[1:], [])
    r = schema.validate_table(t, tmp_path)
    assert r["status"] == "violations" and r["violations"][0].startswith("header:")


def test_validate_absent_and_planned(tmp_path):
    results = {r["path"]: r["status"] for r in schema.validate_all(tmp_path)}
    assert results["silver/companies.csv"] == "absent"
    assert results["silver/manual_notes.csv"] == "absent"  # live since 2.10
    assert results["silver/benchmarks.csv"] == "planned"
    assert "0 conformant" in schema.format_report(schema.validate_all(tmp_path))
