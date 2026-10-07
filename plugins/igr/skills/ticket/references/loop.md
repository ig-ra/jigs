# Ticket loop: from `/igr:ticket start` to `/igr:ticket finish`

The working loop for every regular ticket, in any repo. Terms from `../SKILL.md`: `REPO` (canonical checkout), `BASE` (default branch), `SLUG` (GitHub repo), `LOCAL` (the local ticket folder: `<REPO>/igr/tickets/<KEY>/` when the repo has `igr/`, else `<TMP>/igr-ticket/<key>/`). `LOCAL` holds every ticket file: models, briefs, answers, plan, findings. `/igr:ticket start` comes before this file and `/igr:ticket finish` after it (both in `../SKILL.md`). Save corrections to the loop in this file, written generically: the skill serves any repo and ticket, so rules carry no ticket-, PR- or repo-specific examples, and no names or dates (git records who changed what and when). Repo-specific practice (review bots, merge rules) lives in that repo's project memory.

Run the whole loop without being asked again, from investigation to a merge-ready PR.

**Report only at:**
- the hidden-decisions poll (Before code, step 1);
- the approval point (Before code, step 6);
- the exit (After code, "Exit");
- a disagreement with codex that three rounds did not close;
- a step that needs a human decision, including a review bot repeating an answered point.

Nothing in between unless I am blocked or something is irreversible. Reports follow `~/.claude/memory/talking-to-igor.md`: verdict first, and name the rows and points, never number them.

**Never call a review clean**, or relay "no findings", until `<LOCAL>/review-claude.md` has all three tables of After code step 1 filled. If I checked only part, say which part.

**Round trips are the cost.** Each brief → wait → re-read cycle costs 15-20 minutes of wall clock. Merge rounds that do not need to be separate; never drop an independent pass or a reviewer to do it.

**The band.** The PR's progress shows in the igr band above the prompt (`hooks/ticket-band.tsx`). It draws `<TMP>/igr-ticket/<worktree folder>/state.json`, for example `igr-ticket/saw-12203` (the worktree guard refuses writes to `<REPO>/igr/`, so this path is fixed whatever `LOCAL` is). I write that file at the first push and rewrite it at every state change in After code, so nobody has to ask where the PR is:
```json
{ "ticket": "<KEY>", "ticketUrl": "https://linear.app/<workspace>/issue/<KEY>",
  "pr": <number>, "prUrl": "<PR url>",
  "implement": { "status": "done" },
  "reviews":   { "status": "running" },
  "checks":    { "status": "todo", "note": "optional, a few words" } }
```
The band owns its three lines and their labels; the file holds only these keys. Never add rows, Before-code steps or later PRs: a ticket with several PRs shows the PR in progress, and the next PR's first push starts the file over. Statuses: `running` ⏳ (in progress or waiting), `fixing` 🔧 (codex is fixing findings), `done` ✅, `todo` ⬜ (not started), `fail` ❌ (needs a human).
- **`implement`** (Implement → rebase on main → open PR): `running` from the implementing dispatch; `done` when the PR is open on a branch rebased on the latest `BASE`.
- **`reviews`** (simplify + codex + claude → fix → rebase + re-push): `running` while the three reviews of After code step 1 run; `fixing` while codex fixes the pooled findings; `done` when the fixes are rebased and pushed, and my review covers the full final diff.
- **`checks`** (Architect + CI): `running` while waiting on CI and the review bots; `fixing` while a red check or a bot thread is being fixed; `done` when CI is green and the architect bot has approved with every thread answered.
A new push after a line is `done` (new work, a requested rebase) sets the lines it invalidates back to `running`. `/igr:ticket finish` writes the last state, all `done`, with the merge sha as the `checks` note.

## Before code

**Two independent passes, then talk.** Codex judges every problem without seeing my solution, and I judge it without seeing codex's. Comparison starts only when both solutions exist; then we decide together what to keep, do and change. This holds for the ticket design, for new work in the middle of a PR, and for review findings.

**Trivial changes: I do them myself.** A change is trivial when step 1 leaves nothing to design and nothing for codex to check: the edit follows directly from the ticket and the code, it is small, it has one sensible shape, and it hides no decision. For a trivial change I skip codex entirely (steps 2-5 and 7). I write Model A and post it as the living comment, where it is the contract (B = A). Then I make the edit, run the gates in "Rules for both halves", commit, push and open the PR myself. After code still runs in full (the three reviews, CI, the bots), and I make its fixes myself too. If I am unsure whether a change is trivial, it is not.

1. **Investigate, then the hidden decisions.** I read the code on the latest `BASE` and measure prod populations read-only. A rule that depends on data that changes over time (membership, state transitions) gets a prod measurement of that change first.
   The investigation ends with **the decisions this ticket hides**: behaviour, semantics, scope and limits that only a human can answer, and only those that would change a Mental Model row. I ask them as one poll and record the answers before codex's first pass. A code ticket that hides a product decision otherwise reopens its approved contract once per decision.
2. **Codex's independent pass, in parallel with mine.** I spawn codex (`codex-<N>`, right split, on the ticket worktree; read `driving-codex.md` and `herdr-codex.md`, next to this file, now) and brief it first. The brief gives the problem, never my solution:
   - the ticket goal and acceptance criteria, and the recorded answers;
   - the bigger goal, the project's end state, and what is scheduled for deletion;
   - facts codex cannot see (prod numbers, other repos);
   - the standing rules: KISS, no defensive code, no flags, delete orphans;
   - **smallest design first:** propose the smallest change that meets the goal; heavier designs (new tables, transactions, API fields, workflows) appear only as options with their cost;
   - write your own view and Mental Model to `<LOCAL>/codex-design.md` **before** opening `<LOCAL>/model-A.md`; if that file exists by then, compare in the same turn, otherwise stop after writing your view;
   - size the work in rounds per step (change → check → read → decide), never hours.

   While codex works, I write my suggested implementation and Mental Model A to `<LOCAL>/model-A.md`. A is never edited afterwards: it is the drift baseline. Nothing goes on the ticket yet, because codex reads ticket comments. Mental Models use the shape in `mental-model-contract.md`, next to this file: Ships, then ADD / CHANGE / REMOVE rows, then Unchanged, in 50 lines or fewer.
3. **One compare round.** If codex stopped before A existed, I send A now. The compare brief carries everything at once, per driving-codex "Partner, not push": what to keep, drop and change, with reasons; "if the two designs match, say so in one line and do not manufacture a difference"; "name what you would cut for the smallest change that still moves the goal; then say ready, or name the one gap". Every agreed change is a Mental Model row. Only a real disagreement opens another round; three rounds without converging goes back to the human as the disagreement itself.
   Method: codex works from its own plan, with no Superpowers workflows and no internal review loops (reviewing is the After-code job). **Big work** (more than about 2 agent-hours): codex writes `<LOCAL>/plan-<N>.md`, one checkbox step per commit with files, done-criteria, the gate commands and an expected size, every later correction merged into it.
4. **Drift check.** Model B is the agreed row set when codex says ready. I compare B with A row by row; any row that moved us off the goal or into overengineering goes back to codex until it is justified or reverts.
5. **Estimate.** Count the rounds, run `python3 <skill base directory>/../agent-estimate/estimate.py est codex <low-high>`, and report the script's minutes (codex's own number only if it differs, never human days).
6. **Approval.** I report the final model, what changed from A to B and why (`<LOCAL>/A-to-B.md`, not on the ticket), the method and the estimate, and what needs approval. Once approved, B is the contract, and I post the living "Suggested implementation" comment on the ticket: the full suggestion, ending with Model B. Each later approved change updates that comment so it always matches what the PR ships.
   For a **decide** ticket the loop ends here: I record the decision in the ticket's Answer and living comment, open or update the implementation tickets, and run `/igr:ticket finish`.
7. **Fresh session, then implement.** Send `/clear` to codex. Its first prompt points only to the written contract (ticket, acceptance criteria, living comment, plan file for big work) and the stop conditions: "everything there is decided; do not reopen it; if something is missing, ask". Its first answer is a short read-back (scope, steps, out of scope) before any code; a gap means the contract is incomplete, so fix the contract, not the chat. Then codex implements, commits, pushes and opens the PR (Conventional Commit title with the ticket key) without waiting for my review.
   **Status:** the first push of the ticket's branch to GitHub, by codex or by me, moves the ticket to In Review (`save_issue(KEY, state: "In Review")`) as soon as I see it (watcher fire or codex's report). `/igr:ticket start` already set In Progress.
   On dispatch: `estimate.py start codex <low-high> --task "<short>" --ticket <KEY> --model <model>`, id into `<LOCAL>/estimate-ids.md`. One id per implementing dispatch; question rounds are not logged.

## After code

**Codex owns every edit**, except on a trivial change (Before code, "Trivial changes"), where I own every edit. Otherwise I do not patch the branch unless told to make a specific edit myself.

**One PR at a time.** "After code" runs per PR. When a ticket ships several PRs, codex stays on the open PR through review, fixes, CI and the review bots until it merges; the next PR starts only after that. Exception: once the open PR is green and in the merge queue, a next PR that touches unrelated files starts at once, with a fresh codex on its own worktree cut from the latest default branch; do not ask.

1. **Three independent reviews, in parallel, once per PR:**
   - an Opus subagent runs `/simplify`, report-only (medium effort for an additive change off production paths, high for a production path, never xhigh);
   - the Codex plugin's native reviewer (the same built-in reviewer as codex's `/review`), run from my session as a background shell command in the PR's clean worktree: `node ~/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs review --wait --base <base>`, stdout to `<LOCAL>/review-<PR>.md`. Always pass `--base`: without it the plugin reviews uncommitted changes when the tree is dirty, and otherwise diffs against the local default branch, which can be stale. `<base>` is `origin/<default branch>`, or the parent PR's tip for a stacked PR. It is a fresh codex process, so it reads as a reviewer, and the implementing codex keeps its context. It takes no custom text and does not know the contract, so findings that match an accepted trade-off are dropped at verification (step 2). For a design challenge, `adversarial-review` (same script, same `--base`) also takes focus text;
   - **My review: gaps, drift, overengineering.** I read every hunk of the diff, tests included, for every commit since the base, and write `<LOCAL>/review-claude.md` with three tables. An empty cell means the review is not done:
     - **Model B → diff:** each B row → the hunk that implements it; each hunk → its row. A hunk with no row is drift or overengineering; a row with no hunk is a gap.
     - **Ticket → diff:** each acceptance criterion and each "What will change" item → the test or hunk that proves it, or "uncovered".
     - **Deleted or changed tests:** each one → every behaviour its assertions proved → where that behaviour is still tested, or "lost" with a prod measurement of whether the state occurs. A test removed as "only about X" often also covers a guard that stays.
2. **One fix round per findings batch.** I verify every finding myself by reading the code, using driving-codex "Before accepting a finding" (can the state occur, which regime did I measure, what actually happens). One brief to the implementing codex carries the pooled findings, each as "agree, disagree, or better?", with "if you agree, fix and push; if not, stop and write why"; "fix the agreed ones and list the disputed ones"; and "rebase on the latest `BASE` before the push". A later rebase happens only on a conflict or a merge-queue rejection.
3. **Per commit:** the diff against its plan step and done-criteria, source, tests mapped to acceptance criteria, docs, and hosted CI on that head. Findings go back as questions; once agreed, codex fixes.
4. **Review bots.** When the repo has a review bot, follow its project memory. Check every review thread (all bots, `reviewThreads` via GraphQL, not one review) at every push, without waiting for anyone to point at them. A reply that needs no code change (evidence, or a point the contract already decided) I verify and post myself while codex works; I do not hold it for codex's round. Verify each finding myself and ask codex to verify it independently; agree, fix, reply with evidence, resolve.

**When the reviews rerun.** Step 1 runs once, after the first implementation of a PR. At the end, when findings are fixed and the bots agree, I decide whether the diff since the first review is substantial; only if it is, step 1 runs once more on that diff.

**Exit.** The loop ends when CI is green on the PR head, every bot thread is answered with evidence and resolved, and nothing is waiting on codex. When an implementing run's report arrives, close its timer: `estimate.py done <id> --wait <minutes waiting on a human> --note "<why it differed, if by more than half>"`. Then I refresh the "Model B → diff" table of `<LOCAL>/review-claude.md` on the final diff and report once: the PR is ready for approval, plus any drift from contract B that table shows. Do not rewrite the contract to match the code.

## Rules for both halves

**Hold the bigger goal in every round.** Codex reasons from the code in front of it; its comments pull toward extra guards, compatibility paths and tests for states that cannot occur. Before accepting any addition, ask whether it serves the ticket's goal and the project's end state, and whether it is the simplest shape that does. The goal also adds scope: when the project replaces a system, legacy code and tests the change makes dead go in the same change.

**Gates.** Before each commit, once per commit (not after each edit), codex runs only the focused tests for what it changed (including the database or integration test files it touched) and the build. Never locally: the full unit suite, the full database or integration suite, golden or snapshot runs, "affected" sweeps, or a combined pre-PR gate. Hosted CI runs everything. A gate counts as passed only with its own output line quoted. Every brief I send repeats this gate list. The focused gate can be waived for a PR: then codex commits and pushes without running anything, the brief quotes the waiver, and hosted CI is the only gate. Treat that as approval to implement at once; the agreed model still goes on the ticket first.

**CI.** Within a plan, codex goes straight on to the next step after a push and ends its turn at the end of the batch; it never polls CI. I watch hosted CI and the bots on every head the watcher reports, and bring a red result as a mid-round steer or the next prompt. Hosted red means the PR is not done.

**Plan-of-record runs.**
- Codex ticks a step in the plan file when its commit lands and logs mid-work decisions there.
- A correction, steer, stop instruction or priority change goes into the plan file as a step or constraint, not only into chat: a compaction can drop a chat-only instruction.
- **Pending a human decision.** Open questions taken to a human are listed in the plan file (or at the end of the living comment when there is no plan file). Codex never classifies them itself until the decision is recorded.
- **Compaction:** codex compacts itself. The plan file's first line is "After any compaction, re-read this file and the ticket's living comment, then continue from the first unchecked step." When codex's context jumps back up, I send that same prompt once.
- **Late plan:** if a big run has no plan file and codex's context drops below about 30%, I ask for it at the next stop point, before any more code.
- **Scope fence.** Every plan file has a "Not in scope → Follow-ups" section and this Global Constraint: "a finding outside the contract, from any reviewer or test, goes to Follow-ups, never into code". When the feature is off in prod, the plan also says "no new features or hardening". Codex brings the Follow-ups list at each step commit; they become tickets only after approval.
- **Time.** A step with no commit after 1.5 times its expected time, or an uncommitted diff past about twice its expected size, means I check the diff against the plan step; growth beyond the contract pauses codex and goes to a human with its cause. At 1.5 times the ticket's high estimate, I re-estimate from the remaining steps and report it in one line.
- **Watcher.** For every implementing run, keep `<skill base directory>/scripts/watch-codex.sh <codex-name> <worktree> <max-diff-lines>` running in the background. It exits with one line when codex compacts, commits, stops or its uncommitted source diff passes the threshold. On each exit: act (re-read prompt, step check, report or pause), then re-arm it.

**Why rounds and the script:** agent hour estimates are human-calibrated and run several times too high; logged actuals are not.

**New work goes back to "Before code".** A new feature or behaviour change during "After code", even one already decided, waits until the current batch is pushed. Then it goes through Before code steps 2-6 with the same two independent passes: I write my view, codex writes its own before reading mine, we compare and agree (new Mental Model rows), approval is needed if the contract changed beyond that decision, codex implements. The new commit gets the per-commit check and the bots; the reviews follow the rerun rule above.

See also "Steer only what changes the current batch" in `driving-codex.md`.

**Why:** the goal is a simple plan that moves the bigger goal, not a plan that only survived review, and every outside finding checked by both codex and me before anything changes.

Related: `mental-model-contract.md`, `driving-codex.md` and `herdr-codex.md` (next to this file); `~/.claude/memory/talking-to-igor.md`; project memory `review-src-tests-docs.md`, `kiss-recommendations.md`, `kiss-is-boundary-not-line-count.md`.
