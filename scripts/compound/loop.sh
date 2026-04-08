#!/usr/bin/env bash
# Compound Product - Execution Loop
# Runs an AI coding agent repeatedly until all tasks in prd.json are complete.
# Tool is configurable via config.json "tool" field: claude (default), codex, or gemini.
#
# Usage: ./loop.sh [max_iterations]

# Source shared functions (provides ai_run, log, error, config vars, TOOL, OUTPUT_DIR, etc.)
source "$(dirname "$0")/lib.sh"

# Prompt file (same for all tools — piped via stdin)
PROMPT_FILE="$SCRIPT_DIR/iteration-claude.md"

PRD_FILE="$OUTPUT_DIR/prd.json"
PROGRESS_FILE="$OUTPUT_DIR/progress.txt"

# Archive previous run if branch changed
LAST_BRANCH_FILE="$OUTPUT_DIR/.last-branch"
ARCHIVE_DIR="$OUTPUT_DIR/archive"

if [ -f "$PRD_FILE" ] && [ -f "$LAST_BRANCH_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  LAST_BRANCH=$(cat "$LAST_BRANCH_FILE" 2>/dev/null || echo "")

  if [ -n "$CURRENT_BRANCH" ] && [ -n "$LAST_BRANCH" ] && [ "$CURRENT_BRANCH" != "$LAST_BRANCH" ]; then
    DATE=$(date +%Y-%m-%d)
    FOLDER_NAME=$(echo "$LAST_BRANCH" | sed 's|^[^/]*/||')
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$DATE-$FOLDER_NAME"

    echo "Archiving previous run: $LAST_BRANCH"
    mkdir -p "$ARCHIVE_FOLDER"
    [ -f "$PRD_FILE" ] && mv "$PRD_FILE" "$ARCHIVE_FOLDER/"
    [ -f "$PROGRESS_FILE" ] && mv "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"
    echo "   Archived to: $ARCHIVE_FOLDER"

    # Reset progress file for new run
    echo "# Compound Product Progress Log" > "$PROGRESS_FILE"
    echo "Started: $(date)" >> "$PROGRESS_FILE"
    echo "---" >> "$PROGRESS_FILE"
  fi
fi

# Track current branch
if [ -f "$PRD_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ]; then
    echo "$CURRENT_BRANCH" > "$LAST_BRANCH_FILE"
  fi
fi

# Parse arguments (can override config)
while [[ $# -gt 0 ]]; do
  if [[ "$1" =~ ^[0-9]+$ ]]; then
    MAX_ITERATIONS="$1"
  fi
  shift
done

# Initialize progress file
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "# Compound Product Progress Log" > "$PROGRESS_FILE"
  echo "Started: $(date)" >> "$PROGRESS_FILE"
  echo "---" >> "$PROGRESS_FILE"
fi

echo "Starting Compound Product Loop - Tool: $TOOL | Max iterations: $MAX_ITERATIONS"

cd "$PROJECT_ROOT"

# Validate prd.json exists before entering the loop
if [ ! -f "$PRD_FILE" ]; then
  echo "ERROR: No prd.json found at: $PRD_FILE. Run build.sh first." >&2
  exit 1
fi

for i in $(seq 1 $MAX_ITERATIONS); do
  echo ""
  echo "==============================================================="
  echo "  Iteration $i of $MAX_ITERATIONS"
  echo "==============================================================="

  # Invoke the configured AI tool (ai_run from lib.sh)
  OUTPUT=$(cat "$PROMPT_FILE" | ai_run 2>&1 | tee /dev/stderr) || true

  # Update Kanban board after each iteration
  "$SCRIPT_DIR/board.sh" --md "$PRD_FILE" "$PROJECT_ROOT/docs/tasks/board.md" || true

  # Check for completion signal
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    echo "Compound Product completed all tasks!"
    echo "Completed at iteration $i of $MAX_ITERATIONS"
    exit 0
  fi

  echo "Iteration $i complete. Continuing..."
  sleep 2
done

echo ""
echo "Reached max iterations ($MAX_ITERATIONS) without completing all tasks."
echo "Check $PROGRESS_FILE for status."
exit 1
