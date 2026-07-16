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

## Who implements + how it's dispatched (the handoff contract)

**Default impl agent = codex** (`xhigh`). **codex has the `superpowers` skills but NOT the `igr`
plugin** — so codex **cannot run `/igr:impl` (or any `/igr:*`) natively.** When impl runs in codex,
**claude (which has igr) translates this method into a codex handoff doc** and dispatches a one-liner.

- **Handoff doc:** `<prefix>-impl-handoff.md` in the impl **worktree** (uncommitted). Filled from
  `references/impl-handoff-template.md` — names the superpowers skills (`executing-plans` +
  `subagent-driven-development` + `test-driven-development`), the plan's **absolute** path, the
  resolved **target-repo gate command**, the gate/squash cadence, and stop-before-push.
- **Dispatch (one line):** `read <ABS_HANDOFF_PATH> and implement the plan per it; stop before push`.
- **No codex preflight** — the handoff names the superpowers skills; if codex lacks one it says so.
- `/igr:wf:spawn impl` automates authoring + dispatch; a human doing it manually follows the same
  template.

## Plan source

Use the plan **passed to the command** (the target arg) if given; otherwise **find the plan in the
current worktree** (the plan doc the `plan` method produced). Confirm which plan you are executing
before starting.

**The plan lives where it was authored, and docs are never committed** — so the impl agent (a
different worktree/agent) reads the plan by its **absolute path**, not a worktree-relative one. Happy
path: brainstorm→plan→impl share one worktree (via `/igr:wf:spawn`), so the plan is already local;
fallback (planned in the main tree): pass the absolute main-tree path in the handoff.

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
