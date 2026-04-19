#!/usr/bin/env bash
# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
# --- end launchpad preamble ---
set -euo pipefail
# PreToolUse hook: blocks merge, force-push, and approve commands.
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.
#
# Performance: single jq invocation + native Bash [[ =~ ]] matching per segment.
# No grep/sed forks per pattern. Compatible with Bash 3.2 (macOS default).

INPUT=$(cat) || true

# Empty stdin means no tool_input to inspect — allow. Relaxed from earlier
# "fail closed on empty stdin" behavior per hook-hardening review.
if [ -z "$INPUT" ]; then
  exit 0
fi

# jq is required — document as hard dependency; fail loudly if missing.
if ! command -v jq >/dev/null 2>&1; then
  echo "BLOCKED: jq is required by block-merges.sh. Install: brew install jq" >&2
  exit 2
fi

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
[ -z "$COMMAND" ] && exit 0

# Split on command separators (; && ||) into segments, matching each separately
# in pure Bash. Do NOT split on `|` — pipes aren't command separators.
# Newlines treated as implicit ;.
# awk split produces one segment per output line.
SEGMENTS=$(printf '%s' "$COMMAND" | tr '\n' ';' | awk 'BEGIN{RS="(;|&&|\\|\\|)"} NF {print}')

# Lowercase once, then iterate. tr is a single fork for the whole command.
LC_SEGMENTS=$(printf '%s' "$SEGMENTS" | tr '[:upper:]' '[:lower:]')

# Use a here-doc to feed lines; avoid subshell piping that would skip the
# `exit 2` return.
while IFS= read -r lc; do
  # Trim leading whitespace (Bash-native, no fork)
  lc="${lc#"${lc%%[![:space:]]*}"}"
  lc="${lc%"${lc##*[![:space:]]}"}"
  [ -z "$lc" ] && continue

  # gh pr merge
  if [[ "$lc" =~ ^gh[[:space:]]+pr[[:space:]]+merge ]]; then
    echo "BLOCKED: gh pr merge is prohibited. The pipeline stops at PR creation." >&2
    exit 2
  fi

  # git merge main / git merge master (NOT git merge origin/...)
  if [[ "$lc" =~ ^git[[:space:]]+merge[[:space:]]+(main|master)([[:space:]]|$) ]] \
     && ! [[ "$lc" =~ ^git[[:space:]]+merge[[:space:]]+origin/ ]]; then
    echo "BLOCKED: git merge main/master is prohibited. Use 'git merge origin/main' for safe sync." >&2
    exit 2
  fi

  # git push --force / -f
  if [[ "$lc" =~ ^git[[:space:]]+push[[:space:]].*--force ]] \
     || [[ "$lc" =~ ^git[[:space:]]+push[[:space:]]+-f([[:space:]]|$) ]]; then
    echo "BLOCKED: force push is prohibited." >&2
    exit 2
  fi

  # git push origin main/master (any flag form)
  if [[ "$lc" =~ ^git[[:space:]]+push[[:space:]]+.*origin[[:space:]]+(main|master|head:(main|master)) ]]; then
    echo "BLOCKED: push to main/master is prohibited." >&2
    exit 2
  fi

  # gh pr review --approve
  if [[ "$lc" =~ ^gh[[:space:]]+pr[[:space:]]+review[[:space:]]+--approve ]]; then
    echo "BLOCKED: PR auto-approve is prohibited." >&2
    exit 2
  fi
done <<< "$LC_SEGMENTS"

exit 0
