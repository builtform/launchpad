#!/usr/bin/env bash
# PreToolUse hook: blocks merge, force-push, and approve commands.
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Split chained commands (&&, ;, ||) and check each independently.
# For each sub-command, strip quoted strings and heredoc content to avoid
# false positives from text inside commit messages or PR bodies.
BLOCKED_PATTERN="(^|\s)(gh pr merge|git merge (main|master)|gh pr review --approve)(\s|$)"
PUSH_PATTERN="git push.*(origin\s+main|origin\s+master|HEAD:main|HEAD:master)|git push --force|git push -f"

# Remove all content between quotes (single and double) and heredocs
SANITIZED=$(echo "$COMMAND" | sed "s/'[^']*'//g" | sed 's/"[^"]*"//g' | sed 's/\$(cat <<.*//g')

if echo "$SANITIZED" | grep -qiE "$BLOCKED_PATTERN|$PUSH_PATTERN"; then
  echo "BLOCKED: Merge/force-push/approve commands are prohibited. The pipeline stops at PR creation." >&2
  exit 2
fi

exit 0
