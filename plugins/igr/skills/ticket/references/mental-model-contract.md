# Mental Model contract

A compact changeset inventory of what a piece of work commits to build. Extracted from
`/igr:brainstorm` so it can be used on its own — for a ticket, a plan, or any change before
implementation starts. The skill still owns its own copy; this is the reusable form.

## Why it exists

It catches **the gap between intent and design**, before effort is spent. The reviewer reads the
table against what they actually intend and finds: a capability obvious to them that never reached
the spec, a removal nobody meant, a technology they would veto. Something obvious to the human is
often invisible to whoever wrote the spec — this is where that surfaces.

Far cheaper here than after the work is done.

## The shape

```
## Mental Model (as-designed — immutable)

_The design this commits to. The work must honor it; report any drift at the end._

**Ships:** <one line — what capability lands, for whom>

**Deliverables** — changeset vs current system

| tag | capability | tech / where |
|-----|------------|--------------|
| ADD | <what it does> | <tech · path> |
| CHANGE | <what changes> | <tech · path> |
| REMOVE | <what goes, why — replaced-by if any> | <tech · path> |

**Unchanged:** <existing behavior this explicitly does NOT touch>
```

## Rules that make it work

- **One row per deliverable**, fusing capability × the tech chosen for it. Tagged against the
  current system; greenfield means all ADD.
- **Only what gets supplied.** No non-goals, no risks, no rationale. Those are not what the
  reviewer scans for omissions, and they bury the thing that is.
- **`Unchanged` is the one boundary line allowed** — a wrongly-touched invariant IS an omission
  the reviewer scans for.
- **≤50 lines.** One flat scannable table. Split under sub-headers only past ~8 deliverables
  spanning separate subsystems.

## How to use it

Write it, then **stop and ask**: *does this match your intent? anything you expected that is
missing, or here that you did not intend?*

A real gap means either the spec is wrong (fix the spec) or the model misread it (fix the model).
Converge both to the agreed intent before proceeding.

Once agreed it is a **contract**. Do not silently rewrite it to match what the work became — if the
work legitimately diverges, re-derive a second model at the end and report the diff to reconcile
deliberately.

Pairs with the ticket: the ticket says gap, fix and acceptance criteria; this says what changes.
The instinct is selecting less content, not terser prose.
