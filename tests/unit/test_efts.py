# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_efts.py
"""Gate 1.5b: EFTS miner. Fixtures are verbatim excerpts of real captures made
2026-08-31/09-01 (rule 4.20): the EFTS response's first hit, the Harmony
Biosciences 8-K EX-99.1 prose, and two VEVENTs of the benchmark ICS."""

from __future__ import annotations

from datetime import date

import pytest

from biointel import config, efts, schema, store

TODAY = date(2026, 9, 1)

# real EFTS hit (PDUFA in 8-K, 2026-06-01..2026-08-31), verbatim structure
EFTS_PAYLOAD = {
    "hits": {
        "total": {"value": 1},
        "hits": [
            {
                "_id": "0001104659-26-090086:hrmy-20260804xex99d1.htm",
                "_source": {
                    "file_num": [],
                    "display_names": [
                        "Harmony Biosciences Holdings, Inc.  (HRMY)  (CIK 0001802665)"
                    ],
                    "xsl": None,
                    "sequence": "2",
                    "sics": ["2834"],
                    "form": "8-K",
                    "adsh": "0001104659-26-090086",
                    "film_num": ["261235581"],
                    "biz_locations": ["Plymouth Meeting, PA"],
                    "file_type": "EX-99.1",
                    "file_description": "EX-99.1",
                    "inc_states": ["DE"],
                    "items": ["2.02", "7.01", "9.01"],
                    "ciks": ["0001802665"],
                    "file_date": "2026-08-04",
                    "root_forms": ["8-K"],
                },
            }
        ],
    }
}

# real prose excerpts (tag-stripped) from that exhibit, entities as served
HRMY = (
    "Pitolisant GR (Gastro-resistant) Tablets: On track to launch in 1H 2027 &#9679; NDA accepted by FDA in July; "
    "target PDUFA date of April 1, 2027 o Designed with enteric coating meant to reduce the potential for GI side effects "
    "&#8203; Pitolisant HD (high dose) &#9679; Phase 3 registrational clinical trials ongoing in narcolepsy (ONSTRIDE 1) "
    "and idiopathic hypersomnia (IH) (ONSTRIDE 2) o Topline data expected in 2027; anticipated PDUFA date in 2028 &#8203; "
    "WAKIX (pitolisant): Phase 3 trial in PWS (TEMPO) &#9679; Topline data expected in mid-2027 and anticipated PDUFA date in 2028 "
    "&#8203; EPX-100 (clemizole hydrochloride) &#9679; Topline data expected in 1H 2027 and anticipated PDUFA dates in 2028 "
    "&#8203; Next steps in BP-205 development o Multiple ascending dose (MAD) data in healthy volunteers expected in Q4 o "
    "initiate Phase 1b study in Q3; data expected in early 2027 &#8203; Phase 1 MAD Data Expected in Q4 2026"
)

ICS = """BEGIN:VCALENDAR
PRODID:-//Google Inc//Google Calendar 70.9054//EN
VERSION:2.0
X-WR-CALNAME:PDUFA
BEGIN:VEVENT
DTSTART;VALUE=DATE:20081203
DTSTAMP:20260901T041933Z
UID:spmn9v35shp3v7pc8d7ot5r53k@google.com
DESCRIPTION:20081106 FDA has assigned a Prescription Drug User Fee Act (PDU
 FA) goal date of December 3\\, 2008 to this application.
STATUS:CONFIRMED
SUMMARY:GENTA INC DE PDUFA
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20270401
DTEND;VALUE=DATE:20270402
DTSTAMP:20260901T041933Z
UID:test@google.com
SUMMARY:HARMONY BIOSCIENCES HOLDINGS INC PDUFA
END:VEVENT
END:VCALENDAR
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
    companies = [{c: "" for c in schema.COMPANY_COLS}]
    companies[0].update(
        {
            "IID": "9",
            "Name": "Harmony Biosciences Holdings, Inc.",
            "Ticker": "HRMY",
            "CIK": "1802665",
        }
    )
    store.write_table("companies", companies, schema.COMPANY_COLS, con=con)
    yield con
    store.close()


# ---------------------------------------------------------------- adapter
def test_hits_of_flattens_the_real_schema():
    hs = efts.hits_of(EFTS_PAYLOAD)
    assert len(hs) == 1
    h = hs[0]
    assert h["adsh"] == "0001104659-26-090086" and h["doc"] == "hrmy-20260804xex99d1.htm"
    assert h["cik"] == "1802665" and h["form"] == "8-K" and h["file_type"] == "EX-99.1"
    assert h["file_date"] == "2026-08-04"
    assert (
        h["url"]
        == "https://www.sec.gov/Archives/edgar/data/1802665/000110465926090086/hrmy-20260804xex99d1.htm"
    )


# ---------------------------------------------------------------- extractor
def test_extract_from_real_prose():
    text = efts.normalize_text(HRMY)
    cands, skipped = efts.extract(text)
    pd = [c for c in cands if c["kind"] == "pdufa"]
    rd = [c for c in cands if c["kind"] == "readout"]
    exact = next(c for c in pd if c["precision"] == "day")
    assert exact["start"] == "2027-04-01" and "April 1, 2027" in exact["phrase"]
    assert any(c["precision"] == "year" and c["start"] == "2028-01-01" for c in pd)
    assert any(
        c["precision"] == "year" and c["start"] == "2027-01-01" for c in rd
    )  # "expected in 2027"
    assert any(
        c["precision"] == "half" and c["start"] == "2027-01-01" and c["end"] == "2027-06-30"
        for c in rd
    )  # 1H 2027
    assert any(c["precision"] == "quarter" and c["start"] == "2026-10-01" for c in rd)  # Q4 2026
    # early/mid statements: year precision with the modifier retained in the ledger;
    # at the event level the same (company, kind, range) is one event, so the
    # restatements are ledgered as duplicate_in_document, not lost
    recs = efts.examine(text)
    mods = [r for r in recs if r["date_mod"] in ("mid", "early")]
    assert mods and all(r["precision"] == "year" for r in mods)
    assert all(r["decision"] == "accepted" or r["reason"] == "duplicate_in_document" for r in mods)
    # "Month of YYYY" (Tenax 10-Q, sample row 8) is month precision
    c3, _ = efts.extract(
        efts.normalize_text("we expect to report initial topline data in August of 2026. LEVEL is")
    )
    assert (
        c3
        and c3[0]["precision"] == "month"
        and c3[0]["start"] == "2026-08-01"
        and c3[0]["end"] == "2026-08-31"
    )
    # a quarter with no year is counted and skipped, never inferred (real phrasing style)
    c2, s2 = efts.extract(
        efts.normalize_text("Topline data expected in Q4; NDA submission to follow.")
    )
    assert c2 == [] and s2 == 1


def test_rows_from_candidates_are_tier_b_forward_rows_with_provenance(env):
    text = efts.normalize_text(HRMY)
    cands, _ = efts.extract(text)
    hit = efts.hits_of(EFTS_PAYLOAD)[0]
    rows, past = efts._rows_from(cands, hit, "9", "a" * 64, TODAY)
    assert past == 0 and rows
    r = next(
        x
        for x in rows
        if x["outcome_subtype"] == "pdufa_target_date" and x["date_precision"] == "day"
    )
    assert r["event_class"] == "regulatory_decision" and r["confidence_tier"] == "B"
    assert r["scheduled_date"] == "2027-04-01" and r["event_date"] == ""
    assert r["source_url"] == hit["url"]
    assert (
        "adsh=0001104659-26-090086" in r["provenance"] and "doc_id=" + "a" * 64 in r["provenance"]
    )
    assert "April 1, 2027" in r["date_raw"]
    g = next(x for x in rows if x["outcome_subtype"] == "guided_readout")
    assert g["event_class"] == "clinical_readout"


def test_upsert_of_mined_rows_is_idempotent(env):
    text = efts.normalize_text(HRMY)
    cands, _ = efts.extract(text)
    hit = efts.hits_of(EFTS_PAYLOAD)[0]
    rows, _ = efts._rows_from(cands, hit, "9", "a" * 64, TODAY)
    c1 = efts._upsert(rows, efts._identity, env)
    rows2, _ = efts._rows_from(cands, hit, "9", "a" * 64, TODAY)
    c2 = efts._upsert(rows2, efts._identity, env)
    assert c1["inserted"] == len(rows) and c2["inserted"] == 0 and c2["refreshed"] == len(rows)


# ---------------------------------------------------------------- benchmark
def test_parse_ics_unfolds_lines_and_reads_dates():
    ev = efts.parse_ics(ICS)
    assert len(ev) == 2
    assert ev[0]["date"] == "2008-12-03" and ev[0]["summary"] == "GENTA INC DE PDUFA"
    assert "goal date of December 3, 2008" in ev[0]["description"]
    assert ev[1]["date"] == "2027-04-01"


def test_recall_matches_mined_exact_pdufa_by_date_and_name(env, tmp_path, capsys):
    text = efts.normalize_text(HRMY)
    cands, _ = efts.extract(text)
    hit = efts.hits_of(EFTS_PAYLOAD)[0]
    rows, _ = efts._rows_from(cands, hit, "9", "a" * 64, TODAY)
    efts._upsert(rows, efts._identity, env)
    p = tmp_path / "bench.ics"
    p.write_text(ICS, encoding="utf-8")
    assert efts.recall(str(p), today=TODAY) == 0
    out = capsys.readouterr().out
    assert "1/1 upcoming benchmark PDUFA events matched = 1.000" in out
    runs = store.read_table("runs", con=env)
    assert any(x["command"] == "mine-pdufa recall" for x in runs)


def test_same_date_restated_in_another_filing_is_one_event(env):
    hit_a = efts.hits_of(EFTS_PAYLOAD)[0]
    hit_b = dict(
        hit_a,
        adsh="0001104659-26-099999",
        doc="hrmy-10q.htm",
        url="https://www.sec.gov/Archives/edgar/data/1802665/000110465926099999/hrmy-10q.htm",
    )
    cands, _ = efts.extract(efts.normalize_text("target PDUFA date of April 1, 2027"))
    rows_a, _ = efts._rows_from(cands, hit_a, "9", "a" * 64, TODAY)
    rows_b, _ = efts._rows_from(cands, hit_b, "9", "b" * 64, TODAY)
    assert rows_a[0]["event_id"] == rows_b[0]["event_id"]
    c1 = efts._upsert(rows_a, efts._identity, env)
    c2 = efts._upsert(rows_b, efts._identity, env)
    assert c1["inserted"] == 1 and c2["inserted"] == 0 and c2["refreshed"] == 1


def test_abbreviated_month_and_past_tense_anchor_from_merck_prose():
    # verbatim Merck 8-K EX-99.1 phrasings from sample rows 3 and 5 (2026-09-01)
    text = efts.normalize_text(
        "FDA set Prescription Drug User Fee Act (PDUFA) date of Oct. 10, 2026. o FDA accepted for priority review "
        "supplemental applications for WELIREG. FDA set Prescription Drug User Fee Act (PDUFA) dates in the second half "
        "of 2026 for these applications. o Announced positive topline results from Phase 3 KEYNOTE-B15 trial in patients"
    )
    cands, _ = efts.extract(text)
    exact = [c for c in cands if c["kind"] == "pdufa" and c["precision"] == "day"]
    assert exact and exact[0]["start"] == "2026-10-10"
    assert any(
        c["kind"] == "pdufa" and c["precision"] == "half" and c["start"] == "2026-07-01"
        for c in cands
    )
    assert not any(
        c["kind"] == "readout" for c in cands
    )  # "Announced ... topline results" is history


def test_recall_matches_on_benchmark_ticker_prefix(env, tmp_path, capsys):
    hit = efts.hits_of(EFTS_PAYLOAD)[0]
    cands, _ = efts.extract(efts.normalize_text("target PDUFA date of April 1, 2027"))
    rows, _ = efts._rows_from(cands, hit, "9", "a" * 64, TODAY)
    efts._upsert(rows, efts._identity, env)
    ics = ICS.replace(
        "SUMMARY:HARMONY BIOSCIENCES HOLDINGS INC PDUFA",
        "SUMMARY:HRMY Harmony Biosciences Holdings\\, Inc. PDUFA",
    )
    p = tmp_path / "b.ics"
    p.write_text(ics, encoding="utf-8")
    assert efts.recall(str(p), today=TODAY) == 0
    assert "1/1 upcoming benchmark PDUFA events matched" in capsys.readouterr().out


@pytest.mark.parametrize(
    "text,expect",
    [
        # sample 2026-09-01 row 3: negated guidance -> nothing
        (
            "We no longer anticipate topline data from the HERO trial in the third quarter of 2026, and the timing",
            [],
        ),
        # row 4: bullet list, each item keeps its own date; the "First Quarter 2026 Financial Highlights" label is not a date statement
        (
            "l initiation • 1H 2027 — ALTO-300 Phase 2b MDD trial topline data • 2H 2027 — ALTO-207 Phase 2b TRD trial "
            "topline data First Quarter 2026 Financial Highlights Cash Position: As of March 31, 2026",
            [("readout", "half", "2027-01-01"), ("readout", "half", "2027-07-01")],
        ),
        # row 7: "delivered ... topline data" is history; bare year far from the PDUFA anchor is not a date
        (
            "h 31, 2026. \u201cOur team continues its strong execution as we are launch ready ahead of veligrotug\u2019s PDUFA "
            "target date. We delivered positive topline data from both pivotal REVEAL phase 3 clinical trials, and earlier",
            [],
        ),
        # row 9: "PDUFA Date 3Q 2026" -> quarter
        (
            "Brepocitinib Dermatomyositis Priovant Small Molecule PDUFA Date 3Q 2026 Brepocitinib Non-Infectious Uveitis",
            [("pdufa", "quarter", "2026-07-01")],
        ),
        # row 10: glossary entry next to a note maturity -> nothing
        (
            "Offering $45,000 aggregate principal amount of 13.5% Senior Secured Notes due November 1, 2028 PD Pharmacodynamics "
            "PDUFA Prescription Drug User Fee Act Pharmanovia Atnahs Pharma UK Limited",
            [],
        ),
    ],
)
def test_extractor_v004_rules_from_full_run_sample(text, expect):
    cands, _ = efts.extract(efts.normalize_text(text))
    got = [(c["kind"], c["precision"], c["start"]) for c in cands]
    assert got == expect


def test_examine_ledgers_every_window_with_assertion_and_reason():
    text = efts.normalize_text(
        "We no longer anticipate topline data from the HERO trial in the third quarter of 2026. "
        "We delivered positive topline data from the REVEAL trials, which met the primary endpoint. "
        "Topline data expected in Q4. FDA set a PDUFA date of October 4, 2026. "
        "PD Pharmacodynamics PDUFA Prescription Drug User Fee Act"
    )
    recs = efts.examine(text, file_date="2026-08-04")
    by_reason = {}
    for r in recs:
        by_reason.setdefault(r["decision"] + ":" + r["reason"], []).append(r)
    assert (
        "rejected:negated" in by_reason
        and by_reason["rejected:negated"][0]["start"] == "2026-07-01"
    )
    hist = by_reason["rejected:historical"][0]
    assert hist["assertion"] == "historical" and "positive" in hist["outcome_words"]
    anchored = by_reason["rejected:no_year_anchored"][0]
    assert (
        anchored["anchored"] == 1 and anchored["start"] == "2026-10-01"
    )  # Q4 anchored to filing year, flagged
    acc = by_reason["accepted:"][0]
    assert acc["kind"] == "pdufa" and acc["start"] == "2026-10-04"
    assert text[acc["char_start"] : acc["char_end"]].strip() == acc["window"]  # exact grounding
    assert text[acc["phrase_start"] : acc["phrase_start"] + len(acc["phrase"])] == acc["phrase"]
    assert "rejected:no_date_context" in by_reason  # glossary entry kept, not lost


def test_run_writes_ledger_rows(env, monkeypatch):
    hit = efts.hits_of(EFTS_PAYLOAD)[0]
    text = efts.normalize_text(HRMY)
    monkeypatch.setattr(efts, "search", lambda *a, **k: EFTS_PAYLOAD)
    monkeypatch.setattr(efts, "capture_document", lambda h, con: ("a" * 64, text))
    r = efts.run(limit=1, today=TODAY)
    assert r["ledger_rows"] == r["examined"] > r["candidates"] > 0
    led = store.read_table("mined_candidates", con=store.connect())
    assert len(led) == r["ledger_rows"]
    assert {x["rule_version"] for x in led} == {efts.RULE_VERSION}
    assert any(x["decision"] == "accepted" for x in led) and any(
        x["decision"] == "rejected" for x in led
    )
    assert all(len(x["doc_id"]) == 64 and x["adsh"] == hit["adsh"] for x in led)


def test_run_survives_fetch_failures_and_flushes_periodically(env, monkeypatch):
    import requests as _rq

    text = efts.normalize_text(HRMY)
    companies = [{c: "" for c in schema.COMPANY_COLS} for _ in range(60)]
    for i, c in enumerate(companies):
        c.update({"IID": str(100 + i), "Name": f"Co {i}", "Ticker": f"T{i}", "CIK": str(1000 + i)})
    store.write_table("companies", companies, schema.COMPANY_COLS, con=env)
    calls = {"n": 0}

    def fake_capture(h, con):
        calls["n"] += 1
        if calls["n"] % 7 == 0:
            return None  # a failed fetch (5xx/timeout after backoff) must not abort the run
        return ("b" * 64, text)

    def fake_search(*a, **k):
        if k.get("cik") == "1005":
            raise _rq.ReadTimeout("simulated")
        return EFTS_PAYLOAD

    monkeypatch.setattr(efts, "search", fake_search)
    monkeypatch.setattr(efts, "capture_document", fake_capture)
    r = efts.run(today=TODAY)
    assert r["status"] == "ok" and r["errors"] == 1 and r["fetch_failed"] >= 8
    assert r["docs"] == 59 - r["fetch_failed"]
    led = store.read_table("mined_candidates", con=store.connect())
    assert len(led) == r["ledger_rows"] > 0
    fwd = [
        x
        for x in store.read_table("events_table", con=store.connect())
        if (x.get("provenance") or "").startswith("source=efts")
    ]
    assert len(fwd) == r["inserted"] > 0


def test_r7_rules_from_second_full_run_sample():
    # sample row 9 (HUTCHMED): "H2 2026" with the H first is half precision
    c, _ = efts.extract(
        efts.normalize_text(
            "Expecting topline results in H2 2026 for SAFFRON and SANOVO, following full enrollment"
        )
    )
    assert c and c[0]["precision"] == "half" and c[0]["start"] == "2026-07-01"
    # sample row 8 (Maze): "Based on the topline results ..." is history, the date belongs to a trial start
    recs = efts.examine(
        efts.normalize_text(
            "Based on the topline results from HORIZON, Maze plans to initiate a pivotal trial in the first half of 2027, subject to regulatory feedback."
        )
    )
    assert recs and all(
        r["decision"] == "rejected" and r["assertion"] == "historical" for r in recs
    )


def _seed_ledger_via_run(env, monkeypatch, text):
    monkeypatch.setattr(efts, "search", lambda *a, **k: EFTS_PAYLOAD)
    real_capture = efts.capture_document

    def fake_capture(h, con):
        # store a real capture so cached mode and sampling can read the text back
        from biointel import library as _lib

        data = text.encode("utf-8")
        ref_id, _ = _lib.upsert_reference(
            {
                "ref_type": "sec_filing",
                "sec_accession": h["adsh"],
                "url": h["url"],
                "title": "fixture 8-K",
                "publisher": "SEC EDGAR",
                "published_at": h["file_date"],
                "source_system": "efts",
                "source_key": f"{h['adsh']}:{h['doc']}",
                "note": f"captured by mine-pdufa;form={h['form']};cik={h['cik']}",
            },
            con,
        )
        sha, dst, _new = _lib.put_bytes(data, ".htm")
        _lib.add_capture(ref_id, sha, dst, "fetched_html", "test", con)
        _lib.add_link(ref_id, "CIK", h["cik"], "subject", con)
        return sha, efts.normalize_text(text)

    monkeypatch.setattr(efts, "capture_document", fake_capture)
    r = efts.run(limit=1, today=TODAY)
    monkeypatch.setattr(efts, "capture_document", real_capture)
    return r


def test_cached_rerun_sample_judge_precision_explain(env, monkeypatch, capsys, tmp_path):
    from biointel import schema as _schema

    for t_, cols in (
        ("references", _schema.REFERENCE_COLS),
        ("captures", _schema.CAPTURE_COLS),
        ("reference_links", _schema.REFERENCE_LINK_COLS),
    ):
        store.write_table(t_, [], cols, con=env)
    r1 = _seed_ledger_via_run(env, monkeypatch, HRMY)
    assert r1["candidates"] > 0
    # cached re-run reads the stored capture: same windows, no network
    r2 = efts.run_cached(today=TODAY)
    assert r2["docs"] == 1 and r2["examined"] == r1["examined"] and r2["inserted"] == 0
    # blind sample from the ledger, then verdicts, then precision with an interval
    assert efts.sample_ledger(3, seed=1, today=TODAY) == 0
    out = capsys.readouterr().out
    ids = [line.split()[1] for line in out.splitlines() if line.startswith("[")]
    assert len(ids) == 3
    assert (
        efts.judge(ids[0], "correct") == 0
        and efts.judge(ids[1], "wrong", "not a date statement") == 0
    )
    assert efts.judge(ids[2], "unsure") == 0
    reviews = store.read_table("candidate_reviews", con=store.connect())
    assert len(reviews) == 3 and {x["verdict"] for x in reviews} == {"correct", "wrong", "unsure"}
    assert efts.precision_from_reviews() == 0
    out = capsys.readouterr().out
    assert "1/2 = 0.500" in out and "95% CI" in out  # unsure excluded from the denominator
    # a second sample excludes reviewed candidates
    efts.sample_ledger(50, seed=1, today=TODAY)
    out = capsys.readouterr().out
    assert not any(i in out for i in ids)
    # explain: a date present in the cached document and carried by the ledger
    assert efts.explain("HRMY", "2027-04-01", today=TODAY) == 0
    out = capsys.readouterr().out
    assert "documents containing the date 1" in out and "LEDGER" in out
    # explain: a date absent from the documents
    efts.explain("HRMY", "2028-06-30", today=TODAY)
    assert "DATE_NOT_IN_DOCS" in capsys.readouterr().out
    # explain: unknown ticker
    efts.explain("ZZZZ", "2027-04-01", today=TODAY)
    assert "NOT_A_MEMBER" in capsys.readouterr().out


@pytest.mark.parametrize(
    "text,expect",
    [
        (
            "Q32 Bio believes its cash is sufficient to fund operations into 2027, through topline results of the SIGNAL-AA "
            "Part B trial evaluating bempikibart in patients with AA expected in mid-2026.",
            [("readout", "year", "2026-01-01", "mid")],
        ),
        (
            "We plan to initiate this trial in early 2027 and expect to report topline data in the first half of 2029.",
            [("readout", "half", "2029-01-01", "")],
        ),
        (
            "We also expect to report complete enrollment in the adolescent cohort of CEDAR-HCM in the fourth quarter of 2026.",
            [],
        ),
        (
            "The FDA has set a Prescription Drug User Fee Act (PDUFA) action date in the last quarter of 2026.",
            [("pdufa", "quarter", "2026-10-01", "")],
        ),
        (
            "Congress is required to re-authorize the agency's user fee programs every five years, and current legislative "
            "provisions supporting the PDUFA program are set to expire on September 30, 2027.",
            [],
        ),
        (
            "at the earlier of (i) ten trading days following the date of the Company's public announcement that the FDA has "
            "assigned a Prescription Drug User Fee Act goal date for review of iopofosine I 131, and (ii) July 21, 2029.",
            [],
        ),
    ],
)
def test_r8_rules_from_sixty_row_sample_and_extras(text, expect):
    cands, _ = efts.extract(efts.normalize_text(text))
    got = [(c["kind"], c["precision"], c["start"], c["date_mod"]) for c in cands]
    assert got == expect


@pytest.mark.parametrize(
    "text,expect",
    [
        # r8 sample row 8: past tense after the anchor
        (
            "an investigator-sponsored study is evaluating LYMPHIR prior to CAR-T therapy, with positive topline data "
            "presented at the ASTCT 2026 Annual Meeting and additional analyses underway.",
            [],
        ),
        # rows 10 and 38: cash runway "into the ..."
        (
            "VIO estimates that current cash balances will support operations into the first quarter of 2027, beyond the "
            "target PDUFA date for INO-3107.",
            [],
        ),
        (
            "Private placement proceeds are expected to fund operations into the second half of 2029 and through key clinical "
            "milestones, including top-line data from Phase 2 proof-of-concept studies",
            [],
        ),
        # row 19: slide "H2 2026 TOP-LINE DATA 2027 ANTICIPATED NDA SUBMISSION" — the more specific phrase wins the tie
        (
            "Long half-life supports once-daily dosing H2 2026 TOP-LINE DATA 2027 ANTICIPATED NDA SUBMISSION 2027 POTENTIAL APPROVAL",
            [("readout", "half", "2026-07-01")],
        ),
        # row 21: a statement about when the PDUFA date will be known
        (
            "Clarity on the Prescription Drug User Fee Act (PDUFA) date is currently expected by the end of November 2026, "
            "concurrent with the FDA's acceptance of the BLA.",
            [],
        ),
        # rows 25 and 41: "..., with topline data anticipated in X" — the after-phrase wins
        (
            "Enrollment in the second pivotal cohort is expected in the fourth quarter of 2026, with topline data anticipated "
            "in the second quarter of 2027.",
            [("readout", "quarter", "2027-04-01")],
        ),
        (
            "Primary completion is expected in the fourth quarter of 2026, with topline data expected in the first quarter of 2027.",
            [("readout", "quarter", "2027-01-01")],
        ),
        # row 2: timeline header with four date phrases is not attributable
        (
            "no AEs of special interest 1H 2026 2H 2026 1H 2027 2H 2027 FA Phase 2b N=100 Topline Data CSU Phase 3 Start",
            [],
        ),
    ],
)
def test_r9_rules_from_second_sixty_row_sample(text, expect):
    cands, _ = efts.extract(efts.normalize_text(text))
    assert [(c["kind"], c["precision"], c["start"]) for c in cands] == expect


def test_cached_rerun_retires_rows_the_current_rules_no_longer_produce(env, monkeypatch):
    from biointel import schema as _schema

    for t_, cols in (
        ("references", _schema.REFERENCE_COLS),
        ("captures", _schema.CAPTURE_COLS),
        ("reference_links", _schema.REFERENCE_LINK_COLS),
    ):
        store.write_table(t_, [], cols, con=env)
    # a document whose only statement is boilerplate: pretend an older rule accepted it
    boiler = (
        "Congress is required to re-authorize the agency's user fee programs every five years, and current legislative "
        "provisions supporting the PDUFA program are set to expire on September 30, 2027."
    )
    _seed_ledger_via_run(env, monkeypatch, boiler)
    hit = efts.hits_of(EFTS_PAYLOAD)[0]
    stale = efts._blank_row()
    stale.update(
        {
            "event_id": "Mstale0000000001",
            "entity_key": "9",
            "event_class": "regulatory_decision",
            "scheduled_date": "2027-09-30",
            "scheduled_date_end": "2027-09-30",
            "date_precision": "day",
            "outcome_subtype": "pdufa_target_date",
            "confidence_tier": "B",
            "provenance": f"source=efts;adsh={hit['adsh']};doc={hit['doc']};form=8-K;file_date=2026-08-04;phrase=x;doc_id=a",
        }
    )
    from biointel.forward import ALL_COLS

    rows = store.read_table("events_table", con=env) + [stale]
    store.write_table("events_table", rows, ALL_COLS, con=env)
    r = efts.run_cached(today=TODAY)
    assert r["retired"] == 1
    got = next(
        x
        for x in store.read_table("events_table", con=store.connect())
        if x["event_id"] == "Mstale0000000001"
    )
    assert got["status"] == "superseded" and "retired_by=" in got["provenance"]
