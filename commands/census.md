---
description: Build the code census (ground-truth facts for a change surface) — the P1 step of the igr:dev plan method, run standalone.
argument-hint: "<spec-path-or-entry-symbols> [boundary]"
---
Build the code census for: $ARGUMENTS

Run P1 of `igr:dev` `references/plan.md` standalone. Spawn the `igr:code-census` agent (or a `general-purpose` subagent on model sonnet) to do a transitive-closure walk from the entry symbols via the LSP tool, emit the CENSUS schema table (symbol / kind / anchor / signature / visibility / effects+branches / edges_out / edges_in / tests / disposition), and reconcile row-count vs the exhaustive multiline boundary grep (no silent drops). Write it to a sibling `CENSUS.md`. Facts only — no plan, no fixes.
