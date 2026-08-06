# verify-plan report
plan: tests/fixtures/ts-mini/plan-defects.md  ·  index: 0.4.0  ·  census rows: 8  ·  cites: 3  ·  tasks: 4

*Deterministic checks only: (A) structured claims vs CODE — code-block sigs + [C:] cites; (B) the plan vs ITSELF — task/step structure. FALLIBILITY = high-signal (Result added/dropped). Type diffs may be intended port abstraction — verify.*

**NOTE: sig-diff UNSUPPORTED for lang=ts — citations checked only; return-type/fallibility/arg-count checks were SKIPPED. The P3b codex angles must carry the whole signature surface for this plan.**

### Dangling citations — [C:name] not found in code at all (1)
- [C:ghostFn]

### Cited but not in census — exists in code, missing from census rows (1)
- [C:run]

### FALLIBILITY mismatches (HIGH — Result invented/dropped) (0)
- none

### Other return-type diffs (candidates — may be intended abstraction) (0)
- none

### Arg-count mismatches (0)
- none

### Ambiguous pins (multiple real defs w/ differing sigs — verify manually) (0)
- none

## Plan structure (plan vs itself)

### Task numbering gaps (0)
- none

### Step numbering gaps (HIGH — a task's steps must be 1..N) (1)
- plan:46 Task 2 — steps [1, 2, 4]

### Declared file never staged (HIGH — in Files:, absent from this task's `git add`) (1)
- plan:46 Task 2 — `src/engine-normalize.test.ts` not in ['src/engine.ts']

### Task declares files but has no `git add` at all (HIGH) (0)
- none

### Forward references (HIGH — consumes a name a LATER task produces) (1)
- plan:74 Task 3 consumes `render_label` — produced by Task 4

### Undeclared consumes (name not produced by any task and not found in code) (1)
- plan:46 Task 2 consumes `never_defined_thing`

### Placeholders (HIGH — writing-plans forbids these) (1)
- plan:100 `TODO` — TODO: decide whether the label cache needs invalidating.

### `Expected: FAIL` with no `fails if:` clause (HIGH — unverifiable red stage) (1)
- plan:89 Task 3 Step 2

### Vacuous-by-construction tests (candidates — test touches nothing this task changes) (1)
- plan:102 Task 4 — changes ['render_label'], test names ['helper_unrelated']

### Reinvention candidates (new normalize/parse/validate-shaped helper — read the siblings and the stdlib BEFORE accepting it) (1)
- plan:19 Task 1 adds `normalize_host` — check ['src'], existing there: ['Config#', 'Config#maxSize', 'Config#region', 'Stats#', 'Stats#objects', 'Store#', 'Store#`<constructor>`', 'Store#bump']

### Staged-file union (compare against the scope guard / impl handoff)
- 3 files: `src/engine.ts`, `src/normalize.ts`, `src/render.ts`

## Verdict
**HIGH findings: 6** — fix or explicitly justify each before P3b.
