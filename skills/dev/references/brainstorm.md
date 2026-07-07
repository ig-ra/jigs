# igr-dev: brainstorm method (idea → spec)

The richest method. Turn an idea into a hardened spec via **exploratory** review: a census
discovers the angles, per-angle Codex loops exhaust each failure-class, and a load-bearing
clean-rewrite forces fresh reading. This profile was derived by hardening a real spec across ~16
Codex rounds; the angle-driven + clean-rewrite approach caught real bugs that generic looping
missed (see **Why these steps**).

**Preflight:** needs the `superpowers` and `codex` plugins — verify per SKILL.md §Preflight; if absent, STOP with the `/plugin install` line.

## Producer

Use **`superpowers:brainstorming`** to turn the idea into a spec (Q&A → design → spec doc). If the
input `<target>` is **already a spec path**, skip production and go straight to hardening.

The spec doc must carry a `## Open Questions (awaiting human resolution)` section (parked findings
land there) and a revision log (the loop bumps it). Never git-commit the spec — the owner commits
docs themselves.

## Reviewer recipe (EXPLORATORY)

### 1. Step 0 — census (enumerate, do NOT review)

One companion call whose job is to *list the review angles*, not to review. Focus text shape (no
backticks, no `$`):

> Enumerate every review angle for the spec at PATH as a checklist. For each angle give: the
> specific claim the spec makes, and the exact code location (file colon line) to verify it
> against. Do NOT review or fix anything yet — output only the angle backlog. Do NOT run codegraph
> (it hangs); use rg and sed only.

This yields an **angle backlog**. Seed your reading of it with the taxonomy below, but the census
exists to surface **doc-specific** angles you would not have listed — keep those.

### 2. Per-angle loop

For each angle in the backlog, drive L1 in single-focus mode:

`/igr:codex-adversarial-loop PATH --focus "<angle text>"`

where `<angle text>` names the one failure-class + the code location + the standard framing
(verify against actual code; no codegraph; flag over-engineering; no backticks/`$`). L1 loops that
angle to clean and returns a per-focus verdict.

- **Verify** each finding against the cited code before folding (Codex is a lead-generator).
- **Fold minimal, park scope** (invariant 6). Faithfulness/ref/guard/narrow-correctness → apply;
  new abstraction/knob/module or broadened scope → park to Open Questions, keep going.
- Mark an angle **cleared** when it returns `SPEC-SOUND`.
- **Append-on-discovery:** a finding that reveals a new failure-class **adds an angle** to the
  backlog. The backlog grows as you learn.

### 3. Clean-rewrite pass (LOAD-BEARING — not cosmetic)

Once angles are largely cleared, rewrite the spec into a **clean, one-pass, authoritative doc**:
strip ALL round-by-round churn, version-tracing, and patch-history; **KEEP** every decision, its
reasoning, and every rejected alternative. This step is load-bearing because the rewrite forces a
fresh read that exposes bugs the annotated doc hid — several real bugs surfaced ONLY here.

### 4. Re-census + per-angle on the clean doc

New angles appear post-rewrite (the doc reads differently). Re-run the census on the clean doc and
loop the fresh angles.

### 5. Stop condition (the STRONG stop)

Stop when **every census angle is cleared** AND a **completeness-critic** pass returns
`COVERAGE-COMPLETE`. The completeness critic is one call that asks: *what failure-class has NOT
been probed?* — and finds nothing new. Focus shape:

> For the spec at PATH, do not re-review cleared angles. Ask only: what failure-class has NOT yet
> been probed at all? List any unprobed class with the code location to check, or say
> COVERAGE-COMPLETE if none remain. No codegraph; rg and sed only. No backticks or dollar signs.

This is **NOT** "one clean pass." Convergence signal in practice: angles return `SPEC-SOUND`
first-try and findings degrade to consistency-of-your-own-edits rather than code gaps.

## Spec angle taxonomy (seed the census)

Generalizes across specs — but let the census discover doc-specific angles too:

- **faithfulness / grounding** — every file:line cite resolves to what the spec claims
- **type / object-safety** — trait/interface shapes actually compile as described
- **behavior-preservation** — counters / order / semantics unchanged by a refactor
- **boundary / relocation** — what moves where; nothing stranded that won't compile
- **isolation / security** — tenant boundaries, exact-instance handling, footguns
- **mechanics / wiring** — deps, config, log filters, build
- **error-path / concurrency** — panic vs Err, partial-failure, budgets
- **fallibility / contract** — a method that does I/O must return a fallible/Result-shaped
  contract, not infallible
- **scope / over-engineering** — flag anything broadening beyond the stated goal (as a defect)

## Why these steps (evidence the profile is shaped this way)

Hardening `docs/igr/r3-needle-compaction.md` across ~16 rounds, the angle-driven + clean-rewrite
method caught real bugs a generic loop missed: an object-key path helper keyed by the wrong field
(tenant-data-loss class); a "moved" helper that actually applied root-only side effects (had to
stay put); an I/O port method specified **infallible** when the real one returns `Result` (would
silently swallow fail-closed behavior); a GC cache-eviction that fires mid-function and would be
lost if batched onto the return value; an over-exposed enumerator that reopened an isolation
bypass. Two lessons: (a) the **clean-rewrite is not cosmetic** — several bugs surfaced only on
fresh reading; (b) **angles beat generic looping** — a generic "review this" plateaus after 1–2
findings; directing Codex at one failure-class exhausts it.
