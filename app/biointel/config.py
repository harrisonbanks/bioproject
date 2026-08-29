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
            f"root and fill in {name}.")
    return v


_load_dotenv()

# --- paths -----------------------------------------------------------------
ROOT   = Path(__file__).resolve().parent.parent
DATA   = ROOT / "data"
BRONZE = DATA / "bronze"          # raw API responses, exactly as returned
SILVER = DATA / "silver"          # cleaned CSVs
GOLD   = DATA / "gold"            # analysis output

COMPANIES_CSV = SILVER / "companies.csv"
EVENTS_CSV    = SILVER / "events.csv"
PRICES_CSV    = SILVER / "prices.csv"
TRIALS_CSV    = SILVER / "trials.csv"
FINANCIALS_CSV = SILVER / "financials.csv"
SNAPSHOT_CSV  = SILVER / "financial_snapshot.csv"
PARTNERS_CSV  = SILVER / "partners.csv"
PARTNER_SUMMARY_CSV = SILVER / "partner_summary.csv"
DEALS_CSV     = SILVER / "deals.csv"
COUNTERPARTY_CSV = SILVER / "deal_counterparties.csv"
RELATIONSHIPS_CSV = SILVER / "relationships.csv"
RELATIONSHIPS_CSV = SILVER / "relationships.csv"

for p in (BRONZE, SILVER, GOLD):
    p.mkdir(parents=True, exist_ok=True)

# --- endpoints -------------------------------------------------------------
SEC_TICKERS  = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBS     = "https://data.sec.gov/submissions/CIK{cik10}.json"
AV_QUERY     = "https://www.alphavantage.co/query"
FDA_DRUGSFDA = "https://api.fda.gov/drug/drugsfda.json"
FDA_CRL      = "https://api.fda.gov/transparency/crl.json"
YAHOO_CHART  = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
CTGOV_BASE   = "https://clinicaltrials.gov"

# --- behaviour -------------------------------------------------------------
SEC_RATE_LIMIT = 0.11      # seconds between SEC calls (limit is 10/sec)
WINDOW_PRE     = 10        # trading days before t0
WINDOW_POST    = 10        # trading days after t0
PRICE_PAD_DAYS = 90        # calendar days either side of event to request
