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

### Diagram preview

`bin/diagram-preview --terminal kitty path/to/diagram.md` opens Markdown/Mermaid in
an 800 × 600 Kitty window. Press `q` or `Esc` to close. Requires macOS, Python 3,
[glowm](https://github.com/atani/glowm), and Kitty (Ghostty is also supported).
For AeroSpace, float Kitty windows whose title starts with `Diagram:`:

```toml
[[on-window-detected]]
if = 'test %{app-bundle-id} = net.kovidgoyal.kitty && test %{window-title} ~= ^Diagram:'
run = 'layout floating'
```

### Session usage (Claude and Codex)

`bin/usage` measures raw token buckets on both flat plans, from existing local
`~/.claude/projects` and `~/.codex/sessions` logs. Python 3, stdlib only. Every
source file is opened read-only; stdout holds text tables or JSONL and stderr
holds malformed/duplicate/synthetic/unassigned counts. No cache or network.

```sh
bin/usage summary 2026-10-07 2026-10-17
bin/usage tickets 2026-10-07 2026-10-18
bin/usage session claude:SESSION-ID
bin/usage session codex:THREAD-ID
bin/usage export 2026-10-07 2026-10-17 > /tmp/usage.jsonl
python3 -B -m unittest discover -s tests/usage -p 'test_*.py'
```

Dates are UTC, END exclusive: October 7–16 means `[2026-10-07, 2026-10-17)`.
Candidate files have mtime at least START minus one day; whole candidate files
supply metadata before exact record timestamp filtering. This relies on local
append-written logs updating mtime. Imported logs with backdated mtimes may be
missed. A session lookup uses its ID in filenames/paths and has no date cutoff.

Claude: one call per message ID, largest-output usage appearance (last on ties),
union of all tool IDs; synthetic messages excluded and counted. Context = new
input + cache read + cache write. Cache write = 5-minute + 1-hour writes; old
unsplit writes use the 5-minute proxy weight. Codex: one call per response ID in
`token_usage_record` or the same record embedded in compaction; deduped together.
`token_count` contributes meter events only, even when cumulative totals advance.
Codex context = native input; new input = native input minus cached input.
Reasoning is already inside output. Codex cache write is retained as logged;
no unobserved rule for its relationship to input is invented (sampled writes
are zero). Missing TTL/reasoning fields stay null. Never add cache reads or
reasoning to totals a second time. Tool-result sizes are characters, not tokens.

Ticket = key in the record's cwd worktree folder (suffixes allowed), otherwise
latest explicit `ticket start/resume KEY` command in that session, labelled
`via intake`, otherwise unassigned. Keyless `/igr:ticket finish` uses the same
cwd/intake evidence; without either, it stays unassigned. No session-majority
guessing. Recorded start establishes design; successful `tk step` implement
establishes develop, reviews/checks establish review; finish establishes finish.
Done-only band updates preserve finish; explicit new work may change phase.
Todo/fail markers do not advance phases. A step needs literal executable shell
arguments and a matching native `KEY line=status` success receipt. Quoted examples,
opaque code, pipeline errors and background launches do not establish a phase.
Closed heredoc bodies stay opaque; literal tk statements elsewhere in the command
can supply markers. Unclosed or unsupported heredoc syntax stays unproven.
Without a proven marker, phase remains unknown; prior proven state is retained.
Transitions stay scoped to their session and ticket; pre-marker phase is unknown.
Export retains original step/status and source path/line. Native event identity
deduplicates copies (Claude UUID, Codex ordinal; source coordinates when absent).
Different-time meter observations remain distinct. No checkpoint inference.

Summary shows both providers, model/kind splits, raw buckets, main-thread context
median/p90/max and phase totals. Context percentiles interpolate at `(n-1)*p`.
Shares and weighted figures include child calls; main context excludes children.
The ticket table has one row per ticket plus unassigned, provider column groups,
raw buckets/context/flow counts, and JSON phase totals using the same aggregate.
Null means absent evidence, not a measured zero; empty phases have zero calls.
Estimated rounds low/high and completed dispatch minutes sum estimate rows whose
start is inside the report window, separately per provider; they are nullable
local metadata, not canonical ticket size or elapsed ticket duration.
`claude_review_minutes`, between the Claude and Codex column groups, sums completed
`claude-review` actuals separately. It contributes no estimated rounds and does
not change Claude dispatch minutes. Estimate metadata uses `AGENT_ESTIMATES` when
nonempty, otherwise `~/.claude/agent-estimates.tsv`, matching the writer.
Tickets with only in-window estimate/review metadata are included: zero observed
usage, null context statistics, and the existing nullable estimate/actual columns.
Zero observed usage does not mean zero work.

A **resume start** is a session whose first recorded ticket command is resume.
It is not a proven successful handoff; compactions are separate events. Claude
session timelines include linked subagent files; Codex timelines show only the
selected **Codex thread**. All Codex child records remain in summary, tickets and
export, with native role and parent IDs. Timeline gaps are elapsed time between
recorded entries in each thread, not measured latency or human waiting.

**IGR-14 weighted proxy, uncalibrated** is Claude-only: new input 1, 5-minute
write 1.25, 1-hour write 2, cache read .1, output 5; Opus/Fable 1x, Sonnet .6x,
Haiku .2x. Unknown models are excluded from proxy sums and counted explicitly.
This is a guess for historical comparison, never API cost or plan quota. Codex
weekly-meter snapshots are timestamped account-wide events in timeline/export;
they cannot be charged to a ticket. Claude quota percent is absent from the logs.

The historical IGR-14 headlines combine two snapshots of the October 7–16 window:

| Metric | Oct 14 saved scan | Oct 16 saved scan | IGR-15 real tool |
|---|---:|---:|---:|
| Response/model-call count | 32,693 | 39,049 | 39,041 |
| Main / child Claude source files | 117 / 445 | 131 / 534 | 132 / 534 |
| Opus call share | 97.04% | 93.42% | 93.44% |
| Opus weighted share | 98.81% | 96.21% | 96.21% |
| Cache-read weighted share | 75.82% | 76.73% | 76.73% |
| Main context median | 237,605 | 251,792.5 | 251,809 |
| Weighted share at context ≥400K | 29.70% | 33.62% | 33.62% |

The 117 sessions / 238K / 30% headline belongs to Oct 14; roughly 39K responses
belongs to Oct 16. “99% of calls” conflated weighted share with call share.
The final live tool run (2026-10-17, 14.51 s) reads the source logs directly.
The Oct 16 saved 39,049 responses include nine synthetic rows: removing them
leaves 39,040 real calls; one later scanner response gives 39,041. This also
explains the small Opus call-share shift. Removing synthetic rows from the saved
main-context sample gives 251,811; the extra call gives the current 251,809,
less than .01% from the old median. Both weighted shares match after rounding.
The source-file count changes with duplicate provenance: the old scan selected
last appearances in filesystem traversal order; this tool traverses sorted paths
and selects largest output (last on ties). One main session exists in three
project files. Both the saved and current datasets have **130 unique main
session IDs**; source-file counts were 131 then and 132 now. Child source files
remain 534. These file-count differences do not imply extra model work.

Compare named ticket rows over explicit windows using the same commands.
A live `[2026-10-07, 2026-10-18)` ticket report showed IGR-13 with 85 Claude /
33 Codex calls and four Claude resume starts; IGR-15 with 95 Claude / 71 Codex
calls and one Claude resume start. IGR-15 is a partial 1.16.0 after sample,
confirmed by this run's approved contract; it is still in progress.
Historical phases remain incomplete. Plugin cohort membership requires separate
recorded version evidence, not a date guess. These reports cannot establish
complete old ticket histories, successful handoffs, exact remaining quota or a
causal improvement from an unfinished ticket.

### Repo automation

On `main` only, the git hooks auto-bump the plugin version from the conventional-commit type
(feat! → major, feat → minor, else patch) when shipped plugin content (`plugins/igr/**`)
changes. `.githooks/post-commit` amends the bump into a commit made on main (including a
squash merge); `.githooks/post-merge` adds one `chore(release)` bump commit for a
fast-forward or merge, by the strongest type landed. Branch and worktree commits never
bump. **One-time setup per clone: `./setup.sh`**
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
