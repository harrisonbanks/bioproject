# src/biointel/collectors/manual.py
"""Manual collector: `library add <url-or-file> ...` (Ontology v5 §3.9)."""

from __future__ import annotations

import time
from pathlib import Path

import requests

from .. import config, library, results, schema


def _fetch(url: str) -> tuple[bytes, str] | None:
    hdrs = {"User-Agent": config.require("BIOINTEL_USER_AGENT")}
    if "sec.gov" in url:
        time.sleep(config.SEC_RATE_LIMIT)
    r = requests.get(url, headers=hdrs, timeout=60)
    if r.status_code != 200:
        print(f"fetch failed ({r.status_code}); reference kept without capture")
        return None
    ctype = r.headers.get("content-type", "").split(";")[0].strip()
    ext = {"application/pdf": ".pdf", "text/html": ".html",
           "text/plain": ".txt"}.get(ctype, ".bin")
    return r.content, ext


_KIND_BY_EXT = {".pdf": "fetched_pdf", ".html": "fetched_html", ".htm": "fetched_html",
                ".txt": "fetched_text", ".mp4": "media_file", ".srt": "captions"}


def add(pos: list[str], flags: dict, con) -> int:
    if not pos:
        print("usage: library add <url-or-file> --type T [--entity K]... [--for REF]"
              " [--no-fetch] [--kind K] [--title ...] [--published YYYY-MM-DD]"
              " [--publisher ...] [--url U] [--note ...] [--subject S]")
        return 1
    target = pos[0]
    is_url = target.lower().startswith(("http://", "https://"))
    f = {k: v[0] for k, v in flags.items() if v and v[0]}
    fields = {
        "ref_type": f.get("type", "web_page" if is_url else "other"),
        "url": target if is_url else f.get("url", ""),
        "doi": f.get("doi", ""), "pmid": f.get("pmid", ""),
        "sec_accession": f.get("accession", ""),
        "title": f.get("title", "" if is_url else Path(target).stem),
        "authors": f.get("authors", ""), "publisher": f.get("publisher", ""),
        "published_at": f.get("published", ""), "access": f.get("access", ""),
        "note": f.get("note", ""), "source_system": "library_add", "source_key": "",
    }
    if fields["ref_type"] not in schema.REF_TYPES:
        print(f"unknown --type {fields['ref_type']}; one of {', '.join(schema.REF_TYPES)}")
        return 1
    run = results.start("library", f"library add {target}",
                        ["silver:references", "silver:captures", "silver:reference_links"])
    if f.get("for"):
        ref_id = library.resolve(_expand(f["for"], con), con)
        created = False
    else:
        ref_id, created = library.upsert_reference(fields, con)
    added_capture = False
    if not is_url:
        p = Path(target)
        if not p.exists():
            print(f"no such file: {p}")
            results.finish(run, status="error", note="file missing")
            return 1
        sha, dst, _new = library.put_file(p)
        kind = f.get("kind", "media_file" if p.suffix.lower() == ".mp4" else "captions" if p.suffix.lower() == ".srt" else "uploaded_file")
        added_capture = library.add_capture(ref_id, sha, dst, kind, "manual upload", con)
    elif "no-fetch" not in flags:
        got = _fetch(target)
        if got:
            data, ext = got
            sha, dst, _new = library.put_bytes(data, ext)
            kind = f.get("kind", _KIND_BY_EXT.get(ext, "fetched_html"))
            added_capture = library.add_capture(ref_id, sha, dst, kind, "library add", con)
    links = 0
    for ent in flags.get("entity", []):
        if ent:
            kt = "CIK" if ent.isdigit() else "IID"
            links += int(library.add_link(ref_id, kt, ent, f.get("role", "subject"), con))
    if f.get("subject"):
        fields["note"] = (fields["note"] + " | subject: " + f["subject"]).strip(" |")
    run.metric("library", "reference_created", int(created))
    run.metric("library", "capture_added", int(added_capture))
    run.metric("library", "links_added", links)
    results.finish(run)
    print(f"{'created' if created else 'existing'} reference {ref_id[:12]}; "
          f"capture {'added' if added_capture else 'none (no-op or no copy)'}; "
          f"{links} link(s)")
    return 0


def _expand(prefix: str, con) -> str:
    from ..library import _refs
    for r in _refs(con):
        if r["ref_id"].startswith(prefix):
            return r["ref_id"]
    return prefix
