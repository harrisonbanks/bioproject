# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_stakes.py
"""Gate F1 stage 1 tests: the probe's deterministic member selection and its
era/form constants. Network and capture behaviour are proven by the operator's
probe paste (rule 4.20), not by fixtures."""

from __future__ import annotations

import pathlib

import pytest

from biointel import config, schema, stakes, store


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(config, "BRONZE", tmp_path / "bronze")
    store.close()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()


def test_member_ciks_deterministic_iid_order_and_cikless_skipped(db):
    rows = []
    for iid, tick, cik in ((3, "CCC", "300"), (1, "AAA", "100"), (2, "BBB", "")):
        r = dict.fromkeys(schema.COMPANY_COLS, "")
        r.update({"IID": str(iid), "Name": f"N{iid}", "Ticker": tick, "CIK": cik})
        rows.append(r)
    store.write_table("companies", rows, schema.COMPANY_COLS)
    got = stakes._member_ciks()
    assert got == [("100", "AAA", "N1"), ("300", "CCC", "N3")]  # IID order; no-CIK row skipped


def test_probe_constants_cover_the_structured_era():
    assert len(stakes.ERAS) == 4
    assert stakes.ERAS[-1][0] >= "2025-01-01"  # post-mandate structured filings sampled
    for f in ("SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"):
        assert f in stakes.STAKE_FORMS


# ---- stage 2a: cover-page parser locked against all nine probe captures ----
FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "stakes"

EXPECT = {
    "2b2c7d15b92b": (
        "i-STAT Corporation",
        "Abbott Laboratories",
        "37.2",
        "9079441",
        "2003-12-31",
        "450312103",
        True,
    ),
    "2f421ecb67d6": (
        "Abbott Laboratories",
        "The Vanguard Group",
        "5.93",
        "89329582",
        "2014-12-31",
        "002824100",
        False,
    ),
    "62d58afeee49": (
        "Mylan N.V.",
        "Abbott Laboratories",
        "15.32",
        "75000000",
        "2015-04-06",
        "N59465109",
        True,
    ),
    "7b54007c5c4d": (
        "Abbott Laboratories",
        "The Vanguard Group",
        "8.31",
        "147272920",
        "2020-12-31",
        "002824100",
        False,
    ),
    "80273f62f73c": (
        "Abbott Laboratories",
        "Abbott Laboratories Stock Retirement Trust",
        "5.4",
        "89278257",
        None,
        "002824100",
        False,
    ),
    "c0a53f7b3eda": (
        "Akorn, Inc.",
        "Rao Akella",
        "14.8",
        "18640445",
        "2020-01-23",
        "009728106",
        False,
    ),
    "c9f5f52efb06": (
        "Mylan N.V.",
        "Abbott Laboratories",
        "14.25",
        "69750000",
        "2015-06-16",
        "N59465109",
        False,
    ),
    "f3b9737cc8f2": (
        "Abbott Laboratories",
        "Abbott Laboratories Stock Retirement Trust",
        "4.0",
        "61715742",
        "2004-12-31",
        "002824100",
        False,
    ),
    "fd1b534d6be8": (
        "Abbott Laboratories",
        "The Vanguard Group",
        "8.92",
        "155480794",
        "2022-12-30",
        "002824100",
        False,
    ),
}


def test_parse_cover_all_nine_probe_captures():
    """Every field checked against the filings as read (rule 4.20). The 2003
    trust filing genuinely lacks the event-date line (None -> filing-date
    fallback at row build); the two Mylan CUSIPs carry the non-US leading
    letter; the 2005 trust row is the 4.0% exit specimen; Akorn's share
    count sits beyond the digits of 'Row (11)'."""
    for sha, (issuer, owner, pct, shares, event, cusip, has_item4) in EXPECT.items():
        r = stakes.parse_cover((FIXTURES / f"{sha}.txt").read_text(encoding="utf-8"))
        assert r.get("issuer_name") == issuer, sha
        assert r.get("owner_name") == owner, sha
        assert r.get("percent") == pct, sha
        assert r.get("shares") == shares, sha
        assert r.get("event_date") == event, sha
        assert r.get("cusip") == cusip, sha
        assert bool(r.get("item4_text")) is has_item4, sha
        if pct:
            assert r.get("percent_span"), sha  # evidence span rides with the number


def test_parse_cover_refuses_non_cover_text():
    assert stakes.parse_cover("This is an ordinary 10-K risk factors page.") == {}


def _companies(*rows_):
    out = []
    for iid, tick, cik in rows_:
        r = dict.fromkeys(schema.COMPANY_COLS, "")
        r.update({"IID": str(iid), "Name": f"N{iid}", "Ticker": tick, "CIK": cik})
        out.append(r)
    store.write_table("companies", out, schema.COMPANY_COLS)


# ---- stage 2b: XML parser, row build, idempotent collect, measurement ----
XML_EXPECT = {
    "9183de4cfbd8": (
        "The Vanguard Group",
        "102909",
        "1800",
        "Abbott Laboratories",
        "002824100",
        "2026-03-13",
        "0",
        "0",
    ),
    "ffb8318ffe07": (
        "BlackRock, Inc.",
        "2012383",
        "14272",
        "BRISTOL MYERS SQUIBB CO",
        "110122108",
        "2025-03-31",
        "143574230",
        "7.1",
    ),
    "7df83fc281b5": (
        "The Vanguard Group",
        "102909",
        "14272",
        "Bristol-Myers Squibb Co",
        "110122108",
        "2026-03-13",
        "0",
        "0",
    ),
}


def test_parse_structured_all_three_probe_xmls():
    """Both structured variants proven by capture: nested issuerCusipNumber
    (X0202) and flat issuerCusip with no schemaVersion (2025 BlackRock);
    owner CIK from filerCredentials; MM/DD/YYYY event date to ISO."""
    for sha, (owner, ocik, icik, iname, cusip, event, shares, pct) in XML_EXPECT.items():
        r = stakes.parse_structured((FIXTURES / f"{sha}.xml").read_text(encoding="utf-8"))
        assert r.get("owner_name") == owner, sha
        assert r.get("owner_cik") == ocik, sha
        assert r.get("issuer_cik") == icik, sha
        assert r.get("issuer_name") == iname, sha
        assert r.get("cusip") == cusip, sha
        assert r.get("event_date") == event, sha
        assert r.get("shares") == shares, sha
        assert r.get("percent") == pct, sha


def test_parse_structured_refuses_garbage():
    assert stakes.parse_structured("<html>not a schedule</html>") == {}
    assert stakes.parse_structured("no xml at all") == {}


def _hit(sha="a" * 64, form="SC 13D", ciks=("1800", "999777"), fd="2015-04-07"):
    return {
        "sha": sha,
        "form": form,
        "ciks": list(ciks),
        "file_date": fd,
        "adsh": "0001-15-000001",
        "doc": "d.htm",
    }


def test_row_from_owner_resolution_and_exit_semantics():
    parsed = {
        "percent": "15.32",
        "event_date": "2015-04-06",
        "owner_name": "Abbott Laboratories",
        "percent_span": "Percent of Class ... 15.32%",
        "shares": "75000000",
        "cusip": "N59465109",
    }
    r = stakes._row_from(_hit(), parsed, "1800")
    assert r["holder_key"] == "CIK:999777"  # the associated CIK that is not the subject
    assert r["issuer_key"] == "CIK:1800"
    assert r["as_of"] == "2015-04-06"  # event date wins over filing date
    assert r["form"] == "SC 13D" and r["accession"] == "0001-15-000001"
    # exit amendments write at their stated percent (Q4)
    r0 = stakes._row_from(_hit(), {**parsed, "percent": "0"}, "1800")
    assert r0 is not None and r0["percent"] == "0"
    # no event date -> filing-date fallback (the 2003 capture)
    r2 = stakes._row_from(_hit(), {k: v for k, v in parsed.items() if k != "event_date"}, "1800")
    assert r2["as_of"] == "2015-04-07"
    # XML owner CIK beats hit metadata
    r3 = stakes._row_from(_hit(), {**parsed, "owner_cik": "102909"}, "1800")
    assert r3["holder_key"] == "CIK:102909"
    # ambiguous metadata (three CIKs) -> name fallback key
    r4 = stakes._row_from(_hit(ciks=("1800", "1", "2")), parsed, "1800")
    assert r4["holder_key"].startswith("NAME:")
    # unparseable percent -> no row, never a guess
    assert stakes._row_from(_hit(), {**parsed, "percent": "n/a"}, "1800") is None


def test_run_writes_idempotently_and_proposes_stubs(db, monkeypatch):
    _companies((1, "AAA", "100"))

    def fake_search(q, forms, start, end, cik=None, page_from=0):
        if forms == stakes.STAKE_FORMS and cik == "100" and page_from == 0:
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "0001-15-000001:d.htm",
                            "_source": {
                                "ciks": ["0000000100", "0000999777"],
                                "display_names": ["N1 (AAA)", "Abbott Laboratories"],
                                "file_date": "2015-04-07",
                                "form": "SC 13D/A",
                            },
                        }
                    ],
                    "total": {"value": 1},
                }
            }
        return {"hits": {"hits": [], "total": {"value": 0}}}

    monkeypatch.setattr(stakes, "search", fake_search)
    monkeypatch.setattr(stakes, "_capture", lambda h, con: ("f" * 64, ".htm", "text/html"))
    monkeypatch.setattr(
        stakes.library, "store_path", lambda sha, ext: FIXTURES / "62d58afeee49.txt"
    )
    monkeypatch.setattr(stakes, "_owner_sic", lambda cik: "2834")
    assert stakes.run() == 0
    rows = store.read_table("equity_stakes")
    mine = [r for r in rows if r.get("accession") == "0001-15-000001"]
    assert len(mine) == 1
    r = mine[0]
    assert r["holder_key"] == "CIK:999777" and r["issuer_key"] == "CIK:100"
    assert r["percent"] == "15.32" and str(r["as_of"])[:10] == "2015-04-06"
    assert r["form"] == "SC 13D/A" and r["owner_name"] == "Abbott Laboratories"
    assert r["cusip"] == "N59465109" and r["shares"] == "75000000"
    n1 = len(rows)
    assert stakes.run() == 0  # second run: same world, no duplicates
    assert len(store.read_table("equity_stakes")) == n1
    stubs = (config.EXPORTS / "stakes_proposed_stubs.txt").read_text(encoding="utf-8")
    assert "cik 999777 sic 2834" in stubs  # proposed, never auto-added (Q3)


def test_sample_and_precision_retire_wrong_rows(db, monkeypatch, capsys):
    cols = list(schema.EQUITY_STAKE_COLS) + list(schema.EQUITY_STAKE_F1_COLS)
    rows = []
    for i in range(3):
        rows.append(
            {
                "holder_key": f"CIK:90{i}",
                "issuer_key": "CIK:100",
                "percent": "9.9",
                "as_of": f"2015-01-0{i + 1}",
                "doc_id": f"{i}{'e' * 63}",
                "span": "9.9%",
                "form": "SC 13D",
                "filing_date": f"2015-01-0{i + 1}",
                "shares": "1",
                "owner_name": f"O{i}",
                "accession": f"000{i}",
                "cusip": "",
                "item4_text": "",
            }
        )
    store.write_table("equity_stakes", rows, cols)
    assert stakes.sample(2) == 0
    out = capsys.readouterr().out
    assert "F0eeeeeeeeeee" in out or "F1eeeeeeeeeee" in out or "F2eeeeeeeeeee" in out
    review = dict.fromkeys(schema.CANDIDATE_REVIEW_COLS, "")
    r1 = {
        **review,
        "review_id": "r1",
        "candidate_id": "F0" + "e" * 11,
        "rule_version": stakes.RULE_VERSION,
        "verdict": "wrong",
        "reviewer": "t",
        "reviewed_at": "2026-09-03",
    }
    r2 = {**r1, "review_id": "r2", "candidate_id": "F1" + "e" * 11, "verdict": "correct"}
    store.write_table("candidate_reviews", [r1, r2], schema.CANDIDATE_REVIEW_COLS)
    assert stakes.precision() == 0
    left = store.read_table("equity_stakes")
    assert len(left) == 2 and all(str(r["doc_id"])[0] != "0" for r in left)


# ---- F1-r2: patterns from the offline miss analysis (verbatim capture text) ----
ITEM_STYLE = (
    "holding company in accordance with Section 240.13d-1(b)(ii)(G). (Note: See Item 7). "
    "Item 4. Ownership (a) Amount Beneficially Owned: 3,460,000 (b) Percent of Class: 4.868% "
    "(c) Number of shares as to which such person has: (i) sole power to vote: 0"
)
ROW_DIGIT_AFTER_LABEL = (
    "PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) 11 1.1% [See First Preliminary Note] "
    "TYPE OF REPORTING PERSON (See Instructions) 12 PN"
)
DOTTED_LEADER = (
    "11.Percent of Class Represented by Amount in Row (9) "
    "....................................................................... 4.63%*"
)
OWNER_ROW_DIGIT = (
    "NAMES OF REPORTING PERSONS 1 I.R.S. IDENTIFICATION NO. OF ABOVE PERSONS (ENTITIES ONLY) "
    "Invus Public Equities, L.P. 2 CHECK THE APPROPRIATE BOX"
)


def test_r2_item_style_percent_and_shares():
    r = stakes.parse_cover(ITEM_STYLE)
    assert r.get("percent") == "4.868"
    assert r.get("shares") == "3460000"


def test_r2_row_digit_between_label_and_value():
    assert stakes.parse_cover(ROW_DIGIT_AFTER_LABEL).get("percent") == "1.1"


def test_r2_dotted_leader_gap():
    assert stakes.parse_cover(DOTTED_LEADER).get("percent") == "4.63"


def test_r2_owner_label_with_row_digit():
    r = stakes.parse_cover(OWNER_ROW_DIGIT + " Percent of Class: 9.9%")
    assert r.get("owner_name") == "Invus Public Equities, L.P."


def test_r3_exit_filing_records_zero_not_the_qualified_number():
    """Superseded r2's refusal (decision of record): a closing filing states
    a true dated fact — the holder fell below the threshold — so it is
    written as 0, never as the qualified "5" it denies holding."""
    t = "PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) Less than 5% (closing filing)"
    r = stakes.parse_cover(t)
    assert r.get("percent") == "0"
    assert "less than 5%" in r.get("percent_span", "").lower()


# ---- F1-r3: bare-number percents, "-0-", and qualified exits as 0 ----
L = "PERCENT OF CLASS REPRESENTED BY AMOUNT IN "
R3 = [
    (L + "ROW 9 0.00 ____ 12. TYPE OF REPORTING PERSON * EP", "0.00"),
    (L + "ROW (9) 9.99 12. TYPE OF REPORTING PERSON (SEE INSTRUCTIONS) CO", "9.99"),
    (L + "ROW (9) 11 1.1% [See First Preliminary Note] TYPE OF REPORTING PERSON", "1.1"),
    (L + "Row (9) 0.15 12. Type of Reporting Person IN", "0.15"),
    (L + "ROW (9): 4.2 See Exhibit A 12) TYPE OF REPORTING PERSON: HC", "4.2"),
    (L + "Row (9) -0- 12) Type of Reporting Person CO", "0"),
    (L + "ROW (9) Less than 5% (closing filing) 12 TYPE OF REPORTING PERSON* IA", "0"),
    (L + "ROW (9) Less than 0.1% 12 TYPE OF REPORTING PERSON PN", "0"),
    (L + "Row (9) Less than 1% 12. Type of Reporting Person PN", "0"),
    (L + "ROW (9) 12 TYPE OF REPORTING PERSON IA, PN CUSIP No.: 29251M106", None),
    (L + "ROW 9 7.62 12. TYPE OF REPORTING PERSON IV", "7.62"),
    (L + "ROW (9) 37.2%(1)(2) 12 TYPE OF REPORTING PERSON CO", "37.2"),
]


def test_r3_percent_layouts_from_miss_specimens():
    """Every string is verbatim from a real capture the r2 parser missed.
    Exit filings ("Less than X%", "-0-") record 0 — the true dated fact the
    amendment chain must carry — with the phrase kept in the span. A blank
    row 11 yields no percent: nothing is invented from row 12's text."""
    for text, want in R3:
        got, span = stakes._percent_of(text)
        assert got == want, text[:70]
        if want is not None:
            assert span


def test_r4_structured_13d_tag_set():
    """The structured 13D schema uses different tag names from 13G
    (percentOfClass, aggregateAmountOwned, issuerCIK, issuerCUSIP,
    dateOfEvent, reportingPersonCIK) — all verbatim from the Innoviva /
    Armata capture that the r3 parser rejected."""
    r = stakes.parse_structured((FIXTURES / "0919f9aca1fa.xml").read_text(encoding="utf-8"))
    assert r["owner_name"] == "Innoviva, Inc."
    assert r["owner_cik"] == "1080014"
    assert r["issuer_cik"] == "921114"
    assert r["issuer_name"] == "Armata Pharmaceuticals, Inc."
    assert r["cusip"] == "04216R102"
    assert r["event_date"] == "2025-03-12"
    assert r["shares"] == "64178259"
    assert r["percent"] == "85.2"
    assert r["item4_text"]


# ---- F1-r5: rule lines, explanatory parentheticals, NONE, Item/Line labels, caps ----
_D = "-" * 90
R5 = [
    (
        f"11. Percent of Class Represented by Amount in Row (9): 20.58% {_D} {_D} 12. Type of Reporting Person",
        "20.58",
    ),
    (
        "(13) PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (11) 17.4% (based on 81,733,247 shares of "
        "Common Stock outstanding as of August 14, 2013, as reported in the Issuer's Quarterly Report on "
        "Form 10-Q for the quarter ended June 30, 2013) 14 TYPE OF REPORTING PERSON",
        "17.4",
    ),
    (
        f"11. Percent of class represented by amount in row 9 NONE {_D} 12. Type of Reporting person* HC",
        "0",
    ),
    (
        "11 PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) 3.24% - Based on 44,694,512 shares of common "
        "stock outstanding as of October 31, 2019. 12 TYPE OF REPORTING PERSON IA, PN",
        "3.24",
    ),
    (
        "11. PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) Approximately 4.54% as of the date of this "
        "Statement. (Based on 25,684,323 shares) 12. TYPE OF REPORTING PERSON",
        "4.54",
    ),
    (f"11. PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) 16.48 % {_D} 12", "16.48"),
    (
        "11 PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW 9 Up to 9.9999%** **The percentages used herein "
        "are calculated based upon 12,682,493 outstanding shares 12 TYPE OF REPORTING PERSON",
        None,
    ),
    (
        "Item 11: PERCENT OF CLASS REPRESENTED BY LINE 9 -- 4.470780155 Item 12: TYPE OF REPORTING PERSON -- IA",
        "4.470780155",
    ),
    (
        "11) Percent of class represented by amount in Item 9 0.0% 12) Type of reporting person CO",
        "0.0",
    ),
    (
        "11. Percent of Class Represented by Amount in Row (9) N/A 12. Type of Reporting Person IA",
        None,
    ),
    (
        "11 PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) *** 12 TYPE OF REPORTING PERSON IN-IA-OO",
        None,
    ),
    (
        "13 PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (11) See response to Item 5. 14 TYPE OF REPORTING PERSON",
        None,
    ),
    (
        "11 PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW 9 Not Applicable 12 TYPE OF REPORTING PERSON PN",
        None,
    ),
]


def test_r5_residual_layouts_from_miss_specimens():
    """Verbatim residual layouts after r4. Rule lines and explanatory
    parentheticals no longer hide the value; NONE is a stated zero; "Up to"
    is a blocker cap and stays unwritten; N/A, ***, See Item 5 and blank
    rows state no percent and none is invented."""
    for text, want in R5:
        got, _span = stakes._percent_of(text)
        assert got == want, text[:70]


def test_r6_long_explanation_and_value_inside_label():
    """The r5 test used a shorter parenthetical than the real filings; the
    specimens beat it. r6: no terminator required, value may precede
    'in Row'."""
    long = (
        "(13) PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (11) 17.4% (based on 81,733,247 "
        "shares of Common Stock outstanding as of August 14, 2013, as reported in the Issuer's "
        "Quarterly Report on Form 10-Q for the quarter ended June 30, 2013, filed pursuant to the "
        "Securities Exchange Act of 1934, as amended, with the Securities and Exchange Commission "
        "on August 14, 2013, plus 1,382,488 shares issued upon exercise of warrants held by the "
        "Reporting Persons, plus an additional 2,000,000 shares issuable upon conversion of the "
        "notes described in Item 6 hereof, which are convertible within sixty days of the date "
        "hereof at the option of the holder thereof) 14 TYPE OF REPORTING PERSON"
    )
    assert stakes._percent_of(long)[0] == "17.4"
    assert (
        stakes._percent_of("13. Percent of Class Represented by Amount 25.0% in Row (11) 14. Type")[
            0
        ]
        == "25.0"
    )
    assert (
        stakes._percent_of("13. Percent of Class Represented by Amount of Row (11) 5.87% 14. Type")[
            0
        ]
        == "5.87"
    )
    assert (
        stakes._percent_of(
            "11) Percent of Class Represented By Amount in Row 9. 12) Type of Reporting"
        )[0]
        is None
    )


def test_capture_note_persists_search_cik_list(db, monkeypatch):
    """The owner of a 13D/13G is identified by search metadata, not by the
    document text, for the HTML eras. The note must carry that CIK list so a
    later rule version can re-parse from the library without re-searching."""
    _companies((1, "AAA", "100"))
    monkeypatch.setattr(stakes, "_fetch", lambda url: (b"<html>x</html>", ".htm", "text/html"))
    hit = {
        "url": "https://www.sec.gov/Archives/edgar/data/100/000/d.htm",
        "adsh": "0001-15-000001",
        "doc": "d.htm",
        "cik": "100",
        "ciks": ["100", "999777"],
        "name": "N1",
        "form": "SC 13D/A",
        "file_date": "2015-04-07",
    }
    con = store.connect()
    got = stakes._capture(hit, con)
    assert got is not None
    notes = [r["note"] for r in store.read_table("references", con=con)]
    assert any("ciks=100|999777" in n and "file_date=2015-04-07" in n for n in notes)


def test_backfill_enriches_preexisting_capture_notes(db, monkeypatch):
    """Captures taken before the note carried the search CIK list are repaired
    on the next pass, so the library becomes self-sufficient for future rule
    versions. The repair goes through the store layer (P18), never raw SQL.
    Idempotent: a second pass changes nothing."""
    _companies((1, "AAA", "100"))
    monkeypatch.setattr(stakes, "_fetch", lambda url: (b"<html>x</html>", ".htm", "text/html"))
    hit = {
        "url": "https://www.sec.gov/Archives/edgar/data/100/000/d.htm",
        "adsh": "0001-15-000001",
        "doc": "d.htm",
        "cik": "100",
        "ciks": ["100", "999777"],
        "name": "N1",
        "form": "SC 13D/A",
        "file_date": "2015-04-07",
    }
    con = store.connect()
    stakes._capture(hit, con)
    stakes.flush_note_backfill(con)
    # simulate the pre-enrichment state of the captures already in the library
    rows = store.read_table("references", con=con)
    cols = store.table_columns("references", con)
    for r in rows:
        r["note"] = "captured by stakes-probe;form=SC 13D/A;cik=100"
    store.write_table("references", rows, cols, con=con)
    assert all("ciks=" not in str(r["note"]) for r in store.read_table("references", con=con))

    assert stakes._capture(hit, con) is not None  # cached path queues the repair
    assert stakes.flush_note_backfill(con) == 1
    after = [str(r["note"]) for r in store.read_table("references", con=con)]
    assert any("ciks=100|999777" in n and "file_date=2015-04-07" in n for n in after)

    stakes._capture(hit, con)  # second pass: note already carries ciks=
    assert stakes.flush_note_backfill(con) == 0
    assert [str(r["note"]) for r in store.read_table("references", con=con)] == after


def test_sample_prints_the_exact_captured_document_url(db, monkeypatch, capsys):
    """The judging list must link to the document the row was parsed from.
    An accession directory listing under the subject's CIK is wrong for a
    13D/13G: EDGAR indexes the filing under the FILER's CIK, which is the
    owner, not the subject the row is keyed on."""
    _companies((1, "AAA", "100"))
    monkeypatch.setattr(stakes, "_fetch", lambda url: (b"<html>x</html>", ".htm", "text/html"))
    doc_url = "https://www.sec.gov/Archives/edgar/data/999777/000115000001/d.htm"
    hit = {
        "url": doc_url,
        "adsh": "0001-15-000001",
        "doc": "d.htm",
        "cik": "100",
        "ciks": ["100", "999777"],
        "name": "N1",
        "form": "SC 13D/A",
        "file_date": "2015-04-07",
    }
    con = store.connect()
    sha, _ext, _ct = stakes._capture(hit, con)

    cols = list(schema.EQUITY_STAKE_COLS) + list(schema.EQUITY_STAKE_F1_COLS)
    row = {
        "holder_key": "CIK:999777",
        "issuer_key": "CIK:100",
        "percent": "15.32",
        "as_of": "2015-04-06",
        "doc_id": sha,
        "span": "15.32%",
        "form": "SC 13D/A",
        "filing_date": "2015-04-07",
        "shares": "75000000",
        "owner_name": "Abbott",
        "accession": "0001-15-000001",
        "cusip": "N59465109",
        "item4_text": "",
    }
    store.write_table("equity_stakes", [row], cols, con=con)

    assert stakes.sample(1) == 0
    out = capsys.readouterr().out
    assert doc_url in out  # the document itself, not a directory listing
    assert "WARNING" not in out
    assert "re-run `stakes run` after any rule change" in out


def test_sample_warns_when_a_document_url_cannot_be_resolved(db, capsys):
    _companies((1, "AAA", "100"))
    cols = list(schema.EQUITY_STAKE_COLS) + list(schema.EQUITY_STAKE_F1_COLS)
    row = {
        "holder_key": "CIK:999777",
        "issuer_key": "CIK:100",
        "percent": "9.9",
        "as_of": "2015-04-06",
        "doc_id": "z" * 64,
        "span": "9.9%",
        "form": "SC 13G",
        "filing_date": "2015-04-07",
        "shares": "1",
        "owner_name": "O",
        "accession": "0002-15-000002",
        "cusip": "",
        "item4_text": "",
    }
    store.write_table("equity_stakes", [row], cols)
    assert stakes.sample(1) == 0
    out = capsys.readouterr().out
    assert "WARNING: 1 of 1 rows have no resolvable document URL." in out
    assert "(no url)" in out
