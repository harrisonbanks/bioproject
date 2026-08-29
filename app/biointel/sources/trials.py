"""ClinicalTrials.gov API v2.

Free, no key. Base URL https://clinicaltrials.gov/api/v2/
The v1 API is fully retired.

Sponsor matching uses the Essie advanced filter:
    filter.advanced=AREA[LeadSponsorName]AbbVie
AREA[Field]Value targets a specific field rather than doing a general
keyword search. This is substring-tolerant, unlike the FDA join which
needs exact canonical equality.

Known traps, all documented by users of this API:
  - Phase values are exact strings: PHASE1, not "Phase 1" or "phase1".
  - Status values are case-sensitive enums.
  - Arrays (conditions, interventions, collaborators) can be null or empty.
  - Date formats are inconsistent: "2024-01-15", "January 2024", and
    "January 15, 2024" all occur. The API does not normalize them.
"""
from __future__ import annotations
import re
from datetime import date

from .. import config
from ..store import fetch_json

BASE = "https://clinicaltrials.gov"
STUDIES = "api/v2/studies"

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def parse_date(s) -> str | None:
    """Normalize the three date shapes CT.gov emits to YYYY-MM-DD.

    Month-only dates get day 01, which is a stated approximation, not a
    real day. Returns None on anything unrecognized rather than guessing.
    """
    if not s:
        return None
    t = str(s).strip()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):          # 2024-01-15
        return t
    if re.fullmatch(r"\d{4}-\d{2}", t):                # 2024-01
        return t + "-01"

    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", t)   # January 15, 2024
    if m and m.group(1).lower() in MONTHS:
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"

    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{4})", t)                # January 2024
    if m and m.group(1).lower() in MONTHS:
        return f"{int(m.group(2)):04d}-{MONTHS[m.group(1).lower()]:02d}-01"

    return None


def _page(sponsor: str, token: str | None):
    q = {
        "filter.advanced": f"AREA[LeadSponsorName]{sponsor}",
        "pageSize": "1000",
        "countTotal": "true",
        "format": "json",
    }
    if token:
        q["pageToken"] = token
    return fetch_json(f"{BASE}/{STUDIES}", params=q, tag="ctgov_studies")


def _flatten(study: dict) -> dict | None:
    """One study record -> one flat row. Defensive on every nested path."""
    ps = study.get("protocolSection") or {}
    ident = ps.get("identificationModule") or {}
    status = ps.get("statusModule") or {}
    design = ps.get("designModule") or {}
    spons = ps.get("sponsorCollaboratorsModule") or {}
    cond = ps.get("conditionsModule") or {}
    arms = ps.get("armsInterventionsModule") or {}

    nct = ident.get("nctId")
    if not nct:
        return None

    phases = design.get("phases") or []
    interventions = [i.get("name") for i in (arms.get("interventions") or [])
                     if i.get("name")]
    drugs = [i.get("name") for i in (arms.get("interventions") or [])
             if i.get("type") in ("DRUG", "BIOLOGICAL") and i.get("name")]

    enroll = (design.get("enrollmentInfo") or {}).get("count")

    # Collaborators: other organisations working on the trial with the lead
    # sponsor. This is the partnership evidence -- pharma co-development,
    # CROs, diagnostics firms, device makers, academic centres, government.
    collabs = spons.get("collaborators") or []
    collab_names = [c.get("name") for c in collabs if c.get("name")]
    collab_classes = [c.get("class") for c in collabs if c.get("class")]

    return {
        "NCTId": nct,
        "Sponsor": ((spons.get("leadSponsor") or {}).get("name")) or "",
        "SponsorClass": ((spons.get("leadSponsor") or {}).get("class")) or "",
        "Title": ident.get("briefTitle") or "",
        "Phase": "; ".join(phases),
        "Status": status.get("overallStatus") or "",
        "StudyType": design.get("studyType") or "",
        "Conditions": "; ".join(cond.get("conditions") or []),
        "Drugs": "; ".join(drugs),
        "Interventions": "; ".join(interventions),
        "Enrollment": enroll,
        "Collaborators": "; ".join(collab_names),
        "CollaboratorClasses": "; ".join(collab_classes),
        "CollaboratorCount": len(collab_names),
        "StartDate": parse_date((status.get("startDateStruct") or {}).get("date")),
        "PrimaryCompletion": parse_date(
            (status.get("primaryCompletionDateStruct") or {}).get("date")),
        "CompletionDate": parse_date(
            (status.get("completionDateStruct") or {}).get("date")),
        "LastUpdate": parse_date(
            (status.get("lastUpdatePostDateStruct") or {}).get("date")),
    }


def trials_for(sponsor: str, max_pages: int = 10) -> list[dict]:
    """Every trial where `sponsor` is the lead sponsor.

    Paginates with pageToken (cursor-based; v1's offset model is gone).
    max_pages caps runaway pulls at 10,000 trials.
    """
    if not sponsor:
        return []
    rows, token, pages = [], None, 0
    while pages < max_pages:
        try:
            data = _page(sponsor, token)
        except Exception:
            break
        for s in (data.get("studies") or []):
            r = _flatten(s)
            if r:
                rows.append(r)
        token = data.get("nextPageToken")
        pages += 1
        if not token:
            break

    seen, out = set(), []
    for r in rows:
        if r["NCTId"] in seen:
            continue
        seen.add(r["NCTId"])
        out.append(r)
    out.sort(key=lambda r: (r["StartDate"] or ""), reverse=True)
    return out


def sponsor_landscape(limit_note: bool = True) -> list[dict]:
    """Top lead sponsors by study count, for checking what CT.gov calls
    your companies.

    CAUTION: for a high-cardinality field like LeadSponsorName this returns
    only the head of the distribution. The smallest sponsor returned has
    several hundred studies; roughly 50,900 smaller sponsors are absent.
    Useful for large caps, useless for small ones -- use trials_for()
    with the AREA filter for those.
    """
    data = fetch_json(f"{BASE}/api/v2/stats/field/values",
                      params={"fields": "LeadSponsorName"},
                      tag="ctgov_stats")
    if isinstance(data, list) and data:
        return data[0].get("topValues") or []
    return []
