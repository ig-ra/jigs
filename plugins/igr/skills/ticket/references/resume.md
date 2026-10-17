# Resume ticket work

`/igr:ticket resume [key]` continues an existing ticket from its worktree's `igr/resume.md`. The checkpoint is an index into durable artifacts, not a second contract or a transcript. Start and finish remain in `../SKILL.md`; the working rules remain in `loop.md`.

## Save the checkpoint

Write `LOCAL/resume.md` at the events listed in `loop.md` ("Continuation checkpoint"), and before a handoff or intentional stop. Keep it at 60 lines or fewer, replacing obsolete state rather than appending a history. The start procedure's root-only `/igr/` ignore must already cover this file.

Use this shape; write `none`, `pending` or `unknown` explicitly where appropriate. Paths to ticket artifacts are relative to the recorded worktree; repository and worktree paths are absolute. Use full observed SHAs, and evidence paths or URLs instead of copied output.

```markdown
# Resume TEAM-123
Updated: <UTC timestamp>
Ticket: <key and Linear URL>
Repository: <canonical checkout>
Worktree: <existing ticket worktree>
Branch: <branch>
Phase: <design | develop | review | finish>
Loop position: <section, step and current round/plan step>
Contract: <model-B.md and living comment URL; approval evidence or pending>
Plan: <plan file and first unchecked step, or none>
Scope exclusions: <short scope fence or its artifact path>
PR: <number and URL, or none>
Head: <local HEAD SHA>
Base: <review/base ref and its observed SHA, or unknown>
Codex: <agent name, pane id, explicit session id if known; current assignment and reply file, or none>
Watcher: <purpose, task/process id, status and parameters needed to rearm, or none>
State: igr/state.json
Evidence: <review/check artifact, result and exact head/base or inputs it covers>
Deviations: <implementation deviations from the contract, with their source, or none>
Unresolved: <findings/decision file and remaining items, or none>
Follow-ups: <file or list of deferred items, or none>
Corrections: <igr/corrections.md, or none>
Next action: <one concrete action; identify any human decision it awaits>
```

Phase records the actual position: `design` through approval, `develop` for implementation, `review` for PR review/fixes/checks/merge waits, `finish` when the ticket's deliverables are ready for the finish procedure. Record `develop` once the plan is approved, even if dispatch has not happened yet. A pending approval stays `design`. A multi-PR ticket records the current PR and its own next action.

Keep detailed evidence in the existing model, plan, findings and review files. `igr/state.json` remains authoritative for band state and open timer ids: point to it instead of copying or resetting those ids. An interrupted pass is incomplete unless its artifact proves completion. Preserve outstanding human decisions as outstanding.

## Hand off to a fresh session

The loop hands off at fixed points only (`loop.md`): after approval, before the implement dispatch (phase `develop`); when codex reports a PR ready, before its reviews (phase `review`); and when the next PR of a multi-PR ticket starts after the previous one merged (phase `develop`). The PR-ready handoff happens only when the checkpoint's phase moves from `develop` to `review`; a fix report while already in `review` keeps the session, as do all ordinary review/fix rounds. Trivial changes do not hand off.

1. Stop this session's own background watchers (TaskStop) and record in `Watcher:` what the next session must rearm. Codex keeps running in its own pane; never stop it for a handoff.
2. Save the checkpoint with the new phase, and with `Loop position` and `Next action` set to the action after the handoff: the codex dispatch for `develop`, After code step 1 for `review`. A resumed session never repeats the handoff that created it.
3. Inside Herdr, queue the reset into my own pane by its agent name (`<key>` from start step 3; the worktree guard refuses `$HERDR_PANE_ID`), as two separate submissions without `--wait`:
   - `herdr agent prompt <key> "/clear"`
   - `herdr agent prompt <key> "/igr:ticket resume <KEY>"`

   Then end the turn with one short line naming the handoff. Claude Code runs the queued `/clear` after the turn ends, which starts a new session, then runs the resume prompt in it.
4. Outside Herdr, or if the agent name does not resolve to my own pane, report the handoff and ask the human to type `/clear`, then `/igr:ticket resume <KEY>`.

A failed or interrupted handoff leaves the saved checkpoint; `/igr:ticket resume` in any session continues from it.

## Resume procedure

### 1. Locate the existing worktree

Use the current Git worktree's `igr/resume.md` when present. If a key was supplied, normalize it using `../SKILL.md`'s input rules and require it to match the checkpoint.

Otherwise, use the supplied key or the ticket identified by the current branch/session. Run `tk --cwd <session cwd> prep <KEY>` as described in `../SKILL.md`; inspect the returned existing same-ticket worktrees for their checkpoint. Use the checkpoint's actual registered worktree, not a newly derived path. If no key is known, inspect `git worktree list --porcelain` for existing checkpoints; use one only when it identifies a single ticket and worktree. Ambiguity needs the key or worktree from the user.

A missing, unreadable or incomplete checkpoint, a missing worktree or a conflicting ticket identity is a stop with the exact missing/conflicting item. Leave existing work intact. Resume does not fall back to start, create a worktree, fetch/merge/rebase a branch, rename panes, or change ticket status during validation.

### 2. Verify the checkpoint against current evidence

Before changing anything:

- Verify the recorded repository/worktree against Git's registered worktrees and common Git directory. Verify the actual branch and ticket identity. A different branch or worktree is a conflict, not a reason to rewrite the checkpoint to match it.
- Read `git status --short`, actual HEAD, and the recorded base ref's current SHA. Preserve uncommitted work; it may belong to an active Codex run.
- Read the ticket, its living contract comment and the comments created or edited after the checkpoint's `Updated:` time (`list_comments` ordered by update time). Read the referenced contract/plan, unresolved findings and `igr/state.json`. A `develop` or `review` checkpoint needs recorded approval, not merely a Model B file. A missing approval or a conflicting contract needs reconciliation before implementation continues; a pending decision remains pending.
- If there is a PR, use `tk --cwd <worktree> pr state <PR>` and read the PR's head/base refs to confirm it belongs to the recorded branch. Follow the session's GitHub auth/sandbox rules. Compare its current head and base with the checkpoint and local Git evidence; local and remote heads may legitimately differ while Codex is working.
- Treat recorded review/check passes as evidence for their recorded inputs only. When HEAD, base, dependencies or relevant configuration changed, inspect those changes before deciding which evidence still applies. Follow the loop/repo's reuse rules; a checkpoint is not permission to skip a required check or repeat an unchanged gate.
- When a Codex pane or watcher is recorded, read `herdr-codex.md` and the available Herdr skill. Inspect the live pane inventory, worktree, current activity and reply artifact. Agent names can disappear on restart; use recorded pane/session ids to identify the existing run. A saved task id does not prove a watcher is still running.

Changed HEAD/base, a finished agent or a missing watcher can be normal progress. Read the new diff/report/results, reconcile the checkpoint and invalidate only evidence whose inputs changed. A wrong ticket/branch, unresolved contract change or unavailable required evidence stops dependent work. Keep the approved contract intact while reconciling.

### 3. Continue the recorded next action

When the session's current directory is already the verified worktree (the usual case after a handoff), skip `EnterWorktree`: it would only prompt again. Otherwise enter the worktree with `EnterWorktree`; on its documented fallback, use literal absolute paths. Read `loop.md` and the repo instructions/working memories needed for this phase, then continue from the checkpoint's exact loop position:

- `design`: continue the pending investigation, compare round or approval from the existing artifacts. Preserve completed independent passes and immutable Model A.
- `develop`: continue the plan's first unchecked step or the recorded active dispatch. Reuse the existing Codex pane; read a completed reply before sending anything. Dispatch only when no run is already doing that work and the contract authorizes it.
- `review`: continue the recorded review/fix/check/merge-wait action. Keep ordinary fix rounds in the existing review context and preserve the loop's review/rerun rules.
- `finish`: run the existing finish procedure, including its delivery and cleanup proofs.

Restore an agent name only after confirming the pane's identity and absence of a conflicting name. Rearm a missing watcher for an active run only after confirming an equivalent watcher is not already alive. Retain open timers from `state.json`; close/report them through `tk step` when their run actually reports. A resume is neither a new dispatch nor a completed review.

Refresh `resume.md` from the verified state, report the phase and immediate next action in one short line, and continue unless that action awaits a human or is blocked. A resumed conversation does not repeat ticket intake, restart the design or re-ask an already recorded approval. New evidence of a contract gap follows the existing decision process.
