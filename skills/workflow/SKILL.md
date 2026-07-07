---
name: workflow
description: Use when shipping a change as a ladder of small worktree-isolated PRs and you want each PR's plan and post-implement review driven by the igr-dev angle-driven method, with herdr panes providing the git/worktree/PR/watch mechanics. The orchestration layer above igr-dev.
---

# igr-workflow

## Overview

`igr-workflow` is the **orchestration** layer (L3). It ships a change as a ladder of small PRs by
**composing two existing skills — it reimplements neither**:

- **`herdr-pr-orchestration`** supplies all *mechanics*: worker panes, worktrees, the
  session-UUID hand-off, squash, rebase, the test gate, push, PR create, check-watching, merge.
- **`igr-dev`** supplies the per-artifact **methods**: how to produce and harden a spec, a plan, an
  implementation, and a review (census for specs, checklist for plans, `/simplify` +
  `/code-review-skip-simplify` for the diff). igr-dev knows nothing about the pipeline —
  **igr-workflow is what arranges its independent methods into an ordered sequence of phases.**

igr-workflow's only job is the **pipeline** — it moves a unit of work through the phases and, at
each one, calls the matching `/igr-dev` method instead of any inline logic. It owns no review angles
(those live in `igr-dev`) and no git mechanics (those live in `herdr-pr-orchestration`).

**REQUIRED SUB-SKILLS:**
- **`herdr-pr-orchestration`** — read it for the full per-unit pipeline, the spawn helper, the
  UUID hand-off, and every herdr gotcha (ghost-suggestion, finish-watch poll, worktree dialog).
- **`igr-dev`** — read it for the per-method recipes and the §1 review invariants.
- **`herdr`** — the raw CLI (requires `HERDR_ENV=1`).

## Preflight — required environment (verify BEFORE spawning the first worker)

igr-workflow composes an external **binary** (`herdr`) + two **loose skills** (`herdr-pr-orchestration`,
`herdr`). None is a Claude Code *plugin*, so **none can be declared in `plugin.json` `dependencies`**
(that field is plugins-only) — they are gated here at runtime. A missing one otherwise fails
mid-ladder. Check, and STOP with the exact fix if any is absent:

1. **`herdr` binary** — `command -v herdr`. Missing → STOP: install herdr (e.g. `brew install herdr`).
2. **Inside a herdr session** — `HERDR_ENV` must equal `1` (igr-workflow drives herdr panes). Unset → STOP: start this from inside herdr.
3. **`herdr-pr-orchestration` + `herdr` skills** — confirm both are in your available skills (loose skills, typically `~/.claude/skills/<name>/SKILL.md`; best-effort `ls ~/.claude/skills/herdr-pr-orchestration/SKILL.md 2>/dev/null`). Absent → STOP: install the herdr skills; do **not** reimplement the pane/git mechanics inline.

`igr-dev` ships in this same plugin — always present, no check. (If herdr is ever packaged as a plugin, add it to `plugin.json` `dependencies` and drop checks 1+3.)

## Where igr-dev replaces herdr's inline steps

Run the `herdr-pr-orchestration` pipeline exactly as written, but drive each phase's **work**
through the matching `/igr-dev` method (each defines how that work is done):

| herdr step | drive with | igr-dev defines |
|---|---|---|
| Phase I steps 2–4 (inline `writing-plans` + `/igr:codex-adversarial-loop` on the plan) | **`/igr:plan <spec>`** | the plan method (fixed-checklist review) |
| Phase II steps 7–11 (codex implement + squash + gate) | **`/igr:impl`** | the implement method (codex session; tunable gate/squash) |
| Phase III step 13 (inline `/simplify` + `/code-review-skip-simplify`) | **`/igr:review`** | the review method (`/simplify` + `/code-review-skip-simplify` + fix) |

Everything else stays **herdr's orchestration**: spawn, worktree/branch/stacking, pane-swap
(claude→codex→claude-resume), UUID capture + Phase-III resume, rebase-onto-`main`, amend, push,
PR create, watch-checks, merge.

## Spec hardening is UPSTREAM and one-time

The heavyweight spec pass — **`/igr:brainstorm <idea>`** — runs **once, upstream, before the
ladder**, not inside the per-PR loop. Harden the spec to SPEC-SOUND first; then each rung's plan
derives from that settled spec. This keeps the per-PR pipeline fast (a census + clean-rewrite per
rung would be wasteful — a plan's surface is closed).

## Per-unit flow (composed)

1. **Upstream once:** `/igr:brainstorm <idea>` → hardened, SPEC-SOUND spec.
2. **Spawn** the worker (herdr `scripts/herdr-spawn-worker.sh`); own the branch name (`saw-XXXX`).
3. **Phase I — PLAN** (claude opus): `/igr:plan <spec>`. Human resolves Open Questions
   (**STOP, do not proceed on any unresolved OQ**). Then surface the plan's **`## Appendix: Possible
   spec updates`** (spec fold-back — findings that belong in the *spec*, not the plan): **OFFER to
   apply them to the canonical spec; ASK, never auto-update** — the canonical spec may live elsewhere
   (another repo / doc) and is owner-owned, so the owner decides whether/where. Capture the session
   UUID (herdr hand-off).
4. **Phase II — IMPLEMENT** (codex xhigh): herdr swaps the pane to codex → `/igr:impl` (find /
   use the plan → implement → squash → **full gate once**; pass any tweaks, e.g. "gate once after
   squash, not per task") → herdr rebases onto `main` for stacking.
5. **Phase III — REVIEW + SHIP** (claude, resume the Phase-I session): `/igr:review`
   (`/simplify` + `/code-review-skip-simplify`, apply confirmed fixes) → amend → push → open PR (if
   delegated) → watch checks (herdr mechanics for amend/push/PR/watch).

## Seam / boundaries (do not leak)

- igr-workflow **transitions phases + delegates**; it does not review (that is `igr-dev`) and does
  not do raw git/pane mechanics (that is `herdr-pr-orchestration`).
- The **§1 review invariants** (companion-only, no-codegraph, verify-before-fold, park-vs-apply,
  never-commit-docs) are inherited through `igr-dev` — do not re-litigate them here.
- The **herdr gotchas** (poll-don't-`--status done`, ghost-suggestion detection, `Space`+`C-c C-c`
  exit, pre-create worktree, verify cwd before codex) are inherited through
  `herdr-pr-orchestration` — do not duplicate them here.
- **Human-in-the-loop:** the human resolves Open Questions, opens/merges PRs, and often drives
  panes directly. If you see activity you did not initiate, **ASK — do not assume or auto-revert.**

## Gates (STOP and escalate)

- Any Open Question unresolved after `/igr:plan` → STOP; the human resolves before implement.
- Plan produced **spec fold-back** items (`## Appendix: Possible spec updates`) → **OFFER to update the
  canonical spec; ASK, never auto** (the canonical spec may live elsewhere; the owner decides
  whether/where to apply).
- A plan `/igr:codex-adversarial-loop` that hit max rounds without converging → STOP; escalate.
- A failing check after PR → surface it; do not silently retry-merge.
