# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_dossier.py
"""Gate L2: dossier schema + span-verified seed loader (Ontology v5 §3.10, P19)."""

from __future__ import annotations

import pytest

from biointel import config, dossier, library, schema, store


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "bronze").mkdir(parents=True)
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(config, "BRONZE", data / "bronze")
    monkeypatch.setattr(config, "DUCKDB", data / "biointel.duckdb")
    monkeypatch.setattr(config, "EXPORTS", data / "exports")
    store.close()
    con = store.connect(config.DUCKDB)
    for t, cols in (
        ("references", schema.REFERENCE_COLS),
        ("captures", schema.CAPTURE_COLS),
        ("reference_links", schema.REFERENCE_LINK_COLS),
    ):
        store.write_table(t, [], cols, con=con)
    yield con
    store.close()


def _capture(con, tmp_path, accession: str, name: str, html: str) -> str:
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    sha, dst, _ = library.put_file(p)
    ref_id, _ = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": accession,
            "title": name,
            "url": f"https://www.sec.gov/x/{name}",
        },
        con,
    )
    library.add_capture(ref_id, sha, dst, "fetched_text", "test", con)
    return sha


TENQ = (
    "<html><body>On July 20, 2026 the parties entered a Merger Agreement at "
    "$16.25 per share at $1.5 billion enterprise value; terminable below "
    "$46.00; outside date April 20, 2027; Tempus held 12.5 % of the shares; "
    "Merck executed a voting agreement; holders may elect cash.</body></html>"
)
EK = (
    "<html><body>Personalis entered a Commercialization and Reference "
    "Laboratory Agreement with Tempus.</body></html>"
)
F425 = (
    "<html><body>Equity value $1.9 billion; exchange ratio capped at "
    "0.3356; extending into MRD monitoring.</body></html>"
)


@pytest.fixture()
def seeded_library(env, tmp_path):
    con = env
    _capture(con, tmp_path, dossier.ACC_10Q, "tenq.htm", TENQ)
    _capture(con, tmp_path, dossier.ACC_8K, "ek.htm", EK)
    _capture(con, tmp_path, dossier.ACC_425, "f425.htm", F425)
    return con


# ---------------------------------------------------------------- schema
def test_dossier_tables_declared_live_with_doc_id_and_span():
    for path in (
        "silver/deal_terms.csv",
        "silver/deal_timeline.csv",
        "silver/deal_rationale.csv",
        "silver/deal_aspects.csv",
        "silver/deal_comparables.csv",
        "silver/equity_stakes.csv",
        "silver/stated_priorities.csv",
        "silver/assets.csv",
    ):
        t = schema.TABLE_BY_PATH[path]
        assert not t.planned
        assert "doc_id" in t.columns and "span" in t.columns


def test_aspect_enum_matches_the_ontology_vocabulary():
    t = schema.TABLE_BY_PATH["silver/deal_aspects.csv"]
    assert t.enums["aspect"] == schema.ASPECTS
    assert len(schema.ASPECTS) == 15


def test_ma_events_gains_optional_deal_id_and_v4_edge_names_declared():
    assert "deal_id" in schema.TABLE_BY_PATH["silver/ma_events.csv"].optional
    for r in ("exclusive_commercial_partner", "distributes_for", "customer_of", "holds_stake_in"):
        assert r in schema.RELATIONSHIP_TYPES


# ---------------------------------------------------------------- normalizer
def test_normalize_strips_tags_entities_case_and_whitespace():
    raw = "<p>Price&nbsp;of   <b>$16.25</b>\nPER Share</p>"
    assert "price of $16.25 per share" in dossier.normalize(raw)


def test_span_pattern_tolerates_symbol_boundary_whitespace():
    # inline-XBRL tag stripping yields "12.5 %" and "$ 1.9 billion"
    assert dossier.span_pattern("12.5%").search(dossier.normalize("held 12.5</x>% of"))
    assert dossier.span_pattern("$1.9 billion").search(dossier.normalize("<b>$</b>1.9 billion"))
    assert not dossier.span_pattern("12.5%").search("held 12.4 % of")


# ---------------------------------------------------------------- verify + load
def test_all_seed_rows_verify_against_the_fixture_captures(seeded_library):
    verdicts = dossier.verify_seed(seeded_library)
    assert len(verdicts) == len(dossier.SEED)
    assert all(v["status"] == "FOUND" for v in verdicts)
    assert all(len(v["doc_id"]) == 64 for v in verdicts)


def test_seed_loads_verified_rows_and_records_a_ledger_run(seeded_library):
    r = dossier.seed()
    assert r["status"] == "ok" and r["held"] == 0
    assert r["loaded"] == len(dossier.SEED)
    terms = store.read_table("deal_terms", con=seeded_library)
    assert all(len(x["doc_id"]) == 64 and x["span"] for x in terms)
    price = next(x for x in terms if x["field"] == "price_per_share_usd")
    assert price["value"] == "16.25"
    runs = store.read_table("runs", con=seeded_library)
    assert any(x["command"] == "dossier-seed" for x in runs)
    # empty declared tables exist and are conformant
    results = {x["path"]: x for x in schema.validate_db(seeded_library)}
    for t in (
        "deal_terms",
        "deal_aspects",
        "equity_stakes",
        "assets",
        "stated_priorities",
        "deal_comparables",
    ):
        assert results[t]["status"] == "conformant"


def test_seed_is_idempotent(seeded_library):
    dossier.seed()
    first = store.read_table("deal_aspects", con=seeded_library)
    dossier.seed()
    second = store.read_table("deal_aspects", con=seeded_library)
    assert [(r["aspect"], r["doc_id"]) for r in first] == [
        (r["aspect"], r["doc_id"]) for r in second
    ]


def test_rows_whose_span_is_missing_are_held_not_loaded(env, tmp_path):
    con = env
    # capture only the 8-K text: every 10-Q/425-cited row must be held
    _capture(con, tmp_path, dossier.ACC_8K, "ek.htm", EK)
    r = dossier.seed()
    assert r["held"] > 0 and r["status"] == "held"
    terms = store.read_table("deal_terms", con=con)
    assert terms == []  # no 10-Q/425 term row entered
    tl = store.read_table("deal_timeline", con=con)
    assert len(tl) == 1 and tl[0]["step_type"] == "commercial_agreement"


def test_report_mode_writes_nothing(seeded_library):
    r = dossier.seed(report_only=True)
    assert r["loaded"] == 0
    assert (
        not store.has_table("deal_terms", seeded_library)
        or store.read_table("deal_terms", con=seeded_library) == []
    )
