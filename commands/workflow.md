---
description: Ship a change as a ladder of worktree-isolated PRs — the igr:workflow pipeline sequences igr:dev methods over a pluggable orchestration backend (default igr:herdr-workflow).
argument-hint: "<ticket-or-idea>"
---
Ship: $ARGUMENTS

Invoke the `igr:workflow` skill and follow its SKILL.md to orchestrate the per-PR pipeline (brainstorm upstream once -> per-PR plan/impl/review -> PR/gate/merge). `igr:workflow` owns the pipeline only (phase order, gates, session hand-off) and calls the `igr:dev` methods per phase; every git/worktree/PR/rebase/merge action goes through a backend operation implemented by the backend skill (default `igr:herdr-workflow`).

**Preflight first:** SKILL.md §Preflight — run the **selected** backend's preflight (the owner may name a backend in the invocation; default `igr:herdr-workflow` — see SKILL.md §Backend selection). Default herdr backend: you must be inside a herdr pane (`HERDR_ENV=1` + `HERDR_PANE_ID`), which brings the herdr binary + its bundled `herdr` skill (see `igr:herdr-workflow` §Preflight). Not in a pane and no other backend named → STOP. (The herdr session is external — can't be declared in `plugin.json`; the pipeline itself is backend-agnostic.)
