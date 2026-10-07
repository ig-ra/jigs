---
name: agent-estimate
description: "Estimate how long a coding agent (Claude or codex) will actually take, in agent time, never human days. Use whenever giving a time estimate for agent work: how long will this take, estimate this ticket or plan, ETA, sizing a codex dispatch. Counts rounds, converts them to minutes from logged actuals in ~/.claude/agent-estimates.tsv (or $AGENT_ESTIMATES), and logs each run so estimates improve."
---

# Agent-time estimate

Agents learned their sense of time from human developers, so they say "2-3 days" for work they finish in 30 minutes. Never start from human hours or days. Count **rounds**, then let the script turn rounds into minutes from real logged runs.

`estimate.py` sits next to this file, in this skill's base directory; the commands below call it as `<skill dir>/estimate.py`.

## What one estimate covers

One **run**: one agent (Claude or codex) working on its own, from start to "done, ready for review". Human review and decisions are not agent time. Say them separately when the plan has them ("your review: about 15 minutes").

A ticket that codex implements and Claude reviews is two runs, two estimates.

## Count rounds

A **round** is one cycle: change something (edit or command), run or check it, read the result, decide.

1. **Look first.** At most 10 tool calls: the ticket, the files likely touched, existing tests. If you skip this, say so and give a wider range.
2. **Split into pieces** and count rounds per piece:

   | Piece | Rounds |
   |---|---|
   | Known pattern, one place (config, doc, a copy of an existing test) | 1-2 |
   | Moderate change with tests | 3-5 |
   | Unfamiliar code, several files, or new tests to design | 5-10 |
   | Unknown root cause, several systems, possible dead ends | 8-15 |

3. **Add the parts people forget:** reading the ticket and code, the test gate and build, review findings and their fixes, CI.
4. Give a **range** (low-high), never one number. Uncertainty widens the range; do not pad by feel.

## Convert to minutes

Never do this arithmetic yourself. Run:

```bash
python3 <skill dir>/estimate.py est <claude|codex> <low-high>
```

It uses the median minutes per round from that agent's logged runs. Codex and Claude are calibrated separately, because their pace and bias differ. With fewer than 5 logged runs it uses 3 minutes per round and widens the high end; say "uncalibrated" when it does.

Answer in one line, from the script's output:

> Agent time: 25-45 min (8-14 rounds, codex, uncalibrated n=2). Your review: about 15 min.

## Log every run

The log is `~/.claude/agent-estimates.tsv` (override with `AGENT_ESTIMATES`), one row per run, created on first use. Whoever starts the work logs it; when Claude dispatches codex, Claude logs the codex run.

- **When the run starts:** `estimate.py start <agent> <low-high> --task "<short>" --ticket <KEY> --model <model>`. It prints the estimate and an `id`. Keep the id (put it in the ticket's working notes if the session may be compacted).
- **When the run is done:** `estimate.py done <id> --wait <minutes spent waiting on a human> --note "<why it differed, if by more than half>"`.
- **Pace check:** `estimate.py` with no arguments prints minutes per round for each agent.

If you cannot write the file (for example, inside codex's sandbox), print the `start` command and let the orchestrator run it.

## Re-estimate

When something invalidates the estimate (a failing suite on main, a hidden dependency, the root cause is elsewhere), or you have spent 1.5 times the expected rounds, say so and give a new range. Never pretend the first estimate still holds.
