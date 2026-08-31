# src/biointel/collectors/pipeline_docs.py
"""Pipeline collector: `library index` — copy the sec_filing_doc cache into
the store as references + captures (Ontology v5 §3.9; idempotent)."""

from __future__ import annotations

import json
import re

from .. import config, library, results

_ACC_RE = re.compile(r"/edgar/data/(\d+)/(\d{10}-?\d{2}-?\d{6})/")


def run(con) -> int:
    src = config.BRONZE / "sec_filing_doc"
    if not src.is_dir():
        print(f"nothing to index: {src} absent")
        return 0
    run_ = results.start("library", "library index",
                         ["silver:references", "silver:captures", "silver:reference_links"])
    n_ref = n_cap = n_link = n_seen = 0
    patch: dict[str, tuple[str, str]] = {}
    for p in sorted(src.glob("*.txt")):
        n_seen += 1
        meta = {}
        mp = next((c for c in (p.with_suffix(p.suffix + ".meta.json"),
                                p.with_suffix(".meta.json"),
                                p.with_name(p.name + ".meta.json")) if c.exists()), None)
        if mp is not None:
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta = {}
        url = str(meta.get("url", ""))
        m = _ACC_RE.search(url)
        cik = m.group(1) if m else ""
        acc = m.group(2).replace("-", "") if m else ""
        sha, dst, _new = library.put_file(p)
        fields = {
            "ref_type": "sec_filing", "url": url, "sec_accession": acc,
            "title": p.stem, "publisher": "SEC EDGAR",
            "accessed_at": str(meta.get("fetched_at", meta.get("time", ""))),
            "source_system": "pipeline", "source_key": p.name,
        }
        ref_id, created = library.upsert_reference(fields, con)
        n_ref += int(created)
        if not created and url:
            patch.setdefault(ref_id, (url, acc))
        n_cap += int(library.add_capture(ref_id, sha, dst, "fetched_text",
                                         "pipeline fetch", con))
        if cik:
            n_link += int(library.add_link(ref_id, "CIK", cik, "subject", con,
                                           added_by="pipeline"))
    if patch:
        from .. import schema, store
        rows = store.read_table("references", con=con)
        for r in rows:
            if r["ref_id"] in patch and not r["url"]:
                r["url"], r["sec_accession"] = patch[r["ref_id"]]
        store.write_table("references", rows, schema.REFERENCE_COLS, con=con)
    run_.metric("library", "files_seen", n_seen)
    run_.metric("library", "references_new", n_ref)
    run_.metric("library", "captures_new", n_cap)
    run_.metric("library", "links_new", n_link)
    results.finish(run_)
    print(f"index: {n_seen} files seen; {n_ref} references, {n_cap} captures, "
          f"{n_link} links added")
    return 0
