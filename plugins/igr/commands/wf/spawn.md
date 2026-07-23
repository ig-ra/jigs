---
description: Spawn a herdr pane for a workflow phase (brainstorm/plan/impl) — auto workspace + ticket + worktree; impl writes a codex handoff.
argument-hint: "<brainstorm|plan|impl> [idea text | spec/plan path]"
---
Run `/igr:wf:spawn` for mode: **$ARGUMENTS**

The first token is the mode (`brainstorm` | `plan` | `impl`); the rest is idea text (brainstorm) or an
optional doc path. This command opens a herdr pane for ONE phase — it is the lightweight alternative
to the full `/igr:workflow` ladder. Backend = herdr (`igr:herdr-workflow`); read that skill for the
mechanics referenced below.

**Preflight:** inside a herdr pane (`[ "$HERDR_ENV" = 1 ] && [ -n "$HERDR_PANE_ID" ]`) — else STOP
(start from a herdr pane). Helpers: `${CLAUDE_PLUGIN_ROOT}/skills/herdr-workflow/scripts/`; the handoff
template: `${CLAUDE_PLUGIN_ROOT}/skills/dev/references/impl-handoff-template.md`. If `${CLAUDE_PLUGIN_ROOT}`
is unsubstituted, resolve: `ls -d ~/.claude/plugins/cache/*/igr/*/skills | sort -V | tail -1`.

## Shared setup (all modes)

1. **Workspace** — from the current pane: `herdr pane get "$HERDR_PANE_ID"` → its workspace id.
2. **Ticket** — `git branch --show-current`; if it contains a `saw-XXXX` id, use that id + this branch.
   If NOT (e.g. on `main`): **ASK the owner** —
   - (a) create a Linear issue now (Linear MCP `save_issue`, as a sub-issue under a parent they name),
     take its `gitBranchName`;
   - (b) paste an existing ticket id / branch;
   - (c) skip (freeform branch — WARN the PR won't auto-link without a `saw-XXXX` substring).
3. **Labels** — tab label ≤20 chars, no ticket#; worktree dir <25 chars, include the ticket id.

## Mode `brainstorm` / `plan`  (claude, new pane, create-or-reuse worktree)

- Run `herdr-spawn-worker.sh <ws> <label> <worktree-dir> <branch> [base]` — create-or-reuse worktree,
  launch claude, capture the session UUID.
- `plan` needs a spec: find the spec `*.md` in the worktree; else ask for its **absolute** path.
- Dispatch ONE line, then `herdr pane send-keys <pane> Enter`:
  - brainstorm → `/igr:brainstorm <idea text, if any>`
  - plan → `/igr:plan <ABSOLUTE spec path>`

## Mode `impl`  (codex, reuse worktree, handoff doc — codex has NO igr plugin)

1. **Worktree** — if this pane is already in a ticket worktree (finished plan here), reuse its dir. If
   on `main` (planned there), run `herdr-spawn-worker.sh` to create-or-reuse the ticket worktree.
2. **Find the plan** — `*-plan.md` in the worktree; else the **absolute** main-tree path (ask if unsure).
3. **Resolve the gate** — read the TARGET repo's CLAUDE.md / Makefile / justfile / CI for the full gate
   (build + lint + format + tests + behavior-net). Do NOT assume commands.
4. **Author the handoff** — copy the template to `<worktree>/<prefix>-impl-handoff.md` and fill
   `<TICKET>`, `<PREFIX>`, `<ABS_PLAN_PATH>` (absolute), `<RESOLVED_GATE_CMD>`. Leave it **uncommitted**
   (never commit docs).
5. **Spawn codex + dispatch** — use the helper so the `cd` into the worktree is baked into the launch
   and can never be dropped (the failure that lands codex on `main`):
   - `herdr-spawn-worker.sh --agent codex <ws> <label> <worktree-dir> <branch> [base]` — create-or-reuse
     the worktree, tab-create, and launch `cd <worktree> && direnv allow && codex …IGR_IMPL_*…` as ONE
     command. It prints the pane id and STOPS right after launch (no boot-wait — codex readiness is the
     caller's judgment, not a pinned marker).
   - **Read the pane until codex is ready** (judgment — never dispatch into a booting shell; no pinned
     marker), THEN `herdr pane run <pane> 'read <ABS handoff> and implement per it; stop before push'`
     + `herdr pane send-keys <pane> Enter`.
6. **Review** — the plan-claude pane (this one, if you ran it here) **stays alive** → once codex reports
   done, run `/igr:review` here (Phase III). If you spawned the worktree fresh (planned in main), run
   `/igr:review` from a claude pane cd'd into that worktree instead.

**Report** the pane id(s), worktree, branch, and (impl) the handoff path.
