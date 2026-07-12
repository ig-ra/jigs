# Code Census — src/engine.rs

## Scope
*(P0 — SCAFFOLDED by `census scaffold`. PRUNE the candidate entries to the real change frontier; fill the boundary note + checklist from the spec. This is a starting point, not a decision.)*

### Boundary
god-struct(s): Store
SCIP match: `/X#` (fields + inherent methods) + `[X]` (trait/impl methods).

### Candidate entry symbols (pub/pub(crate) fns in target files — PRUNE to the frontier)
| candidate | anchor | signature | boundary-members touched |
|---|---|---|---|
| `compact` | src/engine.rs:3 | `pub fn compact(store: &mut Store, key: &str) -> Result<u64, String>` | 4 |
| `plan_compaction` | src/engine.rs:10 | `pub(crate) fn plan_compaction(store: &Store) -> Vec<String>` | 1 |
| `merge_ranges` | src/engine.rs:18 | `pub fn merge_ranges(store: &Store, lo: usize, hi: usize) -> Result<usize, String` | 0 |
| `report` | src/engine.rs:29 | `pub fn report(store: &Store) -> Stats` | 1 |

### Boundary preview (coverage floor — top members)
| member | accesses |
|---|---|
| `Store::stats` | 2 |
| `Store#cfg` | 2 |
| `Store::get_object` | 1 |
| `Store::put_object` | 1 |
| `Store::persist` | 1 |

### Coverage checklist (FILL from the spec — what 'done' means)
- [ ] 
