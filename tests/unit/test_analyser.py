# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_analyser.py
"""Gate L3: the deal analyser — span-grounded proposals from real filing
prose, seed yardstick, consume semantics (seed wins on key collision)."""

from __future__ import annotations

import pytest

from biointel import analyser, config, library, schema, store

# Verbatim Tempus 10-Q prose (quarter ended 2026-06-30) — the seed dossier's
# own spans stitched into their filing context (rule 4.20: fixtures are real
# captures or excerpts of them).
TENQ = """
<html><body><p>On July 20, 2026, Tempus AI, Inc. entered into an Agreement and
Plan of Merger with Personalis, Inc., dated as of July 20, 2026, under which
each share of Personalis common stock will be converted into the right to
receive $16.25 per share, payable in shares of Tempus Class A common stock,
subject to a cash election for up to 50% of the aggregate consideration. The
exchange ratio is capped at 0.3356 shares of Tempus Class A common stock. The
Merger Agreement provides for a termination fee of $52.5 million payable by
Personalis under specified circumstances, and either party may terminate if the
merger has not been completed by the Outside Date of April 20, 2027. The
transaction is expected to close in the first quarter of 2027. Prior to the
transaction Tempus held approximately 12.5% of Personalis common stock. The
combination is expected to accelerate our precision-medicine platform across
oncology diagnostics. Prior to the transaction the enterprise value of
approximately $1.5 billion reflects Tempus's existing ownership.</p>
<p>Class A common stock, par value $0.0001 per share, of Tempus AI, Inc.</p>
<p>If the marketing period has commenced, the Outside Date is subject to
extension and either party may extend such date to October 20, 2027.</p>
</body></html>
"""


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
    for t_, cols in (
        ("references", schema.REFERENCE_COLS),
        ("captures", schema.CAPTURE_COLS),
        ("reference_links", schema.REFERENCE_LINK_COLS),
    ):
        store.write_table(t_, [], cols, con=con)
    companies = [{c: "" for c in schema.COMPANY_COLS} for _ in range(2)]
    companies[0].update(
        {"IID": "1379", "Name": "Tempus AI, Inc.", "Ticker": "TEM", "CIK": "1717115"}
    )
    companies[1].update(
        {"IID": "1380", "Name": "Personalis, Inc.", "Ticker": "PSNL", "CIK": "1527753"}
    )
    store.write_table("companies", companies, schema.COMPANY_COLS, con=con)
    ev = {c: "" for c in [*schema.MA_COLS, "deal_id"]}
    ev.update(
        {
            "FilerIID": "1380",
            "Filer": "Personalis, Inc.",
            "FilerTicker": "PSNL",
            "Role": "target",
            "Counterparty": "Tempus AI, Inc.",
            "CounterpartyIID": "1379",
            "AnnounceDate": "2026-07-20",
            "Status": "announced/pending",
            "Verified": "yes",
            "deal_id": analyser.SEED_DEAL_ID,
        }
    )
    store.write_table("ma_events", [ev], [*schema.MA_COLS, "deal_id"], con=con)
    ref_id, _ = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": "0001193125-26-326090",
            "url": "https://www.sec.gov/Archives/edgar/data/1717115/000119312526326090/tem-10q.htm",
            "title": "Tempus 10-Q",
            "publisher": "SEC EDGAR",
            "published_at": "2026-08-05",
            "source_system": "efts",
            "source_key": "0001193125-26-326090:tem-10q.htm",
            "note": "captured by dossier-analyse;form=10-Q;cik=1717115",
        },
        con,
    )
    sha, dst, _new = library.put_bytes(TENQ.encode("utf-8"), ".htm")
    library.add_capture(ref_id, sha, dst, "fetched_html", "test", con)
    yield con
    store.close()


def test_proposals_are_span_grounded_and_match_the_seed_yardstick(env, capsys):
    props, texts = analyser.propose(analyser.SEED_DEAL_ID)
    by_field = {p["fields"].get("field") or p["fields"].get("step_type"): p for p in props}
    assert by_field["price_per_share_usd"]["fields"]["value"] == "16.25"
    assert by_field["exchange_ratio_cap"]["fields"]["value"] == "0.3356"
    assert by_field["termination_fee_usd"]["fields"]["value"] == "5.25e+07"
    assert by_field["outside_date"]["fields"]["value"] == "2027-04-20"
    assert by_field["consideration_form"]["fields"]["value"] == "stock with cash election"
    assert by_field["merger_agreement"]["fields"]["step_date"] == "2026-07-20"
    assert by_field["announce_date"]["fields"]["value"] == "2026-07-20"
    assert by_field["prior_stake_pct"]["fields"]["value"] == "12.5"
    assert by_field["enterprise_value_usd"]["fields"]["value"] == "1.5e+09"
    assert by_field["outside_date_extended"]["fields"]["value"] == "2027-10-20"
    prices = [p for p in props if p["fields"].get("field") == "price_per_share_usd"]
    assert len(prices) == 1  # the par-value $0.0001 never becomes a proposal
    assert by_field["expected_close"]["fields"]["step_date"] == "2027-01-01"
    assert any(p["table"] == "deal_rationale" for p in props)
    assert all(
        analyser._span_ok(p, texts) for p in props
    )  # every span verifies against the capture
    lines = analyser.compare_with_seed(props)
    text = "\n".join(lines)
    assert text.count("MATCH") >= 4  # announce via agreement date path differs; core terms agree
    assert (
        "price_per_share_usd" in text
        and "NOT-PROPOSED" not in text.split("price_per_share_usd")[1].split("\n")[0]
    )


def test_consume_writes_rows_and_never_overwrites_seed(env, capsys):
    terms = [{c: "" for c in schema.DEAL_TERM_COLS}]
    terms[0].update(
        {
            "deal_id": analyser.SEED_DEAL_ID,
            "field": "price_per_share_usd",
            "value": "16.25",
            "doc_id": "seedhash",
            "span": "$16.25",
        }
    )
    store.write_table("deal_terms", terms, schema.DEAL_TERM_COLS, con=env)
    assert analyser.analyse(analyser.SEED_DEAL_ID, consume=True) == 0
    rows = store.read_table("deal_terms", con=store.connect())
    price = [r for r in rows if r["field"] == "price_per_share_usd"]
    assert len(price) == 1 and price[0]["doc_id"] == "seedhash"  # seed row untouched
    assert any(r["field"] == "outside_date" and r["value"] == "2027-04-20" for r in rows)
    tl = store.read_table("deal_timeline", con=store.connect())
    assert any(r["step_type"] == "expected_close" for r in tl)
    # idempotent second consume
    n = len(store.read_table("deal_terms", con=store.connect()))
    analyser.analyse(analyser.SEED_DEAL_ID, consume=True)
    assert len(store.read_table("deal_terms", con=store.connect())) == n


def test_conflicting_field_values_are_held_for_judgement(env, capsys):
    # a second capture whose background section describes an all-cash alternative
    alt = (
        "<html><body><p>Management reviewed the strategic rationale for the "
        "proposal from Party B, an all-cash transaction at a lower price.</p></body></html>"
    )
    con = store.connect()
    ref_id, _ = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": "0001193125-26-999999",
            "url": "https://www.sec.gov/Archives/edgar/data/1527753/000119312526999999/defm14a.htm",
            "title": "Personalis DEFM14A",
            "publisher": "SEC EDGAR",
            "published_at": "2026-08-20",
            "source_system": "efts",
            "source_key": "0001193125-26-999999:defm14a.htm",
            "note": "captured by dossier-analyse;form=DEFM14A;cik=1527753",
        },
        con,
    )
    sha, dst, _new = library.put_bytes(alt.encode("utf-8"), ".htm")
    library.add_capture(ref_id, sha, dst, "fetched_html", "test", con)
    analyser.analyse(analyser.SEED_DEAL_ID, consume=True)
    out = capsys.readouterr().out
    assert "CONFLICTED fields held for judgement" in out and "consideration_form" in out
    rows = store.read_table("deal_terms", con=store.connect())
    assert not any(r["field"] == "consideration_form" for r in rows)  # neither value consumed
    # a verdict resolves the conflict: judge the election value correct, the all-cash wrong
    from biointel import efts

    props, _texts = analyser.propose(analyser.SEED_DEAL_ID)
    ids = {
        p["fields"].get("value"): p["proposal_id"]
        for p in props
        if p["fields"].get("field") == "consideration_form"
    }
    efts.judge(ids["stock with cash election"], "correct")
    efts.judge(ids["all cash"], "wrong")
    analyser.analyse(analyser.SEED_DEAL_ID, consume=True)
    rows = store.read_table("deal_terms", con=store.connect())
    forms = [r for r in rows if r["field"] == "consideration_form"]
    assert len(forms) == 1 and forms[0]["value"] == "stock with cash election"


def test_rationale_sentences_dedup_across_documents(env):
    dup = (
        "<html><body><p>The complementary acquisition builds on the companies' "
        "existing partnership, established in November 2023.</p></body></html>"
    )
    con = store.connect()
    for n in ("777777", "888888"):
        ref_id, _ = library.upsert_reference(
            {
                "ref_type": "sec_filing",
                "sec_accession": f"0001193125-26-{n}",
                "url": f"https://www.sec.gov/Archives/edgar/data/1717115/000119312526{n}/f425.htm",
                "title": "425",
                "publisher": "SEC EDGAR",
                "published_at": "2026-07-21",
                "source_system": "efts",
                "source_key": f"0001193125-26-{n}:f425.htm",
                "note": "captured by dossier-analyse;form=425;cik=1717115",
            },
            con,
        )
        sha, dst, _new = library.put_bytes((dup + f"<!-- {n} -->").encode("utf-8"), ".htm")
        library.add_capture(ref_id, sha, dst, "fetched_html", "test", con)
    props, _texts = analyser.propose(analyser.SEED_DEAL_ID)
    dupes = [
        p
        for p in props
        if p["table"] == "deal_rationale" and "existing partnership" in p["fields"]["statement"]
    ]
    assert len(dupes) == 1  # the same sentence in two filings proposes once
