#!/usr/bin/env bash
# detect-structure-drift.sh — Detects directories on disk that are not
# documented in docs/architecture/REPOSITORY_STRUCTURE.md.
#
# Called by: hydrate.sh at session start (synchronous)
# Output: .harness/structure-drift.md (if drift found)
#
# Scans targeted directories at meaningful depths:
#   - apps/*/           (new apps)
#   - apps/*/src/*/     (new source-level directories)
#   - packages/*/       (new packages)
#   - docs/*/           (new doc categories)
#   - scripts/*/        (new script categories)
#   - .claude/*/        (new Claude config directories)
#   - .codex/*/         (new Codex config directories)
#
# Does NOT do phantom detection (directories in doc but not on disk).

set -euo pipefail

SCRIPT_REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"

# An explicit root is required by the Codex hydration path and takes precedence
# over any ambient Claude variable. Argument-free Claude invocations preserve
# their existing CLAUDE_PROJECT_DIR behavior.
if [ "$#" -eq 2 ] && [ "$1" = "--project-root" ] && [ -n "$2" ]; then
  if ! REPO_ROOT="$(cd "$2" 2>/dev/null && pwd -P)"; then
    echo "Structure drift detection refused an invalid project root." >&2
    exit 2
  fi
  if [ "$REPO_ROOT" != "$SCRIPT_REPO_ROOT" ]; then
    echo "Structure drift detection refused a project root that does not own this script." >&2
    exit 2
  fi
elif [ "$#" -eq 0 ]; then
  if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    if ! REPO_ROOT="$(cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && pwd -P)"; then
      echo "Structure drift detection refused an invalid CLAUDE_PROJECT_DIR." >&2
      exit 2
    fi
  else
    REPO_ROOT="$SCRIPT_REPO_ROOT"
  fi
else
  echo "Usage: detect-structure-drift.sh [--project-root PATH]" >&2
  exit 2
fi
STRUCTURE_DOC="$REPO_ROOT/docs/architecture/REPOSITORY_STRUCTURE.md"
DRIFT_REPORT="$REPO_ROOT/.harness/structure-drift.md"

# Ensure .harness/ exists
mkdir -p "$REPO_ROOT/.harness"

# Exit if REPOSITORY_STRUCTURE.md doesn't exist
if [ ! -f "$STRUCTURE_DOC" ]; then
  rm -f "$DRIFT_REPORT"
  exit 0
fi

# Read the doc content once
DOC_CONTENT="$(cat "$STRUCTURE_DOC")"

# Validate doc is not empty
if [ -z "$DOC_CONTENT" ]; then
  rm -f "$DRIFT_REPORT"
  exit 0
fi

UNDOCUMENTED=()

# Helper: check if a directory path appears in the doc
dir_in_doc() {
  local dir_path="$1"
  echo "$DOC_CONTENT" | grep -qF -- "$dir_path" 2>/dev/null
}

# Scan: directories on disk → check if documented
scan_for_undocumented() {
  local base="$1"
  local prefix="$2"

  [ -d "$REPO_ROOT/$base" ] || return 0

  for dir in "$REPO_ROOT/$base"/*/; do
    [ -d "$dir" ] || continue
    local name
    name="$(basename "$dir")"

    # Skip hidden dirs and build artifacts
    [[ "$name" == .* ]] && continue
    [[ "$name" == "node_modules" ]] && continue

    local full_path="${prefix}${name}"
    if ! dir_in_doc "$full_path"; then
      UNDOCUMENTED+=("$full_path/")
    fi
  done
}

# Scan first-level directories
scan_for_undocumented "apps" "apps/"
scan_for_undocumented "packages" "packages/"
scan_for_undocumented "docs" "docs/"
scan_for_undocumented "scripts" "scripts/"
scan_for_undocumented ".claude" ".claude/"
scan_for_undocumented ".codex" ".codex/"

# Scan second-level: apps/*/src/*
for app_dir in "$REPO_ROOT"/apps/*/; do
  [ -d "$app_dir" ] || continue
  local_app="$(basename "$app_dir")"
  if [ -d "$app_dir/src" ]; then
    scan_for_undocumented "apps/$local_app/src" "apps/$local_app/src/"
  fi
done

# Report
if [ ${#UNDOCUMENTED[@]} -eq 0 ]; then
  rm -f "$DRIFT_REPORT"
  exit 0
fi

cat > "$DRIFT_REPORT" << EOF
## Structure Drift

${#UNDOCUMENTED[@]} undocumented $([ ${#UNDOCUMENTED[@]} -eq 1 ] && echo "directory" || echo "directories"):
$(printf -- '- \`%s\`\n' "${UNDOCUMENTED[@]}")

Tell your coding agent to update \`docs/architecture/REPOSITORY_STRUCTURE.md\`.
EOF
