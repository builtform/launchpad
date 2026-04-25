#!/usr/bin/env bash
# Shared Step 0 implementation — used by both harness (full) and L2 (lite) commands.
#
# Single source of truth prevents drift. The "Lite is a strict subset of Full"
# contract is enforced here mechanically: L2 commands call this with --mode=lite
# and a --require list; they do NOT implement their own prereq logic inline.
#
# Usage:
#   Full mode (harness commands — /lp-kickoff, /lp-define, /lp-plan, /lp-build):
#     plugin-prereq-check.sh --mode=full --command=lp-kickoff
#
#   Lite mode (L2 commands — /lp-commit, /lp-review, /lp-ship, etc.):
#     plugin-prereq-check.sh --mode=lite --command=lp-commit \
#       --require=.launchpad/config.yml,.launchpad/agents.yml
#
# Exit codes:
#   0 — prerequisites satisfied; proceed
#   1 — missing prerequisite the caller must handle
#   2 — fatal error (bad invocation, corrupt config)
#
# Performance budget: <200ms warm, <500ms cold.
# Session cache keyed on mtime of config.yml + top-level manifests lives at
# $LP_CACHE_DIR (default: /tmp/lp-prereq-cache-$USER) and is checked before
# re-running detection.

set -euo pipefail

# --- Arg parsing ---
MODE=""
COMMAND=""
REQUIRE=""
REPO_ROOT="${LP_REPO_ROOT:-$(pwd)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode=*)     MODE="${1#--mode=}"; shift ;;
    --command=*)  COMMAND="${1#--command=}"; shift ;;
    --require=*)  REQUIRE="${1#--require=}"; shift ;;
    --repo-root=*) REPO_ROOT="${1#--repo-root=}"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$MODE" || -z "$COMMAND" ]]; then
  echo "usage: $0 --mode=full|lite --command=<name> [--require=path1,path2] [--repo-root=PATH]" >&2
  exit 2
fi

if [[ "$MODE" != "full" && "$MODE" != "lite" ]]; then
  echo "invalid --mode=$MODE (expected 'full' or 'lite')" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="${LP_CACHE_DIR:-/tmp/lp-prereq-cache-$USER}"
mkdir -p "$CACHE_DIR"

# --- Session cache ---
# Key: sha256 of concatenated mtimes for config.yml + top-level manifests.
# Small enough that recomputing it is cheap; skipping the full detection when
# nothing changed is the real win.
compute_cache_key() {
  local key=""
  for f in \
    "$REPO_ROOT/.launchpad/config.yml" \
    "$REPO_ROOT/package.json" \
    "$REPO_ROOT/pyproject.toml" \
    "$REPO_ROOT/Cargo.toml" \
    "$REPO_ROOT/go.mod" \
    "$REPO_ROOT/Gemfile" \
    "$REPO_ROOT/composer.json"
  do
    if [[ -f "$f" ]]; then
      # stat -f for macOS, stat -c for Linux; both produce mtime.
      local mtime
      if mtime=$(stat -f %m "$f" 2>/dev/null); then :;
      else mtime=$(stat -c %Y "$f" 2>/dev/null || echo "0"); fi
      key+="$f:$mtime;"
    fi
  done
  echo -n "$key" | shasum -a 256 | cut -d' ' -f1
}

CACHE_KEY="$(compute_cache_key)"
CACHE_FILE="$CACHE_DIR/$COMMAND-$MODE-$CACHE_KEY"

# --- Lite mode: create-if-missing for required state files ---
# Lite is strictly a subset of Full. It does NOT run the detect→classify→
# present→scaffold protocol. It only ensures the caller's required files
# exist (create with empty defaults if absent). Any more than this belongs
# in Full mode, called from a harness command.
lite_check() {
  local missing=()
  IFS=',' read -ra REQS <<< "$REQUIRE"
  for req in "${REQS[@]}"; do
    req="$(echo "$req" | xargs)"  # trim whitespace
    [[ -z "$req" ]] && continue
    local full_path="$REPO_ROOT/$req"
    if [[ ! -e "$full_path" ]]; then
      missing+=("$req")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Step 0 (lite) — missing required state for /$COMMAND:" >&2
    for m in "${missing[@]}"; do
      echo "  - $m" >&2
    done
    echo "" >&2
    echo "Run /lp-define to seed canonical state, or create these files manually." >&2
    return 1
  fi
  return 0
}

# --- Full mode: detect → classify → present → scaffold ---
# Harness commands get the rich prereq experience. v1 implementation is a
# lightweight wrapper around plugin-stack-detector.py; the interactive
# classify+scaffold layer is built on top of this in calling commands.
full_check() {
  local detect_out
  if ! detect_out=$(python3 "$SCRIPT_DIR/plugin-stack-detector.py" 2>&1); then
    echo "Step 0 (full) — stack detection failed:" >&2
    echo "$detect_out" >&2
    return 2
  fi

  # For now, full mode just emits the detection report to stderr so the
  # harness command can use it. Interactive menu lives in the command prose
  # itself.
  echo "$detect_out" >&2

  # Also check config.yml parses
  if ! python3 "$SCRIPT_DIR/plugin-config-loader.py" --strict > /dev/null 2>&1; then
    echo "Step 0 (full) — .launchpad/config.yml has errors; run /lp-define to reset or fix manually." >&2
    return 1
  fi

  return 0
}

# --- Cache hit fast path ---
if [[ -f "$CACHE_FILE" ]]; then
  # Cache hit — previous run with same mtime set succeeded.
  exit 0
fi

# --- Dispatch ---
if [[ "$MODE" == "lite" ]]; then
  if lite_check; then
    touch "$CACHE_FILE"
    exit 0
  else
    exit 1
  fi
fi

if full_check; then
  touch "$CACHE_FILE"
  exit 0
fi
exit 1
