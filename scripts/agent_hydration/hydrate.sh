#!/usr/bin/env bash
set -euo pipefail
# Session Hydration — inject current project state at session start.
# Called by: SessionStart hook (startup, clear) and /hydrate / /lp-hydrate command.
#
# Plugin-mode behavior:
#   1. Emit a compact "LaunchPad active" session card with core conventions
#   2. Emit backlog summary if docs/tasks/BACKLOG.md exists (capped at 200 lines)
#   3. Emit drift report only if running in the LaunchPad template itself
#
# Drift detection is template-only — in brownfield projects we do NOT call
# detect-structure-drift.sh (structure-check scripts aren't shipped in the
# plugin; brownfield shouldn't be policed against LaunchPad's layout).

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Step 1 — Session card
cat <<'EOF'
## LaunchPad active

Daily loop: /lp-commit → /lp-review → /lp-ship
Conventions: /lp-instructions (core principles), /lp-version (plugin version)

Core principles: fix root causes, no secrets in commits, production-first.
EOF

# Step 2 — Backlog (if present)
BACKLOG="$PROJECT_ROOT/docs/tasks/BACKLOG.md"
if [ -f "$BACKLOG" ]; then
  echo ""
  echo "## Backlog"
  echo ""
  head -n 200 "$BACKLOG"
fi

# Step 3 — Drift report (template-only; skipped in plugin mode)
# We only run drift detection when the maintenance script is present AND the
# REPOSITORY_STRUCTURE.md treaty doc exists. In brownfield (neither present),
# this whole block is skipped silently.
DRIFT_SCRIPT="$PROJECT_ROOT/scripts/maintenance/detect-structure-drift.sh"
DRIFT_TREATY="$PROJECT_ROOT/docs/architecture/REPOSITORY_STRUCTURE.md"
DRIFT_REPORT="$PROJECT_ROOT/.harness/structure-drift.md"
if [ -x "$DRIFT_SCRIPT" ] && [ -f "$DRIFT_TREATY" ]; then
  bash "$DRIFT_SCRIPT" 2>/dev/null || true
  if [ -f "$DRIFT_REPORT" ]; then
    echo ""
    cat "$DRIFT_REPORT"
  fi
fi
