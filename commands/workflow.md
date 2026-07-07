---
description: Ship a change as a ladder of worktree-isolated PRs, sequencing igr:dev methods with herdr git/worktree/PR/watch mechanics.
argument-hint: "<ticket-or-idea>"
---
Ship: $ARGUMENTS

Invoke the `igr:workflow` skill and follow its SKILL.md to orchestrate the per-PR pipeline (brainstorm upstream once -> per-PR plan/impl/review -> PR/gate/merge). `igr:workflow` owns all git/worktree/PR/rebase/merge; it calls the `igr:dev` methods per phase.

**Preflight first:** SKILL.md §Preflight — the `herdr` binary + `HERDR_ENV=1` + the `herdr-pr-orchestration`/`herdr` skills must be present, or STOP. (They are an external binary + loose skills, not plugins, so they can't be declared in `plugin.json`.)
