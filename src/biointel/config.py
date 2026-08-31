# src/biointel/config.py
"""Configuration: paths, endpoints, behaviour; credentials from the environment."""

import os
from pathlib import Path

# --- settings from the environment ----------------------------------------
# Values come from os.environ; <repo-root>/.env is loaded if present
# (names and placeholders in .env.example). Nothing secret lives in code.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv() -> None:
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def require(name: str) -> str:
    """Return the environment variable or fail fast naming it (6.4)."""
    v = os.environ.get(name, "")
    if not v:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env at the repository "
            f"root and fill in {name}."
        )
    return v


_load_dotenv()

# --- paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # <repo-root>: src/biointel/config.py
DATA = ROOT / "data"
BRONZE = DATA / "bronze"  # raw API responses, exactly as returned (files, P16)
DUCKDB = DATA / "biointel.duckdb"  # every silver, gold and ledger table (P16)
EXPORTS = DATA / "exports"  # generated reports and CSV exports; disposable, regenerated
SNAPSHOTS = DATA / "snapshots"  # `freeze` copies of the database file
# Pre-migration CSV folders: read by `migrate` once, then renamed to the
# frozen names below. Live code never reads or writes them (P16).
SILVER_CSV_SRC = DATA / "silver"
GOLD_CSV_SRC = DATA / "gold"
FROZEN_TAG = "20260830"
# LEGACY read paths only (P7 amendment, 2026-08-30): baselines.py, improve.holdout
# and fit.fit read the CSVs as frozen on migration day. Not used by live code.
SILVER = DATA / f"silver_frozen_{FROZEN_TAG}"
GOLD = DATA / f"gold_frozen_{FROZEN_TAG}"

COMPANIES_CSV = SILVER / "companies.csv"
EVENTS_CSV = SILVER / "events.csv"
PRICES_CSV = SILVER / "prices.csv"
TRIALS_CSV = SILVER / "trials.csv"
FINANCIALS_CSV = SILVER / "financials.csv"
SNAPSHOT_CSV = SILVER / "financial_snapshot.csv"
PARTNERS_CSV = SILVER / "partners.csv"
PARTNER_SUMMARY_CSV = SILVER / "partner_summary.csv"
DEALS_CSV = SILVER / "deals.csv"
COUNTERPARTY_CSV = SILVER / "deal_counterparties.csv"
RELATIONSHIPS_CSV = SILVER / "relationships.csv"

for p in (BRONZE, EXPORTS, SNAPSHOTS):
    p.mkdir(parents=True, exist_ok=True)

# --- endpoints -------------------------------------------------------------
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBS = "https://data.sec.gov/submissions/CIK{cik10}.json"
AV_QUERY = "https://www.alphavantage.co/query"
FDA_DRUGSFDA = "https://api.fda.gov/drug/drugsfda.json"
FDA_CRL = "https://api.fda.gov/transparency/crl.json"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
CTGOV_BASE = "https://clinicaltrials.gov"
SEC_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
SEC_SUBS_PAGE = "https://data.sec.gov/submissions/{name}"
SEC_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
SEC_ARCHIVE_DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
SEC_XBRL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
FDA_ORANGE_BOOK = "https://www.fda.gov/media/76860/download?attachment"
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
WIKI_API = "https://en.wikipedia.org/w/api.php"

# --- behaviour -------------------------------------------------------------
SEC_RATE_LIMIT = 0.11  # seconds between SEC calls (limit is 10/sec)
WINDOW_PRE = 10  # trading days before t0
WINDOW_POST = 10  # trading days after t0
PRICE_PAD_DAYS = 90  # calendar days either side of event to request
