"""Canonical company-name matching.

Direct port of the Canon() function in the Events Power Query.
FDA publishes no CIK/ticker/CUSIP/LEI, so name is the only available join.

Method: uppercase, drop apostrophes, & -> AND, strip non-alphanumerics,
remove legal suffixes, then require EXACT equality of the result.

Exact equality is what prevents wrong-company contamination. It also means
subsidiaries filing under unrelated names (Janssen/J&J, Genzyme/Sanofi)
fail as MISSING rather than as WRONG.

Measured on the 314 distinct openFDA CRL sponsor names: 16/18 SEC
registrant names matched; the 2 misses correctly have no CRL records
under those names.
"""

LEGAL_SUFFIXES = {
    "INC", "LLC", "LTD", "LIMITED", "CORP", "CORPORATION", "CO", "COMPANY",
    "PLC", "AG", "SA", "NV", "AB", "LP", "LLP", "GMBH", "AS", "PTY",
    "HOLDINGS", "HOLDING", "USA", "US",
}


def canon(s) -> str:
    """Canonicalize a company name. Mirrors Canon() in the M query exactly."""
    if s is None:
        return ""
    a = str(s).upper()
    b = a.replace("\u2019", "").replace("'", "")
    c = b.replace("&", " AND ")
    d = "".join(ch if (ch.isascii() and (ch.isalnum() or ch == " ")) else " " for ch in c)
    words = [w for w in d.split(" ") if w and w not in LEGAL_SUFFIXES]
    return " ".join(words)
