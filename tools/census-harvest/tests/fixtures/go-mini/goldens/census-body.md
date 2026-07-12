## Appendix: Code Census

*SCIP-harvested skeleton (0.2.7) + model judgment. 3 in-scope rows. Anchors re-resolve at implement HEAD.*

| symbol | kind | anchor | signature | vis | in | out | boundary | behavior (judgment) | disposition |
|---|---|---|---|---|---|---|---|---|---|
| `Compact` | Function | engine/engine.go:5 | `func Compact(s *store.Store, key string) (uint64, error)` | public | 2 | 6 | Store#GetObject, Store#PutObject, Store#Stats | early-return on GetObject err; bump side-effect via PutObject | moves |
| `planCompaction` | Function | engine/engine.go:16 | `func planCompaction(s *store.Store) []string` | private | 0 | 4 | Store#Cfg |  | stays |
| `MergeRanges` | Function | engine/engine.go:24 | `func MergeRanges(s *store.Store, lo int, hi int) (int, error)` | public | 0 | 4 |  | err on lo>hi before any work |  |

## Reconciliation (deterministic coverage floor)

- boundary coupling: **6 member-accesses / 4 members** (prod; 6 bare type-mentions excluded).
- symbols harvested: 8 (6 prod / 2 test); in-scope: 3.
- SCIP<->grep grep-only flags: 5 (review in the skeleton).

| boundary member | accesses |
|---|---|
| `Store#Stats` | 2 |
| `Store#Cfg` | 2 |
| `Store#GetObject` | 1 |
| `Store#PutObject` | 1 |
