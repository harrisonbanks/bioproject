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
