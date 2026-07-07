---
name: herdr-pr-orchestration
description: Use when shipping a hard change as a ladder of small, worktree-isolated PRs by driving herdr worker panes from an orchestrator pane — one claude pane per unit to author spec/plan, codex to implement — across one or more sessions; or any time you orchestrate multiple long-running claude/codex agents in separate herdr panes and git worktrees.
---

# herdr PR Orchestration

## Overview
Drive a hard change as a **ladder of small PRs**, one **herdr worker pane per unit** in its own git worktree.
From the orchestrator pane you spawn workers, dispatch one-line prompts, and watch them via the `herdr` CLI.
Each unit runs **three phases, one agent each**: **Phase I — PLAN** (claude `--model opus`: write the plan, human resolves OQs, harden via `/codex-adversarial-loop`, **remember the session UUID**) → **Phase II — IMPLEMENT** (codex xhigh: implement → squash → rebase → gate → `/review`) → **Phase III — SIMPLIFY + SHIP** (claude, **resuming the Phase-I session**: `/simplify` + `/igr:code-review-skip-simplify xhigh` → push → PR → watch checks). The human watches, decides Open Questions, and opens/merges PRs.

**Core principle:** every agent runs in a pane the human can watch; nothing runs in an invisible background
shell. The orchestrator's job is dispatch + watch + report + gate — not to do the work itself.

## When to use
- A multi-PR refactor/extraction/migration where each rung is a small behavior-preserving PR.
- Any task where you drive ≥1 long-running claude/codex agent in herdr worktree panes.
- NOT for a single quick edit (just do it), and NOT without explicit human opt-in to multi-agent orchestration.

Requires `HERDR_ENV=1`. Read the `herdr` skill for the raw CLI.

The spawn helper (referred to below as `scripts/herdr-spawn-worker.sh`) ships with this skill — run it by absolute path: `${CLAUDE_PLUGIN_ROOT}/skills/herdr-pr-orchestration/scripts/herdr-spawn-worker.sh`. If `${CLAUDE_PLUGIN_ROOT}` is unset/unsubstituted, resolve it: `ls -d ~/.claude/plugins/cache/*/igr/*/skills/herdr-pr-orchestration/scripts/herdr-spawn-worker.sh | sort -V | tail -1`.

## The pipeline (per unit of work)
**Three phases, each owned by ONE agent. The hand-off currency is the claude session UUID** — Phase I captures it; Phase III resumes the SAME session. Phase II is a different agent (codex) entirely.

**Setup.** `git -C <repo-root> fetch && git pull --ff-only origin main`. Spawn with `scripts/herdr-spawn-worker.sh <ws> <label> <worktree-dir> <branch> [base-ref]` → it **pre-creates the worktree+branch** (`git worktree add -b <branch> .worktrees/<dir> <base>`, default base `origin/main`), then launches **plain `claude --model opus`** (NOT `claude --worktree`) and renames. You OWN the branch name — match the human's Linear `gitBranchName` form (e.g. `igor/saw-8194-needle-storage`), include the `saw-XXXX` id so the PR auto-links. Stack by passing a parent branch as `[base-ref]`.

### Phase I — PLAN  (agent: **claude `--model opus`**)
1. **SPEC** (only if no spec exists) — claude writes/refines it → `/codex-adversarial-loop` on the SPEC until SPEC-SOUND. If a spec already exists, skip straight to step 2.
2. **`superpowers:writing-plans`** — claude first reconciles spec-drift (copy canonical spec in, re-grep cited sites vs HEAD, report drift), then writes the plan (plan-ONLY, scope-locked).
3. **Human resolves the Open Questions** the plan surfaced. **STOP and escalate — do NOT proceed with any OQ unresolved.**
4. **`/codex-adversarial-loop` on the PLAN, `max=15`** → until **PLAN-SOUND**. **GATE:** watch each loop; report sound + any new OQs. **Escalate + STOP if (a) it hit max-15 without converging, OR (b) any OQ remains.** Clean-converge + 0 OQs → proceed.
5. **Remember the claude session UUID.** `/rename` it on launch; record the UUID — **Phase III resumes THIS session.** This is the hand-off; do not lose it.

### Phase II — IMPLEMENT  (agent: **codex `-c model_reasoning_effort=xhigh`**)
6. **Close claude, switch the pane to codex.** Clear the line w/ `Escape` first, then `C-c C-c`; if a **Keep/Remove-worktree dialog** appears, `Enter` = Keep, never Remove. **Verify `foreground_cwd` and `cd <worktree>` as its OWN command** before launching codex — claude may leave the shell at repo root. `direnv allow && codex -c model_reasoning_effort=xhigh`.
7. **Implement via `superpowers:implement-plans`, subagent-driven**, scope-locked (focused per-task checks; diff-only reviewer subagents).
8. **Squash** all work to ONE commit.
9. **Pull + rebase onto latest `origin/main`** (`git fetch` first; resolve conflicts preserving both behaviors — a sibling rung may have landed and touched the same files).
10. **Test gate, ONCE, on the rebased commit:** `cargo clippy --workspace --all-targets --all-features -- -D warnings` + `cargo fmt --all --check` + `cargo test --workspace --all-features` + `make net` + `cargo build -p <crate>` standalone; explain counters must not move. Never commit docs/generated dirs.
11. **`/review` — PR-style, vs `main`, orchestrator-driven, IN the codex pane.** The in-TUI `/review` (clean pr-style) — **NOT** the raw `codex review --base main` shell-subcommand whose terminal diff-dump the human dislikes. Watch; read the verdict. **Fix only simple + needed; park complex/risky findings and escalate.** Then STOP before push/PR.

### Phase III — SIMPLIFY + SHIP  (agent: **claude, RESUME the Phase-I session**)
12. **`claude --resume <uuid>`** (fresh pane if gone; verify cwd). **FIRST notify it: codex implemented the plan (give the commit SHA) AND already ran the full gate green → go STRAIGHT to the reviews, do NOT re-gate** (re-running `--workspace` test + net wastes ~30 min; re-gate only the touched crate IF a fix changes code). It's the planning session — it has no memory of codex's work.
13. **`/simplify` + `/igr:code-review-skip-simplify xhigh`.** `/simplify` = the `code-simplifier` agent (auto-scopes to recently-modified code, but the tree is committed → scope it to the diff: `/simplify the changes in git diff HEAD~1..HEAD`, no preserve-X essays). **Fix only simple + needed; park complex.** (A trivially-mechanical rung MAY be downgraded by the human to a lighter `/code-review high` — but this chain is the DEFAULT.)
14. **Amend** the simplify/review fixes into the single commit (PR stays one clean commit; `git add` only tracked files, never the untracked `docs/`).
15. **Push + open the PR** (if the human delegated it) → `git push -u origin <branch>` + `gh pr create --base main` (body: scope + verification + the `SAW-XXXX` link; end with the Claude Code line). The human opens PRs by default but often delegates.
16. **Watch the PR pass all checks** — poll `gh pr checks <branch>` until green; report the URL + check status. If a check fails, surface it. The human also drives panes directly — if you see something you didn't initiate, ASK, don't assume; don't auto-revert.

## Stacking PRs
When the parent PR isn't merged yet, stack the next on it: pass the **parent branch as the `[base-ref]` arg** to
the helper → `git worktree add -b <child-branch> .worktrees/<dir> <parent-branch>` bases the new branch directly
on the parent's tip (no `reset --hard` needed). After the parent merges, `git rebase origin/main` drops the
now-duplicate parent commits, leaving only the child's commits.

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
- **Recognize ghost-suggestion vs the human's real input — a ghost IS empty input, NEVER the human's message.** Both claude and codex render an AI-suggested next-prompt in the *empty* box, styled **dim/faint (ansi `^[[2m`) and/or grey (`38;2;153;153;153`)**. Plain `pane read` strips color, so a ghost looks IDENTICAL to a real typed prompt — you WILL misread it as the human's (cost a whole exit fight once). **Decision rule:** read `--format ansi` and look at the styling of the box text — **dim `[2m` or grey `153` ⇒ ghost ⇒ treat the box as EMPTY / no input** (don't attribute it to the human, don't ASK whether to keep it, don't act on its text); **normal-brightness (default fg, no `[2m`) text after `❯`/`›` ⇒ a real typed prompt** (could be the human's — then [[feedback-igor-acts-in-panes-ask]] applies: ASK, don't clobber). Detect: `pane read <pane> --format ansi | grep -iE '<the text>' | cat -v` → `^[[2m...^[[0m` = ghost. Don't waste keys "clearing" a ghost just to read; for *typing a prompt*, type right over it.
- **Exit needs a TRULY EMPTY input line, and the ghost fights you.** `C-c C-c` only exits when the box is empty; a ghost (or real pending text) *swallows* the Ctrl-C → the first C-c shows an interrupt **recap** and the agent **keeps running** (silent no-op). **`Escape` does NOT dismiss a ghost; `C-u`/`BSpace` are unsupported by `herdr send-keys`.** What works: send **`Space`** (overrides/dismisses the ghost so the box truly empties) then **`C-c C-c` immediately, as one rapid burst** — the ghost **regenerates on idle within ~2s** and will eat the next C-c if you dawdle. So: `send-keys Space; send-keys C-c; send-keys C-c` back-to-back (no sleeps between), then verify the shell prompt returned. Re-burst if the recap (not the shell) reappears. claude in a worktree *can* show a **Keep/Remove-worktree dialog** on exit → `Enter` = Keep, never Remove (Remove deletes the plan/spec); the pre-create plain-`claude` flow exits with NO dialog (verified) and leaves the shell IN the worktree.
- **Pre-create the worktree; do NOT use `claude --worktree`.** `claude --worktree NAME` force-names the branch `worktree-<NAME>` off `main` — a prefix you don't control and that buys nothing. The helper does `git worktree add -b <branch> .worktrees/<dir> <base>` then launches plain `claude`, so you own the branch name (match the Linear `gitBranchName`) + base (stack by passing a parent branch as `<base>`). Remove the worktree yourself when done (`git worktree remove`).
- **`herdr pane run` sends text+Enter but bracketed-paste often swallows the Enter** → follow with `send-keys <pane> Enter`. Long prompts = ONE line (embedded newlines submit partial). Single-quote the arg; avoid apostrophes/backticks/`$`/double-quotes inside.
- **tab-create's root pane inherits the FOCUSED pane's cwd**, not repo root → the helper's launch line `cd <worktree> && …` fixes cwd. **ALWAYS verify `foreground_cwd` and `cd <worktree>` (as its own command) before launching codex** — after claude exits the shell may be at repo ROOT (observed with `claude --worktree`; don't assume the plain-claude flow differs until verified), and launching codex there boots it in the wrong dir (cost 4 relaunches once). A worker's shell cwd also **breaks** if its worktree is later removed → cd to a live dir before reusing.
- **VISIBILITY:** run every *agent* in a pane the human can watch — never `codex exec`/`claude -p`/etc. in your own background bash. Background *waits/polls* in your bash are fine.
- New worktree blocks direnv → `direnv allow` before resuming. `cargo nextest` is often not installed locally even when CI uses it. Watch for repo flaky tests (parallel/timer) — don't chase; the sandboxed test run may always fail on auth/cert (run unsandboxed).

## Human preferences to confirm/carry (defaults from prior runs; re-confirm per human)
- Tab labels short (≤20 chars, no ticket#); worktree DIR names short (<25 chars, include the ticket id). **Branch name = match the human's Linear `gitBranchName` form** (e.g. `igor/saw-XXXX-<slug>`), NOT the `worktree-` prefix; keep `saw-XXXX` in it so the PR auto-links by substring.
- Planning claude launched with `--model opus`; `/rename` the session immediately on launch (capture UUID).
- Codex at xhigh. Implement = speedup + squash (the behavior-net + full test run ONCE on the landed commit, not per WIP commit).
- Never commit the human's gitignored docs dir or generated indexes. Worker stops before push/PR; the human opens PRs (but often drives finalize/review themselves — varies).

## Common mistakes
- Auto-proceeding to implement when an Open Question remains, or after a max-N (non-converged) loop → STOP, escalate.
- Closing/typing in a pane the human is actively driving → collision. Verify, then act; ask if unsure.
- Trusting a `--status done` wait or an output-text marker for a loop/finish → use the verify-on-fire poll.
- Running a review/agent in invisible background bash → run it in the pane.

## Helper script
`scripts/herdr-spawn-worker.sh <ws> <label> <worktree-dir> <branch> [base-ref]` encapsulates step 0 (fetch, `git worktree add -b <branch> .worktrees/<dir> <base>`, tab-create, launch plain `claude --model opus` cd'd in the worktree, `/rename`, capture session UUID). Stack by passing a parent branch as `<base>`. Run it instead of hand-typing. See its `--help`.
