#!/usr/bin/env bash
# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---
__lp_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${__lp_script_dir%/bin*}}"
unset __lp_script_dir
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
# --- end launchpad preamble ---
# Compound Learning — Extract learnings from progress.txt
# Basic version: reads progress.txt, extracts learnings, writes to docs/solutions/.
# Phase 6 upgrades this to the full 5-agent, 14-category system.
#
# Usage: ./compound-learning.sh

source "$(dirname "$0")/lib.sh"

cd "$PROJECT_ROOT"

PROGRESS_FILE="$OUTPUT_DIR/progress.txt"
PRD_FILE="$OUTPUT_DIR/prd.json"
TEMPLATE_FILE="$PROJECT_ROOT/docs/solutions/compound-product/_template.md"

if [ ! -f "$PROGRESS_FILE" ]; then
  log "No progress.txt found. Nothing to extract."
  exit 0
fi

# Derive feature slug from prd.json branch name or current branch
if [ -f "$PRD_FILE" ]; then
  BRANCH_NAME=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
else
  BRANCH_NAME=$(git branch --show-current)
fi

FEATURE_SLUG=$(echo "$BRANCH_NAME" | sed "s|^${BRANCH_PREFIX}||" | sed 's|^compound/||')
if [ -z "$FEATURE_SLUG" ]; then
  FEATURE_SLUG="unknown-feature"
fi

LEARNINGS_DIR="$PROJECT_ROOT/docs/solutions/compound-product/$FEATURE_SLUG"
LEARNINGS_FILE="$LEARNINGS_DIR/${FEATURE_SLUG}-$(date +%Y-%m-%d).md"

# Count task stats from prd.json
TASKS_TOTAL=0
TASKS_COMPLETED=0
ITERATION_COUNT=0

if [ -f "$PRD_FILE" ]; then
  TASKS_TOTAL=$(jq '.tasks | length' "$PRD_FILE" 2>/dev/null || echo 0)
  # Count completed tasks. Newer flow uses .status == "done"; older schemas
  # use .passes == true. Accept both for backward compatibility.
  TASKS_COMPLETED=$(jq '[.tasks[] | select(.status == "done" or .passes == true)] | length' "$PRD_FILE" 2>/dev/null || echo 0)
fi
ITERATION_COUNT=$(grep -c "^## " "$PROGRESS_FILE" 2>/dev/null || echo 0)

# Get PR URL if available
PR_URL=$(gh pr view --json url -q '.url' 2>/dev/null || echo "N/A")

if [ -f "$TEMPLATE_FILE" ]; then
  mkdir -p "$LEARNINGS_DIR"

  EXTRACT_PROMPT="Read this progress log and extract a structured learnings document.

Progress log:
$(cat "$PROGRESS_FILE")

Template to follow (fill in the YAML frontmatter and sections):
$(cat "$TEMPLATE_FILE")

Fill in these values:
- title: ${FEATURE_SLUG}
- feature: ${FEATURE_SLUG}
- date: $(date +%Y-%m-%d)
- branch: ${BRANCH_NAME}
- tasks_total: ${TASKS_TOTAL}
- tasks_completed: ${TASKS_COMPLETED}
- iterations_used: ${ITERATION_COUNT}
- max_iterations: ${MAX_ITERATIONS}
- pr_url: ${PR_URL}

Extract ALL learnings, patterns, gotchas, and file changes from the progress log.
Output ONLY the filled-in markdown document, nothing else."

  LEARNINGS_CONTENT=$(echo "$EXTRACT_PROMPT" | ai_run 2>&1)

  if [ -n "$LEARNINGS_CONTENT" ]; then
    echo "$LEARNINGS_CONTENT" > "$LEARNINGS_FILE"
    log "Learnings saved to: $LEARNINGS_FILE"
  else
    log "WARNING: Failed to extract learnings. Review progress.txt manually."
  fi
else
  log "WARNING: No template found at $TEMPLATE_FILE. Skipping structured extraction."
  mkdir -p "$LEARNINGS_DIR"
  # Fallback: just copy progress.txt as raw learnings
  cp "$PROGRESS_FILE" "$LEARNINGS_FILE"
  log "Raw progress copied to: $LEARNINGS_FILE"
fi

log "Review your learnings: $LEARNINGS_FILE"
log "Promote patterns to: docs/solutions/compound-product/patterns/promoted-patterns.md"
