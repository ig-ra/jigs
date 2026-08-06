# jigs

A jig holds the work steady so the cut lands true. This repo collects **jigs for coding
agents** — methods, skills, and tools that make agent dev work repeatable, precise, and
adversarially checked. Today it contains one Claude Code plugin (**igr**) and its tooling;
codex-side artifacts and runtime-agnostic skills will join as they harden.

## What's here

### The igr plugin — angle-driven dev methods

The core idea: a generic "review this" pass plateaus after one or two findings. Directing a
reviewer at **one failure-class at a time** (an *angle*) and looping it until that class is
exhausted catches real bugs a broad pass misses. The plugin packages that idea into four dev
methods plus the machinery around them, arranged in three strict layers:

| layer | what | where |
|---|---|---|
| **L3 — pipeline** | `igr:workflow` — ships a change as a ladder of small worktree-isolated PRs, sequencing the L2 methods over a pluggable orchestration backend (default: `igr:herdr-workflow`, herdr panes + git worktrees) | `plugins/igr/skills/workflow/`, `…/skills/herdr-workflow/` |
| **L2 — methods** | `igr:dev` — four independent methods, one per artifact kind (below) | `plugins/igr/skills/dev/` |
| **L1 — mechanism** | `/igr:codex-adversarial-loop` — runs ONE (target, focus) review loop against the Codex companion until clean or capped; folds minimal fixes, parks scope-creep as Open Questions | `plugins/igr/commands/codex-adversarial-loop.md` |

Each layer knows nothing about the one above it; the seams are explicit (focus strings down,
ordering/git up).

### The four methods (`/igr:<method> <target>`)

- **`brainstorm`** (idea → spec) — EXPLORATORY hardening: a census discovers the spec's review
  angles (capped at 5 risk-ranked clusters), per-angle codex loops exhaust each failure-class,
  the owner resolves every parked Open Question, then a load-bearing **clean-rewrite** + re-census
  + completeness critic. Exits only through a checklist gate: zero Open Questions, zero run
  records (deterministic grep), COVERAGE-COMPLETE.
- **`plan`** (spec → plan) — a plan's #1 failure mode is asserting wrong facts about the code, so
  the method grounds the plan in a **code census** first (SCIP-harvested ground truth), then
  reviews via cheap mechanical diffs (`census verify-plan`) + exactly three judgment angles
  (contracts/behavior/green-ordering, capped 3 rounds each) + one broad closing pass. Budget: 10
  codex rounds per stage. Refuses dirty specs at intake.
- **`impl`** (plan → code) — codex session, TDD, subagent-driven, tunable gate/squash cadence;
  the test gate is always the target repo's own.
- **`review`** (diff → fixed code) — claude session: `/simplify` for cleanup lenses, then the
  vendored `code-review-skip-simplify` workflow for correctness angles + conventions (skipping
  exactly what `/simplify` covered), then fix-or-park. Scope is always the branch vs its
  merge-base.

### The census tool (`plugins/igr/tools/census-harvest/`)

A Python CLI that turns a [SCIP](https://github.com/sourcegraph/scip) index into a code census's
mechanical spine in seconds — symbols, exact signatures, call edges, boundary coupling — so the
model spends tokens only on judgment (scope, behavior-sensitivity, disposition).
Language-neutral core with adapters for **Rust** (`rust-analyzer scip`), **Go** (`scip-go`), and
**TypeScript** (`scip-typescript` via `bunx`). Subcommands: `scaffold` (P0 scope template),
`harvest` (skeleton), `merge` (skeleton + judgment → census), `verify-plan` (the P3a mechanical
pre-pass — a plan's factual claims diffed against the index, **plus** the plan linted against
itself: step numbering, staged-vs-declared files, forward references, placeholders, red-stage
validity; exit 3 on HIGH findings, fails soft when the plan shape isn't recognized), `doctor`
(preflight with a strict exit-code contract). Golden-file test suite over vendored indexes for all
three languages: `tests/run`; coverage matrix in `tests/SCENARIOS.md`.

### The vendored review workflow (`plugins/igr/workflows/code-review-skip-simplify.js`)

A fork of Claude Code's built-in `/code-review` workflow with two deltas (marked inline):
cleanup lenses reduced to Conventions-only (pair it with `/simplify`, which owns the rest), and
explicit per-level reasoning effort on every finder/verifier agent. The file header records the
upstream generation it was synced from and the re-vendor recipe.

### Repo automation

`.githooks/post-commit` auto-bumps the plugin version from the conventional-commit type
(feat! → major, feat → minor, else patch) and amends the bump into HEAD — for any commit
touching shipped plugin content (`plugins/igr/**`). **One-time setup per clone: `./setup.sh`**
(git cannot auto-enable hooks on clone).

## Install / update

This repo is its own Claude Code **marketplace** (`.claude-plugin/marketplace.json`, name `jigs`):

- Any machine: `/plugin marketplace add ig-ra/jigs` then `/plugin install igr@jigs`.
- Local development: add it as a **directory** marketplace instead (live edits, no push needed):
  `/plugin marketplace add ~/work/dev-tools/jigs`. After committing changes: `/plugin update igr`
  + `/reload-plugins`.

External plugin dependencies (gated at runtime, not in plugin.json): `superpowers`, `codex`
(companion), and — for the default workflow backend — a herdr pane.

## Roadmap / open items

See [TODO.md](TODO.md).
