# Codex in herdr: the mechanics

"Spawn codex", "send it to codex", "pass this to codex", "discuss with codex" and "communicate with codex" all mean codex in a **herdr split pane on a git worktree**, even when herdr is not named. The herdr skill is gated on an explicit mention, so read the herdr skill and this file yourself. What to write to codex lives in `driving-codex.md`, next to this file. For tickets, the loop lives in `loop.md`, next to this file.

## Spawn

1. The worktree comes first, cut from the default branch on `origin` (for example `origin/main`), never local HEAD. For tickets, `/igr:ticket start` creates it.
2. Split from my pane: `herdr pane split --pane <my pane> --direction right --cwd <worktree> --no-focus` (right from a wide pane, down from a tall one). Read every id from the JSON; never guess.
3. Then `herdr agent start <name> --kind codex --pane <new pane>`. A fresh worktree's codex trust modal can read as `idle`, so read the pane before dispatching.

## Briefs and replies

- **Briefs go in files.** The prompt is "Read and follow <path>". Quoting a long brief inline breaks, and backticks execute as command substitution. Do not use `"$(cat file)"`.
- **Brief directory:** use `LOCAL`, the worktree's ignored `igr/` folder (see `../SKILL.md`). It survives forks, compaction and temp cleanup; finish deletes it with the worktree. Record the contract and final result on Linear before cleanup.
- **Codex reads Linear itself** (ticket description and comments). Point it at the ticket; paste only what it cannot see, such as prod numbers or other repos.
- **Replies come to my pane by name.** End each brief with "write your answer to <file>, then run: `herdr agent prompt <my-pane-name> '<file> ready'`". Use one line, with no quotes, backticks or `$` in the argument. Then end my turn: the reply arrives as my next message.
- **A mid-turn message is not a reply** (an evidence request or a route widening, `loop.md` Before code steps 1-2): codex is still working. For evidence, start the work, answer in `design-check.md`, then send codex one line naming the answered claim id; for a widening, write A. A prompt sent while it works is folded in.
- **Ask for long answers as a file.** Codex's TUI scrollback is short.
- **After codex `/compact`**, it forgets where the spec lives, so every later brief names the spec file or ticket comment explicitly.

## Waiting

Every time I send codex a message:

1. Send it with `herdr agent prompt <codex> "<message>" --wait`, run in the background.
   It waits for codex to start, then wakes me when codex stops.
   (Not a separate `herdr agent wait`: right after sending, codex may still be idle, and that wait would wake me at once.)
2. When it wakes me, read codex's pane:
   - finished → read its reply file;
   - asking a question in the chat → answer it (that is a new message: back to step 1);
   - showing an approval or question dialog → answer it as below, then run `herdr agent wait <codex>` in the background and go back to step 2;
   - still working → run `herdr agent wait <codex>` in the background and go back to step 2.
3. If it fails with `agent_prompt_stalled`, codex never started: read the pane before sending anything again.

Do not pass `--until` or `--timeout` to either command: the default already wakes on idle, done and blocked, and a background wait costs nothing.
Never wait for the reply file alone: it cannot see a question, so a stuck codex goes unnoticed.
Never send keys while waiting: an `esc` can interrupt codex mid-answer.

**Answering codex's own dialog:** `herdr agent prompt` is refused while it is blocked. Use `herdr pane send-text <pane> "<text>"`, then `herdr pane send-keys <pane> enter`.

## Restarts and names

- **Names:** my pane is the ticket key (for example `abc-123`), and its codex is `codex-<N>` (`codex-123`). Herdr names must start with a lowercase letter; a bare number is refused. `/igr:ticket start` sets mine.
- After a session restart or fork, herdr names clear for both me and codex. Re-run `herdr agent rename <pane-id> <name>` before briefing. A failed codex reply ("agent target ... not found") means my name is gone.
- After `codex resume`, the agent name is gone too. Use `herdr pane run/read <pane-id>`. `codex resume --last` can pick the wrong session, so resume by explicit id.
- Between plan steps, `/clear` the same codex (`loop.md`, "Clear between steps"). Inside a long step, when its context runs low, `/compact` it. Swapping agents changes the shape of the work and needs approval.
- Humans may instruct codex directly. Before calling a branch commit drift or proposing a revert, ask codex whether it was asked for.

## Worktree guard

- My session is isolated to its worktree. It refuses git in another worktree, `$VAR` in commands, and complex inline shell. Use plain `git -C <path>` commands; put loops in a script file.
- Ask the codex in a worktree to do that worktree's git operations (rebase, push), or read branches via `git fetch` plus `git show origin/<branch>:path`.
- Ticket files are written directly to `LOCAL` in the worktree, ignored by the root-only `/igr/` line in the common Git `info/exclude`. Edit the canonical handoff after `ExitWorktree` with `action: keep` in an EnterWorktree session; a `tk go` session edits it in place by absolute path. Call `<skill base directory>/scripts/tk` by its absolute path for band/timer updates; use separate plain commands and literal paths.
