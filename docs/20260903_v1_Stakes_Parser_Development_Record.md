# docs/20260903_v1_Stakes_Parser_Development_Record.md  (v2: 2026-09-04/05 direction defect, verification, library defect)

# F1 parser development record — measured rounds r1 → r6

Bioindustry Intelligence Platform · 2026-09-03 · written while the F1
collector runs; the gate closes separately with its own evidence. This file
exists so the specimens, the measurements, and the two near-misses are on the
record rather than in a chat log.

## 1. Method
Rule 4.20 made continuous: an offline analyzer (`analyze_stakes_offline.py`,
disposable, DB-free, read-only on the library) re-parses every captured
filing with the production parsers and classifies each outcome as parsed,
correct refusal (no cover-page anchors), real miss (anchors present, no row),
or XML reject. Misses are excerpted verbatim; rules are written only against
those excerpts; every excerpt becomes a test. Coverage is re-measured on the
same library after each round, so each rule change has a number attached.

Because the analyzer needs no database connection, all of this ran WHILE the
collector was downloading — the operator's instruction, and now the standing
pattern: analysis tooling ships with any long-running step, never after it.

## 2. Measured progression (same library, growing as the collector runs)
| Rule | Parse rate among true cover pages | Real misses | XML rejects |
|---|---|---|---|
| r1 (probe rules, 12 specimens) | 0.881 | 2,136 | 95 |
| r2 | 0.959 | 743 | 101 |
| r3 | 0.975 | 462 | 101 |
| r4 | 0.975 | 463 | **0** |
| r5 | 0.987 | 246 | 0 |
| r6 | **0.992** | 147 | 0 |

Correct refusals stayed flat (160 → 175) throughout: the improvement came
from reading real cover pages, not from loosening what counts as one.

## 3. What each round learned, from specimens
- **r2** — four families no probe specimen had shown: Item-4 prose filings
  (old bank-holding 13Gs with no numbered row table at all, just "Percent of
  Class: 4.868%"); a row index printed between label and value ("ROW (9) 11
  1.1%"); dotted leaders; owner labels carrying a row digit.
- **r3** — the largest family: **row 11 printed without a "%" sign** ("ROW 9
  0.00", "ROW (9) 9.99", "-0-"). Every prior pattern required the symbol.
- **r4** — the structured era uses two different tag vocabularies: 13G
  (`classPercent`, `issuerCusipNumber`, `eventDateRequiresFilingThisStatement`)
  and 13D (`percentOfClass`, `aggregateAmountOwned`, `issuerCIK`,
  `issuerCUSIP`, `dateOfEvent`, `reportingPersonCIK`). Adding the 13D set took
  XML rejects to zero.
- **r5** — rule lines (90 dashes) between rows; explanatory parentheticals
  ("17.4% (based on 81,733,247 shares …)") whose numbers must not be mistaken
  for the value; "NONE" as a stated zero; "Item 9"/"LINE 9" label variants;
  "Up to 9.9999%" recognised as a blocker cap and refused.
- **r6** — the r5 test used a shorter parenthetical than the real filings, so
  the family survived a round. Lesson recorded: **specimens go into tests
  verbatim, never abbreviated.** The window no longer needs a terminator, and
  the value may sit inside the label ("…Represented by Amount 25.0% in Row").

## 4. Two errors the loop caught before they reached the data
1. **False 5% on exit filings.** Widening the r2 pattern made "Less than 5%
   (closing filing)" parse as a 5% holding — a stake recorded as held on the
   filing whose purpose is to announce it was sold. Caught by a test written
   from the specimen.
2. **Exit rows dropped entirely.** The first fix refused those filings, which
   threw away a true dated fact the amendment chain must carry. Decision of
   record (operator, 2026-09-03): qualified statements ("Less than 5%",
   "NONE", "-0-") are written as **percent 0** with the phrase verbatim in the
   evidence span — the honest reading, and the same shape the structured-era
   filings already use (`classPercent 0`). "Up to N%" is different: a cap, not
   a holding, and stays unwritten.

Also caught: `RULE_VERSION` had been stuck at an earlier string for two rounds
because an edit failed silently. Standing fix: every edit is proven by reading
the file back before it is claimed.

## 5. State of the parser at r6
189 unit tests; 24 verbatim layouts locked across r2–r6 plus all 16 probe
captures (13 HTML-era, 3 structured-era, plus the Innoviva/Armata 13D). Still
correctly unwritten: "N/A", "***", "See Item 5", blank rows, "Up to" caps —
pages that state no percentage, where inventing one is the failure mode.

## 6. Consequence for the run in flight
The collector loaded r1 at startup, so rows written during this pass carry the
r1 rules. When it finishes, a re-parse pass applies r6 to the library — no
re-fetching, every document already captured — and the gate records both the
r1 row count and the r6 result.

---

## 7. The direction defect (2026-09-04), from the record

**Found by:** the stub-proposal list. It showed one buyer's name under dozens
of holder CIKs ("GlaxoSmithKline plc" under 41; "Abbott Laboratories" under
8) and individuals carrying company SIC codes. A read-only diagnostic settled
the cause: the holder CIKs were the buyers' TARGETS.

**Cause:** the collector searched SEC by each member's CIK and assumed the
member was the SUBJECT of every filing returned. The search also returns
filings where the member is the FILER — GSK's 13G about a company it holds —
and those rows were written backwards: issuer = GSK, holder = the target.
That population is exactly the strategic-stake rows the matcher exists to
read.

**Fix, three rounds because I added a new assumption each time:**
- r7: orientation from the document's issuer; still relied on the note's
  "member" field, which recorded SEC's first-listed CIK, not the searched
  one.
- r7b: removed that dependency but treated "issuer name matched nothing" as
  evidence that the member was the filer. Wrong: spillover text ("Verastem,
  Inc. Common Stock") defeated matching and inverted BlackRock rows again.
- r7c: an unmatched issuer is not evidence of direction; placement by
  containment; when the issuer still cannot be placed, the reporting
  person's name decides (it is the member → member is owner; it is a fund →
  member is being held); a document-stated owner CIK outranks party
  inference. Four orientation tests plus the BlackRock/Verastem regression.

**Rebuild of record** (`20260905T003602-stakes-rebuild`): 41,137 rows;
orientation subject / filer / unresolved = 36,979 / 1,192 / 3,395. The 1,192
"filer" rows are members holding stakes in others. The first rebuild (r7)
counted 11,302 rows as inverted under the old assumption.

**Owner-name residue** (r7): label fragments stored as names ("S.S. OR",
"1", "EIN", "(s)") — twelve verbatim specimens, all fixed; label fragments
now yield an empty name, never junk.

## 8. Verification against SEC's own header (2026-09-05)

SEC's complete-submission file opens with an SGML header stating FILED BY and
SUBJECT COMPANY as structured fields — an authority for holder, issuer and
direction independent of anything parsed from the cover page. It was one
fetch away the whole time and the collector never took it; that is the
design miss underneath this week's work. Rule recorded: when SEC states a
fact as a structured field, that field is the check, not the cover page.

`stakes verify-direction` fetches each filing's header (probe first; three
real headers locked as fixtures), compares holder/issuer/direction per row,
records match / mismatch / no_header, exports mismatches with SEC's version
beside ours. Interim result at 21,500 of 41,137 rows: **98.0% match**, rate
flat since 4,000. Final counts and the mismatch classification land at gate
close.

Percent and event date are not in the header. `stakes crosscheck` runs a
second extraction route that shares no anchor with the parser (backward from
the "Type of Reporting Person" row; date nearest "Date of Event"); agreement
confirms the field, disagreement goes to the human. Both routes agree on all
nine probe captures. The human judges disagreements, not the whole sample.

## 9. The library defect the header work exposed (2026-09-05)

`library.upsert_reference` matches on accession BEFORE URL. A header capture
carrying the filing's accession therefore attached itself to the filing's
reference: the header URL was never recorded, the cache never hit, every
verify-direction run re-fetched every header (four runs crawled for this
reason — the fetch counter in the timing line proved it: cache hits 0, fetch
337.9 s per 300), and 7,235 filing references carried two active captures
that the rebuild could have confused for documents.

Fixes: header captures get their own reference (source `stakes-header`,
accession kept out of the identifier field) and kind `sec_header` (schema
0.13); index and rebuild always prefer the document capture;
`stakes repair-headers` moved 6,074 misattached headers with no network
(`20260905T050519-stakes-repair-headers`; 1,161 references with two
DOCUMENT captures left for inspection). The repair itself first called the
library upsert per header — each call re-reads the whole references table —
and was rewritten to build rows in memory and append once.

## 10. Operating lessons added this round
- Timestamp every log line and every block stage. Four "is it alive"
  round-trips were spent because startup, loop and block boundaries carried
  no clock.
- Instrument before guessing: the per-stage timing line found the cache miss
  in one read after two wrong guesses (whole-file reads, index build).
- No per-row call into a function that scans a table. Three instances this
  week: the capture lookup, the header read, the library upsert.
- Capture everything SEC offers about a filing the first time you touch it.
- A test that can reach the live database will, eventually: `conftest.py`
  now redirects every unit test to a scratch store.
