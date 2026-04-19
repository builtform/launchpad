#!/usr/bin/env bash
# Lefthook pre-commit hook for plugin/ build integrity.
#
# Behavior:
#   1. If staged files touch .claude/ | scripts/ | .launchpad/ | VERSION:
#      → run build-plugin.sh and re-stage plugin/ delta.
#   2. If staged files touch plugin/ WITHOUT any source change:
#      → REJECT (direct edits to plugin/ are not allowed).
#
# Escape hatch: LP_PLUGIN_REGEN=1 environment variable bypasses #2.
# (COMMIT_EDITMSG is unreliable at pre-commit time — git populates it after
# the pre-commit phase, so marker-in-message approaches don't work.)
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
if [ "$plugin_changed" -eq 1 ] && [ "$source_changed" -eq 0 ]; then
  if [ "${LP_PLUGIN_REGEN:-}" = "1" ]; then
    echo "› LP_PLUGIN_REGEN=1 — allowing direct plugin/ edit"
    exit 0
  fi
  echo "✗ direct edits to plugin/ are not allowed" >&2
  echo "  plugin/ is a build artifact generated from .claude/ by scripts/build-plugin.sh" >&2
  echo "  to change plugin/, edit the corresponding source under .claude/ instead" >&2
  echo "  escape hatch: LP_PLUGIN_REGEN=1 git commit ..." >&2
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
