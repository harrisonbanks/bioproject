import json
import urllib.error
import urllib.request

CANDIDATES = [
    "sponsor_name.exact",
    "sponsor_name",
    "openfda.manufacturer_name.exact",
]

WANT = [
    "MERCK",
    "LILLY",
    "JANSSEN",
    "TAKEDA",
    "ARCUTIS",
    "BRIDGEBIO",
    "RECURSION",
    "SCHRODINGER",
    "ABSCI",
]

for field in CANDIDATES:
    url = f"https://api.fda.gov/drug/drugsfda.json?count={field}&limit=1000"
    try:
        data = json.load(urllib.request.urlopen(url))
    except urllib.error.HTTPError as e:
        print(f"[{field}] HTTP {e.code}")
        continue

    hits = [x for x in data["results"] if any(k in x["term"].upper() for k in WANT)]
    print(f"\n=== {field}  ({len(data['results'])} distinct sponsors, {len(hits)} matching)")
    for x in hits:
        print(f"{x['count']:>5}  {x['term']}")
    break
