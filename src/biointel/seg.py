# src\biointel\seg.py
"""SEG-v1: the frozen sentence coordinate system over a 10-K Item 1 slice.

INPUT COORDINATE CONTRACT (frozen with the version, not merely documented):

    SEG-v1 operates on a STRUCTURE-PRESERVING Item 1 slice produced by this
    module's own retrieval path, `seg_item1_slice(seg_normalize(capture_text))`.
    `seg_normalize` canonicalizes horizontal whitespace while PRESERVING
    newlines and blank lines, so paragraph structure survives into the
    substrate. Offsets and verbatim spans are relative to that exact
    structure-preserving Item 1 string, NOT to SEC source bytes and NOT to the
    p2 normalized slice.

The incumbent p2 path is untouched: `efts.normalize_text` and
`priorities.item1_slice` are neither called nor modified here, so p2 extraction
semantics cannot shift because of SEG-v1. The two paths are related by a
COMPATIBILITY INVARIANT, tested on fixtures and measured across the corpus by
the census:

    efts.normalize_text(seg_item1_slice(seg_normalize(capture)))
        == priorities.item1_slice(efts.normalize_text(capture))

Mismatches are reported, never absorbed: they mean SEG-v1 and p2 disagree about
where Item 1 begins or ends for that document.

Paragraph context is genuine at this version: `paragraph_start_offset` and
`paragraph_end_offset` bound the blank-line-delimited block containing the
segment, and `paragraph_context_available` is True. The previous-to-next
neighbour window is retained as an ADDITIONAL field under its own name; it is
not a paragraph and is never presented as one.

Identity: `segment_id` depends only on the identity of the target evidence
span. Context fields (sentence index, neighbours, neighbour window) never
affect it.

SEG-v1 is a CANDIDATE implementation until the R3-0b census closes; nothing in
this module is frozen before that. It is independent of p2 candidate selection. It does not use
`_capture_sentence`, `_SENTENCE_BREAK_RX`, or the R3 candidate index: it
enumerates every sentence of the slice, including sentences p2 has never seen.

KNOWN FROZEN LIMITATION (ratified by the operator 2026-09-12, Option A): an
unterminated bullet followed by ordinary prose may remain in the same SEG-v1
segment unless another explicit boundary signal is present. This behaviour is
deterministic and frozen in SEG-v1. It is not corrected by heuristic here,
because a rule keyed on opening quotes or capitalised clauses would split
legitimate mid-sentence quotations and capitalised names elsewhere. Its
real-corpus prevalence is measured by the census as a clearly labelled
diagnostic proxy, and SEG-v2 is considered only if that prevalence plus manual
examples justify it.

STATUS: SEG-v1 candidate implementation. It becomes frozen on successful R3-0b
census closeout; until then R3-0b is OPEN. Once frozen, any material change to
the boundary rules, the coordinate contract, or the identity serialization is
SEG-v2, never an edit here.
"""

from __future__ import annotations

import hashlib
import html as _html
import re
from dataclasses import asdict, dataclass

SEG_VERSION = "SEG-v1"
ITEM1_STRUCT_VERSION = "ITEM1_STRUCT-v1"  # the SEG-only retrieval representation, versioned separately

# ---------------------------------------------------------------- SEG-only retrieval (candidate)
# Deliberately parallel to efts.normalize_text, with ONE difference: horizontal
# whitespace is canonicalized but newlines and blank lines survive, so the
# paragraph structure SEG-v1 needs is still present. The incumbent function is
# not called, imported, or modified.
_BLOCK_TAG_RX = re.compile(
    r"</?\s*(p|div|br|tr|li|table|h[1-6]|section|article|ul|ol|blockquote)\b[^>]*>",
    re.IGNORECASE,
)
# A private sentinel stands in for a STRUCTURAL block boundary while ordinary
# raw whitespace, including source line wrapping, is collapsed away. Only the
# sentinel becomes a newline afterwards, so a sentence wrapped across two lines
# of the source file stays one segment.
_BLOCK_MARK = "\x00BLOCK\x00"   # one structural line break
_PARA_MARK = "\x00PARA\x00"     # a paragraph break (blank line)


def seg_normalize(raw: str) -> str:
    """Structure-preserving normalization for the SEG-v1 substrate.

    Two substrates, one output shape:

    HTML captures: block tags are the structure and raw newlines are source
    line wrapping, so block tags are marked FIRST, every raw whitespace run is
    then collapsed to one space, and only the marks become line breaks. A
    sentence wrapped across source lines stays one segment.

    Plain-text captures (no structural markup at all): a BLANK LINE is the only
    paragraph signal available, so blank lines are marked as structure and
    preserved, while single line wraps are collapsed as wrapping. Without this,
    a text capture would report one enormous block and `paragraph_context_available`
    would claim a genuine paragraph where real structure had been discarded.
    """
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    if _BLOCK_TAG_RX.search(t):
        # HTML capture: block tags are the structure, raw newlines are wrapping.
        t = _BLOCK_TAG_RX.sub(_BLOCK_MARK, t)
    else:
        # Plain-text capture: there is no markup, so a BLANK LINE is the only
        # paragraph signal available and it is preserved, while a single line
        # wrap is still treated as wrapping and collapsed.
        t = re.sub(r"\n[^\S\n]*\n\s*", _PARA_MARK, t)
    t = re.sub(r"<[^>]+>", " ", t)          # every other tag becomes a space
    t = _html.unescape(t)
    t = t.replace("\u200b", " ").replace("\u00a0", " ").replace("\u2011", "-")
    t = re.sub(r"\s+", " ", t)               # ALL raw whitespace collapses, newlines included
    t = t.replace(_PARA_MARK, "\n\n")        # blank-line structure survives
    t = t.replace(_BLOCK_MARK, "\n")         # only structural marks become breaks
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{2,}", "\n\n", t)         # consecutive block boundaries -> one blank line
    return t.strip()


def seg_item1_slice(text: str) -> str:
    """The Item 1 region of a structure-preserving document.

    Boundary logic mirrors the incumbent slicer exactly (last Item 1A Risk
    Factors match as the end, last table-of-contents Item 1 signature as the
    start, same refusal thresholds) so that the two paths agree on WHERE Item 1
    is while differing only in whether structure survives. Refuses rather than
    guesses, like the incumbent.
    """
    ends = [m.start() for m in _ITEM1A_RF.finditer(text)]
    if not ends:
        return ""
    end = ends[-1]
    start = 0
    for m in re.finditer(r"Item\s*1\b", text[:end], re.IGNORECASE):
        if re.search(r"Item\s*\d", text[m.end(): m.end() + 90], re.IGNORECASE):
            start = m.end()
    body = text[start:end]
    if len(body) < 500 or body.count("us-gaap:") + body.count("xbrli:") > 8:
        return ""
    return body


_ITEM1A_RF = re.compile(r"Item\s*1A\b[^A-Za-z]{0,12}Risk\s+Factors", re.IGNORECASE)

# ---------------------------------------------------------------- boundary rules (candidate)
# A boundary is a terminator (. ? !), optionally followed by closing quotes or
# brackets, then at least one space, then an opener: an uppercase letter, a
# digit, an opening quote or bracket, or a bullet glyph.
_TERMINATOR = r"[.?!]"
_CLOSERS = r"[\"'\u2019\u201d)\]]*"
_OPENER = r"[A-Z0-9\"'\u2018\u201c(\[\u2022\u00b7\u25cf\u2013\u2014]"
_BOUNDARY_RX = re.compile(rf"({_TERMINATOR}{_CLOSERS})\s+(?={_OPENER})")

# A bullet glyph mid-string also opens a new segment even without a terminator,
# because SEC text extraction frequently renders list items without punctuation.
_BULLET_RX = re.compile(r"\s+(?=[\u2022\u00b7\u25cf])")

# In the structure-preserving substrate a line break is itself a boundary
# signal: a block boundary cannot sit inside a sentence.
_LINEBREAK_RX = re.compile(r"\n+")

# Guards: a terminator inside one of these is not a boundary.
_ABBREVIATIONS = (
    "inc", "corp", "co", "ltd", "llc", "lp", "plc", "sa", "nv", "ag", "gmbh",
    "no", "nos", "vs", "etc", "al", "approx", "est", "fig", "figs", "ref",
    "dr", "mr", "mrs", "ms", "prof", "jr", "sr", "st", "mt",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sept", "sep", "oct", "nov", "dec",
    "u.s", "u.k", "e.g", "i.e", "ph.d", "m.d", "b.s", "m.s", "d.c", "n.a",
    "fda", "sec",
)
_ABBREV_RX = re.compile(
    r"(?:^|[\s(\[\"'])((?:[A-Za-z]\.)+[A-Za-z]?|[A-Za-z]+)$"
)
# A decimal point sits between digits; a single capital initial is "A."
_DECIMAL_RX = re.compile(r"\d$")
_INITIAL_RX = re.compile(r"(?:^|\s)[A-Z]$")

MIN_SEGMENT_CHARS = 1  # a segment is any non-empty non-whitespace span


@dataclass(frozen=True)
class Segment:
    segment_id: str
    segment_version: str
    capture_id: str
    document_id: str
    item1_slice_id: str
    entity_key: str
    filing_date: str
    sentence_index: int
    verbatim_text: str
    text_sha256: str
    start_offset: int
    end_offset: int
    previous_segment_id: str | None
    next_segment_id: str | None
    neighbor_context_start_offset: int
    neighbor_context_end_offset: int
    paragraph_start_offset: int
    paragraph_end_offset: int
    paragraph_context_available: bool

    def as_dict(self) -> dict:
        return asdict(self)


def compatibility(raw_capture_text: str) -> tuple[bool, str, str]:
    """Compare the SEG-v1 Item 1 region against the incumbent p2 region.

    Returns (agree, seg_side, p2_side). The two sides are compared after the
    SEG slice is put through the incumbent normalizer, and after stripping
    leading and trailing whitespace on both, because `item1_slice` does not
    strip its own slice edges while `seg_normalize` does. Nothing else is
    normalized away: a difference anywhere inside the region is a real
    disagreement about where Item 1 begins or ends, and is reported.

    Imported lazily so this module still imports nothing from the package at
    definition time and cannot inherit p2 candidate semantics.
    """
    from biointel.efts import normalize_text as _p2_norm
    from biointel.priorities import item1_slice as _p2_slice

    seg_side = _p2_norm(seg_item1_slice(seg_normalize(raw_capture_text))).strip()
    p2_side = _p2_slice(_p2_norm(raw_capture_text)).strip()
    return seg_side == p2_side, seg_side, p2_side


def slice_id(item1_text: str) -> str:
    """Content identity of the exact structure-preserving Item 1 slice.

    This is a CONTENT identity of the slice string under a named retrieval
    version, not a provenance identity in the sense that `capture_id` is: two
    captures whose structure-preserving Item 1 slices are byte-identical share
    this id by design. The retrieval version is part of the seed, so a future
    ITEM1_STRUCT-v2 cannot silently reuse v1 slice ids.

    Serialization, pinned by test:
        I1 + sha256("ITEM1_STRUCT-v1|<exact slice text>")[:16]
    """
    seed = f"{ITEM1_STRUCT_VERSION}|{item1_text}"
    return "I1" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def text_sha256(text: str) -> str:
    """SHA-256 of the exact verbatim span, UTF-8 encoded."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def segment_id(capture_id: str, item1_slice_id: str, start: int, end: int, sha: str) -> str:
    """Canonical identity of a target evidence span. Context never enters it.

    Serialization, frozen and pinned by test:
        SEG + sha256("SEG-v1|<capture_id>|<item1_slice_id>|<start>|<end>|<sha>")[:16]
    pinned by test and following the repository convention used by library._ref_id and
    priorities._skey_of.
    """
    seed = f"{SEG_VERSION}|{capture_id}|{item1_slice_id}|{start}|{end}|{sha}"
    return "SEG" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _is_guarded(text: str, term_pos: int) -> bool:
    """True when the terminator at `term_pos` is an abbreviation, initial or
    decimal point rather than a sentence end."""
    if text[term_pos] != ".":
        return False
    before = text[:term_pos]
    if _DECIMAL_RX.search(before) and term_pos + 1 < len(text) and text[term_pos + 1].isdigit():
        return True
    if _INITIAL_RX.search(before):
        return True
    m = _ABBREV_RX.search(before)
    if m and m.group(1).lower().rstrip(".") in _ABBREVIATIONS:
        return True
    return False


def boundaries(item1_text: str) -> list[int]:
    """SEG-v1 split points: offsets at which a new segment begins. Candidate
    until the R3-0b census closes, frozen thereafter."""
    cuts: set[int] = set()
    for m in _BOUNDARY_RX.finditer(item1_text):
        term_pos = m.start(1)
        if _is_guarded(item1_text, term_pos):
            continue
        cuts.add(m.end())
    for m in _BULLET_RX.finditer(item1_text):
        cuts.add(m.end())
    for m in _LINEBREAK_RX.finditer(item1_text):
        cuts.add(m.end())
    return sorted(cuts)


def paragraphs(item1_text: str) -> list[tuple[int, int]]:
    """Blank-line-delimited blocks of the structure-preserving slice, as
    half-open spans, trimmed of surrounding whitespace. Every non-whitespace
    character of the slice lies in exactly one block."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for chunk in re.split(r"\n\s*\n", item1_text):
        start = item1_text.find(chunk, pos) if chunk else pos
        if chunk.strip():
            s, e = start, start + len(chunk)
            while s < e and item1_text[s].isspace():
                s += 1
            while e > s and item1_text[e - 1].isspace():
                e -= 1
            spans.append((s, e))
        pos = start + len(chunk)
    return spans


class ParagraphContainmentError(AssertionError):
    """No genuine block contains a segment. Fail closed: a fabricated span
    labelled 'paragraph' would be worse than a loud failure."""


def _paragraph_of(para_spans: list[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
    """The genuine block containing the segment, or an error.

    A segment can never straddle a block boundary, because boundaries are
    newlines, newlines are whitespace, and spans are trimmed of whitespace. If
    containment ever fails, the substrate and the segmenter disagree and that
    must surface, never be papered over with an invented span.
    """
    for ps, pe in para_spans:
        if ps <= start and end <= pe:
            return ps, pe
    raise ParagraphContainmentError(
        f"no block contains segment [{start},{end}); blocks={para_spans[:5]}..."
    )


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink a span to exclude leading and trailing whitespace by moving the
    OFFSETS, never by rewriting the text; the verbatim invariant depends on it."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def segment_item1(
    item1_text: str,
    *,
    capture_id: str,
    document_id: str = "",
    entity_key: str = "",
    filing_date: str = "",
) -> list[Segment]:
    """Every SEG-v1 segment of one structure-preserving Item 1 slice, in order.

    Deterministic: the same slice and capture always produce the same records.
    Writes nothing; returns in-memory records only.
    """
    if not item1_text:
        return []
    sid = slice_id(item1_text)
    para_spans = paragraphs(item1_text)
    cuts = [0, *boundaries(item1_text), len(item1_text)]

    spans: list[tuple[int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        s, e = _trim_span(item1_text, a, b)
        if e - s >= MIN_SEGMENT_CHARS:
            spans.append((s, e))

    ids: list[str] = []
    shas: list[str] = []
    for s, e in spans:
        txt = item1_text[s:e]
        sha = text_sha256(txt)
        shas.append(sha)
        ids.append(segment_id(capture_id, sid, s, e, sha))

    out: list[Segment] = []
    for i, (s, e) in enumerate(spans):
        prev_id = ids[i - 1] if i > 0 else None
        next_id = ids[i + 1] if i + 1 < len(spans) else None
        ctx_start = spans[i - 1][0] if i > 0 else s
        ctx_end = spans[i + 1][1] if i + 1 < len(spans) else e
        p_start, p_end = _paragraph_of(para_spans, s, e)
        out.append(Segment(
            segment_id=ids[i],
            segment_version=SEG_VERSION,
            capture_id=capture_id,
            document_id=document_id,
            item1_slice_id=sid,
            entity_key=entity_key,
            filing_date=filing_date,
            sentence_index=i,
            verbatim_text=item1_text[s:e],
            text_sha256=shas[i],
            start_offset=s,
            end_offset=e,
            previous_segment_id=prev_id,
            next_segment_id=next_id,
            neighbor_context_start_offset=ctx_start,
            neighbor_context_end_offset=ctx_end,
            paragraph_start_offset=p_start,
            paragraph_end_offset=p_end,
            paragraph_context_available=True,
        ))
    return out


# ---------------------------------------------------------------- diagnostics
# These never affect boundaries or identity. They exist so the known frozen
# limitation above can be quantified instead of merely asserted.
_BULLET_START_RX = re.compile(r"^[\u2022\u00b7\u25cf]")
_MERGE_HINT_RX = re.compile(r"[\u2022\u00b7\u25cf][^.?!]{3,}\s[\"'\u201c\u2018A-Z][^.?!]*[.?!]")


def suspected_unterminated_bullet_merge(segment: "Segment") -> bool:
    """HEURISTIC PROXY, not a ground-truth error count.

    True when a segment begins with a bullet marker and also contains a later
    clause that terminates, which is the shape an unterminated bullet takes
    when it absorbs the following sentence. Without gold boundary labels this
    cannot distinguish a genuine merge from a bullet item that legitimately
    contains a full sentence, so every figure derived from it must be reported
    as a proxy.
    """
    txt = segment.verbatim_text
    if not _BULLET_START_RX.match(txt):
        return False
    return bool(_MERGE_HINT_RX.search(txt))


def coverage_gaps(item1_text: str, segments: list[Segment]) -> list[tuple[int, int, str]]:
    """Spans of the slice that belong to no segment and are not whitespace.

    SEG-v1 claims to enumerate the full Item 1 evidence space; this function is
    how that claim is checked rather than asserted. An empty result means every
    non-whitespace character of the slice sits inside exactly one segment.
    """
    gaps: list[tuple[int, int, str]] = []
    cursor = 0
    for seg in segments:
        if seg.start_offset > cursor:
            chunk = item1_text[cursor:seg.start_offset]
            if chunk.strip():
                gaps.append((cursor, seg.start_offset, chunk))
        cursor = max(cursor, seg.end_offset)
    if cursor < len(item1_text):
        chunk = item1_text[cursor:]
        if chunk.strip():
            gaps.append((cursor, len(item1_text), chunk))
    return gaps
