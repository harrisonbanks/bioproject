"""Partnership network from clinical trial collaborators.

Every ClinicalTrials.gov study lists collaborators alongside the lead
sponsor. A collaborator is another organisation working on that trial:
a co-developing pharma company, a CRO, a diagnostics or device firm, an
academic centre, or a government body.

Each pairing is documented partnership evidence -- two organisations
working together, with a date and a therapeutic area attached. That makes
it observable fact rather than inference from what a company does.

Collaborator type matters because the bio-industrial ecosystem is wider
than drug companies. A biotech may need a manufacturer, a diagnostics
partner to find the right patients, or a research services firm, and the
type tells you which.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict

from biointel.match import DESCRIPTORS, LEGAL_SUFFIXES

STRIP_WORDS = LEGAL_SUFFIXES | DESCRIPTORS

# CT.gov agency classes, used as the primary signal where present.
CLASS_MAP = {
    "INDUSTRY": "Industry",
    "NIH": "Government",
    "FED": "Government",
    "OTHER_GOV": "Government",
    "NETWORK": "Network",
    "INDIV": "Individual",
    "OTHER": "Other",
    "UNKNOWN": "Other",
}

# Keyword rules refine "Industry" and "Other" into ecosystem roles.
# Order matters: first match wins.
TYPE_RULES = [
    (
        "CRO",
        [
            "quintiles",
            "iqvia",
            "parexel",
            "icon plc",
            "syneos",
            "ppd",
            "covance",
            "labcorp drug development",
            "medpace",
            "pra health",
            "contract research",
            "worldwide clinical",
            "veristat",
            "emmes",
            "clinipace",
            "novotech",
            "fortrea",
            "novella clinical",
            "pharm-olam",
            "premier research",
            "kcr ",
            "psi cro",
            "wcct",
            "celerion",
        ],
    ),
    (
        "CDMO/Manufacturing",
        [
            "lonza",
            "catalent",
            "samsung biologics",
            "wuxi",
            "boehringer ingelheim biopharm",
            "thermo fisher",
            "patheon",
            "recipharm",
            "cambrex",
            "avid bio",
            "contract manufactur",
            "fujifilm diosynth",
            "charles river",
        ],
    ),
    (
        "Diagnostics/Lab",
        [
            "diagnostic",
            "laboratories",
            "labcorp",
            "quest diagnostics",
            "foundation medicine",
            "guardant",
            "exact sciences",
            "natera",
            "myriad genetics",
            "illumina",
            "qiagen",
            "biomarker",
            "pathology",
        ],
    ),
    (
        "Device/Delivery",
        [
            "medtronic",
            "boston scientific",
            "abbott",
            "becton",
            "baxter",
            "stryker",
            "edwards lifesciences",
            "insulet",
            "dexcom",
            "device",
        ],
    ),
    ("Imaging", ["imaging", "radiology", "siemens healthineers", "ge healthcare"]),
    (
        "Academic",
        [
            "university",
            "universit",
            "college",
            "school of medicine",
            "institute of technology",
            "hospital",
            "medical center",
            "medical centre",
            "clinic",
            "cancer center",
            "cancer centre",
            "health system",
            "academic",
            "faculty",
            "khoo teck",
            "sloan kettering",
            "dana-farber",
            "mayo",
            "cleveland clinic",
            "md anderson",
        ],
    ),
    (
        "Foundation/Nonprofit",
        [
            "foundation",
            "charit",
            "trust",
            "association",
            "society",
            "cure ",
            "research fund",
            "nonprofit",
            "non-profit",
        ],
    ),
    (
        "Government",
        [
            "national institute",
            "national cancer",
            "nih",
            "nci ",
            "cdc",
            "department of",
            "ministry of",
            "agency",
            "health canada",
            "veterans affairs",
            "nhs ",
        ],
    ),
]


def classify(name: str, ct_class: str = "") -> str:
    """Best-guess ecosystem role for a collaborator.

    Keyword rules run first because they are more specific than the CT.gov
    class -- 'INDUSTRY' covers a co-developing pharma company and a CRO
    equally. Falls back to the CT.gov class, then to Other.

    This is a heuristic, not a lookup. It should be reviewed, and the
    output carries the raw class so a wrong guess is visible.
    """
    n = (name or "").lower()
    for label, keys in TYPE_RULES:
        if any(k in n for k in keys):
            return label
    c = (ct_class or "").upper()
    if c == "INDUSTRY":
        return "Industry (unclassified)"
    return CLASS_MAP.get(c, "Other")


def _norm(name: str) -> str:
    """Collapse formatting variants of the same organisation.

    ClinicalTrials.gov is a global registry, so this cannot assume ASCII.
    canon() -- built for SEC and FDA names, which are ASCII -- destroys
    non-ASCII text: "universite de montreal" loses its accented letters and
    fragments, and a CJK name reduces to an empty string, which would drop
    the collaborator entirely.

    Three steps:
      1. Transliterate accented Latin to plain ASCII via NFKD decomposition
         (e -> e, A -> A), so European names keep their letters.
      2. Keep any character that is alphanumeric in Unicode terms, so CJK
         and Cyrillic survive intact.
      3. Strip legal suffixes and descriptors, then drop single characters.

    Step 3's single-character drop is needed because punctuated
    abbreviations fragment: "Sanofi S.A." becomes "SANOFI S A", where the
    suffix list removes "SA" as a whole word but not the split letters.
    Single letters are never the distinctive part of an organisation name.
    """
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    # drop combining marks left over from decomposition (accents)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper().replace("\u2019", "").replace("'", "").replace("&", " AND ")
    s = "".join(ch if ch.isalnum() else " " for ch in s)
    words = [w for w in s.split() if w and w not in STRIP_WORDS and len(w) > 1]
    if not words:
        words = [w for w in s.split() if w]
    key = " ".join(words).strip()
    # Known corporate-family variants that formatting rules cannot bridge.
    FAMILY = {
        "HOFFMANN LA ROCHE": "ROCHE",
        "HOFFMANN LAROCHE": "ROCHE",
        "LA ROCHE": "ROCHE",
        "GENENTECH": "GENENTECH",  # kept distinct deliberately
        "MERCK SHARP AND DOHME": "MERCK SHARP DOHME",
    }
    for pat, canon_key in FAMILY.items():
        if pat in key:
            return canon_key
    return key


def build_network(trials: list[dict], companies: list[dict]) -> dict:
    """Company-to-collaborator edges from trial records.

    Returns:
      edges  -- one row per (company, collaborator), with trial count,
                phases, therapy areas and date range
      summary-- one row per company: collaborator counts by type
    """
    name_by_iid = {str(c["IID"]): c.get("Name", "") for c in companies}
    tick_by_iid = {str(c["IID"]): c.get("Ticker", "") for c in companies}

    agg = defaultdict(
        lambda: {
            "Trials": 0,
            "Phases": set(),
            "Conditions": set(),
            "First": None,
            "Last": None,
            "RawNames": set(),
            "Classes": set(),
        }
    )

    for t in trials:
        iid = str(t.get("IID", "")).strip()
        if not iid:
            continue
        names = [x.strip() for x in str(t.get("Collaborators") or "").split(";") if x.strip()]
        classes = [
            x.strip() for x in str(t.get("CollaboratorClasses") or "").split(";") if x.strip()
        ]
        if not names:
            continue
        for i, nm in enumerate(names):
            key = _norm(nm)
            if not key:
                continue
            # never count a company as its own collaborator
            if key == _norm(name_by_iid.get(iid, "")):
                continue
            a = agg[(iid, key)]
            a["Trials"] += 1
            a["RawNames"].add(nm)
            if i < len(classes):
                a["Classes"].add(classes[i])
            ph = str(t.get("Phase") or "").strip()
            if ph:
                for p in ph.split(";"):
                    if p.strip():
                        a["Phases"].add(p.strip())
            cond = str(t.get("Conditions") or "").strip()
            if cond:
                for c in cond.split(";")[:3]:
                    if c.strip():
                        a["Conditions"].add(c.strip())
            d = str(t.get("StartDate") or "").strip()
            if d:
                a["First"] = d if a["First"] is None else min(a["First"], d)
                a["Last"] = d if a["Last"] is None else max(a["Last"], d)

    edges = []
    for (iid, key), a in agg.items():
        display = sorted(a["RawNames"], key=len)[0]
        cls = "; ".join(sorted(a["Classes"]))
        edges.append(
            {
                "IID": int(iid),
                "Company": name_by_iid.get(iid, ""),
                "Ticker": tick_by_iid.get(iid, ""),
                "Collaborator": display,
                "CollaboratorKey": key,
                "Type": classify(display, cls),
                "CTGovClass": cls,
                "Trials": a["Trials"],
                "Phases": "; ".join(sorted(a["Phases"])),
                "TherapyAreas": "; ".join(sorted(a["Conditions"])[:5]),
                "FirstTrial": a["First"] or "",
                "LastTrial": a["Last"] or "",
            }
        )
    edges.sort(key=lambda r: (r["IID"], -r["Trials"], r["Collaborator"]))

    by_co = defaultdict(lambda: defaultdict(int))
    for e in edges:
        by_co[e["IID"]][e["Type"]] += 1
    summary = []
    for c in companies:
        iid = int(c["IID"])
        types = by_co.get(iid, {})
        summary.append(
            {
                "IID": iid,
                "Ticker": c.get("Ticker", ""),
                "Company": c.get("Name", ""),
                "TotalPartners": sum(types.values()),
                **{
                    k: types.get(k, 0)
                    for k in [
                        "Industry (unclassified)",
                        "CRO",
                        "CDMO/Manufacturing",
                        "Diagnostics/Lab",
                        "Device/Delivery",
                        "Imaging",
                        "Academic",
                        "Foundation/Nonprofit",
                        "Government",
                        "Network",
                        "Other",
                    ]
                },
            }
        )
    summary.sort(key=lambda r: -r["TotalPartners"])
    return {"edges": edges, "summary": summary}
