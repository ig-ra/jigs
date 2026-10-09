---
name: ticket
description: "Linear ticket lifecycle for any repo, two modes. /igr:ticket start <key> prepares a Linear ticket (reads it and its comments, creates its worktree in <repo>/.worktrees from the repo's default branch or reports on an existing one, enters it, names the herdr pane and tab after the ticket, reads the handoff (when the repo has one) and working memories, lists leftovers, moves it to In Progress, reports readiness and goes straight into the loop's investigation without waiting for a go). /igr:ticket finish closes the ticket this session worked on, a code ticket after its PRs merged or a decide ticket after the decision is recorded (proves nothing is left unmerged or unrecorded, ticks proven criteria, finalizes the living comment and A-to-B, proposes follow-ups, updates memory and the .remember handoff, closes the idle codex pane, removes the worktree and branch, and only then sets Done; gives the next start prompt). Use when asked to start ticket 12203, pick up SAW-12203, work on ticket X, when resuming after compaction, or when told it was merged, wrap up this ticket, save handoff and remember. The key works with or without the SAW- prefix."
---

# Ticket lifecycle

Two modes, from the first argument:
- `start <key>`, for example `/igr:ticket start 12203` or `/igr:ticket start SAW-12203`. If the first argument is a key with no mode, treat it as `start`.
- `finish`, with no key: the ticket comes from the current session.

If the mode is unclear, ask. Between the two modes, the work follows `references/loop.md` ("Before code", "After code", "Rules for both halves"). Corrections to the loop go in that file.

## Which repo

The skill works in any repo. Derive four values once, with plain commands (the worktree guard refuses compound shell and `$` variables, so run each command alone and paste the literal results into later commands):

- `REPO`, the canonical checkout: run `git rev-parse --path-format=absolute --git-common-dir` in the session's cwd and drop the trailing `/.git`. It gives the same answer from the canonical checkout and from any of its worktrees. If the cwd is not inside a git repo (after a compaction), ask which repo and stop.
- `BASE`, the default branch: `git -C <REPO> symbolic-ref --short refs/remotes/origin/HEAD` (for example `origin/main`). If it fails, use `origin/main` and say so.
- `SLUG`, the GitHub repo for `gh`: `gh repo view --json nameWithOwner -q .nameWithOwner`, run in `REPO`. Pass it as `--repo <SLUG>` to every `gh` call, so the command works from a worktree too.
- `TMP`, the temp root: `printenv TMPDIR` with the trailing `/` dropped, or `/tmp` when it prints nothing. The band hook resolves the same root.

Worktrees live in `<REPO>/.worktrees/igor/<key>`. Check that `.worktrees` is git-ignored (`git -C <REPO> check-ignore .worktrees`); if it is not, report it and do not edit `.gitignore` yourself.

Two repo-local files are optional, and the skill adapts:
- **Handoff** `<REPO>/.remember/remember.md`: used when it exists; if not, skip those steps and say so.
- **Local ticket folder** `LOCAL`: `<REPO>/igr/tickets/<KEY>/` when the repo has an `igr/` folder (untracked), otherwise `<TMP>/igr-ticket/<key>/`. It holds Mental Model A, `A-to-B.md`, `estimate-ids.md`, briefs and answers. Never the session scratchpad, which a fork or compaction can lose.

## `/igr:ticket start <key>`: start a ticket

The ticket loop (`references/loop.md`) begins here. `start` does the mechanical "Start" so every ticket begins the same way, then goes straight into "Before code" step 1 without waiting for a go. It stops after the report only when told "don't start yet", a blocker is not Done, or a worktree conflict needs an answer.

Ticket status follows the work: `start` moves the ticket to In Progress; the first push of the ticket's branch to GitHub, by codex or by me, moves it to In Review (`references/loop.md`, Before code step 7); `finish` sets Done.

### Input

One ticket key. Accept any of `12203`, `SAW-12203`, `saw-12203`, `Saw-12203`. Normalize:
- `KEY` = `SAW-` plus the digits, for example `SAW-12203`. Use it for Linear and for the local ticket folder.
- `key` = lowercase, for example `saw-12203`. Use it for the worktree folder and the pane name.
- `N` = the digits only, for example `12203`. Use it for the herdr tab label.

If no digits are given, ask for the key and stop.

### Steps

#### 1. Read the ticket

Load the Linear tools if they are deferred (ToolSearch `select:mcp__claude_ai_Linear__get_issue,mcp__claude_ai_Linear__list_comments`). Then:
- `get_issue(KEY, includeRelations: true)`: title, description, status, project, milestone, `gitBranchName`, blocks and blocked-by;
- `list_comments(KEY)`: all of them. Decisions often live in comments, not the description.

If the ticket does not exist, stop and say so.

Then move it to In Progress with `save_issue(KEY, state: "In Progress")` (ToolSearch `select:mcp__claude_ai_Linear__save_issue`). Skip this when it is already In Progress, In Review or Done, or when a blocked-by ticket is not Done (step 7 reports and stops then).

#### 2. Worktree from the latest default branch

Derive `REPO`, `BASE`, `SLUG` (see "Which repo"). Use plain `git -C <path>` commands.

- `git -C <REPO> fetch origin --quiet`
- **If `<REPO>/.worktrees/igor/<key>` exists** (for example, resuming after a compaction): report whether it is clean, its commits ahead (`git -C <worktree> rev-list --count <BASE>..HEAD`) and behind. Fast-forward it (`git -C <worktree> merge --ff-only <BASE>`) only when it has no commits of its own. A branch with its own commits, usually with an open PR, is rebased only on request, because a rebase rewrites the pushed head. Never discard work.
- **If it does not exist:** `git -C <REPO> worktree add -b <gitBranchName> .worktrees/igor/<key> <BASE>`. If that branch already exists elsewhere, report it instead of forcing. If another worktree of this repo already holds this ticket's work under a different name (for example the ticket's parent), report it and ask which to use.
- Then `git -C <worktree> branch --unset-upstream`. The new branch tracks the base, and a later plain `git push` would target the default branch.

#### 3. Pane name and tab label = the ticket

Do this **before** entering the worktree: once the session is in a worktree, the worktree guard refuses any command that uses `$HERDR_PANE_ID` or `$HERDR_TAB_ID`, even a plain one.

Check `test "${HERDR_ENV:-}" = 1`. If it fails, skip this step. Two different names, both set here:
- **Agent name** (what codex replies to): `herdr agent rename "$HERDR_PANE_ID" <key>`, for example `saw-12203`. Herdr agent names must start with a lowercase letter, so a bare `12203` is refused. Codex replies to this name (`herdr agent prompt saw-12203 ...`), and the codex for this ticket is named `codex-<N>` when it is spawned. If another live agent already holds the name, report it instead of renaming.
- **Tab label** (what shows in the herdr tab bar): `herdr tab rename "$HERDR_TAB_ID" <N>`, for example `12203`. Tabs are labelled with the bare ticket number. The agent rename does not change the tab label.

If the session is already in a worktree, use literal ids instead: the agent rename returns the pane's `pane_id` and `tab_id` in its JSON, and `herdr agent list` shows them too.

#### 4. Switch into the worktree

Call `EnterWorktree` with `path` set to the worktree, so every later read, edit and git command targets this ticket. Load the tool with ToolSearch if it is deferred. If it refuses because "the current directory is not in a git repository" (after a compaction the session cwd can be a non-git folder), run a Bash `cd <worktree>` and retry. If the session is already in another worktree, EnterWorktree may refuse a target outside `.claude/worktrees/`; then call `ExitWorktree` with `action: keep` and retry. If it still refuses, continue without it and use absolute paths and `git -C <worktree>` for every command.

#### 5. Read the working set

Read these fully. They define how the work is done, and skipping them is how sessions drift:
- the handoff `<REPO>/.remember/remember.md` when it exists, especially the section for this track or ticket;
- `references/loop.md` in this skill's base directory, the loop to follow;
- the project memory for the ticket's project. Find it through `MEMORY.md`. If none matches, say so;
- `~/.claude/memory/talking-to-igor.md`, for the shape of the report.

If the local ticket folder (`LOCAL`) exists, read it too: it holds earlier Mental Models.

The codex references (`references/driving-codex.md`, `references/herdr-codex.md`) are read later, when the loop spawns codex; the loop says where. The review rule lives in `references/loop.md` itself (After code, step 1).

#### 6. Leftovers

List leftovers from other tickets to close. Do not close or remove anything yourself.
- `git -C <REPO> worktree list`. For each `.worktrees/igor/*` other than this one, check its branch's PR with `gh pr list --repo <SLUG> --head <branch> --state all --json number,state`. Merged or closed means it is a leftover. A worktree on a detached HEAD has no branch, so report it as a leftover candidate too.
- `herdr agent list`: codex panes whose cwd is one of those merged worktrees.

#### 7. Report and continue

Report in about five short lines, verdict first, using names rather than numbers:
- the ticket's goal in one sentence, and its status (now In Progress);
- blockers (blocked-by that is not Done) and what it blocks;
- what the comments already decided, and the open questions;
- the worktree path, branch and base sha, the pane name and the tab label;
- leftovers to close.

Then, in the same turn, start `references/loop.md` "Before code" step 1 (my own investigation). Its first stop is the hidden-decisions poll. Stop after the report instead only when told "don't start yet", a blocked-by ticket is not Done, or a worktree conflict needs an answer.

## `/igr:ticket finish`: finish the current ticket

The mirror of `start`. It runs in the session that worked on the ticket, so the ticket, the PR, the codex pane and the decisions are already in context. It closes the loop in `references/loop.md`, for code tickets and for decide tickets.

The order matters: prove the work is finished, clean up the worktree, and only then set Done. A ticket marked Done with work still sitting in a worktree is how work gets lost.

### Which ticket, and what kind

No argument. Work it out from the session, in this order:
1. The current worktree's branch (`git rev-parse --abbrev-ref HEAD` in the session's worktree). Derive `REPO`, `BASE`, `SLUG` from it (see "Which repo"). Names look like `igor/saw-12203-...`, which gives `SAW-12203`.
2. The ticket this conversation has been working on.

If the two disagree, or neither gives an answer, ask which ticket and stop.

Then the kind:
- **Decide ticket:** the title starts with `decide:`, or the ticket has no PR and its worktree has no commits of its own. Its deliverable is the decision, recorded on the ticket.
- **Code ticket:** everything else. Its deliverable is merged code.

### Steps

#### 1. Prove it is finished

If any check fails, stop, report what failed, and change nothing: no texts, no cleanup, no status.

**Code ticket:**
- `gh pr list --repo <SLUG> --search <KEY> --state all --json number,state,headRefName,headRefOid,mergeCommit`: every PR for the ticket is MERGED and none is OPEN. Some tickets ship in several PRs. Record each PR number and merge sha.
- The worktree's `git rev-parse HEAD` equals the `headRefOid` of the last merged PR from this branch, so nothing was committed after the merge or left unpushed.
- `git -C <worktree> status --porcelain` is empty: nothing uncommitted or untracked. If untracked files exist, list them and ask; never delete them silently.
- List the ids in `<LOCAL>/estimate-ids.md` (if the file exists) that are still open in `~/.claude/agent-estimates.tsv`; step 4 closes them.

**Decide ticket:**
- The ticket's Answer section records the decision, with the date.
- The living "Suggested implementation" comment ends with the final Mental Model.
- The tickets that build the decision exist and say so.
- The worktree has no commits of its own (`git -C <worktree> rev-list --count <BASE>..HEAD` is 0) and `status --porcelain` is empty. If it has commits, stop and ask: a decide ticket that produced code needs a PR first.

#### 2. Ticket texts (status unchanged)

Load the Linear tools if they are deferred. Re-read the description and comments right before editing them; other sessions edit them too.
- **Acceptance criteria:** tick each one only where a test, the merged PR or the recorded decision proves it. For any criterion you cannot prove, leave it unticked and name it in the report.
- **Living comment:** the "Suggested implementation" comment must describe what shipped (the merged code, or the decision) and end with the final Mental Model (B). If later commits or decisions changed anything, update the comment.
- **Local models:** make `<LOCAL>/A-to-B.md` final: model A from the same folder against final B, with the reason for each change.
- **Duplicates:** if an older comment repeats the living one (for example an "Agreed plan"), list it in the report; deleting a comment needs approval.

#### 3. Follow-ups

Collect what was deferred, decided for later, or left out of scope. Look at the ticket comments, the resolved PR threads, the decisions made in this conversation, and known costs. For each one, check whether a ticket already covers it. Propose either a new ticket, in the style of its sibling tickets, or a note on the ticket that owns it. Create them only after approval. Already-created follow-ups just get listed.

#### 4. Memory and handoff

- **Project memory** (the file for the ticket's project, found through `MEMORY.md`): append one short paragraph covering what shipped (PR and merge sha, or the decision), new tickets, and facts learned that a later session needs. Update its description and index line if "next" changed.
- **Feedback:** if I was corrected on how I work during the ticket and it is not saved yet, propose the exact edit in the report, naming where it belongs (`references/loop.md` or this file for the ticket loop, `references/driving-codex.md` for briefing codex) rather than a new file, and apply it only after Igor's OK. A fact for a project memory may be written directly.
- **Agent-time estimates:** find this ticket's rows in `~/.claude/agent-estimates.tsv` with an empty `actual_min`. Close each with `python3 <skill base directory>/../agent-estimate/estimate.py done <id> --actual <minutes>`, taking the minutes from when that run actually ended (the codex report, or my last commit for the run), not from now. Put estimated against actual for each row in the report.
- **Handoff** `<REPO>/.remember/remember.md` (skip with a note if the repo has none): rewrite this track's section with a timestamp. Cover the state (ticket Done, PR and sha or the decision), next (the recommended next ticket and why), leftovers, and carried-over open items. Keep other tracks' sections untouched.

#### 5. Clean up

Only after steps 1-4. In this order:
1. Stop this session's background watchers for the ticket (TaskStop).
2. **The codex pane for this ticket** (`herdr agent get codex-<N>`; see `references/herdr-codex.md`). Close it with `herdr pane close <pane>` only when it is idle or done and nothing is running there: read the pane first (`herdr agent read`). If it is working, blocked, or a command is still running, leave it open and report it. Never close a pane that another session or a human started.
3. Leave the worktree: `ExitWorktree` with `action: keep` (it never removes a worktree entered by path).
4. `git -C <REPO> worktree remove .worktrees/igor/<key>`. If git refuses (dirty or locked), stop and report; never pass `--force`.
5. Delete the local branch: `git -C <REPO> branch -D <branch>`. `-D` is needed because a squash merge does not count as merged for git; step 1 already proved nothing is lost. For a decide ticket whose branch was never pushed, the same.

Brief and answer files (`<LOCAL>` and `<TMP>/igr-ticket/<key>/`) stay; list them in the report.

#### 6. Set Done

Only if steps 1-5 succeeded: set the ticket's status to Done, and only when every acceptance criterion is proven (step 2). Otherwise leave the status as it is, report the gap, and wait.

#### 7. Report once

Verdict first, in short lines, following `~/.claude/memory/talking-to-igor.md`:
- what shipped: PR and sha, or the decision; ticket Done (and any criterion left unticked, with the reason);
- follow-ups created or proposed;
- memory and handoff updated;
- cleaned up: worktree, branch, codex pane (or why a pane stayed open);
- other leftovers to close, such as merged worktrees from other tickets;
- the recommended next ticket, in one line with its reason;
- the prompt for after compaction: `/igr:ticket start <next key>`, plus "say go" if more is needed.
