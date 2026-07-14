# verify-plan report
plan: /Users/igorr/work/dev-skills/igr/tools/census-harvest/tests/fixtures/rust-mini/plan-defects.md  ·  index: 0.0.0 (7ae18ed96a 2026-07-05)  ·  census rows: 9  ·  cites: 3

*Structured claims only (code-block sigs + [C:] cites) — deterministic. FALLIBILITY = high-signal (Result added/dropped). Type diffs may be intended port abstraction — verify.*

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
