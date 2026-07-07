---
description: Workflow-backed code review skipping the cleanup angles /simplify already covers — runs correctness angles + conventions only.
argument-hint: "[high|xhigh|max] [PR number / branch / ref range / path / instructions]"
---

Run the **`code-review-skip-simplify`** workflow — the standard workflow-backed code review minus the cleanup angles `/simplify` already owns (reuse, simplification, efficiency, altitude). It keeps the correctness angles (A–E) plus the conventions (CLAUDE.md) check, with an independent verifier per finding.

This workflow ships **inside the igr plugin** at `workflows/code-review-skip-simplify.js`. Plugins cannot register *named* workflows, so invoke it by **path**:

```
Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/code-review-skip-simplify.js", args: "$ARGUMENTS" })
```

If `${CLAUDE_PLUGIN_ROOT}` is unset/unsubstituted in your context, resolve the path first: `ls -d ~/.claude/plugins/cache/*/igr/*/workflows/code-review-skip-simplify.js | sort -V | tail -1`, then pass that as `scriptPath`.

`$ARGUMENTS` = `<level> [target]`:
- **level** (first token): `high` (default), `xhigh`, or `max`. If the first token isn't a level, the whole string is treated as the target and level defaults to `high`.
- **target** (rest): optional PR number, branch, ref range, path, or free-form review instructions (e.g. "only review src/foo.rs", "focus on the new lock ordering"). If omitted, the workflow reviews the current branch diff.

The workflow runs in the background; verified findings arrive as a task notification. When they arrive, present them ranked most-severe first (correctness bugs before conventions findings), or state that nothing survived verification. Use `/workflows` to watch live progress.

Pair with `/simplify` for the cleanup angles this one deliberately skips.
