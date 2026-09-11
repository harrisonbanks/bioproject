# docs/20260911_v1_Manual_S3_Docs_Commit_Gate_Errata.md

# Operating Manual — S3 errata: docs-only commit gate (operator ruling 2026-09-11)

Appends to docs/20260910_v2_Operating_Manual.md §3. Binding on every
session, both roles.

## S3.6 Docs-only commit gate

1. A commit that stages only documentation files (docs\*.md) gates on
   exactly three checks: every deployed file's SHA256 matches its
   delivery hash; the staged list equals the expected list; porcelain
   is otherwise clean. Nothing else.
2. The test suite and ruff NEVER run in a docs-only gate. They prove
   nothing about markdown and cost ~3 minutes per run. Suite and lint
   gates exist for commits that touch src\ or tests\.
3. Mixed commits (code + docs) use the full code gate.
4. Mechanism: gate templates copied without pruning apply code-grade
   checks to no-risk changes; budget follows risk (manual §3 origin
   rule). A gate check that cannot fail for the change class is
   waste, not safety.
