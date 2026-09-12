# docs/20260911_v1_Manual_Errata_S2_And_Scripts_Note.md

# Operating Manual errata: no directory deletes; scripts\ folder queued for review (operator ruling 2026-09-11)

Appends to docs/20260910_v2_Operating_Manual.md §2. Binding on every
session, both roles.

## S2.7 No directory deletion
A block never issues Remove-Item (or any equivalent) against a directory.
Deletions target individually named files only. Before any delete, the
directory's full contents are listed in the block's evidence, and the
operator gives explicit go on that named list. Remove-Item on a path that
is not a single named file is refused at draft time.

Failure of record: block v51u issued `Remove-Item scripts -Force
-ErrorAction SilentlyContinue` immediately after relocating one known
file, without first listing the directory's other contents. The folder
held 18 tracked, unrelated files; PowerShell's confirmation prompt (not
this rule) is what prevented deletion. The operator declined it.

## Queued for review: scripts\
`scripts\` is tracked in git (18 files, including a `refactor\`
subfolder), last touched 2026-08-29 during the src-layout migration
(commits 55bc9c1, 5c16ec8, da29a85). Nothing under `src\biointel\`
imports or invokes anything in it. Left as-is per operator ruling
2026-09-11; not R2/R2v2/R3 scope. When examined, options are: archive via
`git mv scripts docs/archive/scripts-2026-08-29` (preserves history,
reversible), delete with the full file list in the commit evidence, or
confirm continued use and document why each file is kept.
