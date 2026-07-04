# igr-dev: plan method (spec → plan)

A plan's failure surface is **closed and uniform**, so review runs a **FIXED angle checklist** — no
per-doc angle discovery, no clean-rewrite (those are spec-only). But a plan's #1 real failure mode is
**asserting wrong facts about the code** (stale signatures, missed couplings, dropped branches). A
naive single broad loop burns 15–20 rounds *falsifying facts a census would have prevented*. So this
method **grounds the plan in a code census first**, then splits review into cheap **mechanical
diffs** (checked against the census / LSP, no model needed) + a few **judgment angles** run
adversarially with an external model. Target: ≤ ~7 codex rounds, provably ≥ the old broad loop
(which survives as the final pass).

> **census here = code ground-truth (facts the plan depends on)** — NOT the spec method's
> exploratory *angle*-census. Plan angles stay a fixed list; only the facts are discovered.

Never git-commit the plan or census (the owner commits docs). Prefer the **LSP tool**
(`goToDefinition`/`findReferences`/`workspaceSymbol`/`hover`) over grep for all symbol work; grep is
fallback / non-code text only. Language-neutral: same flow for Go or Rust, point the LSP at the repo.

---

## P0 — SCOPE (inline, main session)

From the spec, decide: **entry symbols** (the surface the change touches), the **boundary** it
decouples from (e.g. a god-struct receiver `&Store` / `*Store`, a package, a module), and the
**coverage checklist** (spec requirements). Small output, highest-leverage judgment → keep inline on
the main model; it carries into P2. Only if the spec is large (bloats context) offload the bulk
*read* to one `Explore` subagent, then **ratify** its returned scope inline before P1. Never put a
cheap model on this decision — a mis-scope propagates into census + plan.

## P1 — CENSUS (subagent, ground truth)

Extract every fact the plan will depend on, from code **at the plan's HEAD**, into a structured
table. **Default: one `general-purpose` subagent + schema, model `sonnet`** (mechanical + verifiable
→ Opus wasteful, Haiku too weak for boundary-crossing judgment), run synchronously. Escalate to a
`Workflow` (scope-sweep → parallel facts by dependency-closure → merge → verify) **only** if the
surface exceeds one context — and slice by dependency-closure, **never per-file** (couplings cross
files: a call site and its callee's real signature live apart; a per-file agent structurally cannot
resolve them).

The agent does a **transitive-closure walk** from the entry symbols and returns the table + a
self-audit. Hand it the discipline, not just the goal:

- start = entry symbols (locate by name with LSP `workspaceSymbol` — pass any repo file as the
  `filePath` anchor); for each, LSP `findReferences`/`goToDefinition`/`hover` + read the whole body;
  add every boundary-crossing edge to the frontier; repeat until no new external symbol. The
  **file list is an output**, not a guess. Gotcha: `line`/`character` are 1-based, `character` must
  land on the identifier; the first LSP call right after server start may return empty mid-index —
  **retry once** before trusting a zero result.
- run the **exhaustive** boundary grep as a coverage floor — multiline-aware and follow-into-helpers,
  e.g. `rg -n -U 'boundary\s*[:.]'` — and **reconcile: table row-count vs grep hit-count** (no silent
  drops). This is what prevents blind spots (line-threshold / `&cfg`-via-helper / multiline / hidden
  branch misses).

**CENSUS row schema (language-neutral):**

```
symbol            fully-qualified name
kind              fn | method | type | const | impl | test
anchor            file:line @ HEAD   (re-resolve at implement; never trust)
signature         params + receiver + return/error type (exact, from LSP)
visibility        public | package | private (+ reachable-from)
effects/branches  side-effects, early-returns, fallbacks   (behavior-sensitive flag)
edges_out         boundary-crossing calls/reads
edges_in          callers that depend on it
tests             existing tests covering it
disposition       stays | moves | seam | rename            (filled by the plan)
```

Output to a sibling file (e.g. `CENSUS.md` next to the plan). A verify pass (2nd cheap agent OR the
P3 coverage check) re-runs the boundary grep and asserts every hit has a row.

## P2 — PLAN (superpowers:writing-plans, inline)

Invoke **`superpowers:writing-plans`** inline (the plan is the deliverable; judgment-heavy; carries
into P3). It already gives task decomposition, no-placeholders, and a **Self-Review**. Two deltas
only — because `writing-plans` doesn't know about the census:

1. **Feed the census as input; write from it.** **Cite census rows** (single source of truth — no
   plan↔census drift). Pin only **decisions / irreversible / seams / object-safety-critical**
   signatures; for the mechanical tail write *"re-resolve symbol at HEAD, match its signature"* and
   cite the census row. **A census-citation is NOT a placeholder** — it points at ground truth.
   Over-pinning exact sigs/lines is the root cause of long review loops.
2. **Whole-body for behavior-sensitive symbols.** For every symbol the census flagged
   `effects/branches`, enumerate each branch/fallback/ordering/side-effect as a preservation
   requirement + name a test. (This is the class of the subtlest bugs — dropped fallbacks, error-path
   state, ordering.)
3. **Exit gate = extend the Self-Review with census-coverage:** every census row has a
   task/disposition. Cheap inline check; kills easy gaps before spending any codex round.

## P3 — REVIEW (mechanical pre-pass → codex angle-till-solid → codex full-till-solid)

### (a) Mechanical pre-pass — no codex, deterministic, inline

Main holds census + plan, so run these as inline diffs (LSP + grep + set-compare); no model
reasoning:

- **completeness** — census rows **minus** plan tasks/dispositions → any missing = a gap.
- **signature-match** — for each signature the plan pins, LSP-lookup the real one, compare.
- **coverage** — re-run the boundary grep; every hit has a census row (and a plan task).

Fold these findings first. They are the bulk of what a broad loop wastes rounds on — killed here for
free.

### (b) Codex judgment angles — serial, each looped **till SOLID**

Only the angles that need a thinking model, in dependency order (a fold in one can shift the next):

1. **contracts / errors / fallibility** — `Result` vs infallible, `?` preserved, swallow-vs-propagate
   correctness.
2. **behavior / branches** — every branch/fallback/ordering of each inverted fn preserved; error-path
   state; the highest-value angle.
3. **green-ordering / rollback** — each task leaves the tree buildable; strangler/bridge soundness.

For each: `/igr:codex-adversarial-loop PLAN_PATH --focus "<one angle, exhaustive-in-lens>"`, loop
that angle until a pass returns **zero new findings** (SOLID; remaining = parked). Different model
from the plan's author (codex) is the point — external adversary. Feed each pass the census + FIXED +
PARKED; fold minimal inline (main), park scope/breaking (invariants 5–6). Focus-string rules: **no
backticks, no `$`, no codegraph** (it hangs — rg/sed only); tell it to **enumerate EVERY instance in
the lens, not the top one**, and verify each against code (LSP/rg). Template:

> Review the plan at PLAN_PATH against its spec SPEC_PATH and census CENSUS_PATH, ANGLE ONLY:
> \<angle description\>. Enumerate EVERY instance in this angle, not just the most salient. Verify
> each against the actual code. Here are the already-FIXED items and the PARKED open questions — do
> not re-raise those or other angles. Flag over-engineering as a defect. Do NOT run codegraph; use rg
> and sed only. Say ANGLE-SOLID if the angle is clean.

### (c) Codex full-plan pass — broad, looped **till SOLID**

After all angles are SOLID, run the **broad** loop over the whole plan (this is the old method —
`/igr:codex-adversarial-loop PLAN_PATH` with the full fixed checklist). It is the **convergence
net**: per-angle folds interact (an angle-B fix can reopen A), and a bug fitting no single lens
surfaces here. This pass being present is why the method is **provably ≥ the old broad loop** — worst
case equals it. If it finds anything: fold → re-run the FULL pass till clean (don't re-cycle angles —
full is the closer).

## Stop condition & budget

Stop when the **full-plan pass returns `PLAN-SOUND`** (zero new; a full clean pass is the signal).
Backstop: a total codex-round budget (~12) — the mechanical pre-pass + census pre-strip the bulk, so
convergence should land in **~5–8 rounds**; if the budget hits before full-solid, stop and report the
open findings (the max-cap rule). Per-angle passes needn't be perfect — the final full pass mops
residual.

---

**Recap of the flow:** `P0 scope (inline) → P1 census (sonnet subagent) → P2 writing-plans (inline,
+census) → P3a mechanical pre-pass (inline diffs) → P3b codex per-angle-till-solid → P3c codex
full-till-solid`. The census makes the mechanical pre-pass possible (needs plan↔census in comparable
form) and pre-grounds the facts the judgment angles would otherwise trip on.
