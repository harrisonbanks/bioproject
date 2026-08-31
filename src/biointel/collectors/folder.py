# src/biointel/collectors/folder.py
"""Folder collector: `library import <folder>` — one reference per file."""

from __future__ import annotations

from pathlib import Path

from .. import library, results

_TYPE_BY_EXT = {".pdf": "other", ".html": "web_page", ".htm": "web_page",
                ".txt": "other", ".mp4": "video", ".srt": "video"}
_KIND_BY_EXT = {".pdf": "uploaded_file", ".html": "uploaded_file", ".htm": "uploaded_file",
                ".txt": "uploaded_file", ".mp4": "media_file", ".srt": "captions"}


def run(pos: list[str], flags: dict, con) -> int:
    if not pos:
        print("usage: library import <folder> [--type T] [--entity K]...")
        return 1
    root = Path(pos[0])
    if not root.is_dir():
        print(f"no such folder: {root}")
        return 1
    ref_type = flags.get("type", [""])[0]
    entities = [e for e in flags.get("entity", []) if e]
    run_ = results.start("library", f"library import {root}",
                         ["silver:references", "silver:captures", "silver:reference_links"])
    n_ref = n_cap = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        sha, dst, _new = library.put_file(p)
        fields = {"ref_type": ref_type or _TYPE_BY_EXT.get(p.suffix.lower(), "other"),
                  "title": p.stem, "source_system": "folder", "source_key": sha}
        ref_id, created = library.upsert_reference(fields, con)
        n_ref += int(created)
        n_cap += int(library.add_capture(
            ref_id, sha, dst, _KIND_BY_EXT.get(p.suffix.lower(), "uploaded_file"),
            "folder import", con))
        for ent in entities:
            kt = "CIK" if ent.isdigit() else "IID"
            library.add_link(ref_id, kt, ent, "subject", con)
    run_.metric("library", "references_new", n_ref)
    run_.metric("library", "captures_new", n_cap)
    results.finish(run_)
    print(f"import: {n_ref} references, {n_cap} captures from {root}")
    return 0
