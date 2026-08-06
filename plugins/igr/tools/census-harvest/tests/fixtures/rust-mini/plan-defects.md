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

---

## Planted STRUCTURAL defects (the plan-vs-itself lint)

Task 1 is the clean control — it must produce NO structural finding.

### Task 1: Add the host normalizer

**Files:**
- Create: `src/normalize.rs`

**Interfaces:**
- Consumes: `compact` (exists in code — must NOT be flagged as undeclared)
- Produces: `normalize_host`

- [ ] **Step 1: Write the failing test**

```rust
fn test_normalize_host() { assert_eq!(normalize_host("API."), ""); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cargo test normalize`
Expected: FAIL with "cannot find function"
fails if: the repeated `api.` prefix strip is removed

- [ ] **Step 3: Commit**

```bash
git add src/normalize.rs
```

### Task 2: Route the call sites through it

**Files:**
- Modify: `src/engine.rs:1-40`
- Test: `src/engine_normalize_test.rs`

**Interfaces:**
- Consumes: `normalize_host`, `never_defined_thing`
- Produces: `routed_engine`

- [ ] **Step 1: Write the failing test**

```rust
fn test_routed() { assert!(routed_engine("api.x")); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cargo test routed`
Expected: FAIL with "not wired"
fails if: the call site keeps using the raw label

- [ ] **Step 4: Commit**

```bash
git add src/engine.rs
```

### Task 3: Emit the rendered label

**Files:**
- Modify: `src/engine.rs:40-80`

**Interfaces:**
- Consumes: `render_label`
- Produces: `emit_label`

- [ ] **Step 1: Write the failing test**

```rust
fn test_emit() { assert_eq!(emit_label(), "api.x"); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cargo test emit`
Expected: FAIL with "not implemented"

- [ ] **Step 3: Commit**

```bash
git add src/engine.rs
```

TODO: decide whether the label cache needs invalidating.

### Task 4: Add the label renderer

**Files:**
- Create: `src/render.rs`

**Interfaces:**
- Produces: `render_label`

- [ ] **Step 1: Write the failing test**

```rust
fn test_render() { assert_eq!(helper_unrelated(), 0); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cargo test render`
Expected: FAIL with "cannot find function"
fails if: helper_unrelated is deleted

- [ ] **Step 3: Write the implementation**

```rust
fn render_label(site: &str) -> String { site.to_string() }
```

- [ ] **Step 4: Commit**

```bash
git add src/render.rs
```
