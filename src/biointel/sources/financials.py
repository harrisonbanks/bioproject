"""SEC XBRL CompanyFacts.

  GET https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

Free, no API key. Requires a descriptive User-Agent with a contact email
or EDGAR returns 403. Rate limit 10 requests/second. CIK is zero-padded
to 10 digits.

Returns EVERY structured fact the company has ever filed, in one call.
Structure:

  {"cik": 320193, "entityName": "Apple Inc.",
   "facts": {"us-gaap": {"CONCEPT": {"units": {"USD": [
       {"end":"2024-09-28","val":391035000000,"accn":"...",
        "fy":2024,"fp":"FY","form":"10-K","filed":"2024-11-01",
        "frame":"CY2024"}]}}},
             "dei": {...}}}

KEY TRAP: not all companies use the same tags. Some report `Revenues`,
others `RevenueFromContractWithCustomerExcludingAssessedTax` (common after
ASC 606 took effect in 2018). Never assume a tag exists -- inspect what the
company actually reports. Hence SYNONYMS below and inventory_tags().

Coverage: XBRL was first required by the SEC in 2009, mandatory for large
accelerated filers that year and extended to all filers by 2011. No history
before then.
"""

from __future__ import annotations

from collections import defaultdict

from biointel.store import fetch_json

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

# Ordered by preference. First tag a company actually reports wins.
SYNONYMS = {
    "Cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndDueFromBanks",
    ],
    "ShortTermInvestments": [
        "ShortTermInvestments",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "MarketableSecuritiesCurrent",
    ],
    "Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "RnD": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ],
    "OpEx": [
        "OperatingExpenses",
        "CostsAndExpenses",
    ],
    "OperatingIncome": [
        "OperatingIncomeLoss",
    ],
    "NetIncome": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "TotalAssets": ["Assets"],
    "TotalLiabilities": ["Liabilities"],
    "Equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "LongTermDebt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
    "NetCashOperating": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
}

SHARES = ["EntityCommonStockSharesOutstanding"]  # dei taxonomy

# IFRS taxonomy for foreign private issuers (AstraZeneca, Takeda file 20-F
# under ifrs-full; their facts carry NO us-gaap section at all). Tag list
# validated against the cached AstraZeneca CompanyFacts response.
IFRS_SYNONYMS = {
    "Cash": [
        "CashAndCashEquivalents",
        "Cash",
    ],
    "ShortTermInvestments": [
        "ShorttermDepositsNotClassifiedAsCashEquivalents",
        "CurrentFinancialAssetsAtFairValueThroughProfitOrLoss",
    ],
    "Revenue": [
        "Revenue",
        "RevenueFromContractsWithCustomers",
        "RevenueFromSaleOfGoods",
    ],
    "RnD": ["ResearchAndDevelopmentExpense"],
    "OpEx": [],
    "OperatingIncome": ["ProfitLossFromOperatingActivities"],
    "NetIncome": ["ProfitLoss", "ProfitLossAttributableToOwnersOfParent"],
    "TotalAssets": ["Assets"],
    "TotalLiabilities": ["Liabilities"],
    "Equity": ["Equity", "EquityAttributableToOwnersOfParent"],
    "LongTermDebt": ["LongtermBorrowings", "Borrowings"],
    "NetCashOperating": ["CashFlowsFromUsedInOperatingActivities"],
}


def company_facts(cik10: str) -> dict:
    return fetch_json(FACTS_URL.format(cik10=str(cik10).zfill(10)), tag="sec_companyfacts")


def inventory_tags(cik10: str) -> dict[str, int]:
    """Which us-gaap tags this company actually reports, with fact counts.

    Run this BEFORE fixing a tag set. The whole point of SYNONYMS is that
    the answer differs company to company.
    """
    try:
        data = company_facts(cik10)
    except Exception:
        return {}
    out = {}
    for tag, body in (data.get("facts", {}).get("us-gaap", {}) or {}).items():
        n = sum(len(v) for v in (body.get("units") or {}).values())
        out[tag] = n
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _series(data: dict, taxonomy: str, tags: list[str]) -> list[dict]:
    """First tag in `tags` that the company reports, as a fact list."""
    facts = (data.get("facts", {}) or {}).get(taxonomy, {}) or {}
    for tag in tags:
        body = facts.get(tag)
        if not body:
            continue
        units = body.get("units") or {}
        for unit in ("USD", "shares", "pure"):
            if unit in units and units[unit]:
                return [{**f, "_tag": tag, "_unit": unit} for f in units[unit]]
        for unit, vals in units.items():
            if vals:
                return [{**f, "_tag": tag, "_unit": unit} for f in vals]
    return []


def _pick(rows: list[dict], form_prefix: str | None = None) -> dict[str, dict]:
    """Latest fact per period end. Later `filed` wins, so restatements
    supersede originals."""
    best: dict[str, dict] = {}
    for f in rows:
        end = f.get("end")
        if not end:
            continue
        if form_prefix and not str(f.get("form", "")).startswith(form_prefix):
            continue
        cur = best.get(end)
        if cur is None or str(f.get("filed", "")) > str(cur.get("filed", "")):
            best[end] = f
    return best


def financial_series(cik10: str) -> list[dict]:
    """One row per period end, with whichever concepts the company reports.

    Period rows carry the form (10-K / 10-Q), fiscal year and period, and
    the accession number, so every value is traceable to a filing.
    """
    try:
        data = company_facts(cik10)
    except Exception:
        return []

    by_end: dict[str, dict] = defaultdict(dict)
    tags_used: dict[str, str] = {}

    # Taxonomy detection: 20-F filers carry ifrs-full and no us-gaap.
    have = set((data.get("facts") or {}).keys())
    if "us-gaap" in have:
        taxonomy, synonyms = "us-gaap", SYNONYMS
    elif "ifrs-full" in have:
        taxonomy, synonyms = "ifrs-full", IFRS_SYNONYMS
    else:
        return []

    for field, tags in synonyms.items():
        rows = _series(data, taxonomy, tags)
        if not rows:
            continue
        tags_used[field] = rows[0]["_tag"]
        unit = rows[0].get("_unit", "")
        for end, f in _pick(rows).items():
            by_end[end][field] = f.get("val")
            if unit and unit != "USD":
                by_end[end]["_currency"] = unit
            by_end[end]["_form"] = f.get("form")
            by_end[end]["_fy"] = f.get("fy")
            by_end[end]["_fp"] = f.get("fp")
            by_end[end]["_accn"] = f.get("accn")
            by_end[end]["_filed"] = f.get("filed")
            by_end[end]["_start"] = f.get("start")

    for end, f in _pick(_series(data, "dei", SHARES)).items():
        by_end[end]["SharesOutstanding"] = f.get("val")

    out = []
    for end in sorted(by_end):
        r = {"PeriodEnd": end, "Currency": by_end[end].get("_currency", "USD")}
        r.update(by_end[end])
        r["_tags_used"] = "; ".join(f"{k}={v}" for k, v in sorted(tags_used.items()))
        out.append(r)
    return out


def _duration_facts(data: dict, taxonomy: str, tags: list[str]) -> list[dict]:
    """Duration facts with start and end, latest filing per (start, end)."""
    rows = _series(data, taxonomy, tags)
    best: dict[tuple, dict] = {}
    for f in rows:
        st, en = f.get("start"), f.get("end")
        if not st or not en:
            continue
        cur = best.get((st, en))
        if cur is None or str(f.get("filed", "")) > str(cur.get("filed", "")):
            best[(st, en)] = f
    out = []
    from datetime import date

    for (st, en), f in best.items():
        try:
            d = (date.fromisoformat(en) - date.fromisoformat(st)).days + 1
        except Exception:
            continue
        out.append({**f, "_start": st, "_end": en, "_days": d})
    out.sort(key=lambda r: r["_end"])
    return out


def ttm_operating_cash_flow(cik10: str) -> dict:
    """Trailing twelve months operating cash flow.

    Cash flow statements are CUMULATIVE year-to-date, not per-quarter. A
    10-Q for Q2 reports six months, Q3 reports nine, and the 10-K reports
    twelve. There is no three-month column, so a single reported figure
    cannot be annualized -- that is what produced Sarepta at 836 months of
    runway from a six-month figure that netted near zero.

    Method, in order of preference:
      1. Use the most recent ~365-day fact directly. That is a real annual
         figure and needs no arithmetic.
      2. Otherwise take the latest year-to-date fact, add the prior full
         year, and subtract the matching year-to-date period a year
         earlier. This is the standard TTM construction.
      3. Otherwise fall back to the longest available period, annualized,
         and flag it as approximate.
    """
    try:
        data = company_facts(cik10)
    except Exception:
        return {}

    have = set((data.get("facts") or {}).keys())
    if "us-gaap" in have:
        facts = _duration_facts(data, "us-gaap", SYNONYMS["NetCashOperating"])
    else:
        facts = _duration_facts(data, "ifrs-full", IFRS_SYNONYMS["NetCashOperating"])
    if not facts:
        return {}

    annual = [f for f in facts if 330 <= f["_days"] <= 400]
    latest = facts[-1]

    # 1. a real annual figure that is also the most recent report
    if annual and annual[-1]["_end"] == latest["_end"]:
        a = annual[-1]
        return {
            "OCF_TTM": a["val"],
            "TTM_Method": "annual",
            "TTM_Start": a["_start"],
            "TTM_End": a["_end"],
        }

    # 2. YTD + prior full year - prior matching YTD
    if annual:
        prior = annual[-1]
        ytd = latest
        if ytd["_end"] > prior["_end"]:
            match = None
            for f in facts:
                if f["_end"] >= prior["_end"]:
                    continue
                if abs(f["_days"] - ytd["_days"]) <= 20:
                    if match is None or f["_end"] > match["_end"]:
                        match = f
            if match is not None:
                val = ytd["val"] + prior["val"] - match["val"]
                return {
                    "OCF_TTM": val,
                    "TTM_Method": "ytd+fy-prior_ytd",
                    "TTM_Start": match["_end"],
                    "TTM_End": ytd["_end"],
                }
        return {
            "OCF_TTM": prior["val"],
            "TTM_Method": "last_full_year",
            "TTM_Start": prior["_start"],
            "TTM_End": prior["_end"],
        }

    # 3. longest period available, annualized
    longest = max(facts, key=lambda f: f["_days"])
    return {
        "OCF_TTM": longest["val"] * 365.0 / longest["_days"],
        "TTM_Method": f"annualized_from_{longest['_days']}d",
        "TTM_Start": longest["_start"],
        "TTM_End": longest["_end"],
    }


def latest_snapshot(cik10: str) -> dict:
    """Latest balance sheet position plus TTM burn and runway.

    Burn comes from trailing twelve months operating cash flow, not from a
    single reported figure. Negative OCF means the company is burning.

    Runway is months of cash at that rate. Deliberately crude: it assumes
    constant burn, ignores financing raised since the last filing, and
    ignores milestone-driven cost steps. It is a first-pass read on whether
    a company must raise, license, or sell -- not a forecast.
    """
    rows = financial_series(cik10)
    if not rows:
        return {}

    def last(field):
        for r in reversed(rows):
            if r.get(field) is not None:
                return r[field], r["PeriodEnd"]
        return None, None

    cash, cash_end = last("Cash")
    sti, _ = last("ShortTermInvestments")
    rnd, _ = last("RnD")
    rev, _ = last("Revenue")
    shares, _ = last("SharesOutstanding")
    debt, _ = last("LongTermDebt")

    total_cash = (cash or 0) + (sti or 0)

    ttm = ttm_operating_cash_flow(cik10)
    ocf = ttm.get("OCF_TTM")

    burn_annual = abs(ocf) if (ocf is not None and ocf < 0) else None
    runway_months = None
    if burn_annual and burn_annual > 0 and total_cash:
        runway_months = round(total_cash / (burn_annual / 12.0), 1)

    return {
        "Cash": cash,
        "CashAsOf": cash_end,
        "ShortTermInvestments": sti,
        "TotalCash": total_cash or None,
        "Revenue": rev,
        "RnD": rnd,
        "LongTermDebt": debt,
        "SharesOutstanding": shares,
        "NetCashOperating": ocf,
        "OCFAsOf": ttm.get("TTM_End"),
        "TTMMethod": ttm.get("TTM_Method"),
        "BurnAnnual": round(burn_annual) if burn_annual else None,
        "RunwayMonths": runway_months,
        "Periods": len(rows),
    }
