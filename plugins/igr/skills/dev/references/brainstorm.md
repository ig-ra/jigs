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

| tag | capability | tech / where |
|-----|------------|--------------|
| ADD | <what it does> | <tech · path> |
| CHANGE | <what changes> | <tech · path> |
| REMOVE | <what goes, why — replaced-by if any> | <tech · path> |

**Unchanged:** <existing behavior this explicitly does NOT touch>
```

Each deliverable is ONE table row fusing **capability × the tech chosen for it**, tagged ADD /
CHANGE / REMOVE vs the current system (greenfield → all ADD). **Only what gets supplied** — no
non-goals, no risk section; those are not what the owner scans for omissions. The one boundary line
allowed is **Unchanged** — existing behavior the change explicitly preserves — because a
wrongly-touched invariant IS an omission the owner scans for. Split into more than one table under
sub-headers only if deliverables exceed ~8 and span separate subsystems; otherwise keep one flat,
scannable table.

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

## Route: FOCUSED vs FULL (triage — decided at the Drift-A gate)

Not every spec needs the full machinery. Running the whole census → 5-cluster → 7-cap →
clean-rewrite → re-census pipeline on a small, single-purpose, code-verified spec burns dozens of
codex rounds where 1–3 focused ones carry all the value (observed on real runs: a 1-round spec
beside a 45-round spec of similar length). **Decide the route at the Drift-A gate** — the Mental
Model changeset inventory is already the signal, so this costs nothing extra:

- **FOCUSED** — ≤ 3 real angles, low/med blast radius, spec authored clean in one pass. Signals
  from the Mental Model: few deliverables and **no** high-blast class among them (data-loss /
  isolation / concurrency / security / migration / tenant-boundary). Run: census (to name the ≤ 3
  angles) → the round-parallel angle loop (§2) on those angles → **the clean-rewrite (§4)** →
  completeness critic (§6) on the fresh doc → Drift-B (§7). **KEEP the clean-rewrite** — it is
  inline (no codex rounds) and its fresh read bubbles up hidden problems regardless of how clean the
  doc looked; that bug-surfacing is load-bearing even here. **SKIP only the full re-census +
  re-angle-loop (§5)** — the expensive part. The completeness critic on the fresh doc is the
  lightweight closure; if the fresh read flags something concrete, spend ≤ 1 focused round on it
  rather than re-running the whole census machinery. (Resolve OQs §3 before the rewrite as usual.)
- **FULL** — ≥ 4 angles, OR any high-blast class present, OR a messy multi-pass / heavily-revised
  spec. Run the whole recipe §1–§7 as written.

**The owner confirms the route at the Drift-A stop** (already there): e.g. "read as FOCUSED — 3
angles, low blast; census + 3 parallel angle loops + fresh-rewrite + critic + drift, no re-census,
~minutes. Override to FULL?"

**Guard — TWO branches, do not compress them into one sentence.** When a high-blast class
(data-loss / isolation / concurrency / security / migration / tenant-boundary) is present in the
Mental Model:
- **Default → route FULL**, regardless of angle count; or
- **the owner may hold the route at FOCUSED** — and then that class gets **≥ 1 dedicated angle
  round of its own**, named as such in the backlog.

FOCUSED with no round on the high-blast class is not an available option. The owner may always
override upward. (Stated as branches because the single-sentence form — "forces FULL (or at minimum
one round)" — reliably gets paraphrased down to "forces FULL", which wrongly tells the owner they
cannot route down at all.) FOCUSED still runs **real** adversarial review on the named angles — it
drops the exhaustive ceremony, not the review.

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

### 2. Angle loop — ROUND-PARALLEL (independent angles run concurrently)

The ≤ 5 angle-clusters are **independent failure-classes over the same spec** (kept immutable
*during* a review batch), so their codex reviews are safe to run at the same time. Serial
per-angle looping is the biggest avoidable wall-clock cost — each round is a 2–6 min codex wait,
and running the angles one-at-a-time simply sums those waits (measured on real runs: strictly
serial, zero overlap). **Invert it: parallelize the slow REVIEW, serialize the fast FOLD.**

Per round:

1. **Launch every still-open angle's review concurrently** — one backgrounded companion job per
   angle (`Bash run_in_background: true`), **a unique outfile per angle** (the L1 rule-3 scheme +
   an angle slug, so same-spec / same-worktree lanes never clobber). Each job is **review-only**:
   it emits findings + a per-angle verdict and does **not** edit the spec. Focus text per lane =
   the one failure-class + code location + standard framing (verify against actual code; no
   codegraph; flag over-engineering; no backticks/`$`). Cap at **5 concurrent lanes**; on a
   companion rate-limit (`at capacity` / the L1 environment-seam shapes) back that lane off and serialize the
   overflow — never spin.
2. **Poll every lane** for `REVIEW-COMPLETE` (invariant 4 — never read on the early launch-notify).
3. **Route SERIALLY into the one spec** as lanes return: run each finding through the
   **FOLD / DISCUSS / DROP router (SKILL.md invariant 6)** — Q0 verify against the cited code
   (Codex is a lead-generator, and most findings are hardening pressure rather than bugs), then
   Q1-new / Q2-settled; unsure → DISCUSS. FOLD applies minimally to the spec; DISCUSS goes to
   `## Open Questions` **and** the round report with a recommendation (never blocks the round);
   DROP needs its one-line cite. Two lanes touching the same region → fold the second against the
   first's edits (serial fold makes that safe). Routing is seconds; the parallel wait is what
   mattered.
   **This path drives the companion directly, so it owns the list-carry L1 would otherwise do:**
   maintain FIXED / PARKED / **REFUTED** across rounds and feed all three into every lane's focus
   text next round. Drop REFUTED and each lane re-raises the same false positive every round.
4. **Re-launch only the still-open angles** next round. An angle that returns `SPEC-SOUND` is
   **cleared** — drop it from the batch. **Append-on-discovery:** a finding revealing a new
   failure-class → fold into the nearest of the 5 clusters (widen its focus); fits none → list it
   `UNPROBED` (never silently add a 6th, never silently run it).

**Critical path = the deepest single angle's round count, not the serial sum** — that is the whole
win. **Per-angle cap = 7 rounds.** Angles still open at 7 are **collected, not stopped mid-batch**:
raise them together at the checkpoint / OQ gate (§3, §Budget) with the same diagnostic — NEW
failure-classes (legit progress, owner may grant more) vs re-raises/churn (a stall — fix the
process). Do NOT STOP-and-ASK per angle as each caps; that re-serializes the loop into a chain of
human gates.

*(Transport: in a single session the main model fires the N background jobs and folds. Under
`/igr:wf:spawn` / a pane ladder each lane can instead be its own pane — same round-parallel
structure. The serial `/igr:codex-adversarial-loop SPEC_PATH 7 --focus "<angle>"` stays the
single-angle tool for the FOCUSED route and the fallback when concurrency is unavailable; `7` is
its per-angle `max`.)*

### 3. Owner resolves Open Questions (STOP — before the rewrite)

Once angles are largely cleared, **STOP and present every parked Open Question to the owner**.
Fold each answer into the spec as a settled decision (a substantive fold → re-run the affected
angle once). **The method does not end with OQs in the spec** — parking is a mid-run state, not
an output. Only when the OQ section is empty proceed to the rewrite (so the rewrite bakes the
decisions in, and the fresh read covers them too).

**Scope / boundary is a must-settle OQ class.** The census probes correctness of what the spec
*says*, not how the change is *packaged* — so a scope boundary can slip through SPEC-SOUND
unsettled and then detonate in `/igr:plan`. Before the rewrite, the spec must have **no open
"which change owns capability/config X" or "where is the seam to the next change" question**; if
one is open, park it as an OQ and settle it here, then state the boundary explicitly in the spec
(it maps directly to the Mental Model changeset — an ambiguous deliverable owner IS the OQ). *(A
real run lost a whole plan: a config landed SPEC-SOUND without settling which PR owned it; the
plan built on the wrong split and was discarded + redone — ~2–3h.)* **This is scope only** —
brainstorm does NOT decide PR order / sequencing (that is igr-workflow's; a freeze-before-plan
gate lives there). It only refuses to ship a spec carrying a hidden scope assumption.

### 4. Clean-rewrite pass (LOAD-BEARING — not cosmetic)

Rewrite the spec into a **clean, one-pass, authoritative doc**: strip ALL round-by-round churn,
version-tracing, patch-history, the revision log, round tags, and the (now empty) Open Questions
section; **KEEP** every decision, its reasoning, and every rejected alternative, and **KEEP the
`## Mental Model` contract section verbatim** — it is the immutable as-designed contract, not
run-churn; never rewrite, reword, or drop it. This step is
load-bearing because the rewrite forces a fresh read that exposes bugs the annotated doc hid —
several real bugs surfaced ONLY here.

### 5. Re-census + per-angle on the clean doc

New angles appear post-rewrite (the doc reads differently). Re-run the census on the clean doc
**once**, **re-cluster to ≤ 5** (same cap + ranking as §1), and loop **only genuinely new** angles
(round-parallel, §2). **Do NOT re-loop already-cleared angles to re-confirm them** — that is the
confirm-pass churn (measured on real runs: reverify×2 / confirm×3 rounds that surfaced no new
defect). A cleared angle re-opens only if this single re-census surfaces a *specific* new finding
against it. The re-census itself is **kept** — it catches regressions the rewrite introduced — only
the per-angle re-confirmation is cut. A new finding that parks an OQ → resolve it with the owner
(step 3 rules) before the exit gate.

### 6. Exit gate (the STRONG stop — ALL must hold)

The spec is DONE only when **every one** of these holds — a checklist, not a vibe:

1. **Every census angle cleared** (`SPEC-SOUND`) — including the post-rewrite re-census angles.
2. **Completeness critic** returned `COVERAGE-COMPLETE` (below).
3. **Zero Open Questions** — resolved by the owner (steps 3/5) and folded; the section is gone.
4. **No record of the runs** — clean-rewrite done; deterministic self-check, run it:
   `grep -nE 'Open Questions|AWAITING HUMAN|rounds-spent|Revision log|\[R[0-9]+' SPEC_PATH`
   → **zero hits**, or the gate FAILS (go back to the step that leaks).
5. **Scope boundary settled** (§3) — no open "which change owns X / where is the seam" question;
   the spec states its in-scope / out-of-scope boundary explicitly. (Prevents a plan built on an
   unsettled split being discarded downstream.)

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

**Cleared means cleared** — once an angle returns `SPEC-SOUND`, do not re-loop it to re-confirm;
the completeness critic (one call) is the only post-clearance check. A re-confirmation pass over
already-clean angles is the confirm-pass churn §5 cuts, not convergence.

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
  cleared / remaining / added-on-discovery, FOLD / DISCUSS / DROP counts, rounds spent — and ASK the
  owner: continue / narrow / stop. A checkpoint is a **human gate, not a kill**: append-on-discovery
  grows the backlog legitimately; this is where the owner sees why.
- **Hard backstop ~30 rounds total** — stop regardless, dump the state + the remaining backlog.
  The safety net for unattended runs.

**The counter lives in a SIDECAR, not the conversation and not the final spec:** keep
`rounds-spent: N` + the FOLD/DISCUSS/DROP ledger (every DROP with its cite — this is the audit
trail for what was thrown away) + checkpoint scoreboards + the step-7 Drift-B report in
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
- **data reality / stored state** — every claim about *what data exists* or *which states are
  reachable* ("no bindings of this shape exist", "that field is always set", "nothing is mid-flight
  during a deploy") is verified by **querying the stored state**, never by reasoning about the code
  that writes it. Reasoning tells you what the code *can* produce; the store tells you what it
  *did* — including rows written by versions of the code that no longer exist. This class carries
  outsized blast radius: it is exactly the assumption that fails silently for existing records.
  *(Real run: static reasoning concluded a vendor could have no bindings; a prod query found 15,002
  live ones. Unqueried, the change would have returned 403 for every resumed run of that vendor.)*
- **primitive / reinvention** — does the spec hand-roll something the repo or the stdlib already
  provides? Name the existing function if so. The tell is a **growing list of hand-written rules**:
  a helper that is a sequence of string operations, gaining one more rule per reviewer-supplied
  input, is a parser waiting to be used. Decide the primitive HERE — nothing downstream re-opens
  it, so a hand-rolled helper that reaches the plan just gets hardened instead of questioned.

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
