# tests/unit/test_library.py
"""Gate L1: research library / file room (Ontology v5 §3.9)."""

import json

import pytest

from biointel import config, library, schema, store


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "bronze").mkdir(parents=True)
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(config, "BRONZE", data / "bronze")
    monkeypatch.setattr(config, "DUCKDB", data / "biointel.duckdb")
    monkeypatch.setattr(config, "EXPORTS", data / "exports")
    store.close()
    con = store.connect(config.DUCKDB)
    for t, cols in (
        ("references", schema.REFERENCE_COLS),
        ("captures", schema.CAPTURE_COLS),
        ("reference_links", schema.REFERENCE_LINK_COLS),
    ):
        store.write_table(t, [], cols, con=con)
    yield con
    store.close()


def _mk(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_put_file_dedupes_bytes(env, tmp_path):
    a = _mk(tmp_path, "a.txt", "same bytes")
    b = _mk(tmp_path, "b.txt", "same bytes")
    sha1, p1, new1 = library.put_file(a)
    sha2, p2, new2 = library.put_file(b)
    assert sha1 == sha2 and p1 == p2 and new1 and not new2
    assert p1.parent.name == sha1[:2]


def test_norm_url_strips_tracking_and_case():
    u1 = "https://Example.com/News/story/?utm_source=x&id=7"
    u2 = "https://example.com/News/story?id=7"
    assert library.norm_url(u1) == library.norm_url(u2)


def test_upsert_ladder_attaches_by_accession(env):
    con = env
    r1, c1 = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": "0001234567890123",
            "url": "https://www.sec.gov/x",
            "title": "8-K",
        },
        con,
    )
    r2, c2 = library.upsert_reference(
        {
            "ref_type": "sec_filing",
            "sec_accession": "0001234567890123",
            "url": "https://other.example/mirror",
            "title": "8-K mirror",
        },
        con,
    )
    assert c1 and not c2 and r1 == r2
    assert len(store.read_table("references", con=con)) == 1


def test_capture_row_per_ref_same_bytes_once_on_disk(env, tmp_path):
    con = env
    f = _mk(tmp_path, "press.txt", "press release body")
    sha, dst, _ = library.put_file(f)
    ra, _ = library.upsert_reference(
        {"ref_type": "press_release", "title": "A", "url": "https://a.example/pr"}, con
    )
    rb, _ = library.upsert_reference(
        {"ref_type": "press_release", "title": "B", "url": "https://b.example/pr"}, con
    )
    assert library.add_capture(ra, sha, dst, "uploaded_file", "t", con)
    assert library.add_capture(rb, sha, dst, "uploaded_file", "t", con)
    assert not library.add_capture(ra, sha, dst, "uploaded_file", "t", con)
    files = [p for p in library.library_root().rglob("*") if p.is_file()]
    assert len(files) == 1
    assert len(store.read_table("captures", con=con)) == 2


def test_pipeline_index_idempotent(env, tmp_path):
    con = env
    src = config.BRONZE / "sec_filing_doc"
    src.mkdir(parents=True)
    for i, name in enumerate(["f1.txt", "f2.txt"]):
        (src / name).write_text(f"filing body {i}", encoding="utf-8")
        (src / f"{name}.meta.json").write_text(
            json.dumps(
                {
                    "url": f"https://www.sec.gov/Archives/edgar/data/32003{i}/000119312526000{i}11/doc.htm",
                    "fetched_at": "2026-08-29T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
    from biointel.collectors import pipeline_docs

    assert pipeline_docs.run(con) == 0
    refs = store.read_table("references", con=con)
    caps = store.read_table("captures", con=con)
    links = store.read_table("reference_links", con=con)
    assert len(refs) == 2 and len(caps) == 2 and len(links) == 2
    assert all(r["ref_type"] == "sec_filing" and r["sec_accession"] for r in refs)
    assert pipeline_docs.run(con) == 0
    assert len(store.read_table("references", con=con)) == 2
    assert len(store.read_table("captures", con=con)) == 2


def test_manual_add_file_and_no_fetch(env, tmp_path):
    con = env
    pdfish = tmp_path / "note.pdf"
    pdfish.write_bytes(b"%PDF-1.4 fake")
    from biointel.collectors import manual

    rc = manual.add(
        [str(pdfish)], {"type": ["analyst_note"], "title": ["Note"], "entity": ["320193"]}, con
    )
    assert rc == 0
    rc = manual.add(
        ["https://example.com/story"],
        {"type": ["news_article"], "no-fetch": [""], "title": ["Story"], "entity": ["TEMPUS"]},
        con,
    )
    assert rc == 0
    refs = store.read_table("references", con=con)
    caps = store.read_table("captures", con=con)
    links = store.read_table("reference_links", con=con)
    assert len(refs) == 2 and len(caps) == 1
    nf = [r for r in refs if r["ref_type"] == "news_article"][0]
    assert not any(c["ref_id"] == nf["ref_id"] for c in caps)  # visibly no copy
    assert {(x["key_type"], x["entity_key"]) for x in links} == {
        ("CIK", "320193"),
        ("IID", "TEMPUS"),
    }


def test_retire_capture_keeps_file(env, tmp_path):
    con = env
    f = _mk(tmp_path, "x.txt", "body")
    sha, dst, _ = library.put_file(f)
    r, _ = library.upsert_reference(
        {"ref_type": "other", "title": "X", "url": "https://x.example/1"}, con
    )
    library.add_capture(r, sha, dst, "uploaded_file", "t", con)
    assert library.retire_capture(sha[:12], "ad noise", con) == 1
    row = store.read_table("captures", con=con)[0]
    assert row["status"] == "retired" and row["status_reason"] == "ad noise"
    assert dst.exists()


def test_dedupe_merge_moves_and_resolves(env, tmp_path):
    con = env
    a, _ = library.upsert_reference(
        {
            "ref_type": "news_article",
            "title": "Tempus buys Personalis",
            "published_at": "2026-07-20",
            "publisher": "Reuters",
            "url": "https://r.example/1",
        },
        con,
    )
    b, _ = library.upsert_reference(
        {
            "ref_type": "news_article",
            "title": "Tempus buys Personalis",
            "published_at": "2026-07-20",
            "publisher": "Reuters",
            "url": "https://amp.r.example/1x",
        },
        con,
    )
    f = _mk(tmp_path, "amp.html", "<html>story</html>")
    sha, dst, _ = library.put_file(f)
    library.add_capture(b, sha, dst, "fetched_html", "t", con)
    library.add_link(b, "IID", "TEMPUS", "acquirer", con)
    cands = library.dedupe_candidates(con)
    assert (a, b, cands[0][2]) == cands[0][:2] + (cands[0][2],) and len(cands) == 1
    library.merge_references(a, b, con)
    caps = store.read_table("captures", con=con)
    assert caps[0]["ref_id"] == a
    links = store.read_table("reference_links", con=con)
    assert links[0]["ref_id"] == a
    assert library.resolve(b, con) == a
    refs = {r["ref_id"]: r for r in store.read_table("references", con=con)}
    assert refs[b]["status"] == "retired" and refs[b]["merged_into"] == a


def test_manifest_and_verify_detect_tamper(env, tmp_path, capsys):
    con = env
    f = _mk(tmp_path, "doc.txt", "original")
    sha, dst, _ = library.put_file(f)
    r, _ = library.upsert_reference(
        {"ref_type": "other", "title": "D", "url": "https://d.example/1"}, con
    )
    library.add_capture(r, sha, dst, "uploaded_file", "t", con)
    library.manifest(con)
    assert library.verify(con) == 0
    dst.write_text("tampered", encoding="utf-8")
    assert library.verify(con) >= 2  # manifest line + capture row both fail
    capsys.readouterr()


def test_merge_from_other_machine(env, tmp_path):
    con = env
    r, _ = library.upsert_reference(
        {"ref_type": "press_release", "title": "Here", "url": "https://h.example/1"}, con
    )
    other = tmp_path / "usb"
    (other / "ab").mkdir(parents=True)
    payload = b"remote press release"
    import hashlib

    sha = hashlib.sha256(payload).hexdigest()
    (other / sha[:2]).mkdir(exist_ok=True)
    (other / sha[:2] / f"{sha}.txt").write_bytes(payload)
    hdr = ",".join(schema.REFERENCE_COLS)
    row = {c: "" for c in schema.REFERENCE_COLS}
    row.update(
        {
            "ref_id": "Rremote0000000001",
            "ref_type": "press_release",
            "title": "Remote",
            "url": "https://remote.example/pr",
            "status": "active",
            "source_system": "library_add",
        }
    )
    (other / "references.csv").write_text(
        hdr + "\n" + ",".join(row[c] for c in schema.REFERENCE_COLS) + "\n", encoding="utf-8"
    )
    crow = {c: "" for c in schema.CAPTURE_COLS}
    crow.update(
        {
            "capture_id": sha,
            "ref_id": "Rremote0000000001",
            "kind": "fetched_text",
            "path": f"bronze/library/{sha[:2]}/{sha}.txt",
            "bytes": str(len(payload)),
            "ext": "txt",
            "capture_method": "library add",
            "status": "active",
        }
    )
    (other / "captures.csv").write_text(
        ",".join(schema.CAPTURE_COLS)
        + "\n"
        + ",".join(crow[c] for c in schema.CAPTURE_COLS)
        + "\n",
        encoding="utf-8",
    )
    (other / "reference_links.csv").write_text(
        ",".join(schema.REFERENCE_LINK_COLS) + "\n", encoding="utf-8"
    )
    library.merge_from(other, con)
    refs = store.read_table("references", con=con)
    caps = store.read_table("captures", con=con)
    assert len(refs) == 2 and len(caps) == 1
    assert library.store_path(sha, ".txt").exists()
    library.merge_from(other, con)  # idempotent
    assert len(store.read_table("references", con=con)) == 2
    assert len(store.read_table("captures", con=con)) == 1


def test_cli_find_and_site(env, capsys):
    con = env
    library.upsert_reference(
        {
            "ref_type": "news_article",
            "title": "MRD market grows",
            "publisher": "MedTech Dive",
            "published_at": "2026-07-01",
            "url": "https://m.example/1",
        },
        con,
    )
    rows = library.find_rows(con, text="mrd")
    assert len(rows) == 1 and rows[0]["publisher"] == "MedTech Dive"
    out = library.site(con)
    assert out.exists() and "MRD market grows" in out.read_text(encoding="utf-8")
    capsys.readouterr()


def test_manifest_excludes_itself_and_verify_stays_clean_on_rerun(env, tmp_path):
    con = env
    f = tmp_path / "doc.txt"
    f.write_text("hello", encoding="utf-8")
    sha, dst, _ = library.put_file(f)
    ref_id, _ = library.upsert_reference(
        {"ref_type": "other", "title": "t", "url": "https://x/y"}, con
    )
    library.add_capture(ref_id, sha, dst, "uploaded_file", "test", con)
    library.manifest(con)
    m2 = library.manifest(con)  # second run must not flag the first manifest as altered
    text = m2.read_text(encoding="utf-8")
    assert "manifest-sha256.txt" not in text
    assert text.count("\n") == 1  # exactly one stored file listed
    assert library.verify(con) == 0
