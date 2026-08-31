# src/biointel/sources/orangebook.py
"""FDA Orange Book layer: per-drug patent and exclusivity expiry dates.

WHY. The literature's stated deal engine for biopharma M&A is the
acquirer's loss-of-exclusivity exposure ("patent cliff"): large pharma
buys de-risked assets to replace revenue from expiring blockbusters.
This module supplies the raw dates: the Orange Book data files map
NDA/application numbers -> patent numbers with expiry dates and
regulatory exclusivity end dates. Joined to acquirer approval records
(events layer keys on application numbers already), it yields an
acquirer revenue-at-risk-in-N-years urgency feature for the pairing
model.

SOURCE. The FDA publishes the Orange Book data files as one zip of
tilde(~)-delimited text tables (products.txt, patent.txt,
exclusivity.txt), refreshed monthly.

HONESTY FLAG. fda.gov is UNREACHABLE from the build environment, so the
download URL, zip member names, and column headers are UNTESTED here.
`orangebook-probe` downloads the zip ONCE, lists its members, prints
each header line verbatim, and parses patent.txt; the feature build
refuses to run until a probe has succeeded on the operator machine.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timezone

import requests

from biointel import config, store

# The FDA's stable "Orange Book Data Files" media link. If it 404s or
# redirects to HTML, the probe prints what came back for repointing.
EOB_URL = config.FDA_ORANGE_BOOK

EOB_ZIP = config.BRONZE / "orangebook" / "eob.zip"
PROBE_MARKER = config.BRONZE / "orangebook" / "PROBE_OK"


def _download(force: bool = False) -> bytes:
    """Fetch the Orange Book zip once, cached in bronze with a manifest."""
    EOB_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if EOB_ZIP.exists() and not force:
        return EOB_ZIP.read_bytes()
    r = requests.get(
        EOB_URL, headers={"User-Agent": config.require("BIOINTEL_USER_AGENT")}, timeout=120
    )
    r.raise_for_status()
    EOB_ZIP.write_bytes(r.content)
    (EOB_ZIP.parent / "eob.meta.json").write_text(
        f'{{"tag": "orangebook", "url": "{r.url}", "status": {r.status_code}, '
        f'"bytes": {len(r.content)}, '
        f'"fetched_at": "{datetime.now(timezone.utc).isoformat(timespec="seconds")}"}}',
        encoding="utf-8",
    )
    return r.content


def parse_table(text: str) -> tuple[list[str], list[dict]]:
    """Header + rows from one tilde-delimited Orange Book table."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], []
    header = [h.strip() for h in lines[0].split("~")]
    rows = []
    for ln in lines[1:]:
        vals = ln.split("~")
        rows.append(
            {header[i]: (vals[i].strip() if i < len(vals) else "") for i in range(len(header))}
        )
    return header, rows


def probe() -> dict:
    """Download the zip once, show members and headers, parse patent.txt."""
    try:
        blob = _download()
    except Exception as exc:
        return {
            "status": "fail",
            "message": f"FETCH FAILED: {exc}. fda.gov unreachable or "
            "URL wrong; paste this output back so the URL "
            "is repointed.",
        }
    if blob[:2] != b"PK":
        head = blob[:600].decode("utf-8", errors="replace").replace("\n", " ")
        return {
            "status": "fail",
            "message": "NOT A ZIP -- the URL returned something else "
            "(likely an HTML page). Raw head follows; paste "
            f"this whole output back:\n{head}",
        }
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
        members = zf.namelist()
        pat_name = next((m for m in members if m.lower().endswith("patent.txt")), None)
        if not pat_name:
            return {
                "status": "fail",
                "message": f"patent.txt not among members {members}; paste this output back.",
            }
        text = zf.read(pat_name).decode("utf-8", errors="replace")
        header, rows = parse_table(text)
    except Exception as exc:
        return {"status": "fail", "message": f"PARSE FAILED: {exc}; paste this output back."}

    need = {"Appl_No", "Patent_No", "Patent_Expire_Date_Text"}
    if rows and need.issubset(set(header)):
        PROBE_MARKER.parent.mkdir(parents=True, exist_ok=True)
        PROBE_MARKER.write_text(date.today().isoformat())
        s = rows[0]
        return {
            "status": "ok",
            "message": f"PARSE OK: {len(members)} members {members}; "
            f"patent.txt {len(rows)} rows, header {header}. "
            f"Sample: Appl {s.get('Appl_No')} patent "
            f"{s.get('Patent_No')} expires "
            f"{s.get('Patent_Expire_Date_Text')}. "
            "Orange Book feature build is now unlocked.",
        }
    return {
        "status": "fail",
        "message": f"HEADER MISMATCH: got {header} in {pat_name}, "
        f"need at least {sorted(need)}; {len(rows)} rows. "
        "Paste this whole output back so column names are "
        "corrected on real data.",
    }


def _protection_end_by_appno() -> dict:
    """Appl_No (6-digit) -> latest protection end date across Orange Book
    patent expiries and regulatory exclusivities. Reads the cached zip
    fetched by orangebook-probe; biologics (BLA) are not in the Orange
    Book and simply do not match -- missing, never wrong."""
    if not EOB_ZIP.exists():
        raise FileNotFoundError(
            "Orange Book zip not cached; run `python -m biointel orangebook-probe` first."
        )
    zf = zipfile.ZipFile(io.BytesIO(EOB_ZIP.read_bytes()))
    ends: dict = {}

    def _feed(member_suffix: str, date_col: str):
        name = next((m for m in zf.namelist() if m.lower().endswith(member_suffix)), None)
        if not name:
            return
        _, rows = parse_table(zf.read(name).decode("utf-8", errors="replace"))
        for r in rows:
            ap = "".join(ch for ch in (r.get("Appl_No") or "") if ch.isdigit()).zfill(6)
            txt = (r.get(date_col) or "").strip()
            try:
                d = datetime.strptime(txt, "%b %d, %Y").date()
            except ValueError:
                continue
            if ap != "000000" and (ap not in ends or d > ends[ap]):
                ends[ap] = d

    _feed("patent.txt", "Patent_Expire_Date_Text")
    _feed("exclusivity.txt", "Exclusivity_Date")
    return ends


def loe_urgency(as_of: date, horizon_years: int = 3) -> dict:
    """Per company IID: (matched NDA approvals in Orange Book, of which
    at-risk, share). At-risk = latest protection end on or before
    as_of + horizon (already-expired counts: that revenue is eroding
    now). Count-based proxy -- free data carries no product revenue;
    stated as such wherever reported."""

    ends = _protection_end_by_appno()
    limit = date(as_of.year + horizon_years, as_of.month, min(as_of.day, 28))
    apps: dict = {}
    for r in store.read_table("events"):
        if "pproval" not in (r.get("Outcome") or ""):
            continue
        ap = "".join(ch for ch in (r.get("AppNo") or "") if ch.isdigit()).zfill(6)
        if ap != "000000":
            apps.setdefault(str(r["IID"]), set()).add(ap)
    out = {}
    for iid, s in apps.items():
        matched = [a for a in s if a in ends]
        if not matched:
            continue
        risk = sum(1 for a in matched if ends[a] <= limit)
        out[iid] = (len(matched), risk, round(risk / len(matched), 2))
    return out
