# Herdr file handoff: send and ping

Status: parked implementation, ready for Igor to integrate. Nothing in the active
skills, references, hooks or toolbox loads it. `tk` now contains ticket operations
only; pane-to-pane messaging belongs in the Herdr layer.

## Problem and measured evidence

Owner-supplied analysis, week 2026-10-02 through 2026-10-09,
`handoff-findings.md` section 2. These are aggregate counts, not raw transcripts:

- Codex to Claude: 512 `herdr agent prompt` calls; 151 failed, about 30%.
  Reported categories: 66 socket sandbox failures (`Operation not permitted`),
  30 `unknown option` failures from splitting an unquoted `<file> ready` into
  separate arguments, 16 rejected operations, 11 `agent_blocked`, and
  7 `agent_not_found` after names were lost on restart. Those categories account
  for 130 failures; the supplied list does not classify the other 21.
- Claude: 177 unprompted Codex pane polls, 58 delivery checks within two minutes
  of its own send, and 94 separately armed `until [ -s answer ]` waits.
- Herdr lifecycle waits return on the first settled idle/done/blocked state.
  Implement turns can flicker between working and idle. A lifecycle event alone
  does not establish that the requested answer exists or that the turn finished.

One file-based send command should replace dispatch plus delivery checks plus
separate answer waits. One file-based ping command should construct the reply
text itself, preserving it as a single argument to Herdr.

## Parked files and how to run them

All three files sit beside this handoff:

- [wf-herdr-handoff.py](wf-herdr-handoff.py): executable Python 3, standard library
  only, standalone; imports neither `tk` nor the existing Herdr toolbox.
- [test_wf_herdr_handoff.py](test_wf_herdr_handoff.py): the six preserved handoff
  regressions, synthetic inputs and mocked Herdr responses.
- This document: requirements and integration boundary, not active skill wiring.

From the repository root, for manual use inside Herdr:

```text
plugins/igr/docs/plans/wf-herdr-handoff.py send codex-demo /tmp/brief.md /tmp/answer.md
plugins/igr/docs/plans/wf-herdr-handoff.py ping /tmp/answer.md --to claude-demo
python3 -B -m unittest discover -s plugins/igr/docs/plans -p test_wf_herdr_handoff.py
```

Global `--cwd PATH` and `--json` precede the command. `send` accepts `--timeout`
(default 1800 seconds) and `--interval` (default 2 seconds). `ping --to` accepts
a live agent name or pane ID. Without it, the preserved lookup uses the worktree
folder name, then a unique Claude at exactly the supplied cwd. Names lost after
a restart still require repair or an explicit live target; no guessed recipient.

Exit codes: 0 for READY/SENT/ALREADY_SENT, 1 for STOPPED, 2 for usage/input error,
3 for prerequisite error, 124 for TIMEOUT. Text output is one flushed result line;
`--json` emits structured results. The preserved ping receipts live under
`$TMPDIR/igr-ticket/` (fallback `/tmp/igr-ticket/`), with locking and atomic writes.
This move deliberately retains that storage location.

## Properties to preserve when integrating

1. **Wait on the answer file.** Capture its pre-send fingerprint (mtime, size,
   content hash). READY requires a fresh, nonempty answer and two consecutive
   idle/done observations. An old answer, unknown state or missing file cannot
   establish completion. Use durable brief/answer paths supplied by the caller.
2. **Handle idle flicker.** With no fresh answer, STOPPED requires 30 seconds
   continuously idle/done, plus at least two observations. Working or unknown
   resets that grace. A fresh answer can become READY without waiting 30 seconds.
   Blocked returns STOPPED immediately, without submitting dialog input.
3. **Distinguish timeout sources.** The initial `agent prompt --wait` is bounded
   to at most 10 seconds. Only Herdr's structured `error.code == "timeout"`
   permits continuing to wait for the answer; it does not cause a second prompt.
   A local process timeout, another error code, or the word "timeout" in a target
   name does not satisfy that condition. The overall wait has its own deadline.
4. **One fixed-argv command.** The caller supplies target and file paths, never
   hand-builds or quotes the reply text. The script calls Herdr with an argv list,
   no shell: `<absolute-file> ready` is one argument, including literal spaces,
   backticks or dollar signs in the path. `send` likewise constructs the brief
   and answer pointer internally. Do not convert either to shell interpolation.
5. **Ping only the resolved Claude.** Verify agent kind and refuse blocked
   recipients. Deduplicate successful delivery by resolved path, content and
   recipient pane/session identity. Write the receipt only after successful
   submission. Do not bypass refusal with raw terminal keys, or blindly retry a
   prompt whose outcome is uncertain. Delivery does not prove recipient reading.

Do not substitute `completion_seq` or bare `agent wait` for these properties
without a new live test of mid-turn idle transitions. The existing fake-clock
regressions protect continuous idle grace, fresh/stale files, structured error
handling, literal arguments, blocked refusal and successful-delivery deduplication.

## Likely integration home

Use [skills/herdr-workflow/scripts/wf-herdr.py](../../skills/herdr-workflow/scripts/wf-herdr.py).
It already owns `split`, `run`, `send-keys`, `wait-output`, `subscribe` and other
Herdr plumbing. Add the handoff commands there, or keep a helper beside that
toolbox if embedding the wait/receipt logic would obscure its one-shot commands.
The parked standalone code is the transplant source, not a second active API.

The current toolbox uses direct socket JSON-RPC. Its `rpc()` turns server errors
into a message and exits; a transplant using that transport must retain structured
error codes so a server timeout stays distinguishable from other failures. Keeping
the existing CLI transport initially avoids changing the proven wait semantics.

[skills/ticket/references/herdr-codex.md](../../skills/ticket/references/herdr-codex.md),
"Briefs and replies", currently tells Codex to hand-type
`herdr agent prompt <pane-name> '<file> ready'`. When Igor activates the new command,
replace that line with the file-based ping invocation and update "Waiting" to use
the answer-file contract. Neither reference nor any skill is changed in this split.

Igor's open decisions:

- Approve and install a Codex allow rule for the final ping entry point. A wrapper
  fixes argument construction; it does not remove the sandbox's socket restriction.
  Choose the rule after the final command path is settled. No rule is installed here.
- Decide whether `herdr-codex.md` moves to `herdr-workflow`, leaving ticket-specific
  brief storage/lifecycle guidance or a pointer with the ticket skill.

## Evidence and limits

Earlier real-agent acceptance reported **READY** for send and **SENT tk-tools**
for ping. Both fix-round reports were delivered to the owner. The latest fix-round
notification used direct `herdr agent prompt`; that is transport evidence, not a
new acceptance run of this parked script. Historical acceptance remains the live
proof for the preserved send/ping implementation.

This split ran 23 remaining ticket tests and all six parked handoff tests, compiled
all four Python files, and exercised executable help plus a JSON input-error path
from outside the repository. AST comparison verified the surviving ticket functions,
classes and tests are unchanged, parser changes only remove send/ping, and parked
send/ping/fingerprint bodies retain their behavior (only the error class is renamed).

Not newly exercised live: successful send/ping through the parked entry point,
full-duration idle flicker, restart/name loss, post-move pane resolution, or an allow
rule in the Codex sandbox. Final notification uses the owner's explicit Herdr
command. No private repository recordings, IDs, paths or comment bodies ship here.
No active skill/reference wiring, sandbox configuration, GitHub operation or push.
