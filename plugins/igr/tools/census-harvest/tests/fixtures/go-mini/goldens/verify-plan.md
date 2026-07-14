# verify-plan report
plan: /Users/igorr/work/dev-skills/igr/tools/census-harvest/tests/fixtures/go-mini/plan-defects.md  ·  index: 0.2.7  ·  census rows: 8  ·  cites: 3

*Structured claims only (code-block sigs + [C:] cites) — deterministic. FALLIBILITY = high-signal (Result added/dropped). Type diffs may be intended port abstraction — verify.*

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
