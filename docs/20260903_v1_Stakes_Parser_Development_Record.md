# docs/20260903_v1_Stakes_Parser_Development_Record.md

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
