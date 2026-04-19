#!/usr/bin/env bash
# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
# --- end launchpad preamble ---
set -euo pipefail
# PreToolUse hook: blocks merge, force-push, and approve commands.
# Registered in hooks.json / settings.json ONLY for Bash (matcher: "Bash"),
# so every invocation here is a Bash PreToolUse event.
#
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.
#
# Fail-closed policy: an empty/unparseable payload for a Bash event is a
# malformed hook invocation (Claude Code bug or tampering), not a legitimate
# "no command proposed" signal. Block rather than silently allow.
#
# Performance: single jq invocation + native Bash [[ =~ ]] matching per segment.
# No grep/sed forks per pattern. Compatible with Bash 3.2 (macOS default).

INPUT=$(cat) || true

if [ -z "$INPUT" ]; then
  echo "BLOCKED: block-merges hook received empty stdin for a Bash event." >&2
  echo "  This indicates a malformed hook payload. Failing closed to preserve policy." >&2
  exit 2
fi

# jq is required — document as hard dependency; fail loudly if missing.
if ! command -v jq >/dev/null 2>&1; then
  echo "BLOCKED: jq is required by block-merges.sh. Install: brew install jq" >&2
  exit 2
fi

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
if [ -z "$COMMAND" ]; then
  echo "BLOCKED: Bash tool_input.command is missing or JSON parsing failed." >&2
  echo "  Failing closed to preserve policy — retry once input is well-formed." >&2
  exit 2
fi

# Split on command separators (; && || &) into segments, matching each
# separately in pure Bash. Single `&` (background operator) IS a separator:
# `echo ok & git push origin main` must have the dangerous tail segmented
# out, or the anchored checks (^git push, ^gh pr merge, etc.) will miss it.
# Do NOT split on `|` — pipes aren't command separators.
# Order matters: longer operators (&& ||) listed first so POSIX leftmost-
# longest match picks them before single-char &.
# Newlines treated as implicit ;. awk produces one segment per output line.
SEGMENTS=$(printf '%s' "$COMMAND" | tr '\n' ';' | awk 'BEGIN{RS="(&&|\\|\\||;|&)"} NF {print}')

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

  # git push to protected branch (any remote, any arg order, any refspec form).
  # Matches `main` or `master` as a whole token, allowing the preceding
  # delimiter to be space, colon (HEAD:main), slash (refs/heads/main), or
  # plus (+main force-push refspec), and the trailing delimiter to be
  # space, colon, or end-of-string.
  if [[ "$lc" =~ ^git[[:space:]]+push([[:space:]]|$) ]] \
     && [[ "$lc" =~ (^|[[:space:]:/+])(main|master)([[:space:]]|:|$) ]]; then
    echo "BLOCKED: push references protected branch (main/master)." >&2
    echo "  Use a feature branch. Force-push refspecs (+main) and non-origin pushes are also blocked." >&2
    exit 2
  fi

  # gh pr review with --approve anywhere in the args (not just positional).
  # Matches `gh pr review` prefix AND `--approve` as a standalone token.
  if [[ "$lc" =~ ^gh[[:space:]]+pr[[:space:]]+review([[:space:]]|$) ]] \
     && [[ "$lc" =~ (^|[[:space:]])--approve([[:space:]]|=|$) ]]; then
    echo "BLOCKED: PR auto-approve is prohibited." >&2
    exit 2
  fi
done <<< "$LC_SEGMENTS"

exit 0
