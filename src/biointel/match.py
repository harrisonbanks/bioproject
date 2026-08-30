"""Canonical company-name matching.

Port of the Canon() function from the Events Power Query, extended.

FDA publishes no CIK/ticker/CUSIP/LEI, so name is the only available join.

Method: uppercase, drop apostrophes, & -> AND, strip non-alphanumerics,
remove legal suffixes AND descriptor words, then require EXACT equality.

The descriptor list exists because FDA abbreviates:
    SEC:  ALNYLAM PHARMACEUTICALS, INC.
    FDA:  ALNYLAM PHARMS INC
Both collapse to ALNYLAM. Without this, they never match.

Confirmed cases: ALNYLAM/ACADIA/VANDA PHARMACEUTICALS vs ...PHARMS.

TRADE-OFF: stripping descriptors makes matching looser. Two distinct
companies sharing a distinctive word would now collide, e.g. a
hypothetical ARENA PHARMACEUTICALS and ARENA THERAPEUTICS. Multi-word
distinctive names are unaffected (MERCK vs MERCK SHARP DOHME still
differ). Verification against the returned name still applies, so a
collision would surface as extra rows for a real company, never as
silently wrong data.
"""

# Corporate form. Never distinctive.
LEGAL_SUFFIXES = {
    "INC", "LLC", "LTD", "LIMITED", "CORP", "CORPORATION", "CO", "COMPANY",
    "PLC", "AG", "SA", "NV", "AB", "LP", "LLP", "GMBH", "AS", "PTY",
    "HOLDINGS", "HOLDING", "USA", "US",
}

# Industry descriptors. FDA abbreviates these inconsistently, so they
# cannot be relied on to match.
DESCRIPTORS = {
    "PHARMACEUTICAL", "PHARMACEUTICALS", "PHARMS", "PHARMA", "PHARM",
    "THERAPEUTICS", "THERAPEUTIC", "THERAPY", "THERAPIES",
    "BIOSCIENCES", "BIOSCIENCE", "BIOPHARMACEUTICALS", "BIOPHARMACEUTICAL",
    "BIOPHARMA", "BIOTECHNOLOGY", "BIOTECH", "BIOLOGICS", "BIO",
    "LABORATORIES", "LABORATORY", "LABS", "LAB",
    "SCIENCES", "SCIENCE", "HEALTHCARE", "HEALTH",
    "MEDICINES", "MEDICINE", "MEDICAL",
    "PRODUCTS", "PRODS", "RESEARCH", "DEVELOPMENT",
    "TECHNOLOGIES", "TECHNOLOGY", "SOLUTIONS", "GROUP",
    "INTERNATIONAL", "AMERICA", "AMERICAS", "NORTH",
}

STRIP = LEGAL_SUFFIXES | DESCRIPTORS


def canon(s) -> str:
    """Canonicalize a company name for exact-equality matching."""
    if s is None:
        return ""
    a = str(s).upper()
    b = a.replace("\u2019", "").replace("'", "")
    c = b.replace("&", " AND ")
    d = "".join(ch if (ch.isascii() and (ch.isalnum() or ch == " ")) else " " for ch in c)
    words = [w for w in d.split(" ") if w and w not in STRIP]
    # Never return empty: if every word was stripped, fall back to the
    # un-stripped form so the lookup still has something to search.
    if not words:
        words = [w for w in d.split(" ") if w]
    return " ".join(words)
