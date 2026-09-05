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
    stakes.reset_capture_index()  # per-pass index must not leak between tests
    stakes._PENDING_NOTES.clear()
    yield store.connect(tmp_path / "t.duckdb")
    store.close()
    stakes.reset_capture_index()
    stakes._PENDING_NOTES.clear()


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
    for row in rows_:
        iid, tick, cik = row[:3]
        name = row[3] if len(row) > 3 else f"N{iid}"
        r = dict.fromkeys(schema.COMPANY_COLS, "")
        r.update({"IID": str(iid), "Name": name, "Ticker": tick, "CIK": cik})
        out.append(r)
    store.write_table("companies", out, schema.COMPANY_COLS)
    stakes.reset_name_index()


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


def test_row_from_owner_resolution_and_exit_semantics(db):
    # orient() reads the registry: this test must never touch the live
    # database (it did on the operator machine on 2026-09-04, where CIK 1800
    # is Abbott and the expectation below became wrong by design)
    _companies((1, "MYL", "1800", "Mylan N.V."))  # the member is the SUBJECT here
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
    _companies((1, "AAA", "100", "Mylan N.V."))  # the member is the document's issuer

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
    stakes.reset_capture_index()  # a new pass rebuilds its index from the table

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


def test_capture_index_is_built_once_per_pass(db, monkeypatch):
    """Regression for the 2026-09-04 re-parse stall: the cached-capture check
    must not re-read the references/captures tables per hit."""
    _companies((1, "AAA", "100"))
    monkeypatch.setattr(stakes, "_fetch", lambda url: (b"<html>x</html>", ".htm", "text/html"))
    con = store.connect()
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
    stakes.reset_capture_index()
    stakes._capture(hit, con)
    reads = {"n": 0}
    real = store.read_table

    def counting(name, *a, **k):
        if name in ("references", "captures"):
            reads["n"] += 1
        return real(name, *a, **k)

    monkeypatch.setattr(store, "read_table", counting)
    for _ in range(50):
        assert stakes._capture(hit, con)[2] == "cached"
    assert reads["n"] == 0  # fifty cached hits, zero table reads


# ---- orientation (2026-09-04): the document decides who is subject and who is owner ----
def test_orient_member_is_subject_when_document_names_it_as_issuer(db):
    _companies((1, "MYL", "100", "Mylan N.V."))
    parsed = {"issuer_name": "Mylan N.V.", "owner_name": "Abbott Laboratories", "percent": "15.32"}
    holder, issuer, how = stakes.orient(_hit(ciks=("100", "999777")), parsed, "100")
    assert (holder, issuer, how) == ("CIK:999777", "CIK:100", "subject")


def test_orient_member_is_filer_when_document_names_someone_else(db):
    """GSK's 13G about a company it holds, found by searching GSK's CIK: the
    row must read GSK -> target, not target -> GSK. This is the inversion
    that put one buyer's name under dozens of target CIKs in the stub list."""
    _companies((1, "GSK", "100", "GlaxoSmithKline plc"))
    parsed = {
        "issuer_name": "Small Biotech Inc",
        "owner_name": "GlaxoSmithKline plc",
        "percent": "9.9",
    }
    holder, issuer, how = stakes.orient(_hit(ciks=("100", "555444")), parsed, "100")
    assert (holder, issuer, how) == ("CIK:100", "CIK:555444", "filer")


def test_orient_structured_filing_uses_the_xml_issuer_cik(db):
    """Structured era: the XML names the issuer and the owner outright. A
    member that filed about itself-as-owner must not become a self-stake."""
    _companies((1, "JNJ", "100", "Johnson & Johnson"))
    parsed = {
        "issuer_cik": "777",
        "owner_cik": "100",
        "owner_name": "Johnson & Johnson",
        "percent": "6.1",
    }
    holder, issuer, how = stakes.orient(_hit(ciks=("100", "777")), parsed, "100")
    assert (holder, issuer, how) == ("CIK:100", "CIK:777", "filer")
    parsed2 = {"issuer_cik": "100", "owner_cik": "888", "owner_name": "Vanguard", "percent": "8.0"}
    assert stakes.orient(_hit(ciks=("100", "888")), parsed2, "100") == (
        "CIK:888",
        "CIK:100",
        "subject",
    )


def test_orient_owner_name_decides_when_issuer_is_unplaceable(db):
    """No issuer name parsed, but the reporting person is a fund, not the
    member: the member is being held. Resolved by the document, not by the
    search."""
    _companies((1, "AAA", "100", "Acme Therapeutics Inc"))
    parsed = {"owner_name": "Some Fund LP", "percent": "5.5"}
    holder, issuer, how = stakes.orient(_hit(ciks=("100", "999777")), parsed, "100")
    assert (holder, issuer, how) == ("CIK:999777", "CIK:100", "subject")
    # and when the reporting person IS the member, the member is the owner
    parsed2 = {"owner_name": "Acme Therapeutics, Inc.", "percent": "5.5"}
    assert stakes.orient(_hit(ciks=("100", "999777")), parsed2, "100") == (
        "CIK:100",
        "CIK:999777",
        "filer",
    )


def test_orient_unmatched_issuer_text_is_not_evidence_of_direction(db):
    """The BlackRock inversion that survived r7: issuer text with spillover
    ('Verastem, Inc. Common Stock') matched nothing, and the old rule read
    that as 'the member must be the filer'. Containment now places it; and
    even if it could not, the owner name ('BlackRock') is not the member."""
    _companies((1, "VSTM", "1347178", "Verastem, Inc."))
    parsed = {
        "issuer_name": "Verastem, Inc. Common Stock, par value $0.0001",
        "owner_name": "BlackRock, Inc.",
        "percent": "7.1",
    }
    assert stakes.orient(_hit(ciks=("1364742", "1347178")), parsed, "1364742") == (
        "CIK:1364742",
        "CIK:1347178",
        "subject",
    )


def test_orient_falls_back_only_when_the_document_is_silent(db):
    _companies((1, "AAA", "100"))
    parsed = {"percent": "5.5"}  # neither issuer nor owner parsed
    holder, issuer, how = stakes.orient(_hit(ciks=("100", "999777")), parsed, "100")
    assert how == "unresolved" and issuer == "CIK:100" and holder == "CIK:999777"


def test_rebuild_rederives_rows_from_the_library_with_correct_orientation(db, monkeypatch):
    """A filer-side filing captured under the old assumption is re-derived
    from the library and comes out the right way round, with no network."""
    _companies((1, "GSK", "100", "GlaxoSmithKline plc"))
    monkeypatch.setattr(stakes, "_fetch", lambda url: (b"<html>x</html>", ".htm", "text/html"))
    # capture a document with a note carrying the search metadata
    hit = {
        "url": "https://www.sec.gov/Archives/edgar/data/555444/000/g.htm",
        "adsh": "0009-19-000009",
        "doc": "g.htm",
        "cik": "100",
        "ciks": ["100", "555444"],
        "name": "GSK",
        "form": "SC 13G/A",
        "file_date": "2019-02-14",
    }
    con = store.connect()
    sha, _e, _c = stakes._capture(hit, con)
    stakes.flush_note_backfill(con)
    # the document names Small Biotech as issuer and GSK as the reporting person
    text = (
        "Small Biotech Inc (Name of Issuer) Common Stock 123456789 (CUSIP Number) "
        "NAMES OF REPORTING PERSONS GlaxoSmithKline plc (2) CHECK THE APPROPRIATE BOX "
        "PERCENT OF CLASS REPRESENTED BY AMOUNT IN ROW (9) 9.9% 12 TYPE OF REPORTING PERSON CO "
        "December 31, 2018 (Date of Event Which Requires Filing of this Statement)"
    )
    monkeypatch.setattr(stakes.library, "store_path", lambda s, e: _write_tmp(db, text))
    # seed an INVERTED row, as the old code would have written it
    cols = list(schema.EQUITY_STAKE_COLS) + list(schema.EQUITY_STAKE_F1_COLS)
    inverted = dict.fromkeys(cols, "")
    inverted.update(
        {
            "holder_key": "CIK:555444",
            "issuer_key": "CIK:100",
            "percent": "9.9",
            "as_of": "2018-12-31",
            "doc_id": sha,
            "span": "9.9%",
            "form": "SC 13G/A",
            "filing_date": "2019-02-14",
            "owner_name": "GlaxoSmithKline plc",
            "accession": "0009-19-000009",
        }
    )
    store.write_table("equity_stakes", [inverted], cols, con=con)

    assert stakes.rebuild(con) == 0
    rows = store.read_table("equity_stakes", con=con)
    assert len(rows) == 1
    assert rows[0]["holder_key"] == "CIK:100" and rows[0]["issuer_key"] == "CIK:555444"
    assert rows[0]["owner_name"] == "GlaxoSmithKline plc"


def _write_tmp(_con, text):
    p = config.DATA / "doc_rebuild.htm"  # the fixture redirects config.DATA to tmp_path
    p.write_text(text, encoding="utf-8")
    return p


def test_orient_does_not_depend_on_which_cik_was_searched(db):
    """The BlackRock row that survived the first fix: SEC listed the fund
    first, the note called it the 'member', and the old code inverted the
    row. Orientation must come from the document and the parties alone."""
    _companies((1, "VSTM", "1347178", "Verastem, Inc."))
    parsed = {"issuer_name": "Verastem, Inc.", "owner_name": "BlackRock, Inc.", "percent": "16.9"}
    hit = _hit(ciks=("1364742", "1347178"))  # fund listed first
    # whichever CIK the caller believes was searched, the answer is the same
    for believed_member in ("1364742", "1347178"):
        holder, issuer, how = stakes.orient(hit, parsed, believed_member)
        assert (holder, issuer) == ("CIK:1364742", "CIK:1347178"), believed_member
        assert how == "subject"


def test_r7_person_s_and_leading_slash_label_variants():
    """From the F1-G sample: 'PERSON(S)' glued '(s)' onto names; a leading
    slash before 'I.R.S.' stored the whole label clause as the name."""
    s = " Percent of Class: 9.9%"
    assert (
        stakes.parse_cover(
            "NAME OF REPORTING PERSON(S) Karpus Investment Management (2) CHECK" + s
        )["owner_name"]
        == "Karpus Investment Management"
    )
    assert (
        stakes.parse_cover(
            "NAMES OF REPORTING PERSONS /I.R.S. IDENTIFICATION NOS. OF ABOVE PERSONS (ENTITIES ONLY) CCP IV GP LTD 2 CHECK"
            + s
        )["owner_name"]
        == "CCP IV GP LTD"
    )


def test_parse_header_on_three_real_sec_headers():
    """verify-direction probe captures (2026-09-05): FILED BY / SUBJECT
    COMPANY blocks in either order, group members present, agent or trust
    filers distinct from the parent."""
    fx = FIXTURES
    h0 = stakes.parse_header((fx / "hdr_probe_0.txt").read_text(encoding="utf-8"))
    assert h0["subject"] == [("882365", "I STAT CORPORATION /DE/")]
    assert h0["filed_by"] == [("1800", "ABBOTT LABORATORIES")]
    h1 = stakes.parse_header((fx / "hdr_probe_1.txt").read_text(encoding="utf-8"))
    assert h1["subject"] == [("1800", "ABBOTT LABORATORIES")]
    assert h1["filed_by"] == [("918392", "ABBOTT LABORATORIES STOCK RETIREMENT TRUST")]
    assert stakes.parse_header("no header here") == {"subject": [], "filed_by": []}


# ---- header captures must not attach to filing references (2026-09-05) ----
_SUBMISSION = (
    "<SEC-DOCUMENT>0001-15-000001.txt : 20150407\n<SEC-HEADER>0001-15-000001.hdr.sgml : 20150407\n"
    "ACCESSION NUMBER:\t\t0001-15-000001\nSUBJECT COMPANY:\t\n\tCOMPANY DATA:\t\n"
    "\t\tCOMPANY CONFORMED NAME:\t\t\tMYLAN N.V.\n\t\tCENTRAL INDEX KEY:\t\t\t0000000100\n"
    "FILED BY:\t\t\n\tCOMPANY DATA:\t\n\t\tCOMPANY CONFORMED NAME:\t\t\tABBOTT LABORATORIES\n"
    "\t\tCENTRAL INDEX KEY:\t\t\t0000999777\n</SEC-HEADER>\n<DOCUMENT>...</DOCUMENT>"
)


def _capture_doc_and_header(monkeypatch, con):
    """Capture a filing document, then its submission header, the way the
    collector and verify-direction do."""
    doc_hit = {
        "url": "https://www.sec.gov/Archives/edgar/data/100/000115000001/d.htm",
        "adsh": "0001-15-000001",
        "doc": "d.htm",
        "cik": "100",
        "ciks": ["100", "999777"],
        "name": "Mylan",
        "form": "SC 13D/A",
        "file_date": "2015-04-07",
    }
    hdr_hit = {
        "url": stakes._submission_url("100", "0001-15-000001"),
        "adsh": "0001-15-000001",
        "doc": "0001-15-000001.txt",
        "cik": "100",
        "ciks": ["100"],
        "name": "",
        "form": "SC 13D/A",
        "file_date": "2015-04-07",
    }
    payloads = {
        doc_hit["url"]: (b"<html>doc</html>", ".htm", "text/html"),
        hdr_hit["url"]: (_SUBMISSION.encode(), ".txt", "text/plain"),
    }
    monkeypatch.setattr(stakes, "_fetch", lambda url: payloads[url])
    stakes.reset_capture_index()
    d = stakes._capture(doc_hit, con)
    h = stakes._capture(hdr_hit, con, header=True)
    return doc_hit, hdr_hit, d, h


def test_header_capture_gets_its_own_reference_and_is_cached(db, monkeypatch):
    _companies((1, "MYL", "100", "Mylan N.V."))
    con = store.connect()
    doc_hit, hdr_hit, d, h = _capture_doc_and_header(monkeypatch, con)
    refs = store.read_table("references", con=con)
    assert len(refs) == 2  # the ladder did NOT attach the header to the filing
    kinds = {str(c["kind"]) for c in store.read_table("captures", con=con)}
    assert kinds == {"fetched_html", stakes.HEADER_KIND}
    # second pass: the header is a cache hit, no fetch
    stakes.reset_capture_index()
    monkeypatch.setattr(
        stakes, "_fetch", lambda url: (_ for _ in ()).throw(AssertionError("fetched"))
    )
    assert stakes._capture(hdr_hit, con, header=True)[2] == "cached"
    assert stakes._capture(doc_hit, con)[2] == "cached"


def test_repair_headers_moves_misattached_captures(db, monkeypatch):
    """Simulate the pre-fix state: the header capture sits on the filing's
    reference with kind fetched_html. After repair the filing reference has
    one document capture and the header has its own reference."""
    _companies((1, "MYL", "100", "Mylan N.V."))
    con = store.connect()
    doc_hit, hdr_hit, d, h = _capture_doc_and_header(monkeypatch, con)
    # collapse to the broken state
    refs = store.read_table("references", con=con)
    doc_ref = next(r for r in refs if str(r["source_system"]) == "stakes-probe")
    caps = store.read_table("captures", con=con)
    cols = store.table_columns("captures", con)
    for c in caps:
        c["ref_id"] = doc_ref["ref_id"]
        c["kind"] = "fetched_html"
    store.write_table("captures", caps, cols, con=con)
    rcols = store.table_columns("references", con)
    store.write_table("references", [doc_ref], rcols, con=con)
    assert len({str(c["ref_id"]) for c in store.read_table("captures", con=con)}) == 1

    assert stakes.repair_headers(con) == 0
    caps = store.read_table("captures", con=con)
    by_ref = {}
    for c in caps:
        by_ref.setdefault(str(c["ref_id"]), []).append(c)
    assert len(by_ref) == 2 and all(len(v) == 1 for v in by_ref.values())
    hdr = next(c for c in caps if str(c["kind"]) == stakes.HEADER_KIND)
    assert hdr["ref_id"] != doc_ref["ref_id"]
    # the rebuild's document map never picks the header
    stakes.reset_capture_index()
    idx = stakes._build_capture_index(con)
    assert idx[doc_hit["url"]][1] == d[0]
    assert stakes.repair_headers(con) == 0  # idempotent: nothing left to move
