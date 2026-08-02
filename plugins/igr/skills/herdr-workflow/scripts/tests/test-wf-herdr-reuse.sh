#!/usr/bin/env bash
# Unit test for wf-herdr.sh worktree create-or-reuse (no herdr needed).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
SUT="$here/../wf-herdr.sh"

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git -C "$tmp" init -q
git -C "$tmp" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
git -C "$tmp" branch -M main

# case A: neither branch nor worktree exists -> creates with -b
REPO_ROOT="$tmp" bash "$SUT" --resolve-worktree-only wtA feat/saw-1-x main
test -d "$tmp/.worktrees/wtA" || { echo "A: worktree not created"; exit 1; }
git -C "$tmp/.worktrees/wtA" symbolic-ref --short HEAD | grep -qx feat/saw-1-x || { echo "A: wrong branch"; exit 1; }

# case B: branch exists, no worktree -> add from existing branch (no -b)
git -C "$tmp" branch feat/saw-2-y main
REPO_ROOT="$tmp" bash "$SUT" --resolve-worktree-only wtB feat/saw-2-y main
git -C "$tmp/.worktrees/wtB" symbolic-ref --short HEAD | grep -qx feat/saw-2-y || { echo "B: wrong branch"; exit 1; }

# case C: worktree already exists on the branch -> reuse, no error
REPO_ROOT="$tmp" bash "$SUT" --resolve-worktree-only wtB feat/saw-2-y main
echo "C: reuse ok"

# case D: worktree dir exists on a DIFFERENT branch -> error
if REPO_ROOT="$tmp" bash "$SUT" --resolve-worktree-only wtB feat/saw-3-z main 2>/dev/null; then
  echo "D: expected conflict error"; exit 1
fi
echo "ALL PASS"
