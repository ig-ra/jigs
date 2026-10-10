---
name: ticket
description: "Linear ticket lifecycle for any repo, two modes. /igr:ticket start <key> prepares a Linear ticket (reads it and its comments, creates its worktree in <repo>/.worktrees from the repo's default branch or reports on an existing one, enters it, names the herdr pane and tab after the ticket, reads the handoff (when the repo has one) and working memories, lists leftovers, moves it to In Progress, reports readiness and goes straight into the loop's investigation without waiting for a go). /igr:ticket finish closes the ticket this session worked on, a code ticket after its PRs merged or a decide ticket after the decision is recorded (proves nothing is left unmerged or unrecorded, ticks proven criteria, finalizes the living comment and A-to-B, proposes follow-ups, updates memory and the .remember handoff, closes the idle codex pane, removes the worktree and branch, and only then sets Done; gives the next start prompt). Use when asked to start ticket ABC-123, pick up ticket 123, work on ticket X, when resuming after compaction, or when told it was merged, wrap up this ticket, save handoff and remember. Any Linear key works (TEAM-123, any case); a bare number works when the team prefix is known."
---

# Ticket lifecycle

Two modes, from the first argument:
- `start <key>`, for example `/igr:ticket start ABC-123` or `/igr:ticket start 123`. If the first argument is a key with no mode, treat it as `start`.
- `finish`, with no key: the ticket comes from the current session.

If the mode is unclear, ask. Between the two modes, the work follows `references/loop.md` ("Before code", "After code", "Rules for both halves"). Corrections to the loop go in that file.

## Which repo

Run `<skill base directory>/scripts/tk --help` once; use the absolute skill base directory in every command. Global options precede subcommands. Use separate plain commands and literal paths for the worktree guard.

Run `<skill base directory>/scripts/tk --cwd <session cwd> prep <KEY>` before entering the worktree. JSON gives `repo_root` (`REPO`), `default_branch` (`BASE` = `origin/<default_branch>`), `worktree`, `branch`, `exists`, `local` (`LOCAL`), same-ticket worktrees and panes. It reads context; it does not fetch, create or enter a worktree. Owner comes from the cwd's worktree slot or the first word of git's user name; use `--owner` only to correct a mismatch. `tk` derives the GitHub repo from origin; use `--repo` only for an explicit different target. Derive `SLUG` for manual `gh` calls with `gh repo view --json nameWithOwner -q .nameWithOwner` in `REPO`, and pass it as `--repo <SLUG>` there. `tk` clears token environment overrides; manual `gh` calls below use the same `env -u GITHUB_TOKEN -u GH_TOKEN -u GH_ENTERPRISE_TOKEN gh` prefix. Follow the session's auth/sandbox rules.

Save `worktree` from prep and use that absolute path verbatim for creation, resume, EnterWorktree, LOCAL and cleanup. Save its `owner` too (the directory immediately above the ticket folder), and pass that owner to canonical `tk close` calls. Check that `.worktrees` is git-ignored (`git -C <REPO> check-ignore .worktrees`); if not, report it and do not edit `.gitignore` yourself.

**Ticket files:** `LOCAL` = `<worktree>/igr/`, also returned by `tk prep`. One worktree, one ticket: models, A-to-B, briefs, answers, plans and `state.json` all sit directly there. Open timer ids live in `state.json` → `tk.estimates`. Files survive forks, compaction and temp cleanup. Removing the worktree deletes them; record the approved contract and final result on Linear before cleanup. The optional canonical handoff `<REPO>/.remember/remember.md` is edited only after leaving the worktree.

**Fallback:** on `tk` exit 3, do that step manually and verify the same completion criteria; read back mutations before retrying. For prep, use `git rev-parse --path-format=absolute --git-common-dir` and `git symbolic-ref --short refs/remotes/origin/HEAD` (if missing, use `origin/main` and say so). A non-git cwd needs the repo from the user. Other exit codes: see `tk --help`; failed guards, pending results and timeouts never authorize bypass. Reply/resolve/enqueue manual paths stay next to their commands in `references/loop.md` until proven live.

## `/igr:ticket start <key>`: start a ticket

The ticket loop (`references/loop.md`) begins here. `start` does the mechanical "Start" so every ticket begins the same way, then goes straight into "Before code" step 1 without waiting for a go. It stops after the report only when told "don't start yet", a blocker is not Done, or a worktree conflict needs an answer.

Ticket status follows the work: `start` moves the ticket to In Progress; the first push of the ticket's branch to GitHub, by codex or by me, moves it to In Review (`references/loop.md`, Before code step 7); `finish` sets Done.

### Input

One Linear ticket key, `<TEAM>-<digits>` in any case, for example `ABC-123`, `abc-123` or `Abc-123`. A bare number (`123`) is accepted when the team prefix is known: from the current branch or worktree name, or from an earlier ticket in this session. Normalize:
- `KEY` = the team prefix in upper case, a hyphen, and the digits, for example `ABC-123`. Use it for Linear and the state's ticket key.
- `key` = lowercase, for example `abc-123`. Use it for the worktree folder and the pane name.
- `N` = the digits only, for example `123`. Use it for the herdr tab label.

If no digits are given, or a bare number comes with no known team prefix, ask for the full key and stop.

### Steps

#### 1. Read the ticket

Load the Linear tools if they are deferred (ToolSearch `select:mcp__claude_ai_Linear__get_issue,mcp__claude_ai_Linear__list_comments`). Then:
- `get_issue(KEY, includeRelations: true)`: title, description, status, project, milestone, `gitBranchName`, blocks and blocked-by;
- `list_comments(KEY)`: all of them. Decisions often live in comments, not the description.

If the ticket does not exist, stop and say so.

Then move it to In Progress with `save_issue(KEY, state: "In Progress")` (ToolSearch `select:mcp__claude_ai_Linear__save_issue`). Skip this when it is already In Progress, In Review or Done, or when a blocked-by ticket is not Done (step 7 reports and stops then).

#### 2. Worktree from the latest default branch

If the session is already in an entered worktree, first `ExitWorktree` with `action: keep` and return to the canonical checkout. Run `<skill base directory>/scripts/tk --cwd <session cwd> prep <KEY>` and derive `REPO`, `BASE`, `SLUG`, `worktree`, `owner`, `LOCAL` (see "Which repo"). Use plain `git -C <path>` commands. Inspect `prep`'s same-ticket worktrees and panes before creating anything; report a conflicting location instead of forcing it.

- `git -C <REPO> fetch origin --quiet`
- **If the returned `<worktree>` exists** (for example, resuming after a compaction): report whether it is clean, its commits ahead (`git -C <worktree> rev-list --count <BASE>..HEAD`) and behind. Fast-forward it (`git -C <worktree> merge --ff-only <BASE>`) only when it has no commits of its own. A branch with its own commits, usually with an open PR, is rebased only on request, because a rebase rewrites the pushed head. Never discard work.
- **If it does not exist:** `git -C <REPO> worktree add -b <gitBranchName> <worktree> <BASE>`. If that branch already exists elsewhere, report it instead of forcing. If another worktree of this repo already holds this ticket's work under a different name (for example the ticket's parent), report it and ask which to use.
- Then `git -C <worktree> branch --unset-upstream`. The new branch tracks the base, and a later plain `git push` would target the default branch.

**Local ignore, before entering:** read the common Git directory from `git -C <REPO> rev-parse --path-format=absolute --git-common-dir`. In its `info/exclude`, ensure the root-only local line `/igr/` exists, appending it if absent and preserving other lines. This is shared by every worktree and never committed. Verify `git -C <worktree> check-ignore --verbose igr/state.json` reports the `/igr/` pattern; check `git -C <worktree> ls-files -- igr/` is empty. If ticket files are tracked, stop and report them. All ticket writes, including codex's, go to `LOCAL`; `tk step` requires that same `/igr/` pattern before writing. It covers only root ticket files; nested source folders such as `plugins/igr/` stay visible to Git.

#### 3. Pane name and tab label = the ticket

Do this **before** entering the worktree: once the session is in a worktree, the worktree guard refuses any command that uses `$HERDR_PANE_ID` or `$HERDR_TAB_ID`, even a plain one.

Check `test "${HERDR_ENV:-}" = 1`. If it fails, skip this step. Two different names, both set here:
- **Agent name** (what codex replies to): `herdr agent rename "$HERDR_PANE_ID" <key>`, for example `abc-123`. Herdr agent names must start with a lowercase letter, so a bare `123` is refused. Codex replies to this name (`herdr agent prompt abc-123 ...`), and the codex for this ticket is named `codex-<N>` when it is spawned. If another live agent already holds the name, report it instead of renaming.
- **Tab label** (what shows in the herdr tab bar): `herdr tab rename "$HERDR_TAB_ID" <N>`, for example `123`. Tabs are labelled with the bare ticket number. The agent rename does not change the tab label.

If the session is already in a worktree, use literal ids instead: the agent rename returns the pane's `pane_id` and `tab_id` in its JSON, and `herdr agent list` shows them too.

#### 4. Leftovers, before entering

`tk prep` already reports same-ticket worktrees/panes; inspect them for conflicts or unfinished work. It does not classify other tickets' PRs. List those manually here, before `EnterWorktree`; report only, without closing or removing anything:
- `git -C <REPO> worktree list`. For each other registered ticket worktree under `.worktrees/<owner>/*`, check `gh pr list --repo <SLUG> --head <branch> --state all --json number,state`. Merged or closed means leftover; detached HEAD means a leftover candidate.
- `herdr agent list`: codex panes in those merged worktrees.

These operations run from the canonical checkout.

#### 5. Switch into the worktree

Call `EnterWorktree` with `path` set to the worktree, so every later read, edit and git command targets this ticket. Load the tool with ToolSearch if it is deferred. If it refuses because "the current directory is not in a git repository" (after a compaction the session cwd can be a non-git folder), run a Bash `cd <worktree>` and retry. If it still refuses, continue without it and use absolute paths and `git -C <worktree>` for every command.

#### 6. Read the working set

Read these fully. They define how the work is done, and skipping them is how sessions drift:
- the handoff `<REPO>/.remember/remember.md` when it exists, especially the section for this track or ticket;
- `references/loop.md` in this skill's base directory, the loop to follow;
- the project memory for the ticket's project. Find it through `MEMORY.md`. If none matches, say so;
- `~/.claude/memory/talking-to-igor.md`, for the shape of the report.

If `LOCAL` exists, read it too: it holds earlier Mental Models. Create it inside the worktree when first needed.

The codex references (`references/driving-codex.md`, `references/herdr-codex.md`) are read later, when the loop spawns codex; the loop says where. The review rule lives in `references/loop.md` itself (After code, step 1).

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
1. The current worktree's branch (`git rev-parse --abbrev-ref HEAD` in the session's worktree). Derive `REPO`, `BASE`, `SLUG` from it (see "Which repo"). Names look like `<owner>/abc-123-...`, which gives `ABC-123`.
2. The ticket this conversation has been working on.

If the two disagree, or neither gives an answer, ask which ticket and stop. Save `KEY`, `key`, `LOCAL`, `worktree`, its `owner` and branch before leaving the worktree; the canonical branch is not the ticket branch.

Then the kind:
- **Decide ticket:** the title starts with `decide:`, or the ticket has no PR and its worktree has no commits of its own. Its deliverable is the decision, recorded on the ticket.
- **Code ticket:** everything else. Its deliverable is merged code.

### Steps

#### 1. Prove it is finished

First leave the worktree with `ExitWorktree`, `action: keep`, and return to the canonical checkout. `tk close` inspects the target tree's panes when inside Herdr; cleanup must run outside the target tree. Keep the worktree intact until the checks below pass.

If any check fails, stop, report what failed, and change nothing: no texts, no cleanup, no status.

**Code ticket:**
- `gh pr list --repo <SLUG> --search <KEY> --state all --json number,state,headRefName,headRefOid,mergeCommit`: every PR for the ticket is MERGED and none is OPEN. Some tickets ship in several PRs. Record each PR number and merge sha.
- `<skill base directory>/scripts/tk --cwd <REPO> close <KEY> check --owner <owner>`: require exit 0. This proves the registered worktree is clean (including untracked files), local HEAD exactly matches a merged PR head for its branch, no branch PR is open, local origin agrees with live origin, the merge is reachable on the default branch, and panes are safe when inside Herdr. Keep the ticket-wide PR list above: `close` checks this branch only. If origin is stale, fetch origin and rerun. If untracked files exist, list them and ask; never delete them silently.
- Inspect `<LOCAL>/state.json` → `tk.estimates` and any legacy `<LOCAL>/estimate-ids.md` against open rows in `~/.claude/agent-estimates.tsv`; step 4 closes them.

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
- **Agent-time estimates:** find this ticket's open rows in `~/.claude/agent-estimates.tsv`. For each id in `state.json` → `tk.estimates`, use `<skill base directory>/scripts/tk --cwd <worktree> step <KEY> <line> <current status> --report --actual-minutes <minutes>`. Take minutes from when that run actually ended (the codex report or my last commit), not from now. For legacy ids or missing state, use `python3 <skill base directory>/../agent-estimate/estimate.py done <id> --actual <minutes>`; `tk` cannot report an id it does not hold. Put estimated against actual for each row in the report.
- **Handoff** `<REPO>/.remember/remember.md` (skip with a note if the repo has none): rewrite this track's section with a timestamp. Cover the state (ticket Done, PR and sha or the decision), next (the recommended next ticket and why), leftovers, and carried-over open items. Keep other tracks' sections untouched.

#### 5. Clean up

Only after steps 1-4, from the canonical checkout:
1. Stop this session's background watchers for the ticket (TaskStop).
2. **Final band, before removal:** for a code ticket, run `<skill base directory>/scripts/tk --cwd <worktree> step <KEY> implement done`, then the same for `reviews done` and `checks done --note <merge sha>`.
3. Inside Herdr, read the codex pane (`herdr agent get codex-<N>`, `herdr agent read codex-<N>`). It must be idle/done, owned by this session, and have no running command. Otherwise stop and report; never close another session's or a human's pane. Outside Herdr, skip pane control.
4. **Code ticket:** `<skill base directory>/scripts/tk --cwd <REPO> close <KEY> apply --owner <owner>`. Require exit 0. It repeats the proof, closes the idle codex pane when inside Herdr, removes the worktree without force, and deletes the proven branch. On exit 3, inspect what already happened, redo step 1's proof manually, then finish the remaining pane close / `git -C <REPO> worktree remove <worktree>` / `git -C <REPO> branch -D <branch>`; never force worktree removal.
5. **Decide ticket:** `tk close` requires a merged PR, so after step 1's decide proof, close the verified pane when inside Herdr, `git -C <REPO> worktree remove <worktree>`, then `git -C <REPO> branch -D <branch>`. Stop on any refusal.

Worktree removal deletes the ignored `LOCAL` folder, including briefs, answers and band state. Nothing is copied or moved to the canonical checkout.

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
