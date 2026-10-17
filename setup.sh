#!/usr/bin/env bash
# One-time setup after cloning: activate the repo's git hooks (git cannot auto-enable
# hooks on clone by design). On main, the post-commit and post-merge hooks auto-bump the
# plugin version from the conventional-commit type — see .githooks/.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
git config core.hooksPath .githooks
echo "hooks activated: core.hooksPath = .githooks (main auto-bumps plugin version)"
