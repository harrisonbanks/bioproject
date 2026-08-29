"""Configuration. Edit USER_AGENT and ALPHA_VANTAGE_KEY before first run."""
from pathlib import Path

# --- credentials -----------------------------------------------------------
# SEC requires a descriptive User-Agent with a contact email or returns 403.
USER_AGENT = "Harrison Banks harrybanksm02@gmail.com"

# Alpha Vantage free tier: 25 calls/day. Used only for company descriptions.
ALPHA_VANTAGE_KEY = "HMSYBCQS3CPO2P02"

# --- paths -----------------------------------------------------------------
ROOT   = Path(__file__).resolve().parent.parent
DATA   = ROOT / "data"
BRONZE = DATA / "bronze"          # raw API responses, exactly as returned
SILVER = DATA / "silver"          # cleaned CSVs
GOLD   = DATA / "gold"            # analysis output

COMPANIES_CSV = SILVER / "companies.csv"
EVENTS_CSV    = SILVER / "events.csv"
PRICES_CSV    = SILVER / "prices.csv"

for p in (BRONZE, SILVER, GOLD):
    p.mkdir(parents=True, exist_ok=True)

# --- endpoints -------------------------------------------------------------
SEC_TICKERS  = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBS     = "https://data.sec.gov/submissions/CIK{cik10}.json"
AV_QUERY     = "https://www.alphavantage.co/query"
FDA_DRUGSFDA = "https://api.fda.gov/drug/drugsfda.json"
FDA_CRL      = "https://api.fda.gov/transparency/crl.json"
YAHOO_CHART  = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

# --- behaviour -------------------------------------------------------------
SEC_RATE_LIMIT = 0.11      # seconds between SEC calls (limit is 10/sec)
WINDOW_PRE     = 10        # trading days before t0
WINDOW_POST    = 10        # trading days after t0
PRICE_PAD_DAYS = 90        # calendar days either side of event to request
