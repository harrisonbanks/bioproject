# docs/20260911_v1_Manual_S5_Cost_Ledger_Errata.md

# Operating Manual — S5 cost-ledger errata (operator-supplied Console data, 2026-09-11)

Appends to docs/20260910_v2_Operating_Manual.md §5. Binding: every future §5
disclosure uses these measured anchors until superseded by a newer Console row.

## Measured anchors (Console "Daily token cost", UTC days)

| Date | Sonnet 5 | Haiku 4.5 | Total | Workload |
|---|---|---|---|---|
| Sep 9 | $11.80 | $3.38 | $15.18 | p1 judging campaign |
| Sep 10 | $11.89 | $3.42 | $15.31 | run-to-empty day, ~4,539 calls |
| Sep 11 | not yet populated | not yet populated | $0.00 shown | 758-call p2 sweep (~14:00-14:30 UTC) |

## Per-call anchors (from Sep 10, two days agree within 1%)

- Blended: ~$3.37 per 1,000 calls at this workload's token profile.
- Sonnet 5: ~$5.24 per 1,000 calls.
- Haiku 4.5: ~$1.51 per 1,000 calls.
- Prior coarse anchor (~700 Haiku rows = $3-4) is superseded by the measured
  Haiku line above.

## Sep 11 sweep (758 calls)

- EXTRAPOLATED from the Sep-10 anchor: ~$2.56. Marked extrapolated; replace
  this line with the Console row when it populates (open-queue item in
  handoff v49 §3.2).

## Campaign total

- Measured through Sep 10: ~$31.60 (incl. $0.55 + $0.56 setup days) plus the
  pending Sep-11 sweep row.
