#!/usr/bin/env bash
# Post-build assertion: no bare slash-command refs survived in plugin content.
#
# Scans plugin/commands/, plugin/skills/, plugin/agents/ for bare /<known-cmd>
# references (outside code fences). A surviving bare ref suggests the Python
# rewriter missed something.
set -euo pipefail

DST="${1:?usage: $0 <plugin dir>}"
REPO="${2:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
PREFIX="${3:-lp-}"

errors=0

# Hard-fail assertions
# a) No double-prefix (/lp-lp-... or lp-lp-...)
if grep -rEn '/lp-lp-|\blp-lp-' "$DST/commands" "$DST/skills" "$DST/agents" 2>/dev/null; then
  echo "ERROR: double-prefix detected" >&2
  errors=$((errors + 1))
fi

# b) Every command file has lp- prefix
while IFS= read -r -d '' f; do
  base=$(basename "$f")
  if [[ "$base" != ${PREFIX}* ]]; then
    echo "ERROR: command $f missing ${PREFIX} prefix" >&2
    errors=$((errors + 1))
  fi
done < <(find "$DST/commands" -maxdepth 1 -name '*.md' -print0 2>/dev/null)

# c) Every agent file has lp- prefix
while IFS= read -r -d '' f; do
  base=$(basename "$f")
  if [[ "$base" != ${PREFIX}* ]]; then
    echo "ERROR: agent $f missing ${PREFIX} prefix" >&2
    errors=$((errors + 1))
  fi
done < <(find "$DST/agents" -maxdepth 1 -name '*.md' -print0 2>/dev/null)

# d) Every skill dir has lp- prefix
while IFS= read -r -d '' d; do
  base=$(basename "$d")
  if [[ "$base" != ${PREFIX}* ]]; then
    echo "ERROR: skill dir $d missing ${PREFIX} prefix" >&2
    errors=$((errors + 1))
  fi
done < <(find "$DST/skills" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [ "$errors" -gt 0 ]; then
  echo "  verify-rewrites: $errors error(s)" >&2
  exit 1
fi

echo "  verify-rewrites: ok" >&2
