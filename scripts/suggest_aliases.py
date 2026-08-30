#!/usr/bin/env python3
"""Suggest FDA sponsor names for each company, for you to approve.

FDA uses trade names (JANSSEN PHARMS) where SEC uses legal registrant names
(JOHNSON & JOHNSON). No string transform bridges that, so aliases are a
judgment call about corporate structure. This script proposes candidates;
you decide.

  python suggest_aliases.py            review every company without aliases
  python suggest_aliases.py --iid 2    review one company
  python suggest_aliases.py --list     dump all FDA sponsor names, no prompts
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from difflib import SequenceMatcher

from biointel import config
from biointel.match import canon
from biointel.pipeline import COMPANY_COLS, read_companies

FDA_COUNT = "https://api.fda.gov/drug/drugsfda.json?count=sponsor_name&limit=1000"
CRL_COUNT = "https://api.fda.gov/transparency/crl.json?count=company_name&limit=1000"

NOISE = {
    "PHARMS",
    "PHARMA",
    "PHARMACEUTICAL",
    "PHARMACEUTICALS",
    "USA",
    "US",
    "SUB",
    "AND",
    "CO",
    "INC",
    "LLC",
    "LTD",
    "CORP",
    "THERAPEUTICS",
    "BIOTECH",
    "PRODS",
    "PRODUCTS",
    "LABS",
    "LABORATORIES",
    "HOLDINGS",
    "GROUP",
    "INTERNATIONAL",
    "AMERICA",
    "SCIENCES",
    "BIOSCIENCES",
}


def fetch(url: str) -> list[dict]:
    try:
        return json.load(urllib.request.urlopen(url))["results"]
    except Exception as e:
        print(f"  could not fetch {url}: {e}", file=sys.stderr)
        return []


def tokens(name: str) -> set[str]:
    return {w for w in canon(name).split() if w not in NOISE and len(w) > 2}


def score(company: str, sponsor: str) -> float:
    """0..1. Shared distinctive token dominates; string similarity breaks ties."""
    a, b = tokens(company), tokens(sponsor)
    if not a or not b:
        return 0.0
    overlap = len(a & b) / len(a)
    sim = SequenceMatcher(None, canon(company), canon(sponsor)).ratio()
    return 0.75 * overlap + 0.25 * sim


def candidates(company: str, pool: list[dict], floor: float = 0.30) -> list[tuple]:
    out = []
    for x in pool:
        s = score(company, x["term"])
        if s >= floor:
            out.append((s, x["term"], x["count"]))
    out.sort(reverse=True)
    return out[:15]


def show(cands):
    print(f"\n   {'#':<4}{'score':<8}{'apps':<7}FDA sponsor name")
    print("   " + "-" * 62)
    for i, (s, term, cnt) in enumerate(cands, 1):
        print(f"   {i:<4}{s:<8.2f}{cnt:<7}{term}")


def review(name: str, pool: list[dict]) -> list[str]:
    """Suggest candidates and let the user pick, search, or skip.

    Automatic suggestion fails entirely when the FDA name shares no words
    with the SEC name -- JOHNSON & JOHNSON files as JANSSEN. Those need the
    search option, because only a person knows Janssen is J&J.
    """
    cands = candidates(name, pool)
    picked = []

    while True:
        if cands:
            show(cands)
        else:
            print("   no automatic candidates -- try 's' to search")

        print("\n   numbers  pick those (e.g. 1,3,4)")
        print("   a        all shown")
        print("   s WORD   search all sponsor names for WORD")
        print("   d        done with this company")
        print(f"   picked so far: {'; '.join(picked) if picked else '(none)'}")
        raw = input("   > ").strip()

        if raw.lower() in ("d", ""):
            return picked

        if raw.lower() == "a":
            for c in cands:
                if c[1] not in picked:
                    picked.append(c[1])
            continue

        if raw.lower().startswith("s "):
            term = raw[2:].strip().upper()
            found = sorted(
                [(1.0, x["term"], x["count"]) for x in pool if term in x["term"].upper()],
                key=lambda r: -r[2],
            )[:20]
            if not found:
                print(f"   nothing matching {term!r}")
                cands = []
            else:
                cands = found
            continue

        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(cands):
                t = cands[int(part) - 1][1]
                if t not in picked:
                    picked.append(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iid", type=int)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    print("Fetching FDA sponsor names...")
    pool = fetch(FDA_COUNT) + fetch(CRL_COUNT)
    print(f"{len(pool)} sponsor names retrieved\n")

    if args.list:
        for x in sorted(pool, key=lambda r: -r["count"]):
            print(f"{x['count']:>5}  {x['term']}")
        return

    companies = read_companies()
    todo = [
        c
        for c in companies
        if (args.iid is None and not str(c.get("FDAAliases", "")).strip())
        or (args.iid is not None and str(c["IID"]) == str(args.iid))
    ]

    if not todo:
        print("Nothing to review. Use --iid N to redo one.")
        return

    for c in todo:
        print("=" * 70)
        print(f"IID {c['IID']}  {c['Ticker']}  {c['Name']}")
        print(f"   canonical (current lookup key): {canon(c['Name'])}")
        picked = review(c["Name"], pool)
        c["FDAAliases"] = "; ".join(picked)
        print(f"   saved: {c['FDAAliases'] or '(none)'}\n")

    cols = list(COMPANY_COLS)
    if "FDAAliases" not in cols:
        cols.append("FDAAliases")
    with config.COMPANIES_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(companies)
    print(f"Written to {config.COMPANIES_CSV}")
    print("Now run:  python cli.py events-all")


if __name__ == "__main__":
    main()
