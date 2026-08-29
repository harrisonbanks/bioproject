#!/usr/bin/env python3
"""Command line for the biointel pipeline.

  python cli.py add REGN                    add a company
  python cli.py events 9                    fetch FDA events for one IID
  python cli.py events-all                  every company in companies.csv
  python cli.py window "BLA 761303" 2024-03-22
  python cli.py list                        show companies
  python cli.py coverage                    what has been fetched, and when
"""
import sys, csv
from biointel import (add_company, get_events, get_all_events, price_window,
                      read_companies, read_events, coverage_report)
from biointel import config


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    cmd = argv[1]

    if cmd == "add":
        for t in argv[2:]:
            print(add_company(t)["message"])

    elif cmd == "events":
        print(get_events(int(argv[2]))["message"])

    elif cmd == "events-all":
        r = get_all_events()
        for d in r["detail"]:
            print("  " + d["message"])
        print(f"{r['companies']} companies, {r['added']} new event rows")

    elif cmd == "window":
        rows = price_window(argv[2], argv[3])
        if not rows:
            print("No window. Check the AppNo and date exist in events.csv,"
                  " and that price data covers that date."); return 1
        out = config.GOLD / "window.csv"
        cols = ["IID","AppNo","Drug","Event","RelDay","Date","Open","High",
                "Low","Close","AdjClose","Volume","PctFromT0"]
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        print(f"{len(rows)} rows -> {out}")
        for r in rows:
            pct = "" if r["PctFromT0"] is None else f"{r['PctFromT0']:+7.2f}%"
            print(f"  {r['RelDay']:>3}  {r['Date']}  adj={r['AdjClose']:>9.2f}  {pct}")

    elif cmd == "list":
        for c in read_companies():
            print(f"  {c['IID']:>3}  {c['Ticker']:<6} {c['Name']}")

    elif cmd == "coverage":
        for m in coverage_report():
            print(f"  {m['fetched_at']}  {m['tag']:<22} {m['status']}  {m['url'][:90]}")

    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
