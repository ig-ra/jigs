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

---

## Planted STRUCTURAL defects (the plan-vs-itself lint)

Task 1 is the clean control — it must produce NO structural finding.

### Task 1: Add the host normalizer

**Files:**
- Create: `normalize/normalize.go`

**Interfaces:**
- Consumes: `Compact` (exists in code — must NOT be flagged as undeclared)
- Produces: `normalize_host`

- [ ] **Step 1: Write the failing test**

```go
func TestNormalizeHost(t *testing.T) { _ = normalize_host("API.") }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./...  -run normalize`
Expected: FAIL with "cannot find function"
fails if: the repeated `api.` prefix strip is removed

- [ ] **Step 3: Commit**

```bash
git add normalize/normalize.go
```

### Task 2: Route the call sites through it

**Files:**
- Modify: `engine/engine.go:1-40`
- Test: `engine/engine_normalize_test.go`

**Interfaces:**
- Consumes: `normalize_host`, `never_defined_thing`
- Produces: `routed_engine`

- [ ] **Step 1: Write the failing test**

```go
func TestRouted(t *testing.T) { _ = routed_engine("api.x") }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./...  -run routed`
Expected: FAIL with "not wired"
fails if: the call site keeps using the raw label

- [ ] **Step 4: Commit**

```bash
git add engine/engine.go
```

### Task 3: Emit the rendered label

**Files:**
- Modify: `engine/engine.go:40-80`

**Interfaces:**
- Consumes: `render_label`
- Produces: `emit_label`

- [ ] **Step 1: Write the failing test**

```go
func TestEmit(t *testing.T) { _ = emit_label() }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./...  -run emit`
Expected: FAIL with "not implemented"

- [ ] **Step 3: Commit**

```bash
git add engine/engine.go
```

TODO: decide whether the label cache needs invalidating.

### Task 4: Add the label renderer

**Files:**
- Create: `render/render.go`

**Interfaces:**
- Produces: `render_label`

- [ ] **Step 1: Write the failing test**

```go
func TestRender(t *testing.T) { _ = helper_unrelated() }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `go test ./...  -run render`
Expected: FAIL with "cannot find function"
fails if: helper_unrelated is deleted

- [ ] **Step 3: Write the implementation**

```go
func render_label(site string) string { return site }
```

- [ ] **Step 4: Commit**

```bash
git add render/render.go
```
