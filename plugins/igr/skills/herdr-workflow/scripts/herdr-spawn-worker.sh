#!/usr/bin/env bash
# herdr-spawn-worker.sh — spawn a herdr worker pane running claude in a git worktree whose branch
# name YOU choose (no forced `worktree-` prefix). Run from the orchestrator pane's shell.
#
# Usage:
#   herdr-spawn-worker.sh <workspace-id> <tab-label> <worktree-dir> <branch> [base-ref]
#
#   <workspace-id>   herdr workspace id (e.g. w65421391321653) — `herdr pane list` shows it.
#   <tab-label>      short tab/session name, <=20 chars, no ticket# (e.g. r2a-storage).
#   <worktree-dir>   short dir name under <repo>/.worktrees/ (<25 chars, include the ticket id, e.g. saw-8194-storage).
#   <branch>         FULL branch name you want — match the Linear gitBranchName form, e.g. igor/saw-8194-needle-storage.
#                    No forced prefix. Include the saw-XXXX id so Linear auto-links the PR (substring match).
#   [base-ref]       branch/ref to base off (default origin/main). Pass a PARENT branch to STACK directly —
#                    `git worktree add -b <branch> <dir> <parent>` bases on it; no reset --hard needed.
#
#   REPO_ROOT env overrides the repo root (default = the main worktree from `git worktree list`).
#
# We CREATE-OR-REUSE the worktree+branch (reuse in place if the dir is already a worktree on <branch>,
# add from an existing branch, else `git worktree add -b`), then launch PLAIN `claude` (NOT
# `claude --worktree`) so we own the branch name + base. (`claude --worktree NAME` would force a
# `worktree-<NAME>` branch off main — that prefix is its default, not a git requirement, and gives us nothing.)
# Consequence: closing this claude has NO "Keep/Remove worktree" dialog (that is a --worktree feature) — it
# just exits to the shell (still cd'd in the worktree); remove the worktree yourself with `git worktree remove`.
#
# Prints: pane id, worktree path, branch, and the claude session UUID (resumable). Does NOT dispatch the
# plan prompt — that's the orchestrator's judgment (one-line, then `send-keys <pane> Enter`).
set -euo pipefail

case "${1:-}" in -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0;; esac

# resolve_worktree <wtdir-abs> <branch> <base>: create-or-reuse; exits nonzero on conflict.
#   dir already a worktree on <branch> -> reuse; <branch> exists but no dir -> add from it;
#   neither -> create -b off <base>; dir on a DIFFERENT branch -> error.
resolve_worktree() {
  local wtdir="$1" branch="$2" base="$3"
  if [ -e "$wtdir" ]; then
    local cur; cur="$(git -C "$wtdir" symbolic-ref --short HEAD 2>/dev/null || true)"
    [ "$cur" = "$branch" ] || { echo "worktree $wtdir is on '$cur', not '$branch'" >&2; return 1; }
    echo ">> reusing existing worktree $wtdir ($branch)"; return 0
  fi
  if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$branch"; then
    echo ">> adding worktree $wtdir from existing branch $branch"
    git -C "$REPO_ROOT" worktree add "$wtdir" "$branch"
  else
    echo ">> creating worktree $wtdir (new branch $branch off $base)"
    git -C "$REPO_ROOT" worktree add -b "$branch" "$wtdir" "$base"
  fi
}

REPO_ROOT="${REPO_ROOT:-$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')}"
[ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT" ] || { echo "cannot determine REPO_ROOT (set REPO_ROOT env)" >&2; exit 1; }

# test hook: resolve worktree only (no herdr/tab-create), then exit
if [ "${1:-}" = "--resolve-worktree-only" ]; then
  shift; resolve_worktree "$REPO_ROOT/.worktrees/$1" "$2" "${3:-origin/main}"; exit $?
fi

[ $# -ge 4 ] || { echo "usage: $0 <workspace-id> <tab-label> <worktree-dir> <branch> [base-ref]" >&2; exit 2; }
WS=$1; LABEL=$2; WTDIRNAME=$3; BRANCH=$4; BASE=${5:-origin/main}
WTDIR="$REPO_ROOT/.worktrees/$WTDIRNAME"

jqpane() { python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])'; }
jquuid() { python3 -c 'import sys,json; s=(json.load(sys.stdin)["result"]["pane"].get("agent_session") or {}); print(s.get("value") or "")'; }

echo ">> fetch + resolve worktree $WTDIR  (branch $BRANCH off $BASE)"
git -C "$REPO_ROOT" fetch origin -q || true
resolve_worktree "$WTDIR" "$BRANCH" "$BASE"
git -C "$WTDIR" log --oneline -1 | sed 's/^/   base tip: /'

echo ">> creating tab '$LABEL' in $WS"
PANE=$(herdr tab create --workspace "$WS" --label "$LABEL" | jqpane)
[ -n "$PANE" ] || { echo "tab create failed" >&2; exit 1; }
echo "   root pane: $PANE"

PLAN_MODEL="${IGR_PLAN_MODEL:-opus}"   # planning-claude model knob; sibling of IGR_IMPL_*/IGR_REVIEW_*
echo ">> launching: cd $WTDIR && direnv allow && claude --model $PLAN_MODEL"
herdr pane run "$PANE" "cd $WTDIR && direnv allow && claude --model $PLAN_MODEL"

echo ">> waiting for boot..."
for _ in $(seq 1 40); do
  sleep 3
  herdr pane read "$PANE" --source visible --lines 8 2>/dev/null | grep -q '❯' && break
done

echo ">> /rename $LABEL"
herdr pane run "$PANE" "/rename $LABEL"; sleep 1; herdr pane send-keys "$PANE" Enter; sleep 2

UUID=$(herdr pane get "$PANE" 2>/dev/null | jquuid)
echo "------------------------------------------------------------"
echo "pane=$PANE"
echo "worktree=$WTDIR"
echo "branch=$BRANCH   (off $BASE)"
echo "session=$UUID   # resume: claude --resume \"$LABEL\"  (or the UUID)"
echo "------------------------------------------------------------"
echo "next: dispatch the ONE-LINE spec/plan prompt → herdr pane run $PANE '<prompt>' ; herdr pane send-keys $PANE Enter"
