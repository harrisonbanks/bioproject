import collections
import csv

from biointel import config

rows = list(csv.DictReader(config.EVENTS_CSV.open(encoding="utf-8")))
print(f"total events: {len(rows)}\n")

print("BY OUTCOME")
for k, v in collections.Counter(r["Event"] for r in rows).items():
    print(f"  {k:<12} {v}")

print("\nBY SUBTYPE")
for k, v in collections.Counter(r["SubType"] or "(rejection)" for r in rows).items():
    print(f"  {k:<12} {v}")

print("\nREJECTIONS")
for r in sorted([r for r in rows if r["Event"] == "Rejection"], key=lambda r: r["Date"]):
    print(f"  {r['Date']}  {r['Name'][:30]:<30} {str(r['AppNo']):<14} {r['Outcome']}")

recent = [r for r in rows if r["Date"] >= "2010-01-01"]
print(f"\nEVENTS SINCE 2010 (price data available): {len(recent)} of {len(rows)}")
