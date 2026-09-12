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

PARSER_VERSION = "REC-v1"

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
    return "S" + hashlib.sha256(
        f"{entity_key}|{str(stated_at)[:10]}|{category}".encode()
    ).hexdigest()[:16]


# ---------------------------------------------------------------- levels
def level1(arts: list[Artifact]) -> tuple[dict[str, list], dict[str, list], dict[str, dict], dict[str, int]]:
    """Collect verdict-bearing and sentence-bearing evidence from artifacts."""
    v_by_key: dict[str, list] = {}
    s_by_key: dict[str, list] = {}
    ident: dict[str, dict] = {}
    claimed: set[str] = set()
    stats = {"artifacts": 0, "worksheet_rows": 0, "judged_lines": 0, "header_verbatim": 0,
             "cluster_rows": 0, "unclassified_identifier": 0}
    for a in arts:
        stats["artifacts"] += 1
        wv, ws = parse_worksheet_csv(a)
        for key, v, src in wv:
            v_by_key.setdefault(key, []).append(({"verdict": v, "relabeled": 0, "relabel_to": ""}, src, SRC_WORKSHEET))
            claimed.add(key)
            stats["worksheet_rows"] += 1
        for key, payload, src in ws:
            s_by_key.setdefault(key, []).append((payload, src, SRC_WORKSHEET))
            claimed.add(key)
        bv, bs = parse_block_evidence(a)
        for key, payload, src in bv:
            v_by_key.setdefault(key, []).append((payload, src, SRC_JUDGING))
            claimed.add(key)
            stats["judged_lines"] += 1
        for key, payload, src in bs:
            s_by_key.setdefault(key, []).append((payload, src, SRC_JUDGING))
            claimed.add(key)
            stats["header_verbatim"] += 1
        for key, payload, src in parse_key_identities(a):
            ident.setdefault(key, {"entity_key": payload["entity_key"],
                                   "stated_at": payload["stated_at"],
                                   "category": payload["category"], "source": src})
        for key, payload, src in parse_cluster_csv(a):
            s_by_key.setdefault(key, []).append((payload, src, SRC_CLUSTER))
            claimed.add(key)
            stats["cluster_rows"] += 1
        stats["unclassified_identifier"] += unclassified_shape_matches(a, claimed)
    stats["key_headers"] = len(ident)
    return v_by_key, s_by_key, ident, stats


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


def level3_replay(unresolved: list[str], meta: dict[str, dict], replayer=None) -> dict[str, dict]:
    """Pre-suppression replay, on the unresolved remainder ONLY.

    `replayer(entity_key, stated_at)` returns the FULL candidate list for that
    document under the frozen extractor, before any verdict suppression is
    consulted. Longest-wins per (entity, date, category) reproduces the writer's
    choice. More than one surviving candidate for a key is ambiguous, never
    resolved by preference."""
    out: dict[str, dict] = {}
    if replayer is None:
        return out
    for key in unresolved:
        m = meta.get(key) or {}
        ent, date = m.get("entity_key", ""), m.get("stated_at", "")
        if not ent or not date:
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_REPLAY_NO_CAPTURE}
            continue
        cands = replayer(ent, date) or []
        if not cands:
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_REPLAY_NO_CAPTURE}
            continue
        hits = [c for c in cands if s_key(ent, date, str(c.get("category", ""))) == key]
        if not hits:
            out[key] = {"status": SRC_UNRESOLVED, "reason": R_REPLAY_NO_MATCH}
            continue
        longest = max(len(str(c.get("sentence", ""))) for c in hits)
        winners = [c for c in hits if len(str(c.get("sentence", ""))) == longest]
        if len(winners) != 1:
            out[key] = {"status": SRC_AMBIGUOUS, "reason": R_REPLAY_AMBIGUOUS}
            continue
        out[key] = {"status": SRC_REPLAY, "sentence": str(winners[0]["sentence"]),
                    "category": str(winners[0].get("category", "")), "entity_key": ent, "stated_at": date}
    return out


# ---------------------------------------------------------------- resolver
def resolve(arts: list[Artifact], table_map: dict[str, dict] | None = None, replayer=None) -> tuple[list[Mapping], dict]:
    v_by_key, s_by_key, ident, stats = level1(arts)
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
        mappings.append(m)

    # ---- Level 3 on the unresolved remainder only; never dilutes direct provenance
    replayed = level3_replay(unresolved_for_replay, meta, replayer)
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
            m.evidence_sources.append(EvidenceSource(
                filename="replay:frozen_extractor", sha256="", parser=f"replay/{PARSER_VERSION}",
                era="", session="", raw_ref="pre-suppression candidate pool", raw_lines=[], role="sentence"))
        else:
            m.status = r["status"]
            m.reason = r["reason"]
        if m.resulting_category and m.entity_key and m.stated_at:
            m.resulting_key = s_key(m.entity_key, m.stated_at, m.resulting_category)
    return mappings, stats


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
            "evidence_sources": [asdict(s) for s in p.evidence_sources],
        } for p in picks]
    return out


def census(root: Path | None = None, con=None, replayer=None, out_dir: Path | None = None) -> int:
    arts = manifest(root)
    table_map: dict[str, dict] = {}
    try:
        table_map = level2_tables(con)
    except Exception as exc:  # noqa: BLE001 - a missing database is reported, not fatal
        print(f"LEVEL2 UNAVAILABLE {type(exc).__name__}: {exc}")
    mappings, stats = resolve(arts, table_map, replayer)

    exports = Path(out_dir or config.EXPORTS)
    print(f"R3-0c-ii RECOVERY CENSUS parser {PARSER_VERSION}")
    print(f"generated_utc {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"artifacts {len(arts)} total_bytes {sum(a.size for a in arts)}")
    for k, v in sorted(stats.items()):
        print(f"stat {k} {v}")

    by_status: dict[str, int] = {}
    by_class: dict[str, int] = {}
    reasons: dict[str, int] = {}
    pos = neg = 0
    sentences: dict[str, int] = {}
    for m in mappings:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        by_class[m.key_class] = by_class.get(m.key_class, 0) + 1
        if m.reason:
            reasons[m.reason] = reasons.get(m.reason, 0) + 1
        if m.sentence and m.verdict:
            if m.verdict == "correct":
                pos += 1
            elif m.verdict == "wrong":
                neg += 1
        if m.sentence:
            sentences[m.sentence] = sentences.get(m.sentence, 0) + 1
    recovered = sum(n for s, n in by_status.items() if s in (SRC_WORKSHEET, SRC_JUDGING, SRC_CLUSTER, SRC_TABLE, SRC_REPLAY))
    print(f"reviewed_keys {len(mappings)}")
    for s, n in sorted(by_status.items()):
        print(f"status {s} {n}")
    for c, n in sorted(by_class.items()):
        print(f"key_class {c} {n}")
    for r, n in sorted(reasons.items()):
        print(f"reason {r} {n}")
    print(f"recovered_total {recovered}")
    print(f"recoverable_positives {pos}")
    print(f"recoverable_negatives {neg}")
    print(f"unique_recovered_sentences {len(sentences)}")
    dup = {}
    for n in sentences.values():
        dup[n] = dup.get(n, 0) + 1
    for n in sorted(dup):
        print(f"duplicate_frequency sentences_appearing_{n}x {dup[n]}")

    # conflicts
    key_by_sentence: dict[str, set[str]] = {}
    cats_by_sentence: dict[str, set[str]] = {}
    verds_by_sentence: dict[str, set[str]] = {}
    for m in mappings:
        if not m.sentence:
            continue
        key_by_sentence.setdefault(m.sentence, set()).add(m.reviewed_key)
        if m.original_category:
            cats_by_sentence.setdefault(m.sentence, set()).add(m.original_category)
        if m.verdict:
            verds_by_sentence.setdefault(m.sentence, set()).add(m.verdict)
    print(f"same_sentence_multiple_keys {sum(1 for v in key_by_sentence.values() if len(v) > 1)}")
    print(f"same_sentence_multiple_categories {sum(1 for v in cats_by_sentence.values() if len(v) > 1)}")
    print(f"same_sentence_conflicting_verdicts {sum(1 for v in verds_by_sentence.values() if len(v) > 1)}")

    # era / session
    era_rows: dict[tuple[str, str], dict[str, int]] = {}
    for m in mappings:
        for s in m.evidence_sources:
            if not s.era:
                continue
            b = era_rows.setdefault((s.era, s.session), {})
            b[m.status] = b.get(m.status, 0) + 1
            break
    for (era, sess), b in sorted(era_rows.items()):
        tot = sum(b.values())
        rec = sum(n for s, n in b.items() if s in (SRC_WORKSHEET, SRC_JUDGING, SRC_CLUSTER, SRC_TABLE, SRC_REPLAY))
        print(f"era {era} session {sess} keys {tot} recovered {rec} " + " ".join(f"{s}={n}" for s, n in sorted(b.items())))

    # artifacts manifest + audit bundles to disk
    exports.mkdir(parents=True, exist_ok=True)
    mpath = exports / "20260912_v1_r3_recovery_source_manifest.csv"
    with open(mpath, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "sha256", "bytes", "mtime_utc", "encoding", "era", "session"])
        for a in arts:
            w.writerow([a.relpath, a.sha256, a.size, a.mtime, a.encoding, a.era, a.session])
    apath = exports / "20260912_v1_r3_recovery_audit_bundles.json"
    apath.write_text(json.dumps(audit_bundles(mappings), indent=2)[:4_000_000], encoding="utf-8")
    print(f"manifest {mpath.name} rows {len(arts)}")
    print(f"audit_bundles {apath.name}")
    print(f"RECONCILIATION reviewed_keys {len(mappings)} == sum(status) {sum(by_status.values())}")
    print("R3-0c-ii END")
    return 0


def cli(argv: list[str]) -> int:
    if argv and argv[0] == "r3-census":
        return census()
    print("usage: r3-census")
    return 1
