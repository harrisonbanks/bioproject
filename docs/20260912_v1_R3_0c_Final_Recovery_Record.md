docs/20260912_v1_R3_0c_Final_Recovery_Record.md

# R3-0c final recovery record

**Date:** 2026-09-12
**Status:** CLOSED. This record supersedes the interim Level 1-2 census figures
published in PROJECT_STATUS v1.32 and in
docs/20260912_v1_Document_Processing_and_Evidence_Architecture.md §58.
**Gates:** R3-0c-i (block v57a), R3-0c-ii (v57k, commit 5eae6b6), R3-0c-iii
(v57m, commit 87778a8), R3-0c-iv (v57p, commit be4b72c).
**Evidence:** data\exports\20260912_v57a_r30ci_exports_inventory_evidence.txt,
20260912_v57k_r30cii_gate_evidence.txt, 20260912_v57m_r30ciii_gate_evidence.txt,
20260912_v57p_reconciliation_gate_evidence.txt.

---

## 1. Headline

Final R3-0c: 4,678 recovered mappings of 4,834 authoritative reviewed keys, 29
ambiguous, and 127 unresolved. The recovered mappings collapse to 3,352 unique
sentence texts. At least 3,312 of those currently have consistent binary
strategic-priority labels: 1,632 positive and 1,680 negative. Twenty-seven have
conflicting verdicts; the remaining sentence-level non-binary status is
measured below. Level 3 resolved all 1,639 previously unresolved p2h keys.
Replay used the current frozen 6,992-reference corpus and is therefore a
deterministic reconstruction, not a byte-identical historical replay.

## 2. Reconciliation, with the equations that proved it

1. `RECONCILIATION_EQUATION 4834 == 2936 + 1742 + 29 + 0 + 127 -> True`, being
   pre-existing recovered, replay recovered, pre-existing ambiguous,
   replay-created ambiguous, and final unresolved.
2. `TRANSITION_EQUATION 1869 == 1742 + 0 + 127 -> True`, being the Level 1-2
   unresolved population resolved by replay, made ambiguous by replay, and
   still unresolved.
3. `RECONCILIATION reviewed_keys 4834 == sum(status) 4834`. No record is
   unaccounted for.
4. Replay created zero new ambiguity and overwrote zero direct recoveries.

## 3. Recovery by source

| Source | Mappings |
|---|---|
| `table_direct` | 2,193 |
| `extractor_replay` | 1,742 |
| `judging_evidence_direct` | 548 |
| `worksheet_direct` | 118 |
| `cluster_direct` | 77 |
| **recovered total** | **4,678** |
| `ambiguous` | 29 |
| `unresolved` | 127 |

## 4. The 127 unresolved, characterised honestly

Of the 127 unresolved reviewed keys, 90 lack authoritative verdict evidence and
37 were recorded under rule versions not reproduced by the Level 3 index. Of
the 90 no-verdict keys, 60 are the regenerated 2026-09-12 R2 worksheet entries
that were never judged; the remaining 30 are other no-verdict-evidence cases.
These should not be described as lost labels.

## 5. Mapping-level classes, each with its denominator

5. Denominator recovered mappings, 4,678: correct 2,281, wrong 2,372, unsure
   25, without a usable verdict 0.
6. Denominator ambiguous mappings, 29: verdict-bearing 28, of which correct 4
   and wrong 24.
7. Denominator unresolved mappings, 127: verdict-bearing 37.
8. Mapping-level verdict observations are not a sentence-level training-class
   balance and are never to be quoted as one.

## 6. Sentence-level truth, the training-relevant figures

9. Denominator unique recovered sentences, 3,352.
10. `SENTENCE_CLASS_IDENTITY 1632 + 1680 + 27 + 13 + 0 == 3352 -> True`:
    consistent positive 1,632, consistent negative 1,680, conflicting 27,
    unsure-only 13, without verdict 0.
11. Clean binary training pool: 3,312, before any resolution of the 27
    conflicts and any treatment of the 13 unsure-only sentences.
12. 748 sentences appear under more than one reviewed key; 39 appear under more
    than one category. The duplicate-frequency distribution runs from 2,604
    sentences under a single key to one sentence under twenty.

## 7. Order-dependent tie identities

13. 18 indexed keys had their production winner decided by sweep order at equal
    maximum length.
14. Of those, 7 became recovered mappings, covering 4 distinct recovered
    sentences.
15. Every such mapping carries `replay_order_dependent_tie = true` in the
    recovery record and in the audit bundles.
16. Policy for R3-1: those 7 mappings, or equivalently those 4 sentences, are
    either excluded from the initial training corpus or included with a
    reported sensitivity check showing whether their inclusion changes any
    measured result. They are never treated as equal-confidence labels by
    default.

## 8. Authority-form populations, measured not inferred

| Authority | Distinct keys | S | R |
|---|---|---|---|
| `judged` | 4,495 | 4,495 | 0 |
| `header` | 606 | 606 | 0 |
| `r2_judged` | 240 | 0 | 240 |
| `worksheet` | 180 | 120 | 60 |
| `cluster` | 80 | 80 | 0 |

17. Union 4,834, matching the reviewed-key total exactly.
18. `judged & r2_judged` overlap 0, so the 300 R keys are 240 judged plus 60
    never-judged worksheet entries, disjoint. This is measured; it is no longer
    the inference the v57a report made from lexical shape.
19. Other overlaps: `header & judged` 576, `judged & worksheet` 111,
    `cluster & judged` 80, `cluster & header` 3, `header & worksheet` 1.

## 9. Replay input population and its caveat

20. Documents read 6,992; with rows 3,604; candidates 6,942; distinct keys
    4,742; overflow rows 2,200; keys won on tie 18.
21. The index is a reconstruction from the current frozen corpus under rule
    `L3-a3-p2`. It is not asserted to be a byte-identical replay of any
    historical sweep, because the historical reference and capture set was
    never recorded as an input manifest.
22. The index is cached at `data\exports\20260912_v1_r3_candidate_index.json`,
    SHA-256 `7adadaabdef135de0d67a74b742978b0ba6e8b50fd318d915e4a189ca59bcae1`,
    3,421,495 bytes, and is refused automatically if its index or rule version
    stops matching.

## 10. Runtime anchors of record

23. Cold sweep over 6,992 references: about 83 minutes, measured from block
    v57o's stage timestamps (census start 09:32:57, block end 10:56:25).
24. A census reusing the cache: about one second, measured in v57p.
25. Unit suite at 375 tests: about 3 minutes.
26. Correction of record: the "23m28s" figure printed by v57o's own stage line
    is wrong. The block's duration formatter used a minutes-and-seconds format
    string on a TimeSpan and silently dropped the hour component. The true
    elapsed was 83m28s. The formatter is fixed in the block that commits this
    record.

## 11. What R3-0c did not establish

27. True p2 recall remains unmeasured; that is R3-0b and the benchmark's job.
28. No sentence identity exists yet; SEG-v1 creates it.
29. The adjudication evidence is still not immutable; R3-0d does that.
30. The 27 conflicting sentences and the 13 unsure-only sentences have no
    resolution policy yet; that is a prerequisite for the training corpus, not
    for closing recovery.

## 12. Disposition

31. R3-0c is closed.
32. Next: R3-0b SEG-v1, then R3-0d immutable adjudication ledger, then dataset
    manifests, then R3-1.
