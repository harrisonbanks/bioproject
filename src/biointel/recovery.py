# src\biointel\recovery.py
"""R3-0c-ii: evidence-first recovery of historical verdicts.

Design of record: docs/20260912_v1_R3_Recovery_Benchmark_and_Learned_Extraction_Design.md.

Recovery hierarchy, in order, never reordered:
  Level 1  contemporaneous direct evidence under data\\exports
  Level 2  surviving exact table mappings (READ ONLY)
  Level 3  pre-suppression frozen extractor replay, on the unresolved remainder only
  Level 4  ambiguous or unresolved; never guessed

Three authorities are kept separate (operator ruling 2026-09-12):
  reviewed-key authority : worksheet `key` column, `JUDGED <key>`, `R2-JUDGED <key>`
  key->sentence authority: worksheet row; a triage/full-surface key header
                           immediately followed by its `VERBATIM:` record;
                           a cluster record whose schema explicitly carries both
  verdict authority      : worksheet operator verdict column, `JUDGED`, `R2-JUDGED`
Proposer and model verdicts inside triage headers are NEVER operator verdicts.
Shape matches that no authority classifies are `unclassified_identifier` and
contribute to no recovery total.

This module never writes a table of record. It reads through the store layer
and writes only to config.EXPORTS.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from biointel import config, store

PARSER_VERSION = "REC-v3"
INDEX_CACHE_VERSION = "IDX-v1"
INDEX_CACHE_NAME = "20260912_v1_r3_candidate_index.json"
RULE_VERSION_REPLAYED = "L3-a3-p2"

# ---------------------------------------------------------------- identifiers
# Shape only. A shape match is never, by itself, a candidate id.
_S_SHAPE = r"S[0-9a-f]{16}"
_R_SHAPE = r"R[0-9a-f]{16}"
_SHAPE_RX = re.compile(rf"(?<![0-9A-Za-z])({_S_SHAPE}|{_R_SHAPE})(?![0-9A-Za-z])")

# Authoritative record forms (capture-first, from the v57a inventory specimens).
# judge():     "JUDGED {key} {verdict}; retired {n} relabeled {n}[ -> {cat}]"
# r2_judge():  "R2-JUDGED {key} {verdict}"
_JUDGED_RX = re.compile(
    rf"^\s*JUDGED\s+({_S_SHAPE})\s+(correct|wrong|unsure)\s*;\s*retired\s+(\d+)\s+relabeled\s+(\d+)"
    r"(?:\s*->\s*([a-z_]+))?\s*$"
)
_R2_JUDGED_RX = re.compile(rf"^\s*R2-JUDGED\s+({_R_SHAPE})\s+(correct|wrong|unsure)\s*$")
# triage / full-surface header:  "<key> | CIK:1792044 2023-02-27 pipeline_gap[ | model: verdict - reason]"
_HEADER_RX = re.compile(
    rf"^\s*({_S_SHAPE}|{_R_SHAPE})\s*\|\s*(\S+)\s+(\d{{4}}-\d{{2}}-\d{{2}})\s+([a-z_]+)\s*(\|.*)?$"
)
_VERBATIM_RX = re.compile(r"^\s*VERBATIM:\s*(.+?)\s*$")

VERDICTS = ("correct", "wrong", "unsure")

# recovery source classes (design document §11)
SRC_WORKSHEET = "worksheet_direct"
SRC_JUDGING = "judging_evidence_direct"
SRC_CLUSTER = "cluster_direct"
SRC_OVERFLOW = "overflow_direct"
SRC_BUNDLE = "bundle_direct"
SRC_TABLE = "table_direct"
SRC_REPLAY = "extractor_replay"
SRC_AMBIGUOUS = "ambiguous"
SRC_UNRESOLVED = "unresolved"

# unresolved reason codes
R_NO_SENTENCE = "no_sentence_evidence"
R_NO_VERDICT = "no_verdict_evidence"
R_CONFLICT_SENTENCE = "conflicting_sentence_evidence"
R_REPLAY_AMBIGUOUS = "replay_multiple_candidates"
R_REPLAY_NO_CAPTURE = "replay_capture_unavailable"
R_REPLAY_NO_MATCH = "replay_no_candidate"
R_RULE_VERSION_MISMATCH = "rule_version_not_replayable"
R_RULE_VERSION_UNKNOWN = "rule_version_unknown"
R_NOT_S_KEY = "not_an_s_key_replay_path"

_SESSION_RX = re.compile(r"_(v\d+[a-z]{0,2}|p2[a-z]|r\d+|F\d+)_", re.IGNORECASE)
_DATE_RX = re.compile(r"(20\d{6})")


# ---------------------------------------------------------------- data model
@dataclass
class EvidenceSource:
    """One contributing artifact. A mapping may have several (ruling 2026-09-12)."""

    filename: str
    sha256: str
    parser: str
    era: str
    session: str
    raw_ref: str  # "lines 41-42"
    raw_lines: list[str]
    role: str  # "sentence" | "verdict" | "sentence+verdict" | "identity"


@dataclass
class Mapping:
    reviewed_key: str = ""
    key_class: str = ""  # "S" | "R"
    sentence: str = ""
    verdict: str = ""
    original_category: str = ""
    resulting_category: str = ""
    resulting_key: str = ""
    entity_key: str = ""
    stated_at: str = ""
    status: str = SRC_UNRESOLVED
    reason: str = ""
    sentence_source_class: str = ""
    verdict_source_class: str = ""
    parser_version: str = PARSER_VERSION
    evidence_sources: list[EvidenceSource] = field(default_factory=list)
    segment_id: str = ""  # filled at R3-0b, when SEG-v1 exists
    era: str = ""
    session: str = ""
    rule_version: str = ""
    replay_detail: dict = field(default_factory=dict)
    replay_order_dependent_tie: bool = False


# ---------------------------------------------------------------- artifacts
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sniff_encoding(raw: bytes) -> str:
    if raw[:2] == b"\xff\xfe":
        return "utf-16"
    if raw[:2] == b"\xfe\xff":
        return "utf-16"
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    head = raw[:4096]
    if head.count(b"\x00") > len(head) // 4:
        return "utf-16-le"
    try:
        raw[:65536].decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def era_session_of(name: str, mtime_iso: str) -> tuple[str, str]:
    """Era is the artifact's own date where the filename carries one, else its
    mtime date. Session is the block/session token where the filename carries
    one, else `unknown` - never folded into a neighbouring group."""
    m = _DATE_RX.search(name)
    era = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else (mtime_iso[:10] or "unknown")
    s = _SESSION_RX.search(name)
    return era, (s.group(1) if s else "unknown")


@dataclass
class Artifact:
    relpath: str
    abspath: str
    size: int
    mtime: str
    sha256: str
    encoding: str
    era: str
    session: str
    text: str


def manifest(root: Path | None = None) -> list[Artifact]:
    """Every artifact considered for recovery, content-hashed (design §12)."""
    base = Path(root or config.EXPORTS)
    out: list[Artifact] = []
    if not base.is_dir():
        return out
    for dirpath, _dirs, files in os.walk(base):
        for fn in sorted(files):
            p = Path(dirpath) / fn
            try:
                size = p.stat().st_size
                mtime = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                raw = p.read_bytes()
            except OSError:
                continue
            enc = sniff_encoding(raw)
            try:
                text = raw.decode(enc, errors="replace")
            except (LookupError, ValueError):
                text = raw.decode("utf-8", errors="replace")
            rel = str(p.relative_to(base))
            era, sess = era_session_of(rel, mtime)
            out.append(Artifact(rel, str(p), size, mtime, _sha256(p), enc, era, sess, text))
    return out


# ---------------------------------------------------------------- parsers
def _src(a: Artifact, parser: str, first: int, last: int, lines: list[str], role: str) -> EvidenceSource:
    return EvidenceSource(
        filename=a.relpath, sha256=a.sha256, parser=parser, era=a.era, session=a.session,
        raw_ref=f"lines {first}-{last}", raw_lines=lines, role=role,
    )


def parse_worksheet_csv(a: Artifact) -> tuple[list[tuple[str, str, EvidenceSource]], list[tuple[str, dict, EvidenceSource]]]:
    """Worksheet CSV: one row carries key, sentence and (when judged) verdict.
    Header of record: key,verdict,ai_reason,company,date,category,sentence,...
    Returns (verdict_records, sentence_records). Refuses any file whose header
    lacks an explicit key column or sentence column."""
    verdicts: list[tuple[str, str, EvidenceSource]] = []
    sentences: list[tuple[str, dict, EvidenceSource]] = []
    if not a.relpath.lower().endswith(".csv"):
        return verdicts, sentences
    rdr = csv.DictReader(io.StringIO(a.text))
    cols = [c.strip() for c in (rdr.fieldnames or [])]
    if "key" not in cols or "sentence" not in cols:
        return verdicts, sentences
    for i, row in enumerate(rdr, start=2):
        key = str(row.get("key") or "").strip()
        if not _SHAPE_RX.fullmatch(key):
            continue
        raw = [",".join(f"{c}={str(row.get(c) or '')[:200]}" for c in cols)]
        sent = str(row.get("sentence") or "").strip()
        if sent:
            sentences.append((key, {
                "sentence": sent,
                "category": str(row.get("category") or "").strip(),
                "stated_at": str(row.get("date") or "").strip(),
                "entity_key": str(row.get("company") or "").strip(),
            }, _src(a, "worksheet_csv", i, i, raw, "sentence")))
        v = str(row.get("verdict") or "").strip().lower()
        if v in VERDICTS:
            verdicts.append((key, v, _src(a, "worksheet_csv", i, i, raw, "verdict")))
    return verdicts, sentences


def parse_block_evidence(a: Artifact) -> tuple[list[tuple[str, dict, EvidenceSource]], list[tuple[str, dict, EvidenceSource]]]:
    """Block evidence: JUDGED / R2-JUDGED verdict lines, and key-header lines
    immediately followed by an indented VERBATIM record.

    The VERBATIM association is established by the format (header line then its
    own VERBATIM line), never by proximity alone: any VERBATIM without an
    immediately preceding header is dropped, and a header whose next VERBATIM is
    separated by another header is dropped."""
    verdicts: list[tuple[str, dict, EvidenceSource]] = []
    sentences: list[tuple[str, dict, EvidenceSource]] = []
    lines = a.text.splitlines()
    pending: tuple[int, str, dict, str] | None = None
    for i, line in enumerate(lines, start=1):
        m = _JUDGED_RX.match(line)
        if m:
            verdicts.append((m.group(1), {
                "verdict": m.group(2),
                "relabeled": int(m.group(4)),
                "relabel_to": (m.group(5) or ""),
            }, _src(a, "judged_line", i, i, [line], "verdict")))
            continue
        m = _R2_JUDGED_RX.match(line)
        if m:
            verdicts.append((m.group(1), {"verdict": m.group(2), "relabeled": 0, "relabel_to": ""},
                             _src(a, "r2_judged_line", i, i, [line], "verdict")))
            continue
        m = _HEADER_RX.match(line)
        if m:
            pending = (i, m.group(1), {
                "entity_key": m.group(2), "stated_at": m.group(3), "category": m.group(4),
            }, line)
            continue
        m = _VERBATIM_RX.match(line)
        if m and pending is not None:
            start, key, meta, hline = pending
            payload = dict(meta)
            payload["sentence"] = m.group(1)
            sentences.append((key, payload, _src(a, "header_verbatim", start, i, [hline, line], "sentence")))
            pending = None
            continue
        # any other non-blank line between a header and its VERBATIM is allowed
        # (model reason lines sit there); a second header cancels the first.
    return verdicts, sentences


def parse_key_identities(a: Artifact) -> list[tuple[str, dict, EvidenceSource]]:
    """Key header lines give (entity, date, category) for a key. This is IDENTITY
    evidence only: it never establishes that the key was reviewed, and never
    establishes its sentence. Level 3 replay needs the entity and date to
    reconstruct a candidate pool, and takes them from here."""
    out: list[tuple[str, dict, EvidenceSource]] = []
    for i, line in enumerate(a.text.splitlines(), start=1):
        m = _HEADER_RX.match(line)
        if m:
            out.append((m.group(1), {"entity_key": m.group(2), "stated_at": m.group(3),
                                     "category": m.group(4)},
                        _src(a, "key_header", i, i, [line], "identity")))
    return out


def parse_cluster_csv(a: Artifact) -> list[tuple[str, dict, EvidenceSource]]:
    """Cluster CSV: accepted ONLY where the header explicitly carries both a key
    column and a sentence/statement column. Cluster files without that schema
    establish no key->sentence association and are reported, not guessed."""
    out: list[tuple[str, dict, EvidenceSource]] = []
    name = a.relpath.lower()
    if not (name.endswith(".csv") and "cluster" in name):
        return out
    rdr = csv.DictReader(io.StringIO(a.text))
    cols = [c.strip() for c in (rdr.fieldnames or [])]
    keycol = next((c for c in cols if c in ("key", "candidate_id", "row_key")), None)
    sentcol = next((c for c in cols if c in ("sentence", "statement", "verbatim")), None)
    if not keycol or not sentcol:
        return out
    for i, row in enumerate(rdr, start=2):
        key = str(row.get(keycol) or "").strip()
        sent = str(row.get(sentcol) or "").strip()
        if not _SHAPE_RX.fullmatch(key) or not sent:
            continue
        raw = [",".join(f"{c}={str(row.get(c) or '')[:200]}" for c in cols)]
        out.append((key, {"sentence": sent, "category": str(row.get("category") or "").strip(),
                          "stated_at": "", "entity_key": ""},
                    _src(a, "cluster_csv", i, i, raw, "sentence")))
    return out


def unclassified_shape_matches(a: Artifact, claimed: set[str]) -> int:
    """Shape matches in this artifact that no authority classified."""
    return sum(1 for m in _SHAPE_RX.finditer(a.text) if m.group(1) not in claimed)


# ---------------------------------------------------------------- keys
def s_key(entity_key: str, stated_at: str, category: str) -> str:
    """Delegates to the production key derivation; no second implementation."""
    from biointel import priorities as _p

    return _p._skey_of((entity_key, str(stated_at)[:10], category))


# ---------------------------------------------------------------- levels
def level1(arts: list[Artifact]) -> tuple[dict[str, list], dict[str, list], dict[str, dict], dict[str, int]]:
    """Collect verdict-bearing and sentence-bearing evidence from artifacts."""
    v_by_key: dict[str, list] = {}
    s_by_key: dict[str, list] = {}
    ident: dict[str, dict] = {}
    claimed: set[str] = set()
    stats = {"artifacts": 0, "worksheet_rows": 0, "judged_lines": 0, "header_verbatim": 0,
             "cluster_rows": 0, "unclassified_identifier": 0}
    authority: dict[str, set] = {"worksheet": set(), "judged": set(), "r2_judged": set(),
                                 "header": set(), "cluster": set()}
    for a in arts:
        stats["artifacts"] += 1
        wv, ws = parse_worksheet_csv(a)
        for key, v, src in wv:
            v_by_key.setdefault(key, []).append(({"verdict": v, "relabeled": 0, "relabel_to": ""}, src, SRC_WORKSHEET))
            claimed.add(key)
            authority["worksheet"].add(key)
            stats["worksheet_rows"] += 1
        for key, payload, src in ws:
            s_by_key.setdefault(key, []).append((payload, src, SRC_WORKSHEET))
            claimed.add(key)
            authority["worksheet"].add(key)
        bv, bs = parse_block_evidence(a)
        for key, payload, src in bv:
            v_by_key.setdefault(key, []).append((payload, src, SRC_JUDGING))
            claimed.add(key)
            authority["r2_judged" if src.parser == "r2_judged_line" else "judged"].add(key)
            stats["judged_lines"] += 1
        for key, payload, src in bs:
            s_by_key.setdefault(key, []).append((payload, src, SRC_JUDGING))
            claimed.add(key)
            authority["header"].add(key)
            stats["header_verbatim"] += 1
        for key, payload, src in parse_key_identities(a):
            ident.setdefault(key, {"entity_key": payload["entity_key"],
                                   "stated_at": payload["stated_at"],
                                   "category": payload["category"], "source": src})
        for key, payload, src in parse_cluster_csv(a):
            s_by_key.setdefault(key, []).append((payload, src, SRC_CLUSTER))
            claimed.add(key)
            authority["cluster"].add(key)
            stats["cluster_rows"] += 1
        stats["unclassified_identifier"] += unclassified_shape_matches(a, claimed)
    stats["key_headers"] = len(ident)
    return v_by_key, s_by_key, ident, stats, authority


def level2_tables(con=None) -> dict[str, dict]:
    """Surviving exact key->statement mappings. READ ONLY: this function calls
    only store readers, never a writer."""
    out: dict[str, dict] = {}
    con = con or store.connect()
    if store.has_table("stated_priorities_r2", con):
        for r in store.read_table("stated_priorities_r2", con=con):
            k = "R" + hashlib.sha256(
                f"{r['entity_key']}|{str(r['stated_at'])[:10]}|{r['category']}|{r['statement']}".encode()
            ).hexdigest()[:16]
            out[k] = {"sentence": str(r["statement"]), "category": str(r["category"]),
                      "entity_key": str(r["entity_key"]), "stated_at": str(r["stated_at"])[:10]}
    if store.has_table("stated_priorities", con):
        for r in store.read_table("stated_priorities", con=con):
            k = s_key(str(r["entity_key"]), str(r["stated_at"]), str(r["category"]))
            out.setdefault(k, {"sentence": str(r["statement"]), "category": str(r["category"]),
                               "entity_key": str(r["entity_key"]), "stated_at": str(r["stated_at"])[:10]})
    return out


def rule_versions(con=None) -> dict[str, str]:
    """Latest rule_version per reviewed key, from candidate_reviews. READ ONLY.
    Replay eligibility is decided by this, not by the key's lexical shape."""
    out: dict[str, str] = {}
    con = con or store.connect()
    if not store.has_table("candidate_reviews", con):
        return out
    for r in sorted(store.read_table("candidate_reviews", con=con),
                    key=lambda x: str(x.get("reviewed_at"))):
        out[str(r["candidate_id"])] = str(r.get("rule_version") or "")
    return out


def build_candidate_index(con=None, gauge: str = "replay") -> tuple[dict, dict]:
    """Pre-suppression candidate index over the frozen corpus.

    Reuses the production sweep primitives (`iter_sweep_documents`,
    `extract_priorities`, `make_candidate`, `pool_select`) so candidate
    generation, longest-wins and tie behaviour are the SAME logic the writer
    runs, not a second implementation. No verdict map is consulted, so a
    judged-wrong key's candidate is present.

    The tie rule reproduced here is production's own: strictly-greater
    comparison in sweep order, so the first candidate of maximal length wins.
    Keys whose winner was decided by such a tie are counted and reported.
    """
    from biointel import priorities as _p

    con = con or store.connect()
    pairs: list[tuple[tuple, dict]] = []
    pop = {"documents_read": 0, "documents_with_rows": 0, "candidates": 0}
    for tier, entity, stated_at, cap, text in _p.iter_sweep_documents(con, gauge=gauge):
        pop["documents_read"] += 1
        rows = _p.extract_priorities(text, tier)
        if not rows:
            continue
        pop["documents_with_rows"] += 1
        for row in rows:
            pop["candidates"] += 1
            pairs.append(((entity, stated_at, row["category"]),
                          _p.make_candidate(entity, stated_at, row, cap, tier)))

    best, overflow = _p.pool_select(pairs)

    lengths: dict[tuple, list[int]] = {}
    for k, c in pairs:
        lengths.setdefault(k, []).append(len(str(c["statement"])))
    runners: dict[str, list[dict]] = {}
    for row in overflow:
        rk = s_key(str(row["entity_key"]), str(row["stated_at"]), str(row["category"]))
        runners.setdefault(rk, []).append({"statement": str(row["statement"]),
                                           "length": len(str(row["statement"]))})

    index: dict[str, dict] = {}
    ties = 0
    for k, c in best.items():
        sk = s_key(k[0], k[1], k[2])
        ls = lengths.get(k, [])
        top = max(ls) if ls else 0
        tie = sum(1 for x in ls if x == top) > 1
        ties += 1 if tie else 0
        index[sk] = {
            "s_key": sk, "entity_key": c["entity_key"], "stated_at": c["stated_at"],
            "category": c["category"], "statement": c["statement"], "doc_id": c["doc_id"],
            "source_type": c["source_type"], "section": c["section"],
            "rule_version": _p.RULE_VERSION_F2,
            "winner_length": len(str(c["statement"])), "candidate_count": len(ls),
            "tie_at_max_length": tie, "runner_ups": runners.get(sk, []),
        }
    pop["distinct_keys"] = len(index)
    pop["overflow_rows"] = len(overflow)
    pop["keys_won_on_tie"] = ties
    return index, pop


def index_cache_path(out_dir: Path | None = None) -> Path:
    return Path(out_dir or config.EXPORTS) / INDEX_CACHE_NAME


def load_index_cache(out_dir: Path | None = None) -> tuple[dict, dict] | None:
    """Reuse a previously built index so a rerun does not pay the sweep again.
    Refused unless the cache records this index version and rule version."""
    from biointel import priorities as _p

    p = index_cache_path(out_dir)
    if not p.is_file():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # noqa: BLE001
        print(f"index_cache unreadable ({type(exc).__name__}: {exc}); rebuilding")
        return None
    if blob.get("cache_version") != INDEX_CACHE_VERSION or blob.get("rule_version") != _p.RULE_VERSION_F2:
        print("index_cache version mismatch; rebuilding")
        return None
    return blob["index"], blob["pop"]


def save_index_cache(index: dict, pop: dict, out_dir: Path | None = None) -> Path:
    from biointel import priorities as _p

    p = index_cache_path(out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"cache_version": INDEX_CACHE_VERSION,
                             "rule_version": _p.RULE_VERSION_F2,
                             "parser_version": PARSER_VERSION,
                             "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "pop": pop, "index": index}), encoding="utf-8")
    return p


def level3_replay(unresolved: list[str], index: dict, versions: dict[str, str]) -> dict[str, dict]:
    """Join the unresolved remainder against the pre-suppression index.

    Eligibility: S-keys only, and only where the key's recorded rule version is
    the one the index reproduces. Anything else stays unresolved with a named
    reason rather than being forced through a generator that did not produce it.
    """
    from biointel import priorities as _p

    out: dict[str, dict] = {}
    for key in unresolved:
        if not key.startswith("S"):
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_NOT_S_KEY}
            continue
        rv = versions.get(key)
        if rv is None:
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_RULE_VERSION_UNKNOWN}
            continue
        if rv != _p.RULE_VERSION_F2:
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_RULE_VERSION_MISMATCH}
            continue
        hit = index.get(key)
        if hit is None:
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_REPLAY_NO_MATCH}
            continue
        out[key] = {"status": SRC_REPLAY, "sentence": hit["statement"],
                    "category": hit["category"], "entity_key": hit["entity_key"],
                    "stated_at": hit["stated_at"], "detail": hit}
    return out


# ---------------------------------------------------------------- resolver
def resolve(arts: list[Artifact], table_map: dict[str, dict] | None = None,
            index: dict | None = None, versions: dict[str, str] | None = None) -> tuple[list[Mapping], dict, dict]:
    v_by_key, s_by_key, ident, stats, authority = level1(arts)
    table_map = table_map or {}
    mappings: list[Mapping] = []
    meta: dict[str, dict] = {}
    for key, entries in s_by_key.items():
        for payload, _src, _cls in entries:
            if payload.get("entity_key") and payload.get("stated_at"):
                meta.setdefault(key, {"entity_key": payload["entity_key"], "stated_at": payload["stated_at"]})
    for key, payload in ident.items():
        meta.setdefault(key, {"entity_key": payload["entity_key"], "stated_at": payload["stated_at"]})

    keys = sorted(set(v_by_key) | set(s_by_key))
    unresolved_for_replay: list[str] = []
    for key in keys:
        m = Mapping(reviewed_key=key, key_class=key[:1])
        # ---- verdict authority
        vlist = v_by_key.get(key, [])
        if vlist:
            payload, src, cls = vlist[-1]  # latest evidence wins; all retained below
            m.verdict = str(payload.get("verdict", ""))
            if payload.get("relabeled"):
                m.resulting_category = str(payload.get("relabel_to", ""))
            m.verdict_source_class = cls
            for p, s, _c in vlist:
                m.evidence_sources.append(s)
        # ---- sentence authority
        slist = s_by_key.get(key, [])
        if slist:
            texts = {str(p.get("sentence", "")).strip() for p, _s, _c in slist}
            if len(texts) > 1:
                m.status = SRC_AMBIGUOUS
                m.reason = R_CONFLICT_SENTENCE
            payload, src, cls = slist[0]
            m.sentence = str(payload.get("sentence", ""))
            m.original_category = str(payload.get("category", ""))
            m.entity_key = str(payload.get("entity_key", ""))
            m.stated_at = str(payload.get("stated_at", ""))
            m.sentence_source_class = cls
            for _p, s, _c in slist:
                m.evidence_sources.append(s)
        elif key in table_map:
            t = table_map[key]
            m.sentence = t["sentence"]
            m.original_category = t.get("category", "")
            m.entity_key = t.get("entity_key", "")
            m.stated_at = t.get("stated_at", "")
            m.sentence_source_class = SRC_TABLE
            m.evidence_sources.append(EvidenceSource(
                filename="db:stated_priorities*", sha256="", parser="table_lookup",
                era="", session="", raw_ref="exact key match", raw_lines=[], role="sentence"))
        # ---- status
        if m.status == SRC_AMBIGUOUS:
            pass
        elif m.sentence and m.verdict:
            m.status = m.sentence_source_class
        elif m.sentence and not m.verdict:
            m.status = SRC_UNRESOLVED
            m.reason = R_NO_VERDICT
        elif m.verdict and not m.sentence:
            m.status = SRC_UNRESOLVED
            m.reason = R_NO_SENTENCE
            unresolved_for_replay.append(key)
        # ---- relabel identity (design §9): keep all three
        if m.resulting_category and m.entity_key and m.stated_at:
            m.resulting_key = s_key(m.entity_key, m.stated_at, m.resulting_category)
        if m.evidence_sources:
            m.era = m.evidence_sources[0].era
            m.session = m.evidence_sources[0].session
        m.rule_version = (versions or {}).get(key, "")
        mappings.append(m)

    # ---- Level 3 on the unresolved remainder only; never dilutes direct provenance
    pre = {m.reviewed_key: m.status for m in mappings}
    replayed = level3_replay(unresolved_for_replay, index or {}, versions or {}) if index is not None else {}
    by_key = {m.reviewed_key: m for m in mappings}
    for key, r in replayed.items():
        m = by_key[key]
        if m.status not in (SRC_UNRESOLVED,):
            continue  # direct provenance is never overwritten
        if r["status"] == SRC_REPLAY:
            m.status = SRC_REPLAY
            m.reason = ""
            m.sentence = r["sentence"]
            m.original_category = r.get("category", "")
            m.entity_key = r.get("entity_key", "")
            m.stated_at = r.get("stated_at", "")
            m.sentence_source_class = SRC_REPLAY
            m.replay_detail = r.get("detail", {})
            d = m.replay_detail
            # An identity whose production winner depended on sweep order at equal
            # maximum length is weaker than one decided by length alone; it is
            # flagged, never silently treated as equal-confidence.
            m.replay_order_dependent_tie = bool(d.get("tie_at_max_length"))
            m.evidence_sources.append(EvidenceSource(
                filename=f"replay:frozen_extractor:{d.get('doc_id', '')}", sha256="",
                parser=f"replay/{PARSER_VERSION}", era="", session="",
                raw_ref=(f"pre-suppression pool; candidates={d.get('candidate_count', 0)} "
                         f"winner_length={d.get('winner_length', 0)} tie={d.get('tie_at_max_length', False)} "
                         f"runner_ups={len(d.get('runner_ups', []))} rule={d.get('rule_version', '')}"),
                raw_lines=[str(d.get("statement", ""))[:400]], role="sentence"))
        else:
            m.status = r["status"]
            m.reason = r["reason"]
        if m.resulting_category and m.entity_key and m.stated_at:
            m.resulting_key = s_key(m.entity_key, m.stated_at, m.resulting_category)
    transitions = {"pre_status": pre, "replayed_keys": sorted(replayed)}
    return mappings, stats, {"authority": authority, "transitions": transitions}


# ---------------------------------------------------------------- census
def audit_bundles(mappings: list[Mapping], per_class: int = 3, seed: int = 20260912) -> dict[str, list[dict]]:
    """Deterministic specimens per (parser, source class): first, middle, last."""
    buckets: dict[str, list[Mapping]] = {}
    for m in mappings:
        for s in m.evidence_sources:
            buckets.setdefault(f"{s.parser}|{m.status}", []).append(m)
    rnd = random.Random(seed)
    out: dict[str, list[dict]] = {}
    for k, rows in sorted(buckets.items()):
        rows = sorted(rows, key=lambda r: r.reviewed_key)
        picks = [rows[0], rows[len(rows) // 2], rows[-1]][:per_class]
        if len(rows) > 3 and per_class > 3:
            picks += rnd.sample(rows, min(per_class - 3, len(rows)))
        out[k] = [{
            "reviewed_key": p.reviewed_key, "sentence": p.sentence, "verdict": p.verdict,
            "original_category": p.original_category, "resulting_category": p.resulting_category,
            "resulting_key": p.resulting_key, "status": p.status, "reason": p.reason,
            "parser_version": p.parser_version,
            "replay_order_dependent_tie": p.replay_order_dependent_tie,
            "evidence_sources": [asdict(s) for s in p.evidence_sources],
        } for p in picks]
    return out


def census(root: Path | None = None, con=None, replay: bool = True, out_dir: Path | None = None,
           rebuild_index: bool = False) -> int:
    arts = manifest(root)
    con = con or store.connect()

    table_map: dict[str, dict] = {}
    try:
        table_map = level2_tables(con)
    except Exception as exc:  # noqa: BLE001 - a missing database is reported, not fatal
        print(f"LEVEL2 UNAVAILABLE {type(exc).__name__}: {exc}")
    versions: dict[str, str] = {}
    try:
        versions = rule_versions(con)
    except Exception as exc:  # noqa: BLE001
        print(f"RULE VERSIONS UNAVAILABLE {type(exc).__name__}: {exc}")

    index: dict | None = None
    pop: dict = {}
    if replay:
        print("--- LEVEL 3 PRE-SUPPRESSION INDEX", flush=True)
        cached = None if rebuild_index else load_index_cache(out_dir)
        if cached is not None:
            index, pop = cached
            cp = index_cache_path(out_dir)
            print(f"index_source cache {cp.name} bytes {cp.stat().st_size}", flush=True)
            print(f"index_cache_sha256 {hashlib.sha256(cp.read_bytes()).hexdigest()}", flush=True)
        else:
            try:
                print("index_source sweep (no usable cache); this pays the full corpus sweep", flush=True)
                index, pop = build_candidate_index(con)
                cp = save_index_cache(index, pop, out_dir)
                print(f"index_cache_written {cp.name} sha256 {hashlib.sha256(cp.read_bytes()).hexdigest()}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"LEVEL3 INDEX UNAVAILABLE {type(exc).__name__}: {exc}")
                index = None

    mappings, stats, extra = resolve(arts, table_map, index, versions)
    authority = extra["authority"]
    pre_status = extra["transitions"]["pre_status"]

    exports = Path(out_dir or config.EXPORTS)
    print(f"R3-0c-iv RECOVERY CENSUS parser {PARSER_VERSION}")
    print(f"generated_utc {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"artifacts {len(arts)} total_bytes {sum(a.size for a in arts)}")
    for k, v in sorted(stats.items()):
        print(f"stat {k} {v}")

    # ---- input population of the replay index (clarification 1)
    print("--- REPLAY INPUT POPULATION")
    if index is None:
        print("replay_ran no")
    else:
        for k, v in sorted(pop.items()):
            print(f"pop {k} {v}")
        print("pop_note the index is a RECONSTRUCTION from the current frozen corpus under "
              f"rule {RULE_VERSION_REPLAYED}; it is not asserted to be a byte-identical replay of any "
              "historical sweep, because the historical reference and capture set was never recorded "
              "as an input manifest. Compare pop documents_read against the historical sweep total "
              "before treating a replayed mapping as byte-for-byte historical.")

    # ---- status and class accounting, every count with its denominator
    by_status: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for m in mappings:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        if m.reason:
            reasons[m.reason] = reasons.get(m.reason, 0) + 1
    recovered_statuses = (SRC_WORKSHEET, SRC_JUDGING, SRC_CLUSTER, SRC_TABLE, SRC_REPLAY)
    recovered = [m for m in mappings if m.status in recovered_statuses]
    ambiguous = [m for m in mappings if m.status == SRC_AMBIGUOUS]
    unresolved = [m for m in mappings if m.status == SRC_UNRESOLVED]

    print(f"reviewed_keys {len(mappings)}")
    for s, n in sorted(by_status.items()):
        print(f"status {s} {n}")
    for r, n in sorted(reasons.items()):
        print(f"reason {r} {n}")
    print(f"key_class_S {sum(1 for m in mappings if m.key_class == 'S')}")
    print(f"key_class_R {sum(1 for m in mappings if m.key_class == 'R')}")

    print("--- MAPPING-LEVEL CLASSES (denominator: recovered mappings)")
    print(f"denominator recovered_mappings {len(recovered)}")
    for v in ("correct", "wrong", "unsure"):
        print(f"recovered_verdict_{v} {sum(1 for m in recovered if m.verdict == v)}")
    print(f"recovered_without_usable_verdict {sum(1 for m in recovered if m.verdict not in VERDICTS)}")
    print("--- MAPPING-LEVEL CLASSES (denominator: ambiguous mappings)")
    print(f"denominator ambiguous_mappings {len(ambiguous)}")
    print(f"ambiguous_verdict_bearing {sum(1 for m in ambiguous if m.verdict in VERDICTS)}")
    for v in ("correct", "wrong", "unsure"):
        print(f"ambiguous_verdict_{v} {sum(1 for m in ambiguous if m.verdict == v)}")
    print("--- MAPPING-LEVEL CLASSES (denominator: unresolved mappings)")
    print(f"denominator unresolved_mappings {len(unresolved)}")
    print(f"unresolved_verdict_bearing {sum(1 for m in unresolved if m.verdict in VERDICTS)}")

    # ---- sentence-level truth, reported separately from mapping counts
    print("--- SENTENCE-LEVEL (denominator: unique recovered sentences)")
    verd_by_sentence: dict[str, set] = {}
    cats_by_sentence: dict[str, set] = {}
    keys_by_sentence: dict[str, set] = {}
    for m in recovered:
        if not m.sentence:
            continue
        keys_by_sentence.setdefault(m.sentence, set()).add(m.reviewed_key)
        if m.verdict in VERDICTS:
            verd_by_sentence.setdefault(m.sentence, set()).add(m.verdict)
        if m.original_category:
            cats_by_sentence.setdefault(m.sentence, set()).add(m.original_category)
    uniq = set(keys_by_sentence)
    consistent_pos = sum(1 for s in uniq if verd_by_sentence.get(s) == {"correct"})
    consistent_neg = sum(1 for s in uniq if verd_by_sentence.get(s) == {"wrong"})
    unsure_only = sum(1 for s in uniq if verd_by_sentence.get(s) == {"unsure"})
    conflicting = sum(1 for s in uniq if len(verd_by_sentence.get(s, set())) > 1)
    no_verdict = sum(1 for s in uniq if not verd_by_sentence.get(s))
    print(f"denominator unique_recovered_sentences {len(uniq)}")
    print(f"unique_sentences_consistent_positive {consistent_pos}")
    print(f"unique_sentences_consistent_negative {consistent_neg}")
    print(f"unique_sentences_conflicting_verdicts {conflicting}")
    print(f"unique_sentences_unsure_only {unsure_only}")
    print(f"unique_sentences_without_verdict {no_verdict}")
    _ssum = consistent_pos + consistent_neg + conflicting + unsure_only + no_verdict
    print(f"SENTENCE_CLASS_IDENTITY {consistent_pos} + {consistent_neg} + {conflicting} + "
          f"{unsure_only} + {no_verdict} == {len(uniq)} -> {_ssum == len(uniq)}")
    print(f"clean_binary_training_pool {consistent_pos + consistent_neg}")
    print(f"unique_sentences_multi_category {sum(1 for s in uniq if len(cats_by_sentence.get(s, set())) > 1)}")
    print(f"unique_sentences_multiple_reviewed_keys {sum(1 for s in uniq if len(keys_by_sentence[s]) > 1)}")
    dup: dict[int, int] = {}
    for s in uniq:
        n = len(keys_by_sentence[s])
        dup[n] = dup.get(n, 0) + 1
    for n in sorted(dup):
        print(f"duplicate_frequency sentences_under_{n}_keys {dup[n]}")
    print("class_note mapping-level verdict observations are NOT a sentence-level training-class "
          "balance; the sentence-level lines above are the ones a training corpus may use.")

    # ---- order-dependent tie identities (operator ruling 2026-09-12)
    print("--- ORDER-DEPENDENT TIE IDENTITIES")
    indexed_ties = int(pop.get("keys_won_on_tie", 0)) if pop else 0
    tie_maps = [m for m in mappings if m.replay_order_dependent_tie]
    tie_recovered = [m for m in tie_maps if m.status in recovered_statuses]
    tie_sentences = {m.sentence for m in tie_recovered if m.sentence}
    print(f"indexed_keys_won_on_tie {indexed_ties}")
    print(f"tie_flagged_mappings {len(tie_maps)}")
    print(f"tie_flagged_recovered_mappings {len(tie_recovered)}")
    print(f"tie_flagged_distinct_recovered_sentences {len(tie_sentences)}")
    print("tie_note these identities were decided by sweep order at equal maximum length. "
          "They remain in the recovered corpus, carry replay_order_dependent_tie=true, and R3-1 "
          "must either exclude them initially or report a sensitivity check on their inclusion.")

    # ---- Level 3 transitions, explicit equations
    print("--- LEVEL 3 TRANSITIONS")
    was_unresolved = [m for m in mappings if pre_status.get(m.reviewed_key) == SRC_UNRESOLVED]
    newly_recovered = sum(1 for m in was_unresolved if m.status == SRC_REPLAY)
    newly_ambiguous = sum(1 for m in was_unresolved if m.status == SRC_AMBIGUOUS)
    still_unres = sum(1 for m in was_unresolved if m.status == SRC_UNRESOLVED)
    print(f"level12_unresolved {len(was_unresolved)}")
    print(f"replay_recovered {newly_recovered}")
    print(f"replay_created_ambiguous {newly_ambiguous}")
    print(f"still_unresolved {still_unres}")
    print(f"TRANSITION_EQUATION {len(was_unresolved)} == {newly_recovered} + {newly_ambiguous} + {still_unres} "
          f"-> {newly_recovered + newly_ambiguous + still_unres == len(was_unresolved)}")
    pre_recovered = sum(1 for m in mappings if pre_status.get(m.reviewed_key) in recovered_statuses)
    pre_ambiguous = sum(1 for m in mappings if pre_status.get(m.reviewed_key) == SRC_AMBIGUOUS)
    print(f"pre_existing_recovered {pre_recovered}")
    print(f"pre_existing_ambiguous {pre_ambiguous}")
    print(f"RECONCILIATION_EQUATION {len(mappings)} == {pre_recovered} + {newly_recovered} + "
          f"{pre_ambiguous} + {newly_ambiguous} + {still_unres} -> "
          f"{pre_recovered + newly_recovered + pre_ambiguous + newly_ambiguous + still_unres == len(mappings)}")

    # ---- p2h sub-report on the same accounting
    print("--- P2H SUB-REPORT")
    p2h = [m for m in mappings if m.session == "p2h"]
    p2h_pre_unres = [m for m in p2h if pre_status.get(m.reviewed_key) == SRC_UNRESOLVED]
    print(f"p2h_keys {len(p2h)}")
    print(f"p2h_level12_unresolved {len(p2h_pre_unres)}")
    print(f"p2h_replay_recovered {sum(1 for m in p2h_pre_unres if m.status == SRC_REPLAY)}")
    print(f"p2h_replay_created_ambiguous {sum(1 for m in p2h_pre_unres if m.status == SRC_AMBIGUOUS)}")
    print(f"p2h_still_unresolved {sum(1 for m in p2h_pre_unres if m.status == SRC_UNRESOLVED)}")

    # ---- authority-form set overlaps, measured not inferred
    print("--- AUTHORITY-FORM SET OVERLAPS")
    for name, keys in sorted(authority.items()):
        print(f"authority {name} distinct {len(keys)} S {sum(1 for k in keys if k.startswith('S'))} "
              f"R {sum(1 for k in keys if k.startswith('R'))}")
    names = sorted(authority)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = authority[a] & authority[b]
            print(f"overlap {a}&{b} {len(inter)}")
    allk = set().union(*authority.values()) if authority else set()
    print(f"authority_union {len(allk)}")

    # ---- era and session
    print("--- RECOVERY BY ERA AND SESSION")
    era_rows: dict[tuple[str, str], dict[str, int]] = {}
    for m in mappings:
        b = era_rows.setdefault((m.era or "unknown", m.session or "unknown"), {})
        b[m.status] = b.get(m.status, 0) + 1
    for (era, sess), b in sorted(era_rows.items()):
        tot = sum(b.values())
        rec = sum(n for s, n in b.items() if s in recovered_statuses)
        print(f"era {era} session {sess} keys {tot} recovered {rec} " + " ".join(f"{s}={n}" for s, n in sorted(b.items())))

    exports.mkdir(parents=True, exist_ok=True)
    mpath = exports / "20260912_v3_r3_recovery_source_manifest.csv"
    with open(mpath, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "sha256", "bytes", "mtime_utc", "encoding", "era", "session"])
        for a in arts:
            w.writerow([a.relpath, a.sha256, a.size, a.mtime, a.encoding, a.era, a.session])
    apath = exports / "20260912_v3_r3_recovery_audit_bundles.json"
    apath.write_text(json.dumps(audit_bundles(mappings), indent=2)[:8_000_000], encoding="utf-8")
    print(f"manifest {mpath.name} rows {len(arts)}")
    print(f"audit_bundles {apath.name}")
    print(f"RECONCILIATION reviewed_keys {len(mappings)} == sum(status) {sum(by_status.values())}")
    print("R3-0c-iv END")
    return 0


def cli(argv: list[str]) -> int:
    if argv and argv[0] == "r3-census":
        return census(replay="--no-replay" not in argv, rebuild_index="--rebuild-index" in argv)
    print("usage: r3-census")
    return 1
