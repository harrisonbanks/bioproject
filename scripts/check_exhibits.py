#!/usr/bin/env python3
"""Diagnostic: how many 8-K deal filings have the contract attached?

Reads deals.csv, samples filings, fetches each filing's index.json, and
reports which exhibit types are present.

Why this matters: the published method for extracting contract parties
(Material Contracts Corpus, Stanford) parses exhibit types 2, 10 and 99 --
the agreement documents themselves -- not the 8-K narrative. But SEC rules
only ENCOURAGE attaching the agreement to the Item 1.01 8-K; a company may
instead file it with its next 10-Q or 10-K. So the fix only applies to the
share of filings that actually carry a contract exhibit.

Makes N requests. Cached in bronze, so re-running is free.

  python check_exhibits.py            20 filings across all companies
  python check_exhibits.py 50         50 filings
  python check_exhibits.py 20 16      20 filings for IID 16 only
"""

import sys
from collections import Counter

from biointel.pipeline import read_deals
from biointel.sources.deals import exhibits

EXHIBIT_KINDS = {
    "EX-2": "plan of acquisition (contract)",
    "EX-10": "material contract",
    "EX-99": "additional exhibit (often press release)",
}


def kind(t: str) -> str:
    t = (t or "").upper()
    for pfx, label in EXHIBIT_KINDS.items():
        if t.startswith(pfx):
            return pfx
    return ""


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    iid = sys.argv[2] if len(sys.argv) > 2 else None

    rows = read_deals()
    if iid:
        rows = [r for r in rows if str(r["IID"]) == str(iid)]
    if not rows:
        print("No deal filings. Run: python cli.py deals-all")
        return 1

    # spread the sample across companies and years rather than taking a block
    rows.sort(key=lambda r: (str(r["FilingDate"]), str(r["IID"])))
    step = max(1, len(rows) // n)
    sample = rows[::step][:n]

    print(f"Sampling {len(sample)} of {len(rows)} deal filings\n")
    print(f"  {'DATE':<12}{'TICK':<7}{'ITEM':<7}{'EXHIBITS PRESENT'}")
    print("  " + "-" * 76)

    have_contract = 0
    kinds = Counter()
    no_index = 0

    for r in sample:
        files = exhibits(r["CIK"], r["Accession"])
        if not files:
            no_index += 1
            print(f"  {r['FilingDate']:<12}{r['Ticker']:<7}{r['Item']:<7}(index unavailable)")
            continue
        present = sorted({kind(f["Type"]) for f in files if kind(f["Type"])})
        for k in present:
            kinds[k] += 1
        contract = any(k in ("EX-2", "EX-10") for k in present)
        have_contract += bool(contract)
        label = ", ".join(present) if present else "none"
        flag = "  <- contract" if contract else ""
        print(f"  {r['FilingDate']:<12}{r['Ticker']:<7}{r['Item']:<7}{label}{flag}")

    checked = len(sample) - no_index
    print("\n" + "=" * 78)
    if checked:
        pct = 100 * have_contract / checked
        print(
            f"  Filings with a contract exhibit (EX-2 or EX-10): "
            f"{have_contract}/{checked} = {pct:.0f}%"
        )
    print(f"  Index unavailable: {no_index}")
    print("\n  Exhibit types seen:")
    for k, c in kinds.most_common():
        print(f"     {k:<8}{c:>4}  {EXHIBIT_KINDS.get(k, '')}")
    print("\n  Reference: the Material Contracts Corpus reports a mean of 3.07")
    print("  parties per contract (median 3). Your current extractor is")
    print("  averaging far more than that, which is the symptom of parsing")
    print("  the 8-K narrative instead of the agreement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
