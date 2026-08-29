import sys, json, urllib.request
from datetime import date
from biointel.pipeline import read_companies
from biointel import config

IID = sys.argv[1] if len(sys.argv) > 1 else "23"
c = next(x for x in read_companies() if str(x["IID"]) == IID)
cik = str(c["CIK"]).zfill(10)

url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
req = urllib.request.Request(url, headers={"User-Agent": config.require("BIOINTEL_USER_AGENT")})
data = json.load(urllib.request.urlopen(req))

tag = "NetCashProvidedByUsedInOperatingActivities"
facts = data["facts"]["us-gaap"][tag]["units"]["USD"]

rows = []
for f in facts:
    if not f.get("start"):
        continue
    d = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days + 1
    rows.append((f["start"], f["end"], d, f["val"], f["form"], f.get("fp"), f["filed"]))

rows.sort(key=lambda r: (r[1], r[6]))
print(f"{c['Name']}  ({len(rows)} duration facts)\n")
print(f"{'START':<12}{'END':<12}{'DAYS':>5}  {'VALUE':>16}  {'FORM':<7}{'FP':<4}FILED")
for r in rows[-25:]:
    print(f"{r[0]:<12}{r[1]:<12}{r[2]:>5}  {r[3]:>16,}  {r[4]:<7}{str(r[5]):<4}{r[6]}")