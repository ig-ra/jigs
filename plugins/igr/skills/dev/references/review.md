# igr-dev: review method (diff → fixed code)

This method **defines how code review is done**, and FIXES what it finds. It is the **claude-side**
review — it does **not** use the Codex companion, so the companion invariants (SKILL.md invariants
1–4, 8) do not apply here; verify-before-fold, park-vs-apply, and never-commit-docs (5–7) do.

**Preflight:** needs the `superpowers` plugin (`receiving-code-review`) — verify per SKILL.md §Preflight; if absent, STOP with the `/plugin install` line. (No Codex companion here.)

## Session

**Ensure you are in a claude session.** This method reviews and fixes the diff — it does **not**
run a build/test gate (do not re-run one here).

## Scope

**All committed branch work vs the branch's base** — always; no per-run range/target arg. The
diff is `git diff <base>...HEAD` (**three-dot** = vs the merge-base, i.e. where the branch was
taken from — two-dot would drag in the base's newer commits): base = `origin/main` (fall back
`main`); a stacked rung based on a parent branch uses the parent as base. The tree must be
committed — verify the diff is non-empty before reviewing. (In the pipeline flow the branch is
one squashed commit on the base, so this equals the single-commit diff.)

## Review flow (exactly this)

1. **`/simplify`** scoped to the diff — the code-simplifier pass (reuse / simplification /
   efficiency / altitude). E.g. `/simplify the changes in git diff origin/main...HEAD` (the
   branch diff from §Scope; no preserve-X essays).
2. **`/igr:code-review-skip-simplify <effort>`** — correctness angles + conventions, skipping the
   cleanup angles `/simplify` already covered. **Default effort `xhigh`** (tunable: `high` |
   `xhigh` | `max`; a trivially-mechanical rung MAY be downgraded to `/code-review high`, but
   `xhigh` is the default).

Process findings with rigor — **`superpowers:receiving-code-review`** (verify, don't perform
agreement).

## Triage + fix

Fix only **simple + needed**; **park complex / risky** findings (invariant 6) and escalate. Apply
the confirmed fixes to the code.

## Commits

Single-squashed-commit branch (the pipeline flow) → **amend** the fixes into that commit
(`git add` tracked files only, never the untracked docs dir). Multi-commit branch (standalone
run) → commit the fixes as a new commit per the repo's rules — do not amend history. **No PR /
merge** — that belongs to the workflow layer, not this method.

## Stop

Every confirmed finding fixed or parked; the diff is clean over both passes. Hand any parked Open
Questions to the owner.
