import json, urllib.request
from biointel.match import canon

NAMES = ["ALNYLAM PHARMACEUTICALS, INC.", "Axsome Therapeutics, Inc.",
         "ACADIA PHARMACEUTICALS INC", "Vanda Pharmaceuticals Inc.",
         "Harmony Biosciences Holdings, Inc.", "RHYTHM PHARMACEUTICALS, INC."]

url = "https://api.fda.gov/drug/drugsfda.json?count=sponsor_name&limit=1000"
pool = json.load(urllib.request.urlopen(url))["results"]

for n in NAMES:
    k = canon(n)
    first = k.split()[0] if k else ""
    hits = [x for x in pool if first in x["term"].upper()]
    print(f"\n{n}\n   canonical: {k}")
    for h in hits:
        print(f"      {h['count']:>4}  {h['term']}   (canon: {canon(h['term'])})")
    if not hits:
        print("      nothing in the top 1000 sponsor names")