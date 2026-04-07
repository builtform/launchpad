#!/bin/bash
# Shared functions for compound product pipeline scripts.
# Source this file: source "$(dirname "$0")/lib.sh"

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
  exit 1
}

# Check common requirements
command -v jq >/dev/null 2>&1 || error "jq is required but not installed. Install with: brew install jq"

# Load config
if [ ! -f "$CONFIG_FILE" ]; then
  error "Config file not found: $CONFIG_FILE. This file should exist at scripts/compound/config.json — re-clone or restore it."
fi

# Read config values
REPORTS_DIR=$(jq -r '.reportsDir // "./docs/reports"' "$CONFIG_FILE")
OUTPUT_DIR=$(jq -r '.outputDir // "./scripts/compound"' "$CONFIG_FILE")
MAX_ITERATIONS=$(jq -r '.maxIterations // 25' "$CONFIG_FILE")
BRANCH_PREFIX=$(jq -r '.branchPrefix // "compound/"' "$CONFIG_FILE")
ANALYZE_COMMAND=$(jq -r '.analyzeCommand // ""' "$CONFIG_FILE")
TOOL=$(jq -r '.tool // "claude"' "$CONFIG_FILE")

# Validate AI tool CLI
command -v "$TOOL" >/dev/null 2>&1 || error "$TOOL CLI not found. Install it or change tool in config.json"

# Load enhancement defaults from config
AMBITION_MODE=$(jq -r '.ambitionMode // false' "$CONFIG_FILE")
EVALUATOR_ENABLED=$(jq -r '.evaluator.enabled // false' "$CONFIG_FILE")
SPRINT_CONTRACT=$(jq -r '.evaluator.sprintContract // false' "$CONFIG_FILE")

# ai_run: pipes a prompt into the configured AI tool (non-interactive, full permissions)
# Usage: echo "prompt" | ai_run 2>&1 | tee logfile
ai_run() {
  case "$TOOL" in
    codex)
      codex exec --dangerously-bypass-approvals-and-sandbox "$(cat -)"
      ;;
    gemini)
      gemini --approval-mode=yolo
      ;;
    claude)
      claude --dangerously-skip-permissions --print
      ;;
    *)
      error "Unknown tool: $TOOL. Valid values: claude, codex, gemini"
      ;;
  esac
}

# Export ai_run and TOOL so child scripts can use them
export -f ai_run
export TOOL

# Resolve paths
REPORTS_DIR="$PROJECT_ROOT/$REPORTS_DIR"
OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
TASKS_DIR="$PROJECT_ROOT/docs/tasks"

# Source environment variables (scoped to API keys only)
if [ -f "$PROJECT_ROOT/.env.local" ]; then
  while IFS='=' read -r key value; do
    # Only export API key variables, skip comments and empty lines
    case "$key" in
      \#*|"") continue ;;
      *_API_KEY|*_SECRET_KEY|*_TOKEN|ANTHROPIC_*|OPENAI_*|GEMINI_*)
        export "$key=$value"
        ;;
    esac
  done < "$PROJECT_ROOT/.env.local"
fi
