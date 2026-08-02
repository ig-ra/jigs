---
description: Spawn a herdr pane for a workflow phase (brainstorm/plan/impl) — auto workspace + ticket + worktree; impl writes a codex handoff.
argument-hint: "<brainstorm|plan|impl> [right|tab|down] [idea text | spec/plan path]"
---
Run `/igr:wf:spawn` for mode: **$ARGUMENTS**

The first token is the mode (`brainstorm` | `plan` | `impl`). An **optional placement keyword** may come
immediately after it — `right` → `--placement split-right` (same tab), `tab` → `--placement new-tab`,
`down` → `--placement split-down`; **any other token there is idea/path, not placement**. The placement
keyword overrides the per-mode default (**impl → `right`**, **brainstorm/plan → `tab`**); pass the mapped
`--placement` value to `wf-herdr.sh`. Everything after mode+placement is idea text (brainstorm) or an
optional doc path. This command opens a herdr pane for ONE phase — the lightweight alternative to the
full `/igr:workflow` ladder. Backend = herdr (`igr:herdr-workflow`); read that skill for the mechanics.

**Preflight:** inside a herdr pane (`[ "$HERDR_ENV" = 1 ] && [ -n "$HERDR_PANE_ID" ]`) — else STOP
(start from a herdr pane). Helpers: `${CLAUDE_PLUGIN_ROOT}/skills/herdr-workflow/scripts/`; the handoff
template: `${CLAUDE_PLUGIN_ROOT}/skills/dev/references/impl-handoff-template.md`. If `${CLAUDE_PLUGIN_ROOT}`
is unsubstituted, resolve: `ls -d ~/.claude/plugins/cache/*/igr/*/skills | sort -V | tail -1`.

## Shared setup (all modes)

1. **Workspace** — use the orchestrator's own **`$HERDR_WORKSPACE_ID`** (env, always correct — do NOT
   re-resolve via `pane get`, which drifts when focus moves and lands the tab in another workspace).
   Pass it to the helper, or pass `-` to let the helper default to it. Pins every spawn to YOUR workspace.
2. **Ticket** — `git branch --show-current`; if it contains a `saw-XXXX` id, use that id + this branch.
   If NOT (e.g. on `main`): **ASK the owner** —
   - (a) create a Linear issue now (Linear MCP `save_issue`, as a sub-issue under a parent they name),
     take its `gitBranchName`;
   - (b) paste an existing ticket id / branch;
   - (c) skip (freeform branch — WARN the PR won't auto-link without a `saw-XXXX` substring).
3. **Labels** — tab label ≤20 chars, no ticket#; worktree dir <25 chars, include the ticket id.

## Mode `brainstorm` / `plan`  (claude, NEW tab, create-or-reuse worktree)

- Run `wf-herdr.sh --placement <resolved> - <label> <worktree-dir> <branch> [base]` — default `new-tab`
  (a NEW **workspace-pinned** tab, the right home for brainstorm/plan) unless the caller's placement
  keyword overrode it (`right`→split-right, `down`→split-down). `-` pins the workspace to
  `$HERDR_WORKSPACE_ID`. Create-or-reuse worktree, launch claude, capture the session UUID + terminal id.
- `plan` needs a spec: find the spec `*.md` in the worktree; else ask for its **absolute** path.
- Dispatch ONE line **atomically** via `herdr agent prompt <pane> '<line>'` (no separate `send-keys Enter`):
  - brainstorm → `/igr:brainstorm <idea text, if any>`
  - plan → `/igr:plan <ABSOLUTE spec path>`

## Mode `impl`  (codex, reuse worktree, handoff doc — codex has NO igr plugin)

1. **Worktree** — if this pane is already in a ticket worktree (finished plan here), reuse its dir. If
   on `main` (planned there), run `wf-herdr.sh` to create-or-reuse the ticket worktree.
2. **Find the plan** — `*-plan.md` in the worktree; else the **absolute** main-tree path (ask if unsure).
3. **Resolve the gate** — read the TARGET repo's CLAUDE.md / Makefile / justfile / CI for the full gate
   (build + lint + format + tests + behavior-net). Do NOT assume commands.
4. **Author the handoff** — copy the template to `<worktree>/<prefix>-impl-handoff.md` and fill
   `<TICKET>`, `<PREFIX>`, `<ABS_PLAN_PATH>` (absolute), `<RESOLVED_GATE_CMD>`. Leave it **uncommitted**
   (never commit docs).
5. **Spawn codex + dispatch** — use the helper so the `cd` into the worktree is baked into the launch
   and can never be dropped (the failure that lands codex on `main`):
   - `wf-herdr.sh --agent codex --placement <resolved> - <label> <worktree-dir> <branch> [base]` (default
     `split-right` unless the caller's keyword overrode it — `tab`→new-tab, `down`→split-down)
     — create-or-reuse the worktree, **split the orchestrator's pane to its RIGHT in the SAME tab** (cwd =
     worktree, inherits your workspace), and launch `cd <worktree> && direnv allow && codex …IGR_IMPL_*…`
     as ONE command. codex lands beside the planner (which stays as the reviewer, step 6). Prints pane id
     + terminal id and STOPS right after launch (no boot-wait — the caller waits readiness via `agent wait`).
   - **Wait for readiness** → `herdr agent wait <pane> --timeout 120000` gets codex booted (bare wait =
     settled idle/done/blocked), THEN `pane read`: a **fresh worktree pops codex's "Do you trust this
     directory?" modal, which also reads `idle`** — if up, `send-keys <pane> Enter` (=Yes) and wait again;
     dispatch only once the read shows codex's real input box (**never on bare idle** — see the codex-trust
     gotcha). THEN dispatch **atomically** → `herdr agent prompt <pane> 'read <ABS handoff> and implement
     per it; stop before push'` (no separate Enter). Impl flickers → watch finish via the footer-settle
     discipline (`igr:herdr-workflow` gotchas), NOT a bare `agent wait`.
6. **Review** — the plan-claude pane (this one, if you ran it here) **stays alive** → once codex reports
   done, run `/igr:review` here (Phase III). If you spawned the worktree fresh (planned in main), run
   `/igr:review` from a claude pane cd'd into that worktree instead.

**Report** the pane id(s), worktree, branch, and (impl) the handoff path.
