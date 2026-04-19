#!/usr/bin/env bash
# Lefthook pre-commit hook for plugin/ build integrity.
#
# Behavior:
#   1. If staged files touch .claude/ | scripts/ | .launchpad/ | VERSION:
#      → run build-plugin.sh and re-stage plugin/ delta.
#   2. If staged files touch plugin/ WITHOUT any source change:
#      → REJECT (direct edits to plugin/ are not allowed).
#
# Escape hatch: commit message with "[plugin-regen]" bypasses #2.
#
# Invoked by lefthook with {staged_files} expanded as arguments.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

# Split staged paths into buckets
source_changed=0
plugin_changed=0
for f in "$@"; do
  case "$f" in
    .claude/*|scripts/*|.launchpad/*|VERSION)
      source_changed=1 ;;
    plugin/*)
      plugin_changed=1 ;;
  esac
done

# Case: plugin/ edited without a source change → reject
# (Skip check if the last commit message contains the escape marker — we check
# the current in-progress commit message via COMMIT_EDITMSG if available.)
if [ "$plugin_changed" -eq 1 ] && [ "$source_changed" -eq 0 ]; then
  if [ -f "$REPO/.git/COMMIT_EDITMSG" ] && grep -q '\[plugin-regen\]' "$REPO/.git/COMMIT_EDITMSG"; then
    echo "› [plugin-regen] marker present — allowing direct plugin/ edit"
    exit 0
  fi
  echo "✗ direct edits to plugin/ are not allowed" >&2
  echo "  plugin/ is a build artifact generated from .claude/ by scripts/build-plugin.sh" >&2
  echo "  to change plugin/, edit the corresponding source under .claude/ instead" >&2
  echo "  escape hatch: include [plugin-regen] in the commit message" >&2
  exit 1
fi

# Case: source changed → rebuild plugin/ and re-stage the result
if [ "$source_changed" -eq 1 ]; then
  echo "› source change detected — rebuilding plugin/"
  if ! bash "$REPO/scripts/build-plugin.sh" >/dev/null; then
    echo "✗ plugin build failed — fix the build error and try again" >&2
    exit 1
  fi
  # Re-stage the plugin/ delta. `git add -A` is scoped to plugin/ to avoid
  # accidentally staging unrelated changes.
  git add -A plugin/ || true
  echo "✓ plugin/ rebuilt and staged"
fi

exit 0
