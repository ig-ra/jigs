# Code Census — src/engine.ts, src/engine.test.ts

## Scope
*(P0 — SCAFFOLDED by `census scaffold`. PRUNE the candidate entries to the real change frontier; fill the boundary note + checklist from the spec. This is a starting point, not a decision.)*

### Boundary
god-struct(s): Store
SCIP match: `/X#` (fields + inherent methods) + `[X]` (trait/impl methods).

### Candidate entry symbols (pub/pub(crate) fns in target files — PRUNE to the frontier)
| candidate | anchor | signature | boundary-members touched |
|---|---|---|---|
| `compact` | src/engine.ts:3 | `function compact(store: Store, key: string): Promise<number>` | 3 |
| `planCompaction` | src/engine.ts:12 | `function planCompaction(store: Store): string[]` | 1 |
| `mergeRanges` | src/engine.ts:20 | `function mergeRanges(store: Store, lo: number, hi: number): number` | 0 |
| `report` | src/engine.ts:31 | `function report(store: Store): Stats` | 1 |

### Boundary preview (coverage floor — top members)
| member | accesses |
|---|---|
| `Store#stats` | 2 |
| `Store#cfg` | 2 |
| `Store#getObject` | 1 |
| `Store#putObject` | 1 |

### Coverage checklist (FILL from the spec — what 'done' means)
- [ ] 
