# docs/20260911_v1_Manual_Errata_Block_Discipline.md

# Operating Manual - errata: block discipline (operator ruling 2026-09-11)

Appends to docs/20260910_v2_Operating_Manual.md sections 3, 4, and 7.
Binding on every session, both roles. Each rule closes a failure of record
from the R2 session of 2026-09-11 (numbered in PROJECT_STATUS v1.29).

## E1. The replica carries state (failures 3 and 5)
Before any block ships, it is run on a replica that holds the prior blocks'
side effects: the live data folder (snapshots, exports), untracked files
from earlier blocks, and fixture-run artifacts. A block is verified on that
replica, never on a clean tree.

## E2. No inline code in blocks (failure 4)
Anything beyond git, hash, copy, pytest, ruff, and the package's own CLI
ships as a hash-gated .py file run by path; PowerShell never carries Python
text. Script files deploy under data\scripts\ (gitignored by the existing
data/ rule), so they can never dirty the tree. The gate that first deploys
there confirms the ignore rule in its evidence.

## E3. Test isolation is asserted, not assumed (failure 3)
Code that writes a path derives it from config.DATA or config.EXPORTS,
which the test fixture redirects, and a test asserts the path is under the
redirect. The suite's exit criterion includes a live-folder check printed
in the block's evidence: listings of data\snapshots and data\exports before
and after, with no new files.

## E4. Blocks print state before gating, and the state is the stop message
The first evidence lines of every block are HEAD, tracked changes,
untracked files, and the live snapshot count. A stop prints the full state
block plus the named cause; a stop without its state print is itself a
defect of record. Clean-tree gates count tracked changes only.

## E5. One live block, unique letter, dated names (failures 1 and 2)
Every reissue takes a new letter; download names are never reused, even
across sessions; the replica run greps the block's letter and every
download name against the session's prior blocks before delivery.

## E6. Evidence file over console paste
When a block stops, the operator attaches the evidence file; the console
tail cuts off the state lines.
