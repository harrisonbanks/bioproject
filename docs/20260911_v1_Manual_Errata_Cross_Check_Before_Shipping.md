# docs/20260911_v1_Manual_Errata_Cross_Check_Before_Shipping.md

# Operating Manual errata: mandatory cross-check before shipping any named artifact (operator ruling 2026-09-11)

Appends to docs/20260910_v2_Operating_Manual.md §2 and §9 (self-check).
Binding on every session, both roles.

## The pattern (failures of record, this session)

Four distinct incidents, one shared root cause:

1. **v51d** - download name `20260911_v1_priorities.py` reused a name
   already used earlier the same day; a stale same-named file in
   Downloads was silently hashed instead of the intended one.
2. **v51g** - two blocks both named "v51g" existed in-session; the wrong
   one ran, capping a paid trial at 39 of 120 documents.
3. **v54 handoff** - the same filename
   `20260911_v54_Session_Handoff.md` was generated twice in-session with
   different content (pre- and post-header-fix), handed to the operator
   both times as if it were a single stable artifact.
4. **v51z block letter** - reused across two different attempts (the
   uncommitted v54 push and the v55 reissue), the same defect as #2,
   caught only because the operator had already read ruling 20 closely
   enough to notice.

## Root cause (not four bugs, one missing step)

None of these required new information to catch - each was checkable
against artifacts the assistant had ALREADY produced earlier in the same
conversation. The failure was never generating a bad name; it was
generating a new named artifact (file or block) and shipping it without
first checking it against the full list of names already used this
session. The check was skipped every time, not performed and wrong.

## S2.8 Mandatory pre-ship cross-check

Before presenting ANY new file, download, or block to the operator, the
assistant states (silently, in its own reasoning, not narrated to the
operator) the answer to exactly these two questions:

1. **Name collision:** has this exact filename or block letter appeared
   anywhere earlier in this conversation - as a prior download, a prior
   block, or a prior commit? If yes, the new artifact takes the next
   unused name/letter in sequence, full stop, before anything else about
   it is finalized.
2. **Content staleness:** does this artifact reference a HEAD, a hash, a
   figure, or another artifact's name that could have changed since it
   was last computed in this session? If yes, recompute it against the
   current state before shipping, never against a value already sent.

This check is not satisfied by "I don't recall a collision" - it requires
scanning the actual list of names already issued (visible in the
conversation and in any manifest the session keeps), because the four
failures above all happened while the assistant would have said, if
asked, that nothing was wrong.

## Failure prevented

The compounding pattern of a long session: as more named artifacts
accumulate, the odds of an unchecked collision rise, and every one costs
the operator a full round trip (run the bad block, diagnose, wait for a
reissue) to catch what a one-line check would have caught before it
shipped.
