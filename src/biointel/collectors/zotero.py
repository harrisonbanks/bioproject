# src/biointel/collectors/zotero.py
"""Zotero collector: `library import-zotero` — read the local Zotero API
(read-only, Zotero must be running; pyzotero optional extra [zotero]) and copy
items + attachments into the store. Skipped gracefully when unavailable."""

from __future__ import annotations

from pathlib import Path

from .. import library, results

_TYPE_MAP = {
    "journalArticle": "research_paper", "preprint": "research_paper",
    "newspaperArticle": "news_article", "magazineArticle": "news_article",
    "blogPost": "web_page", "webpage": "web_page", "report": "analyst_note",
    "presentation": "transcript", "videoRecording": "video",
    "document": "other", "book": "book",
}


def run(flags: dict, con) -> int:
    try:
        from pyzotero import zotero  # type: ignore
    except ImportError:
        print("pyzotero not installed; run: pip install -e \".[zotero]\" — skipped")
        return 0
    data_dir = Path(flags.get("data-dir", [str(Path.home() / "Zotero")])[0])
    try:
        zot = zotero.Zotero("0", "user", "", local=True)
        items = zot.everything(zot.top())
    except Exception as e:  # noqa: BLE001 - any local-API failure means "not running"
        print(f"Zotero local API not reachable ({e.__class__.__name__}); "
              "start Zotero and retry — skipped")
        return 0
    run_ = results.start("library", "library import-zotero",
                         ["silver:references", "silver:captures", "silver:reference_links"])
    n_ref = n_cap = n_link = 0
    for it in items:
        d = it.get("data", {})
        if d.get("itemType") in ("attachment", "note"):
            continue
        fields = {
            "ref_type": _TYPE_MAP.get(d.get("itemType", ""), "other"),
            "url": d.get("url", ""), "doi": d.get("DOI", ""),
            "title": d.get("title", ""), "publisher": d.get("publicationTitle",
                                                            d.get("websiteTitle", "")),
            "authors": "; ".join(c.get("lastName", "") for c in d.get("creators", [])),
            "published_at": (d.get("date", "") or "")[:10],
            "source_system": "zotero", "source_key": it.get("key", ""),
        }
        ref_id, created = library.upsert_reference(fields, con)
        n_ref += int(created)
        for tag in d.get("tags", []):
            t = tag.get("tag", "")
            if t.startswith(("IID:", "CIK:")):
                kt, _, key = t.partition(":")
                n_link += int(library.add_link(ref_id, kt, key, "subject", con,
                                               added_by="zotero"))
        for ch in zot.children(it.get("key", "")):
            cd = ch.get("data", {})
            if cd.get("itemType") != "attachment" or not cd.get("filename"):
                continue
            fpath = data_dir / "storage" / ch["key"] / cd["filename"]
            if fpath.exists():
                sha, dst, _new = library.put_file(fpath)
                kind = "fetched_pdf" if fpath.suffix.lower() == ".pdf" else "fetched_html"
                n_cap += int(library.add_capture(ref_id, sha, dst, kind,
                                                 "zotero import", con))
    run_.metric("library", "references_new", n_ref)
    run_.metric("library", "captures_new", n_cap)
    run_.metric("library", "links_new", n_link)
    results.finish(run_)
    print(f"import-zotero: {n_ref} references, {n_cap} captures, {n_link} links added")
    return 0
