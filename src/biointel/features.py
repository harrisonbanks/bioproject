"""Phase M1: the feature table.

One row per (company, calendar quarter end), every feature computed
strictly AS OF that quarter end -- nothing later leaks in. Joined with
the label panel into gold/model_panel.csv, this is the left half of the
sentence the project tests: "given what a company looked like at time T,
predict whether it is acquired after T."

Feature families (source table -> features):

  financials.csv     latest period <= Q (within 400 days): cash + short
                     term investments, revenue, R&D, net income, assets,
                     liabilities, equity, debt, shares. OCF is converted
                     to trailing-twelve-month form using the period's FP
                     marker (FY = annual as-is; Q1/Q2/Q3 = YTD annualized
                     by 12/3, 12/6, 12/9 -- same convention as the
                     shipped TTM burn fix). BurnAnnual, RunwayMonths.
  trials.csv         trials with StartDate <= Q: totals by phase, lead
                     phase (the strongest de-risking signal in biotech
                     target checklists is a late-stage or approved
                     asset), starts in the trailing 12 months.
  events.csv         FDA history <= Q: original approvals ever (the
                     approved-drug flag), approvals and rejections in
                     the trailing 12 months, days since last event.
  event_study.csv    market reaction to events in the trailing 12
                     months: mean CAR[-1,+1] and mean post-event drift.
                     A negative shock plus short runway is the distress
                     -target profile; a positive readout is the
                     asset-attraction profile.
  relationships.csv  relationships with FirstDate <= Q (undated rows
                     count as always-known): totals by kind, deals in
                     the trailing 24 months, license/collaboration
                     counts, in-universe ties (the modal acquirer is an
                     existing partner).

Price features (market cap, 52-week drawdown) require the price API and
are filled when reachable, blank otherwise -- never fabricated.
"""
from __future__ import annotations
import csv as _csv
from collections import defaultdict
from datetime import date, timedelta

from biointel import config

FEATURE_COLS = [
    "IID", "Ticker", "Company", "QuarterEnd",
    # financials
    "FinPeriodEnd", "FinAgeDays", "Currency", "Cash", "STI", "CashSTI", "Revenue",
    "RnD", "NetIncome", "TotalAssets", "TotalLiabilities", "Equity",
    "LongTermDebt", "SharesOutstanding", "OCF_TTM", "TTMBasis",
    "BurnAnnual", "RunwayMonths",
    # pipeline
    "TrialsTotal", "TrialsPh1", "TrialsPh2", "TrialsPh3", "TrialsPh4",
    "LeadPhase", "TrialsStarted12m",
    # FDA
    "OrigApprovalsEver", "HasApprovedDrug", "Approvals12m",
    "Rejections12m", "DaysSinceLastFDAEvent",
    # market reaction
    "CAR12m_mean", "Drift12m_mean", "FDAEventsWithCAR12m",
    # relationships
    "RelTotal", "RelTrial", "RelDeal", "RelInUniverse", "Deals24m",
    "LicensesEver", "CollabsEver",
    # v2 dynamics / catalysts / demand / maturity
    "dCash4q", "dShares4q", "RnDIntensity", "CashToAssets",
    "AgeYears", "Ph3Started24m", "FirstApprovalRecent24m", "HotTA",
    "FDAEventsEver",
    # price (blank when API unreachable)
    "PriceQ", "MarketCap", "Drawdown52w",
]


def _quarter_ends(first: str, last: str) -> list[str]:
    out = []
    for y in range(int(first[:4]), int(last[:4]) + 1):
        for m, dd in ((3, 31), (6, 30), (9, 30), (12, 31)):
            q = f"{y:04d}-{m:02d}-{dd:02d}"
            if first <= q <= last:
                out.append(q)
    return out


def _num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def _load(path, cols=None):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(_csv.DictReader(f))


def build_features(read_companies, start: str = "2010-01-01") -> list[dict]:
    today = date.today().isoformat()
    quarters = _quarter_ends(start, today)
    companies = read_companies()

    fins = defaultdict(list)
    for r in _load(config.SILVER / "financials.csv"):
        fins[int(r["IID"])].append(r)
    for v in fins.values():
        v.sort(key=lambda r: r["PeriodEnd"])

    trials = defaultdict(list)
    for r in _load(config.SILVER / "trials.csv"):
        trials[int(r["IID"])].append(r)

    events = defaultdict(list)
    for r in _load(config.SILVER / "events.csv"):
        events[int(r["IID"])].append(r)

    study = defaultdict(list)
    for r in _load(config.GOLD / "event_study.csv"):
        study[int(r["IID"])].append(r)

    rels = defaultdict(list)
    for r in _load(config.RELATIONSHIPS_CSV):
        rels[int(r["IID"])].append(r)

    # optional price bars, one fetch per ticker for the whole span
    bars_by_ticker = {}
    try:
        from biointel.sources import prices as _prices
        for c in companies:
            t = c.get("Ticker", "")
            if not t:
                continue
            try:
                bars_by_ticker[t] = _prices.daily_bars(
                    t, date.fromisoformat(start) - timedelta(days=400),
                    date.today())
            except Exception:
                bars_by_ticker[t] = []
    except Exception:
        pass

    rows = []
    for c in companies:
        iid = int(c["IID"])
        tick = c.get("Ticker", "")
        for q in quarters:
            qd = date.fromisoformat(q)
            r = {"IID": iid, "Ticker": tick,
                 "Company": c.get("Name", ""), "QuarterEnd": q}

            # ---- financials: latest period <= Q, max 400 days old ----
            fin = None
            shares_ff = None
            for f in reversed(fins.get(iid, [])):
                if f["PeriodEnd"] > q:
                    continue
                if shares_ff is None and _num(f.get("SharesOutstanding")):
                    if (qd - date.fromisoformat(f["PeriodEnd"])).days <= 400:
                        shares_ff = _num(f["SharesOutstanding"])
                if fin is None and any(_num(f.get(k)) is not None
                                       for k in ("Cash", "TotalAssets", "Revenue")):
                    fin = f
                if fin is not None and shares_ff is not None:
                    break
            if fin and (qd - date.fromisoformat(fin["PeriodEnd"])).days <= 400:
                cash = _num(fin.get("Cash"))
                sti = _num(fin.get("ShortTermInvestments"))
                r["FinPeriodEnd"] = fin["PeriodEnd"]
                r["Currency"] = fin.get("Currency", "USD") or "USD"
                r["FinAgeDays"] = (qd - date.fromisoformat(fin["PeriodEnd"])).days
                r["Cash"], r["STI"] = cash, sti
                r["CashSTI"] = (cash or 0) + (sti or 0) if cash is not None else None
                for src, dst in (("Revenue", "Revenue"), ("RnD", "RnD"),
                                 ("NetIncome", "NetIncome"),
                                 ("TotalAssets", "TotalAssets"),
                                 ("TotalLiabilities", "TotalLiabilities"),
                                 ("Equity", "Equity"),
                                 ("LongTermDebt", "LongTermDebt"),
                                 ("SharesOutstanding", "SharesOutstanding")):
                    r[dst] = _num(fin.get(src))
                if r.get("SharesOutstanding") is None and shares_ff:
                    r["SharesOutstanding"] = shares_ff
                ocf = _num(fin.get("NetCashOperating"))
                fp = (fin.get("FP") or "").upper()
                mult = {"FY": 1.0, "Q1": 4.0, "Q2": 2.0, "Q3": 12 / 9}.get(fp)
                if ocf is not None and mult:
                    r["OCF_TTM"] = round(ocf * mult)
                    r["TTMBasis"] = "annual" if fp == "FY" else f"annualized-{fp}"
                    if ocf < 0 and r["CashSTI"]:
                        r["BurnAnnual"] = -r["OCF_TTM"]
                        r["RunwayMonths"] = round(
                            r["CashSTI"] / (r["BurnAnnual"] / 12), 1)

            # ---- pipeline ----
            ts = [t for t in trials.get(iid, [])
                  if t.get("StartDate") and t["StartDate"][:10] <= q]
            r["TrialsTotal"] = len(ts)
            for ph in ("1", "2", "3", "4"):
                r[f"TrialsPh{ph}"] = sum(1 for t in ts
                                         if f"PHASE{ph}" in (t.get("Phase") or ""))
            lead = 0
            for t in ts:
                for ph in (4, 3, 2, 1):
                    if f"PHASE{ph}" in (t.get("Phase") or ""):
                        lead = max(lead, ph)
                        break
            r["LeadPhase"] = lead or None
            y1 = (qd - timedelta(days=365)).isoformat()
            r["TrialsStarted12m"] = sum(1 for t in ts
                                        if t["StartDate"][:10] > y1)

            # ---- FDA ----
            evs = [e for e in events.get(iid, []) if e["Date"] <= q]
            orig = [e for e in evs if e["Event"] == "Approval"
                    and e.get("SubType") == "ORIG"]
            r["OrigApprovalsEver"] = len(orig)
            r["HasApprovedDrug"] = 1 if orig else 0
            r["Approvals12m"] = sum(1 for e in evs
                                    if e["Event"] == "Approval" and e["Date"] > y1)
            r["Rejections12m"] = sum(1 for e in evs
                                     if e["Event"] == "Rejection" and e["Date"] > y1)
            if evs:
                last = max(e["Date"] for e in evs)
                r["DaysSinceLastFDAEvent"] = (qd - date.fromisoformat(last)).days

            # ---- market reaction to trailing-12m events ----
            sts = [s for s in study.get(iid, [])
                   if y1 < s["EventDate"] <= q and s.get("CAR_m1_p1")]
            if sts:
                cars = [_num(s["CAR_m1_p1"]) for s in sts]
                cars = [x for x in cars if x is not None]
                drifts = [_num(s.get("Drift10")) for s in sts]
                drifts = [x for x in drifts if x is not None]
                if cars:
                    r["CAR12m_mean"] = round(sum(cars) / len(cars), 2)
                if drifts:
                    r["Drift12m_mean"] = round(sum(drifts) / len(drifts), 2)
                r["FDAEventsWithCAR12m"] = len(sts)

            # ---- relationships (FirstDate <= Q; undated = always known) --
            rl = [x for x in rels.get(iid, [])
                  if not x.get("FirstDate") or x["FirstDate"][:10] <= q]
            r["RelTotal"] = len(rl)
            r["RelTrial"] = sum(1 for x in rl if x["RelKind"] == "Trial collaboration")
            r["RelDeal"] = sum(1 for x in rl if x["RelKind"] == "Deal")
            r["RelInUniverse"] = sum(1 for x in rl if x.get("PartnerIID") not in ("", None)
                                     and str(x["PartnerIID"]) != str(iid))
            y2 = (qd - timedelta(days=730)).isoformat()
            r["Deals24m"] = sum(1 for x in rl if x["RelKind"] == "Deal"
                                and x.get("FirstDate") and x["FirstDate"][:10] > y2)
            r["LicensesEver"] = sum(1 for x in rl
                                    if x.get("AgreementType") == "License")
            r["CollabsEver"] = sum(1 for x in rl
                                   if x.get("AgreementType") == "Collaboration")

            # ---- v2: dynamics vs 4 quarters ago ----
            q4 = (qd - timedelta(days=365)).isoformat()
            fin4 = None
            for f4 in reversed(fins.get(iid, [])):
                if f4["PeriodEnd"] <= q4:
                    fin4 = f4
                    break
            if fin and fin4:
                c0, c4 = r.get("CashSTI"), None
                cash4 = _num(fin4.get("Cash"))
                sti4 = _num(fin4.get("ShortTermInvestments"))
                if cash4 is not None:
                    c4 = cash4 + (sti4 or 0)
                if c0 and c4:
                    r["dCash4q"] = round(c0 / c4, 3)
                s0 = r.get("SharesOutstanding")
                s4 = _num(fin4.get("SharesOutstanding"))
                if s0 and s4:
                    r["dShares4q"] = round(s0 / s4, 3)
            if r.get("RnD") is not None and r.get("TotalAssets"):
                r["RnDIntensity"] = round(r["RnD"] / r["TotalAssets"], 4)
            if r.get("CashSTI") is not None and r.get("TotalAssets"):
                r["CashToAssets"] = round(r["CashSTI"] / r["TotalAssets"], 4)
            first_fin = fins.get(iid, [])
            if first_fin:
                r["AgeYears"] = round((qd - date.fromisoformat(
                    first_fin[0]["PeriodEnd"])).days / 365.25, 1)

            # ---- v2: catalysts (start- and event-dated only) ----
            y2v = (qd - timedelta(days=730)).isoformat()
            r["Ph3Started24m"] = sum(
                1 for t in ts if t["StartDate"][:10] > y2v
                and "PHASE3" in (t.get("Phase") or ""))
            firsts = sorted(e["Date"] for e in orig)
            r["FirstApprovalRecent24m"] = 1 if (
                firsts and firsts[0] > y2v) else 0
            r["FDAEventsEver"] = len(evs)

            # ---- v2: hot therapeutic area from trial conditions ----
            HOT = ("obes", "oncolog", "cancer", "tumor", "immun",
                   "alzheim", "parkinson", "rare", "orphan", "cardio",
                   "nash", "steatohep")
            conds = " ".join((t.get("Conditions") or "").lower()
                             for t in ts[-40:])
            r["HotTA"] = 1 if any(h in conds for h in HOT) else 0

            # ---- price (optional) ----
            bars = bars_by_ticker.get(tick) or []
            if bars:
                upto = [b for b in bars if b["Date"] <= qd]
                if upto:
                    px = upto[-1]["AdjClose"]
                    r["PriceQ"] = round(px, 2) if px else None
                    if px and r.get("SharesOutstanding"):
                        r["MarketCap"] = round(px * r["SharesOutstanding"])
                    yr = [b["AdjClose"] for b in upto
                          if b["Date"] > qd - timedelta(days=365) and b["AdjClose"]]
                    if yr and px:
                        r["Drawdown52w"] = round((px / max(yr) - 1) * 100, 1)

            rows.append(r)
    return rows


def join_with_labels(features: list[dict]) -> list[dict]:
    """gold/model_panel.csv = features + labels on (IID, QuarterEnd)."""
    labels = {(r["IID"], r["QuarterEnd"]): r
              for r in _load(config.GOLD / "label_panel.csv")}
    out = []
    for f in features:
        lab = labels.get((str(f["IID"]), f["QuarterEnd"])) or {}
        row = dict(f)
        for k in ("AcquiredNext12m", "AcquiredNext24m", "MadeAcquisition12m",
                  "AnnounceDate", "Acquirer", "LabelSource"):
            row[k] = lab.get(k, "")
        out.append(row)
    return out


MODEL_COLS = FEATURE_COLS + ["AcquiredNext12m", "AcquiredNext24m",
                             "MadeAcquisition12m", "AnnounceDate",
                             "Acquirer", "LabelSource"]
