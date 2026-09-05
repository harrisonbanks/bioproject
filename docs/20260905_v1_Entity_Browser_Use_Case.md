# docs/20260905_v1_Entity_Browser_Use_Case.md

# Use case: Entity Browser

Bioindustry Intelligence Platform · 2026-09-05 · use case defined and scoped;
build not started. Decisions taken in plain-English discussion with the
operator on 2026-09-05 and recorded here so nothing is lost.

## 1. Purpose
Browse every entity the system knows about, select any entity type and any
of its attributes, filter and rank on any combination, and drill from any
value to the document it came from. It is the front door to the rest of the
system: profiling, deal matching and hypothesis entry all begin with "show me
who has these qualities." It computes nothing new and writes nothing; it
assembles what the collectors and models have already produced.

## 2. Decisions of record
1. **One browser, entity type is a selector** — not a screen per type. Filter,
   sort, as-of date, drill-down, compare, saved views and export behave
   identically across types; only the attribute catalog changes.
2. **Holders are first-class entities.** Reasons: a holder is a potential
   acquirer and acquirers are half of every deal; a holder's behaviour over
   time (accumulate, hold, exit) is a signal with a track record; the stake
   table is a graph and both ends must be nodes (the direction defect of
   2026-09-04 came from treating one end as a label); holder-first
   questions ("who else holds what Tempus holds") cannot be asked otherwise;
   the cost is one SEC submissions fetch per CIK, cached.
3. **One record, many roles.** An entity is one row keyed by CIK (or a stable
   ID where none exists) with roles attached — company, holder, research
   group. Tempus is one record with two roles, never two records.
4. **All four types ship in the first version:** company, holder, research
   group, deal. Three are fully populated today; deal is populated for all
   447 events at the event level and deep for the analysed subset.
5. **Target screening is not a standalone use case.** A company is a target
   for someone; "likely target" means "has at least one strong plausible
   buyer" and is computed from buyer–target pairs. The scorecard survives as
   a target-side feature. Deal matching (from a target, or from a buyer)
   replaces use cases 1 and 2 of the earlier list.
6. **Local single-user.** No accounts, no roles, no authentication; the GUI
   runs on the operator's machine and talks to a local service that owns the
   database. Administration is a workspace, not a permission.
7. **The GUI is required.** A browser of this kind is not usable from a
   command line; the use case is delivered when the screen exists. The GUI
   is a client of the service layer and never touches the database or the
   library directly.

## 3. Entity types and what exists today (read from schema.py 2026-09-05)

| Type | Population | Attribute groups and source tables |
|---|---|---|
| **Company** | 1,379 universe members | identity — companies; pipeline: trials by phase, conditions, interventions, collaborators — trials; regulatory: approvals, CRLs, forward FDA dates — events, events_table; financials: revenue, cash + STI, burn, runway, market cap, as-of quarter — feature_panel; ownership: holders, stake history, strategic (13D) vs passive (13G) — equity_stakes; network: partners by type, deal filings, counterparties — relationships, deals; IP: patents, CPC classes, LOE exposure — patents, Orange Book; history: acquired / acquirer — ma_events; judgment: open hypotheses — analyst_hypotheses |
| **Holder** | every 13D/13G filer about a universe member | positions with percent and shares over time, form mix, first/last filing, exits, item-4 purpose text — equity_stakes; identity (name, SIC, state) — SEC submissions, to be fetched and cached |
| **Research group** | every trial sponsor / collaborator | classification (Academic / Government / Industry with role refinement), joint-trial and deal counts, partners, therapy areas, first/last activity, evidence — relationships, trials |
| **Deal** | 447 target-role events; 11 with dossiers, growing to ~129 under F2 | parties, announce/completion dates, status, five evidence signals, confidence, verified acquirer — ma_events; terms, timeline, stated rationale, aspects, comparables — deal_terms, deal_timeline, deal_rationale, deal_aspects, deal_comparables |

## 4. Behaviours (identical across types)
1. Type selector.
2. Attribute picker: choose columns; save as a named view per project.
3. Filter and sort on any attribute or combination; server-side paging.
4. As-of date: every attribute as it stood on the chosen date, using the
   models' cutoff discipline; default latest.
5. Drill-down: any value → the row it came from → the document in the
   library that produced the row.
6. Entity page: all roles, all attribute groups, timeline of events, stakes,
   trials, deals; who holds it; what it holds.
7. Compare: two to six entities side by side on chosen attributes.
8. Export: current view as CSV with as-of date and filters in the header.
9. Cross-type navigation: company → holder → position → company → deal; the
   type selector follows.

## 5. Build items, in dependency order
1. **Entity registry** — one row per entity, CIK-keyed where possible, roles
   attached. Today identities are scattered across companies, equity_stakes
   and relationships with no common key. Load-bearing; everything keys on it.
2. **Holder identity fetch** — name, SIC, state per distinct holder CIK from
   SEC submissions; cached in the library; the stub proposer already does this
   for 13D filers. Runs through the fetch pool once its probe passes.
3. **Attribute views** — one wide as-of view per type over existing tables,
   through `store` (P21). No new facts.
4. **Service endpoints** — filter, sort, page, entity, compare, export; local
   service, no auth.
5. **Saved views** — table: name, project, type, columns, filters, as-of.
   Profiling later lives here as named filters.
6. **The GUI** — type selector, attribute picker, grid, entity page, compare,
   drill-down. Delivered together with the service; the use case is not done
   without it.

## 6. Collection widening (raises what the browser can find; not required to ship)
The browser shows what has been collected, and collection is bounded by the
universe: stakes IN members, trials WITH members, deals INVOLVING members. A
fund's positions outside the universe are absent. Three levers, each a
scoped collection gate with a probe first and a recorded before/after count
of browsable rows:
1. **More companies in the universe** — `add`; every added company pulls its
   stakes, trials, deals, collaborators on the next pass.
2. **Collect by holder** — search SEC for everything a holder has filed, not
   only filings about members; same collector, different search key; makes a
   holder's full position list browsable.
3. **Collect research groups directly** — ClinicalTrials.gov by sponsor, not
   only by member company.
Direction of record: build all three, properly, after F1 closes.

## 7. Relationship to the other use cases
Deal matching (buyer–target pairs; from a target or from a buyer), stake
tracking, FDA calendar, event studies, expert hypotheses and deal dossiers
each open from an entity found in the browser. The browser is the first
workspace of the GUI; the others follow the same shell (function selector at
the top, project filter above it, Inspect / Operate / Judge panels inside).

## 8. Administration for this use case
Registry maintenance (merge duplicate identities, attach a CIK to a research
group), holder identity refresh, saved-view management, view-definition
versioning so an exported CSV can be reproduced.

## 9. Out of scope for the first version
Scoring or ranking by model output (that is deal matching); editing any
attribute (all writes stay in their gated paths); anything requiring a
network call at browse time (identity fetches are batch jobs).
