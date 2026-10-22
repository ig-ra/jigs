# Retro: the first two runs of the new ticket flow (IGR-15, IGR-16)

Written 2026-10-18 for IGR-18. IGR-15 and IGR-16 were the first tickets run with fresh-session handoffs, `resume` and `tk` (igr 1.16.0, with 1.16.1-1.16.4 landing during them). Both are tool-building tickets in jigs, with manual help; two samples cannot give a clean before/after. Everything is in raw tokens: new input + cache read + cache write + output. Cost follows from tokens.

Sources: `bin/usage export` (rebuilt by `stats/build.py` and `stats/activity.py`), the raw Claude and Codex logs, `~/.claude/agent-estimates.tsv`, GitHub PRs 3 and 4, and the ticket records of both tickets (`igr/`, copied by the owner into `.worktrees/back` before finish; read for this retro, then removed).

## Verdict

* The handoffs do what IGR-6 set out to do: they cap session length. All six sessions ran 32-156 calls and none passed 400K context.
* Total tokens per ticket did not fall. Both tickets were median length, so the test on a long ticket (where the baseline cost sits) has not run.
* Review is the largest part and has no reset inside it: IGR-15's review session ended at 397K over 156 calls, and the work after the PR opened was 72% of its tokens. Filed as IGR-20.
* Of 13 places where the owner had to step in, 4 were already fixed by 1.16.1-1.16.4, 4 are not flow faults, and 5 became 3 new tickets (IGR-21, IGR-22, IGR-23).

## Tokens against the Oct 7-16 baseline

Main-thread context, Claude (tokens):

| Set | Calls | Median | p90 | Max | Calls at 400K+ |
|---|---|---|---|---|---|
| Baseline Oct 7-16, all | 26,173 | 252K | 550K | 968K | 23.8% |
| Baseline, tickets of 100-400 calls (same length as IGR-15/16) | 9,473 | 217K | 370K | 674K | 5.7% |
| Baseline, tickets over 400 calls | 12,408 | 329K | 610K | 968K | 36.8% |
| IGR-15 | 259 | 207K | 345K | 397K | 0% |
| IGR-16 | 232 | 179K | 254K | 296K | 0% |
| IGR-15 + IGR-16 | 491 | 193K | 295K | 397K | 0% |

Per phase, median / p90 / max: IGR-15 design 180K / 231K / 244K, develop 133K / 144K / 150K, review 258K / 349K / 397K. IGR-16 design 206K / 277K / 296K, develop 116K / 124K / 124K, review 196K / 245K / 252K. Baseline design 192K / 390K / 964K, develop 318K / 623K / 953K, review 383K / 689K / 968K.

Tokens per call and per ticket (Claude, subagents included): baseline 235K per call; IGR-15 181K (59.5M tokens, 328 calls); IGR-16 170K (42.5M, 250 calls). The baseline median ticket (88 tickets with 100+ calls) is 55M tokens and 267 calls, so both tickets are at the median. Same-length baseline tickets already ran at 188K per call, so most of the per-call drop is ticket length, not the flow.

Sessions: in the baseline 61 of 130 main sessions ran over 160 calls; they held 89% of cache-read tokens and 38 went past 400K. Post-dispatch session peaks on the new flow: 150K, 397K, 124K, 252K (median 201K; baseline median 408K with 20 of 39 past 400K). Number of handoffs: 2 per ticket (after approval, at PR ready), 4 in total.

Handoff before and after, first call and call 15 of the fresh session:

| Handoff | Before (last call) | After, first call | After, call 15 |
|---|---|---|---|
| IGR-15 design to develop | 244K | 66K | 125K |
| IGR-15 develop to review | 150K | 66K | 136K |
| IGR-16 design to develop | 296K | 68K | 111K |
| IGR-16 develop to review | 124K | 69K | 132K |

Resumed-session startup: the first call is 64-69K in all 15 sessions of Oct 17 (the fixed baseline, unchanged); call 15 is 111-136K, above the 90-115K predicted in IGR-6. Input for IGR-17.

Calls by actor, IGR-15 / IGR-16: Claude main plus subagents 328 / 250 (subagents 21% / 7%); Codex 244 / 159; Claude own review passes 2 / 2 (estimate log).

Models: the Oct 17 sessions ran mostly on Sonnet (79% / 95% of calls) against 6.5% in the baseline; token counts do not depend on the model.

## Agent working time

Wall spans overstate work (owner pauses, parallel tickets). Recorded turn times: IGR-15 Claude 63 min (spans 186), Codex 105 min (span 286); IGR-16 Claude 27 min (span 145), Codex 32 min (span 185). Agent minutes, not elapsed time. See `active-time-example.csv`.

## Tokens by flow stage (hand-set windows, see `review-cost-example.csv`)

IGR-15 / IGR-16: design 19% / 40%, implement 9% / 9%, first reviews 15% / 17%, findings discussion and fix 19% / 8%, round two and bots 19% / 12%, final pass, merge and finish 19% / 14%. After the PR opened: IGR-15 59M (2.5 times design plus implement), IGR-16 21M (0.7 times). The IGR-15 first-review window also holds the review-token design work.

## What the new activity split shows (main thread Oct 5-17, 9.5B tokens)

Text-only turns 23%, reading code and docs 21%, GitHub/CI/bot threads 16%, codex management 10%, unclassified 8.5%, git 6%, edits 4.5%, worktree setup 3%, Linear 2%, waiting 1.7%, skill/memory reads 1.3%, `tk` bookkeeping 1.1%. Classification is pattern matching, not hand-checked. Subagents: 1.5B tokens (14% of Claude); `/simplify` lens agents 57% of that (about 8% of all Claude tokens), run on Opus/high 92% regardless of the session model. The `/simplify` drop on Oct 16-17 is fewer launching sessions (weekend) and smaller diffs (0.3M tokens per agent against 1.4-2.8M), not a change in fan-out.

## Interventions (corrections and unblocks only)

| # | Ticket | What the owner had to do | Home |
|---|---|---|---|
| 1 | 15, 16 | Type the Linear tool names into the start command | Fixed 7cf5161 (1.16.1); live check unproven |
| 2 | 15 | Sessions ran in a non-Git folder: 4 errors (tk prep fatal, EnterWorktree refused twice, "is the current directory") | Fixed a753b76 (1.16.2) handoff passes the worktree, plus `tk go`; IGR-16 had none |
| 3 | 16 | Herdr agent name lost after /clear: 7 worktree-guard refusals, 1 agent_pane_not_found, a manual pane-id test | Fixed a753b76 (1.16.2) resume restores the name |
| 4 | 16 | Wrong review workflow named in the checkpoint (killed run, 3 diagnosis messages, a handoff to a flow-fixing session) | Fixed 21928c3 (1.16.4) |
| 5 | 15, 16 | Asked for the KISS pass; the rule text had been loaded (IGR-15, 13:25 UTC) | New ticket IGR-21 |
| 6 | 16 | Cut scope by hand in design (sawmills folders, a config file) | The KISS pass doing its job late; evidence for #5 |
| 7 | 16 | Relayed another session's shipped fix into the ticket's session | Not a flow fault |
| 8 | 15 | Late requirement: goal is quota (input, output, cache, both providers); later "review tokens matter more than review minutes" | Not a flow fault (intake) |
| 9 | 15 | Approval report did not say where the deliverable lives | New ticket IGR-23 |
| 10 | 15 | Lost orientation in review ("which reviews", "what is pr3", "where are we") | IGR-23 |
| 11 | 15 | Approved bot-thread replies three times | IGR-23 |
| 12 | 15, 16 | Copied the worktree to `.worktrees/back` before finish | New ticket IGR-22 (decision: finish saves `igr/`: yes) |
| 13 | 16 | /login twice, waived live acceptance | Not flow faults |

Permission prompts: only declined ones leave a trace (2 declined tool uses in the IGR-15 design session); accepted prompts are not recorded. Killed runs: 1 workflow kill, 2 interrupts. Routine messages (about 15 "ready" pings and 6 approvals) are not counted.

## Reviews and fix rounds

IGR-15 (PR 3: first push +930/-6 lines in 3 commits; final +1230 in 8 commits, 9 files; 3 fix rounds; fix churn +534/-228 after the first review, then a final cut of 157 lines):
* Round one (native Codex review, Opus `/simplify`, my pass): real: a crash on string `subagent` roles (287 real Codex sessions), the finish phase overwritten by final band updates, duplicate events across copied logs, an env path ignored; the review-minutes column added as design; lexical timestamp sort rejected on measurement; speed refactors skipped.
* Round two: my check of the round-one fix found it dropped 8 real steps (heredoc bodies); fixed, and the bot threads were answered.
* Final pass: the native review found lost parent-phase evidence in session lookups; the step parser was cut (-157 lines).

IGR-16 (PR 4: first push +127/-6 in 2 commits; final +153/-6, 3 files; 1 fix round of +28/-2):
* Round one: two real findings fixed (an instruction gap on naming the agent after launch; PR search matched tickets that only mention the key, fixed by a branch-key filter); five others dropped.
* Round two: two bot threads were real behaviours (a worktree held under another owner; a dirty tree reported as merged), left as follow-ups by the owner's KISS cut.
* Native Codex review: clean twice. `/simplify`: two runs, 3 notes, none applied.

Estimated against actual minutes (estimate log; Codex dispatches unless noted):

| Dispatch | Estimated | Actual |
|---|---|---|
| IGR-15 usage tool | 15-85 (12-16 rounds) | 16 |
| IGR-15 findings round 1 | 5-45 | 19 |
| IGR-15 round 2 | 5-45 | 15 |
| IGR-15 final | 5-35 | 7 |
| IGR-16 tk go | 10-55 | 4 |
| IGR-16 review fix | 1-20 | 3 |
| Claude review passes (IGR-15: 2 and 1; IGR-16: 2 and 2) | 1 round | 1-2 |

## Verdict per row of IGR-14's improvements table

| Row | Verdict |
|---|---|
| Fresh-session handoffs | Works: no session past 156 calls or 400K, startup 66K. Total tokens did not fall (median-length tickets). Review is unreset: IGR-20. Call 15 is above the prediction: IGR-17 |
| Handoff for the design phase | Open. Design peaked at 244K and 296K on short designs (71 and 93 calls); no evidence of need yet |
| Cheaper models for mechanical subagents and reviewers | Open (IGR-12), evidence added: lens agents run Opus/high regardless of session model |
| Trim the 66K fixed baseline | Unchanged: 64-69K in all 15 sessions; each handoff pays it again (IGR-17) |
| Fold Linear get/update pairs and worktree exit/remove into `tk` | Low value: Linear 2% and worktree setup 3% of main-thread tokens |
| Read memory and task-output files less | Low value: skill and memory reads 1.3% of main-thread tokens |
| Code search tool | Untested. The pool it could shrink is code and doc reading, 21% of main-thread tokens and 12% in subagents; test on subagents first |
| `tk wait` and `tk ref` | Stay demoted: waiting 1.7%, `tk` bookkeeping 1.1% |

## Decision: should finish save `igr/` for every ticket?

Yes. The owner copied it by hand for both tickets, and this retro could not have run without the copy. Filed as IGR-22.

## What was lost or not measured

* The worktrees of both tickets were already removed before the retro; the records survived only in the owner's copies. The IGR-16 copy was made at 19:00 IDT, three minutes after the merge, and can miss later files. The IGR-15 copy has no `corrections.md` (the checkpoint says none).
* Accepted permission prompts are not in the logs.
* Standalone Codex native reviewer: no usage file, so its tokens are missing, not zero. Codex phases read `unknown` (Codex runs no `tk step`).
* Activity classification and stage windows are not hand-checked (IGR-19).
* Ticket tags: about 28-47% of Claude calls June-September, 82% in October; phases only from Oct 5.

## Follow-ups filed

IGR-19 (extractor for review cost: agent working time and tokens per stage), IGR-20 (handoff inside review), IGR-21 (KISS-pass gate), IGR-22 (finish saves `igr/`), IGR-23 (report stops state position and deliverable place), and a comment on IGR-12 with the subagent data.
