#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
OUTPUT_DIR=$(jq -r '.outputDir // "./scripts/compound"' "$CONFIG_FILE")
OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
MAX_CYCLES=$(jq -r '.evaluator.maxCycles // 3' "$CONFIG_FILE")

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EVALUATOR] $1"; }

# Require ai_run (exported by auto-compound.sh)
if ! declare -f ai_run >/dev/null 2>&1; then
  log "Error: ai_run function not available. evaluate.sh must be called from auto-compound.sh."
  exit 1
fi

# Write a skipped report so the pipeline knows no evaluation occurred
write_skipped_report() {
  local reason="$1"
  cat > "$OUTPUT_DIR/evaluator-report.json" <<SKIP_EOF
{"status":"skipped","reason":"$reason","design":null,"originality":null,"craft":null,"functionality":null}
SKIP_EOF
  log "Wrote skipped report: $reason"
}

# Check Playwright availability
if ! command -v npx >/dev/null 2>&1 || ! npx playwright --version >/dev/null 2>&1; then
  write_skipped_report "Playwright not available. Install with: npx playwright install"
  log "Warning: Playwright not available — evaluator skipped (no evaluation performed)"
  exit 0
fi

# Check port availability
for port in 3000 3001; do
  if lsof -i :"$port" >/dev/null 2>&1; then
    write_skipped_report "Port $port already in use"
    log "Warning: port $port already in use — evaluator skipped (no evaluation performed)"
    exit 0
  fi
done

# Start dev server in its own process group so cleanup kills all children
cd "$PROJECT_ROOT"
set -m  # enable job control for process groups
pnpm dev &
DEV_PID=$!
set +m
trap "kill -- -$DEV_PID 2>/dev/null || kill $DEV_PID 2>/dev/null || true" EXIT

# Wait for readiness (both web :3000 and API :3001)
WEB_READY=false
API_READY=false
for i in $(seq 1 30); do
  if [ "$WEB_READY" = "false" ] && curl -s http://localhost:3000 >/dev/null 2>&1; then WEB_READY=true; fi
  if [ "$API_READY" = "false" ] && curl -s http://localhost:3001/health >/dev/null 2>&1; then API_READY=true; fi
  if [ "$WEB_READY" = "true" ] && [ "$API_READY" = "true" ]; then break; fi
  if [ "$i" -eq 30 ]; then
    write_skipped_report "Servers did not start within 30s (web=$WEB_READY, api=$API_READY)"
    log "Warning: servers did not start — evaluator skipped (no evaluation performed)"
    exit 0
  fi
  sleep 1
done

log "Dev servers ready (web + API)."

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
PRD file: ${PRD_PATH:-$(ls "$PROJECT_ROOT"/docs/tasks/prd-*.md 2>/dev/null | head -1)}
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
    RESULT=$(jq -r ".$dim.result" "$OUTPUT_DIR/evaluator-report.json" 2>/dev/null || echo "fail")
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

# Cleanup (trap handles this, but be explicit)
kill -- -$DEV_PID 2>/dev/null || kill $DEV_PID 2>/dev/null || true
exit 0
