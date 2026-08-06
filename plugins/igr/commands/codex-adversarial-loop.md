---
description: Loop Codex adversarial-review on a target (spec / plan / code diff) until clean or max rounds, folding minimal fixes and parking over-engineering/breaking findings as Open Questions. Can be driven by a caller (igr-dev) with a single supplied focus/angle.
argument-hint: "[target-file] [max=10; 3 when --focus] [--focus \"angle\"] [--model <name>] [-- settled decisions to protect]"
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
- **--model \<name\>** (optional flag, anywhere in `$ARGUMENTS`): the Codex **review model** to pass to
  the companion (`adversarial-review --model <name>`). Use it when the default is wrong for your account
  — e.g. a ChatGPT-account login cannot use `gpt-5.3-codex`. **Precedence for the review model `<M>`
  is defined ONCE in hard-rule 1** (flag → env → config.toml → fallback) — do not restate it here.
  To set it once for **every** run (incl. when driven by `/igr:plan` / `/igr:brainstorm`),
  export `IGR_REVIEW_MODEL` — e.g. in `~/.claude/settings.json` `"env": { "IGR_REVIEW_MODEL": "gpt-5.6-sol" }`.
  **Review reasoning-effort is NOT settable** here — the companion's `adversarial-review` exposes
  `--model` but no `--effort` (only its `task` command does). Best-effort: set `model_reasoning_effort`
  in `${CODEX_HOME:-~/.codex}/config.toml` (may be ignored, like config `model` is). `IGR_REVIEW_EFFORT`
  is reserved for when the companion adds a review `--effort` flag (upstream). Impl effort IS settable
  (see `/igr:impl`).
- **settled** (everything after a literal `--`, optional): owner-settled decisions to protect
  from re-litigation this run, in addition to any the target already marks as settled.

### Single-focus (caller-driven) mode

When `--focus` is supplied, run in **single-focus mode**: loop that ONE angle to clean, report a
per-focus verdict, and return. Do **not** claim overall project convergence — the caller (e.g.
the `igr-dev` skill running a census of many angles) owns cross-angle convergence and decides
whether to run further angles. Without `--focus`, behave exactly as today: one self-directed
loop to the first clean pass over the whole target. Everything else (companion invocation,
the FOLD/DISCUSS/DROP router, no-codegraph, no-commit-docs) is identical in both modes.

## Hard rules (do NOT violate)

1. **Companion only.** Launch reviews via the Codex companion in `Bash(run_in_background:true)`.
   **NEVER** spawn the `codex:codex-rescue` Agent for a review — it has edit/commit tools and
   will auto-commit during a "review only". Resolve the companion path with the latest version:
   `ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1`
   then `node "<path>" adversarial-review --model "<M>" "<focus>"`. **If that glob is empty → the `codex` plugin is
   not installed: STOP and tell the user to run `/plugin install codex`** (do not fall back to the
   `codex:codex-rescue` Agent). `codex` is an external plugin (install from the `openai-codex` marketplace) — not a hard `plugin.json` dependency, so igr stays marketplace-agnostic.
   **Always pass `--model "<M>"`** — the codex `review` feature ignores `config.toml model` and falls back to a built-in default (`gpt-5.3-codex`) that a **ChatGPT-account** login cannot use (HTTP 400). Resolve **<M>** by precedence: the `--model` arg (Arguments) → `$IGR_REVIEW_MODEL` → the `model = "…"` line from `${CODEX_HOME:-~/.codex}/config.toml` → `gpt-5.5`. Never rely on the binary's review default.
2. **zsh eval gotcha — strip ALL backticks and `$` from the focus string**, or the companion
   crashes (`(eval): parse error`). Refer to code as `file colon line` plainly; no backticks.
3. **Launch exactly once per round**, redirected to a **unique** output file
   `/tmp/codex-loop-<worktree>-<topic>-r<N>.out` (worktree = basename of the cwd from rule 4;
   topic = a short slug of the target). The worktree component is what keeps **concurrent runs
   in sibling worktrees with same-named targets** (parallel PR-ladder rungs) from clobbering
   each other — /tmp is machine-global. For **concurrent angle-lanes against the SAME target in
   the SAME worktree** (the brainstorm round-parallel angle loop — see `references/brainstorm.md`
   §2), add a short **angle/lane slug** to the prefix too; otherwise same-target same-worktree
   jobs share a path and clobber. **Delete any pre-existing file at the path before
   launching** (a stale outfile from an earlier run already contains REVIEW-COMPLETE and would
   satisfy the poll instantly with an old verdict). Never point two runs at the same file. If a
   launch fails: run **one** foreground diagnostic (`pwd`, read the outfile, read the actual
   error) **before** relaunching — never re-fire blind, never spam.
4. **cwd must be the directory/worktree that contains the target** so untracked files (e.g. a
   new spec) are in the companion's working tree and reviewable. Verify with `pwd` first.
5. **Never git-commit docs** (the owner commits docs themselves). For non-doc targets, follow
   the repo's normal commit rules; for docs, leave the edits uncommitted and say so.
6. **The companion has no `--help`** — probing it **dispatches a real turn** (`… task --help` starts
   a codex thread with `--help` as the prompt and burns a turn). Read the usage string near the top
   of `codex-companion.mjs` instead. Note its own usage line omits `--model` for
   `adversarial-review`, but the flag **is** parsed (`valueOptions: [base, scope, model, cwd]`) —
   keep passing it per rule 1; there is still no `--effort` there.
7. Track via `/codex:status`. A **rejected** `Agent` tool-use can still leave a Codex job
   running — if that ever happens, tell the user the exact `/codex:cancel <id>` line to type
   (you cannot invoke `/codex:cancel` yourself).
8. **Environment seams — match known failure shapes on the outfile BEFORE calling a round "malformed"
   (rule 3).** These are tooling/env errors, **not review findings**; naming the cause saves the ~30-min
   "Codex did not return valid structured JSON" dead-end. These env-retries do **not** count toward the cap.
   - **`failed to initialize sqlite state runtime` / `app-server exited unexpectedly`** → a running
     **desktop Codex.app** holds a lock on `~/.codex`. Fix: quit it, OR re-run under a separate state home
     seeded with the login —
     `ALT=$(mktemp -d); cp -p ~/.codex/auth.json ~/.codex/config.toml "$ALT"/; chmod 600 "$ALT/auth.json"; CODEX_HOME="$ALT" node "<path>" adversarial-review --model "<M>" "<focus>"`
     — then `rm -rf "$ALT"` when done. **Caveat: this copies a live auth token into a temp dir — only on
     this error, keep it `0600`, clean it up.**
   - **`invalid_request_error` + `model is not supported`** → the review model is unavailable to this
     account. Retry the round **ONCE** with `--model` = the `config.toml model` (or another supported model);
     still failing → STOP and tell the user: *"Codex account cannot use review model &lt;X&gt; — set `IGR_REVIEW_MODEL` to a supported one (e.g. gpt-5.5)."*
   - Neither shape matched → the existing malformed-run path (rule 3: one foreground diagnostic, retry once).

## Setup (before round 1)

1. Parse `$ARGUMENTS` (above). `cd` to the directory/worktree that contains the target so
   untracked files are reviewable; verify with `pwd` (rule 4).
2. Read the target and, if it has one, its sibling spec / source. Locate the target's revision
   log and any owner-settled markers (e.g. "owner-settled", "do not re-litigate") so round 1
   can seed the don't-re-litigate list.
3. Derive the per-round outfile prefix: `<worktree>` = basename of the cwd (the
   directory/worktree from step 1) + `<topic>` = a short slug of the target filename (rule 3).
4. Initialize three empty lists: **FIXED** (folded), **PARKED** (Open Questions awaiting the
   human), **REFUTED** (dropped — false positive / already covered / out-of-scope). All three are
   fed to every later round's focus string (loop step 1); REFUTED is what stops a false positive
   from being re-raised each round.

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
   - **REFUTED**: findings already checked against the code and dropped, each with its one-line
     reason — "verified against the code and rejected, do NOT re-raise". Omit this and the same
     false positive returns every round;
   - **Do NOT re-litigate** these settled decisions: the `--` arg + any the target marks as
     owner-settled. If a reviewer keeps no-shipping a settled call, the fix is BOTH: pin it
     here AND harden the target to state the rule + the mechanism the reviewer keeps missing.
   - Framing: verify against the ACTUAL current code (read the cited files); **flag
     over-engineering as a defect — do not demand new features/abstractions**; output concrete
     findings with severity + file:line evidence; say `SPEC-SOUND` (or `PLAN-SOUND`) if clean;
     **end the output with the single final line REVIEW-COMPLETE** (the loop's completion
     sentinel — plain token, safe under rule 2).
2. **Announce** "codex-loop round N/max on <target>" to the user. **Launch** the companion
   (rule 1/3), `run_in_background: true` — only ONE companion job in flight at a time.
   **The harness completion notification is a launch-finished hint, NOT a read trigger** — the
   companion process exits before the review job finishes writing the outfile. After the
   notification, **poll the outfile for the `REVIEW-COMPLETE` terminator** (the sentinel the
   framing requested), e.g. `grep -q REVIEW-COMPLETE <outfile>` every ~20–30s; only on the
   sentinel **read the outfile** (not the task-output file — that is empty when stdout is
   redirected with `>`). **Stall rule:** sentinel absent AND the outfile size unchanged for
   ~3 min → stop polling and triage **in this order**:
   1. **READ the outfile and look for a written verdict** (`SPEC-SOUND` / `PLAN-SOUND` /
      `ANGLE-SOLID` / a findings list). The reviewer sometimes writes its full verdict and stops
      **without emitting the sentinel** (~3 of 12 rounds observed) — that round is **COMPLETE, not
      stalled**. Confirm nothing is still writing (`pgrep -f adversarial-review` empty) and consume
      the verdict. Calling this a FAILED round and relaunching wastes a whole round; a
      sentinel-only poller burns the entire timeout (~17 min observed once).
   2. Verdict absent → **match the content against the rule-8 env-error shapes** (sqlite lock /
      model-not-supported) and act on the specific cause.
   3. Neither → generic FAILED round: one foreground diagnostic (rule 3), fix the cause, retry that
      round once — do not count it toward the cap or loop blindly.

   (File still growing → keep waiting.)
3. **Route every finding — FOLD / DISCUSS / DROP** — this is the core discipline. A codex finding
   is usually **not** a bug; it is often pressure to close or harden a point that does not need
   it. Exactly ONE disposition per finding, announced. **Execute the gates in order — do not
   pattern-match the categories:**
   - **Q0 verify** — does the cited code/contract actually say what Codex claims? **Read the
     file:line.** No → **DROP**.
   - **Q1 new** — does the fix introduce something that does not exist yet (abstraction, module,
     config knob, protocol/schema, policy choice, exhaustive test matrix, broadened scope)? Yes →
     **DISCUSS**.
   - **Q2 settled** — does it touch an owner-settled decision, an immutable `## Mental Model`, a
     security / trust-boundary posture, a scope-or-ownership seam, or depend on an infra/platform
     fact you have not verified? Yes → **DISCUSS**.
   - None of the above → **FOLD**. **Unsure at any gate → DISCUSS** (bias to asking the human,
     never to silently expanding scope).

   What each disposition does:
   - **FOLD** → **apply to the target now**, minimal: faithfulness correction, wrong line ref, a
     missing precondition/guard, tightening a test, narrowing/widening an EXISTING invariant. An
     inconsistency your own earlier folds created is FOLD-eligible by default.
   - **DISCUSS** → **do NOT apply.** Append to the target's `## Open Questions (awaiting human
     resolution)` section **and** print it in this round's report with a recommendation. The loop
     does **not** block on it (park-don't-pause, step 5):
     ```
     ### OQ<k>: <title>  [R<N> codex finding]
     - Finding: ...
     - Why deferred: <Q1 new abstraction/scope | Q2 settled/security/seam/unverified-fact>
     - Suggested: A) ...  B) ...   Recommend: <X, why>
     - Status: AWAITING HUMAN
     ```
     A feasibility-dependent fix: verify the fact inline if that is cheap; if it needs
     infra/platform truth you do not have, it is DISCUSS — never a silent fold.
   - **DROP** → one line, and it **must cite** the code line that refutes it, the invariant that
     already covers it, or the out-of-scope/follow-up entry. **No cite → DISCUSS, not DROP.**
     Add it to the **REFUTED** list (Setup step 4) — carried into every later round's focus
     string. **Without the REFUTED list a false positive is re-raised every single round for the
     life of the loop.**

   **Round report format:**
   ```
   FOLD:    <finding> — <the wrong assumption, file:line> — <the minimal edit>
   DISCUSS: <finding> — <the decision> — A) … B) … — recommend: <X, why>
   DROP:    <finding> — refuted by <file:line> | covered by <invariant> | out-of-scope <ref>
   ```

   **The mix is a convergence signal:** a round returning zero FOLD (all DISCUSS/DROP) means this
   angle is exhausted — report that, do not keep grinding for a "clean" pass.
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
- the **FIXED** changelog (what was FOLDed across rounds);
- the **Open Questions** list — every DISCUSS, each with its recommendation (the only thing
  awaiting the human);
- the **REFUTED** list — every DROP with its one-line cite (so the human can audit what was
  thrown away, and a later run does not re-litigate it);
- the **per-round disposition mix** (FOLD / DISCUSS / DROP counts) — a tail of rounds with zero
  FOLD is the exhaustion signal;
- final verdict and the path to the (uncommitted, for docs) revised target.

**In single-focus mode**, frame the final verdict as a compact **per-focus result** the caller
can consume: the angle reviewed, its verdict (`SPEC-SOUND` / `PLAN-SOUND` / needs-attention),
what was FOLDed, what is DISCUSS-pending, what was DROPped. Do not recommend overall stop —
return control to the caller.

Then let the human (or the calling director) resolve the Open Questions and decide on any
further rounds / angles.
