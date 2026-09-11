# docs/20260911_v1_Boot_Protocol_Step0_Push_Errata.md

# Boot protocol - Errata: Step 0 push rule (operator ruling 2026-09-11)

Amends the boot protocol of handoff v51 (step 1) and Operating Manual v2 §1
and §9 (session boot ritual). Binding on every session, both roles. Every
future handoff carries Step 0 inline in its boot protocol.

## Step 0. Origin holds the handoff's HEAD before the boot window opens

1. Every docs commit is pushed to origin (`jason/refactor`) in the same block
   that commits it, and that block gates on `git rev-parse HEAD` equal to
   `git rev-parse origin/jason/refactor`.
2. Before opening the temporary public window, the operator confirms that
   origin's HEAD equals the HEAD that the handoff names.
3. A boot clone whose HEAD differs from the handoff's stated HEAD is a Step 0
   failure; the remedy is the operator attaching the missing files, and a
   re-clone remains forbidden.

## Failure of record

1. Stated: handoff v51 named HEAD as the v1.28 docs commit following 68ecbc9.
2. True: origin held 68ecbc9, and PROJECT_STATUS v1.28, Addendum A errata 3,
   and the S5 cost-ledger errata were absent from the boot clone.
3. Mechanism: the close-out docs were not committed and pushed before the
   handoff was issued.
4. Fix: this rule; the corrective docs commit reached origin as 47450db.
