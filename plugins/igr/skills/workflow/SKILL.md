---
name: workflow
description: Use when shipping a change as a ladder of small worktree-isolated PRs with each PR's plan and post-implement review driven by the igr-dev methods. The orchestrator-agnostic pipeline layer above igr-dev; it drives a pluggable orchestration backend (default igr:herdr-workflow) for the pane/worktree/PR mechanics.
---

# igr-workflow

## Overview

`igr-workflow` is the **orchestration** layer (L3) — an **orchestrator-agnostic pipeline**. It ships a
change as a ladder of small PRs by moving each unit through a fixed phase sequence and, at each phase,
calling the matching `/igr-dev` method. It composes two things and **reimplements neither**:

- **`igr-dev`** — the per-artifact **methods** (produce/harden a spec, a plan, an implementation, a
  review: census for specs, fixed-checklist for plans, `/simplify` + `/igr:code-review-skip-simplify`
  for the diff). igr-dev knows nothing about sequencing.
- **an orchestration BACKEND** — the **mechanics** of driving real agents: spawn an isolated worker,
  dispatch a prompt, watch it finish, swap the agent (claude↔codex), resume a session, shape git
  (squash/rebase/stack), push/PR/watch-checks. Default backend = **`igr:herdr-workflow`**
  (herdr panes + worktrees). igr-workflow names only the **backend operations** below — **never a
  specific CLI** — so the backend is swappable (tmux, plain terminal, a CI runner…).

igr-workflow owns the **pipeline**: phase order, which method runs each phase, the session hand-off,
the gates, human-in-loop. It owns **no** review angles (those live in `igr-dev`) and **no** tool
mechanics (those live in the backend skill).

**When to use:** a multi-PR refactor/extraction/migration where each rung is a small
behavior-preserving PR. **NOT** for a single quick edit (just do it), and **NOT** without explicit
human opt-in to multi-agent orchestration (the pipeline spawns and drives long-running agents).

## Backend interface (what igr-workflow requires of any orchestrator)

**Backend selection:** the owner names the backend skill in the invocation (e.g. "ship X —
backend: igr:tmux-workflow"); absent an explicit choice, the default is **`igr:herdr-workflow`**.
Select ONCE, before spawn-worker; run the **selected** backend's preflight and route every
operation below through that one skill — never mix backends mid-pipeline.

The pipeline calls these **abstract operations**; the backend skill implements each (herdr's
implementation: `igr:herdr-workflow`). A new backend is "supported" once it provides all of:

| operation | contract |
|---|---|
| **spawn-worker** | create an isolated workspace (its own git worktree + a branch **you name**; stack by basing on a parent branch) running a **watchable** agent; return a **session handle** |
| **dispatch** | send one instruction to the worker |
| **watch-finish** | block until the worker's current task **truly** completes (verify state — do not trust early "done" markers) |
| **swap-agent** | change which agent runs in the worker (claude→codex→claude) |
| **resume-session** | reattach to a prior session by handle — the Phase I→III hand-off |
| **shape-git** | squash to one commit; rebase onto latest `main`; stack on a parent branch |
| **ship** | push; open the PR (if delegated); watch checks to green |

**Invariant across every backend:** each agent runs somewhere the human can watch — **never an
invisible background shell**. Background *waits/polls* are fine.

## Preflight (verify BEFORE spawn-worker)

The pipeline is orchestrator-agnostic — its only prerequisite is that the **active backend is usable**,
so **run the backend's own preflight**. Default **herdr** backend (`igr:herdr-workflow`): the
single gate is *"inside a herdr pane"* (`HERDR_ENV=1` + `HERDR_PANE_ID`) — which brings the herdr
binary **and** its bundled `herdr` skill; see that skill's **§Preflight** for the exact check. A
**different** backend brings its own. `igr:herdr-workflow` and `igr-dev` ship in this plugin —
no check.

## The pipeline (agnostic — phases, methods, gates)

**Spec hardening is UPSTREAM and one-time:** `/igr:brainstorm <idea>` → a SPEC-SOUND **and
brainstorm-clean** spec **before** the ladder (its exit gate: OQs owner-resolved, clean-rewrite +
re-census done, zero run records), not inside the per-PR loop (a census + clean-rewrite per rung
would be wasteful — a plan's surface is closed). Each rung's plan derives from that settled spec;
`/igr:plan` re-verifies cleanliness at intake and warns if the spec is dirty.

**Lightweight entry points (standalone, not the full ladder).** The full pipeline below is now the
*less common* path. Most runs enter one phase at a time via **`/igr:wf:spawn <brainstorm|plan|impl>`**
(herdr backend): it resolves the ticket + worktree and opens a pane running the right agent for that
phase. `brainstorm`/`plan` dispatch a native `/igr:` command to claude; `impl` writes a codex handoff
(codex has no igr plugin — see `igr:dev` `references/impl.md`). Use the full pipeline when you want
the whole ladder driven end-to-end; use `/igr:wf:spawn` to start/continue a single phase.

Then, per unit of work — **three phases, each ONE agent**. The hand-off currency is the **session
handle**: Phase I captures it, Phase III resumes it; Phase II is a different agent (codex).

0. **spawn-worker** — own the branch name (match the tracker's branch form, include the ticket id so
   the PR auto-links); capture the session handle.
1. **Phase I — PLAN** (claude): **dispatch** `/igr:plan <spec>`.
   - Human resolves the plan's Open Questions → **STOP; do not proceed on any unresolved OQ.**
   - Surface the plan's `## Appendix: Possible spec updates` (spec fold-back — findings that belong in
     the *spec*, not the plan) → **OFFER to apply to the canonical spec; ASK, never auto** (the
     canonical spec is owner-owned and may live elsewhere — another repo/doc).
   - Capture the session handle.
2. **Phase II — IMPLEMENT** (codex): **swap-agent** to codex → **dispatch** `/igr:impl` (implement →
   squash → **full gate once**; pass tweaks, e.g. "gate once after squash, not per task") →
   **shape-git**: rebase onto latest `main` for stacking.
   - **Plan location across worktrees:** docs are never committed, so when the plan and the impl
     worktree differ (planned in main), the impl agent reads the plan by **absolute path** (carried
     in the codex handoff). The happy path keeps plan+impl in one worktree so this doesn't arise.
   - **codex has no `igr` plugin** → Phase II does not dispatch `/igr:impl` *to codex* verbatim; the
     driving claude renders the impl method into a codex handoff doc (see `igr:dev`
     `references/impl.md` §"Who implements + how it's dispatched").
3. **Phase III — REVIEW + SHIP** (claude, **resume-session**): **dispatch** `/igr:review` (`/simplify`
   + `/igr:code-review-skip-simplify`, apply confirmed fixes) → amend → **ship** (push → open PR if
   delegated → watch checks).

## Gates (STOP and escalate)

- Phase-I `/igr:plan` intake reports a **dirty spec** (Open Questions / revision-log churn) →
  STOP; finish `/igr:brainstorm` first (the owner may explicitly override).
- Any Open Question unresolved after `/igr:plan` → STOP; the human resolves before implement.
- Plan produced **spec fold-back** (`## Appendix: Possible spec updates`) → **OFFER to update the
  canonical spec; ASK, never auto** (it may live elsewhere; the owner decides whether/where).
- A plan `/igr:codex-adversarial-loop` that hit max rounds without converging → STOP; escalate.
- A failing check after PR → surface it; never silently retry-merge.
- **Human-in-the-loop:** the human resolves OQs, opens/merges PRs, and often drives the worker
  directly. See activity you did not initiate → **ASK — do not assume or auto-revert.**

## Seam / boundaries (do not leak)

- igr-workflow **transitions phases + delegates**; it does not review (that is `igr-dev`) and does
  **not** touch tool mechanics — every pane/git/worktree/watch action goes through a **backend
  operation** (above), implemented by the backend skill.
- The **§1 review invariants** (companion-only, no-codegraph, verify-before-fold, the
  FOLD/DISCUSS/DROP router,
  never-commit-docs) are inherited through `igr-dev` — do not re-litigate here.
- The **backend mechanics + gotchas** (spawn/CLI/pane/worktree/finish-watch/exit) live in the backend
  skill (`igr:herdr-workflow` for herdr) — do not duplicate or reimplement them here.
