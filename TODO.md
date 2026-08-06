# TODO

## Open items

- **`census verify-plan` → plan-internal linter (the durable half of the SAW-9947 field report).**
  Nine review rounds found 21 defects, *nearly all plan-authoring bookkeeping*; a documented rule
  (class-generalization, `plan.md` §P3b) was under-applied 4× in the same run. Prose is followed
  stochastically; an exit code is not. Move these plan-internal structural facts into
  `verify-plan` — it already parses the plan's markdown and diffs against the SCIP index, with a
  golden suite:
  - step numbering `1..N` per task, no gaps;
  - union of task `git add` == declared scope guard; every `Files:` entry appears in its task's `git add`;
  - every type/helper used in task N defined in a task `< N` (**also the forward-reference half of
    P3b angle 3 — currently paid for in codex rounds**);
  - each planned test: symbols it invokes ∩ symbols its own task modifies ≠ ∅ (vacuous-by-construction);
  - every `Expected: FAIL` carries a `fails if:` clause (presence check);
  - a new helper whose name-shape (`Normalize|Parse|Valid|Canonical`) already resolves in the same
    package → reinvention candidate (better from the index than from `rg`).
  Risk: new coupling to `superpowers:writing-plans`' markdown shape → **fail soft**
  (`STRUCTURE-UNRECOGNIZED`, never a false clean) + fixtures in the existing golden suite. ~150–200
  lines in `census.py`. Also: have `census scaffold` emit the `### Behavioral nouns` placeholder so
  the noun list is a visible hole in a generated file rather than a rule to remember.
- **`CLASS:` line on every FOLD** (trimmed from the field report's `CLASS:` + `SWEEP:` proposal).
  One phrase naming the defect class, in the invariant-6 fold format — forces the abstraction
  without adding a second performative line. Land it *after* the linter, which makes the sweep
  itself mechanical; dropping SWEEP avoids two lines of ceremony on trivial folds.

- **TS `verify-plan` sig-diff** — unsupported (`SIG_CFG` = rust+go); on TS plans P3a checks
  citations only and prints a loud UNSUPPORTED notice. Worth building now that curator (TS) is a
  production target: return-type + arg-count diff are achievable from plan code fences
  (`Promise<T>` vs `T`, `| null` unions map to the fallibility class); thrown-exception
  fallibility stays with the codex angles.
- **Dev-SKILL preflight: codex-session detect** (skipped low #5) — the impl row requires a codex
  session but the detect paragraph has no check for it.
- **Stall-based per-angle cap** (parked in `plan.md` §P3b "Pending refinement") — replace flat
  cap-3 with "loop while each round finds a NEW defect class"; adopt only with the
  class-generalization discipline, after data from real runs.

## Tools to evaluate

Candidates that overlap with parts of this plugin — check whether they replace or improve a layer:

- **[claude-octopus](https://github.com/nyldn/claude-octopus)** — orchestrates up to 10 models
  (Claude, Codex, Gemini, Ollama…) with consensus gates (75% agreement) and adversarial-review
  patterns over a Discover→Define→Develop→Deliver workflow. Overlap: multi-model adversarial
  review — compare against the single-reviewer codex loop (L1) and the workflow pipeline (L3).
- **[codemoot](https://github.com/katarmal-ram/codemoot)** — Claude + GPT as complementary
  reviewers: one plans/writes, the other critiques, iterate to consensus with automated fixing
  loops. Overlap: the produce-then-adversarially-review core of igr-dev — compare its debate loop
  against the fold/park triage discipline.
- **codex MCP** (`codex mcp-server` in the Codex CLI) — exposes Codex as an MCP server so Claude
  calls it as a tool instead of shelling out. Could replace the companion mechanics in
  `/igr:codex-adversarial-loop` (outfile polling, zsh eval gotchas, backtick/`$` stripping) with
  structured tool calls. Check: review-model/effort control, long-run streaming, and whether the
  no-codegraph constraint still holds.
