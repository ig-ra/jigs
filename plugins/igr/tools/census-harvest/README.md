# census — SCIP-driven code census

One CLI (`census`) that produces a code census's **mechanical spine** deterministically from a [SCIP](https://github.com/sourcegraph/scip) index, so a model only fills the two **judgment** gaps. The P1 accelerator for the `igr:dev` **plan** method: instead of a model driving LSP/grep per symbol (~25 min, positioning landmines, flaky LSP), the tool harvests the complete substrate in seconds.

## Subcommands (the deterministic rails)
```
census doctor       preflight : check venv/protobuf/scip_pb2 (exit 2) + the indexer for --lang (exit 1)
census scaffold     P0 assist : Scope template + candidate entry symbols + boundary preview
census harvest      P1        : symbols/signatures/edges/boundary-coupling/test-flag → skeleton.json
census merge        assemble  : skeleton.json + model's judgment.json → census.md
census verify-plan  P3a       : diff the plan's factual claims (sigs/return-types/cites) vs SCIP → divergences
```
The model fills the gaps between them: **scope** (which candidates are in the change surface) and **behavior/disposition** (a compact `judgment.json` — never re-typed rows).

## `verify-plan` — mechanical P3a pre-pass
After the plan is written, this diffs its **structured factual claims** against ground truth so the model only **fixes** flagged lines instead of hand-sweeping the plan. Parses the plan's **code-fenced `fn` signatures** and **`[C:name]` citations**; resolves each against the **full SCIP index** (all symbols — incl. TO-side seam files not in the 3-file skeleton) + the skeleton (census rows). Reports:
- **dangling citations** (`[C:x]` not in code) and **cited-but-not-in-census** (in code, missing from census rows);
- **FALLIBILITY mismatches** — `Result` invented/dropped vs the real method (highest-signal — this is the class that otherwise leaks into codex review);
- **return-type diffs** — candidates (a port returning `dyn`/re-keyed type may be *intended* abstraction — verify);
- **arg-count mismatches**; **ambiguous pins** (name → several real defs, verify by hand).

Deferred pins (empty `->`, or a `/*… at HEAD */` standing in for omitted args/type) are **not** flagged. Multi-line sigs + `/* */` block comments are handled. Prose ("returns X") and behavior/branch semantics are **out of scope** — those stay for the model + P3b codex.

## Boundary — repo-agnostic
Name the **god-struct type** you decouple from: `--boundary-struct Store`. The tool matches SCIP symbols `/Store#` (fields + inherent methods) **and** `[Store]` (trait/impl methods) — so **one type name yields the complete boundary, no trait enumeration**. Works on any Rust repo (pass that repo's god-struct). `--boundary-type` is a raw-substring fallback (e.g. a module). Omit both for non-decoupling tasks.

`--grep-token store` adds a textual receiver cross-check: the harvest reports **grep-only flags** (lines grep finds but SCIP didn't resolve to a boundary member = SCIP misses or textual FPs) so the model reviews a bounded list instead of re-grepping. Comment-aware; `#[cfg(test)]` spans excluded.

## Why SCIP (not live LSP)
Same engine (rust-analyzer), batch dump not per-symbol calls: one `index.scip` has every symbol + signature + resolved reference. No positioning (pre-resolved), no per-call model cost, no server flakiness. The sibling `code-census` agent has the live-LSP fallback for when no indexer exists.

## Languages (`--lang rust | go | ts | none`)
Consumes SCIP; swap the indexer per language, and `--lang` selects a per-language **adapter** (test detection, visibility, signature source, sig parsing). The SCIP symbol/anchor/edge skeleton is generic; the adapters carry the per-language bits.

| lang | indexer | test-flag | visibility | signature | boundary (`--boundary-struct`) | verify-plan sig-diff |
|---|---|---|---|---|---|---|
| **rust** | `rust-analyzer scip` | `#[cfg(test)]` spans | `pub`/`pub(crate)` | `signature_documentation` | `/X#` + `[Trait]impl` | ✓ (`Result` fallibility) |
| **go** | `scip-go` (or `go run github.com/scip-code/scip-go/cmd/scip-go@latest`) | `*_test.go` files | exported = Name capitalized | doc-fence | `/X#` (struct+methods) | ✓ (`error` fallibility) |
| **ts** | `scip-typescript` (or `bunx @sourcegraph/scip-typescript`) | `*.test/.spec.ts(x)`, `__tests__/` | `export`/`private` from source line | `documentation` code-fence; kind inferred from descriptor | `/X#` (class+members) | — (citations only) |
| **none** | any SCIP | — | `?` | best-effort | `/X#` | — |

Notes: Go/TS drop Rust's `[Trait]impl` boundary dimension (they have no such encoding). TS visibility is read from the **source line** (scip-typescript's hover omits `export`/`private`); Go visibility is the name-capitalization rule. verify-plan's signature diffing runs for rust+go (keyword+fallibility model); ts gets citation checks only. All three validated end-to-end (rust-analyzer / `bunx scip-typescript` / `go run scip-go`).

## Tests
Golden-file suite over vendored SCIP fixtures (rust/go/ts, same mini-domain each): `tests/run`.
Coverage matrix + known gaps: `tests/SCENARIOS.md`. Regenerate goldens (intentional output
changes only): `tests/regen.sh`.

## Setup
Run the preflight — it tells you exactly what (if anything) is missing:
```
./census doctor --lang rust      # rust | go | ts | none
```
- **Python ≥ 3.12** on PATH as `python3` — census.py uses 3.12 f-string syntax; the wrapper refuses to build the venv with an older interpreter (clear message, not a `SyntaxError`).
- **venv + protobuf** — **auto-built on first `census` call** (the wrapper creates a tool-local `venv/` from `requirements.txt`, one time; gitignored, rebuilt per plugin version). No manual step. Opt out with `CENSUS_NO_BOOTSTRAP=1`, then build it yourself: `python3 -m venv venv && venv/bin/pip install -r requirements.txt`.
- **indexer on PATH** — you must install this (external, per-language; the tool can't): `rust-analyzer` (rust), `scip-go` (go), `scip-typescript` (ts). `doctor` exit **1** = missing → the agent's live-LSP **Path B**. Exit **2** = venv/protobuf/scip_pb2 broken → tool fault, fix before use.
- `scip_pb2.py` is vendored (compiled from `scip.proto`); regenerate only if the proto changes (keep `requirements.txt` protobuf pin in sync):
  `venv/bin/pip install grpcio-tools && venv/bin/python -m grpc_tools.protoc -I. --python_out=. scip.proto`

## Usage
```
# 1. index (seconds; current HEAD) — pick the indexer for the language
rust-analyzer scip /path/to/repo --output /tmp/index.scip          # rust
scip-go --output /tmp/index.scip                                    # go   (run in the module)
go run github.com/scip-code/scip-go/cmd/scip-go@latest --output /tmp/index.scip   # go, no perm-install (needs go toolchain)
scip-typescript index --output /tmp/index.scip                      # ts   (run in the project; reads tsconfig)
bunx @sourcegraph/scip-typescript index --output /tmp/index.scip    # ts, zero-install (needs bun) — bin first, else bunx
# then pass --lang rust|go|ts to harvest/scaffold below

# 2. (optional) scaffold the P0 Scope
census scaffold --index /tmp/index.scip --repo /path/to/repo \
    --file src/store/tiered_compaction.rs --boundary-struct Store --boundary-struct StreamState \
    --out prefix-census.md

# 3. harvest the skeleton
census harvest --index /tmp/index.scip --repo /path/to/repo \
    --file src/store/tiered_compaction.rs [--file src/store.rs] \
    --boundary-struct Store --boundary-struct StreamState \
    --grep-token store --grep-token stream --lang rust \
    --json skeleton.json --out skeleton.md

# 4. model writes judgment.json  { "file:line": {"behavior": "...", "disposition": ""}, ... }

# 5. render
census merge --skeleton skeleton.json --judgment judgment.json --out census-body.md

# 6. (P3a) after the plan is written, verify its claims vs code
census verify-plan --plan prefix-plan.md --skeleton skeleton.json --index /tmp/index.scip
```

## What it does NOT do (judgment — the model's job)
- **scope** — which harvested symbols are in the change surface.
- **behavior?** — read the body, flag branches/ordering/side-effects.
- **disposition** — stays / moves / seam / rename.
