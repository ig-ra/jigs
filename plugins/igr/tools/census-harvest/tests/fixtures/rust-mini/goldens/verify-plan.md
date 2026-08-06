# verify-plan report
plan: tests/fixtures/rust-mini/plan-defects.md  ·  index: 0.0.0 (7ae18ed96a 2026-07-05)  ·  census rows: 9  ·  cites: 3  ·  tasks: 4

*Deterministic checks only: (A) structured claims vs CODE — code-block sigs + [C:] cites; (B) the plan vs ITSELF — task/step structure. FALLIBILITY = high-signal (Result added/dropped). Type diffs may be intended port abstraction — verify.*

### Dangling citations — [C:name] not found in code at all (1)
- [C:ghost_fn]

### Cited but not in census — exists in code, missing from census rows (1)
- [C:run]

### FALLIBILITY mismatches (HIGH — Result invented/dropped) (1)
- plan:11 `stats` — plan `Result<Stats, String>` vs real `Stats`  @('src/store.rs', 38)

### Other return-type diffs (candidates — may be intended abstraction) (1)
- plan:21 `report` — plan `u64` vs real `Stats`  @('src/engine.rs', 28)

### Arg-count mismatches (1)
- plan:16 `put_object` — plan 1 vs real [3]  @('src/store.rs', 30)

### Ambiguous pins (multiple real defs w/ differing sigs — verify manually) (1)
- plan:26 `estimate` (2 defs)

## Plan structure (plan vs itself)

### Task numbering gaps (0)
- none

### Step numbering gaps (HIGH — a task's steps must be 1..N) (1)
- plan:75 Task 2 — steps [1, 2, 4]

### Declared file never staged (HIGH — in Files:, absent from this task's `git add`) (1)
- plan:75 Task 2 — `src/engine_normalize_test.rs` not in ['src/engine.rs']

### Task declares files but has no `git add` at all (HIGH) (0)
- none

### Forward references (HIGH — consumes a name a LATER task produces) (1)
- plan:103 Task 3 consumes `render_label` — produced by Task 4

### Undeclared consumes (name not produced by any task and not found in code) (1)
- plan:75 Task 2 consumes `never_defined_thing`

### Placeholders (HIGH — writing-plans forbids these) (1)
- plan:129 `TODO` — TODO: decide whether the label cache needs invalidating.

### `Expected: FAIL` with no `fails if:` clause (HIGH — unverifiable red stage) (1)
- plan:118 Task 3 Step 2

### Vacuous-by-construction tests (candidates — test touches nothing this task changes) (1)
- plan:131 Task 4 — changes ['render_label'], test names ['helper_unrelated']

### Reinvention candidates (new normalize/parse/validate-shaped helper — read the siblings and the stdlib BEFORE accepting it) (1)
- plan:48 Task 1 adds `normalize_host` — check ['src'], existing there: ['Config', 'Persist', 'Stats', 'Store', 'alt', 'bump', 'caller', 'cfg']

### Staged-file union (compare against the scope guard / impl handoff)
- 3 files: `src/engine.rs`, `src/normalize.rs`, `src/render.rs`

## Verdict
**HIGH findings: 7** — fix or explicitly justify each before P3b.
