# docs/20260905_v1_Parallel_Fetch_Scope.md

# Scope: parallel SEC fetching within the published rate limit

Bioindustry Intelligence Platform · 2026-09-05 · scoped, not started.

## 1. Why this and not hardware
Every long run this week — the collection (~24 h), the re-parse (~1.5 h), the
header verification (~14 h) — was bound by SEC's rate limit, not by the
machine (Ryzen 9 5900X, 32 GB, NVMe; CPU idle during fetches). The code makes
one request at a time and sleeps `SEC_RATE_LIMIT = 0.11 s` between them, so
its effective rate is one request per (0.11 s + round-trip latency), about
1–2 per second. SEC's published fair-access limit is 10 requests per second
per source (sourced: config.py cites it; SEC's developer page states it).
The gap between ~1.5/s and 10/s is the only speed lever the project has.

## 2. What changes
A small worker pool (N workers) that shares ONE token bucket enforcing the
aggregate rate, so total requests per second never exceed a configured
ceiling regardless of N. Applies to the three fetch loops: the collector's
document fetch, the header fetch, and any future feeder. Searches (EFTS) stay
serial — they are few and their pagination is sequential.

## 3. Decisions to take before building
1. **Ceiling.** 10/s is the limit; running at the limit risks the ban SEC
   applies to abusers, which would stop every feeder. Recommendation: a
   ceiling of 5/s (half the limit), configurable, with the value recorded in
   every run's parameters.
2. **Back-off.** On any 429 or 403, the pool stops for a cooling period and
   halves the ceiling for the rest of the run, recording both. A ban is a
   project-level outage; caution is cheaper.
3. **Probe first (rule 4.20).** A 200-request probe at the proposed ceiling,
   with response codes and latencies recorded, before any full run uses it.

## 4. Expected effect (arithmetic, not a promise)
At 5/s aggregate, 41,000 fetches take about 2.3 hours instead of ~14. The
collection would have taken ~6 hours instead of ~24. Runtime of record still
comes from operator timestamps.

## 5. Not in scope
Any change to what is fetched, parsed or written. Order of writes is
preserved by collecting results in a queue and writing in the main thread
through `store` (P21), so the single-writer DuckDB constraint is untouched.

## 6. Files
`config.py` (ceiling, workers), a new `fetchpool.py`, the three fetch call
sites, tests with a fake server asserting the aggregate rate is honoured.
