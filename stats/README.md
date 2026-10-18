# stats: ticket-flow token usage

## IGR-19 coverage pilot (step 1)

```sh
python3 -B -m stats.ticket_flow 2026-10-17 2026-10-18
```

UTC, END exclusive. This implementation slice measures **IGR-15/16 only**; full three-repo collection and review/activity enrichment follow after the approved gate. It reads the existing bin/usage readers, native transcripts, estimate dispatch timestamps and available local commit author dates. GitHub reads only jigs PR 3/4 identity, creation, merge and first bot activity time. No input logs, GitHub state, bin/usage behavior or dashboard assets are changed.

Outputs: `stats/runs/2026-10-17_2026-10-18/{stages,tickets,run}.csv` are tracked; `calls.csv` in that directory is generated and ignored. The command returns nonzero for a failed numeric pilot gate, retaining the measured evidence; a collection error publishes no new set. Hand reconciliation is a one-time documented check, not implied by command exit 0 alone. Identical sources give stable CSV formatting/order; no generated wall-clock time is written. Event timestamps remain evidence.

Accepted step-1 output columns (the tracked pilot files retain this schema):

- `calls.csv`: canonical provider/call ID/timestamp and ticket basis; repo, actor, session/parent/turn; native or first-call start/basis; call source path/line; chosen marker timestamp/source/repo; stage, stage_order, review_pass, cycle; four raw token buckets; missing_reason. `repo` comes from lexical fixed-root cwd mapping; non-repo parent-directory cwd stays blank.
- `stages.csv`: ticket/stage/review_pass/cycle keys; each actor's new_input_tokens/cache_read_tokens/cache_write_tokens/output_tokens; Claude-main and Codex minutes_raw; turn_overlap_min; calls/turns; coverage. `tickets.csv` sums these measures by ticket. Repo is not an aggregate key. Actor names are claude_main, claude_subagents and codex; no reasoning-token double count.
- `run.csv`: long-form ticket/actor/metric/value/numerator/denominator/repo/pr/source records. Includes UTC window, pilot call/Claude-duration/Codex-pair/PR counts, reader diagnostics, unmatched starts, unknown/ambiguous shares, PR head-ref/created/merged/first-bot facts and marker inventory. Reader diagnostics include scanned pre-window context; per-ticket counts describe the measured population. Full GitHub head-SHA/count/churn enrichment is not collected in this slice.

Missing values stay blank, known-empty quantities zero, and a required missing component propagates through aggregates. All pilot summaries have `coverage=partial`: full enrichment is pending, standalone native-review usage is absent, and an unmatched Codex start does not supply duration. Observed raw work is still reported. No Claude-child minutes column is invented; its minute-share numerators/denominators are blank. Native-review commands are markers, not zero-token observations. Activity/family and foreground-wait columns are deferred to step 2. Same-session overlap is a diagnostic alongside raw minutes, never subtracted.

**Coverage gate passed.** 981 canonical calls conserve; all 24 actor/token buckets and completed raw durations sum through stages to tickets. Claude minutes 62.553067 / 27.024650 round to **63/27**; Codex 104.859500 / 31.890033 round to **105/32**. Unknown token share is **0%** for each ticket/observed actor; unknown raw-minute share is **0%** for each ticket/provider. IGR-16 retains one unmatched start, IGR-15 zero. The first native session identity survives copied parent metadata in a child file.

Ambiguous order means only a different session of the same ticket overlaps the turn. It is common, not hidden: Claude-main ambiguous token shares are **78.245% / 47.145%**, child and Codex shares **100% / 100%**. Claude-main ambiguous raw-minute shares are **88.982% / 54.923%**, Codex **100% / 100%**. This labels ticket-flow position under concurrent work, not each turn's purpose. Stable timestamp/source ordering selects a marker; the whole turn keeps it, including calls after later markers. Earlier context and completion-only turns remain included.

### One-time hand reconciliation

`review-cost-example.csv` uses millions of tokens (`_m`), not stage minutes. Compare each file's own token shares; its hand counts are rounded to 0.1M. The generated audit totals are 88.196M / 58.022M versus hand 82.9M / 57.9M. No hand clock window assigns an extractor turn.

Crosswalk: design/implement map directly; early PR/bot-stage work and first_review map to the mixed first-reviews bin. Fix markers use the latest explicit fix-dispatch task: IGR-15 findings round 1, round 2 and final review map to the corresponding hand bins (estimate TSV rows 240/245/247); IGR-16 fix dispatch row 243 maps to fix1. IGR-15 further_review plus finish map to final; IGR-16 further_review maps to round2, finish to final. This is comparison arithmetic only; generated stages stay separate.

| Ticket | Bin | Pilot % | Hand % | Gap, points |
|---|---|---:|---:|---:|
| IGR-15 | design / implement | 20.686 / 6.475 | 19.421 / 8.926 | +1.265 / -2.452 |
| IGR-15 | first reviews / fix1 | 14.911 / 20.789 | 14.717 / 19.059 | +0.195 / +1.730 |
| IGR-15 | round2 / final | 15.920 / 21.219 | 18.697 / 19.180 | -2.777 / +2.039 |
| IGR-16 | design / implement | 47.131 / 3.424 | 40.242 / 9.326 | **+6.890 / -5.902** |
| IGR-16 | first reviews / fix1 | 19.405 / 6.514 | 16.753 / 7.599 | +2.652 / -1.085 |
| IGR-16 | round2 / final | 10.850 / 12.675 | 11.917 / 14.162 | -1.067 / -1.487 |

Both >5-point gaps are explained. The hand implement boundary is 15:15 UTC; the observed implement dispatch is 15:18:12 (`~/.claude/agent-estimates.tsv:241`). Five design-latched turns contain **4,007,747 tokens at/after that hand boundary**: Claude turns `9fef16bc-9dab-4817-8538-2d4f8ddda45a` (1,767,119), `7a115b6e-456e-4f25-95a7-0edcef032ae2` (1,015,882), `1a61d868-9cad-4664-8263-8e8bfececfb1` (660,172); Codex turns `01a14a6f-aba8-75d1-8de3-9522f8e54b0a` (545,780) and `01a14a70-ecda-77d3-b0ad-414e608f7265` (18,794). Their native starts/first calls precede the recorded implement marker; the audit retains design from ticket start (`5d92909e-...jsonl:11`). The Claude duration references are `5d92909e-...jsonl:1771`, `d7328052-...jsonl:207` and `:287`; full source paths and call timestamps are in calls.csv.

That diagnostic accounts for 6.907 points of displacement, leaving design/implement comparison residuals about -0.017 / +1.005 points. It does not reassign or split any turn. All other bins differ by <5 points; high ambiguity does not prevent this evidence-based explanation. Numeric and hand check output: `NUMERIC_GATE PASS failures=0; hand reconciliation requires report`, `TOKEN_BUCKET_CONSERVATION PASS checks=24`, `HAND_RECONCILIATION PASS: all >5pp gaps explained; stage assignments unchanged`. Full local gate evidence: `igr/gate-1.md`.

Not yet exercised: full three-repo/window output, complete activity/family/wait/estimate enrichment, full GitHub review/fix/bot/size and churn, combined pipeline fixture, 57% simplify claim, Claude's 50-call audit/IGR-14 note. Existing dashboard notes below describe the separate unchanged dashboard; prototype cleanup and the full column dictionary are scheduled for later approved steps.

### Local measurements (step 2)

`local.collect(end)` now collects the local slice for the fixed home-relative jigs, condition-curator and agent-platform roots. It reuses canonical `bin/usage.collect` records, retaining earlier context and unassigned calls. Repo mapping is lexical and does not require surviving worktree directories. This slice is fixture-tested; the command above remains the explicit two-ticket pilot until step 4 integrates the full command. The accepted pilot CSVs have not been regenerated.

Local audit additions: `activity`, `activity_basis`, `activity_source`, `child_type`, full `child_description`, `child_family`, and `child_basis`. Activity uses native tool inputs with the prototype's first-match vocabulary, extended to Codex tool names/source. Missing inputs remain `other` with a missing-input reason. Child identity comes from sidecars/native metadata and linked launch inputs. A recorded simplify launch can supply its lenses' family. Missing identity remains blank; parent-session links can supply a ticket from prior evidence, never a future/majority ticket. Audit missing reasons name absent child fields and attribution evidence.

Local stage/ticket additions: `foreground_wait_min`, `simplify_passes`, `native_review_passes`, `own_review_passes`, and `fix_rounds`. Waits are the union of matched foreground invocation/result intervals, clipped to completed raw turn intervals: an observed floor, never subtracted from raw work. Explicit background waits and unmatched results supply no interval. `turn_overlap_min` charges same-session overlap to later source-ordered turns; cross-session work remains parallel. Both minute diagnostics sum through stages to tickets. Missing wait collection is blank; observed no-wait is zero. Review counts use distinct invocation groups, including reruns; simplify lenses share their launch group. Fix dispatches/transitions count rounds, while commits remain cycle evidence rather than rounds.

Ticket estimate additions: `dispatches`, `estimated_rounds_low/high`, `estimated_minutes_low/high`, and `completed_dispatch_minutes`, from deduplicated estimate TSV dispatch IDs whose start is in the requested window. Each dispatch's raw identity, bounds, actual minutes and TSV row source are also run provenance. Blank required bounds/actuals propagate through sums; a known empty dispatch set is zero. Raw provider minutes remain independent of dispatch elapsed-minute estimates.

Native hydration now prefers recorded starts, retains completion-only/incomplete turns, deduplicates provider identities and durations, and includes recorded Codex children. Full completed duration is selected by completion timestamp; incomplete turns supply calls but no duration. No Claude-child duration is manufactured. Successful step receipts and native/estimate invocation markers feed the existing ticket-wide, whole-turn stage latch; only another session of the same ticket overlapping the turn marks stage order ambiguous.

Not exercised in step 2: real three-repo/full-window collection, pilot regeneration, full GitHub enrichment, combined pipeline fixture, existing usage suite, full suite or CI, the 57% simplify measurement, and the externally owned 50-call audit/IGR-14 note. Their planned gates and ownership remain unchanged.

### GitHub enrichment and tables (step 3)

`github_fetch.collect({repo: ticket_keys})` now supplies the full read-only PR snapshot and timestamp markers for table assembly. It checks host-keyring authentication first and uses the same `env -u GITHUB_TOKEN -u GH_TOKEN -u GH_ENTERPRISE_TOKEN gh` prefix for every request. Call it outside the sandbox. PR listings, submitted reviews, inline/issue comments and current commits use paginated GET requests. Exact case-insensitive separator-bounded ticket keys join head refs, including zero or multiple PRs. A failed request or incomplete current commit list aborts collection; it cannot become an empty successful result. Command integration remains step 4; accepted pilot CSVs remain unchanged.

Ticket snapshot columns: `prs`, `pr_files`, `pr_additions`, `pr_deletions`, `pr_commits`, `initial_commits`, `fix_commits`, `initial_additions/deletions`, `fix_additions/deletions`, `churn_ratio`, `fix_split_status`, `bot_reviews`, `bot_comments`, `bot_threads`, and `review_after_bot`. `pr_files` sums each PR's changed-file count; it is not a count of unique files across PRs. Bot identity uses API user type. Review/comment IDs deduplicate within their API surface; inline replies roll up to thread roots, including a bot reply to a human root. Draft reviews do not supply submitted-review boundaries or bot review counts.

Author dates split current PR commits before versus at/after the earliest submitted PR review. Churn is fix added+deleted divided by initial added+deleted. `fix_split_status` is one of `author_time_estimate`, `suspect`, `unavailable`. Interleaved author partitions, disagreement with a reviewed SHA present in the fetched list, or author/committer dates straddling the cutoff mark an available estimate suspect. Missing boundary/stats/ancestry or a zero initial denominator leaves affected results blank, preserving known counts. Multi-parent commit line sums are unavailable to avoid counting ancestry twice. No old Git objects are recovered. Rebase/amend/squash history can still defeat this estimate without a detectable inconsistency. Ticket ratios require every PR contribution and use combined line totals, never a mean of PR ratios; the worst split status propagates.

`review_after_bot` is one ticket-wide value: 1 for an observed agent review invocation strictly after the ticket's first bot activity, 0 for none when applicable timing and review evidence are available, blank for unavailable/not-applicable evidence or an unresolved cross-source equality. It does not assert that the bot caused the review. Review invocations are selected in the requested UTC window; prior bot context remains available. Stage/ticket `fix_cycles` counts observed fix cycles independently of fix rounds and commit counts. A PR's submitted review boundary can establish a first-review stage without inventing an agent pass.

Shared schemas and required-component sums live in `table_common.py`; stage, ticket and run assembly each have a small module. `coverage=complete|partial` describes source/attribution gaps. Unmatched starts, unrecorded native-review usage, missing child identity, unavailable PR/estimate components and unknown/ambiguous attribution remain visible without discarding recorded work. Known-empty sets are zero; uncollected sources and required missing components remain blank. Duplicate canonical calls are rejected before publication.

Run provenance includes each PR's repo, number, current head ref/SHA, snapshot sizes, split counts/status and bot counts, plus existing event/source references. Run diagnostics count measured source files/sessions, PR heads, unassigned calls, unknown calls, ambiguous turns, unmatched starts, multi-repo tickets, no-PR tickets and native-review usage gaps. Completion-only turns contribute source/repo coverage; unavailable token buckets cannot fabricate a coverage-share denominator. No per-repo aggregate rows or warning matrix is added. CSV formatting/publication is shared; source/serialization failure before publication preserves the previous four output files.

Step 3 validation is offline fixtures plus build/import. Live checks were limited to host-keyring authentication and one jigs repository metadata GET. Full PR/API and Sawmills access, live churn, full-window output, the combined pipeline fixture and later acceptance gates remain unexercised.

Goal: same quality, fewer tokens per ticket. The flow started on 2026-10-05.

- `milestones.json`: **the critical changes to the ticket flow and how we work.** One entry per change: `hash`, `label`, `effect` (`down` saves tokens, `up` adds work, `mixed` adds work now and may save later, `base` baseline), `why`. `effect` is a reading of the commit message, not a measurement. Edit it when you know better.
- `build_flow.py`: reads `bin/usage export` and the milestones, writes `site/data.json`.
- `build.py`: the older CSV export (daily, weekly, tickets). Not used by the site.
- `site/`: the dashboard, deployed to brisk as `ticket-stats`.

## Refresh

```sh
python3 stats/build_flow.py 2026-10-05 2026-10-19 --usage .worktrees/igor/igr-18/bin/usage   # END is exclusive
BRISK_SERVER=http://localhost:8787 brisk deploy stats/site
```

`bin/usage` is not on local `main` yet; use the copy in the worktree (or `origin/main`) until it is. Set `BRISK_SERVER` explicitly: the active brisk profile is the remote instance.

## What counts as a critical change

A commit under `plugins/igr` that changes what a session or codex does per ticket:

- adds, removes or reorders a step, pass, review or check;
- changes how codex is driven (clearing, effort, briefs, passes);
- moves work to a script (`tk`) or to CI;
- changes context handling (resume, `/clear`, handoffs);
- changes test or tool-output policy.

Not critical: wording, the progress band, release bumps (`chore(release)`), agent-estimate internals, bug fixes to a mechanism that already exists, file locations.

## Reviewed through

Every `plugins/igr` commit up to `093019d` (2026-10-17 18:57, `origin/main`) has been read. To update, list only newer ones:

```sh
git log origin/main --reverse --format='%h %aI %s' --stat 093019d..origin/main -- plugins/igr
```

Read but not added, so nobody reads them again:

| commit | why not |
| --- | --- |
| 141bb05 | tk CLI added but not used by the loop; `8421409` is when the loop runs on it |
| efd9e52, 9481f6e, be8c666 | extend the cut / earn-its-place check; `9686720` and `78d9ad0` are the step |
| 8309afd, 8611d2a, caa7849, 14269be | approval report and brief wording |
| 504f09c | moves references into the plugin, same content |
| 57c4c75 | small test-run bound, next to `cd086fb` |
| 3957047, 49bed03, a753b76, 21928c3 | fixes to resume (`1a24aa2`) |
| 7cf5161 | Linear connection fix |
| 5d536c7, 5d27223 | where tk keeps its files |
| 7fb61f5 | parks herdr handoff tools, not used by the loop |
| 98e7a6b, 5b7958f, 4c60880, fb668bd | agent-estimate internals |
| 265dee8, c6f6722, 6be2234 | band UI, release |

## How to read the numbers

- **Weighted** is the IGR-14 proxy from `bin/usage` (cache read 0.1x, cache write 1.25-2x, output 5x, model multiplier). Claude only, uncalibrated. Codex has raw tokens only.
- Only calls tagged with a ticket count.
- Stage comes from `tk step` commands, which only exist after `8421409` (2026-10-10 16:10). Before it, develop and review cost sits under design or unknown. Compare totals across that change, not stages.
- Tickets can run for days: 90% finish within 1.4 days, the longest took 7. Tickets started in the last 2 days of data are treated as still running.
- Before/after around a change is observation, not proof: ticket size, neighbouring changes and small samples all move it. Quality is not measured.
