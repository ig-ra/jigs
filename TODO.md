# TODO

## Open items

- **TS `verify-plan` sig-diff** — unsupported (`SIG_CFG` = rust+go); on TS plans P3a checks
  citations only and prints a loud UNSUPPORTED notice. Worth building now that curator (TS) is a
  production target: return-type + arg-count diff are achievable from plan code fences
  (`Promise<T>` vs `T`, `| null` unions map to the fallibility class); thrown-exception
  fallibility stays with the codex angles.
- **Repo restructure** — move the plugin to `plugins/igr/`, add a root
  `.claude-plugin/marketplace.json` (marketplace name `jigs`) so any machine can
  `/plugin marketplace add ig-ra/jigs`; update the post-commit hook's content-dir regex; move the
  local checkout to `~/work/dev-tools/jigs` and re-register the directory marketplace.
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
