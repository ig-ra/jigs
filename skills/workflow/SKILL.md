---
name: workflow
description: Use when shipping a change as a ladder of small worktree-isolated PRs with each PR's plan and post-implement review driven by the igr-dev methods. The orchestrator-agnostic pipeline layer above igr-dev; it drives a pluggable orchestration backend (default igr:herdr-pr-orchestration) for the pane/worktree/PR mechanics.
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
  (squash/rebase/stack), push/PR/watch-checks. Default backend = **`igr:herdr-pr-orchestration`**
  (herdr panes + worktrees). igr-workflow names only the **backend operations** below — **never a
  specific CLI** — so the backend is swappable (tmux, plain terminal, a CI runner…).

igr-workflow owns the **pipeline**: phase order, which method runs each phase, the session hand-off,
the gates, human-in-loop. It owns **no** review angles (those live in `igr-dev`) and **no** tool
mechanics (those live in the backend skill).

**When to use:** a multi-PR refactor/extraction/migration where each rung is a small
behavior-preserving PR. **NOT** for a single quick edit (just do it), and **NOT** without explicit
human opt-in to multi-agent orchestration (the pipeline spawns and drives long-running agents).

## Backend interface (what igr-workflow requires of any orchestrator)

The pipeline calls these **abstract operations**; the backend skill implements each (herdr's
implementation: `igr:herdr-pr-orchestration`). A new backend is "supported" once it provides all of:

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

The pipeline is orchestrator-agnostic, but the **active backend** has its own environment needs. For
the default **herdr** backend:

1. **Inside a herdr pane** — both `HERDR_ENV` (=`1`) and `HERDR_PANE_ID` set (`[ "$HERDR_ENV" = 1 ] && [ -n "$HERDR_PANE_ID" ]`); a real pane, not just inherited env. Unset → STOP: start from inside a herdr pane. (In a pane ⇒ the `herdr` CLI is present — no binary check.)
2. **`herdr` raw-CLI skill** available (external loose skill, typically `~/.claude/skills/herdr/SKILL.md`). Absent → STOP: install it; do not reimplement the CLI inline.

`igr:herdr-pr-orchestration` and `igr-dev` ship in this plugin — no check. A **different** backend
brings its own preflight instead of 1–2.

## The pipeline (agnostic — phases, methods, gates)

**Spec hardening is UPSTREAM and one-time:** `/igr:brainstorm <idea>` → a SPEC-SOUND spec **before**
the ladder, not inside the per-PR loop (a census + clean-rewrite per rung would be wasteful — a plan's
surface is closed). Each rung's plan derives from that settled spec.

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
3. **Phase III — REVIEW + SHIP** (claude, **resume-session**): **dispatch** `/igr:review` (`/simplify`
   + `/igr:code-review-skip-simplify`, apply confirmed fixes) → amend → **ship** (push → open PR if
   delegated → watch checks).

## Gates (STOP and escalate)

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
- The **§1 review invariants** (companion-only, no-codegraph, verify-before-fold, park-vs-apply,
  never-commit-docs) are inherited through `igr-dev` — do not re-litigate here.
- The **backend mechanics + gotchas** (spawn/CLI/pane/worktree/finish-watch/exit) live in the backend
  skill (`igr:herdr-pr-orchestration` for herdr) — do not duplicate or reimplement them here.
