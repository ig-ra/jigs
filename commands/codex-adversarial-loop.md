---
description: Loop Codex adversarial-review on a target (spec / plan / code diff) until clean or max rounds, folding minimal fixes and parking over-engineering/breaking findings as Open Questions. Can be driven by a caller (igr-dev) with a single supplied focus/angle.
argument-hint: "[target-file] [max=10; 3 when --focus] [--focus \"angle\"] [-- settled decisions to protect]"
allowed-tools: Bash, Read, Edit
---

# Codex adversarial-review loop

Run **repeated** Codex adversarial-review rounds against a target, fold the findings, and
keep going until the review converges (clean pass) or a round cap is hit. This is the
deterministic version of "read the codex-review memory and loop with codex."

## Arguments

Parse positionally from `$ARGUMENTS` (a single string) — do not rely on `$1`/`$2`
substitution:

- **target** (first token, optional): path to the artifact to review — a spec, a plan, or a
  doc. If omitted, review the working-tree **diff / branch** (the companion's default).
- **max** (second token, optional): max rounds. **Default 10** (self-directed whole-target
  mode); **default 3 when `--focus` is supplied** (single-focus mode — one narrow angle should
  converge fast; the caller owns the cross-angle budget and overrides explicitly when an angle
  warrants more, e.g. the brainstorm method passes 7).
- **--focus "\<text\>"** (optional flag, anywhere in `$ARGUMENTS`): a caller-supplied angle /
  framing for this run — typically ONE review dimension from a larger census. Strip it out
  before positional parsing, then use `\<text\>` as the core of every round's focus instead of
  inventing a generic "review this" framing. This is the L1/L2 seam: a director (the `igr-dev`
  skill) builds the angle; L1 runs it. Keep the text free of backticks and `$` (rule 2).
- **settled** (everything after a literal `--`, optional): owner-settled decisions to protect
  from re-litigation this run, in addition to any the target already marks as settled.

### Single-focus (caller-driven) mode

When `--focus` is supplied, run in **single-focus mode**: loop that ONE angle to clean, report a
per-focus verdict, and return. Do **not** claim overall project convergence — the caller (e.g.
the `igr-dev` skill running a census of many angles) owns cross-angle convergence and decides
whether to run further angles. Without `--focus`, behave exactly as today: one self-directed
loop to the first clean pass over the whole target. Everything else (companion invocation,
triage, park-vs-apply, no-codegraph, no-commit-docs) is identical in both modes.

## Hard rules (do NOT violate)

1. **Companion only.** Launch reviews via the Codex companion in `Bash(run_in_background:true)`.
   **NEVER** spawn the `codex:codex-rescue` Agent for a review — it has edit/commit tools and
   will auto-commit during a "review only". Resolve the companion path with the latest version:
   `ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1`
   then `node "<path>" adversarial-review "<focus>"`. **If that glob is empty → the `codex` plugin is
   not installed: STOP and tell the user to run `/plugin install codex`** (do not fall back to the
   `codex:codex-rescue` Agent). `codex` is an external plugin (install from the `openai-codex` marketplace) — not a hard `plugin.json` dependency, so igr stays marketplace-agnostic.
2. **zsh eval gotcha — strip ALL backticks and `$` from the focus string**, or the companion
   crashes (`(eval): parse error`). Refer to code as `file colon line` plainly; no backticks.
3. **Launch exactly once per round**, redirected to a **unique** output file
   `/tmp/codex-loop-<topic>-r<N>.out` (topic = a short slug of the target). Never point two
   runs at the same file. If a launch fails: run **one** foreground diagnostic (`pwd`, read the
   outfile, read the actual error) **before** relaunching — never re-fire blind, never spam.
4. **cwd must be the directory/worktree that contains the target** so untracked files (e.g. a
   new spec) are in the companion's working tree and reviewable. Verify with `pwd` first.
5. **Never git-commit docs** (the owner commits docs themselves). For non-doc targets, follow
   the repo's normal commit rules; for docs, leave the edits uncommitted and say so.
6. Track via `/codex:status`. A **rejected** `Agent` tool-use can still leave a Codex job
   running — if that ever happens, tell the user the exact `/codex:cancel <id>` line to type
   (you cannot invoke `/codex:cancel` yourself).

## Setup (before round 1)

1. Parse `$ARGUMENTS` (above). `cd` to the directory/worktree that contains the target so
   untracked files are reviewable; verify with `pwd` (rule 4).
2. Read the target and, if it has one, its sibling spec / source. Locate the target's revision
   log and any owner-settled markers (e.g. "owner-settled", "do not re-litigate") so round 1
   can seed the don't-re-litigate list.
3. Derive a short topic slug from the target filename for the per-round outfile names.
4. Initialize empty **FIXED** and **PARKED** (Open Questions) lists.

## The loop

For round `N` = 1 .. max:

1. **Build the focus string** (no backticks, no `$`). Include:
   - the target path and a one-line task framing. **If `--focus "<text>"` was supplied, use
     `<text>` verbatim as that angle / task framing** (single-focus mode); otherwise derive a
     generic framing from the target as before;
   - **FIXED so far**: a short changelog of what prior rounds already resolved (so Codex sees
     current state and does not re-raise resolved items);
   - **PARKED / Open Questions**: items already deferred to the human — "acknowledged-deferred,
     do NOT re-flag as new findings";
   - **Do NOT re-litigate** these settled decisions: the `--` arg + any the target marks as
     owner-settled. If a reviewer keeps no-shipping a settled call, the fix is BOTH: pin it
     here AND harden the target to state the rule + the mechanism the reviewer keeps missing.
   - Framing: verify against the ACTUAL current code (read the cited files); **flag
     over-engineering as a defect — do not demand new features/abstractions**; output concrete
     findings with severity + file:line evidence; say `SPEC-SOUND` (or `PLAN-SOUND`) if clean.
2. **Announce** "codex-loop round N/max on <target>" to the user. **Launch** the companion
   (rule 1/3), `run_in_background: true` — only ONE companion job in flight at a time. Wait for
   completion (the harness notifies), then **read the unique outfile** (not the task-output
   file — that is empty when stdout is redirected with `>`). If the outfile has no verdict /
   findings section (crashed or malformed run), treat it as a FAILED round: run one foreground
   diagnostic (rule 3), fix the cause, retry that round once — do not count it toward the cap
   or loop blindly.
3. **Triage every finding** — this is the core discipline:
   - **Minimal / clear** (faithfulness correction, wrong line ref, a simple missing
     precondition/guard, tightening a test, a narrow correctness fix — **no** new abstraction,
     config knob, broadened scope, or architectural change) → **apply to the target now**.
   - **Over-engineering OR breaking / major change** (new abstraction/module/knob, broadened
     scope, architectural shift, or contradicts a settled decision) → **do NOT apply** → append
     to the target's `## Open Questions (awaiting human resolution)` section:
     ```
     ### OQ<k>: <title>  [R<N> codex finding]
     - Finding: ...
     - Why deferred: adds <new abstraction / scope / breaking change> beyond a minimal fix
     - Suggested: A) ...  B) ...
     - Status: AWAITING HUMAN
     ```
   - If genuinely unsure whether a fix counts as over-engineering, **park it** (bias to asking
     the human, not to silently expanding scope).
4. **Bump the revision** and update the target's revision log with the round's fixed list +
   any new Open Questions. Do not commit docs.
5. **Stop conditions** (check after applying):
   - **Converged** — the pass returned zero new findings, or every remaining finding is already
     a parked Open Question (`SPEC-SOUND` / `PLAN-SOUND`). → **STOP. Recommend stop; do not
     dangle another round.** A clean pass IS the stop signal. (In single-focus mode this means
     THIS angle is clean — return the per-focus verdict to the caller; the caller, not this
     command, decides overall convergence.)
   - **Cap** — `N == max`. → **STOP**, report "hit max rounds, M findings still open".
   - Otherwise continue to round `N+1` automatically (park-don't-pause: never block the loop on
     the human mid-run).

## Final report

When the loop stops, report:
- rounds run and why it stopped (converged vs cap);
- the FIXED changelog (what changed across rounds);
- the **Open Questions** list for the human to resolve (the only thing awaiting them);
- final verdict and the path to the (uncommitted, for docs) revised target.

**In single-focus mode**, frame the final verdict as a compact **per-focus result** the caller
can consume: the angle reviewed, its verdict (`SPEC-SOUND` / `PLAN-SOUND` / needs-attention),
what was folded, what was parked. Do not recommend overall stop — return control to the caller.

Then let the human (or the calling director) resolve the Open Questions and decide on any
further rounds / angles.
