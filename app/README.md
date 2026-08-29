# biointel

Python port of the `20260724_securitymaster_v03.xlsm` pipeline.
Same endpoints, same logic, same outputs. Nothing new added.

## Install

```
pip install -r requirements.txt
```

Edit `biointel/config.py`: set `USER_AGENT` (SEC returns 403 without a
descriptive one) and `ALPHA_VANTAGE_KEY`.

## Migrate the existing workbook

```
python migrate_from_excel.py path/to/20260724_securitymaster_v03.xlsm
```

Pulls `1_Companies` -> `data/silver/companies.csv` and
`Events_Master` -> `data/silver/events.csv`.

## Commands

```
python cli.py add REGN ARQT BBIO      add companies
python cli.py events 9                FDA events for one IID
python cli.py events-all              every company (replaces 13 button presses)
python cli.py window "BLA 761303" 2024-03-22
python cli.py list                    show companies
python cli.py coverage                what was fetched, and when
```

## What maps to what

| Excel | Python |
|---|---|
| `CompanyLookup` query | `sources/sec.py` + `sources/alphavantage.py` |
| `AddCompany` macro | `pipeline.add_company()` |
| `Events` query | `sources/fda.py` |
| `GetEvents` macro | `pipeline.get_events()` |
| `PriceWindow` query | `sources/prices.py` |
| Settings tables | `config.py` |
| `1_Companies` sheet | `data/silver/companies.csv` |
| `Events_Master` sheet | `data/silver/events.csv` |
| `Window` sheet | `data/gold/window.csv` |
| (none) | `data/bronze/` — raw responses |

`GetEvents` has no counterpart because it only existed to copy query output
somewhere permanent before the next refresh overwrote it. Power Query has no
cache; CSVs do.

## Layers

- **bronze** — raw API responses exactly as returned, plus URL and fetch
  timestamp. Never parsed, never filtered. A filter change is a re-parse,
  not a re-download.
- **silver** — cleaned CSVs. Open in Excel.
- **gold** — analysis output.

`fetch_json(..., cache=True)` is the default, so a repeat call returns the
stored response without hitting the network. Pass `cache=False` to force a
refresh.

## Behaviour preserved from the Excel version

- Canonical name matching: uppercase, drop apostrophes, `&` -> ` AND `,
  strip non-alphanumerics, remove legal suffixes, require **exact equality**.
  Contamination is impossible; subsidiaries fail as missing, not wrong.
- Approvals filtered to `submission_status == "AP"` and
  (`ORIG` or `EFFICACY`). `LABELING` and `MANUF (CMC)` discarded.
- Events deduped on (Event, Date, AppNo).
- CRL `application_number` has its `/Original n` suffix stripped so two rows
  for one decision collapse.
- t0 = first trading session on or after the event date.
- RelDay is a row offset within the ticker's own series, not calendar
  arithmetic.
- `PctFromT0` from adjusted close at RelDay 0.
- Alpha Vantage failure strings unchanged: `RATE LIMIT - 25 lookups used
  today`, `UNAVAILABLE - check the API key`, `NOT PROVIDED`.
- SEC calls rate-limited to 10/sec.

## Tested

Parsers were tested against real API responses:

- CRL parse: 5 Regeneron records -> 4 events after dedup
- Verification filter: `Pfizer Ireland Pharmaceuticals` excluded from a
  `PFIZER INC` lookup
- Approval filter: 5 submissions -> 2 kept (EFFICACY + ORIG)
- Event window: real Yahoo PFE data -> 21 rows, RelDay -10..+10,
  PctFromT0 = 0 at t0, adjclose != close
- Next-trading-day rule: Sat 2024-03-23 -> t0 Mon 2024-03-25
- Migration: 16 companies and 689 event rows out of the live workbook

**Not tested:** live network calls. Run `python cli.py add REGN` first and
confirm it returns a real company name before trusting anything else.

## Aliases

FDA uses trade names where SEC uses legal registrant names:

| SEC | FDA |
|---|---|
| JOHNSON & JOHNSON | JANSSEN PHARMS, JANSSEN BIOTECH, JANSSEN PRODS |
| Merck & Co., Inc. | MERCK, MERCK SHARP DOHME, MSD SUB MERCK |
| ELI LILLY & Co | LILLY, ELI LILLY AND CO, ELI LILLY CO |
| TAKEDA PHARMACEUTICAL CO LTD | TAKEDA PHARMS USA |

No string transform bridges JOHNSON & JOHNSON to JANSSEN. Aliases are a
judgment about corporate structure, so they are entered, not inferred.

```
python suggest_aliases.py            review every company without aliases
python suggest_aliases.py --iid 6    redo one company
python suggest_aliases.py --list     dump all FDA sponsor names
```

Per company it shows scored candidates. You can pick numbers, type
`s janssen` to search all sponsor names for a word, or `d` when done.
Selections are written to the `FDAAliases` column in `companies.csv`
(semicolon separated) and can be edited by hand afterwards.

Then re-run `python cli.py events-all`. Each alias is searched separately
and results are unioned; verification still requires exact canonical
equality against the alias searched, so no other company's records can
enter.

## Clinical trials

ClinicalTrials.gov API v2. Free, no key. Base `https://clinicaltrials.gov/api/v2/`.
The v1 API is fully retired.

```
python cli.py trials IID       one company
python cli.py trials-all       every company
python cli.py calendar IID     pipeline calendar: trials + FDA, date order
python cli.py sponsors         top CT.gov lead sponsors (head of distribution)
```

Writes `data/silver/trials.csv`, one row per trial, deduped on (IID, NCTId).

### Sponsor matching

Uses the Essie advanced filter:

```
filter.advanced=AREA[LeadSponsorName]Regeneron
```

`AREA[Field]Value` targets a specific field rather than doing a general
keyword search. It is substring-tolerant, so a distinctive token usually
suffices. This is a **different mechanism** from the FDA join, which needs
exact canonical equality.

Default search term is the first distinctive word of the SEC name, after
`canon()` strips legal suffixes and descriptors. Override per company by
adding a `CTGovName` column to `companies.csv`.

### Known traps, all handled

- **Phase** values are exact strings: `PHASE1`, not "Phase 1" or "phase1".
- **Status** values are case-sensitive enums: `RECRUITING`, `COMPLETED`,
  `ACTIVE_NOT_RECRUITING`, `TERMINATED`, `WITHDRAWN`, `NOT_YET_RECRUITING`,
  `SUSPENDED`, `ENROLLING_BY_INVITATION`, `UNKNOWN`.
- **Arrays can be null or empty** -- conditions, interventions,
  collaborators. `_flatten()` is defensive on every nested path.
- **Dates are not normalized.** `2024-01-15`, `January 2024`, and
  `January 15, 2024` all occur. `parse_date()` handles all three and
  returns `None` rather than guessing on anything else. Month-only dates
  get day 01, which is an approximation, not a real day.
- **Pagination is cursor-based** (`pageToken`), not v1's offset model.
  `pageSize` max is 1000; capped at 10 pages per sponsor.
- **`sponsors` shows only the head of the distribution.** For a
  high-cardinality field like LeadSponsorName, the smallest sponsor
  returned has several hundred studies and roughly 50,900 smaller ones are
  absent. Fine for large caps, useless for small ones -- use `trials` with
  the AREA filter for those.

### Pipeline calendar

`calendar IID` merges `trials.csv` and `events.csv` into one dated
timeline per company: trial phases and FDA actions together. Writes
`data/gold/calendar_{IID}.csv`.

Note: this covers **clinical trial phase and past FDA action dates**.
Forward-looking PDUFA goal dates are not included and cannot be, because
21 CFR 314.430 bars FDA from confirming an application exists until the
sponsor discloses it.

## Financials

SEC XBRL CompanyFacts.
`GET https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Free, no API key. Requires a descriptive User-Agent with contact email or
EDGAR returns 403. Rate limit 10 req/sec. **Keyed on CIK**, so there is no
name matching and none of the alias problems that affect FDA and CT.gov.

```
python cli.py backfill        fill CIK for rows migrated from Excel
python cli.py fin IID         one company
python cli.py fin-all         every company
python cli.py snapshot        cash, burn and runway per company
python cli.py tags IID        which XBRL tags a company actually reports
```

Run `backfill` first. Rows imported from the workbook have a blank CIK and
financials cannot be fetched without it.

Writes `data/silver/financials.csv` (one row per period end) and
`data/silver/financial_snapshot.csv` (one row per company).

### The tag problem

Not all companies use the same XBRL tags. Some report `Revenues`, others
`RevenueFromContractWithCustomerExcludingAssessedTax`, which became common
after ASC 606 took effect in 2018. Never assume a tag exists.

`SYNONYMS` in `sources/financials.py` lists alternates per field in
preference order; the first tag a company actually reports wins, and the
tag chosen is recorded in `_tags_used`. `cli.py tags IID` shows exactly
which tags a given company reports, with fact counts.

Coverage begins 2009, when XBRL was first required, extended to all filers
by 2011.

### Restatements

One request returns every fact the company has ever filed, including
restatements. `_pick()` keeps the fact with the latest `filed` date for
each period end, so a 10-K/A supersedes the original 10-K.

Every row carries `Accession` and `Filed`, so any value can be traced to
its filing.

### Burn and runway

`BurnAnnual` comes from `NetCashProvidedByUsedInOperatingActivities` --
actual cash consumed, not an expense line. Negative operating cash flow
means the company is burning. The figure is annualized from the reported
period length, so a quarterly 10-Q value scales by roughly 4.

`RunwayMonths` = (cash + short-term investments) / (annual burn / 12).

This is deliberately crude. It assumes constant burn, ignores financing
already raised or committed, and ignores milestone-driven cost steps.
It is the standard first-pass indicator of whether a company must raise,
license, or sell -- not a forecast.

Companies with positive operating cash flow show no runway, which is
correct: they are not burning.

## Partnership network

Derived from ClinicalTrials.gov collaborators. **No API calls** -- built
entirely from `trials.csv`.

```
python cli.py partners        build the network
python cli.py partners-of IID one company's collaborators
```

Writes `data/silver/partners.csv` (one row per company-collaborator pair)
and `data/silver/partner_summary.csv` (one row per company, counts by
type).

### What a collaborator is

Every study lists collaborators alongside the lead sponsor: co-developing
pharma companies, CROs, diagnostics and device firms, academic centres,
government bodies. Each pairing is documented partnership evidence with a
date and therapeutic area attached -- observable fact, not inference from
what a company does.

### Collaborator types

Keyword rules run first, then the CT.gov agency class as fallback:

`Industry (unclassified)` · `CRO` · `CDMO/Manufacturing` ·
`Diagnostics/Lab` · `Device/Delivery` · `Imaging` · `Academic` ·
`Foundation/Nonprofit` · `Government` · `Network` · `Other`

Keywords beat the CT.gov class because `INDUSTRY` covers a co-developing
pharma company and a CRO equally. The raw class is carried through in
`CTGovClass` so a wrong guess is visible.

This is a heuristic and should be reviewed. `Industry (unclassified)` is
the bucket for industry collaborators no rule matched.

### Name normalisation

Reuses `canon()` from the FDA join, then drops single-character tokens.
Necessary because punctuated abbreviations fragment: "Sanofi S.A."
canonicalizes to `SANOFI S A`, where `canon()` removes `SA` as a whole
word but not the split letters. Without the extra step, "Sanofi" and
"Sanofi S.A." remain separate organisations.

Verified: Sanofi / Sanofi S.A., Bayer AG / Bayer A.G., Eli Lilly and
Company / Eli Lilly & Co all merge. `Roche` and `F. Hoffmann-La Roche`
stay separate -- the matcher fails as distinct, never as wrong.

A company is never counted as its own collaborator.

### Requires a re-pull

The `Collaborators` field was added after the first trials pull. If
`trials.csv` has no `Collaborators` column, `partners` will say so.
Delete `data/silver/trials.csv` and run `trials-all` again.
