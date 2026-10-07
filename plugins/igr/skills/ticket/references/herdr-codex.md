# Codex in herdr: the mechanics

"Spawn codex", "send it to codex", "pass this to codex", "discuss with codex" and "communicate with codex" all mean codex in a **herdr split pane on a git worktree**, even when herdr is not named. The herdr skill is gated on an explicit mention, so read the herdr skill and this file yourself. What to write to codex lives in `driving-codex.md`, next to this file. For tickets, the loop lives in `loop.md`, next to this file.

## Spawn

1. The worktree comes first, cut from the default branch on `origin` (for example `origin/main`), never local HEAD. For tickets, `/igr:ticket start` creates it.
2. Split from my pane: `herdr pane split --pane <my pane> --direction right --cwd <worktree> --no-focus` (right from a wide pane, down from a tall one). Read every id from the JSON; never guess.
3. Then `herdr agent start <name> --kind codex --pane <new pane>`. A fresh worktree's codex trust modal can read as `idle`, so read the pane before dispatching.

## Briefs and replies

- **Briefs go in files.** The prompt is "Read and follow <path>". Quoting a long brief inline breaks, and backticks execute as command substitution. Do not use `"$(cat file)"`.
- **The brief directory must survive the session.** The session scratchpad can vanish after a fork or overnight, so use the ticket's `LOCAL` folder (see `../SKILL.md`), for example `<TMP>/igr-ticket/<key>/`.
- **Codex reads Linear itself** (ticket description and comments). Point it at the ticket; paste only what it cannot see, such as prod numbers or other repos.
- **Replies come to my pane by name.** End each brief with "write your answer to <file>, then run: `herdr agent prompt <my-pane-name> '<file> ready'`". Use one line, with no quotes, backticks or `$` in the argument. Then end my turn: the reply arrives as my next message.
- **Ask for long answers as a file.** Codex's TUI scrollback is short.
- **After codex `/compact`**, it forgets where the spec lives, so every later brief names the spec file or ticket comment explicitly.

## Waiting

- Prefer codex messaging me. When I need a fallback, run a background `herdr agent wait <name> --timeout <ms>`, or poll for the answer file in a background `until [ -s file ]` loop.
- Bare `wait` returns on idle, done or blocked. Never pass `--until idle,blocked`, which drops `done`. Implement and review turns flicker between working and idle, so verify on fire (the pane footer plus the answer file) and re-wait if it is mid-step.
- **Approvals:** `herdr agent wait <name> --until blocked` in the background; on fire, read the pane and ask for the approval.
- **Never send keys while waiting.** An `esc` can interrupt codex mid-answer.
- **Answering codex's own question dialog:** `herdr agent prompt` is refused while it is blocked. Use `herdr pane send-text <pane> "<text>"`, then `herdr pane send-keys <pane> enter`.

## Restarts and names

- **Names:** my pane is the ticket key (for example `abc-123`), and its codex is `codex-<N>` (`codex-123`). Herdr names must start with a lowercase letter; a bare number is refused. `/igr:ticket start` sets mine.
- After a session restart or fork, herdr names clear for both me and codex. Re-run `herdr agent rename <pane-id> <name>` before briefing. A failed codex reply ("agent target ... not found") means my name is gone.
- After `codex resume`, the agent name is gone too. Use `herdr pane run/read <pane-id>`. `codex resume --last` can pick the wrong session, so resume by explicit id.
- When codex's context runs low, `/compact` the same codex; swapping agents changes the shape of the work and needs approval.
- Humans may instruct codex directly. Before calling a branch commit drift or proposing a revert, ask codex whether it was asked for.

## Worktree guard

- My session is isolated to its worktree. It refuses git in another worktree, `$VAR` in commands, and complex inline shell. Use plain `git -C <path>` commands; put loops in a script file.
- Ask the codex in a worktree to do that worktree's git operations (rebase, push), or read branches via `git fetch` plus `git show origin/<branch>:path`.
- Writing to the main checkout from inside an EnterWorktree session: the Write tool is refused for paths outside the worktree, such as `<REPO>/igr/tickets/`. Write the file to a temp folder, then copy it with a plain `cp <tmp file> <absolute path>`; `mkdir -p` and `cp` as separate plain commands pass the guard. Heredocs and `&&` chains are refused.
