#!/usr/bin/env bash
set -eo pipefail
# Session Hydration — inject current project state at session start
# Called by: SessionStart hook (startup, resume, clear, compact) and /lp-hydrate command
#
# Loads:
# 1. Runs structure drift detection (writes report if drift found)
# 2. Project backlog (docs/tasks/BACKLOG.md)
# 3. Structure drift report (.harness/structure-drift.md) — if exists

SCRIPT_REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"

# Codex passes an explicit root so an ambient Claude variable cannot redirect
# project reads or drift-report writes. Claude continues to supply
# CLAUDE_PROJECT_DIR when this script is invoked without arguments.
if [ "$#" -eq 2 ] && [ "$1" = "--project-root" ] && [ -n "$2" ]; then
  if ! REPO_ROOT="$(cd "$2" 2>/dev/null && pwd -P)"; then
    echo "Hydration refused an invalid project root." >&2
    exit 2
  fi
  if [ "$REPO_ROOT" != "$SCRIPT_REPO_ROOT" ]; then
    echo "Hydration refused a project root that does not own this script." >&2
    exit 2
  fi
elif [ "$#" -eq 0 ]; then
  if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    if ! REPO_ROOT="$(cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && pwd -P)"; then
      echo "Hydration refused an invalid CLAUDE_PROJECT_DIR." >&2
      exit 2
    fi
  else
    REPO_ROOT="$SCRIPT_REPO_ROOT"
  fi
else
  echo "Usage: hydrate.sh [--project-root PATH]" >&2
  exit 2
fi

# Step 1: Run drift detection (creates/updates .harness/structure-drift.md)
DRIFT_SCRIPT="$REPO_ROOT/scripts/maintenance/detect-structure-drift.sh"
if [ -x "$DRIFT_SCRIPT" ]; then
  bash "$DRIFT_SCRIPT" --project-root "$REPO_ROOT" 2>/dev/null || true
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
