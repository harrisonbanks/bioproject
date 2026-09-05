# docs/20260905_v1_Administration_Use_Case.md

# Use case: Administration — global and per use case

Bioindustry Intelligence Platform · 2026-09-05 · defined and scoped; build
not started. Inventory read from the live command list (70 commands,
`python -m biointel`, 2026-09-05), not from memory.

## 1. Purpose and principles
1. The operator is one local person who uses and manages the whole system.
   There are no accounts, roles or permissions; Administration is a
   workspace in the GUI, selected like any other function.
2. Every administrative action is a call to an existing gated function
   through the local service. The GUI never writes to the database or the
   library directly (P21). Where an action does not yet exist as a function,
   it is listed below as **new** and is built as a command first, screen
   second.
3. Roughly 70% of the administrative *functions* already exist as commands.
   What does not exist is any *view* over them — status boards, queues,
   comparisons, history. Most of this use case is reading the ledger, the
   coverage table, the registry and the review tables and laying them out.
4. Every status line and every action carries a wall-clock timestamp
   (operating rule of 2026-09-05).

## 2. Global administration

### 2.1 Universe — the company list
| Function | Exists | New |
|---|---|---|
| add a listed company | `add TICKER` | |
| add a private / unlisted stub | `add --stub NAME --cik N` | |
| rebuild by the rule of record | `universe`, `universe-probe` | |
| list, browse | `list`, `sponsors` | |
| retire a member with reason | | **new** |
| stub-approval queue as a screen | text file today | **new** |
| per-member coverage (which collectors ran, when) | `coverage` (global) | per-member view **new** |

### 2.2 Data collection — every source, run and watched in one place
| Function | Exists | New |
|---|---|---|
| per-source collectors | `events-all`, `trials-all`, `fin-all`, `deals-all`, `cparty-all`, `mine-pdufa run`, `stakes run`, `harvest`, `ingest`, `calendar-forward` | |
| probes before parsers (rule 4.20) | `universe-probe`, `orangebook-probe`, `chembl-probe`, `stakes probe`, `priorities probe`, `fetch-probe` | |
| what was fetched, when | `coverage` | |
| status board: per source — last run, rows, failures, freshness | | **new** |
| start / stop / resume with the timestamped log tail | commands run to completion today | **new** (background jobs) |
| fetch-pool switch, rate, back-off events | `config.FETCH_POOL_*` | screen **new** |
| collection widening: by holder, by research group (Entity Browser §6) | | **new** collectors, own gates |

### 2.3 Library — the document store
| Function | Exists | New |
|---|---|---|
| add, import, index, find, show, open, list, view, manifest, merge, verify, dedupe, retire-capture | `library …` (the most complete admin surface in the system) | |
| storage totals per source system | | **new** |
| two-document references (1,161 left after repair-headers) as a review list | | **new** |
| header-vs-document integrity check | | **new** |

### 2.4 Ledger and results
| Function | Exists | New |
|---|---|---|
| every run; runs per model; render a report from its record | `report ledger`, `report runs MODEL`, `report MODEL [DATE]` | |
| the registry: models, implementations, evaluations, declared inputs | `models` | |
| run a model under input enforcement | `run MODEL` | |
| schema validation; database snapshot | `validate`, `freeze` | |
| thirteen-fingerprint status with the settled loop behind it | PowerShell loop today | screen **new** |
| run comparison side by side; artefact browser | | **new** |

### 2.5 Rules, models, measurement
| Function | Exists | New |
|---|---|---|
| blind samples, precision, recall, judging | `mine-pdufa sample / precision / recall / judge`, `stakes sample / precision / crosscheck / verify-direction` | |
| measurement board: per parser — rule version, precision with interval, coverage, last measured; per model — benchmark of record, pass mark, adopted or not, holdout status | | **new** |
| constants audit as a live table (provenance class per constant, P20) | docs/20260903_v1_Constants_Audit.md | **new** view |
| pre-registration entry: write the pass mark before the run | prose in scope messages today | **new** |

### 2.6 Projects and studies — new entirely
Create, select, archive a project; define a study as a company subset; save
views per project (Entity Browser); tag every run with project and study;
file exports by project. The universe and library are shared and appear
unfiltered under Administration. Deletion constrained by results: a study or
parameter set that produced a report of record cannot be removed, only
superseded (P16 extended).

### 2.7 Schema, config, health
| Function | Exists | New |
|---|---|---|
| schema validation; one-time migrations | `validate`, `migrate` | |
| schema version and pending migrations as a screen | | **new** |
| config switches: pool on/off and rate, staleness windows, size thresholds (all declared in schema.py / config.py since the annotation pass) | files | screen **new** |
| health: disk, database size, library size, what is running now | | **new** |

### 2.8 Manual layer
Exists and complete: `manual add-entity / add-attribute / add-note / list /
validate / export / load`. Needs a screen, not a function.

## 3. Administration per use case

| Use case | Owns | Exists | New |
|---|---|---|---|
| **Entity Browser** | registry maintenance (merge duplicate identities, attach a CIK to a research group); holder identity refresh; saved-view management; view-definition versioning | — | all |
| **Deal matching** (buyer–target pairs; replaces standalone target screening) | benchmark of record and pass mark; adopted engine; frozen pair protocol; scorecard weights with provenance; holdout ledger (both accesses spent) | `pairs-exact`, `pairs-full-exact`, `pairs-aspect`, `backtest`, `robust`, `improve`, `models` | pre-registration entry; v2 sensitivity grid (LOE horizons) as a screen |
| **Stake tracking** | parser rule version and precision; direction verification and mismatch review; crosscheck disagreements; stub approvals; rebuild; header repair | `stakes run / rebuild / verify-direction / crosscheck / stubs / sample / precision / repair-headers` | the three queues (mismatches, disagreements, stubs) as Judge screens |
| **FDA calendar** | miner rule version, precision, recall vs the benchmark snapshot; review queue; forward-calendar sources | `mine-pdufa run / sample / precision / recall / explain / extras / judge`, `calendar-forward` | queue as a screen; recall history |
| **Event studies** | benchmark index (XBI), estimation window, event scope | `study`, `study-all`, `window` | window and benchmark as declared config with provenance (constants in code today) |
| **Expert hypotheses** | expert list; artifact attachment; resolve open calls; ledger | `hypothesis ledger / list / resolve`; `hypotheses.add` (Python only) | entry form; artifact upload; per-expert page |
| **Deal dossiers** | which deals are collected; analyser rule version and precision; verdict queue; seed protection | `dossier-analyse --collect / --consume`, `dossier-seed`, `judge` | collection status per deal; verdict queue as a screen |

## 4. Shape in the GUI
Administration is one workspace reached from the function selector, with
the project selector above it. Inside: the eight global panels of §2 as a
left-hand list, and each use case's admin as a section within that use
case's own workspace (so stake-tracking queues appear where stake tracking
is used, and also roll up under Administration → Measurement). Every
"queue" is a Judge screen (row + evidence + one keystroke); every "run" is
an Operate screen (start, live log tail, stop); every "status" is an Inspect
screen over the ledger.

## 5. Build order
1. Projects and studies (everything else is filtered by them).
2. The status board and measurement board (read-only over existing tables;
   fastest payoff; replaces the manual `Select-String` checks).
3. The Judge queues for stake tracking (three exist as text files today).
4. Background jobs with start / stop / resume.
5. Registry maintenance for the Entity Browser.
6. Config, schema and health screens.
7. Remaining per-use-case screens as their gates land.

## 6. Out of scope
Multi-user anything; remote access; any write path that bypasses the gated
functions; automation that changes rules or thresholds without a
pre-registered gate.
