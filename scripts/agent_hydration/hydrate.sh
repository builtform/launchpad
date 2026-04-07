#!/bin/bash
# Session Hydration — inject current project state at session start
# Called by: SessionStart hook (startup, clear) and /Hydrate command
#
# Design: Only loads the backlog dashboard. Repo structure is loaded
# on-demand via CLAUDE.md progressive disclosure.
# Extensible: add future session-start context below.

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
BACKLOG="$REPO_ROOT/docs/tasks/BACKLOG.md"

if [ -f "$BACKLOG" ]; then
  cat "$BACKLOG"
else
  echo "No backlog found. Run a workflow to generate docs/tasks/BACKLOG.md."
fi
