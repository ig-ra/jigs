## Appendix: Code Census

*SCIP-harvested skeleton (0.0.0 (7ae18ed96a 2026-07-05)) + model judgment. 4 in-scope rows. Anchors re-resolve at implement HEAD.*

| symbol | kind | anchor | signature | vis | in | out | boundary | behavior (judgment) | disposition |
|---|---|---|---|---|---|---|---|---|---|
| `compact` | Function | src/engine.rs:3 | `pub fn compact(store: &mut Store, key: &str) -> Result<u64, String>` | public | 2 | 10 | Store::get_object, Store::persist, Store::put_object, Store::stats | early-return on empty key; bump side-effect via put_object; persist ordering after put | moves |
| `plan_compaction` | Function | src/engine.rs:10 | `pub(crate) fn plan_compaction(store: &Store) -> Vec<String>` | package | 0 | 8 | Store#cfg |  | stays |
| `merge_ranges` | Function | src/engine.rs:18 | `pub fn merge_ranges(store: &Store, lo: usize, hi: usize) -> Result<usize, String` | public | 0 | 10 |  | Err on lo>hi before any work |  |
| `report` | Function | src/engine.rs:29 | `pub fn report(store: &Store) -> Stats` | public | 0 | 7 | Store::stats |  | seam |

## Reconciliation (deterministic coverage floor)

- boundary coupling: **7 member-accesses / 5 members** (prod; 8 bare type-mentions excluded).
- symbols harvested: 9 (6 prod / 3 test); in-scope: 4.
- SCIP<->grep grep-only flags: 0 (review in the skeleton).

| boundary member | accesses |
|---|---|
| `Store::stats` | 2 |
| `Store#cfg` | 2 |
| `Store::get_object` | 1 |
| `Store::put_object` | 1 |
| `Store::persist` | 1 |
