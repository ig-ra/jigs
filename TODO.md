# TODO

## Open items

- **`census scaffold` should emit the `### Behavioral nouns` placeholder** in its `## Scope`
  template, so the noun list is a visible hole in a generated file rather than a rule to remember.
  (The P0/P1 prose landed in v1.7.0; this makes it structural. Same move as the plan linter.)
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
