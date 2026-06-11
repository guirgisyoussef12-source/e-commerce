#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "❌ Error: Please enter a commit message!"
    echo "Usage: ./scripts/git_sync.sh \"your message\""
    exit 1
fi

COMMIT_MSG=$1

./scripts/test.sh

echo "=== ⬆️ [2/5] Pushing Verified Code to GitHub ==="
git add .
git commit -m "$COMMIT_MSG"

CURRENT_BRANCH=$(git branch --show-current)
echo "🔄 Releasing updates on branch: $CURRENT_BRANCH"
git pull origin "$CURRENT_BRANCH" --rebase
git push origin "$CURRENT_BRANCH"

echo "🚀 Code is live on GitHub and fully verified by automated tests!"