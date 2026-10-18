# stats: ticket-flow measurements

## Command and outputs

```sh
python3 -B -m stats.ticket_flow 2026-10-05 2026-10-18
```

Two positional `YYYY-MM-DD` dates, UTC, START inclusive and END exclusive; END must be later. Python stdlib only. Run from the jigs checkout outside the sandbox. Local discovery uses fixed home-relative roots: `~/my/dev-tools/jigs` (`ig-ra/jigs`), `~/work/condition-curator` (`Sawmills/condition-curator`), and `~/work/agent-platform` (`Sawmills/agent-platform`). Lexical cwd mapping includes deleted worktrees; authored-commit lookup uses their configured home-relative repository when the recorded worktree is gone, retaining unavailable status for absent objects; recorded session/parent links resolve tickets without majority attribution. Canonical calls, JSON iteration and timestamp parsing come from `bin/usage` through one SourceFileLoader bridge; its behavior is unchanged.

GitHub access is read-only, using the host keyring. The collector authenticates first, then prefixes every paginated GET with:

```sh
env -u GITHUB_TOKEN -u GH_TOKEN -u GH_ENTERPRISE_TOKEN gh auth status
# Each API request uses this same environment prefix:
env -u GITHUB_TOKEN -u GH_TOKEN -u GH_ENTERPRISE_TOKEN gh api --method GET ENDPOINT
```

The command writes `stats/runs/START_END/`: tracked `stages.csv`, `tickets.csv`, `run.csv`, and generated, ignored `calls.csv` for call inspection and the externally owned 50-call audit. It returns 0 with `TICKET_FLOW_OUTPUT_WRITTEN PATH` after successful collection, assembly and publication; source/API failure returns 2. Collection/serialization failures preserve previous outputs. There is no partial successful collection or missing-repo zero. File replacement happens after serialization; this is not a transactional multi-file filesystem swap.

Identical inputs produce identical bytes: all columns and rows have stable order, UTF-8 CSV uses LF, floating values have six decimal places, and no generated wall-clock timestamp is added. Event times remain provenance. Logs, estimates and current GitHub state can change between runs. The accepted pilot directory `2026-10-17_2026-10-18` retains its original step-1 schema and data; the dictionary below describes the complete command schema.

## Developer checks

```sh
# Offline suite: three live tests skipped; no network or real-log access.
python3 -B -m unittest discover -s tests/stats -p 'test_*.py'
# Same suite, deliberately outside the sandbox; host keyring and real logs required.
TICKET_FLOW_LIVE=1 python3 -B -m unittest discover -s tests/stats -p 'test_*.py'
# Offline check of one written run, including its retained ignored audit.
python3 -B -m stats.ticket_flow.check stats/runs/2026-10-05_2026-10-18
# Standing acceptance check for the published run, including overall other <5%.
python3 -B -m stats.ticket_flow.check stats/runs/2026-10-05_2026-10-18 --activity-target
```

The checker reads only the four CSVs. It checks identity/population, raw token/minute conservation, activity evidence, PR missingness/aggregation, and grouped native-review agreement. Overall and actor/repo activity shares are diagnostics for any window; missing activity labels or tokens still fail. By default it prints `ACTIVITY_TARGET_NOT_REQUESTED`. The published 2026-10-05 through 2026-10-18 acceptance run additionally requires overall activity `other <5%`: run the standing command above with `--activity-target`. It prints `ACTIVITY_TARGET_PASS` or `ACTIVITY_TARGET_FAIL` with numerator, denominator, percentage and strict target; a zero denominator fails the requested target. This target measures coverage for the published mix, not validity of every date window. The checker prints recorded unknown/ambiguous shares without recomputing them. Success ends `OUTPUT_CHECK_PASS checks=N`; missing evidence or failed assertions end `OUTPUT_CHECK_FAIL failures=N`, exit 1, with affected files/keys/metrics and numbers. The original pilot lacks required activity/PR/native evidence and fails explicitly. A checkout without ignored `calls.csv` cannot be certified. No baseline mode or fixed historical totals.

Live opt-in authenticates via the exact host-keyring prefix above, checks jigs PR 3/IGR-15 against independently fetched review/comment lists and commits, forces actual multiple-page commit fetching, then runs 2026-10-17 through 2026-10-18 against real home logs and estimates in a temporary working directory and checks its internal consistency without `--activity-target`. The one-day activity mix cannot fail the live test. All three tests skip unless `TICKET_FLOW_LIVE=1`; missing prerequisites after opt-in fail. Direct requests print actual gh command/GET-page counts and elapsed time; the separate command prints its elapsed time, with request count unmeasured. No retries. Real quota applies; the one-day command measured 5 minutes 10 seconds in the step-7b run (3600-second cap); the full published window takes tens of minutes. A developer can select just `test_live` with normal unittest selectors.

Every behavioral fix carries its regression tests. A real run regenerates tracked outputs; it does not replace tests. The live test publishes only temporary outputs. Serialized consistency cannot independently prove native-source completeness, stage intent, semantic churn accuracy or the separate 50-call classification audit; one PR/day cannot cover every repo or log dialect. No Claude-child duration or standalone native-review usage is invented.

## Measurement and missingness

Calls are selected by call timestamp. Full completed durations are selected by completion timestamp, even if they began before START. Earlier context stays available for attribution. Incomplete turns can supply calls; completion-only turns can supply time. Claude main time sums native `turn_duration` records. Codex time uses completed native start/complete pairs, including children. No Claude-child minutes or standalone native-review usage is invented. Unmatched Codex starts remain counted alongside recorded work.

Each ticket has one timestamp-ordered marker timeline: ticket start/finish, successful step receipts, estimate dispatches, simplify/native/own review invocations, PR creation/merge, earliest submitted review, authored fix commits and first bot activity. Native turn start is preferred, first attributable call otherwise, duration-derived start for completion-only evidence. Latest marker at/before that start is latched for the entire turn. Equal-time markers use stable source/identity order. `stage_order=ambiguous` means only that a different session of the same ticket overlaps the turn. Unknown stage and ambiguous order are separate diagnostics; neither discards tokens/time. No hand clock-window stage assignment. Native-review markers require an executable reviewer command, directly or in a recorded literal shell wrapper; documentation writes, searches, waits, delegated messages and help-only queries are excluded. A recorded receiver invocation counts, as does each genuine rerun. Opaque dynamically constructed wrapper commands cannot establish an invocation. `first_review` means the first agent review pass and can follow a fix stage when a bot or human reviewed the PR first; remote reviews never count as agent passes.

Blank means unavailable or not applicable; zero means an observed empty set/count. A required missing token/PR/estimate component propagates through the relevant sum. PR lookup is available only after successful queries for all recorded known-repo associations of that ticket; no recorded association leaves PR measures blank and coverage partial. Successful empty lookups retain zero. The exact global `no_pr_tickets` total is blank if any named ticket lacks lookup evidence. Source failures abort the run. `coverage` is one `complete|partial` field: attribution gaps, ambiguous ordering, missing child identity, unrecorded native-review usage, incomplete durations, malformed reader records, unavailable PR/estimate components or unmatched starts can make it partial. Recorded provider work remains present. Codex parentage alone is not a coverage gap: measured child durations count; missing child type, description, family or other required evidence still makes coverage partial, including completion-only children. Claude-child duration remains unavailable. A complete row does not establish that all unrecorded work was captured.

Raw minutes include foreground sleeps/watches. `foreground_wait_min` is a floor from matched foreground tool invocation/result intervals; background/unmatched waits are not proved. `turn_overlap_min` is same-session overlap charged once to the later source-ordered turn. Both are reported alongside raw minutes, never subtracted. Cross-session work remains parallel actor work; summed agent minutes are not wall elapsed time. No Claude-child time denominator exists.

## Column dictionary

Definitions below expand every current schema field. `A` expands to each of `claude_main`, `claude_subagents`, `codex`; `T` expands to each of `new_input_tokens`, `cache_read_tokens`, `cache_write_tokens`, `output_tokens`. These denote twelve separate summary columns, in actor/token order. Tokens are raw counts, with no prices, weights, or extra reasoning-token addition. Missing canonical buckets stay blank; no calls for a known actor set yields zero in summaries.

### calls.csv (generated audit)

| Column(s) | Source, unit and missingness |
|---|---|
| `provider`, `id` | Canonical usage provider (`claude\|codex`) and provider call ID; deduplicated identity pair. |
| `timestamp` | Canonical call UTC event time; determines window inclusion. |
| `ticket`, `ticket_basis` | Canonical/native ticket attribution and evidence basis, including recorded parent links; blank if unresolved. |
| `repo` | Fixed-root lexical call cwd, falling back to the turn repo; blank for unmapped cwd. |
| `actor` | Claude main/child or Codex; Codex includes children. |
| `session`, `parent_session`, `turn` | Native session, recorded parent and native/composite turn ID; parent blank when absent. |
| `turn_start`, `start_basis` | Attribution start, UTC; basis `native_start\|first_call\|duration_record`. Blank time if unavailable. |
| `source` | Canonical source path and line for the call. |
| `marker_time`, `marker_source`, `marker_repo` | Selected ticket marker's event time, source reference and repo; blank when absent/unmapped. |
| `stage` | Latched `design\|implement\|first_review\|fix\|bots_ci\|further_review\|finish\|unknown`. |
| `stage_order` | `timestamp\|ambiguous`, by cross-session turn overlap only. |
| `review_pass`, `cycle` | Ticket timeline's cumulative review-pass/fix-cycle ordinal; blank before any. |
| `activity` | First-match native tool-input classification; exact labels below. |
| `activity_basis` | `native_tool_inputs\|no_tools\|missing_tool_input`; missing inputs force `other`. |
| `activity_source` | Semicolon-separated native tool source path/lines; blank for no tools. |
| `child_type`, `child_description`, `child_family` | Recorded sidecar/native metadata or linked launch; description retained in full. Family `simplify\|review\|explore` when evidenced; otherwise blank. Non-children blank. |
| `child_basis` | Sidecar/native/linked launch or simplify invocation reference; blank without evidence. |
| `new_input_tokens`, `cache_read_tokens`, `cache_write_tokens`, `output_tokens` | Four disjoint canonical raw buckets; integer tokens, unavailable bucket blank. |
| `missing_reason` | Semicolon-separated `unassigned_ticket`, `no_preceding_marker`, `missing_tool_input`, `missing_child_type`, `missing_child_description`, `missing_child_family`; blank if none. |

Activity labels, in rule precedence: `reply / communication (no tool)` for no tools; otherwise `human poll`, `subagent dispatch`, `agent communication`, native worktree setup/cleanup, Skill instruction reads, `linear`, `native codex review`, `codex management (herdr)`, `github / CI / bot threads`, `tk bookkeeping (step, estimate)`, `worktree setup / cleanup`, `tests / measurements`, `git`, `waiting`, `codex briefs and replies`, `design docs (models, plan, KISS)`, `review docs`, `checkpoint`, `skill / memory reads`, `source edits`, `code / doc reading`, wait-tool fallback `waiting`, then `other`. One call gets one label, including mixed-tool calls. The unclassified token share counts `other`; it differs from unknown-stage share. ToolSearch reads API definitions (`code / doc reading`); Skill loads skill instructions (`skill / memory reads`); EnterWorktree/ExitWorktree are worktree setup/cleanup. Monitor uses the command rules, falling back to waiting. `agent communication` covers native handbacks and agent messages: the no-tool reply label would be inaccurate for those tool calls. Direct `tools.NAME(...)` calls inside Codex exec are read statically, skipping quoted/commented examples; source text is never executed. Recognized nested operations use the same vocabulary. Bash script location or interpreter alone does not establish purpose; opaque scripts remain `other`. Tool names/input vocabulary is heuristic; the separate 50-call audit measures classification quality.

### stages.csv

One row per `ticket,stage,review_pass,cycle`; repo is not a grouping key. Unknown/unassigned work remains included.

| Column(s) | Source, unit and missingness |
|---|---|
| `ticket`, `stage`, `review_pass`, `cycle` | Audit/turn latched keys as above, also groups for window markers without calls or completed turns. Ticket blank if unassigned. |
| `A_T` (12 columns) | Sum corresponding actor's canonical call token bucket; any required missing bucket makes that sum blank. |
| `claude_main_minutes_raw`, `codex_minutes_raw` | Sum selected full completed native durations, minutes; known-empty zero. |
| `foreground_wait_min`, `turn_overlap_min` | Observed waits and same-session overlap in minutes, as described above; waits propagate missing components. |
| `simplify_passes`, `native_review_passes`, `own_review_passes` | Count window-selected invocation groups by kind, not individual simplify lenses; known-empty zero. |
| `fix_rounds` | Explicit fixing/dispatch invocation count; running/fixing receipt plus first dispatch is one invocation. |
| `fix_cycles` | One for each stage key in `fix` with an observed cycle; independent of round/commit counts. |
| `calls`, `turns` | Audit call count and window-completed native turn count; known-empty zero. Incomplete turns do not supply duration. |
| `coverage` | `complete\|partial` for the row's source/attribution evidence. |

### tickets.csv

One row per ticket, including a blank-ticket group when unassigned work exists. Contains `ticket`, every `A_T`, both `*_minutes_raw`, `foreground_wait_min`, `turn_overlap_min`, all three `*_passes`, `fix_rounds`, `fix_cycles`, `calls`, `turns`, and `coverage` with the stage definitions above. Each measure sums stage rows with required-component propagation. Additional columns:

| Column(s) | Source, unit and missingness |
|---|---|
| `dispatches` | Deduplicated estimate TSV dispatch IDs started within the window; count, blank if not collected. |
| `estimated_rounds_low`, `estimated_rounds_high` | Sum selected TSV lower/upper rounds bounds; missing bound propagates. |
| `estimated_minutes_low`, `estimated_minutes_high` | Sum TSV `est_min` bounds, minutes; missing bound propagates. |
| `completed_dispatch_minutes` | Sum selected TSV `actual_min`, minutes; unfinished/missing values propagate. Not the native-duration total. |
| `prs` | Distinct `(repo,number)` head-ref matches; zero if lookup succeeded with none, blank if unavailable. |
| `pr_files`, `pr_additions`, `pr_deletions`, `pr_commits` | Sum current PR snapshot changed-file/added-line/deleted-line/commit counts; any missing contribution propagates. Files can repeat across PRs. |
| `initial_commits`, `fix_commits` | Current PR commits partitioned before versus at/after earliest submitted review using author dates; missing boundary/date makes affected values blank. |
| `initial_additions`, `initial_deletions`, `fix_additions`, `fix_deletions` | Sum current commit stats per partition, lines; missing stats/ancestry or multi-parent ancestry makes affected sums blank. |
| `churn_ratio` | Combined fix added+deleted divided by combined initial added+deleted; unitless. Blank if any required PR contribution unavailable or initial denominator zero. Never an average of PR ratios. |
| `fix_split_status` | Worst PR status: `author_time_estimate\|suspect\|unavailable`; no matched PR means unavailable. |
| `bot_reviews` | Count submitted reviews by the three named review-bot logins below, deduplicated by review ID; draft reviews excluded. |
| `bot_comments` | Bot inline plus issue comments, IDs deduplicated within each API surface. |
| `bot_threads` | Distinct inline thread roots containing bot comments, including replies to human roots. |
| `review_after_bot` | Ticket-wide 1 if observed agent review strictly follows first bot activity, 0 for known applicable absence; blank if unavailable/not applicable or unresolved tied cross-source order. No causality claim. |

PR joins use the whole case-insensitive separator-bounded ticket key in the head ref, zero to many PRs across repos. Listings and reviews/comments/commits are paginated; all current commits must be returned. PR facts are current snapshots, not window-limited historical size. Author-time churn is an estimate: interleaved partitions, contradiction with a reviewed SHA present in the current list, or author/committer dates straddling the cutoff mark an available estimate suspect. Rebase/amend/squash history can defeat the split without a visible inconsistency. No historical Git objects are recovered. Bot counts are snapshot totals, not distinct reviewed-head rounds.

### run.csv (long-form provenance)

| Column | Meaning |
|---|---|
| `ticket`, `actor` | Applicable ticket/actor context, blank for global facts or unresolved ticket. |
| `metric`, `value` | Metric name and scalar/string value; blank value for unavailable facts. |
| `numerator`, `denominator` | Raw tokens or minutes underlying percentage rows; blank if population/component unavailable. Percent value is 100 × numerator / denominator; zero denominator gives blank percent. |
| `repo`, `pr` | Applicable marker/PR repo and PR number; blank for local/global metrics. No repo aggregate rows. |
| `source` | Native path/line, estimate TSV row or `github:REPO#NUMBER` reference; blank for derived totals. |

Metric families (every emitted name):

- Window: `window_start`, `window_end_exclusive` (UTC event boundaries).
- Global measured population: `source_files`, `sessions`, `unassigned_calls`, `unknown_calls`, `ambiguous_turns`, `multi_repo_tickets`, `no_pr_tickets`, `pr_heads` (counts; unavailable PR data stays blank).
- Reader counters: `reader_malformed`, `reader_duplicate`, `reader_synthetic`, `reader_unassigned` from the canonical reader. Collection includes pre-window context, so these are not window call totals; extra counter keys, if supplied by that reader, retain the `reader_` prefix.
- Per ticket: `calls`, `unmatched_starts`, `claude_duration_records`, `codex_completed_pairs`, `prs_found`, `native_review_usage_missing` (counts); `pr_lookup_available` is 1 for successfully queried ticket associations, 0 otherwise. Unmatched starts reflect native turns starting before exclusive END, including pre-START context; starts at or after END are excluded. Native-review missing count is observed window invocations, not missing token quantity.
- Per ticket/actor: `unknown_tokens_pct`, `ambiguous_tokens_pct` (four-bucket token counts); `unknown_minutes_pct`, `ambiguous_minutes_pct` (completed raw minutes). Unobserved actors/Claude-child time have blank denominators, not synthetic zeros.
- Per PR: `pr_head_ref`, `pr_head_sha`, `pr_created`, `pr_merged`, `pr_first_review`, `pr_first_bot`; `pr_pr_files`, `pr_pr_additions`, `pr_pr_deletions`, `pr_pr_commits`; `pr_initial_commits`, `pr_fix_commits`, `pr_initial_additions`, `pr_initial_deletions`, `pr_fix_additions`, `pr_fix_deletions`, `pr_churn_ratio`, `pr_fix_split_status`, `pr_bot_reviews`, `pr_bot_comments`, `pr_bot_threads`. These preserve the snapshot/partition definitions above; event values are UTC timestamps and absent events stay blank.
- `marker_KIND`: full context marker inventory with UTC event value and source. Kinds `design`, `implement`, `first_review`, `fix`, `bots_ci`, `further_review`, `finish`, `review`, `simplify`, `native_review`, `own_review`, `commit` as available; context can predate START.
- `estimate_identity`, `estimate_rounds_low`, `estimate_rounds_high`, `estimate_minutes_low`, `estimate_minutes_high`, `estimate_actual_minutes`: each selected dispatch's ID/bounds/actual with TSV row source and agent in `actor`; unfinished values blank.

## Accepted coverage gate (historical pilot)

Step 1's `2026-10-17_2026-10-18` pilot contains 981 canonical calls. All 24 actor/token buckets and recorded completed durations conserve from calls/turns through stages to tickets. Claude minutes **62.553067 / 27.024650** round to **63/27**; Codex **104.859500 / 31.890033** to **105/32**, for IGR-15/16. Unknown tokens and raw minutes are **0%** in every observed ticket/actor/provider group. Unmatched starts: IGR-15 zero, IGR-16 one. Missing native-review usage/Claude-child time remains unavailable, never a fabricated denominator.

Ambiguous token shares: Claude main **78.245% / 47.145%**, children and Codex **100% / 100%**; ambiguous raw-minute shares Claude main **88.982% / 54.923%**, Codex **100% / 100%**. This is concurrent ticket-flow ordering, not inferred turn purpose. High ambiguity did not prevent the documented hand reconciliation. The pilot remains accepted historical evidence. This batch regenerates only `2026-10-05_2026-10-18`, leaving the pilot directory and hand references unchanged; invoking the command with the pilot dates would regenerate that directory under the current rules. Its original first-bot markers used the earlier any-Bot rule; the named-bot definition below applies to new command output. Full evidence: local `igr/gate-1.md`.

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

## Required three-repo run

The outside-sandbox run `timeout 3600 python3 -B -m stats.ticket_flow 2026-10-05 2026-10-18` completed on 2026-10-18 UTC from committed review-fix code **7f2142f**, exit 0, in approximately **1476 seconds**. It printed `TICKET_FLOW_OUTPUT_WRITTEN stats/runs/2026-10-05_2026-10-18`. All three repos completed: **4 jigs, 12 agent-platform and 152 condition-curator PRs** (168 total, 167 repo/head-SHA pairs). PR joins remain author-neutral, with complete earlier context and no PR creation/merge date filter.

The generated set has **65,752 calls, 1,543 stage rows, 136 ticket rows (including unassigned work), 10,532 run rows**. Token, completed-duration, count and publication-population reconciliation passed **3135 assertions**. Compared with the prior publication, all 65,752 raw call identities/buckets and recorded minutes conserve; 15446 audit rows changed stage/marker/ordinal provenance. Raw recorded minutes: Claude main **8908.474082**, Codex **6912.360654**. These are agent sums, not elapsed time.

**The overall activity target passes:** `other` is **466,781,611 / 12,526,312,980 tokens = 3.726408655%**, below **5%**, across 2333 calls. Activity labels and denominator are unchanged from the accepted activity-correction run. Native-review invocation recognition is separate from activity classification; removing wait/document/message/help markers does not relabel these calls. No source snapshot or real-data determinism rerun is implied.

| Actor | Other tokens | All raw tokens | Other % |
|---|---:|---:|---:|
| claude_main | 273,659,199 | 8,155,963,903 | 3.355326 |
| claude_subagents | 15,435,651 | 1,299,221,622 | 1.188069 |
| codex | 177,686,761 | 3,071,127,455 | 5.785718 |

| Repo | Other tokens | All raw tokens | Other % |
|---|---:|---:|---:|
| unmapped repo | 44,593,088 | 715,605,164 | 6.231521 |
| Sawmills/agent-platform | 41,721,153 | 648,244,057 | 6.436026 |
| Sawmills/condition-curator | 366,354,317 | 10,860,089,759 | 3.373400 |
| ig-ra/jigs | 14,113,053 | 302,374,000 | 4.667416 |

The acceptance criterion applies to the overall token share. Codex, agent-platform and unmapped-repo subgroups remain above 5% and are shown explicitly. The 50-call activity hand audit remains Igor's separate check; passing the percentage does not establish a misclassification rate. Opaque scripts and unsupported tool kinds remain other.

Observed source gaps: **5180 unassigned calls**, **3715 unknown-stage calls**, **9019 ambiguous selected turns**, **144 unmatched starts** (starts before exclusive END, including earlier context), **143 window native-review invocations with missing usage**, and **3871 Claude-child calls without a classified family**. Ticket coverage: 129 partial, 7 complete. PR lookup is unavailable for 15 named tickets plus unassigned work; their PR measures and the exact global `no_pr_tickets` total are blank, not observed zero. Selected population: 1276 source files, 1275 sessions; reader counters include historical context (100629 duplicates, 46 synthetic, 62778 unassigned, 0 malformed). Missing native-review token quantities and Claude-child durations remain unavailable. Unknown stage is separate from activity other.

No rate-limit or repo-access error occurred. Two Python syntax warnings arose while statically decoding recorded wrapper strings; collection completed. Individual phase costs were not profiled. Correction commits, quoted gates, ticket/row deltas and unexercised checks: local `igr/report-6.md`; earlier reports remain historical evidence.

## Preservation and the separate dashboard

The obsolete untracked copies `stats/activity.py`, `stats/build.py`, `stats/daily.csv`, `stats/weekly.csv`, `stats/tickets.csv`, `stats/activity-daily.csv`, `stats/activity-tickets.csv`, `stats/subagents.csv` are excluded from this change. Originals remain in the canonical checkout; no files are deleted. The extractor supersedes their measurement job.

The following supplied artifacts are tracked unchanged: `build_flow.py`, `milestones.json`, `site/`, `active-time-example.csv`, `review-cost-example.csv`, `retro-igr-15-16.md`. Before/after SHA-256 inventories and canonical byte comparisons establish preservation; same-named `site/{daily,weekly,tickets}.csv` remain included. No dashboard regeneration/deployment is part of this work.

The separate dashboard's goal is same quality with fewer tokens per ticket; its flow history starts 2026-10-05. `milestones.json` records critical workflow changes (`hash`, `label`, `effect`, `why`); effects are readings of commit messages, not measured savings. `build_flow.py` reads usage exports and milestones to write `site/data.json`. The preserved site was deployed as `ticket-stats`; that historical deployment is not refreshed/verified here.

For the dashboard, weighted usage is the uncalibrated IGR-14 Claude proxy, with no Codex weighted estimate. Only ticket-tagged calls count. Stage receipts began with `8421409` (2026-10-10 16:10); compare totals rather than stages across that change. Recent tickets can still be running. Before/after observations are affected by ticket size, nearby changes and small samples; findings quality is not measured. This dashboard interpretation is separate from the raw extractor schema above.

The supplied milestone review covered `plugins/igr` through `093019d`; see preserved `milestones.json` and retro for historical context. No dashboard refresh is needed to rerun the extractor.

## Validation and remaining ownership

Accepted fixture evidence: deterministic combined command, all three fixed roots, blank/zero propagation, token/completed-duration conservation, completion-only work, END exclusion and failed-source preservation. Step 4 (`da90362`) passed 19 focused tests and 21 usage bridge compatibility tests; steps 1–3 supply module tests. Reused gates require unchanged code/dependency/config inputs. Step 4b (`51b5683`) passed 48 focused tests and the build/import gate; step 5a (`92f6d9c`) passed 13 focused activity/pipeline tests plus build/import; step 5 passed compilation/import, real-data conservation and the overall activity target; no packaging build exists. Step 6 passed the affected module gates for PR lookup availability, executable-review recognition, END-retained starts, child coverage and mapped-root authored evidence, plus README table validation and build/import; its real full-window run passed conservation and the activity target. No full suite or hosted CI polling is required.

The 50-call activity audit and IGR-14 note remain Claude's work for Igor to review. Neither is completed by this data run. The audit surface is the generated `stats/runs/2026-10-05_2026-10-18/calls.csv`; native paths/line references contain local provenance and are intentionally not tracked. The 57% simplify claim, findings quality and standalone native-review usage remain unproved here.

Approved follow-ups filed: [IGR-28](https://linear.app/ig-ra/issue/IGR-28) Codex analysis-versus-change split; [IGR-29](https://linear.app/ig-ra/issue/IGR-29) bot rounds by reviewed head; [IGR-30](https://linear.app/ig-ra/issue/IGR-30) make `bin/usage` an importable package. Outside-contract findings belong in follow-ups, without changing the settled classifier or adding sources.

## Published population and review bots

Published tables include tickets with window calls, completed turns, local markers or selected estimate evidence, plus unassigned work. Earlier context and every recorded repo association for those tickets remain complete. GitHub enrichment cannot select the population; inactive tickets and tickets without a recorded known-repo association cause no guessed request. PR joins remain author-neutral, with no creation/merge date filter.

Review bots are `sawmills-architect-review[bot]`, `cubic-dev-ai[bot]` and `chatgpt-codex-connector[bot]`. Only those logins count toward bot reviews, comments, threads, first-bot time and ticket-wide `review_after_bot`. Baz (`baz-reviewer[bot]`), CodeRabbit (`coderabbitai[bot]`) and all other bot accounts are excluded. These numbers differ from the earlier any-Bot rule. All comments remain thread-root inputs; every submitted review still participates in the unchanged first-review churn boundary.
