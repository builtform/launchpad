#!/usr/bin/env bash
# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---
__lp_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${__lp_script_dir%/bin*}}"
unset __lp_script_dir
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
# --- end launchpad preamble ---
set -eo pipefail

# Source shared functions (provides ai_run, log, config vars)
source "$(dirname "$0")/lib.sh"

MAX_CYCLES=$(jq -r '.evaluator.maxCycles // 3' "$CONFIG_FILE")

elog() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EVALUATOR] $1"; }

# Write a skipped report so the pipeline knows no evaluation occurred
write_skipped_report() {
  local reason="$1"
  cat > "$OUTPUT_DIR/evaluator-report.json" <<SKIP_EOF
{"status":"skipped","reason":"$reason","design":null,"originality":null,"craft":null,"functionality":null}
SKIP_EOF
  elog "Wrote skipped report: $reason"
}

# Check Playwright availability
if ! command -v npx >/dev/null 2>&1 || ! npx playwright --version >/dev/null 2>&1; then
  write_skipped_report "Playwright not available. Install with: npx playwright install"
  elog "Warning: Playwright not available — evaluator skipped (no evaluation performed)"
  exit 0
fi

# Check port availability
for port in 3000 3001; do
  if lsof -i :"$port" >/dev/null 2>&1; then
    write_skipped_report "Port $port already in use"
    elog "Warning: port $port already in use — evaluator skipped (no evaluation performed)"
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
    elog "Warning: servers did not start — evaluator skipped (no evaluation performed)"
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
  elog "Cycle $cycle of $MAX_CYCLES"

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
    elog "Warning: no report produced, skipping"
    break
  fi

  # Check if all 4 dimensions passed
  ALL_PASS=true
  for dim in design originality craft functionality; do
    RESULT=$(jq -r ".$dim.result" "$OUTPUT_DIR/evaluator-report.json" 2>/dev/null || echo "fail")
    if [ "$RESULT" != "pass" ]; then ALL_PASS=false; fi
  done

  if [ "$ALL_PASS" = "true" ]; then
    elog "All dimensions passed on cycle $cycle"
    break
  fi

  if [ "$cycle" -eq "$MAX_CYCLES" ]; then
    elog "Max cycles reached. Final report saved."
    break
  fi

  # Run generator fix cycle
  elog "Dimensions failed. Running generator fix cycle..."
  echo "Read $OUTPUT_DIR/evaluator-report.json. Fix the failed dimensions. The evaluator found issues by testing the running application -- take the feedback seriously. Commit your fixes." | ai_run 2>&1

  git add -u
  if ! git diff --cached --quiet; then
    git commit -m "fix: address evaluator feedback (cycle $cycle)"
  fi
done

# Cleanup (trap handles this, but be explicit)
kill -- -$DEV_PID 2>/dev/null || kill $DEV_PID 2>/dev/null || true
exit 0
