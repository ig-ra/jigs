#!/usr/bin/env bash
# Watch a codex agent during an implementing run. Exits with one line when it
# compacts, commits, stops, or its uncommitted source diff grows past a threshold.
# Usage: watch-codex.sh <codex-name> <worktree> [max-diff-lines (default 1500)]
NAME=${1:?codex agent name, e.g. codex-<N>}
WT=${2:?worktree path}
MAX=${3:-1500}
ctx_of() { herdr agent read "$NAME" 2>/dev/null | grep -o 'Context [0-9]*% left' | tail -1 | grep -o '[0-9]*'; }
if [ -d "$WT/src" ] || [ -d "$WT/scripts" ]; then PATHS="src scripts"; else PATHS="."; fi
diff_lines() { git -C "$WT" diff --numstat -- $PATHS | awk '{s+=$1+$2} END {print s+0}'; }
prev_ctx=$(ctx_of)
prev_head=$(git -C "$WT" rev-parse HEAD)
while true; do
  sleep 20
  ctx=$(ctx_of)
  head=$(git -C "$WT" rev-parse HEAD)
  status=$(herdr agent get "$NAME" 2>/dev/null | grep -o '"agent_status":"[a-z]*"' | head -1 | cut -d'"' -f4)
  lines=$(diff_lines)
  if [ -n "$ctx" ] && [ -n "$prev_ctx" ] && [ "$ctx" -gt $((prev_ctx + 15)) ]; then
    echo "COMPACTED: context ${prev_ctx}% -> ${ctx}% at $(date +%H:%M)"; exit 0
  fi
  # A rebase moves HEAD many times; only a finished rebase or a real commit counts.
  rebasing=
  for d in rebase-merge rebase-apply; do
    [ -d "$(git -C "$WT" rev-parse --git-path "$d")" ] && rebasing=1
  done
  if [ -n "$rebasing" ]; then prev_head=$head; fi
  if [ -z "$rebasing" ] && [ "$head" != "$prev_head" ]; then
    echo "COMMIT: $(git -C "$WT" log --oneline -1) at $(date +%H:%M)"; exit 0
  fi
  # Status flickers between turns; report a stop only when it holds for two checks in a row.
  if [ "$status" = "idle" ] || [ "$status" = "done" ] || [ "$status" = "blocked" ]; then
    if [ -n "$stopped_once" ]; then
      echo "STOPPED: status=$status context=${ctx}% at $(date +%H:%M)"; exit 0
    fi
    stopped_once=1
  else
    stopped_once=
  fi
  if [ "$lines" -gt "$MAX" ]; then
    echo "GROWTH: uncommitted src+scripts diff ${lines} lines > ${MAX} at $(date +%H:%M)"; exit 0
  fi
  [ -n "$ctx" ] && prev_ctx=$ctx
done
