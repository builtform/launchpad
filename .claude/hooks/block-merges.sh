#!/usr/bin/env bash
# PreToolUse hook: blocks merge, force-push, and approve commands.
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [ -z "$COMMAND" ]; then
  exit 0
fi

if echo "$COMMAND" | grep -qiE "(gh pr merge|git merge (main|master)|git push.*(origin\s+main|origin\s+master|HEAD:main|HEAD:master)|git push --force|git push -f|gh pr review --approve)"; then
  echo "BLOCKED: Merge/force-push/approve commands are prohibited. The pipeline stops at PR creation." >&2
  exit 2
fi

exit 0
