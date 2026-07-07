---
name: dev
description: Use when doing one specific piece of dev work — hardening an idea into a spec, hardening a spec into a plan, implementing a plan, or reviewing an implementation diff — and you want the angle-driven method (census for specs, fixed checklist for plans, /simplify + /igr:code-review-skip-simplify for diffs) instead of a generic one-pass review. Invoked as /igr:<method> <target>.
---

# igr-dev

## Overview

`igr-dev` is a **library of independent dev methods** — one per kind of artifact. Each method
defines *how that one piece of work is done*: how to harden a spec, how to harden a plan, how to
implement, how to review. It **produces** artifacts with `superpowers` skills and **reviews** them
adversarially — driving `/igr:codex-adversarial-loop` for the spec and plan, and `/simplify` +
`/igr:code-review-skip-simplify` for the code diff.

**igr-dev knows nothing about ordering.** It does not know these methods can be sequenced, does not
chain them, and does not touch PR / branch / merge. Sequencing the methods into a per-PR pipeline is
`igr-workflow`'s job (see **Boundaries**).

**Core principle — the asymmetry that shapes review:**
- **Spec review is EXPLORATORY** → an *angle*-census discovers doc-specific angles; a *clean-rewrite*
  is load-bearing. Open-ended failure surface.
- **Plan review is a FIXED angle CHECKLIST** → closed, uniform angle surface (no angle-discovery, no
  clean-rewrite). But the plan is first **grounded in a CODE census** (ground-truth facts from the
  code at HEAD — distinct from the spec's *angle*-census), so review splits into cheap **mechanical
  diffs** (vs census/LSP) + a few **judgment angles looped to SOLID** + a final **broad pass**. See
  `references/plan.md`.

## Invocation

`/igr:<method> <target> [extra args]`

- **method** (first token, required): `brainstorm` | `plan` | `impl` | `review`. Independent — pick
  the one for the work at hand.
- **target**: the artifact — an idea/spec path (`brainstorm`), a spec path (`plan`), a plan path or
  worktree (`impl`), or the diff (`review`). If a `brainstorm` input is already a spec, skip
  production and go straight to hardening.
- **extra args** (method-specific): `brainstorm`/`plan` — text after `--` = owner-settled decisions
  to protect from re-litigation, passed to `/igr:codex-adversarial-loop`. `impl` — free-form execution
  tweaks + extra plan context (e.g. "do not run the full gate after each task; squash then gate
  once"). `review` — the `/igr:code-review-skip-simplify` effort level (default `xhigh`).

## Methods

| method | input → output | producer (superpowers) | review profile | recipe |
|--------|---------------|------------------------|----------------|--------|
| `brainstorm` | idea → spec | `brainstorming` | **EXPLORATORY** (census + clean-rewrite) | `references/brainstorm.md` |
| `plan` | spec → plan | `writing-plans` (+ code census) | **code census → mechanical diffs + judgment angles-till-SOLID + broad pass** | `references/plan.md` |
| `impl` | plan → code | `executing-plans` + `subagent-driven-development` | **codex session**, tunable gate/squash — production | `references/impl.md` |
| `review` | diff → fixed code | `receiving-code-review` | **claude session** — `/simplify` + `/igr:code-review-skip-simplify`, then FIX | `references/review.md` |

**Dispatch:** read `references/<method>.md` for the invoked method's full recipe and follow it.
Each method is self-contained — it does not hand off to or assume another method ran first.

## Preflight — required plugins

igr-dev **produces** artifacts with `superpowers` skills and **reviews** them with the Codex
companion (`codex` plugin). Both are external and declared in `plugin.json` `dependencies`
(Claude Code auto-installs declared deps at install/enable). **Verify before the first use in a
method** — a disabled/absent dep otherwise surfaces as a mid-run failure:

| method | external plugins needed |
|--------|-------------------------|
| `brainstorm` | `superpowers` (`brainstorming`) · `codex` (companion) |
| `plan` | `superpowers` (`writing-plans`) · `codex` (companion) |
| `impl` | `superpowers` (`executing-plans`, `subagent-driven-development`) · a `codex` session |
| `review` | `superpowers` (`receiving-code-review`) — **no** Codex companion |

**Detect** (presence on disk = installed): superpowers → `ls -d ~/.claude/plugins/cache/*/superpowers/*/ 2>/dev/null`; codex companion → `ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null`. **If a needed one is empty → STOP** and tell the user the exact line to run: `/plugin install superpowers` or `/plugin install codex` (then re-run the method). Do not silently degrade or reimplement the skill inline.

*(`/simplify` is built-in and `/igr:code-review-skip-simplify` now ships with this plugin (`workflows/`) — neither is an external-plugin dep.)*

## Boundaries (what igr-dev is NOT)

igr-dev sits between a mechanism it drives and a workflow that drives it:

- **`/igr:codex-adversarial-loop`** (the mechanism below): runs ONE `(target, focus)` to clean and
  reports a per-focus verdict. Knows companion mechanics; nothing about specs/plans/angles.
- **`igr-workflow`** (the layer above): **sequences** these methods into a per-PR pipeline and does
  all git / worktree / PR / rebase / gate / merge orchestration, plus pane/session hand-offs.

igr-dev owns each **individual method** (produce + review one artifact) and per-method convergence.
It **may** make the code commits intrinsic to a method (`impl`/`review`, per repo rules + the
owner's commit policy). It must **NOT** sequence methods, know a "pipeline", or do PR / branch /
merge / rebase — those are `igr-workflow`. The **focus string** is the seam to the mechanism below;
**anything about ordering or git** is the seam to `igr-workflow` above.

## How igr-dev drives the reviewer

*Applies to the methods that use `/igr:codex-adversarial-loop` — `brainstorm` and `plan`. `impl`
implements in a codex session; `review` uses `/simplify` + `/igr:code-review-skip-simplify` in a claude
session — see their references.*

For each angle: build the angle text → invoke `/igr:codex-adversarial-loop <target> --focus "<angle>"`
(single-focus mode) → consume its per-focus verdict → aggregate across angles → **you** decide
overall convergence. L1 loops one angle to clean; **igr-dev owns cross-angle convergence**.

The angle text you pass as `--focus` MUST (this is what makes the method work):
- name the ONE failure-class to probe + the exact code location(s) to verify it against;
- say "verify against the ACTUAL current code (read the cited files) before reporting";
- say "do NOT run codegraph (it hangs); use rg and sed only";
- say "flag over-engineering as a defect — do not demand new features/abstractions";
- contain **no backticks and no `$`** (refer to code as file colon line) or the companion crashes.

## Hard invariants (inherited by every method)

These are encoded in the `/igr:codex-adversarial-loop` command — **igr-dev drives that command, it
does not reimplement the mechanics.** Restated so every method honors them:

1. **Companion only.** Reviews go through the Codex companion via `/igr:codex-adversarial-loop`
   (`Bash(run_in_background:true)`). **NEVER** spawn the `codex:codex-rescue` Agent for a review —
   it has edit/commit tools and auto-commits during "review only".
2. **No codegraph** in any focus string (it hangs the companion ~60 min). rg/sed only.
3. **zsh eval gotcha** — strip ALL backticks and `$` from the focus string.
4. **One companion job in flight**, unique outfile per round; poll the outfile for the verdict
   marker (the completion notification fires early, before the verdict exists).
5. **Verify every finding against the actual code before folding** — Codex is a lead-generator,
   not an oracle.
6. **Triage: apply-minimal vs park-scope.** Minimal/clear fix (faithfulness, wrong ref, missing
   guard, narrow correctness — no new abstraction/knob/scope) → apply. Over-engineering OR
   breaking/major (new abstraction/module/knob, broadened scope, contradicts a settled call) → do
   NOT apply → park to the target's `## Open Questions (awaiting human resolution)`. Unsure → park.
7. **Never git-commit docs** (the owner commits docs). For code, follow the repo's commit rules;
   for docs, leave edits uncommitted and say so.
8. **cwd = the directory containing the target** so untracked files are in the companion's tree.

**Scope:** invariants 1–4 and 8 govern the methods that drive `/igr:codex-adversarial-loop`
(`brainstorm`, `plan`). Invariants 5–7 (verify-before-fold, park-vs-apply, never-commit-docs) apply
to **every** method — including `impl` (codex) and `review` (`/simplify` +
`/igr:code-review-skip-simplify`), which do not touch the Codex companion.

## Red flags — STOP, you are breaking discipline or leaking into the workflow

- About to sequence methods / open a PR / merge / rebase / create-or-switch branches → that is
  **`igr-workflow`**, not igr-dev. (Code commits within a method, per repo rules, are fine.)
- About to spawn `codex:codex-rescue` for a review → **wrong tool**, use `/igr:codex-adversarial-loop`.
- Folding a finding you have not read the cited code for → **verify first**.
- Adding a new abstraction/knob/module because Codex suggested it → **park it**, don't apply.
- Putting backticks or `$` in a focus string → the companion will crash.
- Declaring a spec "done" after one clean pass → specs converge on **all-angles-cleared +
  COVERAGE-COMPLETE**, not one pass (see `references/brainstorm.md`).

## Convergence philosophy (shared)

The signal is not "a clean pass." It is: angles return `SPEC-SOUND` / `PLAN-SOUND` **first-try**,
and findings degrade from code-gaps to consistency-of-your-own-edits. For specs the strong stop is
**every census angle cleared AND a completeness-critic pass returns COVERAGE-COMPLETE**. For plans
it is **the broad full-plan pass returning `PLAN-SOUND`** after the mechanical pre-pass + each
judgment angle is SOLID (every task executable, zero orphaned requirement, census fully covered).
Per-method details in the reference files.

**REQUIRED BACKGROUND:** the review discipline lives in the `/igr:codex-adversarial-loop` command —
read it if any invariant above is unclear.
