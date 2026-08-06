#!/usr/bin/env bash
# regen.sh — rebuild the vendored SCIP indexes AND the golden outputs for the census test suite.
# Run ONLY when intentionally changing fixture sources or census.py output format; hand-review the
# golden diff before committing. Requires per-language indexers:
#   rust: rust-analyzer            (brew install rust-analyzer)
#   go:   scip-go                  (go install github.com/scip-code/scip-go/cmd/scip-go@latest)
#   ts:   bunx @sourcegraph/scip-typescript   (needs bun)
# A missing indexer skips that language's regen (existing index/goldens stay).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CENSUS="$HERE/../census"
FX="$HERE/fixtures"

regen_lang() { # <lang> <fixture-dir> <files...>
  local lang=$1 dir=$2; shift 2
  local G="$dir/goldens"; mkdir -p "$G"
  local files=(); for f in "$@"; do files+=(--file "$f"); done
  "$CENSUS" harvest --index "$dir/index.scip" --repo "$dir" "${files[@]}" \
    --boundary-struct Store --grep-token store --grep-token s --lang "$lang" \
    --json "$G/skeleton.json" --out "$G/skeleton.md"
  "$CENSUS" scaffold --index "$dir/index.scip" --repo "$dir" "${files[@]}" \
    --boundary-struct Store --lang "$lang" --out "$G/scaffold.md"
  "$CENSUS" merge --skeleton "$G/skeleton.json" --judgment "$dir/judgment.json" --out "$G/census-body.md"
  # --no-fail: the fixture plans are ALL defects by design, so verify-plan exits 3; without this
  # the script's `set -e` would abort mid-regen.
  "$CENSUS" verify-plan --plan "$dir/plan-defects.md" --skeleton "$G/skeleton.json" \
    --index "$dir/index.scip" --no-fail --out "$G/verify-plan.md" >/dev/null
  echo "regen[$lang]: goldens -> $G"
}

# rust
if command -v rust-analyzer >/dev/null; then
  (cd "$FX/rust-mini" && rust-analyzer scip . --output index.scip >/dev/null 2>&1)
  regen_lang rust "$FX/rust-mini" src/engine.rs
else echo "regen[rust]: rust-analyzer missing — SKIPPED" >&2; fi

# go (binary or vendored index already present)
if command -v scip-go >/dev/null; then
  (cd "$FX/go-mini" && scip-go --output index.scip >/dev/null 2>&1)
fi
if [ -f "$FX/go-mini/index.scip" ]; then
  regen_lang go "$FX/go-mini" engine/engine.go engine/engine_test.go
else echo "regen[go]: no scip-go and no vendored index — SKIPPED" >&2; fi

# ts
if command -v bunx >/dev/null; then
  (cd "$FX/ts-mini" && bunx @sourcegraph/scip-typescript index --output index.scip >/dev/null 2>&1)
  regen_lang ts "$FX/ts-mini" src/engine.ts src/engine.test.ts
else echo "regen[ts]: bunx missing — SKIPPED" >&2; fi
