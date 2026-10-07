# Driving a codex subagent

Default shape for any non-trivial task. Short beats long — most of my long briefs were context codex
could read itself, plus mechanism I should not have been choosing. Long briefs cause the damage they
try to prevent: a 101-line brief with five claims and an evidence block made codex spend about 3M
tokens re-measuring production instead of reading three lines of code, when the right brief was about
15 lines (the property, the evidence anchor, the stop condition).

```
Own the method. Use no Superpowers workflows in this run; work from your own plan. Do not pause for workflow approval unless a real product decision is missing. Verification appropriate to risk remains required.

<the constraint, and why it exists>
<evidence: file:line or pasted output — never just my conclusion>
Verify this before implementing. Approve it or propose better; I want the reasoning either way.
If it cannot be done as stated, STOP and tell me — that is the finding, not something to work around.
```

**Four rules, in priority order.**

1. **State the property, never the mechanism.** What must be true, and why. I have blocked codex
   outright by naming an impossible mechanism when the property behind it was easy. Catching myself
   writing a procedure means I am doing its job badly.

   **This applies to every message, not the first.** A correction, a disagreement, a request to cut
   scope — each is a new brief and gets the same shape. Familiarity with the problem is not a reason
   to switch to instructions; it is when I am most likely to. The test: *if my message names what to
   change rather than what must be true, I am directing.*
2. **Verify before implement, always.** One round trip, never wasted. It catches *my* wrong premises
   before they become its code.
3. **Give evidence, not conclusions.** The asymmetry is consistent: instructions get compliance
   including my bugs; problem-plus-hypothesis gets something better than mine.

   **A conclusion I derived is more dangerous than one I read**, because it arrives already feeling
   verified. Hand over the reasoning and let it refute; a looked-up fact gets a citation, a reasoned
   one gets labelled as mine.
4. **Ask for honest partials.** "Say plainly if a check was not exercised." Produces accurate
   proven/not-proven reporting even when it makes its own work look incomplete.

## Partner, not push

Codex is a partner, not a subordinate: do not push codex or orchestrate it. Communicate with it on everything, reach common and mutual agreement, then let codex implement and push.

- **Every follow-up goes to it as a question:** review findings, CI failures, outside-review suggestions, doc edits. It agrees, disagrees with reasons, or proposes something better. Only after mutual agreement does codex implement, commit and push, in one go. Codex owns every edit; I patch only what I am told to. Exception: a trivial ticket change, which I make myself (`loop.md`, "Trivial changes").
- **One brief per round:** each point with my view and its evidence, ending "agree, disagree, or better?". To save a round trip I may add "if you agree, implement and push; if not, stop and write why".
- **If I already sent an instruction,** follow it with `STEER, mid-round —`, turning it back into a proposal and holding the push.
- **Relay codex's conclusions in its own words.**

**Why:** my CI-fix brief said "Push the fix" and "Please run every real-PG file" before we had agreed. Rounds run as questions found real improvements and kept good code I would have changed.

## Before accepting a finding

A mechanism being *correct* is not the same as it being *reachable*, or *harmful*. Three questions,
cheapest first. Each has cost me a day when skipped.

**1. Can the state occur?** One query usually settles it. One day produced five findings where the
mechanism was real and the population empty — a guard for rows the write path refuses, an
empty-string key no producer sends, an over-cap aggregate nothing approaches, a scope overflow two
orders of magnitude inside the real bound. Ask the real bound before calling something an overflow; a
fixture limit of 1 proves nothing about a production limit of 500. "Fails closed elsewhere" is itself
evidence the state is absent, so go count the history. Then say which it is: absent-and-unreachable
justifies deleting the branch, absent-but-creatable justifies keeping it with the measurement and the
revisit trigger written down.

**2. Which regime did I measure?** The trap on the other side, and it cost more than the rule saved.
I measured a field combination over a recent window, got zero, and declined — but the zero was an
artifact of the *current* design, records too short-lived to accumulate it, and the change removed
exactly that. Over full history: dozens of keys. If a change removes a bound, extends a lifetime, or
merges populations, today's distribution describes the old world only. Pick the window the new regime
implies, and label which regime a number covers — "zero in 7 days" and "zero ever" are different
claims, and I published the first as the second.

**3. If it does occur, what actually happens?** The one I miss most. I verified a mechanism — a Case
that could not be loaded — and inherited the reviewer's consequence, "duplicate Cases", without
testing it. The agent path already covered that case; the true cost was one model call. I escalated it
as a blocker and a schema migration got scoped to buy an optimization. Ask what already handles this,
and what breaks if the code in question never runs.

**A finding that cites a written rule isn't answered by population.** "Can it occur?" refutes a
speculative risk, not a documented standard. Comply with the cheapest shape the rule accepts.

**A fix much larger than expected is evidence against the premise, not just a bigger job.** When
codex said the honest minimum was a migration, that was the moment to re-examine the requirement. I
accepted the estimate instead.

**When a measurement disagrees with my model, find the mechanism before narrating past it.** I had
the story that N Leads in a Case each arm their own triage dispatch, so a Case gets judged N times
concurrently. The prod query said zero concurrent surplus. Instead of asking what was preventing it I
relabelled my own claim — "sequential, not concurrent" — and kept the story. The preventer was one hop
further down the path I had already flagged as untraced: the work-plane task keys on the Case, not the
Lead, so the second dispatch deduplicates. That one hop was the answer to the whole ticket. **A number
that does not fit is a pointer to a mechanism I have not read yet; an explanation that makes it fit
without naming that mechanism is a rationalization.** Corollary: a component I labelled "not traced"
is not a footnote — it is the first place to look when the model breaks.

**Check whether a fallback feeds the failure it handles.** A guard that mints a new object on refusal
can raise the very number it measures, so one refusal becomes permanent. Trace the loop before
choosing the fallback.

**Withdraw loudly.** I had resolved the thread and posted a table of zeros; the correction needed a
new comment saying the table was wrong, and the thread reopened. A wrong decline left on the record
teaches the next reader the wrong lesson.

**Deleting an impossible-state test can take a reachable guard with it.** Fixtures often assert two
things — the impossible arrangement, and a property that still holds. Ask what else the test covered.

## Hardening a ticket before there is a plan

Different job: the thing under test is **my spec**. Cheapest round I run, and it has never failed to
find something.

```
What I believe, as claims to test. Treat the evidence as a pointer, not proof — I may have read it wrong.
1. <claim> — <file:line>. If true, I predict <the concrete failure>.
Verify each independently. Tell me plainly which are wrong and where I misread.
```

- **Claims, not statements.** "I believe X, here is the line, correct me" gets disagreement; "X is
  true" gets elaboration on X.
- **Give the predicted failure, not just the fact.** Then it can refute the *consequence* — the fact
  is usually right and the consequence wrong. That is the shape of most of my errors.
- **Say where my conclusion would break and ask it to hunt there** — a second candidate source, a
  bypass, an operator path. Produces the findings I did not know to ask for.
- **Name stop conditions, and scope them.** Stop when a gate reveals a *design* problem; fix and
  carry on for its own typo or type error. Left ambiguous, it halted on a missing brace.
- **When a measurement supports me, hand over the number AND the worlds it is consistent with.**
  "Does this confirm X" invites agreement; "which of these two does this evidence distinguish" gets
  the refutation. Zero lock waits meant either the guards skipped the requests or the locks were
  granted uncontended — I asked it that way once and got a flat, correct no. Three times that same
  number was really an unrelated abort happening earlier.
- **Ask it to attack my proposed fix**, not just report the defect. It breaks mine with real reasons
  often enough that shipping my first fix would have been wrong.
- **Its blockers are reasoned from code, which cannot see a product decision.** Ask whether the answer
  is a decision — scope I will lose, a population being deleted, a degradation the owner accepts. Half
  the hard blocks dissolve that way; none dissolve by arguing.
- **Withdraw a stop condition in those words** once a decision answers it, or it keeps deliberating
  over settled ground and reports it unresolved.

## The default loop

Run this without being asked. Report once, at the end. Nobody should have to say "now ask it
whether it's ready" — that is me making the human run the loop. One ticket once took fifteen
messages to get right; nine of them drove rounds I should have driven myself.

**0. Understand it myself first.** Read the code before writing any brief. I cannot partner on a
mechanism I have only grepped. If I cannot state how the thing works in my own words, I am not ready
to ask codex anything.

**1. Two independent passes, then converge.** Codex judges the problem without
seeing my solution: the brief gives the goal, context, decisions and facts, never my design. I write
my own solution down first, independently. Communication starts only when both exist: share mine,
compare the two, and decide together what to keep, do and change. *"If they are the same, say so in
one line and do not manufacture a difference."* Handing it my design to attack is a review
relationship, not a partnership, and it anchors its answer on mine. Codex reads Linear comments, so
nothing of my solution goes on the ticket before its pass. The same applies to new work in the
middle of a PR and to review findings.

**Rounds are free; coming back to the human is not.** Loop as many times as the work needs and report
once, at the end. What makes a round legitimate is that *the last answer changed the question* — new
evidence, a real disagreement, a correction that opened something. What makes it waste is asking the
same question in different words, fishing for confirmation, or starting a round because I did not
know what to do next. If I cannot say in one line what this round closes that the last one did not,
I do not have a round, I have a stall.

**Three rounds without convergence means it is not a technical question.** Codex reasons from code
and cannot see a product decision. Stop, and bring the human the disagreement itself — "we disagree on X,
its reason is Y, mine is Z, this needs your call" — not a fourth round. Half the hard blocks dissolve
that way; none dissolve by arguing.

**2. Cut — always, before anything is written down.** By now the spec is bigger than the job, and
every addition was individually right, which is how it got that way. Ask which parts it would cut for
the smallest change that still moves the property. Name cut candidates without arguing for them —
arguing tells it the answer. It once cut a ticket by two thirds this way, and withdrew one of its own
requirements as overreach.

**3. Ready? — one explicit question, always asked.** "Is it a good idea" and "can someone open the
branch tomorrow without stopping to ask" are different questions. I have skipped the second one.

**4. Write it down in its words.** Ask for the agreement in its wording and carry that. My paraphrase
drifts toward what I already believed.

**Exit:** when it says ready, or names a gap that needs a human. Not before, not after.

### Two things that keep costing the human a message

**No intermediate reports.** Nothing between "starting" and "settled" unless I am blocked or
something is irreversible. It is the largest single source of noise.

**Never open a brief with what I got wrong.** "Withdraw loudly" is about the record — the ticket, the
thread, what the next reader finds. In a brief it is noise, and it primes agreement: an agent told
three times that I was wrong will not tell me I am wrong a fourth.

## Sizing, method, gates

**Say the weight class, not the method.** Codex defaults to heavy process — multi-agent flows with
per-task reports — and will spend it on a two-line change, burning the context it needs to finish.

- *"Small: one new file, additive, nothing on a production path. Focused test plus the gate — skip
  the review flow."*
- *"Heavy: modifies code serving production traffic. Full rigor and an adversarial pass."*

**Make the method choice explicit.** The default prompt prefix asks Codex to choose its workflow and
explain why; do not prescribe one here.

**Say which gates.** The ticket loop's gate rule wins: focused tests for what changed (including the
database or integration test files touched) plus the build, once per commit. Hosted CI runs every
full suite; codex never runs them locally and never polls CI.

**Ask for its estimate in rounds, and log the run myself.** When codex sends its plan or
verification reply, ask how many rounds the work will take (low-high, per the `agent-estimate`
skill), never hours or days. I run `estimate.py start codex <low-high> ...` when I send the go and
`estimate.py done <id>` when it reports done, because its sandbox cannot write the log.

**Name a past mistake to stop its repeat.** "Do not enumerate cases in an allowlist — that already
cost two rounds." Ends whack-a-mole immediately.

**Scope "stop if the diff grows" to design problems.** Mechanical churn that follows from the change
is expected. Say so, or it stops on it.

**Under-specifying what matters is as bad as over-specifying mechanism.** Before sending, ask what a
fast literal reading would let it do that I would reject.

**Quote the owner's ask verbatim in every brief, and check the result against the quote, not against
my brief.** My paraphrase drifts — I have sent codex something wider than asked and only the owner
noticed. Codex cannot catch what it never saw.

**Quote the task, not the orchestration.** The owner's message usually carries both: what must be built, and
how I should arrange agents to build it — which worktree, which pane, which model, which agent to
spawn. Only the first belongs in a brief. Handing over the second tells the implementor it is the
orchestrator. One agent read "create another down split, spawn there codex-x, pass it the ticket" as its own
assignment, built a tmux session and tried to delegate downward; it read my words correctly, they were
the wrong words. When both live in one sentence, quote the clause naming the work and say in my own
voice that the rest was mine. If the whole message is orchestration, there is no verbatim to pass and
the ticket is the brief.

## "Keep it simple" needs a test attached

Not actionable alone — it cannot tell load-bearing from ceremony without knowing the end state.

- **Judge against the end state, not this ticket.** Name where the whole effort is going. That is what
  stops overengineering and defensive code at the source: it can then see that a guard protects
  something being deleted two tickets out, or that a seam it was about to generalize is about to be
  replaced. Far more reliable than enumerating what not to build.
- **Name what is scheduled for deletion** — do not invest in it, migrate it, or test it.
- **Name what is out of scope**, so it does not build compensation for it.
- **Give a checkable direction**: "net-negative lines on the hot path." Then a net-positive diff is a
  question I can ask.
- **Name the one place rigor IS wanted**, or "simple" reads as permission to skip the part most likely
  to bite.
- **Invite it to call the brief overengineered.** My briefs grow across rounds and some of it is
  belt-and-braces I talked myself into. That is a finding, not a deviation.

## Relaying its findings

- **Read the code before repeating any of them.** Its facts hold; its phrasing is loose. "Eviction
  drops timestamps" meant "drops the rows carrying them" — same evidence, very different conversation
  with the owner.
- **Read the whole report, not the running commentary.** It narrates provisional verdicts and reverses
  them after deeper tracing; the last one is the considered one.
- **Its corrections to me are the deliverable.** Record them in the ticket, not in chat. Half of what I
  learn per round is that one of my own lists was incomplete.
- **When it names a class, enumerate the members by tool before anyone ships the first fix.** It
  said "a finding is an instance, not the bug" about our own PR and was right; then a production
  incident hit six walls of one class — a restricted login lacking authority — and five guard PRs
  shipped one wall at a time. One query against the catalog produced the whole closure (36 functions,
  14 tables) in a minute. The enumeration is the deliverable; the first instance is not.
- **Check every "covered elsewhere" claim.** Open the file and line. One held exactly as described;
  one rested on a construct that did not exist.

## Verify state; never trust a report of it

Four faces of one failure.

- **Which head am I reviewing?** A worktree can be reset, a branch rebased, a PR head sit behind
  local. Check the local log, the PR head SHA, and whether they match. If a finding looks stale,
  suspect the head before the reviewer.
- **Git state.** Its account of its own commits and pushes has been wrong in both directions. Ask git.
- **Did CI actually run?** A pushed head had zero Actions runs while review apps still posted. "Checks
  are showing" is not "the suite ran."
- **Never call a gate green before it executed**, mine or its. Quote the gate's own words.

## Fresh sessions and steering

A cleared session re-litigates settled ground from a bare ticket link. Give it the **architecture** and
where this piece sits, then point at the durable brief rather than pasting it.

**It reaches Linear itself.** Name the tickets and say "description **plus all comments**"; when two
comments disagree, say which one wins. Left implicit it reads the description alone, and the decisions
live in the comments.

**Warn it about the consequence that will look like a bug.** Any intermediate step leaves something
odd — a call with one legal answer, a guard with nothing to guard. Say which, and that it is
deliberate.

**Steering mid-run works.** A prompt sent while it is working is folded in. Label it `STEER,
mid-round — <what changed>, applies to <which section>`, then restate what still stands, or it treats
the steer as replacing the whole task.

**Steer only what changes the current batch.** Steer mid-round when the information changes what it is
building right now: a premise of the agreed batch is wrong, I correct my own instruction, or a line
goes stale because of exactly this change (send that one as a question it can decline). **Wait** when
it is new work, even if the owner already decided it: a new behaviour, an outside reviewer's finding
unrelated to the batch, or anything that needs it to verify a premise. After the batch is pushed, the
new item gets its own round: the decision verbatim, the evidence, "agree, disagree, or better?", and
"do not implement until we agree". Mixing a new behaviour into an unrelated batch skips that
discussion and blurs what the commit contains (an owner decision steered into a /simplify fix batch
was caught this way).

## Mechanical traps

- **Generated files.** If a file says GENERATED, regenerate it — editing the source alone fails a
  parity gate. Cost one red CI round.
- **Replace versus extend.** When it edits a lookup table, say which you mean. Its "fix" to a
  test-selection map replaced an entry and silently dropped an existing test from coverage.
- **It commits and opens PRs unless told not to.** Say so when it matters.
- **`git diff main..HEAD` shows phantom deletions** once main moves. Use `git merge-base` first.
- **Arm the wait in a background shell right after every prompt.** Without it there is no notification
  and I sit polling or miss the reply.
- **In a file that moves, cite the statement, not the line.** Give the anchor text or the object
  name and let it locate them. My line numbers went stale four times in one day on one migration
  file, and one stale citation had me reporting that the migration died before our fix when it had
  already run it — I relayed that twice before codex caught it.
- **No backticks in a prompt passed through a shell** — they execute as command substitution and
  silently delete words from the brief.
- **Never send keys while waiting.** A wait that presses keys can interrupt a turn mid-answer. Waits
  only read.
