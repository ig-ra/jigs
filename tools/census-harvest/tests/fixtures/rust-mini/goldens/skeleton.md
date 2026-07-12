## Census skeleton (SCIP-harvested; mechanical only — judgment via `census merge`)

| symbol | kind | anchor | signature | vis | in | out | boundary members | test? |
|---|---|---|---|---|---|---|---|---|
| `engine` | Module | src/engine.rs:1 | `pub mod engine` | public | 4 | 0 |  |  |
| `compact` | Function | src/engine.rs:3 | `pub fn compact(store: &mut Store, key: &str) -> Result<u64, String>` | public | 2 | 10 | Store::get_object, Store::persist, Store::put_object, Store::stats |  |
| `plan_compaction` | Function | src/engine.rs:10 | `pub(crate) fn plan_compaction(store: &Store) -> Vec<String>` | package | 0 | 8 | Store#cfg |  |
| `estimate` | Function | src/engine.rs:14 | `fn estimate(store: &Store) -> usize` | private | 1 | 3 | Store#cfg |  |
| `merge_ranges` | Function | src/engine.rs:18 | `pub fn merge_ranges(store: &Store, lo: usize, hi: usize) -> Result<usize, String>` | public | 0 | 10 |  |  |
| `report` | Function | src/engine.rs:29 | `pub fn report(store: &Store) -> Stats` | public | 0 | 7 | Store::stats |  |
| `tests` | Module | src/engine.rs:34 | `mod tests` | private | 0 | 0 |  | TEST |
| `compact_helper` | Function | src/engine.rs:38 | `fn compact_helper(store: &mut Store) -> u64` | private | 1 | 4 | Store::stats | TEST |
| `test_compact` | Function | src/engine.rs:43 | `fn test_compact()` | private | 0 | 10 | Store::new | TEST |

## Boundary coupling (coverage floor — member accesses only, prod)

| member | accesses |
|---|---|
| `Store::stats` | 2 |
| `Store#cfg` | 2 |
| `Store::get_object` | 1 |
| `Store::put_object` | 1 |
| `Store::persist` | 1 |

## SCIP<->grep reconciliation
| file | SCIP member-lines | grep hit-lines |
|---|---|---|
| src/engine.rs | 7 | 7 |

**grep-only lines (SCIP didn't resolve — review): 0**
