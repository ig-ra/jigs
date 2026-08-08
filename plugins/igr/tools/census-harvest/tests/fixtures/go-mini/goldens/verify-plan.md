# verify-plan report
plan: tests/fixtures/go-mini/plan-defects.md  ·  index: 0.2.7  ·  census rows: 8  ·  cites: 3  ·  tasks: 4

*Deterministic checks only: (A) structured claims vs CODE — code-block sigs + [C:] cites; (B) the plan vs ITSELF — task/step structure. FALLIBILITY = high-signal (Result added/dropped). Type diffs may be intended port abstraction — verify.*

### Dangling citations — [C:name] not found in code at all (1)
- [C:GhostFn]

### Cited but not in census — exists in code, missing from census rows (1)
- [C:Run]

### FALLIBILITY mismatches (HIGH — Result invented/dropped) (1)
- plan:11 `Stats` — plan `(Stats, error)` vs real `Stats`  @('store/store.go', 35)

### Other return-type diffs (candidates — may be intended abstraction) (0)
- none

### Arg-count mismatches (1)
- plan:16 `PutObject` — plan 1 vs real [2]  @('store/store.go', 27)

### Ambiguous pins (multiple real defs w/ differing sigs — verify manually) (1)
- plan:21 `Report` (2 defs)

## Plan structure (plan vs itself)

recognized: 4 tasks · 4 with `Files:` · 4 with steps · 4 with `git add` · 4 with `Interfaces:`

### Task numbering gaps (0)
- none

### Step numbering gaps (HIGH — a task's steps must be 1..N) (1)
- plan:70 Task 2 — steps [1, 2, 4]

### Declared file never staged (HIGH — in Files:, absent from this task's `git add`) (1)
- plan:70 Task 2 — `engine/engine_normalize_test.go` not in ['engine/engine.go']

### Task declares files but has no `git add` at all (HIGH) (0)
- none

### Forward references (HIGH — consumes a name a LATER task produces) (1)
- plan:98 Task 3 consumes `render_label` — produced by Task 4

### Undeclared consumes (name not produced by any task and not found in code) (1)
- plan:70 Task 2 consumes `never_defined_thing`

### Placeholders (HIGH — writing-plans forbids these) (1)
- plan:124 `TODO` — TODO: decide whether the label cache needs invalidating.

### `Expected: FAIL` with no `fails if:` clause (HIGH — unverifiable red stage) (1)
- plan:113 Task 3 Step 2

### Vacuous-by-construction tests (candidates — test touches nothing this task changes) (1)
- plan:126 Task 4 — changes ['render_label'], test names ['helper_unrelated']

### Reinvention candidates (new normalize/parse/validate-shaped helper — read the siblings and the stdlib BEFORE accepting it) (1)
- plan:43 Task 1 adds `normalize_host` — check ['normalize'] (no indexed siblings)

### Staged-file union (compare against the scope guard / impl handoff)
- 3 files: `engine/engine.go`, `normalize/normalize.go`, `render/render.go`

## Verdict
**HIGH findings: 7** — fix or explicitly justify each before P3b.
