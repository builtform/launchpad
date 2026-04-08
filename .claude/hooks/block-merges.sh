#!/usr/bin/env bash
# PreToolUse hook: blocks merge, force-push, and approve commands.
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Fail closed: if we can't parse the input, block rather than allow
if [ $? -ne 0 ] || [ -z "$INPUT" ]; then
  echo "BLOCKED: Could not parse hook input. Failing closed for safety." >&2
  exit 2
fi

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Match forbidden commands at command boundaries only.
# Uses word-boundary-aware patterns that won't match inside strings/heredocs.
# Key insight: dangerous commands always appear at the START of a shell statement,
# preceded by nothing, &&, ;, or ||. They never appear mid-argument.

# Normalize: convert newlines to && (treating each line as a separate command)
# then flatten to single line for boundary matching.
FLAT=$(echo "$COMMAND" | sed 's/[[:space:]]*$//' | tr '\n' '&' | sed 's/&/\&\& /g')

# A command boundary is: start of string, or after && ; ||
if echo "$FLAT" | grep -qiE "(^|&&|;|\|\|)[[:space:]]*(gh pr merge)"; then
  echo "BLOCKED: gh pr merge is prohibited. The pipeline stops at PR creation." >&2
  exit 2
fi

# Block "git merge main" but allow "git merge origin/main" (safe sync for /commit and /ship)
if echo "$FLAT" | grep -qiE "(^|&&|;|\|\|)[[:space:]]*(git merge[[:space:]]+(main|master))" && \
   ! echo "$FLAT" | grep -qiE "git merge[[:space:]]+origin/(main|master)"; then
  echo "BLOCKED: git merge main/master is prohibited. Use 'git merge origin/main' for safe sync." >&2
  exit 2
fi

if echo "$FLAT" | grep -qiE "(^|&&|;|\|\|)[[:space:]]*(git push --force|git push -f)"; then
  echo "BLOCKED: force push is prohibited." >&2
  exit 2
fi

if echo "$FLAT" | grep -qiE "(^|&&|;|\|\|)[[:space:]]*(git push[[:space:]]+(-u[[:space:]]+)?origin[[:space:]]+(main|master|HEAD:(main|master)))"; then
  echo "BLOCKED: push to main/master is prohibited." >&2
  exit 2
fi

if echo "$FLAT" | grep -qiE "(^|&&|;|\|\|)[[:space:]]*(gh pr review --approve)"; then
  echo "BLOCKED: PR auto-approve is prohibited." >&2
  exit 2
fi

exit 0
