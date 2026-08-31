# src/biointel/library.py
"""Research library / file room (Ontology v5 §3.9; gate L1).

Three tables in the store (`references`, `captures`, `reference_links`)
over a content-addressed file store `data/bronze/library/<aa>/<sha>.<ext>`.
Collectors (biointel.collectors.*) bring documents in; this module owns
identity, dedupe, retirement, manifest/merge/verify and navigation.

Implementation note (GATEL1 runbook §2): files are deduplicated on disk by
SHA-256 — one file per hash — while the `captures` table is keyed
(`capture_id`, `ref_id`) so the same bytes may be cited from two
references without a second copy existing.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import config, results, schema, store

ADDED_BY_DEFAULT = "operator"
_TRACK_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                 "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid", "ref"}
_TEXT_EXTS = {".txt", ".htm", ".html"}
_LEDGER_INPUTS = ["silver:references", "silver:captures", "silver:reference_links"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def library_root() -> Path:
    return config.BRONZE / "library"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def store_path(sha: str, ext: str) -> Path:
    ext = ext if ext.startswith(".") or ext == "" else "." + ext
    return library_root() / sha[:2] / f"{sha}{ext}"


def put_file(src: Path) -> tuple[str, Path, bool]:
    """Copy `src` into the store under its hash. Returns (sha, path, new)."""
    sha = sha256_file(src)
    dst = store_path(sha, src.suffix.lower())
    if dst.exists():
        return sha, dst, False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return sha, dst, True


def put_bytes(data: bytes, ext: str) -> tuple[str, Path, bool]:
    sha = hashlib.sha256(data).hexdigest()
    dst = store_path(sha, ext)
    if dst.exists():
        return sha, dst, False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return sha, dst, True


def norm_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() not in _TRACK_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                       urlencode(q), ""))


def _ref_id(fields: dict) -> str:
    seed = (fields.get("sec_accession") or fields.get("doi")
            or fields.get("pmid") or norm_url(fields.get("url", ""))
            or (fields.get("source_system", "") + "|" + fields.get("source_key", ""))
            or (fields.get("title", "") + "|" + fields.get("published_at", "")))
    return "R" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _refs(con) -> list[dict]:
    return store.read_table("references", con=con) if store.has_table("references", con) else []


def resolve(ref_id: str, con) -> str:
    """Follow merged_into chains to the surviving ref_id."""
    by_id = {r["ref_id"]: r for r in _refs(con)}
    seen = set()
    while ref_id in by_id and by_id[ref_id].get("merged_into") and ref_id not in seen:
        seen.add(ref_id)
        ref_id = by_id[ref_id]["merged_into"]
    return ref_id


def find_reference(fields: dict, con) -> str | None:
    """Identifier ladder: source key -> accession/doi/pmid -> normalised URL."""
    rows = _refs(con)
    ss, sk = fields.get("source_system", ""), fields.get("source_key", "")
    if ss and sk:
        for r in rows:
            if r["source_system"] == ss and r["source_key"] == sk:
                return resolve(r["ref_id"], con)
    for ident in ("sec_accession", "doi", "pmid"):
        v = fields.get(ident, "")
        if v:
            for r in rows:
                if r[ident] == v:
                    return resolve(r["ref_id"], con)
    u = norm_url(fields.get("url", ""))
    if u:
        for r in rows:
            if norm_url(r["url"]) == u:
                return resolve(r["ref_id"], con)
    return None


def upsert_reference(fields: dict, con) -> tuple[str, bool]:
    """Attach to an existing reference via the ladder, or create one.
    Returns (ref_id, created)."""
    existing = find_reference(fields, con)
    if existing:
        return existing, False
    row = {c: "" for c in schema.REFERENCE_COLS}
    row.update({k: str(v) for k, v in fields.items() if k in row and v})
    row["ref_id"] = _ref_id(fields)
    row.setdefault("accessed_at", "")
    row["accessed_at"] = row["accessed_at"] or _now()
    row["added_by"] = row["added_by"] or ADDED_BY_DEFAULT
    row["status"] = "active"
    have = {r["ref_id"] for r in _refs(con)}
    if row["ref_id"] in have:  # seed collision on different identifiers
        row["ref_id"] = "R" + hashlib.sha256(
            (row["ref_id"] + row["title"] + _now()).encode()).hexdigest()[:16]
    store.append_rows("references", [row], schema.REFERENCE_COLS, con=con)
    return row["ref_id"], True


def add_capture(ref_id: str, sha: str, path: Path, kind: str, method: str,
                con, archive_url: str = "", archive_ts: str = "") -> bool:
    """One capture row per (sha, ref). Returns True when a row was added."""
    rows = store.read_table("captures", con=con) if store.has_table("captures", con) else []
    if any(r["capture_id"] == sha and r["ref_id"] == ref_id for r in rows):
        return False
    st = path.stat()
    row = {c: "" for c in schema.CAPTURE_COLS}
    row.update({
        "capture_id": sha, "ref_id": ref_id, "kind": kind,
        "path": str(path.relative_to(config.DATA)).replace("\\", "/"),
        "bytes": str(st.st_size), "ext": path.suffix.lstrip("."),
        "mime": _mime(path.suffix), "captured_at": _now(),
        "capture_method": method, "archive_url": archive_url,
        "archive_ts": archive_ts, "status": "active",
    })
    store.append_rows("captures", [row], schema.CAPTURE_COLS, con=con)
    return True


def add_link(ref_id: str, key_type: str, entity_key: str, role: str, con,
             added_by: str = ADDED_BY_DEFAULT) -> bool:
    rows = (store.read_table("reference_links", con=con)
            if store.has_table("reference_links", con) else [])
    if any(r["ref_id"] == ref_id and r["key_type"] == key_type
           and r["entity_key"] == entity_key and r["role"] == role for r in rows):
        return False
    store.append_rows("reference_links", [{
        "ref_id": ref_id, "key_type": key_type, "entity_key": entity_key,
        "role": role, "added_at": _now(), "added_by": added_by,
    }], schema.REFERENCE_LINK_COLS, con=con)
    return True


def _mime(suffix: str) -> str:
    return {
        ".pdf": "application/pdf", ".html": "text/html", ".htm": "text/html",
        ".txt": "text/plain", ".mp4": "video/mp4", ".srt": "text/plain",
        ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
    }.get(suffix.lower(), "application/octet-stream")


def _ledger(command: str, params: dict, metrics: dict, status: str = "ok") -> str:
    run = results.start("library", command, list(_LEDGER_INPUTS), params=params)
    for name, value in metrics.items():
        run.metric("library", name, value)
    return results.finish(run, status=status)


# ---------------------------------------------------------------- commands

def retire_capture(capture_id: str, reason: str, con=None) -> int:
    con = con or store.connect()
    rows = store.read_table("captures", con=con)
    n = 0
    for r in rows:
        if r["capture_id"].startswith(capture_id) and r["status"] == "active":
            r["status"], r["status_reason"] = "retired", reason
            n += 1
    if n:
        store.write_table("captures", rows, schema.CAPTURE_COLS, con=con)
    return n


def dedupe_candidates(con=None) -> list[tuple[str, str, str]]:
    """(ref_a, ref_b, why) pairs by fuzzy title + same date + same publisher/author."""
    con = con or store.connect()
    rows = [r for r in _refs(con) if r["status"] == "active" and not r["merged_into"]]
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            ta, tb = a["title"].lower().strip(), b["title"].lower().strip()
            if not ta or not tb:
                continue
            same_title = ta == tb or (len(ta) > 20 and (ta in tb or tb in ta))
            same_date = a["published_at"] and a["published_at"] == b["published_at"]
            same_pub = (a["publisher"] and a["publisher"].lower() == b["publisher"].lower()) or \
                       (a["authors"] and a["authors"].lower() == b["authors"].lower())
            if same_title and same_date and same_pub:
                out.append((a["ref_id"], b["ref_id"], f"title+date+publisher: {a['title'][:60]}"))
    return out


def merge_references(keep: str, retire: str, con=None) -> None:
    """Move captures and links from `retire` onto `keep`; retire with merged_into."""
    con = con or store.connect()
    caps = store.read_table("captures", con=con)
    moved_caps = 0
    for r in caps:
        if r["ref_id"] == retire:
            if any(c["capture_id"] == r["capture_id"] and c["ref_id"] == keep for c in caps):
                r["status"], r["status_reason"] = "retired", f"merged into {keep}"
            else:
                r["ref_id"] = keep
                moved_caps += 1
    store.write_table("captures", caps, schema.CAPTURE_COLS, con=con)
    links = store.read_table("reference_links", con=con)
    kept = {(x["key_type"], x["entity_key"], x["role"]) for x in links if x["ref_id"] == keep}
    out = []
    for x in links:
        if x["ref_id"] == retire:
            if (x["key_type"], x["entity_key"], x["role"]) in kept:
                continue
            x["ref_id"] = keep
        out.append(x)
    store.write_table("reference_links", out, schema.REFERENCE_LINK_COLS, con=con)
    refs = store.read_table("references", con=con)
    for r in refs:
        if r["ref_id"] == retire:
            r["status"], r["merged_into"] = "retired", keep
    store.write_table("references", refs, schema.REFERENCE_COLS, con=con)
    print(f"merged {retire} -> {keep} ({moved_caps} captures moved)")


def manifest(con=None) -> Path:
    """BagIt-style fixity list over the store + row exports."""
    con = con or store.connect()
    lines = []
    for p in sorted(library_root().rglob("*")):
        if p.is_file():
            lines.append(f"{sha256_file(p)}  {p.relative_to(library_root()).as_posix()}")
    out = library_root() / "manifest-sha256.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    exp = config.EXPORTS / "library"
    exp.mkdir(parents=True, exist_ok=True)
    for t in ("references", "captures", "reference_links"):
        if store.has_table(t, con):
            store.export_csv(t, exp / f"{t}.csv", con=con)
    print(f"manifest: {len(lines)} files -> {out}")
    return out


def verify(con=None) -> int:
    """Re-hash every store file against the manifest and the captures table.
    Returns the number of problems found (0 = clean)."""
    con = con or store.connect()
    problems = 0
    mpath = library_root() / "manifest-sha256.txt"
    listed = {}
    if mpath.exists():
        for line in mpath.read_text(encoding="utf-8").splitlines():
            if line.strip():
                sha, rel = line.split(None, 1)
                listed[rel.strip()] = sha
    for rel, sha in listed.items():
        p = library_root() / rel
        if not p.exists():
            print(f"MISSING {rel}")
            problems += 1
        elif sha256_file(p) != sha:
            print(f"ALTERED {rel}")
            problems += 1
    for r in (store.read_table("captures", con=con) if store.has_table("captures", con) else []):
        p = config.DATA / r["path"]
        if not p.exists():
            print(f"MISSING capture file {r['path']}")
            problems += 1
        elif sha256_file(p) != r["capture_id"]:
            print(f"ALTERED capture file {r['path']}")
            problems += 1
    print(f"verify: {problems} problems")
    return problems


def merge_from(folder: Path, con=None) -> None:
    """Merge another machine's library folder + exports (USB reconciliation)."""
    con = con or store.connect()
    folder = Path(folder)
    copied = 0
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.name != "manifest-sha256.txt" and not p.name.endswith(".csv"):
            sha = sha256_file(p)
            dst = store_path(sha, p.suffix.lower())
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
                copied += 1
    refs_csv = folder / "references.csv"
    new_refs = new_caps = new_links = 0
    idmap: dict[str, str] = {}
    if refs_csv.exists():
        _, rrows = store.read_csv_rows(refs_csv)
        for r in rrows:
            rid, created = upsert_reference(r, con)
            idmap[r["ref_id"]] = rid
            new_refs += int(created)
        _, crows = store.read_csv_rows(folder / "captures.csv")
        for r in crows:
            rid = idmap.get(r["ref_id"], r["ref_id"])
            p = store_path(r["capture_id"], "." + r["ext"] if r["ext"] else "")
            if p.exists():
                new_caps += int(add_capture(rid, r["capture_id"], p, r["kind"],
                                            r["capture_method"] or "merge", con))
        _, lrows = store.read_csv_rows(folder / "reference_links.csv")
        for r in lrows:
            rid = idmap.get(r["ref_id"], r["ref_id"])
            new_links += int(add_link(rid, r["key_type"], r["entity_key"], r["role"], con,
                                      added_by=r.get("added_by", "merge")))
    _ledger(f"library merge {folder}", {"folder": str(folder)},
            {"files_copied": copied, "references_new": new_refs,
             "captures_new": new_caps, "links_new": new_links})
    print(f"merge: {copied} files copied, {new_refs} references, "
          f"{new_caps} captures, {new_links} links added")


# ---------------------------------------------------------------- navigation

def find_rows(con=None, entity: str = "", ref_type: str = "", text: str = "",
              publisher: str = "", since: str = "") -> list[dict]:
    con = con or store.connect()
    refs = [r for r in _refs(con) if r["status"] == "active"]
    if entity:
        links = store.read_table("reference_links", con=con)
        keep = {x["ref_id"] for x in links if x["entity_key"] == entity}
        refs = [r for r in refs if r["ref_id"] in keep]
    if ref_type:
        refs = [r for r in refs if r["ref_type"] == ref_type]
    if publisher:
        refs = [r for r in refs if publisher.lower() in r["publisher"].lower()]
    if since:
        refs = [r for r in refs if r["published_at"] >= since]
    if text:
        t = text.lower()
        refs = [r for r in refs if t in r["title"].lower() or t in r["note"].lower()]
    return sorted(refs, key=lambda r: r["published_at"] or r["accessed_at"], reverse=True)


def show(ref_prefix: str, con=None) -> None:
    con = con or store.connect()
    for r in _refs(con):
        if r["ref_id"].startswith(ref_prefix):
            for k in schema.REFERENCE_COLS:
                if r[k]:
                    print(f"  {k}: {r[k]}")
            for c in store.read_table("captures", con=con):
                if c["ref_id"] == r["ref_id"]:
                    print(f"  capture {c['capture_id'][:12]} {c['kind']} "
                          f"{c['status']} {c['path']}")
            for x in store.read_table("reference_links", con=con):
                if x["ref_id"] == r["ref_id"]:
                    print(f"  link {x['key_type']}:{x['entity_key']} ({x['role']})")
            return
    print("not found")


def open_ref(ref_prefix: str, con=None) -> None:
    con = con or store.connect()
    for c in store.read_table("captures", con=con):
        if (c["ref_id"].startswith(ref_prefix) or c["capture_id"].startswith(ref_prefix)) \
                and c["status"] == "active":
            p = config.DATA / c["path"]
            print(f"opening {p}")
            if sys.platform == "win32":
                import os
                os.startfile(p)  # noqa: S606
            else:
                subprocess.run(["xdg-open", str(p)], check=False)  # noqa: S603,S607
            return
    print("no active capture")


def view_entity(entity: str, con=None) -> Path:
    """Disposable Explorer folder for one entity (P16: exports are disposable)."""
    con = con or store.connect()
    out = config.EXPORTS / "library" / entity
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    caps = store.read_table("captures", con=con)
    index = ["ref_id,capture_id,file,title,ref_type,publisher,published_at"]
    for r in find_rows(con, entity=entity):
        for c in caps:
            if c["ref_id"] == r["ref_id"] and c["status"] == "active":
                safe = "".join(ch if ch.isalnum() or ch in "._- " else "_"
                               for ch in (r["title"][:60] or r["ref_id"]))
                name = f"{r['published_at'] or 'nodate'}_{r['ref_type']}_{safe}.{c['ext']}".replace(" ", "_")
                src = config.DATA / c["path"]
                if src.exists():
                    shutil.copy2(src, out / name)
                index.append(",".join([r["ref_id"], c["capture_id"][:12], name,
                                       r["title"].replace(",", " "), r["ref_type"],
                                       r["publisher"].replace(",", " "), r["published_at"]]))
    (out / "index.csv").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"view: {len(index) - 1} files -> {out}")
    return out


def site(con=None) -> Path:
    """One self-contained HTML page over the whole index (report, disposable)."""
    con = con or store.connect()
    import html as _h
    import json
    refs = find_rows(con)
    links = store.read_table("reference_links", con=con) if store.has_table("reference_links", con) else []
    caps = store.read_table("captures", con=con) if store.has_table("captures", con) else []
    by_ref: dict[str, list] = {}
    for x in links:
        by_ref.setdefault(x["ref_id"], []).append(f"{x['entity_key']}({x['role']})")
    cap_by_ref: dict[str, list] = {}
    for c in caps:
        if c["status"] == "active":
            cap_by_ref.setdefault(c["ref_id"], []).append(
                {"path": ("../../" + "bronze/library/" if False else "") + c["path"], "kind": c["kind"]})
    data = [{
        "id": r["ref_id"], "type": r["ref_type"], "title": r["title"] or r["url"],
        "publisher": r["publisher"], "date": r["published_at"],
        "entities": by_ref.get(r["ref_id"], []),
        "url": r["url"],
        "files": [{"href": "../../" + c["path"], "kind": c["kind"]}
                  for c in cap_by_ref.get(r["ref_id"], [])],
    } for r in refs]
    payload = _h.escape(json.dumps(data), quote=False)
    page = ("<!doctype html><meta charset='utf-8'><title>Research library</title>"
            "<style>body{font-family:sans-serif;margin:2em}input,select{margin:0 .5em .5em 0;"
            "padding:.3em}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;"
            "padding:.35em;text-align:left;font-size:14px}</style>"
            "<h1>Research library</h1>"
            "<input id=q placeholder='text'><input id=e placeholder='entity'>"
            "<select id=t><option value=''>any type</option>" +
            "".join(f"<option>{t}</option>" for t in schema.REF_TYPES) +
            "</select><span id=n></span>"
            "<table><thead><tr><th>date</th><th>type</th><th>title</th><th>publisher</th>"
            "<th>entities</th><th>files</th></tr></thead><tbody id=b></tbody></table>"
            f"<script>const D={payload};"
            "function esc(s){const d=document.createElement('span');d.textContent=s||'';"
            "return d.innerHTML}"
            "function row(r){const fs=r.files.map(f=>`<a href='${f.href}'>${f.kind}</a>`)"
            ".join(' ')+(r.url?` <a href='${esc(r.url)}'>source</a>`:'');"
            "return `<tr><td>${esc(r.date)}</td><td>${esc(r.type)}</td><td>${esc(r.title)}"
            "</td><td>${esc(r.publisher)}</td><td>${esc(r.entities.join(' '))}</td>"
            "<td>${fs}</td></tr>`}"
            "function go(){const q=document.getElementById('q').value.toLowerCase(),"
            "e=document.getElementById('e').value.toLowerCase(),"
            "t=document.getElementById('t').value;const rows=D.filter(r=>"
            "(!q||(r.title+' '+r.publisher).toLowerCase().includes(q))&&"
            "(!e||r.entities.join(' ').toLowerCase().includes(e))&&(!t||r.type===t));"
            "document.getElementById('b').innerHTML=rows.map(row).join('');"
            "document.getElementById('n').textContent=rows.length+' / '+D.length}"
            "for(const id of['q','e','t'])document.getElementById(id)"
            ".addEventListener('input',go);go();</script>")
    out = config.EXPORTS / "library_site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"site: {len(data)} references -> {out}")
    return out


# ---------------------------------------------------------------- CLI

def _flags(argv: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    pos, flags, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags.setdefault(key, []).append(argv[i + 1])
                i += 2
            else:
                flags.setdefault(key, []).append("")
                i += 1
        else:
            pos.append(a)
            i += 1
    return pos, flags


def _one(flags: dict, key: str, default: str = "") -> str:
    return flags.get(key, [default])[0]


def cli(argv: list[str]) -> int:
    """`python -m biointel library <sub> ...` — see GATEL1 runbook §4."""
    from . import collectors
    if not argv:
        print(cli.__doc__)
        return 1
    sub, rest = argv[0], argv[1:]
    con = store.connect()
    schema_tables = ("references", "captures", "reference_links")
    for t in schema_tables:  # create-on-first-use with the declared header
        if not store.has_table(t, con):
            store.write_table(t, [], getattr(schema, {
                "references": "REFERENCE_COLS", "captures": "CAPTURE_COLS",
                "reference_links": "REFERENCE_LINK_COLS"}[t]), con=con)
    pos, flags = _flags(rest)
    if sub == "add":
        return collectors.manual.add(pos, flags, con)
    if sub == "import":
        return collectors.folder.run(pos, flags, con)
    if sub == "index":
        return collectors.pipeline_docs.run(con)
    if sub == "import-zotero":
        return collectors.zotero.run(flags, con)
    if sub == "find":
        for r in find_rows(con, entity=_one(flags, "entity"), ref_type=_one(flags, "type"),
                           text=_one(flags, "text"), publisher=_one(flags, "publisher"),
                           since=_one(flags, "since")):
            print(f"{r['ref_id'][:12]}  {r['published_at'] or '----------'}  "
                  f"{r['ref_type']:16} {r['title'][:70] or r['url'][:70]}")
        return 0
    if sub == "list":
        return cli(["find"] + rest)
    if sub == "show":
        show(pos[0], con)
        return 0
    if sub == "open":
        open_ref(pos[0], con)
        return 0
    if sub == "view":
        view_entity(_one(flags, "entity") or pos[0], con)
        return 0
    if sub == "site":
        site(con)
        return 0
    if sub == "manifest":
        manifest(con)
        return 0
    if sub == "verify":
        return 1 if verify(con) else 0
    if sub == "merge":
        merge_from(Path(pos[0]), con)
        return 0
    if sub == "retire-capture":
        n = retire_capture(pos[0], _one(flags, "reason", "retired by operator"), con)
        print(f"retired {n} capture rows")
        return 0
    if sub == "dedupe":
        cands = dedupe_candidates(con)
        if _one(flags, "merge"):
            keep, ret = _one(flags, "keep"), _one(flags, "merge")
            merge_references(keep, ret, con)
            return 0
        for a, b, why in cands:
            print(f"{a[:12]}  {b[:12]}  {why}")
        print(f"{len(cands)} candidate pairs (confirm with: library dedupe "
              f"--keep <ref> --merge <ref>)")
        return 0
    print(f"unknown library subcommand: {sub}")
    return 1
