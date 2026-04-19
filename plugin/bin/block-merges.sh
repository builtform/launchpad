#!/usr/bin/env bash
# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
# --- end launchpad preamble ---
set -euo pipefail
# PreToolUse hook: blocks merge, force-push, and approve commands.
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat) || true

# Fail closed: if jq is missing or input is empty
if ! command -v jq >/dev/null 2>&1 || [ -z "$INPUT" ]; then
  echo "BLOCKED: Could not parse hook input (jq missing or empty stdin). Failing closed." >&2
  exit 2
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || true

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Normalize: convert newlines to ;; (treating each line as a separate command)
# then flatten to single line for boundary matching.
FLAT=$(printf '%s' "$COMMAND" | tr '\n' ';')

# Split into segments on && ; || and check each independently.
# This prevents "git merge origin/main" in one segment from suppressing
# detection of "git merge main" in another segment.
while IFS= read -r seg; do
  seg=$(echo "$seg" | sed 's/^[[:space:]]*//')
  [ -z "$seg" ] && continue

  # gh pr merge
  if echo "$seg" | grep -qiE "^gh pr merge"; then
    echo "BLOCKED: gh pr merge is prohibited. The pipeline stops at PR creation." >&2
    exit 2
  fi

  # git merge main/master (but not origin/main)
  if echo "$seg" | grep -qiE "^git merge[[:space:]]+(main|master)" && \
     ! echo "$seg" | grep -qiE "^git merge[[:space:]]+origin/"; then
    echo "BLOCKED: git merge main/master is prohibited. Use 'git merge origin/main' for safe sync." >&2
    exit 2
  fi

  # git push --force / -f
  if echo "$seg" | grep -qiE "^git push[[:space:]].*--force|^git push[[:space:]]+-f"; then
    echo "BLOCKED: force push is prohibited." >&2
    exit 2
  fi

  # git push to main/master (with any flags before origin)
  if echo "$seg" | grep -qiE "^git push[[:space:]]+.*origin[[:space:]]+(main|master|HEAD:(main|master))"; then
    echo "BLOCKED: push to main/master is prohibited." >&2
    exit 2
  fi

  # gh pr review --approve
  if echo "$seg" | grep -qiE "^gh pr review[[:space:]]+--approve"; then
    echo "BLOCKED: PR auto-approve is prohibited." >&2
    exit 2
  fi

done <<< "$(echo "$FLAT" | tr ';&' '\n' | sed 's/|/\n/g')"

exit 0
