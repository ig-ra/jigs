---
name: herdr-workflow
description: The herdr layer on top of the agnostic igr:workflow — runs igr:workflow's PR-ladder pipeline on herdr, implementing its backend operations (spawn-worker, dispatch, watch-finish, swap-agent, resume-session, shape-git, ship) with herdr panes + git worktrees. Use to ship a change as a ladder of worktree-isolated PRs when you are inside herdr. Owns the herdr mechanics + gotchas; the pipeline itself (phases, methods, gates) lives in igr:workflow.
---

# herdr-workflow — the herdr layer for igr:workflow

## What this is

A **thin herdr specialization on top of the generic `igr:workflow`**. `igr:workflow` is the
orchestrator-agnostic **core** — it owns the *pipeline* (phase order, which `/igr` method runs each
phase, gates, hand-off) and defines a **backend interface**. This skill is the **herdr binding**: it
runs that pipeline on herdr, implementing each backend operation with herdr panes + git worktrees, and
owns the herdr **mechanics + gotchas**. It contains **no pipeline narrative and no work-step method
choices** (those live in `igr:workflow` + the caller's `/igr:plan|impl|review`).

**To run a herdr PR ladder:** read `igr:workflow` for the pipeline (phases/gates/hand-off), and use
the operations below whenever it calls a backend op. Standalone use: you can drive these mechanics
directly, but the *what/when* is not defined here.

**Core principle:** every *agent* runs in a pane the human can watch — never an invisible background
shell (`codex exec`/`claude -p`/background bash). Background *waits/polls* are fine.

## Preflight (single gate — verify before any operation)

Run inside a **herdr pane**: `[ "$HERDR_ENV" = 1 ] && [ -n "$HERDR_PANE_ID" ]`. Unset → STOP: start from a herdr pane. **Being in a pane implies both herdr prerequisites** — so this is ONE check, not two:
- the **`herdr` CLI/binary** — you are running under it; and
- its bundled **`herdr` skill** (the raw-CLI reference) — ships *with* herdr (`github.com/ogulcancelik/herdr`, `SKILL.md`), so it rides along with the install. **Read it for the CLI verbs.**

(Edge case: if the `herdr` skill is not in your available skills despite being in a pane, install it from the herdr repo into your skills dir — do not reimplement the CLI inline. Don't vendor it — it's versioned with herdr.)

The spawn helper (referred to below as `scripts/herdr-spawn-worker.sh`) ships with this skill — run it by absolute path: `${CLAUDE_PLUGIN_ROOT}/skills/herdr-workflow/scripts/herdr-spawn-worker.sh`. If `${CLAUDE_PLUGIN_ROOT}` is unset/unsubstituted, resolve it: `ls -d ~/.claude/plugins/cache/*/igr/*/skills/herdr-workflow/scripts/herdr-spawn-worker.sh | sort -V | tail -1`.

## Backend operations (herdr implementation)

Each maps a `igr:workflow` backend operation to concrete herdr mechanics. Read the matching **Gotcha**
before running any of them — the gotchas are where the real failures live.

### spawn-worker
`git -C <repo-root> fetch && git pull --ff-only origin main`, then
`scripts/herdr-spawn-worker.sh <ws> <label> <worktree-dir> <branch> [base-ref]` → it **pre-creates the
worktree+branch** (`git worktree add -b <branch> .worktrees/<dir> <base>`, default base `origin/main`),
launches **plain `claude --model "${IGR_PLAN_MODEL:-opus}"`** (NOT `claude --worktree`) cd'd in the worktree, `/rename`s,
and prints the pane id, worktree path, branch, and the **claude session UUID** (the session handle).
You OWN the branch name — match the tracker's `gitBranchName` form (e.g. `igor/saw-8194-needle-storage`),
include the `saw-XXXX` id so the PR auto-links. **Stack** by passing a parent branch as `[base-ref]`.

### dispatch
`herdr pane run <pane> '<ONE-LINE prompt>'` then `herdr pane send-keys <pane> Enter` (bracketed-paste
often swallows the Enter). One line only — embedded newlines submit partial. Single-quote the arg;
avoid apostrophes/backticks/`$`/double-quotes inside.

### watch-finish
Background **POLL for status ≠ `working`** (never `herdr wait agent-status --status done`), then
**verify on fire** — see the Gotchas (the codex loop / `/review` / subagent implement all flicker
working↔idle, so watch the pane FOOTER and re-poll). Never trust a scrollback text marker.

### swap-agent  (claude → codex, and back)
Close the current agent, then launch the next in the SAME pane. Close: clear the line FIRST
(`send-keys <pane> Escape`), THEN `C-c C-c`; a ghost fights you — see the Gotcha for the
`Space`+`C-c C-c` burst. If a **Keep/Remove-worktree dialog** appears, `Enter` = Keep, never Remove.
**Verify `foreground_cwd` and `cd <worktree>` as its OWN command** before launching (the shell may be
at repo root). codex: `direnv allow && codex ${IGR_IMPL_MODEL:+--model "$IGR_IMPL_MODEL"} -c model_reasoning_effort="${IGR_IMPL_EFFORT:-xhigh}"` (model+effort from the `IGR_IMPL_*` env — see `/igr:impl`; independent of the review model).

### resume-session  (the Phase I→III hand-off)
`claude --resume <uuid|"name">` (fresh pane if the old one is gone; **verify cwd**). The resumed
session has **no memory** of what a different agent (codex) did in between — **first notify it**
(e.g. "codex implemented the plan at SHA X and already ran the full gate green → go straight to the
reviews, do NOT re-gate"; re-gate only the touched crate if a fix changes code). `codex resume <uuid>`
for codex.

### shape-git  (squash / rebase / stack / amend / gate)
- **Squash** all work to ONE commit.
- **Pull + rebase onto latest `origin/main`** (`git fetch` first; resolve conflicts preserving BOTH
  behaviors — a sibling rung may have landed on the same files).
- **Test gate, ONCE, on the rebased commit** (repo-specific — e.g. sawmills:
  `cargo clippy --workspace --all-targets --all-features -- -D warnings` + `cargo fmt --all --check`
  + `cargo test --workspace --all-features` + `make net` + `cargo build -p <crate>` standalone;
  explain-counters must not move). Never commit docs/generated dirs.
- **Amend** review/simplify fixes into the single commit (`git add` only tracked files, never untracked
  `docs/`) — the PR stays one clean commit.
- **Stack:** pass the **parent branch as `[base-ref]`** to spawn-worker → the child branch bases
  directly on the parent's tip (no `reset --hard`). After the parent merges, `git rebase origin/main`
  drops the now-duplicate parent commits, leaving only the child's.

### ship
`git push -u origin <branch>` + `gh pr create --base main --body-file <f>` (body: scope + verification
+ the `SAW-XXXX` link; end with the Claude Code line). The human opens PRs by default but often
delegates. Then **watch checks**: poll `gh pr checks <branch>` until green; report URL + status;
surface any failure.

## Quick reference
| Need | Do |
|---|---|
| Spawn worker | `scripts/herdr-spawn-worker.sh <ws> <label> <worktree-dir> <branch> [base-ref]` (pre-creates worktree+branch, plain claude) |
| Send a prompt | `herdr pane run <pane> '<ONE-LINE prompt>'` then `herdr pane send-keys <pane> Enter` |
| Watch a finish | background POLL for status≠`working` (NOT `--status done` — see Gotchas) |
| Tell ghost from human input | `pane read <pane> --format ansi \| grep '<text>' \| cat -v` → dim `^[[2m` or grey `153` = **ghost = empty/no input** (not the human's); normal-bright after `❯`/`›` = real typed prompt |
| Exit claude past a ghost | `send-keys Space; send-keys C-c; send-keys C-c` (rapid burst — ghost regenerates in ~2s + swallows C-c; Escape/C-u/BSpace don't work) |
| Close agent | clear line FIRST (`send-keys <pane> Escape`), THEN `send-keys <pane> C-c C-c`; if a Keep/Remove-worktree dialog appears, `Enter` = Keep |
| Resume | `claude --resume <uuid\|"name">` · `codex resume <uuid>` |
| Review (codex) | `/review` IN the codex pane (pr-style, vs main) — NOT the `codex review --base main` shell diff-dump |
| Review (claude) | `/simplify` + `/igr:code-review-skip-simplify xhigh` (post-codex-review) |
| Open PR (if delegated) | `git push -u origin <branch>` + `gh pr create --base main --body-file <f>` |
| Watch PR checks | poll `gh pr checks <branch>` until green; report status + URL |
| Hand off Phase I→III | capture the claude session UUID (`/rename` + record); Phase III = `claude --resume <uuid>` |

## Gotchas (each = a real failure that cost turns)
- **Finish-watch = background POLL for status ≠ `working`, NEVER `herdr wait agent-status --status done`.** `--status done` HANGS when an agent finishes into `idle` — which it does whenever you've recently *read* that pane (`done` = "finished AND pane unseen"; a seen pane goes `idle`). Poll: `for i in $(seq 1 N); do st=$(herdr pane get <pane>|…agent_status); [ "$st" != working ] && [ -n "$st" ] && break; sleep 12; done` (run_in_background).
- **The codex-adversarial-loop, codex `/review`, AND subagent-driven codex implement all flicker status working↔idle between internal steps** (the orchestrator goes idle WAITING on a task-agent/companion for minutes), so a raw status-poll fires EARLY. **Watch the codex pane FOOTER instead** — fire only when status≠`working` AND the footer shows no `Working`/`esc to interrupt`/`shell`, settled ≥2; on fire READ + VERIFY (converged/committed vs mid-step) and re-poll. `herdr wait output --source recent` scans STALE scrollback → false-fires; don't trust text markers.
- **Recognize ghost-suggestion vs the human's real input — a ghost IS empty input, NEVER the human's message.** Both claude and codex render an AI-suggested next-prompt in the *empty* box, styled **dim/faint (ansi `^[[2m`) and/or grey (`38;2;153;153;153`)**. Plain `pane read` strips color, so a ghost looks IDENTICAL to a real typed prompt — you WILL misread it as the human's (cost a whole exit fight once). **Decision rule:** read `--format ansi` and look at the styling of the box text — **dim `[2m` or grey `153` ⇒ ghost ⇒ treat the box as EMPTY / no input** (don't attribute it to the human, don't ASK whether to keep it, don't act on its text); **normal-brightness (default fg, no `[2m`) text after `❯`/`›` ⇒ a real typed prompt** (could be the human's — the human often drives panes directly: ASK before typing over, clearing, or acting on it — never clobber). Detect: `pane read <pane> --format ansi | grep -iE '<the text>' | cat -v` → `^[[2m...^[[0m` = ghost. Don't waste keys "clearing" a ghost just to read; for *typing a prompt*, type right over it.
- **Exit needs a TRULY EMPTY input line, and the ghost fights you.** `C-c C-c` only exits when the box is empty; a ghost (or real pending text) *swallows* the Ctrl-C → the first C-c shows an interrupt **recap** and the agent **keeps running** (silent no-op). **`Escape` does NOT dismiss a ghost; `C-u`/`BSpace` are unsupported by `herdr send-keys`.** What works: send **`Space`** (overrides/dismisses the ghost so the box truly empties) then **`C-c C-c` immediately, as one rapid burst** — the ghost **regenerates on idle within ~2s** and will eat the next C-c if you dawdle. So: `send-keys Space; send-keys C-c; send-keys C-c` back-to-back (no sleeps between), then verify the shell prompt returned. Re-burst if the recap (not the shell) reappears. claude in a worktree *can* show a **Keep/Remove-worktree dialog** on exit → `Enter` = Keep, never Remove (Remove deletes the plan/spec); the pre-create plain-`claude` flow exits with NO dialog (verified) and leaves the shell IN the worktree.
- **Pre-create the worktree; do NOT use `claude --worktree`.** `claude --worktree NAME` force-names the branch `worktree-<NAME>` off `main` — a prefix you don't control and that buys nothing. The helper does `git worktree add -b <branch> .worktrees/<dir> <base>` then launches plain `claude`, so you own the branch name (match the Linear `gitBranchName`) + base (stack by passing a parent branch as `<base>`). Remove the worktree yourself when done (`git worktree remove`).
- **`herdr pane run` sends text+Enter but bracketed-paste often swallows the Enter** → follow with `send-keys <pane> Enter`. Long prompts = ONE line (embedded newlines submit partial). Single-quote the arg; avoid apostrophes/backticks/`$`/double-quotes inside.
- **tab-create's root pane inherits the FOCUSED pane's cwd**, not repo root → the helper's launch line `cd <worktree> && …` fixes cwd. **ALWAYS verify `foreground_cwd` and `cd <worktree>` (as its own command) before launching codex** — after claude exits the shell may be at repo ROOT (observed with `claude --worktree`; don't assume the plain-claude flow differs until verified), and launching codex there boots it in the wrong dir (cost 4 relaunches once). A worker's shell cwd also **breaks** if its worktree is later removed → cd to a live dir before reusing.
- **VISIBILITY:** run every *agent* in a pane the human can watch — never `codex exec`/`claude -p`/etc. in your own background bash. Background *waits/polls* in your bash are fine.
- New worktree blocks direnv → `direnv allow` before resuming. `cargo nextest` is often not installed locally even when CI uses it. Watch for repo flaky tests (parallel/timer) — don't chase; the sandboxed test run may always fail on auth/cert (run unsandboxed).

## Human preferences to confirm/carry (defaults from prior runs; re-confirm per human)
- Tab labels short (≤20 chars, no ticket#); worktree DIR names short (<25 chars, include the ticket id). **Branch name = match the human's Linear `gitBranchName` form** (e.g. `igor/saw-XXXX-<slug>`), NOT the `worktree-` prefix; keep `saw-XXXX` in it so the PR auto-links by substring.
- Planning claude launched with `--model "${IGR_PLAN_MODEL:-opus}"` (env knob, default opus); `/rename` the session immediately on launch (capture UUID).
- Codex at xhigh. Implement = speedup + squash (the behavior-net + full test run ONCE on the landed commit, not per WIP commit).
- Never commit the human's gitignored docs dir or generated indexes. Worker stops before push/PR; the human opens PRs (but often drives finalize/review themselves — varies).

## Common mistakes
- Trusting a `--status done` wait or an output-text marker for a loop/finish → use the verify-on-fire poll.
- Running a review/agent in invisible background bash → run it in the pane.
- Closing/typing in a pane the human is actively driving → collision. Verify, then act; ask if unsure.
- Reimplementing the pipeline here (phase order, which method to run, gates) → that is `igr:workflow`. This skill is mechanics only.

## Helper script
`scripts/herdr-spawn-worker.sh <ws> <label> <worktree-dir> <branch> [base-ref]` encapsulates spawn-worker (fetch, `git worktree add -b <branch> .worktrees/<dir> <base>`, tab-create, launch plain `claude --model opus` cd'd in the worktree, `/rename`, capture session UUID). Stack by passing a parent branch as `<base>`. Run it instead of hand-typing. See its `--help`.
