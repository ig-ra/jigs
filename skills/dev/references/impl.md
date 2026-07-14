# igr-dev: impl method (plan → code)

This method **defines how implementation is done**. It is production, not review.

**Preflight:** needs the `superpowers` plugin (`executing-plans`, `subagent-driven-development`) and a `codex` session — verify per SKILL.md §Preflight; if absent, STOP with the `/plugin install` line.

## Session (default)

Default is a **codex session** (`xhigh` reasoning). **Ensure you are in a codex session** before
implementing. Model + effort are settable at launch (codex CLI: `-m/--model` + `-c model_reasoning_effort=`):

```
codex ${IGR_IMPL_MODEL:+--model "$IGR_IMPL_MODEL"} -c model_reasoning_effort="${IGR_IMPL_EFFORT:-xhigh}"
```

- **`IGR_IMPL_MODEL`** — impl session model (e.g. `gpt-5.6-terra`); unset = codex's `config.toml` default.
- **`IGR_IMPL_EFFORT`** — reasoning effort (default `xhigh`; e.g. `high`).

Set once in `~/.claude/settings.json` `"env": { "IGR_IMPL_MODEL": "gpt-5.6-terra", "IGR_IMPL_EFFORT": "high" }`.
These are **independent of the review knobs** (`IGR_REVIEW_MODEL`, `/igr:codex-adversarial-loop`) — different flow, different model/effort.

## Plan source

Use the plan **passed to the command** (the target arg) if given; otherwise **find the plan in the
current worktree** (the plan doc the `plan` method produced). Confirm which plan you are executing
before starting.

## Implement

Drive the plan with **`superpowers:executing-plans`** + **`superpowers:subagent-driven-development`**
— subagent-driven, scope-locked, task by task (failing-test → minimal code → refactor).

## Tunable knobs (honor caller-supplied context / tweaks)

The command accepts free-form execution tweaks and extra plan context — **honor them.** Common:
- **gate cadence** — default = focused per-task checks during implementation; caller may say "do
  NOT run the full gate after each task".
- **squash-then-gate** — caller may say "squash after ALL tasks are implemented, THEN run the full
  gate once". This is the default speedup pattern: the full gate + behavior-net run **once** on the
  landed/squashed commit, not per WIP commit.
- any extra plan context / constraints the caller passes.

## Gate (default)

After implementing (and squashing, per the knobs) run the repo's **full gate once** on the final
commit — build + lint + format + tests + behavior-net. **The gate is the TARGET repo's own** —
read it from that repo's CLAUDE.md / Makefile / justfile / CI config; do not assume any specific
commands. (Example — needle-wide: clippy `-D warnings`, `fmt --check`,
`test --workspace --all-features`, `make net`, standalone crate build; explain-counters must not
move.) Never commit docs / generated dirs.

## Commits

Code commits per the repo's rules + the owner's commit policy (commit/push only when asked). **No
PR / merge / rebase orchestration** — that belongs to the workflow layer, not this method.

## Stop

All plan tasks implemented + the full gate green on the final commit.
