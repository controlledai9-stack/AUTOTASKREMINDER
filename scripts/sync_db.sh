#!/usr/bin/env bash
# Commits and pushes the local tracker database so the GitHub Actions
# scheduler can see your latest tasks.
#
# Run this after adding/editing tasks locally, whenever you want the next
# scheduled email to reflect those changes:
#
#   ./scripts/sync_db.sh
#
# See docs/ARCHITECTURE.md for why this manual sync step is necessary.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "$(git status --porcelain data/tracker.db 2>/dev/null)" ]]; then
  echo "No changes to data/tracker.db - nothing to sync."
  exit 0
fi

git add data/tracker.db
git commit -m "chore: sync local task changes"
git push

echo "Synced! GitHub Actions will now see your latest tasks on its next scheduled run."
