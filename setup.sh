#!/usr/bin/env bash
# One-time setup after cloning: activate the repo's git hooks (git cannot auto-enable
# hooks on clone by design). The post-commit hook auto-bumps the plugin version from
# the conventional-commit type — see .githooks/post-commit.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
git config core.hooksPath .githooks
echo "hooks activated: core.hooksPath = .githooks (post-commit auto-bumps plugin version)"
