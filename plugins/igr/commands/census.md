---
description: Build the code census (ground-truth facts for a change surface) standalone — P0 scope + the P1 igr:code-census agent of the igr:dev plan method.
argument-hint: "<spec-path-or-entry-symbols> [boundary]"
---
Build the code census for: $ARGUMENTS

Standalone P0+P1 of the `igr:dev` plan method. Follow `references/plan.md` §P0 and §P1 exactly — do not improvise a pipeline here:

1. **P0 (scope):** per §P0, write the `## Scope` section (entry symbols / boundary / coverage checklist) to `<prefix>-census.md`.
2. **P1 (census):** spawn the `igr:code-census` agent on that file. Its def owns the method — `census doctor` preflight, SCIP harvest primary, live-LSP fallback when no indexer, judgment.json + `census merge` (tables are rendered, never hand-built).

Facts only — no plan, no fixes. Never git-commit the census (the owner commits docs).
