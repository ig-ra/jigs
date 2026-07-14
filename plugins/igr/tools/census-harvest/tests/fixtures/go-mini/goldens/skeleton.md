## Census skeleton (SCIP-harvested; mechanical only — judgment via `census merge`)

| symbol | kind | anchor | signature | vis | in | out | boundary members | test? |
|---|---|---|---|---|---|---|---|---|
| `engine` | Package | engine/engine.go:1 | `package engine` | private | 5 | 0 |  |  |
| `Compact` | Function | engine/engine.go:5 | `func Compact(s *store.Store, key string) (uint64, error)` | public | 2 | 6 | Store#GetObject, Store#PutObject, Store#Stats |  |
| `planCompaction` | Function | engine/engine.go:16 | `func planCompaction(s *store.Store) []string` | private | 0 | 4 | Store#Cfg |  |
| `estimate` | Function | engine/engine.go:20 | `func estimate(s *store.Store) int` | private | 1 | 4 | Store#Cfg |  |
| `MergeRanges` | Function | engine/engine.go:24 | `func MergeRanges(s *store.Store, lo int, hi int) (int, error)` | public | 0 | 4 |  |  |
| `Report` | Function | engine/engine.go:35 | `func Report(s *store.Store) store.Stats` | public | 0 | 4 | Store#Stats |  |
| `compactHelper` | Function | engine/engine_test.go:9 | `func compactHelper(s *store.Store) uint64` | private | 1 | 4 | Store#Stats | TEST |
| `TestCompact` | Function | engine/engine_test.go:13 | `func TestCompact(t *testing.T)` | public | 1 | 11 |  | TEST |

## Boundary coupling (coverage floor — member accesses only, prod)

| member | accesses |
|---|---|
| `Store#Stats` | 2 |
| `Store#Cfg` | 2 |
| `Store#GetObject` | 1 |
| `Store#PutObject` | 1 |

## SCIP<->grep reconciliation
| file | SCIP member-lines | grep hit-lines |
|---|---|---|
| engine/engine.go | 6 | 11 |

**grep-only lines (SCIP didn't resolve — review): 5**
- engine/engine.go:5  `func Compact(s *store.Store, key string) (uint64, error) {`
- engine/engine.go:16  `func planCompaction(s *store.Store) []string {`
- engine/engine.go:20  `func estimate(s *store.Store) int {`
- engine/engine.go:25  `s *store.Store,`
- engine/engine.go:35  `func Report(s *store.Store) store.Stats {`
