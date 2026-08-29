"""Bronze layer: fetch and store raw API responses before any parsing.

Why: Power Query re-fetches on every refresh and stores only the parsed,
filtered result. Rows discarded by the filter are gone. Storing the raw
response means a filter change is a re-parse, not a re-download.

Also gives a coverage-as-of record, which matters because the openFDA CRL
dataset had publication paused in April 2026 -- today's pull may not be
reproducible later.
"""
from __future__ import annotations
import hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config

_last_sec_call = 0.0


def _key(url: str, params: dict | None) -> str:
    raw = url + "|" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def fetch_json(url: str, params: dict | None = None, headers: dict | None = None,
               *, tag: str, cache: bool = True, timeout: int = 60,
               raw_text: bool = False):
    """GET an endpoint, storing the raw response in bronze.

    tag      -- subfolder name, e.g. 'sec_submissions', 'fda_crl'
    cache    -- if True and a stored response exists, return it without a call
    raw_text -- return the body as text instead of parsing JSON. Needed for
                HTML filings, which are documents rather than APIs.
    """
    global _last_sec_call
    folder = config.BRONZE / tag
    folder.mkdir(parents=True, exist_ok=True)
    k = _key(url, params)
    ext = "txt" if raw_text else "json"
    body_path = folder / f"{k}.{ext}"
    meta_path = folder / f"{k}.meta.json"

    if cache and body_path.exists():
        txt = body_path.read_text(encoding="utf-8", errors="replace")
        return txt if raw_text else json.loads(txt)

    if "sec.gov" in url:                       # SEC limit is 10 req/sec
        gap = time.time() - _last_sec_call
        if gap < config.SEC_RATE_LIMIT:
            time.sleep(config.SEC_RATE_LIMIT - gap)
        _last_sec_call = time.time()

    hdrs = {"User-Agent": config.USER_AGENT}
    if headers:
        hdrs.update(headers)

    r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    meta = {
        "url": r.url,
        "status": r.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tag": tag,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    r.raise_for_status()
    if raw_text:
        body_path.write_text(r.text, encoding="utf-8")
        return r.text
    data = r.json()
    body_path.write_text(json.dumps(data), encoding="utf-8")
    return data


def coverage_report() -> list[dict]:
    """Every stored bronze response with its URL and fetch time."""
    out = []
    for meta in sorted(config.BRONZE.rglob("*.meta.json")):
        out.append(json.loads(meta.read_text(encoding="utf-8")))
    return out
