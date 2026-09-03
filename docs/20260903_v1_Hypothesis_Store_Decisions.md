# docs/20260903_v1_Hypothesis_Store_Decisions.md

# Expert-hypothesis store — decisions of record (2026-09-03)

Purpose: expert and operator judgment about where the industry is going
becomes a first-class input to the system, held to the same as-of and
never-test discipline as every other input. Separate gate from F2; order
between them undecided until both scopes exist. Nothing built yet.

## Decisions closed
1. **One table**, `analyst_hypotheses`. Past and future entries are the same
   rows, distinguished only by `as_of`. No second table.
2. **Fields**: expert (real name — no aliasing; decision of record), subject
   (a company), predicate (wants / is in play / theme), object (a company, a
   category from the shared F2 enum, or a theme), horizon as stated by the
   expert (optional), confidence, statement verbatim, `source_kind`
   (`direct` / `article` / `report` / `transcript` / `social`), entered-by,
   entered-on, `as_of`, `evidence_class`, `doc_id` when an artifact exists.
   Manual-layer provenance rules apply (P5).
3. **`as_of` = the artifact date when one exists, else the entry date.**
   Never the date typed in for a recalled call. This is the leak guard: a
   hypothesis informs only predictions made after its as-of.
4. **`evidence_class`**: `documented` (dated artifact in the library — email,
   message, note, article, slide) or `recollected` (no artifact).
   Recollected calls ARE entered, flagged, and excluded from scoring; an
   artifact found later upgrades the flag. Settled 2026-09-03.
5. **Articles**: stored in the library like any document; publication date
   is `as_of`; the quoted analyst or the publication is the expert;
   `source_kind = article`.
6. **No expiry.** No system clock, no default horizon. A call with a stated
   horizon is scored against that horizon because the horizon is part of the
   prediction. A call with no horizon stays `open` until a deal resolves it,
   the target is acquired by someone else, or the expert withdraws it.
   Reason recorded: a fabricated 18-month default would have scored the
   Tempus–Personalis call (32 months stake-to-announcement) as a miss; the
   only published distribution found (Povel & Sertsios, JCF 2014, Table 2B:
   median 15 months, 75th pct 28, 90th pct 49, n=155, all-industry, likely
   underestimated per the authors) puts a quarter of stake-to-deal intervals
   beyond 28 months. Any future default is measured on this project's own
   data once the F1 stakes chain exists.
7. **Scoring**: per expert, over `documented` calls only — hit, miss, open,
   withdrawn — using the same forward test the matcher takes. Recollected
   calls shown as counts, never as a rate. Track record requires the full
   denominator: retrospective entry recovers all calls in the period from
   artifacts, or the rate is reported as incomplete.
8. **Matcher access**: declared input, its own aspect, equal weight until a
   ledger exists, never test evidence (P10, P19). The user is one value in
   `expert`; own hunches accumulate a track record on the same terms.
9. **Never test evidence.** A hypothesis about a deal cannot score the
   matcher's prediction of that deal.

## Open
1. Who supplies artifacts (operator or expert).
2. Order relative to F2.

## Not in scope
Weighting experts by track record (own gate after a ledger exists).
