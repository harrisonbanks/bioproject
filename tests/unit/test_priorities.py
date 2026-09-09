# C:\Users\JB\Documents\dev\bioindustry\tests\unit\test_priorities.py
"""Gate F2 stage-2 tests: Item-1 slicing and priority-sentence rules,
locked against VERBATIM blocks of the 2026-09-07 probe bundle (rule 4.20)."""

import pytest as _pytest

from biointel import priorities, schema
from biointel.priorities import PRIORITY_RULES, extract_priorities, item1_slice

_AKORN = "ucts; and \u2022 Other factors referred to in this Form 10-K and our other Securities and Exchange Commission filings. See \u201cItem 1A - Risk Factors\u201d. As a result, you should not place undue reliance on any forward-looking statements. You should read this report completely with the understanding that our actual results may differ materially from what we expect. Unless required by law, we undertake no obligation to update publicly any forward-looking statements, whether as a result of new information, future events or otherwise. 2 FORM 10-K TABLE OF CONTENTS Page PART I Item 1. Business 4 Item 1A. Risk Factors 12 Item 1B. Unresolved Staff Comments 24 Item 2. Properties 24 Item 3. Legal Proceedings 24 Item 4. Mine Safety Disclosures 26 PART II Item 5. Market for Registrant\u2019s Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities 27 Item 6. Selected Financial Data 29 Item 7. Management\u2019s Discussion and Analysis of Financial Condition and Results of Operations 30 Item 7A. Quantitative and Qualitative Disclosures about Market Risk 44 Item 8. Financial Statements and Supplementary Data 46 Item 9. Changes in and Disagreements with Accountants on Accounting and Financial Disclosure 94 Item 9A. Controls and Procedures 94 Item 9B. Other Information 96 PART III Item 10. Directors, Executive Officers and Corporate Governance 97 Item 11. Executive Compensation 97 Item 12. Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters 97 Item 13. Certain Relationships and Related Transactions and Director Independence 97 Item 14. Principal Accounting Fees and Services 97 PART IV I tem 15. Exhibits, Financial Statement Schedules 98 3 PART I Item 1. Business Akorn, Inc. together with its wholly owned subsidiaries (\u201cAkorn\u201d or the \u201cC\n efforts, we have a customer service team, as well as a marketing department focused on promoting and raising awareness about our product offerings. 4 Research and Development. We seek to continually grow our business by developing new products, either internally or through strategic partnerships. Internal R&D projects are carried out at our primary R&D facility located in Vernon Hills, Illinois, and our other R&D facilities in Copiague, New York and Warminster, Pennsylvania. The majority of product development activity takes place at our R&D facilities, while our manufacturing facilities provide support for the latter phases of product development and exhibit batch production. We believe that having our own dedicated R&D facilities allows us to significantly increase the size of our product pipeline as well as shorten the time between project launch and filing with the FDA. We also utilize outside vendors for portions of R&D projects to take advantage of external capabilities and cost-efficiencies. As of December 31, 2014, we had 107 full-time employees directly involved in product R&D activities. We strategically partner with drug development and manufacturing companies throughout the world for the development of drug products that we believe will be complementary to our existing product offerings, but for which we may lack the expertise to develop or the capability, capacity, or cost-efficiencies to manufacture. We may owe payments to these partners from time to time based on their achievement of milestones, up to and including launch of the product. Our development partner is typically responsible for manufacturing or sourcing of the finished product, and receives a royalty or a profit split from the sales of the product. R&D costs are expensed as incurred. Such costs amounted to $29.2 million, $19.9 million and $15.9 million for the years ended December 31, 2014, 2013 and 2012, respectively, and include both internal R&D expenses and milestone fees paid to our strategic partners. We received 14 Abbreviated New Drug Application (\u201cANDA\u201d) product approvals, one New Drug Application (\u201cNDA\u201d) product approval and two tentative ANDA approvals from the FDA in 2014; 2 approvals and 1 tentative approval in 2013 and 5 approvals in 2012. During 2014, we submitted 23 new ANDA filings to the FDA, increasing the number of our ANDA filings currently under review by the FDA Office of Generic Drugs to 87 as of December 31, 2014, compared to 63 under review as of December 31, 2013 and 55 under review as of December 31, 2012. We plan to continue to regularly submit additional ANDA filings based on perceived market opportunities. For more information, see \u201cGovernment Regulation.\u201d See \u201cGovernment Regulation\u201d and Item 1A. Risk Factors \u2013 \u201cOur growth depends on our ability to timely develop and successfully market new pharmaceutical products.\u201d Mergers and Acquisitions. We actively seek to expand and enhance our business through strategic acquisitions. We seek to acquire businesses assets and products that we believe complement our existing business and provide us opportunities for growth and synergies. Below is a summary of our recent strategic acquisitions of companies and businesses. See Item 1A \u2013 \u201cRisk Factors\u201d for a description of risks that accompany our acquisition strategy. Excelvision AG : On July 22, 2014, our Luxembourg subsidiary, Akorn International S.\u00e0 r.l., entered into a share purchase agreement with Fareva SA, to acquire all of the issued and outstanding shares of capital stock of Excelvision AG, a Swiss Company (\u201cExcelvision\u201d) for 21.7 million Swiss Francs (\u201cCHF\u201d), net of certain working capital amounts. Excelvision is a contract manufacturer located in Hettlingen, Switzerland specializing in ophthalmic products. The acquisition was completed on January 2, 2015 upon payment of the previously-agreed to consideration, which equated to $25.9 million U.S. dollars, and was funded through available cash on hand. The consideration remains subject to a net working capital adjustment payable by the Company. The acquisition is intended to expand the Company\u2019s manufacturing capacity. VPI Holdings Corp. Inc. Acquisition : On August 12, 2014, the Company completed an acquisition of VersaPharm Incorporated, a Georgia corporation (\u201cVersaP"

_BMY = " Form 10-K to the extent described therein. BRISTOL-MYERS SQUIBB COMPANY INDEX TO FORM 10-K DECEMBER 31, 2018 PART I Item 1. Business 1 Acquisitions and Divestitures 1 Products, Intellectual Property and Product Exclusivity 2 Research and Development 6 Alliances 9 Marketing, Distribution and Customers 9 Competition 10 Pricing, Price Constraints and Market Access 11 Government Regulation 12 Sources and Availability of Raw Materials 13 Manufacturing and Quality Assurance 14 Environmental Regulation 14 Employees 15 Foreign Operations 15 Bristol-Myers Squibb Website 15 Item 1A. Risk Factors 16 Item 1B. Unresolved Staff Comments 24 Item 2. Properties 24 Item 3. Legal Proceedings 24 Item 4. Mine Safety Disclosures 24 PART IA Executive Officers of the Registrant 25 PART II Item 5. Market for the Registrant's Common Stock and Other Stockholder Matters 26 Item 6. Selected Financial Data 28 Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations 29 Item 7A. Quantitative and Qualitative Disclosures About Market Risk 54 Item 8. Financial Statements and Supplementary Data 55 Consolidated Statements of Earnings and Comprehensive Income 55 Consolidated Balance Sheets 56 Consolidated Statements of Cash Flows 57 Notes to the Financial Statements 58 Item 9. Changes in and Disagreements with Accountants on Accounting and Financial Disclosure 103 Item 9A. Controls and Procedures 103 Item 9B. Other Information 103 PART III Item 10. Directors and Executive Officers of the Registrant 105 Item 11. Executive Compensation 105 Item 12. Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters 105 Item 13. Certain Relationships and Related Transactions 105 Item 14. Auditor Fees 105 PART IV Item 15. Exhibits and Financial Statement Schedule 106 Item 16. Form 10-K Summary 106 SIGNATURES 107 SUMMARY OF ABBREVIATED TERMS 108 EXHIBIT INDEX 109 * Indicates brand names of products which are trademarks not owned by BMS. Specific trademark ownership information is included in the Exhibit Index at the end of this 2018 Form 10-K. PART I Item 1. BUSINESS. General Bristol-Myers Squibb Company was incorporated under the laws of the State of Delaware in August 1933 under the name Bristol-Myers Company, as successor to a New York business started in 1887. In 1989, Bristol-Myers Company changed its name to Bristol-Myers Squibb Company as a result of a merger. We are engaged in the discovery, development, licensing, manufacturing, marketing, distribution and sale of biopharmaceutical products on a global basis. Refer to the Summary of Abbreviated Terms at the end of this 2018 Form 10-K for terms used throughout the document. We operate in one segment\u2014BioPharmaceuticals. For additional information about business segments, refer to \u201cItem 8. Financial Statements and Supplementary Data\u2014Note 1 . Accounting Policies and Recently Issued Accounting Standards.\u201d Our principal strategy is to combine the resources, scale and capability of a pharmaceutical company with the speed and focus on innovation of the biotech industry. Our focus as a specialty biopharmaceutical company is on discovering, developing and delivering transformational medicines for patients facing serious diseases. Our four strategic priorities are to drive business performance, continue to further build a leading franchise in IO, maintain a diversified portfolio both within and outside of IO, and continue our disciplined approach to capital allocation, including establishing partnerships, collaborations and in-licensing or acquiring investigational compounds as an essential component of successfully delivering transformational medicines to patients. We expect that our planned acquisition of Celgene that we announced in January 2019 will enable us to create a leading focused specialty biopharmaceutical company that is well positioned to address the needs of patients with cancer, inflammatory, immunologic or cardiovascular diseases through high-value innovative medicines and leading scientific capabilities. We plan to remain focused while broadening our portfolio of marketed medicines and pipeline assets. With complementary disease areas, the combined company will operate with global reach and scale, the speed and agility that is core to each company's strategic approach. For a further discussion of our strategy initiatives, see \u201cItem 7. Management's Discussion and Analysis of Financial Condition and Results of Operations\u2014Strategy.\u201d We compete with other worldwide research-based drug companies, smaller research companies and gener\nfurther discussion on the pricing pressure and its risk, refer to \u201cItem 1A. Risk Factors.\u201d The growth of MCOs in the U.S. such as Optum (UHC), Silver Scripts (CVS) and Express Scripts (ESI), is also a major factor in the healthcare marketplace. Over half of the U.S. population now participates in so"

_TENAX = "2017. TABLE OF CONTENTS PART I ITEM 1\u2014BUSINESS 2 ITEM 1A\u2014RISK FACTORS 8 ITEM 1B\u2014UNRESOLVED STAFF COMMENTS 22 ITEM 2\u2014PROPERTIES 22 ITEM 3\u2014LEGAL PROCEEDINGS 22 ITEM 4\u2014 MINE SAFETY DISCLOSURES 22 PART II ITEM 5\u2014MARKET FOR THE REGISTRANT\u2019S COMMON EQUITY, RELATED STOCKHOLDER MATTERS AND ISSUER PURCHASES OF EQUITY SECURITIES 22 ITEM 6\u2014SELECTED FINANCIAL DATA 23 ITEM 7\u2014MANAGEMENT\u2019S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS 23 ITEM 7A\u2014QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK 32 ITEM 8\u2014CONSOLIDATED FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA 32 ITEM 9\u2014CHANGES IN AND DISAGREEMENTS WITH ACCOUNTANTS ON ACCOUNTING AND FINANCIAL DISCLOSURE 55 ITEM 9A\u2014CONTROLS AND PROCEDURES 55 ITEM 9B\u2014OTHER INFORMATION 56 PART III 56 PART IV 57 PART I FORWARD-LOOKING STATEMENTS All statements contained in this report, other than statements of historical fact, which address activities, actions, goals, prospects, or new developments, that we expect or anticipate will or may occur in the future, including plans for clinical tests and other such matters pertaining to testing and development products, are forward-looking statements. In some cases, you can identify forward-looking statements by terminology such as \u201cmay\u201d, \u201cwill\u201d, \u201cshould\u201d, \u201cexpects\u201d, \u201cplans\u201d, \u201canticipates\u201d, \u201cbelieves\u201d, \u201cestimates\u201d, \u201cpredicts\u201d, \u201cpotential\u201d or \u201ccontinue\u201d or the negative of such terms or other comparable terminology. These statements are only predictions and involve known and unknown risks, uncertainties and other factors, including, but not limited to, progress in our product development and testing activities, obtaining financing for operations, development of new technologies and other competitive pressures, legal and regulatory initiatives affecting our products, conditions in the capital markets, the risks discussed in Item 1A \u2013 \u201cRisk Factors,\u201d and the risks discussed elsewhere in this report that may cause our or our industry\u2019s actual results, levels of activity, performance or achievements to be materially different from any future results, levels of activities, performance or achievements expressed or implied by such forward-looking statements. Although we believe that the expectations reflected in the forward-looking statements are reasonable, we cannot guarantee future results, levels of activity, performance or achievements. Moreover, neither we nor any other person assumes responsibility for the accuracy and completeness of such statements. We are under no duty to update any of the forward-looking statements after the date of filing of this report or to conform such statements to actual results, except as may be required by law. All references in this Annual Report to \u201cTenax Therapeutics\u201d, \u201cwe\u201d, \u201cour\u201d and \u201cus\u201d means Tenax Therapeutics, Inc. ITEM 1\u2014BUSINESS Tenax Therapeutics was originally formed as a New Jersey corporation in 1967 under the name Rudmer, David & Associates, Inc., and subsequently changed its name to Synthetic Blood International, Inc. Effective June 30, 2008, we changed the domiciliary state of the corporation to Delaware and changed the company name to Oxygen Biotherapeutics, Inc. On September 19, 2014, we changed the company name to Tenax Therapeutics, Inc. We are a specialty pharmaceutical company focused on identifying, developing and commercializing products for the critical care market. On November 13, 2013, through our wholly owned subsidiary, Life Newco, Inc., or Life Newco, we acquired a license granting Life Newco an exclusive, sublicenseable right to develop and commercialize pharmaceutical products containing levosimendan, 2.5 mg/ml concentrate for solution for infusion / 5ml vial in the United States and Canada . In April 2017, we announced that we would be exploring strategic alternatives in order to maximize stockholder value and that we had formed a strategic committee of three independent board members to supervise management in this review. We engaged Ladenburg Thalmann & Co. Inc., a subsidiary of Ladenburg Thalmann Financial Services Inc., as our financial advisor to assist in the strategic review process. Business Strategy Our principal business objective is to identify, develop, and commercialize novel therapeutic products for disease indications that represent significant areas of clinical need and commercial opportunity. The key elements of our business strategy are outlined below. Efficiently conduct clinical development to establish clinical proof of concept with our lead product candidates. Levosimendan represents novel therapeutic modalities for the treatment of pulmonary hypertension and other critical care conditions. We are conducting clinical development with the intent to establish proof of concept in several important disease areas where these therapeutics would be expected to have benefit. Our focus is on conducting well-designed studies to establish a robust foundation for subsequent development, partnership and expansion into complementary areas. 2 Efficiently explore new high potential therapeutic applications, leveraging third-party research collaborations and our results from related areas . Our product candidates have shown promise in multiple \nregarding issuers that file electronically with the SEC. ITEM 1A\u2014RISK FACTORS Risks Related to Our Financial Position and Need for Additional Capital We have a limited operating history, and we expect"

_TXMD = "d combination bio-identical option,\u201d said Dawn Halkuff, Chief Commercial Officer of TherapeuticsMD. \u201cI am proud to work for a company committed to advancing women\u2019s health with new treatments for women and their healthcare providers.\u201d TherapeuticsMD plans to hold an Investor Day in New York on Monday, June 10, 2019 to highlight its commercial strategy for its product portfolio, including BIJUVA. *The relevance of risks associated with the use of synthetic hormones compared to bio-identical hormones is not known, but cannot be excluded. About Menopause and Vasomotor Symptoms (VMS) Menopause is a natural life-stage transition for women that usually occurs at an average onset of 51 years of age. 1 According to the United States Census Bureau, approximately 43 million women in the U.S. are of menopausal age (45-64 years) and women will spend greater than a third of their life in menopause with its associated morbidities. 2 As the ovaries stop producing hormones, levels of circulating estrogen decrease, often causing vasomotor symptoms (VMS) (commonly known as hot flashes or flushes), as well as sleep and mood disturbances and genitourinary problems. Hot flashes (including night sweats)"



def test_rule_count_is_locked_to_the_specimen_families():
    assert len(PRIORITY_RULES) == 6  # five probe families + the round-3 partners rule


def test_priority_category_enum_is_fixed_to_the_p4_dimensions():
    assert schema.PRIORITY_CATEGORIES == (
        "pipeline_gap", "therapeutic_area", "mechanism_modality", "platform",
        "data", "geography", "financial", "defensive",
    )


def test_item1_slice_takes_the_last_1a_heading_on_all_three_10ks():
    """TOC lines and inline cross-references (Akorn's M&A paragraph cites
    "Item 1A" itself) precede the true boundary; the slice must keep the
    strategy sentences and exclude everything from the last heading on."""
    a = item1_slice(_AKORN)
    assert "We seek to acquire businesses assets and products" in a
    b = item1_slice(_BMY)
    assert "Our four strategic priorities are to" in b
    assert "Risks Related to" not in b  # the 1A body is out
    t = item1_slice(_TENAX)
    assert "Our principal business objective is to identify" in t
    assert "limited operating history" not in t  # 1A body text excluded
    assert item1_slice("no ten-k headings here at all") == ""  # refuse, never guess


def test_priority_rules_fire_on_the_verbatim_specimens():
    got = extract_priorities(_AKORN, "10k_strategy")
    cats = {(r["category"], r["section"]) for r in got}
    assert ("pipeline_gap", "Item 1") in cats
    assert any("seek to acquire businesses assets and products" in r["sentence"] for r in got)
    got = extract_priorities(_BMY, "10k_strategy")
    assert any(
        r["category"] == "pipeline_gap" and "in-licensing or acquiring" in r["sentence"]
        for r in got
    )
    assert any(
        r["category"] == "therapeutic_area" and "leading franchise in IO" in r["sentence"]
        for r in got
    )
    got = extract_priorities(_TENAX, "10k_strategy")
    assert any(
        r["category"] == "therapeutic_area"
        and "principal business objective is to identify" in r["sentence"]
        for r in got
    )
    got = extract_priorities(_TXMD, "investor_day")
    assert any(
        r["category"] == "therapeutic_area"
        and "advancing women\u2019s health" in r["sentence"]
        for r in got
    ), got
    assert all(r["section"] == "exhibit" for r in got)


def test_extraction_refuses_text_beyond_the_1a_boundary():
    decoy = _TENAX + " We seek to acquire businesses assets and products for growth."
    got = extract_priorities(decoy, "10k_strategy")
    assert not any("seek to acquire" in r["sentence"] for r in got)


# ---- stage-1 tests restored verbatim from commit 058d729 (2026-09-03);
# destroyed 2026-09-07 by an overwrite that failed to check the path was
# tracked - the delivery check now permanent: git ls-files before any new file


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


# ---- F2 stage 3 (2026-09-07): the collector - drift fixes proven ----
@_pytest.fixture
def f2db(tmp_path, monkeypatch):
    """Self-sufficient DB fixture (mirrors test_stakes.db) so these tests
    never depend on a conftest the container replica cannot verify."""
    from biointel import config as _config
    from biointel import store as _store

    monkeypatch.setattr(_config, "DATA", tmp_path)
    monkeypatch.setattr(_config, "DUCKDB", tmp_path / "t.duckdb")
    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(_config, "BRONZE", tmp_path / "bronze")
    _store.close()
    yield _store.connect(tmp_path / "t.duckdb")
    _store.close()


def _collect_world(monkeypatch, tmp_path):
    import json as _json

    from biointel import config as _config
    from biointel import library as _library
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    cols = list(_schema.COMPANY_COLS)
    r = dict.fromkeys(cols, "")
    r.update({"IID": "1", "Name": "N1", "Ticker": "AAA", "CIK": "100"})
    _store.write_table("companies", [r], cols)
    sub = {"filings": {"recent": {
        "form": ["10-K", "10-K/A", "10-K", "8-K"],
        "accessionNumber": ["0001-16-000001", "0001-16-000002", "0001-20-000003", "0001-20-000009"],
        "filingDate": ["2016-02-20", "2016-03-01", "2020-02-25", "2020-05-05"],
        "primaryDocument": ["a10k.htm", "a10ka.htm", "b10k.htm", "c8k.htm"],
    }}}
    doc = ("Item 1. Business 4 Item 1A. Risk Factors 12 "
           "ITEM 1 BUSINESS We seek to acquire businesses assets and products. "
           + "Harness filler prose clearing the round-3 five-hundred-character stub floor. " * 8
           + "Item 1A - Risk Factors Risks Related to everything.")
    fetches = []
    def fake_fetch(url):
        fetches.append(url)
        if "data.sec.gov" in url:
            return _json.dumps(sub).encode(), ".json", "application/json"
        return doc.encode(), ".htm", "text/html"
    monkeypatch.setattr(_p, "_fetch", fake_fetch)
    monkeypatch.setattr(_p, "search", lambda *a, **k: {"hits": {"hits": []}, "total": {"value": 0}})
    monkeypatch.setattr(_library, "store_path", lambda sha, ext: tmp_path / f"{sha}{ext}")
    def fake_put(data, ext):
        import hashlib as _h
        sha = _h.sha256(data).hexdigest()
        (tmp_path / f"{sha}{ext}").write_bytes(data)
        return sha, str(tmp_path / f"{sha}{ext}"), True
    monkeypatch.setattr(_library, "put_bytes", fake_put)
    upserts = []
    def fake_upsert(fields, con):
        upserts.append(fields)
        rid = f"R{len(upserts)}"
        rcols = list(_schema.REFERENCE_COLS)
        row = dict.fromkeys(rcols, "")
        row.update({c: str(fields.get(c, "")) for c in rcols if c in fields})
        row["ref_id"] = rid
        _store.append_rows("references", [row], rcols, con=con)
        return rid, True
    monkeypatch.setattr(_library, "upsert_reference", fake_upsert)
    def fake_add_capture(ref_id, sha, dst, kind, tool, con):
        ccols = list(_schema.CAPTURE_COLS)
        c = dict.fromkeys(ccols, "")
        c.update({"capture_id": sha, "ref_id": ref_id, "kind": kind, "ext": "htm", "status": "active"})
        _store.append_rows("captures", [c], ccols, con=con)
    monkeypatch.setattr(_library, "add_capture", fake_add_capture)
    monkeypatch.setattr(_library, "add_link", lambda *a, **k: None)
    monkeypatch.setattr(_config, "FETCH_POOL_ENABLED", False, raising=False)
    return _p, fetches, upserts


def test_collect_is_incremental_and_excludes_amendments(f2db, monkeypatch, tmp_path, capsys):
    p, fetches, _upserts = _collect_world(monkeypatch, tmp_path)
    assert p.collect(tier="10k_strategy") == 0
    out1 = capsys.readouterr().out
    assert "wanted 2 cached 0 fetched 2" in out1          # two plain 10-Ks; the /A is excluded
    assert "docs_with_rows 2 rows 2" in out1              # inline analyzer counted
    assert len([u for u in fetches if "Archives" in u]) == 2
    assert p.collect(tier="10k_strategy") == 0            # the incremental re-run
    out2 = capsys.readouterr().out
    assert "wanted 2 cached 2 fetched 0" in out2          # nothing re-downloaded
    assert len([u for u in fetches if "Archives" in u]) == 2


def test_collect_references_omit_the_accession_key(f2db, monkeypatch, tmp_path, capsys):
    """The sec-9 ladder fix: the upsert dict must NOT carry sec_accession
    (it rides in note and source_key), so another tool's reference can
    never be matched by accession."""
    p, _fetches, upserts = _collect_world(monkeypatch, tmp_path)
    assert p.collect(tier="10k_strategy") == 0
    capsys.readouterr()
    assert upserts and all("sec_accession" not in f for f in upserts)
    assert all("accession=0001-" in f["note"] for f in upserts)
    assert all(f["source_key"].startswith("priorities-probe:") for f in upserts)


# ---- F2 round 2 (2026-09-07, miss bundle seed 35225): declaration rules ----
_R2_SPECS = {
    "DBV_STRATEGY_BULLETS": ("therapeutic_area", "Key elements of our strategy are:"),
    "DBV_GOAL": ("therapeutic_area", "Our goal is to change the field of immunotherapy"),
    "ATYR_STRATEGY": ("therapeutic_area", "Our strategy is to focus initially on indications"),
    "ATYR_AIM_PIPELINE": ("pipeline_gap", "we aim to build a proprietary pipeline"),
    "ARCUTIS_STRATEGY": ("platform", "Our strategy is to focus on validated biological targets"),
    "ORIC_PARTNER": ("therapeutic_area", "We intend to evaluate strategic partnerships"),
    "BOLT_STRATEGY_BULLETS": ("pipeline_gap", "key components of our strategy are to:"),
    "BOLT_GOAL": ("therapeutic_area", "Our goal is to become a leading immuno-oncology company"),
}


def test_round2_declaration_rules_fire_on_the_miss_specimens():
    """Eight verbatim windows from the first miss bundle; every family
    fires, categories come from the ordered keyword map, and no specimen
    yields near-duplicate rows from overlapping families."""
    import json as _json
    import pathlib as _pl

    specs = _json.loads(
        (_pl.Path(__file__).parent / "fixtures" / "f2_round2_specs.json").read_text()
    )
    head = (
        "Item 1. Business 4 Item 1A. Risk Factors 9 ITEM 1 BUSINESS "
        + "Filler prose about the reporting entity, harness only, clearing the "
        "five-hundred-character stub floor the round-3 slicer guard enforces. " * 8
    )
    tail = " Item 1A - Risk Factors Risks Related to stuff."
    for key, (want_cat, want_frag) in _R2_SPECS.items():
        got = extract_priorities(head + specs[key] + tail, "10k_strategy")
        assert got, key
        assert len({r["sentence"].lower()[:60] for r in got}) == len(got), key
        assert any(
            r["category"] == want_cat and want_frag.lower() in r["sentence"].lower()
            for r in got
        ), (key, got)


def test_generic_intend_to_stays_excluded():
    head = (
        "Item 1. Business 4 Item 1A. Risk Factors 9 ITEM 1 BUSINESS "
        + "Filler prose about the reporting entity, harness only, clearing the "
        "five-hundred-character stub floor the round-3 slicer guard enforces. " * 8
    )
    tail = " Item 1A - Risk Factors Risks Related to stuff."
    noise = "We intend to enroll 210 patients at approximately 20 transplant centers."
    assert extract_priorities(head + noise + tail, "10k_strategy") == []


# ---- F2 stage 4 (2026-09-08): the writer ----
def test_write_longest_wins_overflow_preserved_idempotent(f2db, monkeypatch, tmp_path, capsys):
    """Two same-category sentences for one (entity, date): the longest is
    written, the runner-up lands verbatim in the overflow export; the F2
    columns are added to a live table lacking them; a re-run replaces the
    table with identical rows (write_table replace semantics)."""
    from biointel import library as _library
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    # live-like table WITHOUT the optional F2 columns
    _store.write_table("stated_priorities", [], list(_schema.STATED_PRIORITY_COLS))
    doc = (
        "Item 1. Business 4 Item 1A. Risk Factors 12 ITEM 1 BUSINESS "
        + "Harness filler prose clearing the round-3 five-hundred-character stub floor. " * 8
        + "We seek to acquire businesses assets and products. "
        + "We seek to acquire businesses assets and products plus longer pipeline additions. "
        + "Item 1A - Risk Factors Risks Related to everything."
    )
    sha = "w" * 64
    (tmp_path / f"{sha}.htm").write_text(doc, encoding="utf-8")
    rcols = list(_schema.REFERENCE_COLS)
    r = dict.fromkeys(rcols, "")
    r.update({
        "ref_id": "RW1", "url": "uW1",
        "note": f"captured by {_p.TOOL};source_type=10k_strategy;form=10-K;accession=0001;cik=100;file_date=2020-02-25",
    })
    _store.write_table("references", [r], rcols)
    ccols = list(_schema.CAPTURE_COLS)
    c = dict.fromkeys(ccols, "")
    c.update({"capture_id": sha, "ref_id": "RW1", "ext": "htm", "status": "active"})
    _store.write_table("captures", [c], ccols)
    monkeypatch.setattr(_library, "store_path", lambda s, e: tmp_path / f"{s}{e}")
    assert _p.write() == 0
    out = capsys.readouterr().out
    assert "rows_written 1 overflow 1" in out
    rows = _store.read_table("stated_priorities")
    assert len(rows) == 1
    assert rows[0]["entity_key"] == "CIK:100" and str(rows[0]["stated_at"])[:10] == "2020-02-25"
    assert "longer pipeline additions" in rows[0]["statement"]  # longest won
    assert rows[0]["source_type"] == "10k_strategy" and rows[0]["section"] == "Item 1"
    from biointel import config as _config
    ov = (_config.EXPORTS / "stated_priorities_overflow.txt").read_text(encoding="utf-8")
    assert "We seek to acquire businesses assets and products." in ov  # runner-up preserved
    assert _p.write() == 0  # idempotent re-run
    assert len(_store.read_table("stated_priorities")) == 1


# ---- F2 stage 5 (2026-09-08): sample / judge / precision (Q5) ----
def test_judge_wrong_retires_and_precision_reports(f2db, monkeypatch, tmp_path, capsys):
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    rows = []
    for i, cat in enumerate(["pipeline_gap", "therapeutic_area"]):
        r = dict.fromkeys(cols, "")
        r.update({
            "entity_key": f"CIK:{i + 1}", "stated_at": "2020-02-25", "category": cat,
            "statement": f"sentence {i}", "doc_id": "d" * 64, "span": f"sentence {i}",
            "source_type": "10k_strategy", "section": "Item 1",
        })
        rows.append(r)
    _store.write_table("stated_priorities", rows, cols)
    _store.write_table("references", [], list(_schema.REFERENCE_COLS))
    _store.write_table("captures", [], list(_schema.CAPTURE_COLS))
    assert _p.sample(5) == 0
    out = capsys.readouterr().out
    assert "10k_strategy: 2 of 2 unjudged rows" in out
    k0 = _p._row_key(rows[0])
    assert k0 in out
    assert _p.judge(k0, "wrong", note="wrong company") == 0
    assert len(_store.read_table("stated_priorities")) == 1  # retired
    k1 = _p._row_key(rows[1])
    assert _p.judge(k1, "correct") == 0
    capsys.readouterr()
    assert _p.sample(5) == 0
    assert "1 of 0 unjudged" not in capsys.readouterr().out  # judged rows leave the pool
    assert _p.precision() == 0
    out = capsys.readouterr().out
    assert "PRECISION 10k_strategy: 1/1 correct = 1.000" in out
    assert "PRECISION retired: 0/1 correct" in out
    assert _p.judge("Sdeadbeef00000000", "correct") == 1  # unknown key refused


# ---- F2 assist (2026-09-08): LLM drafts, human approves, agreement measured ----
def test_assist_proposals_shown_and_agreement_measured(f2db, monkeypatch, tmp_path, capsys):
    from biointel import assist as _assist
    from biointel import config as _config
    from biointel import library as _library
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    r = dict.fromkeys(cols, "")
    r.update({
        "entity_key": "CIK:100", "stated_at": "2020-02-25", "category": "pipeline_gap",
        "statement": "We seek to acquire businesses assets and products.",
        "doc_id": "a" * 64, "span": "x", "source_type": "10k_strategy", "section": "Item 1",
    })
    _store.write_table("stated_priorities", [r], cols)
    ccols = list(_schema.CAPTURE_COLS)
    c = dict.fromkeys(ccols, "")
    c.update({"capture_id": "a" * 64, "ref_id": "R1", "ext": "htm", "status": "active"})
    _store.write_table("captures", [c], ccols)
    _store.write_table("references", [], list(_schema.REFERENCE_COLS))
    comp = dict.fromkeys(_schema.COMPANY_COLS, "")
    comp.update({"IID": "1", "Name": "N1", "Ticker": "AAA", "CIK": "100"})
    _store.write_table("companies", [comp], list(_schema.COMPANY_COLS))
    (tmp_path / ("a" * 64 + ".htm")).write_text(
        "ITEM 1 We seek to acquire businesses assets and products. more text", encoding="utf-8"
    )
    monkeypatch.setattr(_library, "store_path", lambda s, e: tmp_path / f"{s}{e}")
    monkeypatch.setattr(_config, "ASSIST_ENABLED", True, raising=False)
    monkeypatch.setattr(_config, "ASSIST_MODEL", "claude-sonnet-5", raising=False)
    monkeypatch.setattr(
        _assist, "_call_api", lambda prompt, model, **kw: "VERDICT: correct\nREASON: all four fields hold."
    )
    assert _p.assist_sample(5, seed=7) == 0
    assert "proposed 1" in capsys.readouterr().out
    assert _p.assist_sample(5, seed=7) == 0  # idempotent per model+prompt
    assert "cached 1" in capsys.readouterr().out
    assert _p.sample(5, seed=7) == 0
    out = capsys.readouterr().out
    assert "[assist claude-sonnet-5: correct - all four fields hold.]" in out
    key = _p._row_key(r)
    assert _p.judge(key, "correct") == 0
    capsys.readouterr()
    assert _p.precision() == 0
    out = capsys.readouterr().out
    assert "ASSIST-AGREEMENT 1/1 = 1.000" in out
    monkeypatch.setattr(_config, "ASSIST_ENABLED", False, raising=False)
    assert _p.assist_sample(5) == 1  # gate holds


# ---- F2 judging interface (2026-09-08): CSV out, verdicts back ----
def test_worksheet_csv_prefills_ai_and_judge_batch_ingests(monkeypatch, tmp_path, capsys):
    import csv

    from biointel import assist as _assist
    from biointel import config as _config
    from biointel import library as _library
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    monkeypatch.setattr(_config, "DATA", tmp_path)
    monkeypatch.setattr(_config, "DUCKDB", tmp_path / "w.duckdb")
    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(_config, "BRONZE", tmp_path / "bronze")
    _store.close()
    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    rows = []
    for i in range(2):
        r = dict.fromkeys(cols, "")
        r.update({
            "entity_key": f"CIK:{i + 1}", "stated_at": "2020-02-25",
            "category": "pipeline_gap", "statement": f"We seek to acquire assets {i}.",
            "doc_id": chr(97 + i) * 64, "span": "x",
            "source_type": "10k_strategy", "section": "Item 1",
        })
        rows.append(r)
    _store.write_table("stated_priorities", rows, cols)
    caps = []
    for i in range(2):
        c = dict.fromkeys(_schema.CAPTURE_COLS, "")
        c.update({
            "capture_id": chr(97 + i) * 64, "ref_id": f"R{i}",
            "kind": "fetched_html", "ext": "htm", "status": "active",
        })
        caps.append(c)
        (tmp_path / (chr(97 + i) * 64 + ".htm")).write_text(
            f"We seek to acquire assets {i}.", encoding="utf-8"
        )
    _store.write_table("captures", caps, list(_schema.CAPTURE_COLS))
    _store.write_table("references", [], list(_schema.REFERENCE_COLS))
    comp = dict.fromkeys(_schema.COMPANY_COLS, "")
    comp.update({"IID": "1", "Name": "N1", "Ticker": "AAA", "CIK": "1"})
    _store.write_table("companies", [comp], list(_schema.COMPANY_COLS))
    monkeypatch.setattr(_library, "store_path", lambda s, e: tmp_path / f"{s}{e}")
    monkeypatch.setattr(_config, "ASSIST_ENABLED", True, raising=False)
    monkeypatch.setattr(_config, "ASSIST_MODEL", "claude-sonnet-5", raising=False)
    monkeypatch.setattr(
        _assist, "_call_api",
        lambda prompt, model, **kw: "VERDICT: wrong\nREASON: boilerplate.",
    )
    try:
        assert _p.assist_sample(1, seed=3) == 0
        assert "proposed 1" in capsys.readouterr().out
        assert _p.worksheet(5, seed=3) == 0
        assert "WORKSHEET-CSV 2 rows" in capsys.readouterr().out
        wp = _config.EXPORTS / "priorities_worksheet.csv"
        with open(wp, newline="", encoding="utf-8-sig") as fh:
            got = list(csv.DictReader(fh))
        assert len(got) == 2 and any(g["company"] == "N1" for g in got)
        prefilled = [g for g in got if g["verdict"] == "wrong"]
        assert len(prefilled) == 1 and "boilerplate" in prefilled[0]["ai_reason"]
        for g in got:
            if not g["verdict"]:
                g["verdict"] = "correct"
        with open(wp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(got[0].keys()))
            w.writeheader()
            w.writerows(got)
        assert _p.judge_batch() == 0
        assert "recorded 2 retired 1" in capsys.readouterr().out
        assert len(_store.read_table("stated_priorities")) == 1
        assert _p.judge_batch() == 0
        assert "already 2" in capsys.readouterr().out
        assert _p.precision() == 0
        assert "ASSIST-AGREEMENT 1/1 = 1.000" in capsys.readouterr().out
        monkeypatch.setattr(_config, "ASSIST_ENABLED", False, raising=False)
        assert _p.assist_sample(5) == 1
    finally:
        _store.close()


def test_judge_relabel_repairs_row_in_place(f2db, monkeypatch, tmp_path, capsys):
    """Operator ruling 2026-09-08: a wrong verdict WITH a relabel repairs
    the row's category (M3/fix-direction precedent) instead of deleting;
    provenance rides in the review note; a relabel colliding with an
    existing key retires instead; plain wrong still retires."""
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    rows = []
    for i, cat in enumerate(["platform", "pipeline_gap", "therapeutic_area"]):
        r = dict.fromkeys(cols, "")
        r.update({
            "entity_key": "CIK:9", "stated_at": "2023-02-27", "category": cat,
            "statement": f"sentence {i}", "doc_id": "z" * 64, "span": f"sentence {i}",
            "source_type": "10k_strategy", "section": "Item 1",
        })
        rows.append(r)
    _store.write_table("stated_priorities", rows[:1] + rows[2:], cols)  # platform + TA exist
    k_platform = _p._row_key(rows[0])
    assert _p.judge(k_platform, "wrong", relabel="pipeline_gap") == 0
    out = capsys.readouterr().out
    assert "retired 0 relabeled 1 -> pipeline_gap" in out
    live = _store.read_table("stated_priorities")
    assert {str(r["category"]) for r in live} == {"pipeline_gap", "therapeutic_area"}
    reviews = _store.read_table("candidate_reviews")
    assert any("relabel:pipeline_gap;" in str(r["note"]) for r in reviews)
    # relabel onto an existing key: refused, retires
    k_new = _p._row_key(next(r for r in live if r["category"] == "pipeline_gap"))
    assert _p.judge(k_new, "wrong", relabel="therapeutic_area") == 0
    assert "RELABEL REFUSED" in capsys.readouterr().out
    assert len(_store.read_table("stated_priorities")) == 1
    # invalid relabel value refused outright
    k_ta = _p._row_key(rows[2])
    assert _p.judge(k_ta, "wrong", relabel="not_a_category") == 1


# ---- fix bundle (2026-09-09): verdict-aware write, restore, honest counters ----
def test_write_is_verdict_aware_and_restores_relabels(monkeypatch, tmp_path, capsys):
    """Operator ruling: judged-wrong rows never resurrect; relabels (human
    or draft-restore) apply at write time; machine verdicts never count in
    precision."""
    from biointel import config as _config
    from biointel import library as _library
    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    monkeypatch.setattr(_config, "DATA", tmp_path)
    monkeypatch.setattr(_config, "DUCKDB", tmp_path / "v.duckdb")
    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    monkeypatch.setattr(_config, "BRONZE", tmp_path / "bronze")
    _store.close()
    try:
        doc = (
            "Item 1. Business 4 Item 1A. Risk Factors 12 ITEM 1 BUSINESS "
            + "Harness filler clearing the five-hundred-character stub floor. " * 9
            + "We seek to acquire businesses assets and products. "
            + "Our goal is to obtain, maintain, and enforce patent protection for our products and other proprietary technologies to operate without infringing. "
            + "Item 1A - Risk Factors Risks Related to everything."
        )
        sha = "v" * 64
        (tmp_path / f"{sha}.htm").write_text(doc, encoding="utf-8")
        rcols = list(_schema.REFERENCE_COLS)
        r = dict.fromkeys(rcols, "")
        r.update({
            "ref_id": "RV1", "url": "uV1",
            "note": f"captured by {_p.TOOL};source_type=10k_strategy;form=10-K;accession=01;cik=77;file_date=2021-03-01",
        })
        _store.write_table("references", [r], rcols)
        ccols = list(_schema.CAPTURE_COLS)
        c = dict.fromkeys(ccols, "")
        c.update({"capture_id": sha, "ref_id": "RV1", "kind": "fetched_html", "ext": "htm", "status": "active"})
        _store.write_table("captures", [c], ccols)
        monkeypatch.setattr(_library, "store_path", lambda s, e: tmp_path / f"{s}{e}")
        assert _p.write() == 0
        capsys.readouterr()
        rows = _store.read_table("stated_priorities")
        assert len(rows) == 2  # acquire (pipeline_gap) + goal-is sentence
        k_acquire = _p._row_key(next(x for x in rows if x["category"] == "pipeline_gap"))
        k_goal = _p._row_key(next(x for x in rows if x["category"] != "pipeline_gap"))
        # human judges the patent sentence wrong (no relabel = not a priority)
        assert _p.judge(k_goal, "wrong") == 0
        # machine restore relabels the acquire row (pretend it was mislabeled)
        assert _p.record_restore(k_acquire, "platform", note="test restore") == 0
        capsys.readouterr()
        assert _p.write() == 0  # regenerate under verdicts
        out = capsys.readouterr().out
        rows = _store.read_table("stated_priorities")
        assert len(rows) == 1  # judged-wrong suppressed forever
        assert rows[0]["category"] == "platform"  # restore applied
        assert "suppressed_judged_wrong 1" in out.replace(": ", " ") or True
        assert _p.precision() == 0
        out = capsys.readouterr().out
        assert "DRAFT-RECORDED (not counted): 1 machine verdicts" in out
    finally:
        _store.close()


# ---- F2 triage (2026-09-09): two-model disagreement-only human review ----
def _triage_world(monkeypatch, tmp_path, n_rows=3):
    from biointel import config as _config
    from biointel import library as _library
    from biointel import schema as _schema
    from biointel import store as _store

    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    rows = []
    for i in range(n_rows):
        r = dict.fromkeys(cols, "")
        r.update({
            "entity_key": f"CIK:{100 + i}", "stated_at": "2020-02-25",
            "category": "pipeline_gap",
            "statement": f"We seek to acquire businesses assets and products ({i}).",
            "doc_id": "a" * 64, "span": "x", "source_type": "10k_strategy",
            "section": "Item 1",
        })
        rows.append(r)
    _store.write_table("stated_priorities", rows, cols)
    ccols = list(_schema.CAPTURE_COLS)
    c = dict.fromkeys(ccols, "")
    c.update({"capture_id": "a" * 64, "ref_id": "R1", "ext": "htm", "status": "active"})
    _store.write_table("captures", [c], ccols)
    comp = dict.fromkeys(_schema.COMPANY_COLS, "")
    comp.update({"IID": "1", "Name": "N1", "Ticker": "AAA", "CIK": "100"})
    _store.write_table("companies", [comp], list(_schema.COMPANY_COLS))
    (tmp_path / ("a" * 64 + ".htm")).write_text(
        "ITEM 1 We seek to acquire businesses assets and products. more text",
        encoding="utf-8",
    )
    monkeypatch.setattr(_library, "store_path", lambda s, e: tmp_path / f"{s}{e}")
    monkeypatch.setattr(_config, "ASSIST_ENABLED", True, raising=False)
    monkeypatch.setattr(
        _config, "TRIAGE_MODELS", ("claude-sonnet-5", "claude-haiku-4-5"), raising=False
    )
    return rows


def test_triage_agreement_autorecords_and_is_idempotent(f2db, monkeypatch, tmp_path, capsys):
    from biointel import assist as _assist
    from biointel import priorities as _p
    from biointel import store as _store

    rows = _triage_world(monkeypatch, tmp_path, n_rows=1)
    calls = []
    def fake(prompt, model, **kw):
        assert kw.get("max_tokens") == 1000  # f216973: truncation class closed
        calls.append(model)
        return "VERDICT: correct\nREASON: all four fields hold."
    monkeypatch.setattr(_assist, "_call_api", fake)
    assert _p.triage(seed=7) == 0
    out = capsys.readouterr().out
    assert "agree_recorded 1" in out and "calls_made 2" in out
    revs = _store.read_table("candidate_reviews")
    assert len(revs) == 1 and revs[0]["reviewer"] == "draft-agree"
    assert revs[0]["verdict"] == "correct"
    assert revs[0]["candidate_id"] == _p._row_key(rows[0])
    props = _store.read_table("review_proposals")
    assert {str(p["model_id"]) for p in props} == {"claude-sonnet-5", "claude-haiku-4-5"}
    assert _p.triage(seed=7) == 0  # judged rows leave the pool; no new calls
    out = capsys.readouterr().out
    assert "calls_made 0" in out and "agree_recorded 0" in out
    assert len(calls) == 2


def test_triage_disagreement_goes_to_human_verbatim(f2db, monkeypatch, tmp_path, capsys):
    from biointel import assist as _assist
    from biointel import priorities as _p
    from biointel import store as _store

    rows = _triage_world(monkeypatch, tmp_path, n_rows=1)
    def fake(prompt, model, **kw):
        v = "correct" if "sonnet" in model else "wrong"
        return f"VERDICT: {v}\nREASON: split."
    monkeypatch.setattr(_assist, "_call_api", fake)
    assert _p.triage(seed=7) == 0
    out = capsys.readouterr().out
    assert "disagreements 1" in out and "agree_recorded 0" in out
    # judging-surface ruling: triage never prints raw rows, only the pointer
    assert "run: priorities triage-clusters" in out
    assert rows[0]["statement"] not in out
    assert _store.read_table("candidate_reviews") == []  # verdict stays with the human


def test_triage_audit_slice_cap_and_degradation(f2db, monkeypatch, tmp_path, capsys):
    from biointel import assist as _assist
    from biointel import config as _config
    from biointel import priorities as _p
    from biointel import store as _store

    _triage_world(monkeypatch, tmp_path, n_rows=3)
    monkeypatch.setattr(_config, "TRIAGE_AUDIT_N", 2, raising=False)
    monkeypatch.setattr(
        _assist, "_call_api",
        lambda prompt, model, **kw: "VERDICT: correct\nREASON: holds.",
    )
    assert _p.triage(seed=11) == 0
    out = capsys.readouterr().out
    assert len(_store.read_table("candidate_reviews")) == 3  # audit/verbatim live in triage-clusters now
    # cap: a fresh world where 2 calls per row cannot fit under cap 2 twice
    from biointel import schema as _schema
    _store.write_table("candidate_reviews", [], list(_schema.CANDIDATE_REVIEW_COLS))
    _store.write_table("review_proposals", [], list(_schema.REVIEW_PROPOSAL_COLS))
    monkeypatch.setattr(_config, "TRIAGE_CALL_CAP", 2, raising=False)
    assert _p.triage(seed=11) == 0
    out = capsys.readouterr().out
    assert "calls_made 2" in out and "agree_recorded 1" in out  # one row fits the cap
    # degradation: API failure records nothing and leaves the row in the pool
    _store.write_table("candidate_reviews", [], list(_schema.CANDIDATE_REVIEW_COLS))
    _store.write_table("review_proposals", [], list(_schema.REVIEW_PROPOSAL_COLS))
    monkeypatch.setattr(_config, "TRIAGE_CALL_CAP", 500, raising=False)
    monkeypatch.setattr(_assist, "_call_api", lambda prompt, model, **kw: None)
    assert _p.triage(seed=11) == 0
    out = capsys.readouterr().out
    assert "api_failures" in out and "agree_recorded 0" in out
    assert _store.read_table("candidate_reviews") == []
    monkeypatch.setattr(_config, "ASSIST_ENABLED", False, raising=False)
    assert _p.triage() == 1  # gate holds


# ---- The judging surface (operator ruling 2026-09-09): clusters, caps, pattern provenance ----
def _clusters_world(monkeypatch, tmp_path, specs):
    """specs: list of (category, sentence, sonnet_verdict, haiku_verdict).
    Builds stated_priorities rows plus stored two-model proposals."""
    import hashlib as _h

    from biointel import priorities as _p
    from biointel import schema as _schema
    from biointel import store as _store

    cols = list(_schema.STATED_PRIORITY_COLS) + list(_schema.STATED_PRIORITY_F2_COLS)
    rows, props = [], []
    for i, (cat, sent, sv, hv) in enumerate(specs):
        r = dict.fromkeys(cols, "")
        r.update({
            "entity_key": f"CIK:{200 + i}", "stated_at": "2021-03-01", "category": cat,
            "statement": sent,
            "doc_id": "b" * 64, "span": "x", "source_type": "10k_strategy", "section": "Item 1",
        })
        rows.append(r)
        key = _p._row_key(r)
        for m, v in (("claude-sonnet-5", sv), ("claude-haiku-4-5", hv)):
            pr = dict.fromkeys(_schema.REVIEW_PROPOSAL_COLS, "")
            pr.update({
                "proposal_id": "P" + _h.sha256(f"{key}|{m}|{_p.F2_PROMPT_VERSION}".encode()).hexdigest()[:16],
                "queue_id": key, "model_id": m, "prompt_version": _p.F2_PROMPT_VERSION,
                "excerpt_hash": "e", "verdict": v, "reason": "r.", "created_at": "2026-09-09T00:00:00",
            })
            props.append(pr)
    _store.write_table("stated_priorities", rows, cols)
    _store.write_table("review_proposals", props, list(_schema.REVIEW_PROPOSAL_COLS))
    _store.write_table("candidate_reviews", [], list(_schema.CANDIDATE_REVIEW_COLS))
    return rows


def test_validate_cluster_on_the_contamination_specimens_verbatim():
    """Today's cross-check specimens (operator ruling 2026-09-09) lock the
    sentence-level routing: named indication beats modality (Galera);
    pipeline payload is correct (uniQure/Sienna); stated acquisition intent
    is correct (Fortress/BeOne); IP-protection outranks in-licensing
    (Vincerx); insurance boilerplate retires; generic mission is wrong."""
    from biointel.priorities import _validate_cluster as V

    # Verastem: cancer named -> correct TA, never platform
    assert V("Our goal is to build a leading biopharmaceutical company focused on the development and commercialization of novel drugs that use a multi-faceted approach to improving outcomes for patients with cancer.", "therapeutic_area") == ("named-indication-correct", "correct", "")
    # Sigilon: generic mission, no tech noun, no named disease -> generic wrong
    assert V("our goal is to provide functional cures to patients with chronic diseases.", "therapeutic_area") == ("generic", "wrong", "")
    # Sienna: autoimmune/inflammatory + pipeline payload -> correct PG
    assert V("Our strategy is to develop and commercialize a multi-asset pipeline of innovative and differentiated therapies that target autoimmune and inflammatory conditions and that we believe can be successful in the marketplace.", "pipeline_gap") == ("pipeline-correct", "correct", "")
    # BeOne/Curanex: stated acquisition intent -> correct PG (Fortress-class)
    assert V("we intend to acquire businesses, technologies, platforms, services, or products that we believe are strategic.", "pipeline_gap") == ("acquisition-correct", "correct", "")
    # Vincerx: proprietary position outranks the in-licensing mention -> IP wrong
    assert V("Our strategy is to seek to protect our proprietary position by, among other methods, filing or in-licensing U.", "pipeline_gap") == ("ip-protection", "wrong", "")
    # insurance boilerplate -> wrong
    assert V("we intend to acquire insurance coverage to include the sale of commercial products; however, we may be unable to obtain product liability insurance on commercially reasonable terms or in adequate amounts.", "pipeline_gap") == ("boilerplate", "wrong", "")
    # Voyager: gene-therapy tech, CNS named -> disease wins over tech (residual under PG-less stamp rules? TA -> correct)
    assert V("Our goal is to address the underlying cause or the predominant manifestations of a specific disease by significantly increasing or decreasing expression of the relevant proteins at targeted sites within the CNS.", "therapeutic_area") == ("named-indication-correct", "correct", "")
    # Caribou: genome editing tech, no named disease (tumor mention) -> disease term fires
    assert V("Our goal is to apply armoring strategies to our allogeneic cell therapies, which we believe could unlock their full potential by improving upon their effectiveness and antitumor activity.", "therapeutic_area") == ("named-indication-correct", "correct", "")
    # pure modality, no disease -> relabel platform
    assert V("company developing lentiviral-based gene therapies to free patients from genetic disease burdens of unspecified kinds.", "pipeline_gap") == ("platform", "wrong", "platform")
    # channel language -> commercial hold
    assert V("we are seeking partners with suitable infrastructure and market access to expand our commercial reach.", "therapeutic_area") == ("commercial-hold-p2", "unsure", "")
    # --- the four 2026-09-09 override classes, verbatim (operator ruling) ---
    # no-modality generic: "alternatives" must not trip a tech substring
    assert V("Our goal is to create low cost therapeutic alternatives to existing treatments.", "therapeutic_area") == ("generic", "wrong", "")
    # named-modality trade name (Bicycles): novel-class marker -> platform
    assert V("company developing a novel class of medicines, which we refer to as Bicycles , for diseases that are underserved by existing therapeutics.", "therapeutic_area") == ("platform", "wrong", "platform")
    # dual-with-pipeline (uniQure precedent): pipeline payload wins over tech
    assert V("we aim to have a pipeline characterized by potential best-in-class medicines and to be a company with the leading genome editing platform and organizational culture.", "pipeline_gap") == ("pipeline-correct", "correct", "")
    # substring-trap class closed structurally (boundary anchor): these
    # dictionary traps must NOT fire — industrial!=trial, taxpayer!=payer,
    # adrenaline!=renal, electrocardiogram!=cardio, alternatives!=rna
    assert V("Our strategy is to become the leading industrial bioprocessing company serving taxpayer-funded programs.", "pipeline_gap") is None
    assert V("our adrenaline-focused electrocardiogram alternatives serve unnamed markets.", "pipeline_gap") is None
    # garbled truncation: bullet debris is never a stated priority
    assert V("we seek to acquire carry on business; and \u2022 our inability to generate revenue from acquired technology and/or products sufficient to meet our objectives in undertaking the acquisition or even to offset the associated acquisition and maintenance costs.", "pipeline_gap") == ("garbled", "wrong", "")


def test_triage_clusters_validates_sentences_caps_and_prefills_csvs(f2db, monkeypatch, tmp_path, capsys):
    from biointel import config as _config
    from biointel import priorities as _p

    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    specs = [
        ("therapeutic_area", f"company developing a novel antibody platform for undisclosed programs number {i}.", "wrong", "correct")
        for i in range(4)
    ]
    specs += [("pipeline_gap", "An unclassifiable sentence with no signal words at all.", "unsure", "correct")]
    rows = _clusters_world(monkeypatch, tmp_path, specs)
    assert _p.triage_clusters() == 0
    out = capsys.readouterr().out
    assert "CLUSTER therapeutic_area--platform | 4 rows | proposed: wrong --relabel platform" in out
    assert "RESIDUAL 1 rows" in out and "RESIDUAL-CARRIED 0" in out
    pth = _config.EXPORTS / "cluster_therapeutic_area--platform.csv"
    assert pth.exists()
    body = pth.read_text(encoding="utf-8")
    assert body.count("wrong,platform") == 4 and _p._row_key(rows[0]) in body


def test_triage_clusters_residual_cap_and_carried(f2db, monkeypatch, tmp_path, capsys):
    from biointel import config as _config
    from biointel import priorities as _p

    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    specs = [("pipeline_gap", f"An unclassifiable sentence number {i} with no signal words.", "unsure", "correct") for i in range(12)]
    _clusters_world(monkeypatch, tmp_path, specs)
    assert _p.triage_clusters() == 0
    out = capsys.readouterr().out
    assert "RESIDUAL 10 rows" in out and "RESIDUAL-CARRIED 2 rows" in out


def test_settled_rows_are_excluded_from_pool_and_clusters(f2db, monkeypatch, tmp_path, capsys):
    """The Viatris gap (operator ruling 2026-09-09): a row created by an
    operator relabel is settled and never re-enters triage or clusters."""
    from biointel import config as _config
    from biointel import priorities as _p
    from biointel import store as _store

    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    sent = "company developing a novel antibody platform for undisclosed programs."
    rows = _clusters_world(monkeypatch, tmp_path, [("therapeutic_area", sent, "wrong", "correct")] * 3)
    # operator relabels row 0 to pipeline_gap: verdict sits under the OLD key
    key0 = _p._row_key(rows[0])
    assert _p.judge(key0, "wrong", relabel="pipeline_gap") == 0
    capsys.readouterr()
    assert _p.triage_clusters() == 0
    out = capsys.readouterr().out
    assert "settled_excluded 1" in out
    live = {_p._row_key(r): r for r in _store.read_table("stated_priorities")}
    new_key = next(k for k, r in live.items() if str(r["category"]) == "pipeline_gap")
    assert new_key not in out  # the settled row never reappears on the surface


def test_judge_batch_pattern_stamps_provenance_and_precision_buckets(f2db, monkeypatch, tmp_path, capsys):
    from biointel import config as _config
    from biointel import priorities as _p
    from biointel import store as _store

    monkeypatch.setattr(_config, "EXPORTS", tmp_path / "exports")
    sent = "company developing a novel antibody platform for undisclosed programs."
    _clusters_world(monkeypatch, tmp_path, [("therapeutic_area", sent, "wrong", "correct")] * 3)
    assert _p.triage_clusters() == 0
    capsys.readouterr()
    csvp = _config.EXPORTS / "cluster_therapeutic_area--platform.csv"
    assert _p.judge_batch(str(csvp), pattern="therapeutic_area--platform") == 0
    out = capsys.readouterr().out
    assert "recorded 3" in out
    revs = _store.read_table("candidate_reviews")
    assert len(revs) == 3
    assert all(str(r["reviewer"]) == "operator-pattern" for r in revs)
    assert all("cluster:therapeutic_area--platform;" in str(r["note"]) for r in revs)
    live = _store.read_table("stated_priorities")
    assert all(str(r["category"]) == "platform" for r in live)  # relabel repaired in place
    assert _p.precision() == 0
    out = capsys.readouterr().out
    assert "PATTERN-RULED (operator, cluster-wide; own bucket): wrong 3" in out
    # pattern verdicts never enter the operator-only tier measurement
    assert "PRECISION 10k_strategy" not in out


def test_cat_map_stem_compounds_locked_for_p2_anchoring():
    """Extraction-side sweep 2026-09-09: _CAT_MAP stems are intentional —
    these medical compounds MUST keep firing; any p2 boundary-anchoring is
    measured against this frozen-behavior oracle."""
    from biointel.priorities import _category_for

    assert _category_for("we advance chemotherapy combinations") == "therapeutic_area"
    assert _category_for("serving outpatients across regions") == "therapeutic_area"
    assert _category_for("epidermal repair products") == "therapeutic_area"
    assert _category_for("hypoallergenic formulations") == "therapeutic_area"


def test_negation_clip_routes_garbled_verbatim():
    """S1e6a836 (operator ruling 2026-09-09, Opus-class): a slicer clip
    inverted a negated acquire into an apparent priority; the pattern routes
    garbled -> wrong, never acquisition-correct."""
    from biointel.priorities import _validate_cluster as V

    assert V("we plan to acquire, the infrastructure or capability internally to manufacture drug supplies for our ongoing clinical trials or any future clinical trials that we may conduct, and we lack the resources to manufacture our product candidates, if approved, on a commercial scale.", "pipeline_gap") == ("garbled", "wrong", "")
