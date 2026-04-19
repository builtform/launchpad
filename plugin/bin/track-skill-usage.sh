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
# Usage (called automatically by Claude Code hooks):
#   This script receives hook context via environment variables:
#     CLAUDE_TOOL_NAME  — the tool that was invoked (e.g., "Skill")
#     CLAUDE_TOOL_INPUT — JSON string with the tool's input parameters
#
# The script is idempotent and creates the usage JSON file if it doesn't exist.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root
# ---------------------------------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

USAGE_FILE="$REPO_ROOT/docs/skills-catalog/skills-usage.json"
USAGE_DIR="$(dirname "$USAGE_FILE")"

# ---------------------------------------------------------------------------
# Only process Skill tool invocations
# ---------------------------------------------------------------------------
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
if [ "$TOOL_NAME" != "Skill" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Extract skill name from tool input
# ---------------------------------------------------------------------------
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
if [ -z "$TOOL_INPUT" ]; then
  exit 0
fi

# Parse the skill name from the JSON input
# Expected format: {"skill": "skill-name", ...}
SKILL_NAME=""
if command -v python3 >/dev/null 2>&1; then
  SKILL_NAME=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    print(data.get('skill', ''))
except:
    pass
" "$TOOL_INPUT" 2>/dev/null) || true
fi

# Fallback: basic extraction if python3 is not available or fails
if [ -z "$SKILL_NAME" ]; then
  # Try to extract skill name using sed (handles {"skill": "name"} format)
  SKILL_NAME=$(printf '%s' "$TOOL_INPUT" | sed -n 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' 2>/dev/null) || true
fi

# Strip any namespace prefix (e.g., "ms-office-suite:pdf" -> "pdf")
if [[ "$SKILL_NAME" == *:* ]]; then
  SKILL_NAME="${SKILL_NAME##*:}"
fi

if [ -z "$SKILL_NAME" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Ensure the usage file and directory exist
# ---------------------------------------------------------------------------
mkdir -p "$USAGE_DIR"

if [ ! -f "$USAGE_FILE" ]; then
  cat > "$USAGE_FILE" <<'EOF'
{
  "last_audit_date": null,
  "skills": {}
}
EOF
fi

# ---------------------------------------------------------------------------
# Update the usage file with current date stamp
# ---------------------------------------------------------------------------
TODAY=$(date +%Y-%m-%d)

if command -v python3 >/dev/null 2>&1; then
  python3 -c "
import json, sys

usage_file = sys.argv[1]
skill_name = sys.argv[2]
today = sys.argv[3]

with open(usage_file, 'r') as f:
    data = json.load(f)

if 'skills' not in data:
    data['skills'] = {}

data['skills'][skill_name] = today

with open(usage_file, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" "$USAGE_FILE" "$SKILL_NAME" "$TODAY"
else
  # Minimal fallback without python3 — unlikely on macOS but handle gracefully
  # Just log a warning; don't corrupt the file
  echo "[track-skill-usage] WARNING: python3 not found, skipping usage update for '$SKILL_NAME'" >&2
fi
