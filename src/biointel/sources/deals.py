"""Material agreements from SEC Form 8-K.

  GET https://data.sec.gov/submissions/CIK##########.json

Keyed on CIK. No name matching -- none of the alias problems that affect
the FDA and ClinicalTrials.gov joins.

Why 8-K rather than full-text search: Item numbers are FILED METADATA.
The submissions response carries an `items` field alongside form and
date, so filtering to Item 1.01 reads a field rather than searching prose.

Items captured:
  1.01  Entry into a Material Definitive Agreement
  1.02  Termination of a Material Definitive Agreement
  2.01  Completion of Acquisition or Disposition of Assets

These cover agreements of ANY type -- licensing, manufacturing, supply,
distribution, service, financing -- not only drug licensing. That is what
reaches the non-drug and financial counterparties in the ecosystem.

STRUCTURE TRAP: filings.recent is columnar. Each field is its own array
and index i across all of them describes one filing. The arrays must be
zipped before filtering, and must never be sorted independently.

CIK TRAP: data.sec.gov needs the CIK zero-padded to 10 digits.
sec.gov/Archives needs it WITHOUT leading zeros. Mixing them returns 404.
"""

from __future__ import annotations

import re

from biointel.store import fetch_json

SUBS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"

ITEM_LABELS = {
    "1.01": "Material agreement entered",
    "1.02": "Material agreement terminated",
    "2.01": "Acquisition or disposition completed",
}
DEAL_ITEMS = set(ITEM_LABELS)


def _zip_recent(recent: dict) -> list[dict]:
    """Columnar arrays -> list of filing dicts. Index i is one filing."""
    keys = [
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "form",
        "items",
        "primaryDocument",
        "primaryDocDescription",
    ]
    present = [k for k in keys if isinstance(recent.get(k), list)]
    if not present:
        return []
    n = max(len(recent[k]) for k in present)
    out = []
    for i in range(n):
        out.append({k: (recent[k][i] if i < len(recent[k]) else None) for k in present})
    return out


def all_filings(cik10: str) -> list[dict]:
    """Every filing in the submissions response.

    `filings.recent` holds roughly the last 1,000 filings. Older ones live
    in `filings.files`, each a separate JSON that must be fetched. Both are
    included so deal history is not truncated at recent filings.
    """
    try:
        data = fetch_json(SUBS_URL.format(cik10=str(cik10).zfill(10)), tag="sec_submissions")
    except Exception:
        return []

    rows = _zip_recent((data.get("filings") or {}).get("recent") or {})

    for extra in (data.get("filings") or {}).get("files") or []:
        name = extra.get("name")
        if not name:
            continue
        try:
            more = fetch_json(
                f"https://data.sec.gov/submissions/{name}", tag="sec_submissions_page"
            )
        except Exception:
            continue
        rows += _zip_recent(more if isinstance(more, dict) else {})
    return rows


def deal_filings(cik10: str) -> list[dict]:
    """8-K filings carrying Item 1.01, 1.02 or 2.01.

    `items` is a comma-separated string such as "1.01,9.01". A single
    filing can carry several deal items; each becomes its own row so the
    event type is unambiguous.
    """
    out = []
    for f in all_filings(cik10):
        form = str(f.get("form") or "")
        if not form.startswith("8-K"):
            continue
        raw = str(f.get("items") or "")
        if not raw:
            continue
        found = [i.strip() for i in raw.split(",") if i.strip() in DEAL_ITEMS]
        if not found:
            continue

        acc = str(f.get("accessionNumber") or "")
        acc_plain = acc.replace("-", "")
        cik_plain = str(int(str(cik10)))  # Archives wants no padding
        folder = ARCHIVE.format(cik=cik_plain, acc=acc_plain)

        for item in found:
            out.append(
                {
                    "Item": item,
                    "EventType": ITEM_LABELS[item],
                    "FilingDate": f.get("filingDate"),
                    "ReportDate": f.get("reportDate"),
                    "AcceptedAt": f.get("acceptanceDateTime"),
                    "Form": form,
                    "Accession": acc,
                    "AllItems": raw,
                    "PrimaryDoc": f.get("primaryDocument"),
                    "FilingURL": f"{folder}/{f.get('primaryDocument')}"
                    if f.get("primaryDocument")
                    else folder,
                    "IndexURL": f"{folder}/{acc}-index.htm",
                }
            )
    out.sort(key=lambda r: str(r["FilingDate"] or ""), reverse=True)
    return out


EXHIBIT_FN_RE = re.compile(r"(?i)ex[-_]?(\d{1,2})[\._]?(\d{0,3})[a-z]*\.(?:htm|html|txt)$")


def exhibit_type_from_name(filename: str) -> str:
    """Exhibit type from the FILENAME, e.g. d856103dex1045.htm -> EX-10.45.

    Verified against real index.json responses: the directory.item 'type'
    field contains icon names ('text.gif'), never exhibit types -- that
    field is unusable and was the cause of the 0/20 diagnostic failure.
    The filename is the reliable carrier: ...ex99.htm, ...ex101.htm,
    ...dex1045.htm.
    """
    m = EXHIBIT_FN_RE.search(filename or "")
    if not m:
        return ""
    major, minor = m.group(1), m.group(2)
    joined = major + minor
    # Real 8-K exhibit majors are 1,2,3,4,5,10,16,23,99. A two-digit token
    # like '41' is EX-4.1; '1045' is EX-10.45; '99'/'991' stay EX-99[.1].
    TWO_DIGIT_MAJORS = {"10", "99", "16", "23"}
    if major in TWO_DIGIT_MAJORS:
        return f"EX-{major}" + (f".{minor}" if minor else "")
    if len(major) == 2 and major not in TWO_DIGIT_MAJORS:
        # split: first digit major, rest minor  (41 -> 4.1, 21 -> 2.1)
        return f"EX-{major[0]}.{major[1]}{minor}"
    if joined[:2] in TWO_DIGIT_MAJORS:
        return f"EX-{joined[:2]}" + (f".{joined[2:]}" if joined[2:] else "")
    return f"EX-{major}" + (f".{minor}" if minor else "")


def exhibits(cik10: str, accession: str) -> list[dict]:
    """Files in a filing folder, from index.json.

    The 'Type' returned here is derived from the filename via
    exhibit_type_from_name(); the raw index.json 'type' field is an icon
    name and is preserved separately as 'RawType'.
    """
    acc_plain = str(accession).replace("-", "")
    cik_plain = str(int(str(cik10)))
    folder = ARCHIVE.format(cik=cik_plain, acc=acc_plain)
    try:
        data = fetch_json(f"{folder}/index.json", tag="sec_filing_index")
    except Exception:
        return []
    items = (data.get("directory") or {}).get("item") or []
    out = []
    for it in items:
        nm = it.get("name") or ""
        out.append(
            {
                "Name": nm,
                "Size": it.get("size"),
                "Type": exhibit_type_from_name(nm),
                "RawType": it.get("type"),
                "URL": f"{folder}/{nm}",
            }
        )
    return out
