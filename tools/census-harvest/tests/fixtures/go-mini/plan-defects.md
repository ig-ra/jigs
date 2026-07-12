# Plan fixture (go) — planted verify-plan defects

Every defect below is DELIBERATE. The golden report must flag exactly these.

Tasks cite [C:Compact] (in census — OK), [C:GhostFn] (dangling — exists nowhere),
and [C:Run] (exists in code at caller/caller.go, but not a census row — cite-gap).

Planted signature claims:

```go
func Stats() (Stats, error)
```
(FALLIBILITY: real `Stats` is infallible — error invented.)

```go
func PutObject(key string) error
```
(ARG-COUNT: real has 2 params; plan pins 1.)

```go
func Report(s *store.Store) uint64
```
(AMBIGUOUS: two real defs — engine/engine.go returns store.Stats, alt/alt.go returns int — differing sigs.)

Correct pin — must NOT flag:

```go
func Compact(s *store.Store, key string) (uint64, error)
```

Deferred pin — must NOT flag:

```go
func MergeRanges(s *store.Store /* re-resolve at HEAD */) (int, error)
```
