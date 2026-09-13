# tests\unit\test_seg.py
"""SEG-v1 locking tests.

SEG-v1 is a candidate implementation until the R3-0b census closes; these tests
exist so that any change to boundary rules, the coordinate contract, or the
identity serialization fails loudly rather than silently shifting every segment
id, both before and after that closeout.
"""

from __future__ import annotations

import hashlib

import pytest

from biointel import seg

CAP = "cap0123456789abcdef"

# Pathology fixture. Shapes are those the corpus actually produces: abbreviated
# company forms, U.S.-style initialisms, decimals, personal initials, bullet
# debris, table fragments, fused headings, doubled whitespace, parentheticals,
# quotations, and a very long clause.
RAW_HTML = (
    "<html><p>Item 1. Business</p>"
    "<p>Our strategy is to grow. We seek to acquire assets that complement our existing "
    "business and to expand into new therapeutic areas.</p>"
    "<ul><li>expand commercial reach</li><li>enter new geographies</li></ul>"
    "<p>Acme Inc. was founded in 1998. The U.S. market grew 3.5% last year.</p>"
    "<p>" + ("padding sentence about ordinary operations. " * 20) + "</p>"
    "<p>Item 1A. Risk Factors</p><p>risk text</p></html>"
)

PATHOLOGY = (
    "Our strategy is to grow. "
    "We seek to acquire businesses, assets and products that complement our existing business. "
    "Acme Inc. was founded in 1998. "
    "The U.S. market grew 3.5% last year. "
    "J. Smith leads the team. "
    "\u2022 expand commercial reach "
    "\u2022 enter new geographies "
    "\"We intend to expand,\" the CEO said. "
    "Revenue rose (see Item 7). "
    "Product Candidate Phase Indication Status ABC-123 2 oncology ongoing. "
    "Item 1. Business We are a clinical-stage company. "
    "We intend to continue to invest in our platform and to expand our pipeline through "
    "acquisitions, in-licensing and collaborations in areas where we believe our scientific "
    "expertise, our regulatory experience and our commercial infrastructure together give us a "
    "durable advantage over other potential acquirers of the same assets."
)


def _segs(text: str = PATHOLOGY, capture_id: str = CAP):
    return seg.segment_item1(text, capture_id=capture_id, document_id="doc1",
                             entity_key="CIK:1", filing_date="2023-01-01")


# ---- version and contract ----------------------------------------------------
def test_version_is_exactly_seg_v1():
    assert seg.SEG_VERSION == "SEG-v1"
    assert all(s.segment_version == "SEG-v1" for s in _segs())


def test_paragraph_context_is_genuine_and_contains_the_segment():
    body = seg.seg_item1_slice(seg.seg_normalize(RAW_HTML))
    for s in seg.segment_item1(body, capture_id=CAP):
        assert s.paragraph_context_available is True
        assert s.paragraph_start_offset <= s.start_offset
        assert s.end_offset <= s.paragraph_end_offset
        assert body[s.paragraph_start_offset:s.paragraph_end_offset].strip() != ""


def test_paragraph_spans_come_from_blank_line_blocks():
    body = seg.seg_item1_slice(seg.seg_normalize(RAW_HTML))
    blocks = seg.paragraphs(body)
    assert len(blocks) > 1
    for s in seg.segment_item1(body, capture_id=CAP):
        assert (s.paragraph_start_offset, s.paragraph_end_offset) in blocks


def test_seg_retrieval_preserves_structural_blocks():
    doc = seg.seg_normalize(RAW_HTML)
    assert "\n\n" in doc
    assert "  " not in doc


def test_source_line_wrapping_is_not_a_structural_boundary():
    """Raw newlines in SEC HTML are source line wrapping, not structure. A
    sentence wrapped across source lines must stay one segment."""
    wrapped = ("<html><p>Our strategy is to grow\nand to acquire assets\n"
               "that complement the business.</p><p>Second block here.</p></html>")
    doc = seg.seg_normalize(wrapped)
    assert doc == "Our strategy is to grow and to acquire assets that complement the business.\n\nSecond block here."
    segs = seg.segment_item1(doc, capture_id=CAP)
    assert [s.verbatim_text for s in segs] == [
        "Our strategy is to grow and to acquire assets that complement the business.",
        "Second block here.",
    ]


def test_a_plain_text_capture_keeps_blank_line_paragraphs_and_collapses_wraps():
    """With no markup, a blank line is the only paragraph signal available, so
    it survives; a single line wrap is still wrapping and is collapsed."""
    doc = seg.seg_normalize("First sentence.\nSecond sentence.\n\nThird sentence in a new paragraph.")
    assert doc == "First sentence. Second sentence.\n\nThird sentence in a new paragraph."
    assert seg.paragraphs(doc) == [(0, 32), (34, 68)]


# ---- real filing specimens (rule 4.20: pinned against captures, not inventions)
# Verbatim excerpts of the p2-normalized 10-K text already held in
# tests/unit/test_priorities.py, which came from the 2026-09-07 probe bundle:
# Akorn 10-K 2015 (capture 03fdcee3d8f8) and BMY 10-K 2019 (62ab199b8ecc).
AKORN_REAL = (
    "Mergers and Acquisitions. We actively seek to expand and enhance our business through "
    "strategic acquisitions. We seek to acquire businesses assets and products that we believe "
    "complement our existing business and provide us opportunities for growth and synergies. "
    "See Item 1A \u2013 \u201cRisk Factors\u201d for a description of risks that accompany our acquisition "
    "strategy. Excelvision AG : On July 22, 2014, our Luxembourg subsidiary, Akorn International "
    "S.\u00e0 r.l., entered into a share purchase agreement with Fareva SA, to acquire all of the issued "
    "and outstanding shares of capital stock of Excelvision AG, a Swiss Company for 21.7 million "
    "Swiss Francs, net of certain working capital amounts. Such costs amounted to $29.2 million, "
    "$19.9 million and $15.9 million for the years ended December 31, 2014, 2013 and 2012, "
    "respectively."
)
AKORN_BULLET_DEBRIS = (
    "ucts; and \u2022 Other factors referred to in this Form 10-K and our other Securities and Exchange "
    "Commission filings. See \u201cItem 1A - Risk Factors\u201d. As a result, you should not place undue "
    "reliance on any forward-looking statements."
)
BMY_REAL = (
    "Our four strategic priorities are to drive business performance, continue to further build a "
    "leading franchise in IO, maintain a diversified portfolio both within and outside of IO, and "
    "continue our disciplined approach to capital allocation, including establishing partnerships, "
    "collaborations and in-licensing or acquiring investigational compounds as an essential "
    "component of successfully delivering transformational medicines to patients. We expect that "
    "our planned acquisition of Celgene that we announced in January 2019 will enable us to create "
    "a leading focused specialty biopharmaceutical company."
)
BMY_TABLE_FRAGMENT = (
    "PART I Item 1. Business 1 Acquisitions and Divestitures 1 Products, Intellectual Property and "
    "Product Exclusivity 2 Research and Development 6 Alliances 9 Item 1A. Risk Factors 16"
)


def _real(text: str):
    return seg.segment_item1(text, capture_id=CAP)


# Exact spans measured against this implementation and pinned, so any boundary
# change on real filing text fails loudly instead of drifting.
AKORN_REAL_SPANS = [(0, 25), (26, 109), (110, 263), (264, 360), (361, 683), (684, 821)]
AKORN_BULLET_SPANS = [(0, 9), (10, 113), (114, 143), (144, 227)]
BMY_REAL_SPANS = [(0, 443), (444, 607)]
BMY_TABLE_SPANS = [(0, 14), (15, 163), (164, 179)]


def test_real_specimen_spans_are_pinned_exactly():
    for text, expected in ((AKORN_REAL, AKORN_REAL_SPANS),
                           (AKORN_BULLET_DEBRIS, AKORN_BULLET_SPANS),
                           (BMY_REAL, BMY_REAL_SPANS),
                           (BMY_TABLE_FRAGMENT, BMY_TABLE_SPANS)):
        assert [(s.start_offset, s.end_offset) for s in _real(text)] == expected


def test_real_akorn_specimen_keeps_abbreviations_and_decimals_intact():
    texts = [s.verbatim_text for s in _real(AKORN_REAL)]
    assert any(t.startswith("We seek to acquire businesses assets and products") for t in texts)
    assert any("S.\u00e0 r.l., entered into a share purchase agreement" in t for t in texts)
    assert any("$29.2 million, $19.9 million and $15.9 million" in t for t in texts)
    assert not any(t.startswith("2 million") or t.startswith("l., entered") for t in texts)


def test_real_akorn_specimen_offsets_and_coverage():
    segs = _real(AKORN_REAL)
    for s in segs:
        assert AKORN_REAL[s.start_offset:s.end_offset] == s.verbatim_text
    assert seg.coverage_gaps(AKORN_REAL, segs) == []


def test_real_akorn_bullet_debris_is_segmented_and_flagged_consistently():
    segs = _real(AKORN_BULLET_DEBRIS)
    texts = [s.verbatim_text for s in segs]
    assert any(t.startswith("\u2022 Other factors referred to in this Form 10-K") for t in texts)
    assert seg.coverage_gaps(AKORN_BULLET_DEBRIS, segs) == []


def test_real_bmy_specimen_keeps_the_long_strategic_priorities_sentence_whole():
    texts = [s.verbatim_text for s in _real(BMY_REAL)]
    assert any(t.startswith("Our four strategic priorities are to drive business performance")
               and t.endswith("transformational medicines to patients.") for t in texts)


def test_real_bmy_table_fragment_splits_on_item_numbering_without_losing_text():
    segs = _real(BMY_TABLE_FRAGMENT)
    for s in segs:
        assert BMY_TABLE_FRAGMENT[s.start_offset:s.end_offset] == s.verbatim_text
    assert seg.coverage_gaps(BMY_TABLE_FRAGMENT, segs) == []
    assert len(segs) > 1


def test_real_specimens_are_deterministic():
    for text in (AKORN_REAL, AKORN_BULLET_DEBRIS, BMY_REAL, BMY_TABLE_FRAGMENT):
        assert [s.as_dict() for s in _real(text)] == [s.as_dict() for s in _real(text)]


def test_item1_struct_version_is_in_the_slice_id_seed():
    import hashlib
    body = "some structure preserving item one text"
    expected = "I1" + hashlib.sha256(
        f"{seg.ITEM1_STRUCT_VERSION}|{body}".encode()
    ).hexdigest()[:16]
    assert seg.slice_id(body) == expected
    assert seg.ITEM1_STRUCT_VERSION == "ITEM1_STRUCT-v1"


def test_paragraph_containment_fails_closed_rather_than_fabricating_a_span():
    with pytest.raises(seg.ParagraphContainmentError):
        seg._paragraph_of([(0, 5)], 10, 20)


def test_compatibility_invariant_holds_against_the_incumbent_p2_region():
    ok, seg_side, p2_side = seg.compatibility(RAW_HTML)
    assert ok, f"SEG and p2 disagree about Item 1:\nSEG {seg_side[:200]!r}\np2  {p2_side[:200]!r}"


def test_incumbent_p2_path_is_not_modified_by_seg():
    from biointel.efts import normalize_text
    from biointel.priorities import item1_slice
    assert normalize_text("a   b\n\nc") == "a b c"
    assert item1_slice("no item one here") == ""


def test_neighbour_window_is_additional_and_distinct_from_the_paragraph():
    segs = _segs()
    for i, s in enumerate(segs):
        assert s.neighbor_context_start_offset <= s.start_offset
        assert s.neighbor_context_end_offset >= s.end_offset
        if i == 0:
            assert s.neighbor_context_start_offset == s.start_offset
        if i == len(segs) - 1:
            assert s.neighbor_context_end_offset == s.end_offset


# ---- the offset invariant ----------------------------------------------------
def test_verbatim_text_is_exactly_the_slice_span():
    for s in _segs():
        assert PATHOLOGY[s.start_offset:s.end_offset] == s.verbatim_text


def test_text_hash_matches_the_verbatim_bytes():
    for s in _segs():
        assert s.text_sha256 == hashlib.sha256(s.verbatim_text.encode("utf-8")).hexdigest()


def test_spans_are_ordered_non_overlapping_in_range_and_non_empty():
    segs = _segs()
    prev_end = -1
    for s in segs:
        assert 0 <= s.start_offset < s.end_offset <= len(PATHOLOGY)
        assert s.start_offset >= prev_end
        assert s.verbatim_text.strip() != ""
        prev_end = s.end_offset
    assert [s.sentence_index for s in segs] == list(range(len(segs)))


def test_no_coverage_gaps_every_non_whitespace_character_is_covered():
    segs = _segs()
    assert seg.coverage_gaps(PATHOLOGY, segs) == []


# ---- identity ----------------------------------------------------------------
def test_slice_id_serialization_is_pinned():
    import hashlib
    body = seg.seg_item1_slice(seg.seg_normalize(RAW_HTML))
    assert seg.slice_id(body) == "I1" + hashlib.sha256(
        f"ITEM1_STRUCT-v1|{body}".encode()).hexdigest()[:16]


def test_segment_id_serialization_is_pinned():
    sha = seg.text_sha256("Our strategy is to grow.")
    expected = "SEG" + hashlib.sha256(
        f"SEG-v1|{CAP}|{seg.slice_id(PATHOLOGY)}|0|24|{sha}".encode()
    ).hexdigest()[:16]
    assert _segs()[0].segment_id == expected
    assert _segs()[0].segment_id == seg.segment_id(CAP, seg.slice_id(PATHOLOGY), 0, 24, sha)


def test_ids_are_stable_across_runs():
    assert [s.segment_id for s in _segs()] == [s.segment_id for s in _segs()]


def test_id_changes_when_the_target_span_changes():
    a = seg.segment_id(CAP, "I1abc", 0, 10, "deadbeef")
    assert a != seg.segment_id(CAP, "I1abc", 0, 11, "deadbeef")
    assert a != seg.segment_id(CAP, "I1abc", 1, 10, "deadbeef")
    assert a != seg.segment_id(CAP, "I1xyz", 0, 10, "deadbeef")
    assert a != seg.segment_id("other", "I1abc", 0, 10, "deadbeef")
    assert a != seg.segment_id(CAP, "I1abc", 0, 10, "cafebabe")


def test_context_does_not_affect_identity():
    """The same span in a slice with different neighbours keeps its id when the
    slice and offsets are the same; identity inputs exclude context entirely."""
    sid = seg.slice_id(PATHOLOGY)
    first = _segs()[0]
    assert first.segment_id == seg.segment_id(CAP, sid, first.start_offset, first.end_offset,
                                              first.text_sha256)


def test_slice_id_is_a_content_identity_of_the_structure_preserving_slice():
    assert seg.slice_id("abc") == seg.slice_id("abc")
    assert seg.slice_id("abc") != seg.slice_id("abd")
    assert seg.slice_id(PATHOLOGY).startswith("I1")


def test_determinism_is_record_for_record():
    assert [s.as_dict() for s in _segs()] == [s.as_dict() for s in _segs()]


# ---- boundary pathologies, pinned by exact text -----------------------------
@pytest.mark.parametrize("expected", [
    "Our strategy is to grow.",
    "Acme Inc. was founded in 1998.",
    "The U.S. market grew 3.5% last year.",
    "J. Smith leads the team.",
    "\u2022 expand commercial reach",
    "Revenue rose (see Item 7).",
])
def test_pathology_segments_appear_verbatim(expected):
    assert expected in [s.verbatim_text for s in _segs()]


def test_abbreviations_initials_and_decimals_do_not_split():
    texts = [s.verbatim_text for s in _segs()]
    assert not any(t.startswith("was founded") for t in texts)
    assert not any(t.startswith("market grew") for t in texts)
    assert not any(t.startswith("Smith leads") for t in texts)
    assert not any(t.startswith("5% last year") for t in texts)


def test_a_numbered_heading_splits_from_its_sentence_frozen_behaviour():
    """Pinned observed behaviour, not an aspiration: "Item 1." ends in a
    terminator after a digit and is followed by a capital, so SEG-v1 cuts
    there. The heading becomes its own segment and no source text is lost."""
    texts = [s.verbatim_text for s in _segs()]
    assert "Item 1." in texts
    assert "Business We are a clinical-stage company." in texts


def test_a_very_long_clause_is_one_segment():
    longest = max(_segs(), key=lambda s: len(s.verbatim_text))
    assert longest.verbatim_text.startswith("We intend to continue to invest")
    assert longest.verbatim_text.endswith("the same assets.")


def test_doubled_whitespace_never_enters_a_span_edge():
    text = "First sentence.   Second sentence.  "
    for s in seg.segment_item1(text, capture_id=CAP):
        assert s.verbatim_text == s.verbatim_text.strip()
        assert text[s.start_offset:s.end_offset] == s.verbatim_text


def test_empty_and_whitespace_only_slices_return_nothing():
    assert seg.segment_item1("", capture_id=CAP) == []
    assert seg.segment_item1("   ", capture_id=CAP) == []


# ---- the ratified known limitation, pinned -----------------------------------
def test_unterminated_bullet_merges_with_following_prose_frozen_behaviour():
    """Operator ruling 2026-09-12 (Option A): this merge is SEG-v1 behaviour.
    It is pinned so a later silent 'fix' fails rather than shifting every id."""
    merged = "\u2022 enter new geographies \"We intend to expand,\" the CEO said."
    assert merged in [s.verbatim_text for s in _segs()]


def test_merge_diagnostic_is_a_proxy_and_flags_the_pinned_case():
    flagged = [s for s in _segs() if seg.suspected_unterminated_bullet_merge(s)]
    assert len(flagged) == 1
    assert flagged[0].verbatim_text.startswith("\u2022 enter new geographies")


def test_merge_diagnostic_does_not_flag_a_clean_bullet():
    clean = [s for s in _segs() if s.verbatim_text == "\u2022 expand commercial reach"]
    assert clean and not seg.suspected_unterminated_bullet_merge(clean[0])


def test_diagnostic_never_alters_boundaries_or_identity():
    before = [(s.segment_id, s.start_offset, s.end_offset) for s in _segs()]
    for s in _segs():
        seg.suspected_unterminated_bullet_merge(s)
    after = [(s.segment_id, s.start_offset, s.end_offset) for s in _segs()]
    assert before == after


# ---- independence from p2 ----------------------------------------------------
def test_seg_imports_no_biointel_code_at_module_level():
    """SEG-v1 must enumerate the full Item 1 space independently of candidate
    selection. Module-level imports of biointel code are forbidden, so nothing
    in the segmentation path can reach p2 selection. The only package imports
    are inside `compatibility()`, which exists precisely to compare the two
    regions and is never called by segmentation."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(seg.__file__).read_text(encoding="utf-8"))
    module_level = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            module_level.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_level.add(node.module or "")
    assert not any(m.startswith("biointel") for m in module_level), sorted(module_level)


def test_segmentation_never_calls_p2_selection():
    """The segmentation entry points must not touch p2 at all; only the
    compatibility helper may, and only to compare regions."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(seg.__file__).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name != "compatibility":
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    name = getattr(sub, "module", "") or ""
                    names = [a.name for a in getattr(sub, "names", [])]
                    assert not name.startswith("biointel"), f"{node.name} imports {name}"
                    assert not any(n.startswith("biointel") for n in names), node.name


# ---- compatibility comparison transform (defect of record 2026-09-12) --------
# `compatibility()` used to run the incumbent normalizer over the SEG slice a
# SECOND time. By that point `seg_normalize` has already stripped tags and run
# `html.unescape`, so an entity-encoded `&lt; 40%` in the filing has become a
# literal `< 40%`, and the incumbent's generic `<[^>]+>` consumed it along with
# every character up to the next `>` in plain evidence text. The SEG substrate
# never lost the text: the checker did. Measured on the three captures of
# record, the deletions were 3,441, 871 and 1,758 characters.
#
# ENTITY ENCODING AND A DOWNSTREAM TAG ARE BOTH REQUIRED to reproduce it: with
# a literal `<` in the source the operator is consumed on the FIRST pass by both
# sides alike, and with no later `>` the pattern cannot match at all.

COMPARISON_HTML = (
    "<html><p>Item 1. Business</p>"
    "<p>Our strategy is to grow. Effects are most favorable in patients with low left "
    "ventricular ejection fraction (LVEF) (&lt; 40%); and we see an opportunity to "
    "initiate therapy pre-operatively with a <b>50% risk reduction</b> in mortality.</p>"
    "<p>The trial enrolled PD-L1&gt;1% and &lt;1% patient populations. The safety profile "
    "was <i>consistent</i> with prior studies.</p>"
    # The incumbent slicer refuses a region under 500 characters, so the fixture
    # carries the same ordinary padding the pathology fixture uses.
    "<p>" + ("padding sentence about ordinary operations. " * 20) + "</p>"
    "<p>Item 1A. Risk Factors</p><p>risk text</p></html>"
)


def test_the_seg_substrate_carries_the_operators_before_any_comparison():
    """The substrate is not where the loss was; pin that first."""
    body = seg.seg_item1_slice(seg.seg_normalize(COMPARISON_HTML))
    assert "(LVEF) (< 40%); and we see an opportunity to initiate therapy" in body
    assert "PD-L1>1% and <1% patient populations." in body


def test_compatibility_agrees_when_the_region_carries_comparison_operators():
    agree, seg_side, p2_side = seg.compatibility(COMPARISON_HTML)
    assert agree, f"seg_side={seg_side!r}\np2_side={p2_side!r}"
    assert "< 40%" in seg_side and "< 40%" in p2_side
    assert "<1% patient populations." in seg_side


def test_the_old_double_normalization_is_what_deleted_the_evidence():
    """Mechanism pin, not a behaviour requirement: re-running the incumbent
    normalizer over an already-normalized slice still destroys it, which is why
    `compatibility` must not do that."""
    from biointel.efts import normalize_text as _p2_norm

    body = seg.seg_item1_slice(seg.seg_normalize(COMPARISON_HTML))
    twice = _p2_norm(body)
    assert "< 40%" in body
    assert "< 40%" not in twice
    assert "opportunity to initiate therapy" not in twice
    assert len(twice) < len(body)


def test_compare_norm_is_idempotent():
    body = seg.seg_item1_slice(seg.seg_normalize(COMPARISON_HTML))
    once = seg._compare_norm(body)
    assert seg._compare_norm(once) == once


def test_compare_norm_neither_strips_tags_nor_unescapes():
    """It flattens whitespace and folds three characters. Nothing else."""
    assert seg._compare_norm("a <b> c") == "a <b> c"
    assert seg._compare_norm("&lt; 40%") == "&lt; 40%"
    assert seg._compare_norm("&amp; x") == "&amp; x"
    assert seg._compare_norm("a\u200bb\u00a0c\u2011d") == "a b c-d"
    assert seg._compare_norm("  a \n\n b  ") == "a b"
