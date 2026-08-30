"""One-shot cleanup: remove 'Company Search Feed' pseudo-companies from
companies.csv and universe.csv (rows created before the parser filter)."""

import csv

for path, keycol in (("data/silver/companies.csv", "Name"), ("data/silver/universe.csv", "Name")):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        cols = rows[0].keys() if rows else []
    keep = [r for r in rows if "search feed" not in (r.get(keycol) or "").lower()]
    removed = len(rows) - len(keep)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cols))
        w.writeheader()
        w.writerows(keep)
    print(f"{path}: removed {removed} feed-junk rows, {len(keep)} remain")
