"""Patent layer v2: firm-technology substrate from PatentsView BULK files.

WHY THE REWRITE. The operator probe of 2026-08-26 showed
search.patentsview.org no longer resolves: the PatentSearch API was shut
down on 2026-03-20 and PatentsView survives as bulk datasets on the
USPTO Open Data Portal (data.uspto.gov). The query-API route is dead;
the bulk-download route replaces it.

FILES NEEDED (classic PatentsView bulk schema, stable for years):
  g_patent.tsv.zip                 patent_id, patent_date, patent_title
  g_assignee_disambiguated.tsv.zip patent_id, disambig_assignee_organization
  g_cpc_current.tsv.zip            patent_id, cpc_subclass
These are LARGE (multi-GB total). Download is resumable; parsing is
streamed; nothing is held in memory beyond the matched-patent id map.

ROUTE UNCERTAINTY, probe-gated per rule 0.6.3. Two candidate hosts:
  (a) legacy S3: s3.amazonaws.com/data.patentsview.org/download/ --
      may or may not have survived the migration; cheapest if live.
  (b) ODP bulk products via api.uspto.gov (free key from MyUSPTO,
      pasted into ODP_API_KEY below) -- exact product URLs unknown
      until the listing is seen.
`patents-probe` tests (a) with a 4-byte ranged GET, falls back to
printing (b)'s product listing verbatim for repointing, and unlocks
`patents-ingest` only when a directly usable route is confirmed.

JOIN. Assignee organizations match companies.csv Name/FDAAliases via
match.canon() exact equality -- the pipeline's standard name join, so
failures are missing, never wrong.
"""
from __future__ import annotations
import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone

import requests

from .. import config
from ..match import canon

# --- operator-supplied credential (free, only needed if S3 is dead) --------
ODP_API_KEY = ""              # MyUSPTO free key; probe says if required

S3_BASE = "https://s3.amazonaws.com/data.patentsview.org/download/"
ODP_SEARCH = ("https://api.uspto.gov/api/v1/datasets/products/search"
              "?q=PatentsView")

BULK_FILES = {
    "g_patent.tsv.zip":                 ["patent_id", "patent_date",
                                         "patent_title"],
    "g_assignee_disambiguated.tsv.zip": ["patent_id",
                                         "disambig_assignee_organization"],
    "g_cpc_current.tsv.zip":            ["patent_id", "cpc_subclass"],
}

BULK_DIR = config.BRONZE / "patents_bulk"
PROBE_MARKER = BULK_DIR / "PROBE_OK"
PATENTS_CSV = config.SILVER / "patents.csv"
OUT_COLS = ["IID", "PatentId", "PatentDate", "CPCSubclass", "AssigneeRaw"]


# --------------------------------------------------------------------------
# probe
# --------------------------------------------------------------------------
def _ranged_head(url: str) -> tuple[int, bytes, str]:
    r = requests.get(url, headers={"User-Agent": config.USER_AGENT,
                                   "Range": "bytes=0-3"}, timeout=60)
    return r.status_code, r.content[:4], r.headers.get("Content-Length", "?")


def probe() -> dict:
    """Stage 1: is legacy S3 live? Stage 2: else print the ODP listing."""
    s3_url = S3_BASE + "g_patent.tsv.zip"
    try:
        status, magic, length = _ranged_head(s3_url)
        if status in (200, 206) and magic[:2] == b"PK":
            BULK_DIR.mkdir(parents=True, exist_ok=True)
            PROBE_MARKER.write_text(json.dumps(
                {"route": "s3", "date": date.today().isoformat()}))
            return {"status": "ok",
                    "message": f"S3 ROUTE LIVE: {s3_url} answered {status}, "
                               f"zip magic OK, range-length {length}. "
                               "`patents-ingest` is now unlocked "
                               "(multi-GB download, resume-safe)."}
        s3_note = (f"S3 answered {status} with head {magic!r} -- not a "
                   "usable zip.")
    except Exception as exc:
        s3_note = f"S3 unreachable: {exc}."

    try:
        hdrs = {"User-Agent": config.USER_AGENT}
        if ODP_API_KEY:
            hdrs["X-API-KEY"] = ODP_API_KEY
        r = requests.get(ODP_SEARCH, headers=hdrs, timeout=60)
        head = r.text[:2000]
        auth_hint = ("" if ODP_API_KEY else
                     " (No ODP_API_KEY set -- if this is an auth error, get "
                     "a free key via MyUSPTO/data.uspto.gov and paste it "
                     "into ODP_API_KEY in biointel/sources/patents.py.)")
        return {"status": "fail",
                "message": f"{s3_note}\nODP LISTING (status {r.status_code})"
                           f"{auth_hint} -- paste this WHOLE output back so "
                           f"the exact product URLs are wired in:\n{head}"}
    except Exception as exc:
        return {"status": "fail",
                "message": f"{s3_note}\nODP also failed: {exc}. Paste this "
                           "output back."}


# --------------------------------------------------------------------------
# resumable download
# --------------------------------------------------------------------------
def _download_resumable(fname: str) -> None:
    BULK_DIR.mkdir(parents=True, exist_ok=True)
    dest = BULK_DIR / fname
    done = dest.with_suffix(dest.suffix + ".done")
    if done.exists():
        return
    have = dest.stat().st_size if dest.exists() else 0
    hdrs = {"User-Agent": config.USER_AGENT}
    if have:
        hdrs["Range"] = f"bytes={have}-"
    with requests.get(S3_BASE + fname, headers=hdrs, stream=True,
                      timeout=300) as r:
        if have and r.status_code == 200:      # server ignored Range
            have = 0
        r.raise_for_status()
        mode = "ab" if have else "wb"
        with dest.open(mode) as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    done.write_text(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    print(f"  downloaded {fname}: {dest.stat().st_size:,} bytes")


# --------------------------------------------------------------------------
# streaming parse
# --------------------------------------------------------------------------
def _rows(zip_path, needed: list[str]):
    """Yield dicts of the needed columns from the single TSV member.
    Aborts loudly, echoing the REAL header, if expected columns are
    absent -- the counterparty lesson applied to file schemas."""
    with zipfile.ZipFile(zip_path) as zf:
        member = next(m for m in zf.namelist() if m.endswith(".tsv"))
        with zf.open(member) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace",
                                    newline="")
            rd = csv.reader(text, delimiter="\t")
            header = next(rd)
            header = [h.strip().strip('"') for h in header]
            missing = [c for c in needed if c not in header]
            if missing:
                raise RuntimeError(
                    f"HEADER MISMATCH in {zip_path.name}: need {needed}, "
                    f"missing {missing}. REAL header follows -- paste back "
                    f"so column names are corrected:\n{header}")
            idx = {c: header.index(c) for c in needed}
            for vals in rd:
                if len(vals) < len(header):
                    continue
                yield {c: vals[i].strip().strip('"') for c, i in idx.items()}


def _company_canon_map() -> dict[str, tuple[str, str]]:
    """canon(name/alias) -> (IID, display name) from companies.csv."""
    out: dict[str, tuple[str, str]] = {}
    with config.COMPANIES_CSV.open(encoding="utf-8", newline="",
                                   errors="replace") as f:
        for r in csv.DictReader(f):
            iid, name = r.get("IID", ""), r.get("Name", "")
            if not iid:
                continue
            for nm in [name] + [a.strip() for a in
                                (r.get("FDAAliases") or "").split(";")]:
                c = canon(nm)
                if c and c not in out:
                    out[c] = (iid, name)
    return out


def build_from_local(paths: dict) -> dict:
    """Assemble silver/patents.csv from the three local bulk zips.
    paths: {filename: Path}. Separated from download for offline testing
    through the real parse path."""
    cmap = _company_canon_map()

    # pass 1: assignees -> matched patent ids
    pat_iid: dict[str, tuple[str, str]] = {}
    n_assign = 0
    for r in _rows(paths["g_assignee_disambiguated.tsv.zip"],
                   BULK_FILES["g_assignee_disambiguated.tsv.zip"]):
        n_assign += 1
        hit = cmap.get(canon(r["disambig_assignee_organization"]))
        if hit:
            pat_iid[r["patent_id"]] = (hit[0],
                                       r["disambig_assignee_organization"])
    # pass 2: dates for matched ids
    pat_date: dict[str, str] = {}
    for r in _rows(paths["g_patent.tsv.zip"],
                   BULK_FILES["g_patent.tsv.zip"]):
        if r["patent_id"] in pat_iid:
            pat_date[r["patent_id"]] = r["patent_date"]
    # pass 3: CPC rows for matched ids, written streaming
    n_out = 0
    PATENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PATENTS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        w.writeheader()
        for r in _rows(paths["g_cpc_current.tsv.zip"],
                       BULK_FILES["g_cpc_current.tsv.zip"]):
            hit = pat_iid.get(r["patent_id"])
            if not hit:
                continue
            w.writerow({"IID": hit[0], "PatentId": r["patent_id"],
                        "PatentDate": pat_date.get(r["patent_id"], ""),
                        "CPCSubclass": r["cpc_subclass"],
                        "AssigneeRaw": hit[1]})
            n_out += 1
    firms = len({v[0] for v in pat_iid.values()})
    return {"status": "ok",
            "message": f"patents.csv: {n_out:,} patent-CPC rows, "
                       f"{len(pat_iid):,} matched patents across {firms} "
                       f"companies (scanned {n_assign:,} assignee rows) "
                       f"-> {PATENTS_CSV}"}


# --------------------------------------------------------------------------
# BigQuery route (Google Patents Public Datasets) -- keyless for the
# operator beyond an existing Google login. `patents-sql` writes a query
# generated from the operator's own company names; the operator runs it
# in the BigQuery console and exports the result; `patents-import`
# consumes that export. Matching happens on a canon() key computed
# IDENTICALLY on both sides: Python emits the key list from match.canon,
# and the SQL reproduces canon (uppercase, punctuation to space, & to
# AND, strip the same legal-suffix/descriptor word list, collapse
# whitespace), so the round trip is deterministic and failures are
# missing, never wrong.
# --------------------------------------------------------------------------
SQL_OUT = config.GOLD / "patents_bigquery.sql"
EXPORT_COLS = ["publication_number", "assignee_name", "match_key",
               "filing_date", "grant_date", "cpc_subclass"]


def _name_sources() -> list[tuple[str, str]]:
    """(name, IID-or-CIK-tag) pairs from companies.csv (+ aliases) and,
    when present, universe.csv."""
    out = []
    with config.COMPANIES_CSV.open(encoding="utf-8", newline="",
                                   errors="replace") as f:
        for r in csv.DictReader(f):
            if not r.get("IID"):
                continue
            out.append((r.get("Name", ""), r["IID"]))
            for a in (r.get("FDAAliases") or "").split(";"):
                if a.strip():
                    out.append((a.strip(), r["IID"]))
    uni = config.SILVER / "universe.csv"
    if uni.exists():
        with uni.open(encoding="utf-8", newline="", errors="replace") as f:
            for r in csv.DictReader(f):
                if r.get("Name"):
                    out.append((r["Name"], f"CIK:{r.get('CIK','')}"))
    return out


def canon_key_map() -> dict[str, str]:
    """canon(name) -> tag. Tags are the company IID when known from
    companies.csv (aliases included); universe-only members carry a
    'CIK:<cik>' tag so expanded-universe firms are still captured.
    Deterministic rule: an IID always wins over a CIK tag; otherwise
    first-seen wins."""
    m: dict[str, str] = {}
    for name, tag in _name_sources():
        k = canon(name)
        if not k:
            continue
        if k not in m or (m[k].startswith("CIK:")
                          and not tag.startswith("CIK:")):
            m[k] = tag
    return m


def write_sql() -> dict:
    """Generate gold/patents_bigquery.sql for the operator to paste into
    the BigQuery console (project bigquery-public-data is not needed;
    the table is patents-public-data.patents.publications)."""
    from .. import match as _match
    keys = sorted(canon_key_map())
    if not keys:
        return {"status": "fail",
                "message": "No company names found (companies.csv empty?)."}
    strip_words = "|".join(sorted(_match.STRIP))
    key_list = ",\n    ".join(f"'{k}'" for k in keys)
    sql = f"""-- Generated by biointel patents-sql on {date.today().isoformat()}
-- Run in the BigQuery console (console.cloud.google.com/bigquery) while
-- signed in with your Google account. Then: Save results -> CSV
-- (Google Drive if over 10 MB), download it, place it in
-- data\\bronze\\patents_bulk\\ and run:  python cli.py patents-import
WITH keys AS (
  SELECT k FROM UNNEST([
    {key_list}
  ]) AS k
),
pubs AS (
  SELECT p.publication_number,
         a.name AS assignee_name,
         TRIM(REGEXP_REPLACE(REGEXP_REPLACE(
             REGEXP_REPLACE(REGEXP_REPLACE(UPPER(a.name),
                 r"'", ''),
                 r'&', ' AND '),
                 r'[^A-Z0-9 ]', ' '),
             r'\\b({strip_words})\\b', ' ')) AS raw_key,
         p.filing_date, p.grant_date,
         c.code AS cpc_code
  FROM `patents-public-data.patents.publications` AS p,
       UNNEST(p.assignee_harmonized) AS a,
       UNNEST(p.cpc) AS c
  WHERE p.country_code = 'US' AND p.grant_date > 0
)
SELECT DISTINCT
  publication_number, assignee_name,
  REGEXP_REPLACE(raw_key, r' +', ' ') AS match_key,
  filing_date, grant_date,
  SUBSTR(cpc_code, 1, 4) AS cpc_subclass
FROM pubs
WHERE REGEXP_REPLACE(raw_key, r' +', ' ') IN (SELECT k FROM keys)
"""
    SQL_OUT.parent.mkdir(parents=True, exist_ok=True)
    SQL_OUT.write_text(sql, encoding="utf-8")
    return {"status": "ok",
            "message": f"SQL written for {len(keys)} name keys -> {SQL_OUT}\n"
                       "Open console.cloud.google.com/bigquery (your normal "
                       "Google login), paste the file contents, Run, then "
                       "Save results -> CSV (Drive if over 10 MB), download, "
                       "drop the .csv into data\\bronze\\patents_bulk\\ and "
                       "run: python cli.py patents-import"}


def _iso(d: str) -> str:
    d = (d or "").strip()
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else ""


def import_export() -> dict:
    """Consume the BigQuery CSV export(s) from data/bronze/patents_bulk/
    into silver/patents.csv."""
    BULK_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BULK_DIR.glob("*.csv"))
    if not files:
        return {"status": "fail",
                "message": "No .csv export found in data\\bronze\\"
                           "patents_bulk\\. Run patents-sql, execute it in "
                           "BigQuery, export, and drop the file there."}
    kmap = canon_key_map()
    n_out, n_unmatched, firms = 0, 0, set()
    PATENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PATENTS_CSV.open("w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=["IID", "PatentId", "PatentDate",
                                            "FilingDate", "CPCSubclass",
                                            "AssigneeRaw"])
        w.writeheader()
        for path in files:
            with path.open(encoding="utf-8", newline="",
                           errors="replace") as f:
                rd = csv.DictReader(f)
                missing = [c for c in EXPORT_COLS
                           if c not in (rd.fieldnames or [])]
                if missing:
                    return {"status": "fail",
                            "message": f"HEADER MISMATCH in {path.name}: "
                                       f"missing {missing}. REAL header -- "
                                       "paste back so this is corrected:\n"
                                       f"{rd.fieldnames}"}
                for r in rd:
                    tag = kmap.get(r["match_key"])
                    if not tag:
                        n_unmatched += 1
                        continue
                    w.writerow({"IID": tag, "PatentId":
                                r["publication_number"],
                                "PatentDate": _iso(r["grant_date"]),
                                "FilingDate": _iso(r["filing_date"]),
                                "CPCSubclass": r["cpc_subclass"],
                                "AssigneeRaw": r["assignee_name"]})
                    n_out += 1
                    firms.add(tag)
    return {"status": "ok",
            "message": f"patents.csv: {n_out:,} patent-CPC rows across "
                       f"{len(firms)} matched keys "
                       f"({n_unmatched:,} export rows with no local key -- "
                       f"expected 0) -> {PATENTS_CSV}"}


def _find_local() -> dict | None:
    """Manually downloaded bulk zips in data/bronze/patents_bulk/.
    Filenames may carry version suffixes; match on the stem. Returns
    {canonical_name: Path} when all three are present, else None."""
    if not BULK_DIR.exists():
        return None
    found = {}
    for canonical in BULK_FILES:
        stem = canonical.replace(".tsv.zip", "")
        hits = [p for p in BULK_DIR.glob("*.zip")
                if p.name.startswith(stem)]
        if not hits:
            return None
        found[canonical] = max(hits, key=lambda p: p.stat().st_size)
    return found


def ingest() -> dict:
    """Build silver/patents.csv. Preferred route: the three bulk zips
    manually downloaded (keyless) from the ODP dataset page into
    data/bronze/patents_bulk/ -- used whenever present, no probe
    needed since nothing is fetched. Network fallback requires a
    successful probe (rule 0.6.3)."""
    local = _find_local()
    if local:
        print("Local bulk files found (keyless route):")
        for k, p in local.items():
            print(f"  {k}: {p.name} ({p.stat().st_size:,} bytes)")
        return build_from_local(local)
    if not PROBE_MARKER.exists():
        return {"status": "fail",
                "message": "No local bulk files and no successful probe. "
                           "KEYLESS ROUTE: download the three files from "
                           "the ODP dataset page (PatentsView Granted "
                           "Patent Disambiguated Data) -- "
                           "g_patent, g_assignee_disambiguated, "
                           "g_cpc_current -- into data\\bronze\\"
                           "patents_bulk\\, then re-run this command."}
    route = json.loads(PROBE_MARKER.read_text()).get("route")
    if route != "s3":
        return {"status": "fail",
                "message": f"Probe route '{route}' has no wired download "
                           "URLs yet; paste the probe output back."}
    print("Downloading PatentsView bulk files (multi-GB, resume-safe; "
          "re-run this command if interrupted):")
    for fname in BULK_FILES:
        _download_resumable(fname)
    return build_from_local({f: BULK_DIR / f for f in BULK_FILES})
