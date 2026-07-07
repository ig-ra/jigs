---
description: Ship a change as a ladder of worktree-isolated PRs, sequencing igr:dev methods with herdr git/worktree/PR/watch mechanics.
argument-hint: "<ticket-or-idea>"
---
Ship: $ARGUMENTS

Invoke the `igr:workflow` skill and follow its SKILL.md to orchestrate the per-PR pipeline (brainstorm upstream once -> per-PR plan/impl/review -> PR/gate/merge). `igr:workflow` owns all git/worktree/PR/rebase/merge; it calls the `igr:dev` methods per phase.

**Preflight first:** SKILL.md §Preflight — a herdr pane (`HERDR_ENV=1` + `HERDR_PANE_ID` set) + the external `herdr` raw-CLI skill must be present, or STOP. (`igr:herdr-pr-orchestration` now ships in this plugin; the herdr session + `herdr` skill are external and can't be declared in `plugin.json`.)
