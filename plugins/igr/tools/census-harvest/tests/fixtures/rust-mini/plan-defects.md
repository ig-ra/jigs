# Plan fixture (rust) — planted verify-plan defects

Every defect below is DELIBERATE. The golden report must flag exactly these.

Tasks cite [C:compact] (in census — OK), [C:ghost_fn] (dangling — exists nowhere),
and [C:run] (exists in code at src/caller.rs, but not a census row — cite-gap).

Planted signature claims:

```rust
fn stats(store: &Store) -> Result<Stats, String>;
```
(FALLIBILITY: real `stats` is infallible — Result invented.)

```rust
fn put_object(key: &str) -> Result<(), String>;
```
(ARG-COUNT: real has 3 params incl. receiver; plan pins 1.)

```rust
fn report(store: &Store) -> u64;
```
(TYPE DIFF: real returns `Stats` — no Result either side, so plain type diff.)

```rust
fn estimate(store: &Store) -> usize;
```
(AMBIGUOUS: two real defs — src/engine.rs and src/alt.rs — with differing sigs.)

Correct pin — must NOT flag:

```rust
fn compact(store: &mut Store, key: &str) -> Result<u64, String>;
```

Deferred pin — must NOT flag:

```rust
fn plan_compaction(store: &Store) -> /* re-resolve at HEAD */;
```
