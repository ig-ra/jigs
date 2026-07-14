# census test suite — what's covered

Golden-file tests over **vendored SCIP indexes** (`fixtures/<lang>-mini/index.scip`) — no
indexer needed at test time; the tool consumes the stable SCIP protobuf format, not the
indexer version. All three fixtures implement the **same mini-domain** (god-type `Store` +
engine target + external caller + test twin + ambiguous name + fallible/infallible pairs),
so shared-core behavior is exercised against all three indexers' data shapes and the
goldens stay comparable.

**Run:** `tests/run` · **Regenerate goldens:** `tests/regen.sh` (needs that language's
indexer; hand-review the golden diff before committing).

## Scenario matrix

| scenario | rust | go | ts |
|---|---|---|---|
| entry fn → boundary member accesses (edges_out) | ✓ | ✓ | ✓ |
| god-type boundary: fields + methods (`/Store#`) | ✓ | ✓ | ✓ |
| trait/impl boundary dimension (`[Store]`) | ✓ | n/a (rust-analyzer-only encoding) | n/a |
| external callers (edges_in) | ✓ | ✓ | ✓ |
| test twin excluded from floor + flagged | `#[cfg(test)]` island | `_test.go` file | `*.test.ts` file |
| visibility ladder | pub / pub(crate) / private | Exported / unexported | export / private / protected |
| multiline signature | ✓ | ✓ | ✓ |
| grep cross-check clean (0 false flags) | ✓ | ✓ | ✓ |
| scaffold candidate list | ✓ | ✓ | ✓ |
| merge: skeleton + judgment.json → census body | ✓ | ✓ | ✓ |
| verify-plan: dangling citation | ✓ | ✓ | ✓ |
| verify-plan: cited-but-not-in-census | ✓ | ✓ | ✓ |
| verify-plan: FALLIBILITY (Result/error invented) | ✓ | ✓ | **GAP** (sig-diff unsupported) |
| verify-plan: return-type diff | ✓ | via ambiguous case | **GAP** |
| verify-plan: arg-count mismatch | ✓ | ✓ | **GAP** |
| verify-plan: ambiguous pin (2 defs, differing RTs) | ✓ | ✓ | **GAP** |
| verify-plan: correct pin NOT flagged | ✓ | ✓ | n/a |
| verify-plan: deferred pin (`re-resolve at HEAD`) NOT flagged | ✓ | ✓ | n/a |
| verify-plan: loud UNSUPPORTED notice when sig-diff off | n/a | n/a | ✓ |
| doctor exit 0 (deps + indexer ok) | ✓ | — | — |
| doctor exit 1 (no indexer → Path B) | ✓ (stripped PATH) | — | — |
| doctor exit 0 with `--lang none` | ✓ | | |

Unit tests (no fixtures): `visibility` ×3 langs, `rust_test_spans` (incl.
`cfg(any(test, feature="test-utils"))`), `parse_sig` ×3 langs + deferred pin + nested
generics, `norm_rt` path stripping, `kind_of` descriptor inference (scip-typescript
kind=0), `member_label` trait encoding.

## Known gaps

- **ts verify-plan sig-diff** — unsupported in the tool (`SIG_CFG` has rust+go only); the
  report carries a loud UNSUPPORTED notice (tested). Feature work if TS repos become a
  regular igr:plan target: return-type + arg-count diff are achievable; thrown-exception
  fallibility is not in TS's type system and stays with the codex angles.
- **go pipeline goldens** — skipped until `go-mini/index.scip` is vendored (needs scip-go
  once: `tests/regen.sh` with it installed; the test suite reports the skip loudly).
- **doctor exit 2** (broken venv/protobuf) — not simulated; would require breaking the
  real venv.

## Regressions pinned (bugs these tests were built around)

1. **scip-typescript param symbols evicting the enclosing fn** — param defs share the fn's
   def line; last-write-wins in `def_by_line` dropped single-line-sig fns as containers,
   mis-attributing their edges/boundary accesses to the previous container
   (`test_ts`: `compact` owns `Store#getObject`).
2. **grep cross-check not skipping test files** — SCIP floor excludes them, grep didn't →
   false grep-only flags on go/ts test files (`test_ts`: `grep_only_flags == 0`).
3. **verify-plan `by_name` built from `display_name` only** — empty in scip-typescript, so
   every exists-in-code cite was mislabeled dangling (`test_ts_degrades_loudly`:
   `[C:run]` lands in cite-gap).
