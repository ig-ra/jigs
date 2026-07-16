# Impl handoff — <TICKET> / <PREFIX>

You are implementing an already-hardened plan. You are **codex**; you do NOT have the igr plugin,
so run the method natively with your **superpowers** skills (you DO have those).

## Method
Drive the plan with **superpowers:executing-plans** + **superpowers:subagent-driven-development** —
subagent-driven, scope-locked, task by task (failing test -> minimal code -> refactor, per
superpowers:test-driven-development).

## Plan
Read the plan at its ABSOLUTE path (it lives in the owner's tree, uncommitted — do NOT expect it in git):
  <ABS_PLAN_PATH>
Its `## Appendix: Code Census` is the ground-truth facts; re-resolve every symbol anchor at HEAD
before editing (anchors drift).

## Gate cadence
- During implementation: focused per-task checks only (the task's own tests + a quick build of the
  touched crate/package).
- After ALL tasks: **squash to one commit**, THEN run the target repo's **full gate ONCE** on the
  squashed commit:
    <RESOLVED_GATE_CMD>
  (build + lint + format + tests + behavior-net; explain-counters / invariants must not move.)
- Never commit docs / generated dirs.

## Commits
Commit per the repo's rules. **STOP before push / PR / merge / rebase** — that is the owner + the
workflow layer, not you.

## Done
All plan tasks implemented + full gate green on the final squashed commit. Report the final SHA.
