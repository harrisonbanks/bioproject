# docs/20260906_v1_GATEM_Maintained_Accuracy_Scope.md

Scope for the post-F1 gate family "M" (maintained accuracy): the improvements
approved in conversation on 2026-09-06. Design only; no code until each
sub-gate gets its own go. Sequencing: after F1 closes, after the fetch-probe
decision, alongside (not blocking) F2.

## Purpose, in one sentence

Every update run — daily or whenever — checks new rows on arrival the way
this week's archaeology checked 41,137 rows after the fact, so defects are
caught at row one, disputed rows queue without blocking the pipeline, and
precision stays a continuously measured number.

## M1 — ingest-time direction verification

- On `stakes run SINCE`, every new row's SGML header (FILED BY / SUBJECT
  COMPANY) is captured and compared at write time, reusing `parse_header`
  and `_fix_decision` unchanged.
- Agreeing rows write normally. Disagreeing rows write to a `disputed`
  status (new column, schema bump) instead of the clean table view.
- Cost: one small cached fetch per filing, inside the run's existing rate
  budget.
- Exit criteria: a probe over one known month of filings shows every
  header-contradicted specimen lands in `disputed` and zero clean rows do;
  regression tests on the Allergan and self-filing patterns pass against
  the ingest path.

## M2 — scheduled second-route crosscheck

- `stakes crosscheck --since <last run>` runs as part of every update run,
  scoped to new rows only; disagreements append to the review queue.
- Same family logic as 2026-09-06: route-B silence is a coverage gap, not a
  disagreement; only value-vs-value conflicts queue.
- Exit criteria: on a replayed month, queue contents equal the full-run
  crosscheck restricted to that month, exactly.

## M3 — standing judge queue (accumulate without blocking)

- Disputed and disagreeing rows are EXCLUDED from every model's declared
  inputs (enforced by `store.enforce`, the existing mechanism) until judged.
  The pipeline runs on clean rows; accumulation costs coverage, never
  accuracy.
- Verdicts land whenever given, stamped `as_of` the verdict date (append-
  only; no backdating what the system knew).
- A `correct` verdict promotes the row to clean; a `wrong` verdict corrects
  it from the header/document and records the correction; `unsure` leaves
  it excluded with the reason.
- `stakes precision` recomputes over all verdicts to date per rule version.
- Surfaces later as the Judge panel of the dashboard (already third in the
  agreed GUI build order); until then, the CLI + worksheet flow from
  2026-09-06 is the interface.
- Exit criteria: a row judged months late produces the same final table
  state as one judged same-day, proven on a replica.

## M4 — LLM judge assist (proposer, never verdict)

- `assist.py` calls the Anthropic API once per queued row with: field in
  dispute, stored value, route-B value, stored as_of, and the same wide
  excerpt `dump_excerpts` extracts. Never the whole filing.
- Prompt is a versioned repo artifact (`prompts/judge_assist_v1.txt`),
  pinned model version, structured reply: `correct|wrong|unsure|abstain` +
  one-sentence reason. `abstain` is mandatory for two-values-in-one-box
  cases (codifying the 52-row refusal of 2026-09-06).
- Proposals stored in `review_proposals` (review id, model id, prompt
  version, excerpt hash, timestamp). Displayed beside the queue row; never
  auto-applied; `precision` counts human verdicts only.
- Malformed reply or API failure degrades to an empty proposal; the queue
  never depends on the API.
- `ASSIST_ENABLED` config, default False; key from environment only.
- Acceptance gate before trust: run against the 148 rows judged 2026-09-06
  and measure agreement with the human verdicts; the number goes in the
  ledger, and the feature ships only if agreement is high on the decided 96
  and it abstains on the 52.

## Deferred items this gate absorbs or names

- r9 event-date repair: route A misses year-end event dates (confirmed
  60/60, 2026-09-06); own gate, rule 4.20 (three real specimens before any
  regex), own commit and regression tests; repairs ~5,400 rows.
- Update cadence: operator-chosen; nothing in M1-M4 assumes daily.
- Predecessor→successor registry handling: decided under F1 step 4, not
  here (separate proposal).

## Decision points for the operator, per sub-gate

M1: none open. M2: none open. M3: whether `unsure` rows ever expire to a
permanent excluded state (proposal: no expiry, consistent with the
hypothesis-store decision). M4: model choice and per-run cost cap
(proposal: current small model, cap 200 calls/run).
