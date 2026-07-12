# igr

Angle-driven dev methods for Claude Code: harden idea→spec (census + clean-rewrite), spec→plan
(code census + mechanical diffs + judgment angles + broad pass), implement, review — plus the
`igr:workflow` PR-ladder orchestration and the codex adversarial-review loop. See
`skills/dev/SKILL.md` for the method library and `skills/workflow/SKILL.md` for the pipeline.

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
