#!/usr/bin/env bash
# Post-build assertions on the generated plugin tree:
#   a) No double-prefix (/lp-lp-... or lp-lp-...)
#   b) Every command file has lp- prefix
#   c) Every agent file has lp- prefix
#   d) Every skill dir has lp- prefix
#   e) No surviving bare /<known-command> references (indicates the rewriter
#      missed a reference somewhere — pure-anchor rules used to skip these
#      inside code fences).
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

# e) Scan for unresolved bare /<known-command> references (missing lp- prefix).
#    Known commands are collected from the source .claude/commands/ tree
#    (top-level + harness/ subdir). Pattern guards against URLs, paths, and
#    already-prefixed refs via word boundaries.
if [ -d "$REPO/.claude/commands" ]; then
  # Build pattern: /(cmd1|cmd2|...) bounded so it doesn't match /lp-cmd1,
  # /some-cmd1, http://...cmd1, or paths like ./scripts/cmd1.
  # Use portable find (no -printf; BSD find on macOS doesn't support it).
  CMD_NAMES=$(
    {
      find "$REPO/.claude/commands" -maxdepth 1 -name '*.md' 2>/dev/null
      find "$REPO/.claude/commands/harness" -maxdepth 1 -name '*.md' 2>/dev/null
    } | while IFS= read -r path; do
      basename "$path" .md
    done | grep -Ev "^${PREFIX}" | sort -u
  )
  if [ -n "$CMD_NAMES" ]; then
    # Join with | to form regex alternation. Pattern matches /<name> with
    # word boundaries that exclude letters/digits/hyphen/colon/slash around it.
    ALTERNATION=$(echo "$CMD_NAMES" | tr '\n' '|' | sed 's/|$//')
    # Using awk for Perl-like look-around via explicit boundary chars.
    UNRESOLVED=$(
      grep -rEn "(^|[^[:alnum:]/:-])/(${ALTERNATION})([^[:alnum:]/:-]|$)" \
        "$DST/commands" "$DST/skills" "$DST/agents" 2>/dev/null \
        | grep -Ev "/${PREFIX}" || true
    )
    if [ -n "$UNRESOLVED" ]; then
      echo "ERROR: unresolved bare slash-command reference(s) in plugin content:" >&2
      echo "$UNRESOLVED" | head -20 >&2
      errors=$((errors + 1))
    fi
  fi
fi

if [ "$errors" -gt 0 ]; then
  echo "  verify-rewrites: $errors error(s)" >&2
  exit 1
fi

echo "  verify-rewrites: ok" >&2
