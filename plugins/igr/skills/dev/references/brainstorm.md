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
land there) and a revision log (the loop bumps it) — **both are working-state only**: step 3
resolves and empties the OQs, the clean-rewrite (step 4) strips the log, and the final spec
carries **no record of the runs** (audit lives in the sidecar — see §Budget). Never git-commit
the spec — the owner commits docs themselves.

## Mental Model contract (write once, immutable — the Drift-A gate)

Before hardening, capture the **as-designed mental model** — a ≤ 50-line PM + staff-eng *changeset
inventory* of what the spec commits to build. It guards the two distinct drifts this method exists
to catch:

- **Drift A — intent vs model, caught HERE by the owner.** The owner reads the model against *what
  they actually intend* and catches the gap: a capability obvious to them that never reached the
  spec, a removal they didn't mean, a tech they'd veto. Something obvious to the human is often not
  obvious to the producer — this is where that shows up. Far cheaper to fix now than after ~16
  hardening rounds on an already-off spec.
- **Drift B — hardening vs contract, caught at exit by the method (step 7).** This frozen model is
  the baseline that step 7 diffs the hardened spec against.

**When.** Right after the Producer writes the spec. If the input was **already a spec**: reuse its
`## Mental Model` section if present; else generate one from the incoming spec now.

**How.** Inline (main model — the spec is in context; **no codex, no subagent**). Write it into the
spec as a top-level `## Mental Model` section in this exact shape (fixed so the step-7 diff is
clean — deliverables match by meaning, not line):

```
## Mental Model (as-designed — immutable)

_The design this spec commits to. Immutable contract — the hardened spec must honor it;
the method reports any drift at exit._

**Ships:** <one line — what capability lands, for whom>

**Deliverables** — changeset vs current system
- ADD    **<cap>** — <what it does> · <tech/approach>
- CHANGE **<cap>** — <what changes> · <tech>
- REMOVE **<cap>** — <what goes, why> · <replaced-by, if any>
```

Each deliverable is ONE line fusing **capability × the tech chosen for it**, tagged ADD / CHANGE /
REMOVE vs the current system (greenfield → all ADD). **Only what gets supplied** — no non-goals, no
risk section; those are not what the owner scans for omissions. Group under sub-headers only if
deliverables exceed ~8 and span separate subsystems; otherwise keep one flat, scannable list.

**The Drift-A gate (STOP — owner reviews before hardening).** Present the model in chat and ask the
owner directly: *does this match your intent? anything you expected that's missing, or here you
didn't intend?* Fold the answer — a real gap means the **spec** is wrong (fix it) or the **model**
misread it (fix the model); converge both to the agreed intent. **Only on the owner's sign-off**
freeze the section and start the census (§1).

**Immutable thereafter.** The method NEVER auto-edits `## Mental Model` once frozen — not in a
per-angle fold, not in the clean-rewrite (step 4 KEEPs it verbatim). If hardening legitimately
forces a design change, that surfaces as **Drift B at exit** for the owner to reconcile
deliberately — the contract is not silently rewritten to match. (The section's tokens don't match
the exit-gate grep in §6, so it rides through the gate untouched.)

## Reviewer recipe (EXPLORATORY)

### 1. Step 0 — census (enumerate, do NOT review)

One companion call whose job is to *list the review angles*, not to review. Focus text shape (no
backticks, no `$`):

> Enumerate every review angle for the spec at SPEC_PATH as a checklist. For each angle give: the
> specific claim the spec makes, and the exact code location (file colon line) to verify it
> against. Do NOT review or fix anything yet — output only the angle backlog. Do NOT run codegraph
> (it hangs); use rg and sed only.

This yields an **angle backlog**. Seed your reading of it with the taxonomy below, but the census
exists to surface **doc-specific** angles you would not have listed — keep those.

**Cluster, rank, cap at 5.** The raw census often emits 12–15 fine-grained angles — do NOT loop
them one-by-one. Cluster near-duplicates into ONE focus each (e.g. error-path + fallibility over
the same surface = one loop); rank the clusters by risk — data-loss / isolation / correctness
first, mechanics / wiring last; **run at most 5 angle-clusters**. Whatever doesn't fit: fold into
the nearest cluster's focus text, or list it in the backlog as `UNPROBED` for the owner to see at
the next checkpoint — **never silently drop it, never silently run a 6th**.

### 2. Per-angle loop

For each angle in the backlog, drive L1 in single-focus mode:

`/igr:codex-adversarial-loop SPEC_PATH 7 --focus "<angle text>"`

where `<angle text>` names the one failure-class + the code location + the standard framing
(verify against actual code; no codegraph; flag over-engineering; no backticks/`$`). L1 loops that
angle to clean and returns a per-focus verdict.

The `7` is the **per-angle cap**, passed as L1's `max` arg (overriding its single-focus default of
3 — spec angles run without census grounding, so they get more headroom than the plan method's 3).
An angle not `SPEC-SOUND` at 7 → **STOP and ASK the owner**, same diagnostic as the plan method:
are the remaining findings NEW failure-classes (legit progress — the owner may grant another
batch) or re-raises/churn (a stall — fix the process, don't spend rounds)?

- **Verify** each finding against the cited code before folding (Codex is a lead-generator).
- **Fold minimal, park scope** (invariant 6). Faithfulness/ref/guard/narrow-correctness → apply;
  new abstraction/knob/module or broadened scope → park to Open Questions, keep going.
- Mark an angle **cleared** when it returns `SPEC-SOUND`.
- **Append-on-discovery (within the cap):** a finding that reveals a new failure-class → **fold it
  into the nearest of the 5 clusters** (widen that cluster's focus text). If it fits none, do NOT
  silently add a 6th angle — list it as `UNPROBED`; the owner decides at the next checkpoint
  whether to grant it a slot.

### 3. Owner resolves Open Questions (STOP — before the rewrite)

Once angles are largely cleared, **STOP and present every parked Open Question to the owner**.
Fold each answer into the spec as a settled decision (a substantive fold → re-run the affected
angle once). **The method does not end with OQs in the spec** — parking is a mid-run state, not
an output. Only when the OQ section is empty proceed to the rewrite (so the rewrite bakes the
decisions in, and the fresh read covers them too).

### 4. Clean-rewrite pass (LOAD-BEARING — not cosmetic)

Rewrite the spec into a **clean, one-pass, authoritative doc**: strip ALL round-by-round churn,
version-tracing, patch-history, the revision log, round tags, and the (now empty) Open Questions
section; **KEEP** every decision, its reasoning, and every rejected alternative, and **KEEP the
`## Mental Model` contract section verbatim** — it is the immutable as-designed contract, not
run-churn; never rewrite, reword, or drop it. This step is
load-bearing because the rewrite forces a fresh read that exposes bugs the annotated doc hid —
several real bugs surfaced ONLY here.

### 5. Re-census + per-angle on the clean doc

New angles appear post-rewrite (the doc reads differently). Re-run the census on the clean doc,
**re-cluster to ≤ 5** (same cap + ranking as §1), and loop the fresh angles. A new finding that
parks an OQ → resolve it with the owner (step 3 rules) before the exit gate.

### 6. Exit gate (the STRONG stop — ALL must hold)

The spec is DONE only when **every one** of these holds — a checklist, not a vibe:

1. **Every census angle cleared** (`SPEC-SOUND`) — including the post-rewrite re-census angles.
2. **Completeness critic** returned `COVERAGE-COMPLETE` (below).
3. **Zero Open Questions** — resolved by the owner (steps 3/5) and folded; the section is gone.
4. **No record of the runs** — clean-rewrite done; deterministic self-check, run it:
   `grep -nE 'Open Questions|AWAITING HUMAN|rounds-spent|Revision log|\[R[0-9]+' SPEC_PATH`
   → **zero hits**, or the gate FAILS (go back to the step that leaks).

Report on exit: the clean spec path + the sidecar audit log path (§Budget) + the **Drift-B verdict**
(step 7). Skipping the rewrite,
the re-census, or OQ resolution = the method did NOT finish, whatever the angle verdicts say.

The completeness critic is one call that asks: *what failure-class has NOT
been probed?* — and finds nothing new. Focus shape:

> For the spec at SPEC_PATH, do not re-review cleared angles. Ask only: what failure-class has NOT yet
> been probed at all? List any unprobed class with the code location to check, or say
> COVERAGE-COMPLETE if none remain. No codegraph; rg and sed only. No backticks or dollar signs.

If the critic (or the `UNPROBED` list) names an unprobed class, **ASK the owner**: grant it an
angle slot or explicitly accept the gap — never silently drop it, never silently exceed the cap.

This is **NOT** "one clean pass." Convergence signal in practice: angles return `SPEC-SOUND`
first-try and findings degrade to consistency-of-your-own-edits rather than code gaps.

### 7. Drift check (Drift B — as-hardened vs the contract)

After the exit gate passes, **re-derive** the mental model from the **final clean spec** (model #2 —
same template, inline, no codex) and **semantically diff** it against the frozen `## Mental Model`
contract: match deliverables by *meaning*, not text — a rewording is not drift; an added / dropped /
re-teched capability is. Report in **chat** (and append to the sidecar §Budget as audit) — **never
back into the spec, never auto-editing the contract**:

```
Drift vs Mental Model (as-hardened):
- ADDED:   <capability not in the contract> · <tech>
- REMOVED: <contract capability now gone>
- CHANGED: <cap> — contract said X; hardened spec does Y   ← intended?
- <unchanged deliverables, listed by name>
Verdict: HONORS CONTRACT  |  DRIFTED (<n> deltas)
```

Drift B is a **report, not an auto-fix**: the method surfaces the deltas; the **owner** decides
whether hardening improved the design (amend the contract deliberately) or wandered off it (a
regression to fix). A `DRIFTED` verdict does NOT block the exit — the spec is DONE per §6 — it is
the owner's signal to reconcile. Fold the verdict into the exit report.

## Budget & checkpoints (stage-separate)

This stage owns its **own** budget — separate from the plan method's (which has a 10-round stage
budget of its own). Three tiers:

- **Angle cap = 5 clusters** per census pass (§1 — cluster + rank; overflow → `UNPROBED`,
  owner-gated at checkpoints).
- **Per-angle cap = 7** (§2 above — passed as L1's `max`; STOP-and-ASK on a capped angle).
- **Checkpoint every ~10 cumulative codex rounds** — count EVERY companion call: the census,
  per-angle rounds, the re-census, the completeness critic. Report the scoreboard — angles
  cleared / remaining / added-on-discovery, FIXED count, PARKED count, rounds spent — and ASK the
  owner: continue / narrow / stop. A checkpoint is a **human gate, not a kill**: append-on-discovery
  grows the backlog legitimately; this is where the owner sees why.
- **Hard backstop ~30 rounds total** — stop regardless, dump the state + the remaining backlog.
  The safety net for unattended runs.

**The counter lives in a SIDECAR, not the conversation and not the final spec:** keep
`rounds-spent: N` + the FIXED/PARKED ledger + checkpoint scoreboards + the step-7 Drift-B report in
**`<prefix>-brainstorm-log.md`** (scratch; survives compaction / session resume; never committed,
deletable after). The working spec's revision log is fine mid-run, but the exit gate requires the
FINAL spec to carry no run records — the sidecar is where the audit trail lives instead. L1
reports rounds-run per invocation in its final report — sum those into the sidecar; do not
recount from memory.

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
