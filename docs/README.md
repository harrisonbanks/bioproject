docs/README.md

# biointel — Bioindustry Intelligence Platform

Nightly-refreshable M&A intelligence for ~1,400 listed drug companies from
free public data: an M&A target screen and buyer–target pairing (Model 1)
and an FDA-catalyst price-action model (Model 2; research: `docs/20260830_v2_FDA_Catalyst_Research.md`, requirements: `docs/20260830_v1_FDA_Catalyst_Product_Design.md`); Model 4 Horizon Scanning (entity discovery): `docs/20260830_v1_Horizon_Scanning_Design.md`. Design: see
`docs/20260830_v3_Ontology_and_Matching_Design.md`; rules:
`docs/20260830_v2_Design_Principles.md`; state: `docs/PROJECT_STATUS.md`;
diagrams: current state `docs/20260829_v1_System_Diagram.png`, target state `docs/20260830_v1_System_Diagram_TARGET_STATE.png`; plan and gate ledger: `docs/20260830_v1_Implementation_Plan.md`.

## Install (Windows, Python 3.13, venv + pip)

```
git clone https://github.com/harrisonbanks/bioproject.git bioindustry
cd bioindustry
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"        # add ".[ner]" for spacy (cparty-all)
Copy-Item .env.example .env              # then fill in the two values
```

`.env` (git-ignored) holds `BIOINTEL_USER_AGENT` (SEC requires a
descriptive agent with a contact email) and `BIOINTEL_ALPHA_VANTAGE_KEY`
(used only by `add`). No credential lives in code.

## Layout

```
src/biointel/           package; run as  python -m biointel <command>
  interfaces/cli.py     55 commands (python -m biointel prints the list)
  config.py             paths, every HTTP endpoint, windows, .env loader
  store.py              all HTTP through one cache with manifests
  sources/              one adapter per public source
  universe, pipeline, labels, features, study, fit, improve, pairs,
  baselines, score      universe → tables → panels → models
scripts/                diagnostics; scripts/refactor/ (migration tooling)
tests/unit/             pytest (python -m pytest tests/unit)
docs/                   status, design, runbook, handoff, diagram, baseline hashes
data/                   git-ignored: bronze (raw) → silver (tables) → gold (panels, outputs)
```

## Rebuild from empty data (in order)

```
python -m biointel universe-probe
python -m biointel universe
python -m biointel ingest 1400          # financials, trials, FDA events, deals per company
python -m biointel partners
python -m biointel relationships
python -m biointel harvest
python -m biointel verify-fill
python -m biointel qa
python -m biointel qa-corroborate
python -m biointel labels
python -m biointel study-all            # Model 2
python -m biointel features
python -m biointel orangebook-probe
python -m biointel predict              # Model 1: ranked targets + best-fit acquirers
python -m biointel pairs-full-exact
```

Optional: `text-ingest N` (10-K text; adds nothing to accuracy), `cparty-all`
(needs spacy), `patents-sql` / `patents-import` (BigQuery console step),
`chembl-ingest`.

## Data layers

- **bronze** — raw API responses exactly as returned, with URL and
  timestamp manifests; never edited.
- **silver** — cleaned tables, model-agnostic (any model may read any table).
- **gold** — derived panels and outputs: `label_panel.csv`,
  `event_study.csv`, `feature_panel.csv`, `model_panel.csv`,
  `ma_predictions.csv`, `pair_full_exact_report.txt`.

## Validated numbers (see PROJECT_STATUS 0.5 for the ledger)

Target screen 2.2× chance on held-out deals (both holdout accesses spent);
pairing engine (MASS-exact on trial diseases): true target in the top 10 of
~860 candidates 27% of the time; event study: approvals ≈ +0.3%,
rejections −7% / −22% CAR[−1,+1]. Substrate hierarchy: diseases >
mechanisms > patents.

## Regression check

`docs/regression_baseline.txt` holds SHA-256 hashes of `predict` and
`pairs-full-exact` outputs; every refactor gate re-runs both and compares.

## Entity resolution

Names are matched by `match.canon()`: uppercase, drop apostrophes, `&` →
`AND`, strip non-alphanumerics and legal suffixes, then exact equality.
Failures are missing, never wrong. FDA trade names are bridged by the
`FDAAliases` column in `companies.csv` (`scripts/suggest_aliases.py`).

## Contributing

Branch per person (`jason/…`, `harrison/…`), pull request into `main`.
Definition of done: `python -m ruff check src scripts tests`,
`python -m ruff format --check src scripts tests`,
`python -m pytest tests/unit`, and the regression hashes.
