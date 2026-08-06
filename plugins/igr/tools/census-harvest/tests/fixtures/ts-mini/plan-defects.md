# Plan fixture (ts) — citations only (sig-diff unsupported for ts)

Cites: [C:compact] (in census — OK), [C:ghostFn] (dangling — exists nowhere),
and [C:run] (exists in code at src/caller.ts, but not a census row — cite-gap).

This sig claim is WRONG on purpose — ts sig-diff is unsupported, so the report
must NOT flag it (and must carry the explicit UNSUPPORTED notice instead):

```ts
function stats(store: Store): Promise<Stats>;
```

---

## Planted STRUCTURAL defects (the plan-vs-itself lint)

Task 1 is the clean control — it must produce NO structural finding.

### Task 1: Add the host normalizer

**Files:**
- Create: `src/normalize.ts`

**Interfaces:**
- Consumes: `compact` (exists in code — must NOT be flagged as undeclared)
- Produces: `normalize_host`

- [ ] **Step 1: Write the failing test**

```ts
function test_normalize_host() { expect(normalize_host("API.")).toBe(""); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bun test normalize`
Expected: FAIL with "cannot find function"
fails if: the repeated `api.` prefix strip is removed

- [ ] **Step 3: Commit**

```bash
git add src/normalize.ts
```

### Task 2: Route the call sites through it

**Files:**
- Modify: `src/engine.ts:1-40`
- Test: `src/engine-normalize.test.ts`

**Interfaces:**
- Consumes: `normalize_host`, `never_defined_thing`
- Produces: `routed_engine`

- [ ] **Step 1: Write the failing test**

```ts
function test_routed() { expect(routed_engine("api.x")).toBe(true); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bun test routed`
Expected: FAIL with "not wired"
fails if: the call site keeps using the raw label

- [ ] **Step 4: Commit**

```bash
git add src/engine.ts
```

### Task 3: Emit the rendered label

**Files:**
- Modify: `src/engine.ts:40-80`

**Interfaces:**
- Consumes: `render_label`
- Produces: `emit_label`

- [ ] **Step 1: Write the failing test**

```ts
function test_emit() { expect(emit_label()).toBe("api.x"); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bun test emit`
Expected: FAIL with "not implemented"

- [ ] **Step 3: Commit**

```bash
git add src/engine.ts
```

TODO: decide whether the label cache needs invalidating.

### Task 4: Add the label renderer

**Files:**
- Create: `src/render.ts`

**Interfaces:**
- Produces: `render_label`

- [ ] **Step 1: Write the failing test**

```ts
function test_render() { expect(helper_unrelated()).toBe(0); }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bun test render`
Expected: FAIL with "cannot find function"
fails if: helper_unrelated is deleted

- [ ] **Step 3: Write the implementation**

```ts
function render_label(site: string): string { return site; }
```

- [ ] **Step 4: Commit**

```bash
git add src/render.ts
```
