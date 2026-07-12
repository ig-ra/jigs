# Code Census — engine/engine.go, engine/engine_test.go

## Scope
*(P0 — SCAFFOLDED by `census scaffold`. PRUNE the candidate entries to the real change frontier; fill the boundary note + checklist from the spec. This is a starting point, not a decision.)*

### Boundary
god-struct(s): Store
SCIP match: `/X#` (fields + inherent methods) + `[X]` (trait/impl methods).

### Candidate entry symbols (pub/pub(crate) fns in target files — PRUNE to the frontier)
| candidate | anchor | signature | boundary-members touched |
|---|---|---|---|
| `Compact` | engine/engine.go:5 | `func Compact(s *store.Store, key string) (uint64, error)` | 3 |
| `MergeRanges` | engine/engine.go:24 | `func MergeRanges(s *store.Store, lo int, hi int) (int, error)` | 0 |
| `Report` | engine/engine.go:35 | `func Report(s *store.Store) store.Stats` | 1 |

### Boundary preview (coverage floor — top members)
| member | accesses |
|---|---|
| `Store#Stats` | 2 |
| `Store#Cfg` | 2 |
| `Store#GetObject` | 1 |
| `Store#PutObject` | 1 |

### Coverage checklist (FILL from the spec — what 'done' means)
- [ ] 
