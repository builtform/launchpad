#!/usr/bin/env bash
# Inject a self-locating PLUGIN_ROOT preamble into every copied plugin bin script.
#
# Claude Code SHOULD export CLAUDE_PLUGIN_ROOT to hook commands, but that is not
# guaranteed across all invocation paths. Adding a shim makes each script
# resolve its own plugin root deterministically.
set -euo pipefail

BIN_DIR="${1:?usage: $0 <plugin/bin dir>}"

SHIM=$'# --- launchpad plugin self-locating preamble (injected by build-plugin.sh) ---\n'
# PLUGIN_ROOT is computed from the script path. The parameter-expansion
# pattern `${__lp_script_dir%/bin*}` strips everything from `/bin` onward,
# so scripts at any depth under plugin/bin (including plugin/bin/compound/)
# resolve to the plugin root correctly.
SHIM+=$'__lp_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
SHIM+=$'PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${__lp_script_dir%/bin*}}"\n'
SHIM+=$'unset __lp_script_dir\n'
SHIM+=$'PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"\n'
SHIM+=$'# --- end launchpad preamble ---\n'

injected=0
while IFS= read -r -d '' script; do
  # Skip if shim already present
  if grep -q 'launchpad plugin self-locating preamble' "$script"; then
    continue
  fi
  # Read first line (shebang) and rest
  first_line=$(head -n 1 "$script")
  rest=$(tail -n +2 "$script")

  # Detect shebang: inject shim AFTER shebang, before rest
  if [[ "$first_line" == \#!* ]]; then
    tmp=$(mktemp)
    {
      printf '%s\n' "$first_line"
      printf '%s' "$SHIM"
      printf '%s\n' "$rest"
    } > "$tmp"
    mv "$tmp" "$script"
  else
    # No shebang — prepend shim + original content
    tmp=$(mktemp)
    {
      printf '%s' "$SHIM"
      cat "$script"
    } > "$tmp"
    mv "$tmp" "$script"
  fi

  # Preserve executable bit
  chmod +x "$script" 2>/dev/null || true
  injected=$((injected + 1))
done < <(find "$BIN_DIR" -type f \( -name '*.sh' \) -print0)

echo "  shim: injected into $injected scripts" >&2
