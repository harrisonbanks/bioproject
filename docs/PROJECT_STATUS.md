docs/PROJECT_STATUS.md

# Bioindustry Intelligence Platform — Project Status

Version 1.16. Supersedes v1.15. F1 CLOSED (2026-09-06/07), commits
9564753 … the F1-close commit, 244 tests:
- `verify-direction` finished: 40,617 match / 520 mismatch / 0 no-header of
  41,137 (run 20260906T031232). Mismatches classified: 434 genuine
  inversions (173 clean swaps + 261 successor-name collisions concentrated
  on eight predecessor entities), 86 benign (35 filer-of-record, 14
  issuer-CIK-only, 37 NAME rows the header cannot arbitrate).
- Root cause in orient(): the `if by_name:` branch trusted a name-index hit
  SEC never listed as a party (_norm strips legal suffixes, so "Allergan,
  Inc." resolves to "Allergan plc"). r8 refuses off-party name hits and
  off-party searched members; regression tests on the Allergan and
  self-filing patterns.
- `stakes fix-direction` (run 20260906T040209): 434 fixed from the cached
  SGML header, 2 issuer-agent self-filings refused (would have become
  self-stakes), 84 benign untouched, 1 duplicate dropped; table of record
  41,136 rows; residual mismatch export exactly 86. Commit 9564753.
- `stakes crosscheck` on the corrected table (run 20260906T040611): 25,886
  agree / 12,553 disagreement lines, classified into families: 6,972
  route-B silences (coverage gaps, not evidence), 5,390 date rows (stored =
  filing date where the document states an event date — the year-end 13G/A
  family confirmed 60/60 by blind judging), 223 large-delta dates, 58
  genuine percent conflicts (0.15% of both-routes-extracted rows).
- Human judging of the disputed sample via LLM-drafted verdicts (excerpt
  extraction + proposed verdict + human approval): 96 decided + 1 override,
  52 semantically ambiguous rows left queued (multi-person filings,
  warrants-vs-common, as-converted sums). `stakes precision` on the
  disputed sample: 7/96 = 0.073 [0.036, 0.143], run 20260906T200507 —
  the low number IS the finding (disagreements are overwhelmingly real
  stored-value errors, dominated by the r9 date family).
- entity_lineage (schema 0.14, manual layer, commits a1c6d54 + ba63cf3):
  hand-entered predecessor→successor CIK pairs with SEC formerNames
  sources. Five entered on evidence (Allergan, Endo, Perrigo, Alkermes,
  Valeant — the last reversed vs the naive pairing); three rejected as
  false pairs (Theravance/Innoviva spin-off, Biofrontera AG/Inc dual
  listing, the two unrelated Catalysts). stubs() sets mapped predecessors
  aside as historical names.
- `stakes stubs` on the corrected table (run 20260907T044737): 1,554
  distinct non-member 13D owners, 23 SIC-plausible, 17 approved and added
  as private stubs (IIDs 1381–1397; Baxter, Sun Pharma, Medtronic, LabCorp,
  Fresenius ×2, Aventis, Incyte, Lantheus and eight smaller); 6 rejected as
  individuals, deferred to the person-holder design question.
- Thirteen fingerprints MATCH after the full loop re-run (predict 20260907T051335,
  pairs-full-exact ...51444, pairs-exact ...51603, develop ...51611, tune
  ...51653) — also closing L4-P, the store extension, and the constants
  annotation pass, all previously code-done awaiting this proof.
- Gate M scoped and committed (4fc8498,
  docs/20260906_v1_GATEM_Maintained_Accuracy_Scope.md): ingest-time header
  verification, scheduled crosscheck, standing judge queue (disputed rows
  excluded from model inputs, never blocking), LLM judge-assist as proposer
  with recorded provenance. r9 (event-date repair, ~5,400 rows) named there
  as a deferred gate under rule 4.20.
- Known gaps recorded, not built: relation types beyond merged_into
  (spin-off, subsidiary); `add --stub` CLI token-loop defect (worked around
  via pipeline.add_company_stub); individual 13D holders as entities.

Version 1.15. Supersedes v1.14. F1 close in progress (2026-09-04/05),
commits 01323da … 281e880 plus the next K-block commit, 232 tests:
- Collector complete: 37,772 rows (r1), re-parse +4,918 (r6), then the
  DIRECTION DEFECT: the collector assumed the searched member was the
  subject; filings where the member was the filer were written backwards
  (11,302 rows under the first rebuild). Fixed in three rounds (r7 → r7c,
  orientation from the document's issuer and the reporting person's name,
  never from the search); rebuild of record 41,137 rows, subject / filer /
  unresolved 36,979 / 1,192 / 3,395. Full account in the parser development
  record v2 §7.
- Verification against SEC's SGML submission header (FILED BY / SUBJECT
  COMPANY) running: 98.0% match at 21,500 of 41,137, rate flat since 4,000.
  Percent and event date checked by a second extraction route
  (`stakes crosscheck`); the human judges disagreements only.
- Library defect found and repaired: the identifier ladder attached header
  captures to filing references (accession before URL); 6,074 moved, kind
  `sec_header` added (schema 0.13). Record v2 §9.
- Performance defects fixed, each found by timing lines, not by guessing:
  per-hit table scan in the capture lookup (indexed once per pass);
  whole-file reads for a 4 KB header (64 KB bound); per-header library upsert
  in the repair (batched). Timestamps on every progress line and startup
  stage; unit tests isolated from the live database (conftest).
- Stub list of 2026-09-04 is VOID (built from inverted rows); `stakes stubs`
  regenerates from the corrected table.
- Machine specs recorded (docs/…machine_specs, operator): Ryzen 9 5900X, 32 GB,
  2× NVMe. Every long run was SEC-rate-bound; hardware is not the constraint.
  Parallel fetching within SEC's limit is the one speed lever; scoped
  separately.
- Remaining to close F1: final header-verification counts and mismatch
  classification; crosscheck run; human judgment of disagreements; stub
  decisions; fingerprints (also proving L4-P, store extension, annotation
  pass); docs; commit.

v1.14. Supersedes v1.13. Session 2026-09-03 (evening), commits
3399234 … 058d729, all on jason/refactor, 217 tests:
- Constants annotation pass (3399234): every constant marked with its
  provenance class at its definition; size thresholds and staleness windows
  declared once in schema.py (PAIRS_ACQUIRER_SIDE_REVENUE 2e9,
  SCORE_ACQUIRER_SIDE_REVENUE 1e10, SCORE_ACQUIRER_SIDE_MARKETCAP 7.5e10,
  SCORE_TARGET_CAP_BAND, the two staleness windows) with values UNCHANGED —
  unifying them moves `predict` output and is the threshold reconciliation
  gate (docs/20260903_v1_Threshold_Reconciliation_Gate.md: measure the
  buyer/target size boundary from the ~129 resolvable deals with the
  selection rule pre-registered, not asserted).
- Six false docstring claims corrected against the executing line
  (3399234, fd00d64), all describing the pre-v0.81 architecture as live:
  score.py's cap cut is $75B not $100B; the 50/30/20 pairing fit and its
  $5B/$50B eligibility retired at v0.81 (predict uses MASS-exact x 100);
  pairs.py's rarity handling is the paper's Eq 10 over raw counts, not
  TF-IDF; pairs.py does not write pair_report.txt (the LEGACY `pairs`
  command does); study.py has no SPY benchmark. Audit v5 records the
  pattern and the rule: a docstring is not evidence until checked against
  the running line. score.py's unused `toks = _condition_tokens()` is the
  retired engine's remnant, left in place for the reconciliation gate.
- Store extension (15c5ebc): `store.update_rows` (row-level update by
  declared key) and `store.add_columns` (idempotent declared-column add),
  identifiers from schema.py, quoted. stakes.py now contains no raw SQL.
- Raw-SQL guard (058d729): tests/unit/test_no_raw_sql.py fails the suite on
  SQL outside store/results/schema/migrate; allowlist asserted exactly. The
  `references` rename was sized (29 sites, 8 modules, 2 fingerprint-
  protected, live migration) and cancelled under P9.
- Expert-hypothesis store built (1c9cb47): analyst_hypotheses table at
  schema 0.12, `hypotheses.add/attach_artifact/resolve/as_of_rows/ledger`,
  CLI `hypothesis ledger|list|resolve`. Decisions of record in
  docs/20260903_v1_Hypothesis_Store_Decisions.md. Not yet wired into any
  model (aspect-match v2's pre-registration owns that).
- F2 probe written, not run (058d729): priorities.py captures specimens of
  the three source types across two eras; runs after F1 closes.
- Blind-sample fix (5e92aa3): the judging list links to the captured
  document, not an accession directory under the subject CIK (EDGAR indexes
  13D/13G under the filer's CIK).
- Design Principles v6 drafted with P20 (sourced constants) and P21 (the
  store tier speaks SQL; nothing else does) — the operator's document,
  committed on approval.
- Proofs owed at F1 close (all need the database): thirteen fingerprints
  covering L4-P, the store extension, and the annotation pass together.

v1.13. Supersedes v1.12. Session 2026-09-03 (afternoon), all
committed on jason/refactor (fea4bfd … 8449877):
- F1 in progress: collector running (~45% of 1,379 members, ~23k rows at
  last check), interruption-safe; parser at rule F1-r6, coverage 0.881 →
  0.992 measured five times on the live library (development record
  docs/20260903_v1_Stakes_Parser_Development_Record.md); capture notes now
  carry the search CIK list with backfill for existing captures (eab75eb),
  routed through the store layer. The r6 re-parse of record is re-running
  `stakes run` after the collector finishes (documents cached, no
  re-download). Then: blind 60, precision, stub list, fingerprints, close.
- Constants audit (docs/20260903_v1_Constants_Audit.md, v2 at c7f0b43):
  every numeric parameter classified. UNSOURCED inside models of record:
  pairs.py `>= 8` token pool floor (defines every chance baseline), `> $2B`
  buyer cut, `<= 450`-day staleness; score.py's thirteen hand-set weights;
  study.py's fast(3)/slow(7) drift; improve.py positive floors. Three
  inconsistent buyer thresholds across pairs.py and score.py; two staleness
  windows. Remediation is a named gate, not done.
- MASS engine independently re-derived from the paper (arXiv 2404.07179,
  Eqs 6–10): matches pairs.py to 7e-15 on 110 pairs. Unpublished convention
  found: score 0 on Eq 8's undefined case (most central firm) — recorded as
  unsourced item 7.
- LEGACY commands guarded (26c5d07): fit, pairs, pairs-fit, pairs-protocol,
  pairs-substrate refuse to run; each would have overwritten a frozen
  baseline file. Six tests.
- F2 scope of record (docs/20260903_v1_GATEF2_SCOPE.md, 8449877): five
  decisions closed; build blocked on F1 close and explicit go.
- Hypothesis-store decisions recorded
  (docs/20260903_v1_Hypothesis_Store_Decisions.md).
- Standing rules adopted today: no numeric constant without a source line
  (1.11); no hand-written SQL — every table access through `store` (P18
  enforced; a reserved-word collision on `references` was the symptom);
  every delivered file carries a unique dated download name and every doc
  block ends with a verify line before the commit (two stale-copy commits
  were caught and repaired today); specimens go into tests verbatim.
- Gates parked for after F1, each its own scope: `store` extension
  (`update_rows`, `add_columns`, identifiers from schema.py); `references`
  table rename (migration; sequenced after the store gate); constants
  remediation (annotate, reconcile thresholds, sensitivity-report `>= 8`,
  replace drift SMA); hypothesis store; order of hypothesis store vs F2.
- Tests: 199.

v1.12. Supersedes v1.11. Gate L4-P DONE (0.8a): the two unsourced
constants inside `aspect-match` are ELIMINATED, not re-tuned.
TA_JACCARD_MIN is gone — therapeutic_area_overlap contributes its raw
Jaccard value as the aspect's strength, so there is no threshold to source
and the matcher keeps information the cut discarded; the aspect score is now
an equal-weight sum of strengths rather than a count of yes/no aspects (the
equal-weight prior is unchanged, per the standing decision). LOE_HORIZON_YEARS
is gone — the paired evaluation runs at every value in LOE_HORIZONS (3, 5, 7,
10) and reports all four side by side, with the pre-registered mark applied at
each and the horizon that beats it named; nothing is selected after the fact.
Re-tuning either value against the same historical deals was refused: that is
fitting on the test set, the leak class already retracted once (the 6.2x ROC
result). 191 tests; two of them assert that neither constant can return
(`TA_JACCARD_MIN` and `LOE_HORIZON_YEARS` must not exist, and LOE_HORIZONS
must hold more than one value, since a single value would be a choice). The
L4 results of record stand as run and are NOT re-run here; the re-run happens
under the aspect-match v2 pre-registration after the feeders.

Research finding recorded the same day, from the M&A prediction literature:
irrational threshold setting and sample selection bias are the named,
documented flaws that discredited early takeover-prediction models, and the
strongest current framing of the buyer-target problem is link prediction on a
temporal industry network (peer effects between firms), which produces
deal-level predictions without ad-hoc feature engineering. Published work in
that line excludes target edges as features to eliminate leakage, the same
discipline this project enforces. Direction of record for aspect-match v2:
after F1 and F2 supply dated edges (stakes, relationships, priorities, prior
deals), v2 is scoped as a temporal-graph link-prediction model evaluated
against the frozen protocol beside mass-exact, replacing hand-set aspect
rules with learned structure. It is a gate with its own pre-registration and
is not started early.

v1.11. Supersedes v1.10. CORRECTION (2026-09-03), recorded on the
gate it affects: two constants inside `aspect-match` — TA_JACCARD_MIN 0.05
(therapeutic-area overlap threshold) and LOE_HORIZON_YEARS 5 (patent-cliff
window) — are UNSOURCED. Neither was derived, measured, or taken from a
source; both were chosen by the assistant when aspects.py was written and
were not labelled arbitrary at the time. Research 2026-09-03 confirms no
canonical Jaccard threshold exists (thresholds are task-specific and must be
tested on representative data; published values range 0.2-0.5 for other
tasks) and no empirical LOE-horizon optimum was found (industry commentary
frames three-to-five-year windows, which is consistent with 5 but is
commentary, not measurement). The L4 results stand as run — paired HR@5
0.108, NOT ADOPTED, commit 3f3c7a0 — and are not re-run: re-tuning these
constants against the same historical deals would fit parameters on the test
set, the leak class retracted once already (the 6.2x ROC result). Both are
swept under the aspect-match v2 pre-registration, on deals not used to set
them, with swept values recorded as run parameters. The constants are marked
UNSOURCED in aspects.py at the point of definition. Related standing rule
adopted the same day: no numeric constant enters a scope, rule, or document
without a source line (paper, measurement on our own data, or operator
instruction); absent one, the parameter is stated as unset and the design
does not depend on it.

v1.10. Supersedes v1.09. Gate L4 DONE (0.8a): `aspect-match`, the
second acquirer-pairing implementation (module aspects.py; `pairs-aspect
[forward]`, 68th command), and the forward hit/false-alarm test (Ontology
v5 §5.5–§5.6). Rules-first methodology: eight analyst-stated presence
rules (equal weights, the naive prior) derived from the Tempus record and
the literature, never fitted to deals; the four Tempus-sequence deals
(Ambry, Deep 6, Paige, Personalis) excluded from both evaluations as the
rules' source (P19). Paired beside MASS-exact on 129 shared events and
shared samples: aspect-match HR@5 0.108 (±0.005) vs MASS-exact 0.335
(±0.014) — the pre-registered pass mark (HR@5 > 0.334 + 2× pooled sd
0.0107) fires NOT ADOPTED; mass-exact stands, the number ships as the
finding. Forward test (85 buyers, 1,389 buyer-years, 613 degenerate,
123 evaluable deals, median pool 660): hits@5 8 vs chance 0.88, hits@10
11 vs 1.76, hits@25 17 vs 4.39; 5,921 top-10 false alarms; the pool
definition (members with ≥8 trial tokens at the year-end, minus
acquirer-side and the buyer; chance = k/pool) rides verbatim in the run
note. Per-aspect coverage recorded as ledger run metrics (binding
amendment): three derived aspects (TA overlap, prior relationship,
financing capacity) carried both evaluations; patent_cliff_pressure
(Orange Book zip absent) and every stated aspect (attribute tables empty
before the cutoffs) evaluable 0 — the sparsity is a queryable fact of
each run, and the paper's interpretation is that the aspect matcher
cannot beat the trial-text engine until the stated-aspect substrate
exists (a3 analyser rules and 13D/13G ingestion, future gates).
Untouched-surface proof: empty diff over pairs/labels/forward/efts/
analyser at 3124814; thirteen fingerprints MATCH. Incident R1, recorded:
the closing block re-ran `robust` and `improve` outside the five-command
regeneration set of record, overwriting two at-rest reports; both were
restored byte-exact by rendering their original 2026-08-31 ledger records
(P17 render-from-record; disposable script, deleted after use, evidence
in the gate commit). Regression facts restated as settled: regeneration
set = predict, pairs-full-exact, pairs-exact, develop, develop tune; the
six legacy files hash from data\gold_frozen_20260830\, all other baseline
names from data\exports\; fixed-list routing, no fallback. Deferred,
named: `report pairs-aspect` RENDERERS entry (lands with the next
results.py gate); aspect weights beyond equal (own pre-registration);
a3 aspect-extraction rules. Order of record L1 → 1.4 → L2 → 2.10 → 1.5 →
2.9′ → L3 → L4 complete.
v1.09. Supersedes v1.08. Gate L3 DONE (0.8a): the deal analyser.
`dossier-analyse DEAL_ID [--collect] [--consume]` (67th command; module
analyser.py, rule version L3-a2). Collect: per-party EFTS full-text
queries (merger vocabulary, forms 8-K/425/DEFM14A/PREM14A/S-4/6-K/10-Q/
10-K) over announce−30..+150d, every hit captured. Propose: span-grounded
rules over party-scoped normalized captures — price per share (par-value
guard), exchange-ratio cap, termination fee, outside date and its
extended variant, announce date, prior stake, enterprise value,
consideration form, agreement date, expected close, rationale sentences
(statement-level dedup) — each proposal carrying capture id + verbatim
span, machine-verified by dossier.span_pattern. Review: proposals queue
into candidate_reviews (ids "A…"); conflicting values for one field are
held and consumed only when a verdict makes one value uniquely correct;
judged-wrong and unsure never write; seed rows never overwritten;
consume idempotent. Yardstick (TEM-PSNL): raw precision 20/32 = 0.625
[0.453, 0.771]; 8 verdict-gated rows consumed, including two facts the
hand-built seed lacked (termination fee $76,806,179; outside date
extended 2028-04-20); dossier now 12 terms / 2 timeline / 5 rationale.
Batch probe (ten never-seen historical deals, review-only): ~100
documents, 0 fetch failures, 100% span verification; five-deal
spot-check (74 proposals) 26/31/17 correct/wrong/unsure = 0.456 raw —
accuracy concentrates in deal 8-Ks and proxies, noise in 10-K risk
boilerplate. a3 agenda recorded, not built: doc-type guards for
rationale/price rules, two-tier and reverse termination-fee fields,
termination-floor rule, ticker-less deal_id naming. Known cosmetic
issue: harvest rows without FilerTicker produce deal_ids like
"-20260501". Next gate: L4.
v1.08. Supersedes v1.07. Gate 2.9′ DONE (0.8a): universe widening.
The rule of record (universe.py docstring, cited in the paper): beyond the
SIC 2834/2836 core, a diagnostics, tools or data company is admitted as a
member when it is a plausible party to biopharma M&A or FDA-adjacent
events; admission by instance — `add TICKER` (listed, any SIC) or
`add --stub NAME [--cik C]` (private; Exchange="private" marks the stub) —
dated by the registry's Created column. First instances: Tempus AI
(TEM, IID 1379) and Personalis (PSNL, IID 1380). The seed dossier's
ma_events index row is attached: FilerIID 1380, CounterpartyIID 1379,
AnnounceDate 2026-07-20, Verified yes, deal_id TEM-PSNL-20260720 —
closing the L2 deferral. Manual-layer attributes ma_events.<Column>
(entity_key FilerTicker|AnnounceDate) are applied at every labels rebuild;
the write carries the optional deal_id column (a dropped-column and a
list/tuple defect were found by round-trip evidence and fixed; the test
now reads the written table through the CLI's own import). Measured
effect of the widening on the frozen protocol: ranked universe 1,357 →
1,359; candidate pool 862 → 863; median true-target rank 80, hit@10
0.27, hit@25 0.39 all unchanged. Targeted-mine finding: 2 companies,
2 queries, 0 hits — diagnostics filings contain no PDUFA/readout
language; the widened class contributes M&A structure, not FDA
catalysts. The seven live regression baselines are re-hashed explicitly
in the gate commit (the six legacy frozen files are untouched).
Next gate: L3.
v1.07. Supersedes v1.06. Gate 1.5c DONE (0.8a): realized events,
delays and outcome states written from the `mined_candidates` ledger, no
re-fetching. r10 rules (RULE_VERSION 1.5c-r10): readout contract-clause
guard, cash-runway guard with an expectation-verb exception, `1H:2026`
colon halves. `mine-pdufa write-realized`: historical readout statements
become `clinical_readout`/`topline_readout_disclosed` rows dated by the
disclosing filing (`disclosure_datetime` = filing date; `event_date` only
for exact days), `outcome_state` mapped conservatively (met_primary 24,
not_met 41, unspecified 1,583); past exact-day PDUFA targets become
`regulatory_decision` rows (actual outcomes join from Drugs@FDA at their
own gate, never guessed); 2,053 realized rows. `write-delays`: negated
guidance becomes `delay_timing`/`review_delay` rows (9), and live forward
guidance for a withdrawn range is superseded with `withdrawn_by=` recorded
(1). Numbers of record (r10, fresh blind sample, seed 505): precision
56/60 = 0.933 [0.841, 0.974]; recall 0.846 raw / 0.915 members — stable
across r9 and r10, which satisfies the pre-stated stopping rule. Ledger
66,074 rows across r6–r10; 8 stale rows retired at r10; events_table
22,750. Known r11 candidates (documented, not built): "half of calendar
year YYYY", report-verb preference beyond the 3-word window, undated
readouts adjacent to trial-start dates. Reverse benchmark comparison now
counts forward rows only (realized rows excluded). Next gate: 2.9′.
v1.06. Supersedes v1.05. Gate 1.5b-eval DONE (0.8a): measured
improvement loop over the miner. New: `candidate_reviews` (SCHEMA_VERSION
0.10, 49 declared) storing blind human verdicts per candidate and rule
version; `mine-pdufa run --cached` (re-examines all 2,404 captured filing
documents with the current rules, no network, ~27 min); `sample`/`judge`/
`precision` (Wilson 95% interval from stored verdicts, per rule version);
`explain TICKER DATE [--live]` (classifies each benchmark miss:
NOT_A_MEMBER / NO_CIK / NO_DOCUMENTS / DATE_NOT_IN_DOCS /
SEEN_NOT_EXTRACTED, with a live EFTS probe separating VOCABULARY_MISS from
NOT_IN_EDGAR_FULLTEXT); `extras` (mined dates absent from the benchmark);
`_retire_stale` (rows a retired rule produced are superseded on re-run,
provenance +retired_by). Rules iterated r7→r8→r9, each failure window a
unit test. Numbers of record (r9): precision 56/60 = 0.933 [0.841, 0.974];
recall 55/65 = 0.846 raw, 54/59 = 0.915 members-only; all ten misses
classified — five non-members, five press-release-only (dates in no EDGAR
filing; the benchmark's notes cite Business Wire) — zero extraction
failures; five true finds the benchmark lacks (Gilead, BridgeBio,
Nuvation, IID 1210, Inhibrx). Coverage ceiling documented: an EDGAR-only
miner cannot see unfiled press releases — the case for a later IR-polling
gate. r10 rules named for 1.5c: readout clause guard, through-the-data
runway, 1H:YYYY colon form. Windows console output made encoding-safe.
Next gate: 1.5c.
v1.05. Supersedes v1.04. Gate 1.5b DONE (0.8a): SEC EDGAR full-text
miner (`mine-pdufa`, 66th command) — per-company EFTS queries (ciks filter,
forms 8-K/10-Q/10-K/6-K/20-F), 2,653 filing documents captured into the
library, rule-based extraction of PDUFA target dates and readout guidance
with date ranges, precision, modifier and raw window; every examined window
kept in the `mined_candidates` ledger (14,002 rows at rule version r6) with
character offsets, assertion status (affirmed/negated/historical/
hypothetical), outcome words, 8-K item codes and decision/reason; 701
distinct forward events (tier B). Numbers of record: precision 8/10 on the
operator-judged sample; recall 55/65 = 0.846 against an operator-captured
snapshot of FDA Tracker's public PDUFA calendar (benchmark only — their
terms forbid automated collection; aggregates published, entries never
redistributed). Design basis from research 2026-09-01: TimeML/TIMEX3
normalization, NegEx/ConText assertion status, Dolphin et al. 2026 grounded
8-K event extraction, event-study outcome categories. r7 (H1/H2 form,
"based on" as historical) ships with the gate and is re-measured at 1.5c.
Full-run runtime of record 75 min. Next gate: 1.5c.
v1.04. Supersedes v1.03. Gate 1.5a DONE (0.8a): the forward FDA calendar
is live. `events_table` gains optional forward columns (SCHEMA_VERSION 0.8:
scheduled_date_end, date_precision day/month/quarter/half/year, date_raw,
status blank/superseded, confidence_tier A–D) and `calendar-forward` (65th
command) writes forward rows: 16,112 future CT.gov primary-completion rows
(class clinical_readout, subtype estimated_primary_completion, tier C — never
"results expected") and, from the FDA Advisory Committee Calendar's data
endpoint (https://www.fda.gov/datatables-json/advisory-committee-calendar-json;
the calendar page is a client-side shell), two rows per upcoming meeting —
meeting (tier A) and briefing-document release two business days before (tier
B, derived) — 194 records, 2 upcoming, 4 rows, endpoint response captured as a
dated library snapshot. Deterministic ids; re-runs refresh last_verified; a
moved date inserts a new row and marks the old one superseded. events-migrate
preserves forward rows. L1 manifest self-listing defect fixed (verify clean on
re-run). events_table 20,398; captures 742; validate 38/0/8/1; pytest 122;
thirteen fingerprints MATCH. Testing standard adopted: external-source parsers
are built and tested against a real captured response. Regression loop
runtime of record: ~3–4 minutes (timestamps), not the "~2 h" previously
quoted. Next gate: 1.5b.
v1.03. Supersedes v1.02. Gate 2.10 DONE (0.8a) under the storage
ruling of 2026-08-31: the database is the sole store for every operational
fact; git carries no row content (the dossier SEED in dossier.py is marked
LEGACY); machines reconcile only by the hashed snapshot; `manual export` /
`manual load` (data\manual\hand_data.json, git-ignored, rides in snapshots)
is the rebuild path for all eleven hand tables (manual trio + eight dossier
tables; round trip 17 rows / 6 tables proven, run-recorded). Manual layer
live at SCHEMA_VERSION 0.7: add-entity / add-attribute / add-note / list /
validate / export / load (64th command); attribute targets validated against
the declared schema (undeclared table.column refused); precedence is visible
(merged_rows returns applied overrides) with no consumer until L3 by design,
so fingerprints held by construction. First manual attribute of record:
ma_events.deal_id = TEM-PSNL-20260720 (pre-registered index-row link for
2.9′). Next gate: 1.5.
v1.02. Supersedes v1.01. Gate L2 DONE (0.8a): dossier schema live at
SCHEMA_VERSION 0.6 — deal_terms/deal_timeline/deal_rationale/deal_aspects/
deal_comparables plus equity_stakes/stated_priorities/assets (47 declared),
ASPECTS vocabulary (15) as the deal_aspects enum, v4 relationship type names
declared, ma_events gains optional deal_id. The Tempus–Personalis seed
(deal_id TEM-PSNL-20260720) loaded 16/16 span-verified rows across 5 tables
(run 20260831T203033-dossier): dossier-seed resolves each row's SEC accession
to its active library capture, stamps the capture hash as doc_id at load
time, and verifies the row's verbatim span occurs in the capture (whitespace-
tolerant at symbol boundaries for inline-XBRL); rows without a stating
captured source stay out (equity_value_usd pending the Tempus PR capture via
`library add <file> --for Rf573315b3de`; three Merck rows pending the
merger-agreement exhibit or §9 news URLs). Membership check
MEMBERSHIP_MATCHES 0: 2.9′ precedes L3 (order of record
L1 → 1.4 → L2 → 2.10 → 1.5 → 2.9′ → L3 → L4); the deal's ma_events index row
attaches at 2.9′. Next gate: 2.10 (manual layer).
v1.01. Supersedes v1.00. Decision 2026-08-31 (0.7, 0.9): L2 loads its
seed dossier (Tempus–Personalis) through a committed hand-curated seed on the
verified-overlay pattern — every field carrying a `doc_id` resolving to an
active library capture plus its span (P19) — and gate 2.10 (manual layer) is
pulled forward to immediately after L2, so the order of record is
L1 → 1.4 → L2 → 2.10 → 1.5 → L3 → L4 (1.6, 1.7, 2.9′ as they fall due);
first corrections arrive at L3, so the correction machinery exists exactly
when needed. Implementation Plan v14.
v1.00. Supersedes v0.99. Gate 1.4 DONE (event table + forward FDA
calendar view live; 0.8a): `events_table` per Ontology v5 §3.6 with the
approved date semantics (`event_date` = realized action date; `scheduled_date`
= goal/expected date only) and the complete event-class vocabulary incl. the
seven v4 classes (only `regulatory_decision` populated at 1.4); `events-migrate`
(62nd command) copied all 4,282 `events` rows 1:1; `calendar IID` is now a view
over trials + events_table with an empty forward section until gates 1.5/1.6.
v0.99: Gate L1 DONE (research library live; 0.8a).
v0.98: File-room design approved (Ontology v5 §3.9;
plan v11 row L1); AI-over-store noted for future development.
v0.97: P19 Evidence added (Design Principles v5). Sequencing decided (0.7, 0.9): L1 → 1.4 → L2 → 1.5 → L3 → L4, with 1.6, 1.7 and 2.9′ placed as they fall due; next gate L1.
v0.96: Diagrams: target state v2 (after Ontology v4) and research-process diagram added.
v0.95: Design decision of 2026-08-31: deal dossiers on
top of a research library (Ontology v4; Implementation Plan v9 rows L1–L4, 2.9′;
0.7, 0.9). v0.94 recorded the data-snapshot policy (0.5). PART 0 otherwise as
regenerated at v0.93 from the tree at 93c2194 and the run ledger; current-state
diagram v2. PARTS 1–7 and the changelog
are unchanged from v0.81 except where noted. Design
decisions of 2026-08-30/31 are in docs/20260831_v5_Design_Principles.md
(binding) and
docs/20260831_v5_Ontology_and_Matching_Design.md.


# PART 0 — COLD START (read this first in any new session)

Regenerated in full 2026-08-31 (DOC gate after Phase 0) from the live tree at
commit 93c2194 and the run ledger. PARTS 1–7 below are the historical record
(v0.3–v0.81) and are not rewritten; where they conflict with PART 0, PART 0
is current.

**Continuation guarantee scope:** with this file, the design principles
(P1–P18), the Implementation Plan, the session handoff, and the repository,
a new session has everything needed to continue: codebase map, every
command, data layout, final numbers with provenance, protocol ledger,
standing rules, and the open queue.

## 0.1 Environment & locations
- Repository: https://github.com/harrisonbanks/bioproject (public as of 2026-08-31 — to be set private; key rotation pending). Branch `jason/refactor` holds all work since 2026-08-29 (commits 76a3ba3 … 93c2194); `main` is at the pre-refactor commit b52de01.
- Operator machines: Harrison `C:\Users\bocchirock\Documents\dev\bioindustry\` (pre-refactor layout until merge); Jason `C:\Users\JB\Documents\dev\bioindustry\` (current layout; data regenerated 2026-08-29: 1,379 universe members; migrated to DuckDB 2026-08-30; frozen 2026-08-31 as the snapshot of record, 0.5). Windows, Python 3.13, venv at `<root>\.venv`, venv + pip (no uv, P9).
- Repository layout: `src/biointel/` package (modules below) · `scripts/` diagnostics and `scripts/refactor/` gate tooling · `docs/` · `tests/unit/` (65 tests) · `pyproject.toml` (dependencies: numpy, scikit-learn, scipy, requests, openpyxl, duckdb>=1.3,<2; dev: ruff, mypy, pytest) · `requirements.lock` (UTF-8) · `.env` (git-ignored; template `.env.example`).
- Data layout (P16; all git-ignored under `data\`): `bronze\` raw API responses and documents with manifests, never edited · `biointel.duckdb` every silver, gold and ledger table (49 declared in `schema.py` at SCHEMA_VERSION 0.10: 46 live incl. 4 ledger, the L1 library tables, 1.4 events_table, the L2 dossier/attribute tables and the 2.10 manual tables, 1 planned) · `exports\` reports and CSV exports, disposable, regenerated per check · `snapshots\<date>\` `freeze` copies of the database file · `silver_frozen_20260830\`, `gold_frozen_20260830\` pre-migration CSVs, read only by LEGACY code, never written.
- Install: `python -m venv .venv` → `.venv\Scripts\python.exe -m pip install -e ".[dev]"`; optional `".[ner]"` for spacy.
- Credentials: `BIOINTEL_USER_AGENT`, `BIOINTEL_ALPHA_VANTAGE_KEY` in `.env`; read via `config.require()` at the HTTP call sites; nothing in code.
- Run form: `& "<root>\.venv\Scripts\python.exe" -m biointel <command>`.

## 0.2 Deployment workflow (Implementation Plan §1)
Per gate: scope message → go → dry-run on a container copy → single files delivered with the deploy path on line 1 (overwrites under `NAME_vNNN` names; no zips) → operator downloads to `C:\Users\JB\Downloads\` → one block of absolute-path commands, each annotated with its expected result, `git --no-pager` throughout → operator pastes → exit proof: `pytest`, `ruff`, the thirteen fingerprints in `docs/regression_baseline.txt` (seven live exports regenerated into `data\exports\`, six legacy files unchanged), `validate` → docs (PROJECT_STATUS, Implementation Plan, handoff) → one commit and push, after proof only. Data files are never shipped; each machine's data is authoritative there. Conventions: docs/20260829_v2_MACHINE_RUNBOOK.md; process of record: docs/20260823_OPERATINGMANUAL_NEW.md.

## 0.3 Codebase map (generated from the tree at 93c2194, 2026-08-31)
| Module (src/biointel/) | Lines | Role |
|---|---|---|
| __init__.py | 51 | re-exports of pipeline entry points |
| __main__.py | 8 | entry point: python -m biointel |
| config.py | 89 | paths (P16 layout), all HTTP endpoints, windows; .env loader; require() |
| schema.py | 1241 | schema as code: entity types, attribute groups, relationship types (incl. v4 typed-edge names), event classes (incl. the v4 classes since 1.4), ASPECTS vocabulary, 47-table map with types/keys/enums; validate (CSV and database) |
| store.py | 516 | bronze fetch/cache and manifests; DuckDB store layer (single point of table access: connect, read_table, write_table, append_rows, export_csv, write_export); input enforcement (enforce, InputViolation, trace) |
| migrate.py | 109 | one-time CSV → DuckDB migration (refuses if the database exists; freezes the CSV folders) |
| results.py | 423 | run ledger (P17): start/finish, render-from-record dispatch, run_type, ledger views, data/exports/ledger.csv |
| legacy_ledger.py | 428 | transcribed legacy report rows with quoted source lines; `ledger-seed` |
| models/base.py | 50 | Entry contract: model, name, run_type, declared inputs, outputs, func |
| models/registry.py | 340 | three models by question, six implementations, seven evaluations (L4: aspect-match, aspect-paired), declared tables and columns; COMMAND_TO_ENTRY |
| models/harness.py | 47 | run an entry: enforcement on, run_type set, call, enforcement off |
| models/adapters.py | 107 | adapters from entries to the existing functions |
| pipeline.py | 1204 | company registry, per-layer getters, ingest, text_ingest (10-K Item 1); events_table migration (preserves forward rows since 1.5a) + calendar view (1.4); table access via store |
| universe.py | 261 | rule-defined membership (EDGAR browse, 2001+ window, Form-25 delisting) |
| labels.py | 1164 | merger trails, harvest, verify_fill, qa, qa_corroborate, qa_wiki, merged events, label panel |
| features.py | 399 | as-of firm-quarter feature panel + label join (model-agnostic, P1) |
| network.py | 361 | partner classification, relationships |
| match.py | 114 | canon() entity resolution |
| score.py | 312 | target-screen/scorecard: hand scorecard predict (drives `predict` today), backtest; records runs |
| improve.py | 848 | target-screen/fitted: engineered features, develop, tune, textsweep (record + render); `holdout` LEGACY (spent) |
| fit.py | 676 | target-screen evaluations robust, improve (record + render); gen-1 `fit` LEGACY |
| pairs.py | 455 | acquirer-pairing/mass-exact: pairs-exact, pairs-full-exact (record + render), build_pair_feature |
| aspects.py | 642 | gate L4: acquirer-pairing/aspect-match — analyst-stated presence rules over aspects, paired protocol beside mass-exact, forward hit/false-alarm test; per-aspect coverage as run metrics |
| baselines.py | 654 | LEGACY: rejected pairing engines (cosine, supervised, protocol, substrates); paper baselines; not maintained |
| study.py | 263 | fda-event-study/daily-bars: CAR vs XBI by outcome class |
| interfaces/cli.py | 858 | dispatch for 68 commands (L4); configures logging |
| efts.py | 1563 | gate 1.5b: EFTS adapter, document capture with backoff, examine()/extract() with ledger records, forward-row writer, precision sample/record, ICS recall benchmark |
| forward.py | 477 | gate 1.5a: forward calendar writers — date-range parser, trials transform, FDA AdCom JSON-endpoint writer, supersession upsert |
| manual.py | 319 | gate 2.10: manual layer — DB-only store, schema-validated overrides, visible precedence (merged_rows), export/load rebuild path for all hand tables |
| dossier.py | 427 | gate L2: Tempus–Personalis seed rows + span-verified loader (accession→capture resolution, doc_id stamped at load, propose→report→load) |
| sources/*.py (11) | 2,535 | one adapter per public source: sec, financials (XBRL), deals (8-K), counterparty (NER, optional spacy), trials (CT.gov v2), fda (Drugs@FDA, CRL), prices (Yahoo), orangebook, chembl, patents (BigQuery export), alphavantage |

Removed in the refactor (26133aa): fossil tree, Excel workbook, duplicate scripts, `crsp_import`, `ner_status`, `_pair_by_date`, dead USPTO route (−2,750 lines).

## 0.4 CLI commands (68, all live; `python -m biointel` prints the list)
- Universe/ingest: universe-probe, universe, ingest N, text-ingest N, add, backfill.
- Layers: fin(-all), trials(-all), events(-all), deals(-all), cparty(-all), partners, relationships, snapshot.
- Labels/QA: harvest, verify-fill, qa, qa-corroborate, qa-wiki, labels.
- Models (all routed through the registry harness under input enforcement): features, predict [QUARTER], robust, improve, develop [tune|textsweep], pairs-exact, pairs-full-exact, pairs-aspect [forward] (L4), study-all, backtest; `models` (the registry), `run MODEL [--impl N] [--eval N] [--as-of D]`.
- Reporting and ledger: report MODEL [DATE], report ledger, report runs MODEL, ledger-seed (once), validate, freeze, migrate (once), events-migrate (once; gate 1.4), dossier-seed [--report] (L2; idempotent; LEGACY as a store since 2.10), manual SUB (2.10: add-entity, add-attribute, add-note, list, validate, export, load), calendar-forward [trials|adcom|all] [--file RESPONSE.json] (1.5a; idempotent), mine-pdufa run|run --cached|write-realized|sample|judge|precision|recall|explain|extras (1.5b/1.5c; run idempotent, flushes every 50 companies), dossier-analyse DEAL_ID [--collect] [--consume] (L3).
- Data adapters: patents-sql, patents-import, orangebook-probe, chembl-probe, chembl-ingest.
- Lookups: list, coverage, calendar IID, window, study, tags, sponsors, deals-of, partners-of.
- LEGACY (P7; kept, not maintained, not re-run): fit, holdout (both accesses spent), pairs, pairs-fit, pairs-protocol, pairs-substrate.

## 0.5 Numbers of record, with provenance (generated from the run ledger; P6)
**Snapshot of record (decision 2026-08-31, option A):** Jason's 2026-08-29 data is the snapshot of record for every number from Phase 1 onward. It was frozen as it stood on 2026-08-31 (no data-changing command run before the freeze): `data\snapshots\20260831\biointel.duckdb`, 95,170,560 bytes, SHA-256 `B93A833BE46667AD402C71776C41D5E34EF1AC2126A73138D24C74D3928C0E65`, byte-identical to the live `data\biointel.duckdb` at freeze time; `manifest.json` lists 12,053 bronze fetches and contains no credential (0 occurrences of `apikey`, checked before any copy). Transfer to Harrison: the whole `data\snapshots\20260831\` folder on a USB drive after the merge, never through git; identity on his machine is proved by the same SHA-256 and by an equal `data_snapshot_hash` in `report runs` after his first run. Harrison's 2026-08-25/26 results (holdout 2.2×, substrate nulls, protocol 0.222) remain `historical-file` ledger rows labelled with the earlier snapshot, and the paper states that provenance in one sentence. On this snapshot the relationship features (`RelDeal`, `Deals24m`, `LicensesEver`, `CollabsEver`, the S1 merger-row label signal) are trial-collaboration-only because `cparty-all` was never run (spacy absent) and 10-K text is absent; any enrichment enters only at a named gate that records a new baseline with a ledger note (Implementation Plan §1 step 5). Each ledger row carries its `data_snapshot_hash`; `report runs MODEL` shows both snapshots side by side.

| Model | Metric | Harrison snapshot (2026-08-25/26, historical) | Jason snapshot (2026-08-29, of record) | Status |
|---|---|---|---|---|
| target-screen / fitted (gen-2) | holdout 2023+ AUC-PR / lift / ROC | 0.079 / 2.2× / 0.720 (holdout_report, historical-file) | not run (P10: both accesses spent) | final |
| target-screen / fitted | development best (tune, hist-gbm fund+eng) | 0.0674 / 2.13× (v0.68 record) | 0.0561 / 1.87× (ledger run tune) | snapshot-dependent |
| target-screen / gen-1 (LEGACY) | test AUC-PR / lift / ROC | 0.204 / 6.7× / 0.915 (price-inclusive; retracted as headline, leak) | — | closed |
| acquirer-pairing / mass-exact | paired HR@5 vs MASS-inspired | 0.310 vs 0.222 (corrected engine, midpoint tie-ranking) | 0.334 vs 0.224 (129 events; ledger run pairs-exact) | adopted |
| acquirer-pairing / mass-exact | full-universe re-rank | — | 124 events; median rank 80 / pool 862; hit@10 0.27; hit@25 0.39 (regression fingerprint) | current |
| acquirer-pairing / aspect-match (L4) | paired HR@5 vs mass-exact; forward hits@10 vs chance | — | 0.108 vs 0.335 (129 events, shared samples; pass mark NOT ADOPTED, mass-exact stands); forward 11 hits vs 1.76 chance, 5,921 false alarms (runs pairs-aspect / pairs-aspect-forward 2026-09-02) | recorded finding |
| acquirer-pairing / legacy engines | protocol HR@5 | cosine 0.216, MASS-inspired 0.222, latent-SVD 0.143, hybrid 0.186 | — | closed |
| substrates (LEGACY) | paired HR@5 | patents 0.055 vs trials 0.237 (42 events); targets 0.120 vs trials 0.206 (67 events); both REJECTED | — | closed; paper finding: diseases > mechanisms > patents |
| fda-event-study / daily-bars | events; mean CAR[-1,+1] | 1,350 events; approvals +0.31; CRLs −7.1 / −21.1 (N=53/36) | 1,165 events in event_study (no re-run yet under the ledger) | current |
| leak finding | fake lift from price missingness | 6.2× / ROC 0.985 diagnosed and retracted | robust: baseline 6.6× with price, 1.4× fundamentals-only (ledger) | paper methods finding |

The v0.81 text "MASS-exact adoption SUSPENDED" in the historical record is superseded: the corrected engine (midpoint tie-ranking, degeneracy test) is the shipped engine and its paired result is recorded above; Harrison's confirmation of the 0.310 figure on his snapshot remains item 5 of the open queue.

## 0.6 Standing behavioral rules
docs/20260831_v5_Design_Principles.md P1–P19 (binding) and the operating manual. In brief: requirements general-case first, then instances, then derived requirements; declarations and rules read from the repository, not memory; tables model-agnostic, separation enforced at each model's declared inputs by the harness; verify through the real code path and the operator's paste only; one annotated block per turn, absolute paths, `git --no-pager`; probe-first for new endpoints; numbers as-is, holdout ledger binding; legacy code kept, marked, never maintained or re-run; every gate ends in a commit after proof; PROJECT_STATUS updated every progress turn.

## 0.7 Historical decisions (kept for the record; superseded where noted)
- v0.69: final improvement cycle (patent substrate + Orange Book LOE urgency, probe-gated) then assembly → freeze → draft; pre-registered adoption rule for substrates (HR@5 must beat 0.222 outside ±0.010) — executed; both substrates rejected (0.5).
- v0.67 ranked options (exact Sapling formula, EFTS strategic-review scanner, 24-month screen, LightGCN, close measurement) — the exact formula shipped as MASS-exact; EFTS becomes Phase 1 gate 1.5; the rest superseded by the Implementation Plan.
- 2026-08-30/31 decisions: P7 legacy rule; P16 two stores; P17 ledger in MLflow structure; P18 one store layer and SQL convergence; models named by question, M1/M2 labels retired (Implementation Plan v8 §7).
- 2026-08-31 (file room, approved): the research library is references / captures / reference_links in DuckDB over a content-addressed store (`data\bronze\library\<aa>\<sha256>`); collectors are a module family (manual, folder, pipeline, zotero, later video_dl and search), none required; Zotero optional, offline, no account, sync off, as human capture tool; duplicates: hash PK, identifier ladder, `dedupe` with human-confirmed merge, retire-never-delete; reconciliation by USB + manifest + merge + verify; navigation: CLI, generated `library site`, folder views, SQL for agents; AI integration noted for future development (MCP over the store after L3; media transcription; per-person Zotero AI outside the system). Ontology v5 §3.9; plan v11 L1.
- 2026-08-31 (principle): P19 Evidence — every dossier fact, stated priority, equity stake, asset attribute and v4 event row carries a `doc_id` and span; library documents never edited; dossiers regenerated, corrected via the manual layer; patterns tested only on later deals (Design Principles v5).
- 2026-08-31 (sequencing, amended): order of record L1 → 1.4 → L2 → 2.10 → 1.5 → L3 → L4, with 1.6, 1.7 and 2.9′ placed as they fall due — 2.10 pulled forward on the day's second decision (L2 seeds via the verified-overlay pattern; the manual layer lands before L3's review queue produces corrections). Original reasoning stands: L1 first (no fingerprint, both tracks need it); 1.4 before L2 (event table); 1.5 before L3 (EDGAR adapter built once). Ontology v4 §8 Q8; Implementation Plan v10 §3, amended v14 §3.
- 2026-08-31 (design): the unit of record for an acquisition becomes a deal dossier — dated relationship timeline, terms, stated rationale verbatim, aspects with evidence, comparables — every field citing a document in a permanent research library (`data\bronze\library\<sha256>`, indexed by `documents`/`document_links`, added to by code and by hand); new entity attributes (equity stakes, stated priorities, assets), typed relationships and event classes; an `aspect-match` implementation under `acquirer-pairing` tested forward (propose for every buyer at each year-end, count hits and false alarms); universe to widen to diagnostics, tools and data with private stubs (2.9′). Derived from the Tempus AI record (Ambry, Deep 6, Paige, Personalis; Ontology v4 §2.5). Ontology v4; Implementation Plan v9 rows L1–L4, 2.9′. Sequencing against Phase 1 pending (Ontology v4 §8 Q8).
- 2026-08-31: data-snapshot policy option A (0.5): Jason's 2026-08-29 data frozen as the snapshot of record; freeze as it stood (no `cparty-all` first); USB transfer to Harrison, not git (public repository, binary history growth, LFS quota); Ontology §8 Q5 thereby answered: the repository does not carry data.

## 0.8 Refactor record (2026-08-29, branch jason/refactor)
Commits: 76a3ba3 baseline hashes · c5bbf6c line endings · 26133aa dead code and duplicates removed (−2,750 lines) · f0ceeb0 credentials to .env · 49572ec coverage fix, portable VS Code path · 55bc9c1 src layout, pyproject, scripts/docs/data directories · 5c16ec8 ruff · da29a85 endpoints in config, package logging; six scripted gates 00–50 plus two fix scripts, all with matching SHA-256 hashes.

## 0.8a Gate record (Implementation Plan v7 ledger)
- Gate 0.1 DONE 2026-08-30 (880da16): schema.py + validate; config.py de-duplicated.
- Gate 0.2 DONE 2026-08-30 (5dbf595): DuckDB store layer, migrate (19 tables, counts equal), exports/snapshots, CSV folders frozen; in-gate Windows temp-file defect fixed.
- Gate 0.3 DONE 2026-08-30 (29b8701): run ledger (runs, run_params, run_metrics, run_artefacts), render-from-record for seven reports and predict, ledger-seed (7 legacy rows), report views.
- Gate 0.4 DONE 2026-08-31 (93c2194): models/ registry (target-screen: scorecard, fitted; acquirer-pairing: mass-exact; fda-event-study: daily-bars; six evaluations), declared inputs enforced at run time, run_type, models/run commands; first real run caught one undeclared legitimate read, fixed by declaration.
- DOC gate DONE 2026-08-31: this PART 0 regenerated; current-state diagram v2 (docs/20260831_v2_System_Diagram.md); target-state diagram v2 after Ontology v4 (docs/20260831_v2_System_Diagram_TARGET_STATE.md) and research-process diagram (docs/20260831_v1_Research_Process_Diagram.md), both Mermaid, 2026-08-31.
- Gate L4 DONE 2026-09-02: aspect-match + forward test (rules-first, Tempus-sequence deals excluded; equal weights); paired 0.108 vs 0.335 → pass mark NOT ADOPTED, recorded finding; forward 8/11/17 hits at k=5/10/25 vs chance 0.88/1.76/4.39, 5,921 false alarms; coverage metrics show three derived aspects carrying everything; incident R1 (out-of-record re-runs restored byte-exact via render-from-record); pytest 171; thirteen fingerprints MATCH; runbook docs/20260902_v2_GATEL4_INSTALL.md.
- Gate L3 DONE 2026-09-02: deal analyser (collect/propose/judge/consume, span-grounded, conflict-hold, verdict-gated); yardstick 0.625 raw + 8 consumed rows; ten-deal batch probe 0 fetch failures, 100% span-verified, spot-check 0.456 raw; runbook docs/20260902_v2_GATEL3_INSTALL.md.
- Gate 2.9′ DONE 2026-09-02: widening rule + TEM/PSNL members; index row with deal_id; measured no-movement on the frozen protocol (pool 862→863); diagnostics-mine finding; baselines re-hashed explicitly; runbook docs/20260901_v1_GATE29P_INSTALL.md (v2).
- Gate 1.5c DONE 2026-09-01: realized + delay writers over the ledger; r10 fresh-sample precision 0.933 [0.841, 0.974]; 2,053 realized rows with outcome states, 9 delays, 1 withdrawal supersession; runbook docs/20260901_v1_GATE15C_INSTALL.md.
- Gate 1.5b-eval DONE 2026-09-01: candidate_reviews + eval loop; r9 of record — precision 0.933 [0.841, 0.974] (60 blind verdicts), recall 0.846/0.915, misses fully classified, five true finds; runbook docs/20260901_v1_GATE15B_EVAL_INSTALL.md.
- Gate 1.5b DONE 2026-09-01: EFTS miner + candidate ledger — 2,653 documents, 14,002 ledger rows (r6), 701 forward events tier B; precision 8/10 (judged sample), recall 0.846 (FDA Tracker snapshot, benchmark only); pytest 140; validate 39/0/8/1 of 48; thirteen fingerprints MATCH; runbook docs/20260901_v2_GATE15B_INSTALL.md.
- Gate 1.5a DONE 2026-08-31: forward FDA calendar live — schema forward columns (0.8); calendar-forward: 16,112 CT.gov primary-completion rows + FDA AdCom JSON-endpoint writer (194 records, 2 upcoming, 4 rows, dated snapshot in the library); supersession history; events-migrate preserves forward rows; manifest self-listing fixed; events_table 20,398; validate 38/0/8/1; pytest 122; thirteen fingerprints MATCH; runbook docs/20260831_v2_GATE15A_INSTALL.md.
- Gate 2.10 DONE 2026-08-31: manual layer live (SCHEMA_VERSION 0.7; 64th command; schema-validated overrides; visible precedence, no consumer until L3); storage ruling applied — DB sole store, no row content in git, snapshot sole reconciliation, export/load rebuild path (17 rows / 6 tables round trip proven); dossier SEED marked LEGACY; validate 38/0/8/1; pytest 103; thirteen fingerprints MATCH; runbook docs/20260831_v1_GATE210_INSTALL.md.
- Gate L2 DONE 2026-08-31: dossier schema (8 tables, 47 declared, SCHEMA_VERSION 0.6) + span-verified Tempus–Personalis seed, 16/16 rows across 5 tables (run 20260831T203033-dossier); P19 mechanical (accession→capture→doc_id at load; span must occur in the capture); report-driven corrections (3 reassignments, 4 rows pending sources); validate 35/0/8/4; pytest 95; thirteen fingerprints MATCH; runbook docs/20260831_v1_GATEL2_INSTALL.md.
- Gate 1.4 DONE 2026-08-31: `events_table` live (4,282 rows migrated 1:1 from `events`, deterministic event_id, ledger run recorded); `event_date` column added per the approved amendment; v4 event classes declared (vocabulary complete from birth, writers at their own gates); `calendar IID` a view over trials + events_table with forward rows empty until 1.5/1.6; pytest 85; validate 27/0/8/4 (39 declared); thirteen fingerprints MATCH; runbook docs/20260831_v1_GATE14_INSTALL.md.
- Regression baseline: thirteen fingerprints (docs/regression_baseline.txt, ffbbf20), reproduced at every gate since.

## 0.9 Open queue (2026-09-03; detail in docs/20260903_v31_Session_Handoff.md)
1. Snapshot of record decided (0.5); remaining action: after the merge, hand `data\snapshots\20260831\` to Harrison on USB; he places `biointel.duckdb` at `<his root>\data\biointel.duckdb`, verifies the SHA-256 in 0.5 and runs `validate`.
2. `predict` composition (M1-P): `target-screen/fitted` has no fit/predict path; `scorecard` drives `predict`; decide fitted-ranks/scorecard-explains or keep.
3. Rotate the Alpha Vantage key; set the repository private (Harrison).
4. Pull request jason/refactor → main; Harrison's post-merge steps (install, migrate, ledger-seed) in the handoff.
5. Harrison to confirm the corrected MASS-exact figure (0.310) on his snapshot and retire the v0.81 "SUSPENDED" text in PART 5+.
6. Order of record complete (L4 DONE 2026-09-02). Open next, each its own decision or gate: (a) the a3 analyser rule agenda incl. aspect-extraction rules to populate stated_priorities/assets/deal_aspects — the coverage metrics show the aspect matcher is substrate-starved, not rule-starved; (b) 13D/13G ingestion for equity_stakes at scale; (c) aspect weights beyond the equal-weight prior (own pre-registration, weights never set on test deals); (d) `report pairs-aspect` RENDERERS entry with the next results.py gate; (e) gate L1 vs Phase 1 gate 1.4 sequencing question (Ontology §8 Q8) is moot — both done. Previously: L4 — aspect-match: the acquirer-pairing implementation that scores hypothetical pairs from company aspects (dossier-derived vocabulary, typed relationships, stated priorities) and tests them forward against verified deals. Previously: L3 — realized readouts and PDUFA outcomes as events with event_date and disclosure_datetime, delay_timing events from negated guidance, outcome_state from outcome words, all written from the `mined_candidates` ledger (no re-fetching; re-mine with r7 and re-measure precision/recall). Then 2.9′ → L3 → L4 (order of record L1 → 1.4 → L2 → 2.10 → 1.5a → 1.5b → 1.5c → 2.9′ → L3 → L4). Standing, no gate needed: pending seed rows re-admitted by captures — equity_value_usd (Tempus PR via `library add <file> --for Rf573315b3de`), the three Merck rows (merger-agreement exhibit or §9 news URLs), later timeline/comparables rows (remaining §9 URLs); before any rebuild-from-bronze, run `manual export` first and `manual load` after.
7. Universe check before 2.9′: are Tempus AI and Personalis among the 1,379 members (one query; Ontology v4 §8 Q9).
9. F1 close (collector → `stakes run` re-run as the r6 re-parse → blind 60 → precision → stub list → thirteen fingerprints → docs → commit).
10. Post-F1 gates, order to decide: threshold reconciliation (scoped); F2 (scoped, probe code written); hypothesis-store CLI entry and matcher wiring (v2 pre-registration); LOE/token-floor sensitivities (v2). Done ahead of F1: store extension, hypothesis store, annotation pass, raw-SQL guard; references rename cancelled.
8. `predict` composition (item 2) is subordinate to the dossier track: `aspect-match` results (gate L4) inform it; the buyer-agnostic checklist-versus-fitted test remains available as a cheap evaluation.

---

# PART 1 — THE GOAL

## 1.1 Scope statement

> Developed a system to identify suitable business and product partners for
> biotechnology companies across the bio-industrial ecosystem based on
> quantitative and qualitative criteria. Quantitative analysis includes
> balance sheet, accounting metrics and product pipeline data. Qualitative
> analysis profiles companies by clinical trial activity and related data
> factors. A built-in drug pipeline calendar tracks each candidate through
> its FDA clinical trial phase and PDUFA review date, showing where a
> company stands in the testing and approval process.

## 1.2 Scope clarifications agreed during the build

**Partners are not restricted to drug companies.** Stated directly: partners
"can also include connections to financial companies or nondrug companies."
The ecosystem includes CDMOs and manufacturing, diagnostics, devices and
delivery, CROs, computational and AI vendors, academic institutions, and
financial counterparties.

**The four NEC axes are examples, not the definition.** Stated directly:
"Do not exactly copy that. Those were simply categories." Drug repurposing,
drug simulation, de novo design and use of AI are illustrative qualitative
factors, not a fixed required list.

**Qualitative profiling means observed behaviour**, not a fixed taxonomy:
who a company partners with, what kinds of organisations, in what
therapeutic areas, and how consistently.

## 1.3 Position versus commercial equivalents

Cortellis, DealForma, Biotechgate and Evaluate exist to do this job.

| Component | This build |
|-----------|-----------|
| Drug pipelines, trial registries | yes — 19,454 trials |
| Company financials | yes — 3,664 periods |
| Regulatory / FDA data | yes — 1,929 events |
| Deal activity | partial — 1,137 filings, dates and types, **no counterparty names** |
| Partnership network | partial — 1,207 trial collaborations |
| Company capability profiles | no |

---

# PART 2 — CURRENT STATE

## 2.1 Working

| Layer | Source | Key | Volume |
|-------|--------|-----|--------|
| Company identity | SEC ticker map + submissions | ticker → CIK | 40 |
| Company description | Alpha Vantage OVERVIEW | ticker | 40 |
| FDA approvals | openFDA Drugs@FDA | name + alias | 1,911 |
| FDA rejections | openFDA CRL | name + alias | 18 |
| Daily prices | Yahoo Finance chart | ticker | on demand |
| Clinical trials | ClinicalTrials.gov v2 | sponsor name | 19,655 (clean rebuild) |
| Financials | SEC CompanyFacts XBRL | **CIK** | 3,664 periods |
| Pipeline calendar | derived: trials + FDA | IID | per company |
| Trial collaborations | derived from trials.csv | IID | 1,207 |
| Deal filings | SEC 8-K Items 1.01/1.02/2.01 | **CIK** | 1,137 |
| Deal counterparties | rewritten extractor over 8-K text | IID | 1,317 |
| Unified relationships | derived: partners + counterparties | IID | 2,150 |

## 2.2 Commands

```
add TICKER        backfill          events IID / events-all
trials IID / trials-all             calendar IID
fin IID / fin-all                   snapshot
partners          partners-of IID   tags IID
deals IID / deals-all               deals-of IID
window "APPNO" DATE                 list / sponsors / coverage
cparty IID [N] / cparty-all         (output unreliable, see 3.1)
```

## 2.3 Storage

```
data/bronze/    raw API responses + URL + fetch timestamp
data/silver/    companies, events, trials, financials, financial_snapshot,
                partners, partner_summary, deals, deal_counterparties
data/gold/      window.csv, calendar_{IID}.csv
```

## 2.4 Entity resolution

FDA and ClinicalTrials.gov publish no CIK, ticker, CUSIP or LEI. Name is the
only join. SEC-side sources are keyed on CIK and have no matching problem.

| Failure mode | Example | Solution |
|--------------|---------|----------|
| Formatting variance | `Amgen Inc.` vs `Amgen, Inc.` | canonicalization, exact equality |
| Trade vs legal name | `JANSSEN PHARMS` vs `JOHNSON & JOHNSON` | `FDAAliases` column |
| Descriptor abbreviation | `ALNYLAM PHARMS` vs `...PHARMACEUTICALS` | strip descriptors |
| Generic search term | `RHYTHM` returned Medtronic devices | `CTGovName` override |

Verification requires exact canonical equality, so failures are **missing,
never wrong**.

---

# PART 3 — WHAT IS NOT WORKING

## 3.1 Counterparty extraction — REPAIRED (v0.6)

The blocker is resolved: the zip contained 1,062 real fetched 8-K documents
and 20 real `index.json` responses in bronze, satisfying the stated
requirement to resume. The extractor was rewritten and validated against
those real documents.

**What changed, per diagnosed junk class:**
1. **Section bounding.** Extraction runs only inside Items 1.01/1.02/2.01
   and exhibit-index description lines. The old version scanned whole
   documents — that is how director names (Item 5.02) reached the output.
2. **Exhibit descriptions first**, per the Material Contracts Corpus:
   "License Agreement, dated ..., by and between A and B" lines carry
   type, date and parties in one sentence.
3. **ORG-only NER** (PERSON/NORP/FAC dropped) with MCC-style generic
   exclusions (laws, regulations, committees, exchanges, regulators),
   drug-code rejection, document-noun rejection, and 60-char anchor
   proximity.

**Validation on 200 real filings:** mean 1.98 / median 2 counterparties
per nonempty filing (corpus benchmark ~3 parties per contract including
the filer itself); ~90% real organisations in random samples. End-to-end
on Amgen's 96 cached filings: Tularik, Abgenix, Avidia (all real Amgen
acquisitions) and the Daiichi Sankyo collaboration surface correctly.

An Item 1.01 with no counterparty (equity-plan amendment, bylaws) is a
correct empty result; hit rates below 100% are expected.

**Residual known noise:** occasional deal-mechanics phrases survive
("Company Contribution", "Group II"); acceptable for aggregation, flagged
for the capability-classification phase.

## 3.1-old Counterparty extraction — original failure record (three attempts)

**Goal:** turn "Regeneron entered 68 agreements" into "Regeneron partnered
with Sanofi, Bayer, Intellia."

**Attempt 1 — regex patterns.** 1,054 extracted. Roughly half junk:
`Administrative Agent`, `Lessor`, `Inc` (bare suffix), `Third Amendment`.

**Attempt 2 — regex plus role/document stopword filters.** Cleaner on the
specific junk shown, untested on the rest.

**Attempt 3 — spaCy NER hybrid.** 5,887 extracted, hit rates 85-100%, but
6-16 counterparties per filing against a published benchmark of ~3. Sample
inspection showed director names, `Regulation S-K`, `Delaware General
Corporation Law`, `Audit Committee`, `Exhibit 1.1`.

**Diagnostic attempt.** A script to check whether filings carry contract
exhibits returned 0/20 with no exhibit types at all — not even EX-99, which
nearly every 8-K has. The diagnostic itself was buggy; its type-matching did
not correspond to the values SEC returns.

**Root cause:** this environment cannot reach SEC endpoints or read the
fetched documents. Every pattern was written against invented text, run
against real filings elsewhere, and patched based on whichever failures got
pasted back. That loop does not converge.

**Published method, for reference.** The Material Contracts Corpus
(Stanford, 2025) parses exhibit types 2, 10 and 99 — the agreement documents
— not the 8-K narrative. Pretrained RoBERTa NER, then exclusion of generic
entities such as "board of directors", "Delaware corporation" and state
names, then name linking by Levenshtein ratio and acronym matching. Reported
accuracy: perfect recall on 100 contracts, 96% containing only actual
parties, extras at 1.2% of tags. Mean 3.07 parties per contract.

**Requirement to resume:** raw contents of one filing `index.json` and one
8-K document from `data/bronze/`, so patterns are written against real field
values rather than assumed ones. Without that, further attempts repeat the
same loop.

## 3.2 Other defects

| Issue | Effect |
|-------|--------|
| AstraZeneca, Takeda return 0 **deals** | 6-K filers, no 8-Ks — structural; financials restored v0.6 via ifrs-full. `cparty-all` correctly reports no deal filings for both. |
| Schrödinger returns 0 trials | Search term 'SCHRODINGER' misses the CT.gov sponsor spelling (umlaut: 'Schrödinger'). Fix: set CTGovName='Schrödinger' — one cell, then re-run `trials 8`. |
| TTM burn fix written, not shipped | Cash-flow facts are cumulative YTD; annualizing one figure gave Sarepta 836 months of runway |
| ~~6 companies with contaminated trials~~ | **resolved v0.7**: clean rebuild via CTGovName — RYTM now 29 (exactly its own), MRK 2,172 via Merck Sharp & Dohme, JNJ 1,734 via Janssen |
| Collaborator type misclassification | Novella Clinical tagged Academic; it is a CRO |
| `Industry (unclassified)` is the largest partner bucket | Keyword rules do not name most pharma partners |
| Roche / F. Hoffmann-La Roche not merged | Fails as distinct, not wrong |

## 3.3 Structural limits

**PDUFA goal dates cannot be obtained.** 21 CFR 314.430 bars FDA from
confirming an application exists until the sponsor discloses it. The build
captures retrospective **action** dates. This is a permanent limit, not a
gap.

**FDA paused CRL publication** following an April 2026 citizen's petition;
HHS confirmed. Existing coverage intact, new rejections may not appear.

**Alpha Vantage free tier: 25 calls/day.** Affects descriptions only.

**59% of approvals are `SUPPL`** label expansions, not new approvals.

---

# PART 4 — SCOPE STATEMENT, ITEM BY ITEM

| # | Scope phrase | Status |
|---|--------------|--------|
| 1 | balance sheet | done |
| 2 | accounting metrics | done, TTM fix pending |
| 3 | product pipeline data | done |
| 4 | clinical trial activity | done |
| 5 | pipeline calendar, FDA phase | done |
| 6 | PDUFA review date | partial — action dates only, see 3.3 |
| 7 | qualitative data factors | partial — trial collaborations only |
| 8 | identify suitable partners | partial — relationship data incomplete |

---

# PART 5 — REMAINING WORK

## 5.1 Fixes to what exists

| ID | Task | Effort |
|----|------|--------|
| F1 | Ship the TTM burn fix | **done** — in `financials.py`, method audit column `TTMMethod` now written to snapshot |
| F2 | Add `ifrs-full` taxonomy for foreign filers | **done v0.6** — AZN: 21 periods, Takeda: 10 periods from cached facts; `Currency` column added (Takeda reports JPY) |
| F3 | `CTGovName` for the 6 contaminated companies | **done v0.6** — column added to schema (fixing a bug where `add` would have destroyed it) and set for RYTM/LLY/PTCT/VERA/JNJ/MRK; **delete `trials.csv` and re-run `trials-all`** to purge contaminated rows |
| F4 | Extend collaborator type keyword rules | **done v0.6** — Novella Clinical → CRO, more CRO keywords, Roche/F. Hoffmann-La Roche merged |

## 5.2 Blocked

| ID | Task | Blocker |
|----|------|---------|
| B1 | Counterparty extraction | **unblocked and repaired**, see 3.1. On the main machine: delete `data/silver/deal_counterparties.csv`, then `python cli.py cparty-all`. |

## 5.3 Not started

| ID | Task | Notes |
|----|------|-------|
| N1 | Company capability profiles | Requires storing 10-K Item 1 text, then classification. No API returns these. |
| N2 | Merge trial and deal relationships into one table | **done v0.8** — `relationships` command, see 5C |
| N3 | Partner matching output | Depends on N1 and N2 (N2 now done) |

---

# PART 5A — EVENT STUDY ENGINE (new in v0.6)

`biointel/study.py` implements the five designed stock-impact metrics as a
market-model event study (Brown & Warner): CAR vs XBI over [-1,+1], [0,+1],
[-5,+5]; T0 overnight gap vs intraday; abnormal volume vs the [-10,-2]
mean; volatility shift (post/pre std ratio); post-event drift via 3v7-day
mean crossover. If the benchmark is unreachable, CAR falls back to raw
cumulative return and the row is marked `Benchmark=none` — never a silent
substitute. Math validated against real cached REGN bars with a hand-check
(CAR[0,+1] = −0.72 both ways).

Commands: `study "APPNO" DATE`, `study-all` (→ `gold/event_study.csv` +
`gold/event_study_summary.csv` by outcome class), `freeze` (→
`data/frozen/YYYYMMDD/` with coverage manifest, for paper reproducibility).

# PART 5B — DEPLOYMENT RUN RESULTS (v0.7, main machine)

All three rebuild commands ran clean on 2026-08-23:

**trials-all** — 19,655 rows. Contamination fix verified: RYTM 29 (exactly
its own 29 from the audit), VERA 6, PTCT 65, MRK 2,172 (Merck Sharp &
Dohme, no Merck KGaA), JNJ 1,734 (Janssen). One new gap: Schrödinger 0
(umlaut, see 3.2).

**cparty-all** — 1,317 counterparties from ~1,198 filings across 38
companies (AZN/Takeda correctly skip: no 8-Ks). Hit rates 33–100% by
company; low rates cluster in companies whose 8-Ks are dominated by
financing/compensation items, which is expected behaviour, not failure.

**study-all** — 854 events computed into `gold/event_study.csv`:

| Outcome class | N | CAR[-1,+1] mean | median |
|---|---|---|---|
| Approval / New drug | 150 | +0.63 | +0.53 |
| Approval / New indication | 678 | −0.08 | −0.13 |
| Rejection / Later approved | 16 | −1.85 | −1.18 |
| Rejection / Never approved | 10 | −18.19 | −0.72 |

The pattern matches the published event-study literature: approvals mildly
positive (largely priced in), label expansions a non-event, rejections
negative and asymmetric. Never-approved mean (−18.19) versus median
(−0.72) shows a heavy left tail — a few catastrophic CRLs dominate; N=10
is too small to quote as a population estimate in the paper without the
expanded universe.

# PART 5C — UNIFIED RELATIONSHIPS TABLE (N2, done v0.8)

`python cli.py relationships` merges partners.csv (trial collaborations)
and deal_counterparties.csv into `silver/relationships.csv`: one row per
(company, canonical partner, relationship kind, agreement type), with
Count, FirstDate/LastDate, TherapyAreas (trial side), Evidence
(accessions, deal side). Canonicalization reuses network._norm, so name
variants collapse; the fullest raw name seen is kept for display.

**PartnerIID** is set when the partner is itself a universe company —
these in-universe pairs are the direct pairing input for the M&A model,
and `AgreementType = Merger/Acquisition` rows are the acquisition-label
candidates.

Validation on container data (Amgen deal rows + full trial layer): zero
duplicate keys; real Amgen acquisitions surface with dates (Abgenix 2005,
Avidia 2006, BioVex 2011, Micromet 2012 via its merger sub, Onyx 2013,
Five Prime 2021, Teneobio 2021); seven partners correctly bridge both the
trial and deal layers (Novartis, Daiichi Sankyo, Takeda, Immunex...).

**Residual noise, accepted:** occasional deal-mechanics phrases ("Offer
Price") and one regulator ("Turkish Competition Authority"); merger-sub
shell names appear alongside the real target, which is harmless for
labels.

**Main-machine run (v0.9):** 2,150 relationships from 1,207 trial edges +
1,317 deal rows; 71 in-universe pairs; **152 Merger/Acquisition label
candidate rows** — the raw material for the Phase L label panel.

**Caveat carried to Phase L:** acquirer-side filings name the *target*;
the label panel additionally needs the target's own Item 2.01/DEFM14A and
delisting to establish direction and completion. Design already reflects
this (plan §5, L2).

# PART 5D — M&A LABEL SET (Phase L, done v0.10)

`python cli.py labels` writes two outputs:

**silver/ma_events.csv** — cleaned acquisition events from the deal layer.
Merger-sub shells and mechanics phrases are dropped. Direction is resolved
from the filer's own SEC merger trail: target-side proxies (DEFM14A /
PREM14A / SC 14D9) mark the filer as target; an Item 2.01 completion that
NAMES the counterparty marks the filer as acquirer; anything unresolved is
Role=unknown, never guessed.

**gold/label_panel.csv** — firm-quarter panel from 2010: AcquiredNext12m /
AcquiredNext24m (target side), MadeAcquisition12m (acquirer side). Labels
look strictly forward from quarter end (leakage-safe, per Palepu-informed
design in plan §6).

**Two defects caught and fixed during validation:**
1. An asset purchase from a large partner (Amgen–BMS Otezla 2019) falsely
   labelled the partner as acquired. Fix: an in-universe counterparty is
   mirrored as target only when its OWN merger trail corroborates
   (target-side proxy or delisting near completion). The false BMY
   positives disappeared.
2. Completion dates were matched by filer+window and attached to the wrong
   deal (BeiGene row took the Horizon completion). Fix: completion
   requires an Item 2.01 filing that names the same counterparty.
   Precision chosen over recall; unmatched completions leave
   Status=announced-only.

**Spot-check result (v0.12): all 12 positives were three false events,
now fixed.** (1) NVIDIA's 2023 equity investment in Recursion labelled an
acquisition — cause: "stock/share purchase agreement" typed as
Merger/Acquisition; those now type as "Stake purchase" and labels consume
only true merger vocabulary. (2) "Eidos Restricted Share Award" as
BridgeBio's acquirer — junk name (singular word forms missing from the
filter, now added) and inverted direction: BridgeBio acquired Eidos while
its share-issuance proxy triggered the target rule; a completion that
names the counterparty now takes precedence over proxies. (3) Morgan
Stanley Senior Funding "acquiring" Crinetics — a credit agreement typed
M&A, dead under fix 1; if Crinetics is genuinely in a pending 2026
merger, it will resurface from a true merger-agreement row with the real
acquirer. Proxy window tightened to announce−30..+330 days. Regression on
container data: Amgen's real acquisitions (Onyx completed 2013-10-01, BMS
Otezla) intact, zero false positives.

**Label architecture restructured (v0.14) — root cause, not another
patch.** Every spot-check failure came from one structural flaw: labels
were inferred solely from heuristics over acquirer-side 8-K narrative.
Acquisition events are rare and individually verifiable, so the layer is
now propose → verify → consume:

1. **Propose.** Events are machine-assembled from five *independent* SEC
   signals, each a visible column: S1 merger-agreement row, S2 target
   proxies (DEFM14A/PREM14A/SC 14D9), S3 completion naming the
   counterparty, S4 Form 25/15 delisting, S5 cessation of periodic
   filings. Confidence = number of agreeing signals. A new TARGET-SIDE
   PROBER proposes events from each company's own filing trail,
   independent of text extraction — this is what makes P1 universe
   expansion generate labels automatically for acquired/delisted
   companies from their authoritative own-CIK record.
2. **Verify.** `silver/ma_events_verified.csv` is the curated overlay;
   verified rows override proposals and stand alone even when local
   caches predate the filings. Seeded with the web-verified live event:
   **Vertex acquires Crinetics, announced 2026-07-06, $85.00/share cash,
   ~$10.0B equity value, close expected Q3 2026** (Crinetics 8-K and
   DEFA14A; company press releases). The extraction had recorded Morgan
   Stanley Senior Funding — the bridge lender — as acquirer; lenders are
   now categorically excluded from the acquirer field.
3. **Consume.** The panel takes target labels only from verified events
   or proposals with ≥2 independent target-side signals, and stamps
   provenance in `LabelSource` (verified / proposed-cN). For the paper,
   the methods section writes itself: "events proposed from SEC signals,
   hand-verified against filings and announcements."

Container validation: panel positives are exactly the four CRNX quarters,
all `verified`, acquirer Vertex; Amgen regression intact; the prober
independently rediscovered Immunovant's 2019 SPAC-combination proxies and
correctly declined to label the surviving entity as acquired.

**Main-machine confirmation (v0.15):** 107 events; 61 acquirer / 1
target / 45 unknown; exactly 4 positives, all CRNX quarters, source
`verified`, acquirer Vertex — matching the container prediction. Phase L
is closed: the panel is leakage-safe, provenance-stamped, and every
positive label is individually verified. Phase M (feature table +
scoring) is next.

**Historical note — second spot check (v0.13): two survivors, both fixed.** (1) BBIO/Eidos
direction was still inverted — BridgeBio filed the DEFM14A as a
share-issuing acquirer and no Item 2.01 named Eidos. New discriminator
from cached submissions: `still_filing_after()` — a company acquired at T
does not keep filing 10-K/10-Q/8-K past T+15 months; a survivor with
proxies is a share-issuing acquirer, not a target. Validated: BBIO →
survives → acquirer. (2) CRNX appears to be a GENUINE pending 2026 merger
(its DEFM14A/PREM14A are real and the horizon is too recent to judge
survival), but the recorded counterparty was the financing agent.
Financing institutions (bank/agent name patterns) are never recorded as
acquirer; the panel now shows "(acquirer unresolved)". The four CRNX
positive firm-quarters are therefore treated as REAL labels pending the
merger's outcome — the first live positives in the panel.

**Prior run (v0.11):** 135 M&A events (71 acquirer, 3 target, 61
unknown); 12 positive firm-quarters, base rate 0.45%. The 3 target-role
events and 12 positives are pending a one-time manual spot check before
Phase M consumes them — the likely explanation for target roles among 40
surviving companies is SPAC/reverse-merger combinations (the filer was
technically the target yet survived as the listed entity), which are true
corporate events but a different animal from a takeover-and-delisting and
may warrant an EventClass column. 61 unknowns are events announced without
a matchable completion; they cost recall, not correctness. 0.45% is far
too few positives for a trained classifier — confirms the plan's staging:
scoring framework first, statistical model after P1 universe expansion.

**Survivorship note (P2):** with the current 40 surviving companies the
target-side label columns are near-zero by construction. The panel
populates as acquired/delisted companies enter under the P1 universe
rule; the machinery is validated and waiting.

# PART 5E — FEATURE TABLE (Phase M1, done v0.16)

`python cli.py features` builds `gold/feature_panel.csv` and joins it
with labels into `gold/model_panel.csv` — one row per firm-quarter,
every feature strictly as-of quarter end. Families: financials (latest
period ≤ Q within 400 days; OCF converted to TTM via the FP marker, same
convention as the shipped burn fix; BurnAnnual, RunwayMonths, Currency
passthrough for the JPY/Takeda case), pipeline (trials by phase, lead
phase, starts 12m), FDA (original approvals ever, approvals/rejections
12m, days since last event), market reaction (mean CAR[-1,+1] and drift
of trailing-12m events from the event study), relationships (totals by
kind, deals 24m, licenses/collaborations, in-universe ties), and price
(quarter close, market cap, 52-week drawdown — filled when the price API
is reachable, blank otherwise, never fabricated).

Container audit: 2,640 firm-quarters, 1,854 with financials; **zero
leakage** (no FinPeriodEnd past QuarterEnd), zero trial-count
monotonicity violations, all four verified CRNX positives joined. The
CRNX feature rows read like the company Vertex paid $10B for: $1.0–1.3B
cash+STI, ~33 months runway, five Phase-3 trials, lead phase 3 — the
model's first positive example is economically coherent.

**Main-machine run (v0.17):** fin-all restored AstraZeneca (21 IFRS
periods) and Takeda (+8, JPY-flagged) — the R4 fix confirmed live.
`features` produced 2,640 firm-quarters: 1,930 with financials, **1,975
with price/market-cap features** (Yahoo reachable), all 4 verified
positives joined. M1 closed. Remaining in Phase M: M3 pairing score, M4
scoring model, M5 backtest.

# PART 5F — SCORING, PAIRING, BACKTEST (M3-M5, done v0.18)

**Why a transparent score, not a fitted classifier.** The verified label
set holds one acquisition; anything FITTED to it would be curve-tracing
dressed as learning — the overstatement Palepu (1986) documented. Until
P1 expansion supplies enough verified events, the instrument is an
additive 0–100 target score with stated, literature-grounded weights
(de-risked asset 25/20/5; momentum 10/5; acquirable size band 15;
strategic ties 10/5; exit pressure 10), auditable per company via a
ScoreBreakdown column. Acquirer-side companies (annualized revenue >
$10B or market cap > $75B) are excluded from the target list and become
the pairing candidates: Fit = 50·therapeutic-area Jaccard (trial
condition tokens) + 30·prior relationship + 20·size headroom.

Commands: `predict [QUARTER]` → `gold/ma_predictions.csv` (rank, score,
breakdown, top-3 acquirers with fit); `backtest` → the pre-announcement
rank of every verified acquisition.

**Pre-registered live test.** The container backtest is UNREPRESENTATIVE
(no price data → no size points; CRNX's Palsonify approval absent from
the container events cache), and is recorded only for honesty: CRNX
ranked ~30/34 there. The real test is the main-machine `backtest` with
full price + events data — whatever rank it reports for CRNX at
2026-06-30 is the paper's headline validation number, reported as-is.
The score will NOT be tuned to move CRNX up after seeing the result.

# PART 5G — BACKTEST DIAGNOSIS: THE MISS IS A DATA HOLE (v0.19)

The main-machine backtest ranked CRNX ~29/33 pre-announcement. Per the
pre-registration, that number stands as reported. Diagnosis before
interpretation, though, found the input was broken, not the score:

**21 of 40 companies have ZERO FDA events** — including ALNY, ACAD,
VNDA, MDGL, AXSM, TVTX, RYTM, HRMY, AGIO and CRNX, all of which have
approved drugs. The cached openFDA queries show why: they searched the
full registrant descriptor (`sponsor_name:"ALNYLAM PHARMACEUTICALS"`)
while Drugs@FDA files sponsors abbreviated (`ALNYLAM PHARMS INC`), so
the phrase search returned nothing. This is the documented
descriptor-abbreviation failure mode hitting the events layer. Current
code searches the canonical stripped key ("ALNYLAM") with exact-canonical
verification per variant, plus auto-generated abbreviation variants
(PHARMACEUTICALS→PHARMS etc.) in `fda.py::name_variants` — a re-fetch
restores the missing approvals; contamination remains impossible because
verification is unchanged.

CRNX's own arithmetic shows the stakes: with Palsonify's Sept-2025
approval present, its 2026-06-30 score gains approved-drug (+25) and
approval-in-12m (+10) on top of the current 25, before any size or CAR
points — from bottom-quintile to top-tier on data correction alone, with
**weights untouched**. Fixing inputs is correctness; the no-tuning
commitment applies to weights and stands.

Also fixed in features.py: latest-financial-row selection could land on
a dei cover-date row with no substantive fields (Pfizer's missing
revenue/shares let it leak into the target list), and SharesOutstanding
now forward-fills from cover-date rows so MarketCap and the
acquirer-side filter work.

# PART 5H — VALIDATION RECORD ON CORRECTED DATA (v0.20, final for 40-company universe)

Backtest, pre-registered, corrected inputs, weights untouched:

| Quarter | CRNX rank | Score | Universe |
|---|---|---|---|
| 2025-09-30 | 16/30 | 55 | 40-co dev set |
| 2025-12-31 | 11/30 | 60 | 40-co dev set |
| 2026-03-31 | 17/30 | 60 | 40-co dev set |
| 2026-06-30 | 15/31 | 60 | 40-co dev set |

**Honest reading.** The data correction moved CRNX from bottom quintile
(29/33) to mid-pack (11–17 of ~30), not top quintile. Reported as-is.
Three structural reasons, all fixable by design rather than by weights:
(1) score saturation — fifteen companies score 60–70 because binary point
features produce ties; discriminating power requires fitted weights,
which require the labels P1 expansion brings. (2) The acquirer, Vertex,
is not in the 40-company universe, so the pairing engine could not have
named it; acquirer coverage is a universe-size property. (3) A
quality-premium acquisition (33-month runway, freshly launched drug) is
exactly the profile the exit-pressure component cannot see; the
asset-attraction components did fire (approved drug, Phase-3 depth,
size). With N=1 no statistical claim is made in either direction —
which is itself the Palepu-compliant statement.

**Pipeline status: END-TO-END COMPLETE for the development universe.**
Both terminal outputs produce from real data: `ma_predictions.csv`
(ranked pairings with evidence) and the event-study engine
(854+ events, literature-consistent CARs). Every layer is validated,
provenance-stamped, and reproducible via `freeze`.

# PART 5I — UNIVERSE MACHINERY (P1a, shipped v0.21, gated on probe)

`biointel/universe.py` implements the paper's inclusion rule, stated once
and applied mechanically: SIC 2836/2834 filers with an annual report
(10-K/20-F) dated ≥ 2013-01-01 and a NYSE/Nasdaq listing past or
present — **delisted companies kept**, membership dated at entry; any
market-cap floor is applied at analysis time as a sensitivity, never at
ingestion (an ingestion floor would re-introduce size survivorship).

Candidate source: EDGAR browse-by-SIC atom pages; detail per CIK from
the submissions endpoint already in use (retained by EDGAR after
delisting, including tickers, exchanges, and Form 25/15 evidence).

**Honesty gate:** browse-edgar is unreachable from the build
environment, so the endpoint is untested here. `universe-probe` fetches
ONE real page, prints the parse result (or the raw head on failure), and
the full `universe` build refuses to run until a probe succeeds on the
main machine — the counterparty lesson, institutionalized. The parser
was offline-tested against both known atom shapes, with the per-entry
fallback fixed after the feed-level title swallowed the first CIK.

**FINAL UNIVERSE (v0.26): 1,208 members, 422 exchange-delisted kept,
2,394 screened, 38/40 dev set.** The Form-25-only rule settled membership
between the two earlier builds exactly as predicted (645 under the
survivorship bug, 1,347 under the Form-15 over-admission). 422 delisted
is the upper bound on harvestable acquisition labels; not all delistings
are acquisitions (bankruptcies, going-private), which the harvest's
proxy-form signal separates. P1a closed.

**Main-machine harvest (v0.27): 371 proposed events, 347 at
confidence ≥ 2, from 1,208 members** — the label supply went from one
verified acquisition to a ~350-event worklist in one cached-data pass.

**Label set final state (v0.30): 287 machine-verified acquirer fills +
60 manual-worklist rows** (placeholder rerun: 6 cleared, 2 re-resolved,
4 to manual). Phase L is done at universe scale.

**HYBRID VERDICT (v0.67).** latent-SVD alone: HR@5 0.143 / HR@10
0.208 — clearly below MASS-inspired; hybrid fusion: HR@5 0.186 /
HR@10 0.287 — HR@5 worse, HR@10 a wash within single-draw noise.
Latent factors do not rescue the diversifying-deal failure mode;
consistent with the source paper's own finding that MASS beats graph
methods overall. **MASS-inspired stays the adopted engine (HR@5 0.222 /
HR@10 0.284).** Improvement ledger on the pairing track now: cosine →
MASS-inspired (+2.3pp HR@10, real), supervised ranker (top-10 wash,
median worse), latent (−), hybrid (0). Remaining measured-path options,
in order of published support: exact Sapling formula (vs our inspired
approximation), S1 strategic-review conditional numbers, 24-month
horizon screen, torch-based LightGCN (new heavy dependency). Session
context is at its limit; next session resumes from this file — the
pipeline, all engines, and all verdicts carry over intact. Our
pairing misses are the DIVERSIFYING deals (zero portfolio overlap);
the 2026 paper states graph methods take over exactly where
similarity is inapplicable. Shipped into `pairs-protocol`: a
latent-SVD variant (64-dim embedding of trial-term + partner-network
features — generalizes beyond exact overlap) and a rank-fusion HYBRID
of MASS-inspired + latent. Path tested three-metric end-to-end.

**FIELD-PROTOCOL NUMBERS (v0.65).**

| Metric | HR@5 | HR@10 | Protocol |
|---|---|---|---|
| cosine (field baseline = our prior method) | 0.216 ±0.010 | 0.261 | 200 negatives, 20 repeats, 129 events |
| **MASS-inspired (adopted)** | **0.222 ±0.010** | **0.284** | same |

The MASS-style modifications beat cosine on our data exactly as the
paper reports on theirs (+2.3pp HR@10, outside repeat noise). The
tool's practical statement: **given a shopping acquirer, the true
target appears in the top-5 of 200 candidates 22% of the time** (chance
2.5%), and in the full-universe framing, top-10 of ~1,000 about 1 in 5.
Model measurement is COMPLETE across every track. Remaining: regenerate
`ma_predictions.csv` with the MASS-inspired metric as the shipped
pairing engine, results assembly, GEN A-List head-to-head (optional),
final freeze, paper draft. Research find:
the published field evaluates pairing as HR@5 against 200 SAMPLED
negatives — our 0.17–0.21 hit@10 was measured against the FULL ~1,000
candidate universe, a ~5x harder test; the numbers were never
comparable. `pairs-protocol` shipped: same events, field protocol
(200 negatives, 20 repeats), reporting cosine (their stated baseline —
our current method) beside a MASS-inspired variant implementing the
paper's two modifications in spirit (size-asymmetry damping;
strengthened rare-term idf^2) — labeled MASS-INSPIRED, not their exact
formula, honestly. Their published result: the modifications
consistently beat cosine. Ours to measure.

**SUPERVISED PAIR VERDICT (v0.63) — model work now fully closed.**
Test 2020+ (86 events, full ~1,000-candidate sets): hit@10 0.21, median
rank 221; unsupervised similarity: hit@10 0.17, median 139 (127 events,
all years — comparator sets differ, stated plainly). Reading:
supervision adds a little top-10 concentration, similarity carries most
of the signal, and the distribution is bimodal — 14 events ranked in
single digits (portfolio-adjacent deals are nearly nailed) while
diversifying acquisitions are unrankable by portfolio fit. The paper's
pairing claim, conservatively: **the true target appears in the top-10
of ~1,000 candidates 17–21% of the time (~16–21× chance), given the
acquirer** — robust across supervised and unsupervised variants, zero
leakage risk in the unsupervised form. All model tracks now closed:
target screen 2.1–2.2× (two clean holdouts), pairing 16–21×, leak
dissection, ceiling established across eleven improvement attempts.
REMAINING WORK: results assembly, GEN A-List head-to-head (optional),
final freeze, paper draft per the deliverable spec.

**BEST-POSSIBLE-ANSWER BUILD (v0.62).**
The target screen is timing-noise-capped; the pairing model is the only
result with demonstrated headroom (16x from UNSUPERVISED cosine alone;
the field SOTA is supervised). `pairs-fit` shipped: GBM ranker on pair
features (portfolio similarity, size structure, log revenues/cash,
existing-partnership link, acquirer 3y deal appetite, target Ph3
catalysts), trained on pre-2020 true pairs + 40 sampled negatives each,
tested on 2020+ events by re-ranking the FULL candidate set (~1,000).
Comparator fixed in the report: unsupervised hit@10 0.17 / median 139.

**MODEL WORK CLOSED (v0.61) — final numbers, both holdouts spent.**

| Result | Value | Status |
|---|---|---|
| Pairing model (who buys whom) | **hit@10 0.17 vs ~0.01 chance (~16×), median rank 139/956, 127 events** | unsupervised, leak-free by construction, reportable |
| Target screen gen-2 (tuned GBM + engineered + text + pair-fit + catalysts) | **holdout 2023+: AUC-PR 0.079, 2.2× lift, ROC 0.720 (n=12,471, pos=454)** | second and last holdout access, disclosed |
| Target screen gen-1 | holdout 0.081 / 2.1× / 0.720 | first access |
| Leak dissection | fake 6.2×/0.985-ROC via delisting missingness, diagnosed + retracted | headline methods finding |

Dev (2.24×) → holdout (2.2×): confirmed, no overfitting signature. The
target-screen ceiling of free public data is **~2.1–2.2×, established
across ten independent improvement attempts** (two feature rounds, GBM,
ensemble, two tuning grids, activist, wave/TA, text, 3× training
events, catalysts, pair-fit). The formulation pivot paid off where the
literature said it would: the PAIRING question, at ~16×. Iteration is
over; remaining work is results assembly, freeze, and the draft (GEN
A-List head-to-head optional in assembly).

**PAIR RESULTS + HOLDOUT FIX (v0.60).** Main-machine pair model:
**hit@10 = 0.17 vs ~0.01 chance (~16x), median true-target rank 139/956,
127 events** — unsupervised, zero fitted parameters, leak-free by
construction, immediately reportable as the paper's pairing result.
Target-model feedback: dev 0.066/2.2x with _maxSimToAcq — first durable
gain past the plateau. Operator question caught a real defect: holdout
never computed the text score (dev-only path), so the gen-2 final would
have silently zeroed text. Fixed: holdout honors the spec and builds
dev-trained text scores; path exercised end-to-end. Gen-2 close-out:
tune, then the disclosed second holdout.

**PAIR MODEL SHIPPED (v0.59) — certified best per current knowledge.**
`pairs` builds (a) the field-protocol evaluation: for every verified
event whose acquirer resolves into the universe, the TRUE target's rank
among all eligible targets by TF-IDF portfolio similarity at the month
before announcement (median rank, hit@10/@25, MRR →
gold/pair_report.txt); (b) the `_maxSimToAcq` feature (per firm-year max
similarity to any $2B+ acquirer, cached) now inside the engineered set.
Rare-technology emphasis via idf; large-acquires-small via
one-directional eligibility. Ranking math exercised end-to-end in
container (synthetic in-registry pair). Two commands decide the pivot's
value: `pairs` (the pair model's own scoreboard) and `develop` (whether
acquirer-fit lifts the target model).

**FORMULATION PIVOT (v0.58) — the research verdict on WHY
the ceiling exists.** The state-of-the-art M&A prediction line (PLOS
2023 & 2026; arXiv 2024 dynamic-network deep learning) is unanimous:
standalone target classification — OUR design — discards half the
information; the field's best results come from DEAL-LEVEL PAIR
prediction, i.e., link prediction between acquirer and target
portfolios. The 2024 paper criticizes target-only models in exactly our
form ("fail to take advantage of the information of both sides"); the
2026 MASS paper achieves state-of-the-art with an interpretable
asymmetric similarity over weighted bipartite firm-technology networks
(large-acquires-small asymmetry + rare-technology weighting), beating
tree ensembles AND graph neural networks. WE HAVE THE NETWORKS: firm ×
condition/intervention terms (trials), firm × partners (relationships),
firm × text terms (10-K corpus). Build plan: as-of firm portfolio
vectors → MASS-style asymmetric similarity per (acquirer, target,
quarter) → evaluation in the field's protocol (true target ranked
against 200 sampled negatives per acquirer, mAP + AUC-PR,
time-respecting) → similarity-to-plausible-acquirers as a feature back
into the target model. This changes the QUESTION (who fits whom) rather
than adding an eleventh feature to a saturated one.

**EXPANSION VERDICT (v0.57).** Full 2001 run
completed (573 events / 447 target-role; 91,146-quarter panel; 1,508
positives; 11,859 documents), yet dev-window performance is unchanged
(GBM+text 0.062 / 2.1×): tripled training events did not move
2017-2022 out-of-sample ranking. Reading: pre-2009 label mass arrives
feature-poor (XBRL reaches ~2009) and decade-old deal patterns do not
transfer — the ~2× ceiling is an information limit of these features,
not event scarcity. The expansion's DATA contribution stands (label set
roughly doubled). FINAL two shots, catalyst-class features: **S2 trial
outcomes shipped this version** (zero fetches — _p3done12m/_p3done6m
Phase-3 readouts, _term12m terminations, from silver; flow-tested);
S1 strategic-review flag remains if S2 is flat. Pre-registered close:
if S2 (then S1) fail to beat the plateau, model work ends at the gen-1
holdout (2.1×) and the paper's model section is final.

**EXPANSION TO 2001 (v0.56).** Expert synthesis
of the session's research: every improvement failed the same way
(text overfit ~550 positives; activist/wave under-powered; GBM early
plateau) → the binding constraint is EVENTS, not ideas. Window start
moved 2013→2001; legacy annual forms (10-K405/10-KSB) admitted; text
and activist scans extended. Expected: universe 1,194→~2,000+, events
155→400+ corroborated. Honest scope note: XBRL CompanyFacts thins out
pre-2009, so early quarters are feature-poor while contributing full
LABEL value; the gain concentrates in 2009-2012 features + all-era
events. Catalyst features (S1 strategic-review, S2 trial outcomes)
queued to ride the expanded panel.

**TEXT VERDICT, ROUND 2 (v0.55): converged reader DROPS to 0.061.**
The 0.067 was an accident of undertraining acting as regularization —
the converged low-shrinkage reader overfits vocabulary on ~550 positive
examples. Final legitimate knob: a proper shrinkage sweep (alpha 1e-5 →
1e-2) via `develop textsweep`, dev-window only. Pre-registered decision:
best sweep value clearly above 0.067 → tune with text + disclosed second
holdout; sweep topping out ≈0.062–0.067 → text ruled noise-level, gen-2
CLOSED, gen-1 holdout (2.1×) stands as the paper's final model number,
and the free-data ceiling (~2×) becomes an empirically established
finding across five feature families (fundamentals, engineered,
activist, wave/TA, text).

**TEXT ROUND 1 (v0.54).** Corpus
complete at 8,711 CIK-year documents; 56% firm-quarter coverage.
GBM fund+eng+text: **0.067 AUC-PR (2.1× dev)** vs 0.062 without text —
the first improvement since the free-data plateau, direction consistent
with the takeover-text literature. Caveat found in the same run: the
text scorer hit its iteration cap without converging (undertrained), so
0.067 is a floor for the text contribution, not its measure. SGD budget
raised 15→80 iterations; re-run decides the converged number, then the
tuning grid runs WITH the text feature before any second holdout
decision.

**Text scorer shipped (v0.53).** Probe round 2:
0 unparsable, 20-F class confirmed working (AstraZeneca OK). The
fold-safe text scorer is live in `develop`: stateless hashing
vectorizer (no vocabulary crosses fold boundaries), per-origin
SGD-logistic on Item-1 text, out-of-fold score stacked as `_textScore`
into a third spec "fund+eng+text"; as-of correct (each quarter uses the
latest 10-K FILED on or before it, ≤450 days old); rows without a
document score neutral 0.5. Code path proven end-to-end on synthetic
docs in the container; text coverage percentage prints with each run.

**Gen-2 route settled: 10-K TEXT (v0.52).** Activist 13D features were
flat on the main machine (0.062 vs 0.061 plateau); CRSP declined by
operator; crsp-import retired. Fresh research identifies the one major
untried FREE lever with direct literature support: 10-K textual
disclosures — transformer and bank-merger studies find text
significantly improves out-of-sample takeover prediction jointly with
financials, with signal not fully in prices (Lohmeier 2023; Katsafados;
Hoberg-Phillips product-text line). This is also the never-executed
Phase D. `text-ingest [N]` shipped: fetches each member's annual
10-K/20-F Item-1 (Business) text into bronze/tenk_text, resume-safe
tranches, TOC-trap-aware extraction validated on synthetic and cached
docs. Next after ingest: fold-safe text scorer (hashed n-grams +
LASSO-logistic, out-of-fold score stacked as one GBM feature) — no
vocabulary fitting across fold boundaries.

**Generation-2 push opened (v0.51).** Two remaining data-side levers
(math side provably exhausted): (1) **CRSP via Stanford WRDS** — the
operator's institutional access unlocks survivorship-free delisted
prices, honestly restoring the price-feature family (realistic ceiling
moves toward 3–4×); operator to confirm access. (2) **Activist SC 13D
features, shipped**: premise probed on real cached data (13Ds appear
under the subject company's submissions), extraction cached to
gold/activist_13d.csv, two leak-free features (_act13D24m count,
_act13D12m flag) added to the engineered set. Protocol note, on record:
the 2023+ holdout was spent once for gen-1 (2.1×, pristine); if gen-2
beats gen-1 in development, its holdout evaluation is the second and
LAST access, disclosed as such in the paper — standard, documented
practice.

**gen-1 FINAL (v0.50).**

| Stage | Dev (pooled OOF) | Holdout 2023+ (one-shot) |
|---|---|---|
| logistic / fundamentals | 1.6× | — |
| GBM / fund+engineered | 1.9× | — |
| tuned GBM (d3, lr .03, leaf 25) | 2.13× (0.0674) | **2.1× (AUC-PR 0.081, ROC 0.720, n=11,678, pos=450)** |

Holdout confirms development (no overfitting signature). Round-2
verdict: wave/TA features and the ensemble did not beat the GBM —
plateau reached honestly at ~2.1×. Iteration CLOSED; the holdout was
spent once and the number is final. Improvement arc for the paper:
1.6× linear baseline → 2.1× via engineered fundamentals + gradient
boosting under purged walk-forward with single-shot holdout — a 31%
relative gain, leak-free. Remaining: GEN A-List head-to-head, results
assembly, freeze, draft.

**Development round 2 (v0.49).** Additions
from the imbalanced-tabular and takeover-forecasting literature: (1)
_wave — the M&A-wave clock (trailing-12m count of universe acquisition
announcements; other companies' public events, strictly past,
leak-free); (2) five therapeutic-area exposure flags built only from
trials started on or before each quarter (no lookahead); (3) an
ensemble row — rank-average of logistic + GBM, the forecast-combination
technique the takeover literature found beats single models. Rejected on
evidence: SMOTE-style resampling (comparisons favor boosting WITHOUT
resampling); deferred: focal/LDAM custom losses (real PR-AUC gains in
benchmarks but require LightGBM/XGBoost dependency — candidate if the
current round plateaus below target).

**Development round 1 (v0.48):** pooled OOF on purged walk-forward —
logistic/fundamentals 1.6×; logistic/engineered 1.6× (no gain); GBM/
fundamentals 1.7×; **GBM/fund+engineered 0.061 AUC-PR = 1.9× (best)**.
The nonlinear model exploits the engineered features; the linear one
cannot. `develop tune` shipped: 27-point GBM grid (depth × lr × leaf)
on the winning spec, dev-window only, best config persisted to
gold/best_config.json; `holdout tuned fund+engineered` consumes it for
the one-shot 2023+ final.

**Improvement protocol shipped (v0.47).** Research-anchored answer to
"randomize the test sets": plain shuffle-CV is invalid here (12-month
forward labels overlap adjacent quarters; shuffling leaks the future —
the de Prado purging literature exists precisely for this). Implemented
instead in `biointel/improve.py`: (1) PURGED WALK-FORWARD development —
origins 2016–2021, train up to each origin, purge the 4 overlapping
quarters, test the following year, pooled out-of-fold AUC-PR — run
entirely on pre-2023 data; (2) the 2023+ HOLDOUT is untouched during
iteration and evaluated exactly once via `holdout MODEL SPEC` when
iteration stops (anti-p-hacking discipline, on record); (3) engineered
leak-free fundamentals (cash deltas 1q/4q, trial-start momentum, R&D
intensity, company age, deal intensity, cross-sectional cash rank,
low-runway flag — own-past and same-quarter data only); (4) model class
upgrade: sklearn histogram gradient boosting beside the balanced
logistic. Commands: `develop` (iterate freely), `holdout` (once).
Container smoke passed (dev-scale data → INSUFFICIENT guards fire).
Dependency added: scikit-learn.

**FINAL RESULTS TABLE (v0.46).** The honest prediction result:

| Spec | AUC-PR | Lift | ROC | P@10 (mature q) |
|---|---|---|---|---|
| fundamentals (primary) | 0.064 | 1.6× | 0.674 | 0.00 |
| fundamentals-strict | 0.052 | 1.7× | 0.691 | 0.00 |
| (retracted: price-inclusive) | 0.257 | 6.2× | 0.915 | 0.70 |

The paper's four contributions, final: (1) open-data pipeline + 155
machine-corroborated acquisition labels with per-signal audit trail;
(2) FDA-action event study, N=1,350, literature-consistent asymmetry;
(3) fundamentals-only takeover prediction at a modest, stable, honest
1.6–1.7× lift — consistent with the literature's limited-precision
verdict; (4) the leak dissection: free price data's delisting-driven
missingness manufactures a fake 6.2×/0.985-ROC result — demonstrated,
diagnosed, and retracted by the project's own robustness
instrumentation. Remaining: GEN A-List head-to-head (fundamentals
model), results assembly, freeze, write-up.

**LEAK CONFIRMED (v0.45).**
Coverage diagnostic: positive firm-quarters 2.1% price-covered vs 35.3%
for negatives — missingness ≈ label. The 6.2×/0.70 result was
substantially an artifact of survivorship in the free price source
(Yahoo drops delisted tickers), and covered-only cannot rescue it (8
train positives). Retractions and survivals, plainly: RETRACTED as
claims — baseline/strict/split rows of the v0.43 table (all include
price-derived features). SURVIVES — the event study (price-covered
events only, disclosed selection), the label set, the universe, the
pipeline, and the leak dissection itself, which becomes a headline
finding: open-data price features manufacture spectacular fake
takeover-prediction performance via delisting-driven missingness,
demonstrated and diagnosed. NEW PRIMARY SPEC — "fundamentals-only"
(cash, revenue, runway, trials, FDA, relationships; no price-derived
features, leak-free by construction) + its strict-labels variant, both
added to the suite. Whatever those rows report is the paper's honest
prediction result.

**LEAKAGE SUSPICION (v0.44).** The price-only
scenario returned ROC 0.985 — HIGHER than the full model — with P@10
0.10: the signature of an artifact, not signal. Suspected channel:
price-data MISSINGNESS. Delisted (acquired) companies have unreliable
retrospective price coverage; missing values encode as zeros; "no price
data" may itself predict "acquired," leaking today's data availability
backward into the panel (risk R3 materialized as leakage). Two
instruments added to `robust`: (1) a coverage diagnostic printing price
coverage by label class — a large gap confirms the leak; (2) a
"covered-only" scenario running the full model exclusively on
price-covered firm-quarters, where missingness cannot discriminate. If
covered-only holds near 6×, the headline is real; if it collapses, the
honest headline becomes the covered-only number. Reported either way.

**ROBUSTNESS TABLE (v0.43):**

| Scenario | AUC-PR | Lift | ROC | P@10 |
|---|---|---|---|---|
| baseline | 0.257 | 6.2× | 0.915 | 0.70 |
| strict-labels (corroborated only) | 0.201 | 6.4× | 0.910 | 0.70 |
| split-2019 | 0.197 | 5.3× | 0.896 | 0.80 |
| split-2020 | 0.221 | 5.8× | 0.904 | 0.70 |
| no-price | 0.063 | 1.5× | 0.668 | 0.00 |

Verdict: the headline survives label-quality and split-choice attacks
(R1, R4 closed). The no-price collapse is a substantive FINDING, not a
footnote: power concentrates in market-derived features (drawdown,
market cap), consistent with the coefficient table — prices aggregate
much of the takeover story. The paper's sharpest question is therefore
incremental value: baseline minus a PRICE-ONLY model = what the
clinical/regulatory/relationship features add on top of the market's own
signal. Sixth scenario ("price-only": mcap, drawdown, CAR, drift)
added; interpretation frame: if baseline > price-only, fundamentals add
measurable lift; if equal, the honest conclusion is that open
fundamental data mostly recovers what prices already encode — publishable
either way, and squarely in the Powell tradition of separating
predictability from profitability.

**Wiki round + robustness suite shipped (v0.42).** qa-wiki confirmed
26 of 158 residue rows (third source); machine-verified events now 155
(129 EDGAR-strong + 26 wiki). `robust` command runs five scenarios in
one pass — baseline / strict-labels (corroborated events only) /
split-2019 / split-2020 / no-price — each reporting AUC-PR, lift, ROC,
and mature-quarter P@10 to `gold/robustness_report.txt`. The strict
scenario is what makes the 115 uncorroborated rows non-gating: they are
excluded from that result, not hand-verified. Container smoke passed
(insufficient-data guards fire correctly on dev-scale data).

**Corroboration round 2 (v0.41).** Round 2:
129 strong / 27 weak / 131 none; worklist 127. Per the standing
principle that repetitive human work is assigned only when automation is
impossible — and it is not — two additions remove the manual task: (1)
`qa-wiki` corroborates the EDGAR-less residue against Wikipedia's public
API (target page must name the acquirer in acquisition context; a third
independent source, cached, per-row graceful); endpoint validated on
first main-machine run. (2) The scientific dissolution: the robustness
suite's strict run trains on machine-corroborated labels ONLY, so
uncorroborated rows are excluded rather than verified — nothing gates on
a human pass. Any remaining human role shrinks to the small random audit
sample referees expect, which is performed by the assistant with web
checks, not assigned to the operator.

**Corroboration round 1 (v0.40): 110 strong / 21 weak / 156 none;
human worklist 176 → 131.** The none-list decomposed into two fixable
classes and a genuine residue: (a) resolution misses on buyers who ARE
EDGAR filers (short names: Alcon, Mereo; foreign suffixes: Novo Nordisk
A/S, Grifols S.A.; suffix variants: Ligand, Halozyme) — resolver
loosened with bidirectional canon-prefix and two-token matching; (b)
subsidiary shells of EDGAR parents (Zeneca→AstraZeneca, Wyeth→Pfizer,
Allergan Holdco→Allergan) — PARENT_MAP added; (c) genuinely
no-EDGAR acquirers (Lundbeck, Chiesi, Nichi-Iko, PE firms, Concentra) —
correctly human. Re-run retries only unresolved rows (strong/weak kept).

**QA automation shipped (v0.39): `qa-corroborate`.** For every event
with a named acquirer, the acquirer's OWN filing trail is checked as an
independent record: an 8-K/425/S-4 within ±45 days of the agreement date
whose text names the target = "strong" corroboration (two independent
SEC record trails agreeing). Strong rows are pre-verdicted
"ok(machine-corroborated)" in the worklist; the human residue shrinks to
weak/none rows — typically private or foreign acquirers with no EDGAR
presence, which genuinely require a human. Testing surfaced and fixed a
real coverage bug: heavy filers exhaust the submissions "recent" window
(~1,000 filings) by ~2018, so archive pages are now paginated in until
coverage reaches the anchor date.

**ROBUSTNESS RESULT (v0.38): the headline survives.** With true
agreement dates (281 extracted) replacing proxy-filing dates, and again
under aggressive announce−90d censoring:

| Run | AUC-PR (test) | Lift | ROC | P@10 | P@25 |
|---|---|---|---|---|---|
| Corrected dates | 0.257 | 6.2× | 0.915 | 0.70 | 0.64 |
| Censor −90d | 0.204 | **6.7×** | 0.915 | 0.70 | 0.60 |

Reading: the proxy-lag (R7) was inflating precision@10 by exactly one
hit (0.80 → 0.70 corrected); under −90d censoring the lift RISES to
6.7× and precision@10 holds at 0.70 — the stable, quotable pair is
**~6.2–6.7× AUC-PR lift and 0.70 precision@10**. Seagen now correctly
flags inside its label window after date correction. QA machine-half
complete: 281 agreement dates, 347 events classed, 176-row human
worklist emitted (60 stratified sample + 129 flagged incl. Keenova,
Endo-class rows). R7 closed; R1/R2 close with the human worklist;
remaining robustness: rolling splits, verified-only labels, no-price
feature set, then GEN A-List benchmark and results assembly.

**Label QA pass shipped (v0.37).** `qa` command: re-opens each filled
event's cached proxy and extracts (a) the TRUE merger-agreement date via
"Agreement and Plan of Merger ... dated as of [date]" — validated 76/87
on real cached merger documents — replacing the lagging proxy-filing
date in the label panel (kills R7 at the source), and (b) an EventClass
(acquisition / spac / bankruptcy / going-private / reverse-merger) from
document language. Emits `gold/qa_worklist.csv`: a 60-event stratified
human-verification sample plus every structurally flagged row (blank
acquirer, non-acquisition class, proxy-lag > 45 days), each with a
HumanVerdict column. `merged_events` now prefers AgreementDate; `fit`
gains an optional censor-lead argument (`fit 90`) for the announce−90d
sensitivity.

**HEADLINE RESULT (v0.36).**
Censored risk set, mature-quarter evaluation, vectorized fit:

| Metric | Value |
|---|---|
| Test AUC-PR | **0.257** vs 0.0414 base = **6.2× lift** |
| Test AUC-ROC | 0.918 |
| precision@10, latest mature quarter (2025-06-30) | **0.80** |
| precision@25 | 0.68 |

Censoring RAISED the honest numbers (5.7×→6.2×) — the pending-deal
quarters had been polluting the negative class. Top-20 test ranking:
8 flagged acquired, plus Seagen/Mirati/Intra-Cellular/Apellis ranked
1–24 months before their announcements, just outside label windows.
Dominant coefficients tell an interpretable story: high 52-week
drawdown, smaller market cap, more cash, Phase-3 depth.

**One honest caveat carried to robustness (R7):** announce dates are
proxy-filing dates, which LAG press announcements — so a deal announced
by press just before a quarter-end but proxied after it leaves that
quarter uncensored with takeover-premium features and a positive label,
flattering precision@k. Scheduled sensitivity: censor at announce−90d;
QA pass will also pull true agreement dates from the proxy texts already
cached. Also QA-flagged from the top-20: "Keenova Therapeutics"
(unrecognized name) and Endo (bankruptcy, not acquisition — EventClass
work).

**Fit crash diagnosed and fixed (v0.35).** Checkpoint harness localized
the 0xC0000409 to the pure-Python gradient loop dying mid-iteration on
Windows/CPython 3.13 with the full 35k-row panel — an interpreter-level
fault, not a data or logic error (loading, censoring, and
standardization all passed checkpoints). Fix: training and scoring
vectorized with numpy (~100× faster, no interpreter-bound hot loop);
pure-Python path retained as fallback. Full code path re-verified in
0.25s on the smoke panel. One new dependency, documented: numpy.

**FULL-UNIVERSE REBUILD COMPLETE (v0.34) — the headline result
exists.** Panel: 78,936 firm-quarters, 1,390 positives (1.76% base).
Events: 473 (350 target-role). Event study at scale: 1,350 events,
robust asymmetry (approvals +0.31; rejections −7.1 / −21.1 at N=53/36).
Fitted model, time-split: **test AUC-PR 0.193 vs 0.0338 base rate =
5.7× lift; AUC-ROC 0.907.** Top-20 test ranking is denser with real
targets than its flags show — Alexion, Biohaven, Seagen, Horizon,
Mirati, Zogenix, Intra-Cellular (ranked 2 years pre-announcement),
Apellis (2.5 years pre) sit just outside label windows. Snapshot frozen
(12,692-fetch manifest, data/frozen/20260824).

**Two methodology fixes shipped (v0.34), weights untouched:** (1)
risk-set censoring — firm-quarters at/after a company's own announcement
are pending-deal states, now excluded (post-announce Seagen/Horizon
quarters were scoring 0.90+); (2) precision@k now measured at the latest
MATURE quarter (12-month label window fully elapsed) — the 0.00 at
2026-06-30 was structurally meaningless with only two months of window
elapsed. Explicit lift line added. Re-run `fit` only.

**INGEST COMPLETE (v0.33): all 1,194 universe members in, zero layer
errors across ~4,800 pulls.** Data intake is finished; everything from
here is computation on local data.

**Shipped same version:** (1) `labels` now consumes the universe harvest
— auto-filled/verified harvest events become target events for their
ingested IIDs, deduped by (IID, announce-year) with verified rows taking
precedence; container-tested end-to-end. (2) `fit` — the fitted logistic
model (pure stdlib: no new dependencies), time-split at 2021-12-31,
class-weighted loss, AUC-PR + AUC-ROC + precision@k at the true base
rate, full standardized coefficients for interpretability, top-20
test-period ranking with acquired-flag, report to `gold/fit_report.txt`
and scores to `gold/fit_scores.csv`. Insufficient-label guard verified;
full path verified on a synthetic smoke panel (honest near-base-rate
AUC-PR on random labels = no leakage). The checklist `predict` remains
as the baseline comparator for the paper.

**Post-ingest rebuild order:** partners → relationships → labels →
study-all → features → fit → freeze. `study-all` and `features` are the
long ones (large first-run price fetches; re-running resumes cheaply
from cache). `cparty-all` over the full universe is OPTIONAL enrichment
(deal-relationship features for new members) and not required for the
first fitted result.

**Ingest progress (v0.32): 636/1,194 members in (feed-junk cleanup
removed 14 universe rows and 2 registry rows), 558 remaining, still zero
layer errors.** The acquisition-target histories central to Phase M keep
arriving: Loxo, Juno, Kite, Mirati, MyoKardia, Dermira, Ignyta,
Intra-Cellular, Horizon, TESARO, GW Pharma, Principia, Turning Point,
Dicerna, ChemoCentryx, Reata, Seagen...

**Ingest progress (v0.31): 300/1,208 members in, zero layer errors
across 1,200 pulls.** The acquired-company histories central to the
label set are flowing in (Celgene, Alexion, Seagen, Allergan,
Pharmacyclics, Medivation, Onyx, Salix, Shire, InterMune, Acceleron...).
One defect caught in the stream: the EDGAR feed's own header leaked
through the parser as a pseudo-company ("Company Search Feed", ingested
twice). Filter extended at parse time; `cleanup_feed_junk.py` removes
the existing junk rows from companies.csv and universe.csv (IID gaps
left behind are harmless).

**`ingest` shipped (v0.30):** walks the universe in resume-safe tranches
— per member: registry row, financials (CompanyFacts), trials (CT.gov),
FDA events (name variants), deal filings. Prices stay lazy (fetched by
study/features). Delisted members without tickers ingest fine; their
labels need no prices. End-to-end tested through the real code path
(dev-set member removed and re-ingested from cache: all four layers ok,
137 financial periods restored).

**Spot-check verdict (v0.29): auto-fill methodology TRUSTED at ~92%.**
25-row random sample against known deal history: 21 exactly right
(Pharmacyclics→AbbVie, Medivation→Pfizer, Receptos→Celgene,
Bioverativ→Sanofi, Viela→Horizon, Longboard→Lundbeck, Hospira→Pfizer,
EQRx→Revolution, Kinnate→XOMA, Prosensa→BioMarin, Jounce→Concentra...),
2 family-correct entity names (ZS Pharma's "Zeneca Inc" = AstraZeneca US
entity; "Allergan Holdco US" = Allergan), and the post-cutoff
Apellis→Biogen fill independently web-verified ($41.00/share, ~$5.6B,
announced 2026-03-31, completed 2026-05-14 per Biogen's own 8-Ks).
Two systematic failure classes: (a) "HoldCo" placeholder extractions —
fixed: placeholder terms rejected at extraction and already-filled
placeholders cleared for re-extraction on rerun; (b) contested deals
where the extracted bidder lost (Allergan 2014: Valeant's failed hostile
bid vs actual acquirer Actavis) — flagged as a MANUAL class for the
verification pass, alongside the 56 blanks. Announce-date convention
noted: harvest dates are proxy-filing dates, lagging press announcements
by days-to-weeks (Apellis: 2026-04-14 vs 2026-03-31); acceptable and
documented for the panel's quarterly resolution.

**verify-fill main-machine run (v0.28): 291 of 347 acquirers
auto-filled (84%) from 400 proxy documents; 56 remain for manual
resolution.** Next gate before these become training labels: a random
spot-check of the auto-fills — systematic extraction junk must be ruled
out on a sample before the fitted model trains on the column.

**`verify-fill` shipped (v0.27):** for each confidence ≥ 2 event, fetch
its merger proxy from EDGAR (accession + primaryDocument from cached
submissions) and auto-extract the ACQUIRER from the document's own
language ("wholly owned subsidiary of X", "acquired by X", "merger with
X", "by and among X"), with the shell-sub and financing-agent filters
applied. Extraction validated on the real Vertex/Crinetics proxy
language (returns "Vertex Pharmaceuticals Incorporated" exactly, after a
sentence-tail-bleed fix). Rows fill as Verified="auto"; promotion to
"yes" remains a human spot-check decision. ~350 document fetches on
first run, bronze-cached thereafter.

**Universe-wide label harvest (`harvest`) shipped v0.26:**
proposes acquisition events for all 1,208 members from the submissions
records already cached during screening — proxy episodes + Form 25 near
+ filing cessation, confidence 1–3, survivors-with-proxies (share-issuing
acquirers) skipped. Zero ingest required. Container test on the dev set
correctly rediscovered Immunovant's 2019 SPAC combination (conf 2) and
the live Crinetics merger (conf 1, too recent to score cessation).
Output `ma_events_universe.csv` is the VERIFICATION WORKLIST: each
high-confidence row gets its acquirer confirmed against public deal
records, then moves into `ma_events_verified.csv`.

**Second full build (v0.25, superseded): 1,347 members / 487
delisted — over-admitted.** The was-listed proof accepted Form 15,
which OTC companies file at deregistration without ever being
exchange-listed; the 645→1,347 jump includes that class. Refined:
admission-by-history requires the Form 25 family only (the
exchange-delisting form, definitionally exchange-specific); Form 15
remains supporting evidence for the Delisted flag. Expected effect:
membership settles between 645 and 1,347, delisted count becomes the
exchange-true set — the honest denominator for the label harvest.

**First full build (v0.24): 645 members, 2,394 screened, 38/40 dev set
— but 0 delisted, which is a defect, not a finding.** Root cause: EDGAR
blanks the `exchanges` field after delisting, so the NYSE/Nasdaq screen
excluded exactly the acquired companies the expansion exists to capture
— survivorship reintroduced by the inclusion filter. Fix: Form 25/15
evidence is itself proof of exchange listing (Form 25 IS the
exchange-delisting form), so admission is now listed-now OR
was-listed-per-Form-25/15; stale threshold tightened to 400 days. The
two dev-set misses are SIC-rule speaking (research/software-classified
companies), recorded, not patched. Re-run is cheap: all 2,394
submissions are bronze-cached.

**Probe round 2 (v0.23): PARSE OK.** 100 companies parsed from page 1
of the real feed (inline names sparse as expected; submissions fallback
supplies them at build time). The full `universe` build is unlocked and
running on the main machine; results pending.

**Probe round 1 (v0.22):** the real browse-edgar page revealed Perl
serialization artifacts — entry title and company-info name ATTRIBUTES
contain "ARRAY(0x...)" junk; the data lives in child elements
(`<cik>`, `<conformed-name>`), and the payload is ISO-8859-1 and not
reliably well-formed. Parser rewritten per-entry against the pasted real
structure; names missing inline are filled from the submissions record
during build. Probe-gate discipline worked exactly as designed: zero
wasted full-build attempts.

# PART 6 — DEAD ENDS

| Approach | Why |
|----------|-----|
| Alpha Vantage `TIME_SERIES_DAILY_ADJUSTED` | premium only |
| Excel Stocks data type | poor small-cap and delisted coverage, no CIK |
| Stooq CSV | access denied |
| EODHD free tier | past year only |
| SEC full-text search as primary event source | keyword search, not a structured field |
| Drugs@FDA for rejections | confirmed zero `CR` records |
| GLEIF LEI hierarchy | rejected |
| Regex-only counterparty extraction | ~50% junk, see 3.1 |
| spaCy NER on 8-K narrative | wrong document; parses announcements, not agreements |

---

# PART 7 — HONEST ASSESSMENT

**What went well:** every layer with a structured source. SEC identity,
openFDA, ClinicalTrials.gov, XBRL financials, Yahoo prices, the derived
calendar and collaboration network. These went in with one or two
iterations and are reliable.

**What went badly:** extracting names from legal prose. Four cycles, no
working result, each diagnosed only after you ran it.

**The distinction is not difficulty.** For structured APIs the schema can be
reasoned about correctly without seeing output. For prose extraction the
output must be inspected, and this environment cannot reach the endpoints or
read the fetched documents. The result was propose-run-fail-patch, which
does not converge and consumed disproportionate time. This should have been
stated before the second attempt.

**Current state is usable.** Eight of eleven scope components have real data
behind them. The gap is the relationship layer, half-built: trial
collaborations work, deal counterparties do not.

---

## Changelog

| 1.09 | 2026-09-02 | Gate L3 DONE: analyser.py (L3-a2); span-grounded propose/judge/consume with conflict-hold and verdict gating; TEM-PSNL yardstick 20/32 = 0.625 raw, 8 rows consumed (two facts beyond the seed); ten-deal batch, ~100 docs, 0 fetch failures, 100% span-verified, five-deal spot-check 26/57 = 0.456 raw; a3 agenda documented. |
| 1.08 | 2026-09-02 | Gate 2.9′ DONE: widening rule of record; add --stub for private parties; TEM IID 1379, PSNL IID 1380; ma_events index row with deal_id TEM-PSNL-20260720 (manual overrides applied at labels rebuild; dropped-optional-column and list/tuple defects fixed with a round-trip test); measured effect nil (1,357→1,359 ranked, pool 862→863, hit@10 0.27 / hit@25 0.39 unchanged); diagnostics-mine 0-hits finding; live baselines re-hashed explicitly. |
| 1.07 | 2026-09-01 | Gate 1.5c DONE: r10 rules + write-realized/write-delays from the ledger; fresh-sample precision 56/60 = 0.933 [0.841, 0.974]; recall stable 0.846/0.915 (stopping rule satisfied); 2,053 realized rows (outcome states mapped conservatively), 9 delay rows, 1 withdrawn guidance superseded; reverse benchmark count fixed to forward rows only; r11 candidates documented. |
| 1.06 | 2026-09-01 | Gate 1.5b-eval DONE: candidate_reviews (0.10, 49 declared); cached re-runs; per-version precision with Wilson CI; explain --live; stale-row retirement; encoding-safe console. r9 of record: precision 56/60 = 0.933 [0.841, 0.974]; recall 0.846 raw / 0.915 members; ten misses classified (5 non-member, 5 press-release-only, 0 extraction failures); 5 true finds vs the benchmark; r10 rules deferred to 1.5c. |
| 1.05 | 2026-09-01 | Gate 1.5b DONE: SEC EDGAR full-text miner (mine-pdufa, 66th command) with `mined_candidates` ledger (SCHEMA_VERSION 0.9, 48 declared): 2,653 documents captured, 14,002 windows ledgered (r6), 701 forward events tier B; precision 8/10 judged sample; recall 0.846 vs FDA Tracker snapshot (benchmark only per their terms); fetch backoff and periodic flush after an SEC 503/timeout abort; research-based design (TimeML, ConText, Dolphin et al. 2026); r7 rules ship, re-measured at 1.5c; pytest 140; validate 39/0/8/1; thirteen fingerprints MATCH; runbook docs/20260901_v2_GATE15B_INSTALL.md. |
| 1.04 | 2026-08-31 | Gate 1.5a DONE: forward FDA calendar — events_table optional forward columns (SCHEMA_VERSION 0.8); calendar-forward (65th command) trials writer 16,112 rows idempotent with supersession; AdCom writer rebuilt on the calendar's JSON endpoint after the page proved a client-side shell (194 records, 2 upcoming, 4 rows, dated snapshot captured); events-migrate preserves forward rows; L1 manifest self-listing defect fixed; testing standard: real-capture fixtures; regression runtime of record ~3–4 min; events_table 20,398; validate 38/0/8/1; pytest 122; thirteen fingerprints MATCH, PROBLEMS 0; runbook docs/20260831_v2_GATE15A_INSTALL.md. |
| 1.03 | 2026-08-31 | Gate 2.10 DONE: manual layer (SCHEMA_VERSION 0.7; manual trio live; 64th command add-entity/add-attribute/add-note/list/validate/export/load; schema-validated targets; visible precedence via merged_rows, first consumer L3) under the storage ruling — DB sole store, no row content in git, snapshot sole reconciliation; export/load rebuild path for all 11 hand tables (17 rows/6 tables round trip, run-recorded); dossier SEED marked LEGACY; first manual attribute ma_events.deal_id=TEM-PSNL-20260720; validate 38/0/8/1 of 47; pytest 103; thirteen fingerprints MATCH, PROBLEMS 0; runbook docs/20260831_v1_GATE210_INSTALL.md. |
| 1.02 | 2026-08-31 | Gate L2 DONE: dossier schema + span-verified seed — 8 tables live (SCHEMA_VERSION 0.6, 47 declared), ASPECTS enum, v4 edge names, ma_events optional deal_id; dossier-seed (63rd command) propose→report→load with accession→capture doc_id resolution and in-capture span verification; 16/16 rows loaded across 5 tables (run 20260831T203033-dossier); 3 assignments corrected and 4 rows held out pending sources on report evidence; MEMBERSHIP_MATCHES 0 → 2.9′ precedes L3; validate 35/0/8/4 of 47; pytest 95; thirteen fingerprints MATCH, PROBLEMS 0; runbook docs/20260831_v1_GATEL2_INSTALL.md. |
| 1.01 | 2026-08-31 | Decision: L2 seeds the Tempus–Personalis dossier through a committed hand-curated seed (verified-overlay pattern, P19 doc_id+span per field); gate 2.10 pulled forward to immediately after L2 (order of record L1 → 1.4 → L2 → 2.10 → 1.5 → L3 → L4) so the manual layer exists before L3's review queue produces the first corrections. Implementation Plan v14; no code or data change. |
| 1.00 | 2026-08-31 | Gate 1.4 DONE: event table + forward FDA calendar view — EVENT_TABLE_COLS gains `event_date` (approved amendment; scheduled_date reserved for goal dates); seven v4 event classes declared (vocabulary complete from birth); `events-migrate` copied 4,282/4,282 `events` rows with deterministic ids and a ledger run; `calendar IID` a view over trials + events_table, forward rows 0 until 1.5/1.6; pytest 85; ruff clean on gate files; validate 27/0/8/4 (39 declared); thirteen fingerprints MATCH, PROBLEMS 0; runbook docs/20260831_v1_GATE14_INSTALL.md. |
| 0.99 | 2026-08-31 | Gate L1 DONE: research library / file room live — schema references/captures/reference_links; library.py + collectors (manual, folder, pipeline, zotero); 733 filings indexed with CIK links; commands add/import/import-zotero/index/find/show/open/list/view/site/manifest/merge/verify/dedupe/retire-capture; DONE 2026-08-31 (pytest 76; ruff clean on gate files; index 733 refs/733 caps idempotent, 733 CIK links after v002 meta-name fix; URL add, file add, no-fetch, retire-capture 1, dedupe 0; validate 26/0/8/5; manifest 735, verify 0; thirteen fingerprint MATCH, PROBLEMS 0; ledger 35 runs; runbook docs/20260831_v1_GATEL1_INSTALL.md) |
| 0.98 | 2026-08-31 | File-room design approved and written: Ontology v5 (§3.9 rewritten; §8 Q8 marked answered; §7 rows AI-over-store, Zotero-as-reader, video_dl); Implementation Plan v11 (L1 row rewritten; §4 deferred items). Handoff v17, README. No code or data change. |
| 0.97 | 2026-08-31 | P19 Evidence appended (Design Principles v5). Decision: sequencing of the dossier track against Phase 1 — L1 → 1.4 → L2 → 1.5 → L3 → L4, with 1.6, 1.7 and 2.9′ placed as they fall due; next gate L1. Implementation Plan v10 §3, handoff v16, README. No code or data change. |
| 0.96 | 2026-08-31 | Diagrams: `20260831_v2_System_Diagram_TARGET_STATE.md` (library, dossier tables, new attributes and event classes, deal analyser, aspect-match, forward test; supersedes the v1 .md, v1 .png/.svg kept as the pre-v4 poster) and `20260831_v1_Research_Process_Diagram.md` (analyse company → ontology → matchmaking → historical analysis, with the Tempus–Personalis timeline). Handoff v15, README. No code or data change. |
| 0.95 | 2026-08-31 | Design: deal dossiers on a research library (Ontology v4 §3.9–§3.10, §5.5–§5.7, §7; Implementation Plan v9 rows L1–L4, 2.9′); Tempus AI deal record documented as the worked example; Ontology §8 Q5 marked answered, Q8–Q10 added; sequencing against Phase 1 pending. Handoff v14, README. No code or data change; fingerprints untouched. |
| 0.94 | 2026-08-31 | Decision: data-snapshot policy option A — Jason's 2026-08-29 data frozen as the snapshot of record (`data\snapshots\20260831\biointel.duckdb`, 95,170,560 bytes, SHA-256 B93A833BE466…, manifest 12,053 fetches, no credential); freeze as it stood; USB hand-over to Harrison after the merge; Harrison's results stay historical-file rows. Implementation Plan v8, handoff v13, README. No code or data change; fingerprints untouched. |
| 0.93 | 2026-08-31 | DOC gate: PART 0 regenerated in full (layout, workflow, codebase map, 61 commands, numbers of record with two-snapshot provenance from the ledger, rules, historical decisions, gate record, open queue); System Diagram v2 (current state). |
| 0.92 | 2026-08-31 | Gate 0.4 DONE (Phase 0 complete): models/ registry + enforcing harness, run_type, models/run commands (61), 65 tests, fingerprints reproduced; model naming by question, M1/M2 retired. Implementation Plan v7, handoff v12. |
| 0.91 | 2026-08-30 | Gate 0.3 DONE: results.py run ledger (4 tables), render-from-record for 7 reports + predict, report/ledger-seed commands (59), legacy rows seeded with provenance, ledger.csv export, 58 tests; thirteen fingerprints reproduced twice (after split, after re-render). Implementation Plan v6, handoff v11. |
| 0.90 | 2026-08-30 | Gate 0.2 DONE: DuckDB store layer (store.py), migrate command, 57 commands, exports/snapshots folders, CSV folders frozen for legacy, thirteen fingerprints reproduced, 46 tests; P18 (Design Principles v4); Implementation Plan v5; handoff v10. |
| 0.89 | 2026-08-30 | Decisions: P7 legacy amendment (legacy register: baselines.py, improve.holdout, fit.fit), P16 two stores (bronze files + one DuckDB file, exports, snapshots; no MLflow, no SQLite), P17 ledger in MLflow structure; Phase 0 reordered (0.2 storage, 0.3 reporting, 0.4 framework); regression baseline extended to thirteen files. Design Principles v3, Implementation Plan v4, handoff v9. |
| 0.88 | 2026-08-30 | Gate 0.1 DONE: schema.py + validate (56 commands), config.py de-duplicated with guard test, 30 unit tests added; first validate run recorded in 0.8a; Implementation Plan v3, handoff v8. |
| 0.87 | 2026-08-30 | Implementation Plan v2: ontology/product/scanning roadmaps cross-referenced to gates; deferred gates M1-G/H/I added. |
| 0.86 | 2026-08-30 | Implementation plan with gate ledger and standing procedure; target-state system diagram (PNG/SVG/Mermaid); handoff v7. |
| 0.85 | 2026-08-30 | Model 4 Horizon Scanning requirements written; implementation gameplan (Phases 0–3) recorded. |
| 0.84 | 2026-08-30 | Model 2 requirements written (FDA Catalyst Product Design v1); ontology v3 (global universe, stubs, price-action attributes, calendar sources of record, manual notes, benchmarks, Model 4 Horizon Scanning); design principles v2 (P13–P15); research note v2. |
| 0.83 | 2026-08-30 | FDA catalyst research note added (docs/20260830_v1_FDA_Catalyst_Research.md); ontology design v2 adds the shared Regulatory-event extension (§3.6); open queue 0.9 item 3a; README links it. |
| 0.82 | 2026-08-30 | PART 0 regenerated for the refactored tree (src layout, 55 commands, .env credentials, pyproject); refactor record 0.8 and open queue 0.9 added; design principles and ontology/matching design documents referenced. Ledger 0.5 and decision 0.7 carried verbatim; MASS-exact status discrepancy flagged in 0.9. |

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-07-24 | Requirements and gap register |
| 0.2 | 2026-08-10 | Output narrowed to distressed-asset screen |
| 0.3 | 2026-08-17 | Consolidated; Excel to Python migration complete |
| 0.4 | 2026-08-18 | Narrowing withdrawn; full scope restored; four-phase pipeline |
| 0.5 | 2026-08-23 | Trials, financials, collaborations, deal filings all working. Counterparty extraction failed across three attempts and one buggy diagnostic; recorded as blocked with the requirement to resume. Honest assessment added. |
| 0.81 | 2026-08-26 | ADOPTION SUSPENDED -- defect self-caught before deployment: degenerate-acquirer rows (global-max diagonal) scored all-zero and the tie rule granted them rank 1, potentially inflating MASS-exact's 0.318 only. Fixed with midpoint tie-ranking for BOTH metrics + a constructed degeneracy test (now 0.0 HR@5 on the degenerate case). 0.318 quarantined; incumbent remains engine of record; predict()'s exact fit wired but not of record until re-adoption under the unchanged pre-registered rule. **Actions: extract zip, re-run `python cli.py pairs-exact`, paste the block -- this corrected number decides adoption.** |
| 0.80 | 2026-08-26 | Operator directed continued improvement; option 1 (Sapling-exact) shipped. Formula taken verbatim from the PLOS One 2026 paper (Eqs 6-10: sqrt-ubiquity-weighted scalar products, empirical-maxima continuous Sapling with diagonal-inclusive maxima, norm-ratio size asymmetry). `pairs-exact` runs MASS-exact vs the incumbent MASS-inspired engine paired (same events, shared samples). Formula hand-checked against a manual Eq7-9 computation; guard fires for the global-max firm row (degenerate denominator). PRE-REGISTERED RULE: MASS-exact ships only if HR@5 beats the incumbent by >2x pooled repeat std; else incumbent stands. **Actions: run `python cli.py pairs-exact`, paste the block.** |
| 0.79 | 2026-08-26 | TARGETS VERDICT (rule applied): trials 0.206 vs targets 0.120 vs fused 0.205 on 67 paired events -- targets rejected; fused wash shows trials subsume mechanism info. Banked as the second pre-registered null; substrate hierarchy diseases > mechanisms > patents is a paper finding engaging both the MASS line and the Cunningham/Ederer/Ma (JPE 2021) MoA-overlap definition. ChEMBL ingest landed: 7,561 mechanisms, 779 firms, 18,950 firm-target rows. Substrate question CLOSED three ways. Open: operator decision -- next option from the board (Sapling-exact, LightGCN, Purple Book, 13F, Form 4, S1 scanner, short interest, OpenAlex, CMS, 24m) or assembly -> freeze -> draft. |
| 0.78 | 2026-08-26 | Ingest runtime bug caught on operator machine: 44,764 unique drug-name strings made per-name lookups a 12h+ job (my 1h estimate wrong by an order of magnitude, on record). chembl-ingest rewritten BULK-INVERTED: paginate the full mechanism table (~10 pages), batch-fetch mechanism-bearing molecules' synonyms + targets via /set/ (~150 calls total), match locally under the same exact normalization -- minutes, cached, resumable. Mock-tested through the real path incl. pagination and batching. Probe already passed live on the operator machine (dupilumab -> IL-4R alpha). **Actions: Ctrl+C the old run if still going; extract zip; re-run `python cli.py chembl-ingest` (minutes now), paste coverage line; then `python cli.py pairs-substrate targets`, paste the block.** |
| 0.77 | 2026-08-26 | 30GB dump route RETIRED on operator pushback -- chembl.py rewritten to the ChEMBL web-services API: per-name iexact synonym lookups (no fuzzy), bronze-cached so interrupted runs resume, ~zero disk, roughly an hour first run. Probe = one live dupilumab->IL-4Ralpha chain. Offline-tested via mocked API through the real code path (probe, ingest, FirstSeen precedence, unmatched-name skip). Pre-registered adoption rule of v0.76 unchanged. **Actions: run `python cli.py chembl-probe`, paste output; if PROBE OK run `python cli.py chembl-ingest` (long, resumable), paste the coverage summary; then `python cli.py pairs-substrate targets`, paste the block.** |
| 0.76 | 2026-08-26 | ChEMBL molecular-target substrate shipped (operator-approved run): open-access SQLite dump route, probe-gated (`chembl-probe` finds the current tarball in the EBI listing and verifies gzip magic; `chembl-ingest` = resume-safe ~4.5GB download + ~25GB extract, NEEDS ~30GB FREE DISK, then exact-normalized synonym matching firm->drug->mechanism->target into silver/drug_targets.csv with FirstSeen as-of dates). `pairs-substrate targets` runs the paired trials/targets/fused protocol. Offline-tested end-to-end incl. synonym-variant matching and FirstSeen precedence. PRE-REGISTERED RULE (same as patents): targets ships only if its MASS-inspired HR@5 beats trials by >2x pooled repeat std on the paired set; fused is the shippable form if targets win; else the null is reported. Rationale on record: targets attack the measured diversifying-deal blind spot at the mechanism layer. **Actions: run `python cli.py chembl-probe`, paste output; if PROBE OK, run `python cli.py chembl-ingest` (long: download+extract+build; re-run resumes), paste the coverage summary; then `python cli.py pairs-substrate targets`, paste the full block.** |
| 0.75 | 2026-08-26 | SUBSTRATE VERDICT (pre-registered rule applied): patents fail decisively (HR@5 0.055 vs trials 0.237 on 42 paired events, shared samples); fused within noise (0.220); TRIALS STANDS. Reported as a finding: the patent-portfolio substrate from the MASS literature does not transfer to development-stage biopharma, where trial portfolios carry the technology signal (patents solo-cover 74/181 events vs trials 130). v0.65 leftover closed: `predict` now ships the protocol-validated MASS-inspired trials engine (Fit = 100 x idf^2-TFIDF cosine x size damp; fixture-tested ordering) and adds AcqLOE1-3 columns: Orange Book protection-end urgency share per named acquirer (count-based proxy, labeled as untestable in the given-acquirer protocol -- acquirer-side constants cannot move target ranks). All committed improvement work is now DONE; remaining: results assembly -> GEN head-to-head (optional) -> freeze -> paper draft. **Actions: run `python cli.py predict`, paste the summary line + top 10 rows of gold\ma_predictions.csv.** |
| 0.74 | 2026-08-26 | Patent substrate LANDED on operator machine: 120,035 patent-CPC rows, 1,019 matched keys, 0 unmatched export rows (SQL/Python canon parity held on real data). `pairs-substrate` shipped: paired trials/patents/fused comparison under the field protocol -- common candidate pool per cutoff, negatives sampled once per (event,repeat) and shared across all six substrate x metric cells; path tested end-to-end on fixtures. PRE-REGISTRATION CLARIFIED BEFORE RESULTS: adoption test is the paired run itself -- a substrate ships only if its MASS-inspired HR@5 beats the trials MASS-inspired HR@5 on the same paired set by more than 2x the pooled repeat std; if patents win, FUSED is the shippable engine (patents-only cannot rank patent-less firms); otherwise trials stands and the null is reported. **Actions: run `python cli.py pairs-substrate` (expect tens of minutes: per-cutoff matrices x 6 cells), paste the full block.** |
| 0.73 | 2026-08-26 | Literature cross-check completed: the MASS line runs on PATSTAT+AMADEUS+Zephyr+Crunchbase (all commercial); free-public-data construction is a paper differentiator. Patent substrate ADOPTED SOURCE: Google Patents Public Datasets on BigQuery (IFI CLAIMS + Google, CC BY 4.0, continuously updated; sandbox = existing Google login, no credit card, 1TB/mo). patents-sql generates the query from local company names with canon() reproduced in SQL (parity-tested Python vs SQL normalization); patents-import consumes the console CSV export -> silver/patents.csv (IID, PatentId, grant/filing dates, CPCSubclass). Offline-tested end-to-end incl. IID-over-CIK precedence and header-echo abort. **Actions: run `python cli.py patents-sql`; open console.cloud.google.com/bigquery with your normal Google login; paste the contents of gold\patents_bigquery.sql; Run; Save results -> CSV (Drive if over 10 MB); download; drop the .csv into data\bronze\patents_bulk\; run `python cli.py patents-import`; paste both command outputs.** |
| 0.72 | 2026-08-26 | ODP API key path DROPPED (requires MFA + ID.me identity verification; operator declined -- correctly, the keyless route exists: ODP website data products download without a key). patents-ingest gains a local-files mode: three bulk zips placed in data\bronze\patents_bulk\ are consumed directly, version-suffixed names matched by stem, no probe needed since nothing is fetched. CLI-tested end-to-end on fixtures. **Actions: browser-download g_patent, g_assignee_disambiguated, g_cpc_current from https://data.uspto.gov/bulkdata/datasets/pvgpatdis into data\bronze\patents_bulk\ (several GB total), then run `python cli.py patents-ingest`, paste the summary.** |
| 0.71 | 2026-08-26 | Probe verdict: legacy S3 bulk host DEAD (403/XML); api.uspto.gov REACHABLE but key-gated (401). Last blocking step: operator obtains free MyUSPTO API key -> ODP_API_KEY in biointel/sources/patents.py. **Actions: get key at data.uspto.gov, paste into ODP_API_KEY, re-run `python cli.py patents-probe`, paste the whole listing so bulk URLs are wired from real output.** |
| 0.70 | 2026-08-26 | Probe results: Orange Book UNLOCKED (22,205 patent rows, header exact); search.patentsview.org DNS-dead everywhere -- confirmed by research: PatentSearch API shut down 2026-03-20, PatentsView now ODP bulk datasets. patents.py rewritten for the bulk route: two-stage probe (legacy S3 ranged-GET, else ODP product listing echoed verbatim), resumable multi-GB download, streaming three-pass parse with header-echo abort, canon() assignee join to companies.csv -> silver/patents.csv. Full build path offline-tested on fixtures incl. variant-name match and mismatch abort. Noted: one stale pairs-protocol crash in the pasted scrollback (csv newline, pre-handoff run); rerun succeeded, 0.5 numbers unaffected, no code change. **Actions: extract zip, run `python cli.py patents-probe`, paste output; if it prints S3 ROUTE LIVE, follow with `python cli.py patents-ingest` (multi-GB, hours, resume-safe) and paste the summary.** |
| 0.69 | 2026-08-26 | Research cycle: patents (MASS's actual substrate, free via PatentSearch/ODP) + Orange Book LOE acquirer-urgency adopted as the final improvement cycle with a pre-registered adoption rule; 13F/Form4/news/options logged as future work. `patents.py` + `orangebook.py` shipped with probe-gated commands; parsers offline-tested; container probes fail gracefully as expected (endpoints unreachable here). **Actions: extract zip, get free PatentSearch key -> paste into biointel/sources/patents.py, run `python cli.py patents-probe` then `python cli.py orangebook-probe`, paste both outputs.** |
| 0.68 | 2026-08-25 | PART 0 COLD START added: verified codebase map (26 modules/47 commands), environment, workflow, final-number ledger, holdout ledger, behavioral rules, ranked options. Continuation-complete. |
| 0.67 | 2026-08-25 | Latent/hybrid measured: no gain; MASS-inspired stays adopted. Remaining options ranked. Resume next session from this status. |
| 0.66 | 2026-08-25 | Latent-SVD + hybrid shipped into protocol harness. **Actions: extract zip, re-run `python cli.py pairs-protocol`, paste all four lines.** |
| 0.65 | 2026-08-25 | Field-protocol finals: HR@5 0.222 / HR@10 0.284, MASS-inspired adopted. Measurement complete. Next: assembly → freeze → draft. |
| 0.64 | 2026-08-25 | Field-protocol eval + MASS-inspired metric shipped, path tested. **Actions: extract zip, run `python cli.py pairs-protocol` (long: 127 events x 2 metrics x 20 repeats), paste both lines.** |
| 0.63 | 2026-08-25 | Supervised pairs: hit@10 0.21 / median 221 (2020+). Pairing claim locked at 16–21×. ALL model work closed. Next: assembly → freeze → draft. |
| 0.62 | 2026-08-25 | Supervised pair ranker shipped. **Actions: extract zip, run `python cli.py pairs-fit` (expect tens of minutes; prints per-event ranks), paste the summary.** |
| 0.61 | 2026-08-25 | Gen-2 holdout: 2.2× (0.079/0.720) — stable, final. Model iteration closed; both accesses spent. Next: results assembly → freeze → draft. |
| 0.60 | 2026-08-25 | Pair result 16x hit@10 recorded; holdout text-zeroing bug fixed and tested. **Actions: extract zip, then `python cli.py holdout tuned fund+eng+text` (tune already ran); paste output.** |
| 0.59 | 2026-08-25 | Pair model + _maxSimToAcq shipped and math-tested. **Actions: extract zip, run `python cli.py pairs` then `python cli.py develop`; paste both outputs.** |
| 0.58 | 2026-08-25 | Research verdict: pairwise/link-prediction formulation is the field's SOTA; our target-only design is the criticized one. Pair-model build is next. |
| 0.57 | 2026-08-25 | Expansion flat (info ceiling, not event scarcity). S2 trial-outcome catalysts shipped. **Actions: extract zip, run `python cli.py develop`, paste the three hist-gbm rows.** |
| 0.56 | 2026-08-25 | Window extended to 2001 (+legacy forms). Sequential expansion run begins: universe → ingest tranches → label chain → text tranches → rebuild → develop. |
| 0.55 | 2026-08-25 | Converged text drops to 0.061; shrinkage sweep shipped as the final dev knob, decision rule pre-registered. **Actions: extract zip, run `python cli.py develop textsweep`, paste all alpha lines.** |
| 0.54 | 2026-08-25 | Text +8% relative on dev (0.062→0.067); scorer was unconverged — budget raised. **Actions: extract zip, re-run `python cli.py develop`, paste the three hist-gbm rows.** |
| 0.53 | 2026-08-25 | Text scorer wired (fold-safe hashing + OOF stacking); probe clean incl. 20-F. **Actions: extract zip; grind `text-ingest 300` tranches to completion; then `python cli.py develop` and paste the table incl. the fund+eng+text row and coverage line.** |
| 0.52 | 2026-08-25 | Activist flat; CRSP declined; 10-K text route opened with literature backing; text-ingest shipped. **Actions: extract zip, run `python cli.py text-ingest 25` as probe, paste output; then tranche with `text-ingest 300` repeatedly (large job: ~7–9k docs total).** |
| 0.51 | 2026-08-25 | Gen-2: activist 13D features shipped (probed, cached); CRSP/WRDS flagged as operator action. **Actions: extract zip, run `python cli.py develop` (first run builds the activist cache: ~1,200 cached lookups), paste table; confirm WRDS access.** |
| 0.50 | 2026-08-25 | FINAL: holdout 2.1× lift (AUC-PR 0.081, ROC 0.720) confirms dev 2.13×. Iteration closed. Next: GEN head-to-head, results assembly, freeze, draft. |
| 0.49 | 2026-08-25 | Round 2: wave + TA features + ensemble row shipped. **Actions: extract zip, run `python cli.py develop` (new features auto-included), paste full table incl. ensemble rows; then `develop tune` result if not yet pasted.** |
| 0.48 | 2026-08-25 | Dev round 1: GBM+engineered 1.9× best. Tuning grid shipped. **Actions: extract zip, run `python cli.py develop tune`; paste BEST line. Holdout only after tuning plateaus.** |
| 0.47 | 2026-08-25 | Purged walk-forward develop/holdout protocol + engineered features + GBM shipped. **Actions: extract zip, `pip install scikit-learn`, run `python cli.py develop`, paste table.** |
| 0.46 | 2026-08-25 | Final results: fundamentals 1.6–1.7× lift, stable; four-contribution paper structure locked. Next: GEN head-to-head + results assembly + freeze + draft. |
| 0.45 | 2026-08-25 | Leak confirmed (2.1% vs 35.3% coverage); price-feature results retracted; fundamentals-only primary spec + strict variant shipped. **Action: extract zip, re-run `python cli.py robust`, paste the two fundamentals rows.** |
| 0.44 | 2026-08-25 | price-only ROC 0.985 flagged as artifact signature; missingness-leak diagnostic + covered-only scenario shipped. **Action: extract zip, re-run `python cli.py robust`, paste diagnostic line + full table.** |
| 0.43 | 2026-08-25 | Robustness holds (strict 6.4×, splits 5.3–5.8×); no-price collapse logged as finding; price-only scenario added. **Action: extract zip, re-run `python cli.py robust`, paste table.** |
| 0.42 | 2026-08-25 | qa-wiki: +26 confirmed (155 total machine-verified). Robustness suite shipped. **Action: extract zip, run `python cli.py robust`, paste the table — this is the paper's robustness section.** |
| 0.41 | 2026-08-25 | qa-wiki shipped; strict-label run makes residue non-gating; operator manual task eliminated. **Action: extract zip, run `python cli.py qa-wiki`, paste summary.** |
| 0.40 | 2026-08-25 | Resolver v2: prefix/two-token matching + PARENT_MAP; re-run retries none-rows only. **Action: extract zip, re-run `python cli.py qa-corroborate` (cached, fast), paste summary.** |
| 0.39 | 2026-08-25 | qa-corroborate shipped (acquirer-trail verification + submissions pagination fix). **Actions: extract zip, run `python cli.py qa-corroborate`, paste summary — the "still needing a human" count is your remaining manual load.** |
| 0.38 | 2026-08-25 | Robustness holds: 0.70 P@10 and 6.2–6.7× lift stable under date correction and −90d censoring. Human worklist (176 rows) is the open manual task; remaining machine robustness queued. |
| 0.37 | 2026-08-25 | QA pass shipped: agreement-date extraction (76/87 on real docs), EventClass, stratified worklist; fit censor-lead arg. **Actions: extract zip, run `qa` → `labels` → `features` → `fit` → `fit 90`; paste qa summary + both fit headline blocks.** |
| 0.36 | 2026-08-25 | Corrected headline: AUC-PR 0.257 (6.2× lift), ROC 0.918, P@10 0.80 at mature quarter. R7 proxy-lag caveat logged. Next: label QA pass (60-event stratified sample, EventClass, blanks, contested deals), then robustness suite. |
| 0.35 | 2026-08-25 | Crash localized (interpreter fault in hot loop) and fixed via numpy vectorization with fallback. **Actions: extract zip, `pip install numpy`, `python cli.py fit`, paste report.** |
| 0.34 | 2026-08-24 | Full rebuild done; test AUC-PR 0.193 (5.7× lift), ROC 0.907; snapshot frozen. Censoring + mature-quarter fixes shipped. **Action: extract zip, run `python cli.py fit`, paste report.** |
| 0.33 | 2026-08-24 | Ingest complete (1,194/1,194). Harvest wired into labels; `fit` shipped and code-path tested. **Action: extract zip, run the seven-command rebuild block, paste the `labels` summary and the final fit report.** |
| 0.32 | 2026-08-24 | Cleanup done; ingest at 636/1,194, zero errors. Continue tranches to completion. |
| 0.31 | 2026-08-24 | Ingest 300/1,208 clean. Feed-header pseudo-company filter + cleanup script shipped. **Actions: extract zip, run `python cleanup_feed_junk.py`, continue `python cli.py ingest 100` tranches.** |
| 0.30 | 2026-08-24 | Labels final: 287 auto + 60 manual. `ingest` command shipped and code-path tested. **Action: extract zip, run ingest tranches (see command block); expect hours across sessions — resume-safe.** |
| 0.29 | 2026-08-24 | Sample verdict ~92%; Apellis→Biogen independently verified. Placeholder-acquirer fix shipped. **Action: extract zip, re-run `python cli.py verify-fill` (cached docs, fast).** |
| 0.28 | 2026-08-24 | verify-fill: 291/347 acquirers auto-filled (84%). Spot-check sample requested before label promotion. |
| 0.27 | 2026-08-24 | Harvest ran: 371 events / 347 at conf≥2. `verify-fill` ships: auto-extracts acquirers from each event's merger proxy; validated on real Vertex/Crinetics language. **Action: extract zip, run `python cli.py verify-fill`, paste summary; expect a long first run (~350 fetches).** |
| 0.26 | 2026-08-24 | Universe final: 1,208 members / 422 delisted / 38 dev. `harvest` command ships: universe-wide label proposals from cached submissions, zero ingest. **Action: extract zip, run `python cli.py harvest`, paste the summary + first ~15 rows.** |
| 0.25 | 2026-08-24 | Form-15 over-admission fixed: was-listed proof = Form 25 family only. **Action: extract zip, re-run `python cli.py universe` (fully cached, fast).** |
| 0.24 | 2026-08-24 | Universe build v1: 645 members / 0 delisted — exchange-blanking survivorship bug found and fixed (Form 25/15 = was-listed proof). **Action: extract zip, re-run `python cli.py universe`.** |
| 0.23 | 2026-08-24 | Probe succeeded on real feed (100/page). Full universe build running; awaiting counts. |
| 0.22 | 2026-08-24 | Parser rewritten against real probe output (Perl ARRAY artifacts; cik/conformed-name child elements; submissions name fallback). **Actions: extract zip, re-run probe then universe.** |
| 0.21 | 2026-08-24 | P1a shipped: `universe-probe` + `universe` commands; rule-defined membership incl. delisted; probe-gated build. **Actions: extract zip, run probe, then universe if probe prints PARSE OK.** |
| 0.20 | 2026-08-24 | Corrected-data backtest recorded: CRNX 11–17/~30 across four pre-announcement quarters, mid-pack, reported as-is. Pipeline end-to-end complete for the 40-company dev universe. Next: P1 rule-defined universe expansion (labels, acquirer coverage, score discrimination, event-study N all scale with it). |
| 0.19 | 2026-08-24 | Backtest miss diagnosed as events-layer data hole: 21/40 companies had zero FDA events from descriptor-abbreviation query misses. fda.py auto-variants + canonical-key search; features.py substantive-row + shares forward-fill. Weights untouched per pre-registration. **Actions: extract zip, then run the six-command block.** |
| 0.18 | 2026-08-24 | M3–M5 implemented: transparent target score + acquirer pairing + backtest (`predict`, `backtest`). Revenue-basis bug in acquirer threshold fixed. Pre-registered: main-machine CRNX backtest rank is the validation number, reported as-is. **Actions: extract zip, run `python cli.py predict` then `python cli.py backtest`.** |
| 0.17 | 2026-08-24 | fin-all + features confirmed on main machine: AZN/Takeda restored, 1,930 quarters with financials, 1,975 with price. M1 closed. |
| 0.16 | 2026-08-24 | M1 implemented: `features` command builds as-of feature panel + model_panel joined with labels. Audited: zero leakage, monotone counts, coherent CRNX positives. **Actions on main machine: extract zip, run `python cli.py fin-all` (restores AZN/Takeda financials + Currency column under R4), then `python cli.py features`.** |
| 0.15 | 2026-08-24 | Main-machine run confirms restructured labels: 107 events, 4 verified CRNX positives, zero false labels. Phase L closed. Next: Phase M feature table (M1). |
| 0.14 | 2026-08-24 | Label layer restructured: propose (5 independent signals + target-side prober) → verify (curated overlay, seeded with web-verified Vertex/Crinetics $10B deal) → consume (panel takes verified or ≥2-signal events only, provenance stamped). **Action on main machine: extract zip with overwrite, run `python cli.py labels`, paste tail.** |
| 0.13 | 2026-08-24 | Survivor test (`still_filing_after`, cached submissions) resolves share-issuing-acquirer inversion (BBIO); financing-agent filter blanks lender-as-acquirer (CRNX, kept as genuine target event, acquirer unresolved). **Action on main machine: extract zip, run `python cli.py labels` only** — expect ~4 positives, all CRNX. |
| 0.12 | 2026-08-24 | Spot check exposed 3 false label events (SPA-as-M&A, junk counterparty + inverted direction, credit-agreement-as-M&A). Fixed via type split, singular junk words, completion-beats-proxy precedence, tightened proxy window. **Actions on main machine: delete `deal_counterparties.csv`, then `cparty-all` (reads cache, no downloads), `relationships`, `labels`; re-paste positives.** |
| 0.11 | 2026-08-24 | `labels` run on main machine: 135 events, 71/3/61 acquirer/target/unknown, 12 positives, 0.45% base rate. Spot check of the 3 target events + 12 positives requested before Phase M. |
| 0.10 | 2026-08-24 | Phase L implemented: `labels` command builds ma_events.csv (shell/junk filtering, trail-based direction resolution) and leakage-safe firm-quarter label_panel.csv. Two false-labelling defects caught on real data and fixed (uncorroborated mirroring; completion misattribution). **Action on main machine: run `python cli.py labels`** — uses cached submissions, no new endpoints. |
| 0.9 | 2026-08-24 | `relationships` run on main machine: 2,150 rows, 71 in-universe pairs, 152 M&A label candidates. N2 closed. Next: Phase L label panel (L1–L3) and P1 universe rule. |
| 0.8 | 2026-08-24 | N2 implemented: `relationships` command builds unified silver/relationships.csv with PartnerIID in-universe matching and M&A label candidates. Validated: zero dupes, real Amgen acquisitions with dates, cross-layer partner bridging. **Action on main machine: run `python cli.py relationships` (pure derivation, no downloads).** |
| 0.7 | 2026-08-23 | Deployment run on main machine: trials-all 19,655 rows (contamination verified fixed), cparty-all 1,317 counterparties, study-all 854 events with literature-consistent asymmetric CARs. New small defect: Schrödinger umlaut, one-cell fix. |
| 0.6 | 2026-08-23 | Counterparty extraction rewritten against 1,062 real bronze filings and validated (mean 1.98/filing, ~90% real orgs). Exhibit typing fixed: `index.json` `type` is an icon name; type now derived from filename. IFRS taxonomy added (AZN/Takeda restored, Currency column). CTGovName schema + overrides for six contaminated companies. Novella→CRO; Roche variants merged. Event-study engine (`study.py`) with five metrics, validated on real REGN bars. `freeze` command for reproducible snapshots. Master plan: 20260823_v2_Bioindustry_Pipeline_Plan.md. **Actions on main machine: delete `deal_counterparties.csv` and `trials.csv`, then `cparty-all` and `trials-all`.** |
