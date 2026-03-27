#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
OUTPUT_DIR=$(jq -r '.outputDir // "./scripts/compound"' "$CONFIG_FILE")
OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
MAX_CYCLES=$(jq -r '.evaluator.maxCycles // 3' "$CONFIG_FILE")

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EVALUATOR] $1"; }

# Check Playwright availability
if ! command -v npx >/dev/null 2>&1 || ! npx playwright --version >/dev/null 2>&1; then
  log "Skipped: Playwright not available. Install with: npx playwright install"
  exit 0
fi

# Check port availability
for port in 3000 3001; do
  if lsof -i :"$port" >/dev/null 2>&1; then
    log "Skipped: port $port already in use"
    exit 0
  fi
done

# Start dev server
cd "$PROJECT_ROOT"
pnpm dev &
DEV_PID=$!
trap "kill $DEV_PID 2>/dev/null || true" EXIT

# Wait for readiness
for i in $(seq 1 30); do
  if curl -s http://localhost:3000 >/dev/null 2>&1; then break; fi
  if [ "$i" -eq 30 ]; then
    log "Skipped: dev server did not start within 30s"
    exit 0
  fi
  sleep 1
done

log "Dev server ready."

# Read sprint contract if it exists
CONTRACT_CONTEXT=""
if [ -f "$OUTPUT_DIR/sprint-contract.json" ]; then
  CONTRACT_CONTEXT="
Sprint contract (the generator and evaluator agreed on these verification criteria before building):
$(cat "$OUTPUT_DIR/sprint-contract.json")"
fi

# Evaluator cycles
for cycle in $(seq 1 $MAX_CYCLES); do
  log "Cycle $cycle of $MAX_CYCLES"

  EVAL_PROMPT="$(cat "$SCRIPT_DIR/evaluate-prompt.md")

Read the grading criteria: $SCRIPT_DIR/grading-criteria.md
Web URL: http://localhost:3000
API URL: http://localhost:3001
PRD file: $(ls "$PROJECT_ROOT"/docs/tasks/prd-*.md 2>/dev/null | head -1)
Task file: $OUTPUT_DIR/prd.json
Report output: $OUTPUT_DIR/evaluator-report.json
$CONTRACT_CONTEXT"

  echo "$EVAL_PROMPT" | ai_run 2>&1

  # Check results
  if [ ! -f "$OUTPUT_DIR/evaluator-report.json" ]; then
    log "Warning: no report produced, skipping"
    break
  fi

  # Check if all 4 dimensions passed
  ALL_PASS=true
  for dim in design originality craft functionality; do
    RESULT=$(jq -r ".$dim.result" "$OUTPUT_DIR/evaluator-report.json" 2>/dev/null)
    if [ "$RESULT" != "pass" ]; then ALL_PASS=false; fi
  done

  if [ "$ALL_PASS" = "true" ]; then
    log "All dimensions passed on cycle $cycle"
    break
  fi

  if [ "$cycle" -eq "$MAX_CYCLES" ]; then
    log "Max cycles reached. Final report saved."
    break
  fi

  # Run generator fix cycle
  log "Dimensions failed. Running generator fix cycle..."
  echo "Read $OUTPUT_DIR/evaluator-report.json. Fix the failed dimensions. The evaluator found issues by testing the running application -- take the feedback seriously. Commit your fixes." | ai_run 2>&1

  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "fix: address evaluator feedback (cycle $cycle)"
  fi
done

# Cleanup
kill $DEV_PID 2>/dev/null || true
exit 0
