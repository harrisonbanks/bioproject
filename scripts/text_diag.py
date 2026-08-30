"""Anatomy of 10-K text-extraction failures: re-runs extraction on the
first few companies and prints what the documents actually look like
around their item headers. Run: python text_diag.py"""
import csv, re
from biointel import config
from biointel.pipeline import extract_item1, ITEM1_START
from biointel.sources.counterparty import fetch_text
from biointel.labels import _filings_reaching

comps = list(csv.DictReader(open(config.COMPANIES_CSV, encoding="utf-8")))
shown = 0
for c in comps:
    if shown >= 5:
        break
    cik10 = str(c.get("CIK", "")).zfill(10)
    if not cik10.strip("0"):
        continue
    try:
        quads = _filings_reaching(cik10, "2013-01-01")
    except Exception:
        continue
    tenk = [(d, acc, doc) for f, d, acc, doc in quads
            if f in ("10-K", "20-F") and doc and d >= "2013-01-01"]
    if not tenk:
        continue
    d, acc, doc = sorted(tenk)[-1]
    url = (f"https://www.sec.gov/Archives/edgar/data/"
           f"{int(cik10)}/{acc.replace('-', '')}/{doc}")
    raw = fetch_text(url) or ""
    item1 = extract_item1(raw)
    verdict = f"OK({len(item1)})" if len(item1) >= 1500 else "FAIL"
    print(f"{c['Name'][:30]:<32} {d} len={len(raw):>8} {verdict}")
    if verdict == "FAIL":
        hits = [m.start() for m in re.finditer(r"(?i)item", raw[:300000])][:6]
        for h in hits:
            print("   ctx:", repr(raw[h:h+70]))
        starts = list(ITEM1_START.finditer(raw[:400000]))
        print(f"   ITEM1_START matches: {len(starts)}")
    shown += 1
