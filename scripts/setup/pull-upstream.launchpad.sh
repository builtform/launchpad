#!/usr/bin/env bash
set -euo pipefail

# Safe directories — these are NOT customized during init and can be pulled from upstream
SAFE_DIRS=(".claude/commands" ".claude/skills" "scripts/compound" ".github/workflows")

# Check that the launchpad remote exists
if ! git remote get-url launchpad >/dev/null 2>&1; then
  echo "Error: no 'launchpad' remote found." >&2
  echo "Add it with: git remote add launchpad https://github.com/thinkinghand/launchpad.git" >&2
  exit 1
fi

echo "Fetching updates from Launchpad..."
git fetch launchpad

# Build the diff command for safe directories only
DIFF_ARGS=""
for dir in "${SAFE_DIRS[@]}"; do
  DIFF_ARGS="$DIFF_ARGS -- $dir"
done

echo ""
echo "Changes available in safe directories:"
echo "  (${SAFE_DIRS[*]})"
echo ""
git diff --stat HEAD...launchpad/main $DIFF_ARGS

echo ""
read -p "Apply these changes? [y/N]: " CONFIRM
if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
  for dir in "${SAFE_DIRS[@]}"; do
    git checkout launchpad/main -- "$dir" 2>/dev/null || true
  done
  echo "Updates applied. Review changes with 'git diff --cached' before committing."
else
  echo "No changes applied."
  echo "To pull individual files: git checkout launchpad/main -- path/to/file"
fi
