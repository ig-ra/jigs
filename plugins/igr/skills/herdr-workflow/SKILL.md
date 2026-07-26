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

**Create-or-reuse:** the helper now reuses instead of failing — reuses in place if `<dir>` is already
a worktree on `<branch>`, adds a worktree from an existing branch, or creates `-b` when neither exists
(errors only if `<dir>` is checked out on a *different* branch). This is the standalone re-entry path
(`/igr:wf:spawn` on an existing ticket).

### dispatch
`herdr agent prompt <pane> '<ONE-LINE prompt>'` — submits **atomically** (encodes the Enter itself → no
separate `send-keys Enter`; kills the bracketed-paste Enter-swallow). Add `--wait --until idle,blocked
--timeout MS` to block until the turn settles, but ONLY for a **non-flickery** turn (a single
planning/review turn, no subagents). For a **flickery** dispatch (codex impl / the adversarial loop /
any subagent-driven turn) submit WITHOUT `--wait` and watch the finish with the footer-settle discipline
(see watch-finish) — `--wait --until idle` fires EARLY on the mid-work idle flicker, same as a raw poll.
Still one line only (embedded newlines submit partial); single-quote the arg; avoid
apostrophes/backticks/`$`/double-quotes. Legacy fallback if `agent prompt` is unavailable: `pane run
<pane> '<prompt>'` + `pane send-keys <pane> Enter`.

### watch-finish
**Simple (non-flickery) finish** — one planning/review turn, no subagents: `herdr agent wait <pane>
--until idle,blocked --timeout MS` (event-driven; replaces the sleep-poll). **Flickery finish** — the
codex adversarial loop / `/review` / any subagent-driven implement flicker working↔idle mid-work, so
BOTH `agent wait --until idle` AND a raw status poll fire EARLY. There, keep the discipline: watch the
pane FOOTER (fire only when status≠`working` AND no `Working`/`esc to interrupt`/`shell`, settled ≥2),
then READ + VERIFY on fire and re-poll. Never `herdr wait agent-status --status done` (hangs on a seen
pane → `idle`), and never trust a scrollback text marker (`wait-output` matches the command-echo too).

### swap-agent  (claude → codex, and back)
Close the current agent, then launch the next in the SAME pane. Close: clear the line FIRST
(`send-keys <pane> Escape`), THEN `C-c C-c`; a ghost fights you — see the Gotcha for the
`Space`+`C-c C-c` burst. If a **Keep/Remove-worktree dialog** appears, `Enter` = Keep, never Remove.
**Verify `foreground_cwd` and `cd <worktree>` as its OWN command** before launching (the shell may be
at repo root). codex: `direnv allow && codex ${IGR_IMPL_MODEL:+--model "$IGR_IMPL_MODEL"} -c model_reasoning_effort="${IGR_IMPL_EFFORT:-xhigh}"` (model+effort from the `IGR_IMPL_*` env — see `/igr:impl`; independent of the review model).

### spawn-codex  (fresh codex in a new pane — the standalone impl handoff)
For `/igr:wf:spawn impl` (not the in-pipeline swap): open a **new pane in the same workspace** running
codex in the (reused) worktree, rather than swapping the current pane. Use the **worker helper with
`--agent codex`** — it bakes `cd <worktree>` into the launch so it can't be dropped (dropping it lands
codex on `main`, the recurring failure); it branches the launch line by agent and returns right after
launch (no ❯ boot-wait, no `/rename` — those are claude-only):
1. `herdr-spawn-worker.sh --agent codex <ws> <label> <worktree-dir> <branch> [base]` — create-or-reuse
   the worktree, tab-create, and launch `cd <worktree> && direnv allow && codex …IGR_IMPL_*…` (model+effort
   from `IGR_IMPL_*`, the swap-agent line above) as ONE command. Prints the pane id, then STOPS.
2. **Readiness** — `herdr agent wait <pane> --until idle --timeout 120000` gets codex to "booted", THEN
   `herdr pane read <pane>` and CHECK: a **fresh worktree pops codex's "Do you trust this directory?"
   modal, which also reports `idle`** — if it's up, `herdr pane send-keys <pane> Enter` (default = Yes)
   and `agent wait --until idle` again. Dispatch only once the read shows codex's real input box. **Never
   dispatch on bare idle** (see the codex-trust gotcha — status is noisy post-accept, flips through
   `done`, so confirm by READ not status).
3. Dispatch the one-line handoff **atomically**: `herdr agent prompt <pane> 'read <abs handoff>,
   implement per it; stop before push'` (no separate Enter). Impl flickers → watch finish via the
   footer-settle discipline, NOT `agent wait --until idle`.
The plan-claude pane **stays alive** in the same worktree → it is the reviewer (Phase III native
`/igr:review`). No swap-agent self-kill, no resume-session. Because **codex has no `igr` plugin**, the
dispatch is a handoff doc claude authored (`references/impl-handoff-template.md`), NOT `/igr:impl`.

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
| Spawn worker | `scripts/herdr-spawn-worker.sh [--agent claude\|codex] <ws> <label> <worktree-dir> <branch> [base-ref]` (create-or-reuse worktree+branch; `cd` baked into launch) |
| Reuse a worktree | `herdr-spawn-worker.sh` auto-reuses if `<dir>`/`<branch>` already exist (no `exit 1`) |
| Spawn fresh codex (impl) | `herdr-spawn-worker.sh --agent codex …` — see `### spawn-codex`: baked-`cd` launch → readiness (wait-idle → clear codex trust modal → confirm by read) → handoff dispatch |
| Send a prompt | `herdr agent prompt <pane> '<ONE-LINE prompt>'` (atomic; no separate Enter). Add `--wait --until idle,blocked --timeout MS` only for a NON-flickery turn. Legacy: `pane run` + `send-keys Enter` |
| Watch a finish | simple turn: `herdr agent wait <pane> --until idle,blocked --timeout MS`. Flickery (codex loop/`/review`/subagent): footer-settle + verify — `agent wait --until idle` fires early too (see Gotchas) |
| Detect a terminal marker | `herdr pane wait-output <pane> (--match TEXT\|--regex PAT) --timeout MS` — server-side, ~100ms; matches the command-echo too, so use an OUTPUT-only string |
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
- **Finish-watch: `herdr agent wait <pane> --until idle,blocked --timeout MS` for a SIMPLE turn (event-driven, no sleep-poll); NEVER `herdr wait agent-status --status done`.** `--status done` HANGS when an agent finishes into `idle` — which it does whenever you've recently *read* that pane (`done` = "finished AND pane unseen"; a seen pane goes `idle`). Legacy poll if `agent wait` is unavailable: `for i in $(seq 1 N); do st=$(herdr pane get <pane>|…agent_status); [ "$st" != working ] && [ -n "$st" ] && break; sleep 12; done` (run_in_background).
- **The codex-adversarial-loop, codex `/review`, AND subagent-driven codex implement all flicker status working↔idle between internal steps** (the orchestrator goes idle WAITING on a task-agent/companion for minutes) — so `agent wait --until idle` fires EARLY here just like a raw poll (it waits on the SAME flickering status; it does NOT know "settled"). **Watch the codex pane FOOTER instead** — fire only when status≠`working` AND the footer shows no `Working`/`esc to interrupt`/`shell`, settled ≥2; on fire READ + VERIFY (converged/committed vs mid-step) and re-poll. `herdr pane wait-output` scans recent scrollback INCLUDING the echoed command line → false-fires; don't trust text markers for finish.
- **Fresh worktree → codex "Do you trust this directory?" modal that reads as `idle` (verified).** codex trusts per EXACT path (`~/.codex/config.toml [projects."<path>"].trust_level`); a new `.worktrees/<dir>` is never in that list → on launch codex shows a trust modal ("…Press enter to continue") AND reports `agent_status: idle`. So `agent wait --until idle` FALSE-fires and a dispatch types INTO the modal. Codex readiness = wait-idle → `pane read` → if the modal is up, `send-keys <pane> Enter` (default = Yes) and wait-idle again → dispatch only when the read shows codex's real input box. Status is noisy post-accept (flips through `done`) → confirm by READ, never status alone. (The same trust-prompt shape can hit claude on a brand-new folder — if the `❯` wait-output ever times out on a fresh worktree, a claude trust dialog is the likely cause; clear it then re-wait.)
- **Recognize ghost-suggestion vs the human's real input — a ghost IS empty input, NEVER the human's message.** Both claude and codex render an AI-suggested next-prompt in the *empty* box, styled **dim/faint (ansi `^[[2m`) and/or grey (`38;2;153;153;153`)**. Plain `pane read` strips color, so a ghost looks IDENTICAL to a real typed prompt — you WILL misread it as the human's (cost a whole exit fight once). **Decision rule:** read `--format ansi` and look at the styling of the box text — **dim `[2m` or grey `153` ⇒ ghost ⇒ treat the box as EMPTY / no input** (don't attribute it to the human, don't ASK whether to keep it, don't act on its text); **normal-brightness (default fg, no `[2m`) text after `❯`/`›` ⇒ a real typed prompt** (could be the human's — the human often drives panes directly: ASK before typing over, clearing, or acting on it — never clobber). Detect: `pane read <pane> --format ansi | grep -iE '<the text>' | cat -v` → `^[[2m...^[[0m` = ghost. Don't waste keys "clearing" a ghost just to read; for *typing a prompt*, type right over it.
- **Exit needs a TRULY EMPTY input line, and the ghost fights you.** `C-c C-c` only exits when the box is empty; a ghost (or real pending text) *swallows* the Ctrl-C → the first C-c shows an interrupt **recap** and the agent **keeps running** (silent no-op). **`Escape` does NOT dismiss a ghost; `C-u`/`BSpace` are unsupported by `herdr send-keys`.** What works: send **`Space`** (overrides/dismisses the ghost so the box truly empties) then **`C-c C-c` immediately, as one rapid burst** — the ghost **regenerates on idle within ~2s** and will eat the next C-c if you dawdle. So: `send-keys Space; send-keys C-c; send-keys C-c` back-to-back (no sleeps between), then verify the shell prompt returned. Re-burst if the recap (not the shell) reappears. claude in a worktree *can* show a **Keep/Remove-worktree dialog** on exit → `Enter` = Keep, never Remove (Remove deletes the plan/spec); the pre-create plain-`claude` flow exits with NO dialog (verified) and leaves the shell IN the worktree.
- **Pre-create the worktree; do NOT use `claude --worktree`.** `claude --worktree NAME` force-names the branch `worktree-<NAME>` off `main` — a prefix you don't control and that buys nothing. The helper does `git worktree add -b <branch> .worktrees/<dir> <base>` then launches plain `claude`, so you own the branch name (match the Linear `gitBranchName`) + base (stack by passing a parent branch as `<base>`). Remove the worktree yourself when done (`git worktree remove`).
- **Enter-swallow → use `herdr agent prompt <pane> '<text>'` (submits atomically) instead of `pane run` + a separate `send-keys <pane> Enter`.** Bracketed-paste on `pane run` often eats the trailing Enter; `agent prompt` encodes it in one op. Long prompts = ONE line either way (embedded newlines submit partial). Single-quote the arg; avoid apostrophes/backticks/`$`/double-quotes inside. (`pane run` stays correct for shell commands — `cd`, launching the agent — where there's no agent to `prompt` yet.)
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
