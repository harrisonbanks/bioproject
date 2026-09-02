# docs/20260902_v1_Data_Feeder_Roadmap.md

# Data-feeder roadmap — the substrate gates (binding spec so this work is not lost)

Bioindustry Intelligence Platform · 2026-09-02 · written at the close of gate L4.
Purpose: aspect-match v1 was NOT ADOPTED (paired HR@5 0.108 vs 0.335) because its
richest inputs are empty, not because its rules failed. This document specifies the
two feeder gates that fill those inputs, and the re-test that follows. It is the
authoritative to-do; PROJECT_STATUS §open-queue points here.

## Why (one paragraph, plain)
The matcher scores buyer–target pairs from "aspects": who holds stakes in whom,
what buyers say they want, what past deals were about, existing relationships.
Today the stake table has 1 hand-typed row, stated priorities 0 rows, deal
aspects 4 hand-typed rows. Three derived aspects (disease overlap, prior
relationship, relative size) carried the whole v1 evaluation. Feed the tables,
then re-test. Do not re-run or fit weights before the tables are fed.

## Feeder gate F1 — equity stakes from SEC 13D/13G (mechanical)
1. Source: SEC EDGAR full-text search + daily index for forms SC 13D, SC 13D/A,
   SC 13G, SC 13G/A. Free, confirmed-working source class (same fetch/backoff
   stack as the miner; captures into the library per rule 4.20).
2. Extraction: filer (owner) CIK/name, subject-company CIK, percent of class,
   event date, amendment chain. Span-grounded like the analyser: every row
   carries capture id + verbatim span; parser built only after real captures.
3. Writes: `equity_stakes` (owner, subject, pct, as_of, doc evidence), dated so
   the matcher can read "stake held as of cutoff". Owner resolution through the
   registry; non-member owners enter as stubs under the 2.9' widening rule
   (`add --stub`).
4. Measurement: blind sample of parsed rows judged via the candidate_reviews
   queue (ids "F..."), precision with Wilson CI recorded per rule version —
   the exact 1.5b-eval pattern.
5. Exit: stakes rows > 0 at scale across the universe; precision recorded;
   idempotent re-runs; thirteen fingerprints MATCH; evidence per rule 4.21.

## Feeder gate F2 — stated priorities and deal aspects (analyser a3 rules)
1. Sources: earnings-call 8-K exhibits and investor letters already reachable by
   EFTS; the deal paper trails already captured for the ten-deal batch; new
   collects as needed.
2. New analyser rules (rule version L3-a3), per the agenda recorded in
   PROJECT_STATUS 1.10: doc-type guards (deal-PR/proxy vs 10-K boilerplate);
   stated-priority sentences ("we are looking for / our M&A priorities /
   capital-allocation priorities") -> `stated_priorities` rows dated by filing;
   deal aspects from the historical batch -> `deal_aspects` (vocabulary per
   Ontology §3.10); two-tier and reverse termination-fee fields; termination
   floor; price context guard; ticker-less deal_id naming fix.
3. Discipline unchanged: propose -> span-verify -> human judge -> verdict-gated
   consume; conflicts held; seed rows never overwritten; precision recorded per
   rule version.
4. Exit: stated_priorities > 0 across many buyers (coverage counts as run
   metrics); deal_aspects populated across the historical batch; precision
   recorded; fingerprints MATCH; evidence per rule 4.21.

## Then: aspect-match v2 (blocked on F1 + F2 — do not start early)
1. Fresh pre-registration BEFORE looking at results: same adoption mark
   (paired HR@5 must beat 0.335 by > 2x pooled repeat SD on shared events and
   samples); forward test reported against chance with false alarms beside.
2. Same exclusion: the four Tempus-sequence deals never serve as test evidence.
3. Equal weights still; any weight scheme is its own later gate with its own
   pre-registration on deals not used to set the weights.
4. Outcome either way is recorded and acted on: adopted into the product, or
   shelved with the second-round finding.

## Standing constraints that apply to all of the above
Rule 4.20 (real captures before parsers), rule 4.21 (evidence to one file),
P17 (reports render from run records), P19 (evidence spans), declared-input
enforcement at the model registry, no price-derived features into the M&A
screen, holdout ledger binding.
