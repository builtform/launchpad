#!/usr/bin/env bash
# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
# --- end launchpad preamble ---
# =============================================================================
# track-skill-usage.sh — PostToolUse hook for Skill tool invocations
#
# Fires after every `Skill` tool invocation. Extracts the skill name from
# the tool input and updates docs/skills-catalog/skills-usage.json with
# the last-used date stamp.
#
# Performance: jq-only (was python3 + sed fallback, ~60-150ms startup).
# Single fork for extraction + single fork for update = ~10-20ms per call.
# =============================================================================

set -euo pipefail

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
USAGE_FILE="$PROJECT_ROOT/docs/skills-catalog/skills-usage.json"
USAGE_DIR="$(dirname "$USAGE_FILE")"

# Only process Skill tool invocations
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
if [ "$TOOL_NAME" != "Skill" ]; then
  exit 0
fi

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
if [ -z "$TOOL_INPUT" ]; then
  exit 0
fi

# jq is required — fail gracefully if missing (don't crash the user's session)
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

# Extract skill name via jq
SKILL_NAME=$(printf '%s' "$TOOL_INPUT" | jq -r '.skill // empty' 2>/dev/null || true)

# Strip any namespace prefix (e.g., "ms-office-suite:pdf" -> "pdf")
if [[ "$SKILL_NAME" == *:* ]]; then
  SKILL_NAME="${SKILL_NAME##*:}"
fi

if [ -z "$SKILL_NAME" ]; then
  exit 0
fi

# Ensure directory + file exist
mkdir -p "$USAGE_DIR"
if [ ! -f "$USAGE_FILE" ]; then
  printf '%s\n' '{"last_audit_date":null,"skills":{}}' > "$USAGE_FILE"
fi

TODAY=$(date +%Y-%m-%d)

# Update via jq. Write to temp + rename for atomic replacement.
TMP=$(mktemp)
if jq --arg name "$SKILL_NAME" --arg today "$TODAY" \
     '(.skills //= {}) | .skills[$name] = $today' "$USAGE_FILE" > "$TMP" 2>/dev/null; then
  mv "$TMP" "$USAGE_FILE"
else
  # If jq fails (e.g., corrupted JSON), don't crash the session
  rm -f "$TMP"
fi
