#!/usr/bin/env bash
set -eo pipefail
# Session Hydration — inject current project state at session start
# Called by: SessionStart hook (startup, clear) and /Hydrate command
#
# Loads:
# 1. Runs structure drift detection (writes report if drift found)
# 2. Project backlog (docs/tasks/BACKLOG.md)
# 3. Structure drift report (.harness/structure-drift.md) — if exists

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Step 1: Run drift detection (creates/updates .harness/structure-drift.md)
DRIFT_SCRIPT="$REPO_ROOT/scripts/maintenance/detect-structure-drift.sh"
if [ -x "$DRIFT_SCRIPT" ]; then
  bash "$DRIFT_SCRIPT" 2>/dev/null || true
fi

# Step 2: Output backlog
BACKLOG="$REPO_ROOT/docs/tasks/BACKLOG.md"
if [ -f "$BACKLOG" ]; then
  cat "$BACKLOG"
else
  echo "No backlog found. Run a workflow to generate docs/tasks/BACKLOG.md."
fi

# Step 3: Output drift report (just written by Step 1)
DRIFT="$REPO_ROOT/.harness/structure-drift.md"
if [ -f "$DRIFT" ]; then
  echo ""
  cat "$DRIFT"
fi
