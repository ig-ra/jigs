# igr-dev: plan method (spec → plan)

A plan's failure surface is **closed and uniform**, so review runs a **FIXED angle checklist** — no
per-doc angle discovery, no clean-rewrite (those are spec-only). But a plan's #1 real failure mode is
**asserting wrong facts about the code** (stale signatures, missed couplings, dropped branches). A
naive single broad loop burns 15–20 rounds *falsifying facts a census would have prevented*. So this
method **grounds the plan in a code census first**, then splits review into cheap **mechanical
diffs** (checked against the census / LSP, no model needed) + a few **judgment angles** run
adversarially with an external model. Target: ≤ ~7 codex rounds, provably ≥ the old broad loop
(which survives as the final pass).

**Preflight:** needs the `superpowers` and `codex` plugins — verify per SKILL.md §Preflight; if absent, STOP with the `/plugin install` line.

> **census here = code ground-truth (facts the plan depends on)** — NOT the spec method's
> exploratory *angle*-census. Plan angles stay a fixed list; only the facts are discovered.

Never git-commit the plan or census (the owner commits docs). Prefer the **LSP tool**
(`goToDefinition`/`findReferences`/`workspaceSymbol`/`hover`) over grep for all symbol work; grep is
fallback / non-code text only. Language-neutral: same flow for Go or Rust, point the LSP at the repo.

---

## P0 — SCOPE (inline, main session)

**Spec intake gate — run FIRST.** A plan must derive from a **brainstorm-clean** spec. Check for
hardening residue:
`grep -nE 'Open Questions|AWAITING HUMAN|rounds-spent|Revision log|\[R[0-9]+' SPEC_PATH`
Any hit → the spec left brainstorm unfinished (unresolved OQs, no clean-rewrite/re-census):
**WARN the owner and recommend `/igr:brainstorm SPEC_PATH` to finish it** (resolve OQs →
clean-rewrite → re-census → exit gate). **Proceed only on the owner's explicit OK**, and record
that OK in the plan's `## Review status`. Zero hits → proceed.

From the spec, decide: **entry symbols** (the surface the change touches), the **boundary** it
decouples from (e.g. a god-struct receiver `&Store` / `*Store`, a package, a module), and the
**coverage checklist** (spec requirements). Small output, highest-leverage judgment → keep inline on
the main model; it carries into P2. Only if the spec is large (bloats context) offload the bulk
*read* to one `Explore` subagent, then **ratify** its returned scope inline before P1. Never put a
cheap model on this decision — a mis-scope propagates into census + plan.

**P0 writes its scope to the census file.** The judgment stays inline (never a cheap model); only the
*write* is mechanical. Create the scratch **`<prefix>-census.md`** (naming below) and write a `## Scope`
section — entry symbols / boundary / coverage checklist. This is the P1 subagent's **input** (it reads
`## Scope` rather than you re-transcribing it into the prompt) and it survives context compaction.

**Mechanize the enumeration — `census scaffold`, then prune** (kills run-to-run variance in *which candidate
symbols exist*, which is not a judgment). For a decoupling task:
1. From the spec, decide the **boundary god-struct(s)** + **target file(s)** — judgment; precedes scaffold.
2. Build the SCIP index once: `rust-analyzer scip <repo> --output /tmp/<prefix>-index.scip` — **reused by P1**.
3. `<tool>/census scaffold --index <idx> --repo <repo> --file <target> [--file …] --boundary-struct <X> [--boundary-struct <Y>] --out <prefix>-census.md` → writes the `## Scope` template with a **deterministic candidate-entry list** (pub/pub(crate) fns in the targets + boundary-touch counts) + a **boundary preview**. (`<tool>` — here and everywhere below — = the igr plugin's census CLI dir: `${CLAUDE_PLUGIN_ROOT}/tools/census-harvest`; if that variable is unset/unsubstituted, resolve it: `ls -d ~/.claude/plugins/cache/*/igr/*/tools/census-harvest | sort -V | tail -1`.)
4. Judgment on top: **prune candidates to the real entry frontier**, write the **coverage checklist**, flag behavior-sensitive symbols + explicit exclusions.

Enumeration is now identical across runs; only the prune + checklist (the actual scope decision) is judgment — where it belongs. (Non-decoupling task, no god-struct → skip scaffold, enumerate inline.)

**Cite symbols by NAME, not hand-grepped anchors.** A raw `rg <name>` returns BOTH the prod symbol and its `#[cfg(test)]` twin (parallel prod/test versions are common — e.g. a `Materialized*` test path beside the prod `Prepared*` path), and you will cite the wrong (test) line. **Exact anchors are P1's job** — the harvest is `#[cfg(test)]`-aware and resolves every anchor deterministically. If P0 needs an anchor for orientation, take it from the **scaffold** output (test-excluded), never a raw name-grep. (Observed: a P0 cited `#[cfg(test)]`-twin anchors for the move-with-file helpers; P1 had to correct them.)

**Roster the TO-side seam, not just the FROM-side boundary.** A decoupling task has *two* surfaces: the boundary it severs **from** (the god-struct — scaffolded above) and the seam it routes **through** (the already-landed ports/traits + a few cross-file helpers the new code calls). The harvest covers the FROM-side. The TO-side is **P2's to pin** (often as a full trait code-block, which a one-line sig-row can't substitute for) — so hand P2 a **resolve-list, not a discovery task**: in the Scope's `### Boundary`, list the TO-side seam **by path** (from the spec's seam section — e.g. `src/store/{segment_catalog,tier_sink,snapshot_publisher}.rs`, plus cross-file helpers like `with_current_s3_purpose` / `StorageOwnership`). **Do NOT harvest the TO-side into census rows** — a sig-row can't stand in for the trait body P2 pins, and a TO-side row has no `disposition` (you don't modify it), so it would false-flag the P2 coverage gate. Just list the paths; P2 reads them. (Observed r3a-plan-5: P2 spent its only 3 discovery calls re-finding these — a listed roster removes the *find*, keeps the read.)

## P1 — CENSUS (subagent, ground truth)

Extract every fact the plan will depend on, from code **at the plan's HEAD**, into a structured
table. **Default: the `igr:code-census` agent, model `sonnet`** (Opus wasteful; Haiku too weak — it
satisfices judgment, ~13 rows vs ~330). The agent has **two paths (full detail in its def):**
- **PRIMARY — SCIP harvest.** `rust-analyzer scip <repo>` → the `census-harvest` tool
  (`<tool>` — defined in P0 step 3) emits the mechanical skeleton — every symbol + exact signature +
  edges_in/edges_out + a deterministic **boundary-coupling coverage floor** (more precise than a
  `store.`/`stream.` grep: resolved, no false positives) — in **~seconds**. The agent then does **only
  judgment**: scope + behavior-sensitivity (whole-body read) + disposition. No per-symbol LSP, no
  positioning landmines, no flaky-LSP dependence, no ~25-min runtime. Language-neutral: swap the indexer
  (`scip-go` for Go).
- **FALLBACK — live LSP** (only if no indexer): LSP-first (`documentSymbol` map → `hover` → scoped
  `findReferences` → one batched grep), **run SYNCHRONOUSLY** — a background subagent gets no LSP, so the
  guard aborts `DEGRADED`. The positioning-landmine / tool-split / cost-model discipline lives in the def. Escalate to a
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

**Artifact naming + write responsibilities.** The census file shares a **common prefix with the spec
and plan** so the three read as one set: spec `<prefix>.md` (or `r<N>-<name>.md`), plan
`<prefix>-plan.md`, census `<prefix>-census.md` (e.g. spec `r3-needle-compaction.md` → plan
`r3a-needle-compaction-plan.md` → census `r3a-needle-compaction-census.md`). Who writes what:
- **P0** → writes `## Scope` to `<prefix>-census.md`.
- **P1** (subagent) → reads `## Scope`, **appends** `## Census table` + `## Reconciliation` to the same
  file; writes raw `documentSymbol`/grep dumps to a sibling `<prefix>-census-evidence.md`. Any **TO-side
  seam def-locations** it hits during the walk (ports/helpers outside the harvested files) it adds to the
  Scope's roster (path + one-line) — resolve them once at ground-truth time, not per-P2.
- **P3a** → consumes `<prefix>-census-evidence.md` for the deterministic set-compare, then it is
  **discarded**.
- **P2** → folds `## Census table` into the plan as `## Appendix: Code Census`.

**The curated census lives IN the plan** as that `## Appendix: Code Census` — **one self-contained
artifact**: citations resolve within the doc, it rides to implement alongside the tasks, and on disk it
survives context compaction (the exact-fact payload the method exists to protect). **Only the curated
table + reconciliation fold in — never the raw evidence dumps** (stale anchors + noise; the table's
columns already carry the curated subset). Append, don't prepend — keep the plan readable top-down
(goal → tasks → census). A verify pass re-runs the boundary grep and asserts every hit has a row.

## P2 — PLAN (superpowers:writing-plans, inline)

Invoke **`superpowers:writing-plans`** inline (the plan is the deliverable; judgment-heavy; carries
into P3). It already gives task decomposition, no-placeholders, and a **Self-Review**. Two deltas
only — because `writing-plans` doesn't know about the census:

1. **Feed the census as input; write from it.** **Cite census rows by symbol** (they live in the
   plan's `## Appendix: Code Census` — single source of truth, one doc, no drift). Pin only
   **decisions / irreversible / seams / object-safety-critical**
   signatures; for the mechanical tail write *"re-resolve symbol at HEAD, match its signature"* and
   cite the census row. **A census-citation is NOT a placeholder** — it points at ground truth.
   Over-pinning exact sigs/lines is the root cause of long review loops. For the **TO-side seam** (the
   landed ports/helpers the new code routes through), read the files the Scope's roster already lists and
   pin their exact shapes — they are the object-safety-critical signatures worth pinning precisely.
2. **Whole-body for behavior-sensitive symbols.** For every symbol the census flagged
   `effects/branches`, enumerate each branch/fallback/ordering/side-effect as a preservation
   requirement + name a test. (This is the class of the subtlest bugs — dropped fallbacks, error-path
   state, ordering.)

**Plan altitude — pin decisions, not the code.** Delta 2 does NOT mean transcribe every branch into
the plan (unbounded, staleness-prone, the implementer's job). State only what reading the body at HEAD
can't give you: **decisions** (port/seam/return-shape), **invariants** (byte-identical, single-tenant),
**side-effect owners** (which struct owns the effect — Store vs StreamState vs a cache), and a
**preserve-verbatim contract** for the rest (*"preserve every branch/ordering/side-effect/swallow
verbatim, test-backed"* + name the test). A wrong owner is a real defect; a missing branch-transcription
of a test-covered fn is not.

**Task order — buildable at every commit (aim; P3a enforces).** Order tasks so each commit builds and
its named tests pass using **only what earlier commits produced**. *Definitions before uses* — a task
referencing a symbol/type/field/API not yet introduced by an earlier task is a forward-reference = a
broken commit; introduce (and gate the build of) a shared abstraction before any task depends on it;
put a test before the code it guards. *Strangler site-inventory* — before renaming/re-typing/moving a
**shared** symbol, find **all** its callers (in and out of the change surface) and keep the old path
alive for out-of-surface callers so every commit stays green; a change is "additive" only if no
un-updated caller remains. `writing-plans` can **aim** for this but cannot **verify** it (no
build/dep-graph) — it catches plan-visible forward-refs; the code-aware guarantee (visibility, existing
callers) is the P3a green-ordering check.
3. **Exit gate = extend the Self-Review with census-coverage AND buildable order:** every census row
   has a task/disposition, **and** the task order is buildable-at-every-commit (definitions before
   uses; test-before-code; no plan-visible forward-reference). Cheap inline check; kills easy gaps
   before spending any codex round.

## P3 — REVIEW (mechanical pre-pass → codex angle-till-solid → codex full-till-solid)

### (a) Mechanical pre-pass — no codex, deterministic, inline

Main holds census + plan, so run these as inline diffs (LSP + grep + set-compare); no model
reasoning:

- **completeness** — census rows **minus** plan tasks/dispositions → any missing = a gap.
- **signature-match / return-type / fallibility** — for **every factual signature claim anywhere in
  the plan**, LSP-lookup the real one and compare. **Scan the WHOLE plan text, not just the pinned
  `## Interfaces` block:** task-body prose ("returns `SegmentWriteOutput`", "each entry returns
  `CompactionRun<T>`", "the wrapper records timings and returns `output`") states return types +
  fallibility too, and those are the instances that slip through. In particular sweep **every stated
  return type vs the real sig** — `Result` vs infallible, invented-`Result`-on-a-swallowed-error,
  dropped-`Result`, omitted swallow-to-`Ok(None)`. This is the highest-yield mechanical check: a real
  run leaked **5 fallibility defects into codex** because the pre-pass scoped itself to the pinned
  block and skipped the prose — every one would have died here for free.
- **coverage** — re-run the boundary grep; every hit has a census row (and a plan task).

**Scope principle: these checks diff EVERY factual claim in the plan (pins + prose) vs ground truth**
— return types, signatures, anchors, field counts — not only the claims that happen to sit in a
pinned block. A claim in a task body is as load-bearing as one in `## Interfaces`.

**Run the structured half mechanically — `census verify-plan`.** The tool parses the plan's
code-fenced sigs + `[C:name]` citations and diffs them against the SCIP index (all symbols, incl.
TO-side seam files not in the skeleton), emitting a divergence report — deterministic, seconds, ~0
model tokens:
`<tool>/census verify-plan --plan <prefix>-plan.md --skeleton <prefix>-census-skeleton.json --index /tmp/<prefix>-index.scip`
It reports: **dangling/uncensused citations**, **FALLIBILITY mismatches** (`Result` invented/dropped —
the highest-signal class, the one that leaked to codex), **return-type diffs** (candidates — a port
returning `dyn`/re-keyed type may be intended, verify), **arg-count mismatches**, and **ambiguous
pins** (name resolves to several defs — verify by hand). You then only **fix** the flagged lines — no
hand-sweep of the plan. What it can't cover (prose "returns X", behavior/branch semantics) stays for
the model + P3b. (Structured claims → deterministic; prose + semantics → model.)

Fold these findings first. They are the bulk of what a broad loop wastes rounds on — killed here for
free.

### (b) Codex judgment angles — serial, each looped **till SOLID (cap 3, then ASK)**

The angle set is **FIXED — exactly these three** (plan review is a closed checklist, not spec-style
angle-discovery), in dependency order (a fold in one can shift the next):

1. **contracts / errors / fallibility** — `Result` vs infallible, `?` preserved, swallow-vs-propagate
   correctness. (The *mechanical* half — `Result` types, sigs, cites — is now front-stripped by
   `census verify-plan` in P3a; the codex residual here is the *semantic* swallow-vs-propagate intent.)
2. **behavior / branches** — every branch/fallback/ordering/side-effect of each inverted fn preserved;
   error-path state; **evaluation semantics** (probe below); the highest-value angle (largest semantic
   surface → the likeliest to reach the cap).
3. **green-ordering / rollback** — each task leaves the tree buildable; strangler/bridge soundness.

**Evaluation-semantics probe (behavior angle).** Preserve not just a dependency's **type** but **when
it is obtained, how often, and from which source.** Routing a dependency through an indirection
(port/interface/callback) silently changes behavior when it flips *once-and-reused ↔ re-obtained-per-call*
or *a captured/scoped source ↔ a re-resolved/global one* — and the value is mutable, swappable,
time-varying, or scoped (e.g. a config obtained per-call vs prebuilt once; a resource re-resolved per
call vs captured once; a scoped source read as a global one). Pin the evaluation semantics, not only
the signature. This class is **cross-cutting** — it slips past a narrow read of any single lens (it
repeatedly surfaced only in the broad pass), so probe it explicitly here.

For each: `/igr:codex-adversarial-loop PLAN_PATH 3 --focus "<one angle, exhaustive-in-lens>"`, loop
that angle until a pass returns **zero new findings** (ANGLE-SOLID; remaining = parked) **OR a hard
cap of 3 rounds** — whichever first. **The cap travels as L1's `max` arg** (`3` — matches L1's
single-focus default; pass it anyway, intent explicit). When L1 returns capped, **YOU** run the
STOP-and-ASK triage below — L1 only reports; the caller owns the ASK. Different model from the plan's author (codex) is the point —
external adversary. Feed each pass the census + FIXED + PARKED; fold minimal inline (main), park
scope/breaking (invariants 5–6). Focus-string rules: **no backticks, no `$`, no codegraph** (it
hangs — rg/sed only); tell it to **enumerate EVERY instance in the lens, not the top one**, and verify
each against code (LSP/rg).

**Class-generalization (every codex round — angles AND the broad pass).** A codex finding is an
*instance*, not the bug — do **not** fix just it and re-run. Name its defect **class**, then enumerate
the class's **full surface mechanically** (`rg` every method of the trait / every ref of the symbol /
every site of the pattern) — **not from recall** — fold every instance, then re-run to *confirm the
class is dead*. Codex surfaces ~one instance per round and author-recall of the surface is incomplete:
**partial generalization costs repeat rounds** (a class parked over 4 of its 8 methods resurfaced in
the broad pass; behavior classes recurred the same way). The split: the class **surface is a fact —
list it by tool**; which instances are defects is **judgment — decide each**.

**For a recurring or cross-cutting class** (one that resurfaces across rounds despite folding), a
fold-the-defects list is not enough — it has no proof you got them all. Produce an **exhaustive
candidate × verdict table**: **every** candidate in the surface gets a row with a verdict — *in-class →
fixed* OR *safe → why*. The table **is the completeness proof**: a missing member shows up as an
unclassified candidate, and the **safe-with-reason rows** are what actually close "did I miss one?".
(A captured-resource class dribbled one member per round for many rounds until a per-candidate table
enumerated the whole surface — then a single confirm pass returned clean.)

This is what keeps rounds within the cap.

**The 3-round cap is a uniform diagnostic tripwire, not a work budget.** With front-loading (census +
P3a verify-plan) an angle should converge in **~1–2** rounds. **If an angle is not SOLID at 3 rounds,
STOP and ASK the owner** — never silently grind on, never silently kill. Report which
case it is: the remaining findings are **NEW defect classes** (legit progress — the owner may grant
another batch) or **re-raises / churn** (a stall — fix the *process*, e.g. a class the pre-pass should
have caught, don't spend rounds). Hitting the cap is a **checkpoint, not a failure**. Uniform across
all three angles — do not pre-tune per-angle caps by guessed difficulty; let the actual rounds-used
reveal it, and only raise a specific angle's cap if data shows it reliably needs more *legit-progress*
rounds (angle 2 is the likeliest candidate).

**SOLID is qualitative, not zero-findings.** On a large surface a lens can always surface one more
low-risk nit — chasing zero is unbounded. An angle is SOLID when a round's findings **degrade from
real defects to doc-completeness of already-test-covered code** (the value-decay is the signal). Apply
the P2 **plan-altitude** rule at review: "reproduce branch X of a test-covered fn in the plan" is not a
plan defect once the preserve-verbatim contract + a guarding test exist.

**Pending refinement (NOT yet active — flat cap-3 is the current rule).** The flat count is a
placeholder for a **stall-based** cap: *loop while each round finds a NEW defect class; trip only on a
round that surfaces no new class (or a hard ceiling ~5).* That's strictly better — it lets a
legitimately-large angle keep making class-by-class progress while still killing churn. It depends on
the **class-generalization discipline** (on each finding, generalize to its class and self-sweep the
whole plan before re-running — so "no new class this round" is a real convergence signal). Both are
being validated on the current run's angles before folding; adopt the pair together once the data
holds. Until then: flat cap-3 + ASK.

**Per-angle focus template:**

> Review the plan at PLAN_PATH against its spec SPEC_PATH and census CENSUS_PATH, ANGLE ONLY:
> \<angle description\>. Enumerate EVERY instance in this angle, not just the most salient. Verify
> each against the actual code. Here are the already-FIXED items and the PARKED open questions — do
> not re-raise those or other angles. Flag over-engineering as a defect. Do NOT run codegraph; use rg
> and sed only. Say ANGLE-SOLID if the angle is clean.

### (c) Codex full-plan pass — broad, looped **till SOLID**

After all angles are SOLID, run the **broad** loop over the whole plan (this is the old method —
`/igr:codex-adversarial-loop PLAN_PATH <remaining>` with the full fixed checklist, where
`<remaining>` = **10 − rounds spent in P3b**; if that is < 3, STOP and ASK before starting —
don't launch the closer with no budget). It is the **convergence
net**: per-angle folds interact (an angle-B fix can reopen A), and a bug fitting no single lens
surfaces here. This pass being present is why the method is **provably ≥ the old broad loop** — worst
case equals it. If it finds anything: fold → re-run the FULL pass till clean (don't re-cycle angles —
full is the closer).

## Stop condition & budget

Stop when the **full-plan pass returns `PLAN-SOUND`** (zero new; a full clean pass is the signal).
Two nested budgets:
- **Per-angle cap = 3 rounds, then STOP and ASK** (the uniform tripwire, §(b)) — not a silent grind, not
  a silent kill. This is the primary control; it catches a runaway angle at the source.
- **Global stage budget = 10 total codex rounds** (P3b + P3c combined; this stage's own budget —
  separate from the brainstorm method's) — the mechanical pre-pass + census + `verify-plan` pre-strip
  the bulk, so convergence should land in **~5–8 total**. P3c's `max` = the remainder (10 − P3b rounds
  spent); a remainder < 3 → STOP and ASK before P3c. If the budget hits before full-solid, stop and
  report the open findings.

Per-angle passes needn't be perfect — the final full pass mops residual.

## Review status block (write on convergence)

When the method finishes (P3c `PLAN-SOUND`, or it stops at the cap), append a **`## Review status`**
block to the plan — the audit signal that otherwise stays trapped in ephemeral review panes/outfiles.
It is **method-audit, not implementation** — place it at the end, clearly labeled. Contents:
- **Convergence verdict (headline):** `PLAN-SOUND (clean)` vs `CAPPED (N rounds, M open findings)` — the
  one-line "is this trustworthy / done". (A comparison or a fresh reviewer needs exactly this and cannot
  infer it from the tasks.)
- **Parked Open Questions:** count + severities + "owner resolves before/with implement" + a pointer.
- **Per-phase table:** P1 census (rows) · P3a (verify-plan clean) · P3b each angle (rounds → ANGLE-/
  qualitative-SOLID) · P3c (rounds → verdict).
- **Spec-updates:** Appendix §N pointer, if the review surfaced any.
- **Provenance ledger:** one line per fold (`Rn: what`) — **this is where round-provenance lives.**
- **Stamp:** "as of HEAD `<sha>`" (snapshot; the plan may be edited after).

**Provenance lives in this block, NOT inline.** In the task bodies keep only the requirement + its
rationale (a `⚠` + the "why"); **strip the round-tags** (`(P3c-R5)`, `(P3b-angle2)`) — a reader must
never need to know "R5" to implement correctly. The tasks are for the **implementer** (clean); the
block is for the **auditor/comparison**. Never git-commit the plan (the owner commits docs).

## Spec fold-back section (findings that belong UPSTREAM, not in the plan)

The plan review often finds the **spec** is wrong / stale / incomplete — not the plan. Those do NOT
belong in the plan's tasks or Open Questions; collect them in a dedicated **`## Appendix: Possible
spec updates`** section. Two distinct deferred buckets — keep them separate:
- **Open Questions** = a *plan / design decision* the owner must make → resolved **into the plan**
  before implement.
- **Spec fold-back** = the review found the *spec itself* factually wrong/stale (e.g. the spec pins
  `&'a Arc` but the code + plan need an **owned** `Arc`) → applied **upstream to the canonical spec**.

Each fold-back entry: *what the spec says now → what it should say → why* (the finding that surfaced
it). **The plan does NOT edit the spec** — the **canonical spec may live elsewhere** (another repo /
doc) and is owner-owned. Surfacing the list is the plan's job; **applying it is a downstream ASK**
(igr-workflow offers it after the plan stage — never auto-update).

---

**Recap of the flow:** `P0 scope (inline) → P1 census (sonnet subagent) → P2 writing-plans (inline,
+census) → P3a mechanical pre-pass (inline diffs + census verify-plan) → P3b codex per-angle
(SOLID or cap-3-then-ASK) → P3c codex full-till-solid`. The census (the plan's `## Appendix: Code Census`) makes the mechanical pre-pass
possible and pre-grounds the facts the judgment angles would otherwise trip on. **One artifact:
`PLAN.md` (tasks + census appendix); scope stays in-session.**
