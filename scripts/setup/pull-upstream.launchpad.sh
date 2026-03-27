#!/usr/bin/env bash
# =============================================================================
# pull-upstream.launchpad.sh — Delta patching from upstream LaunchPad
#
# Computes the diff between the last-synced LaunchPad commit and the current
# LaunchPad main, classifies each changed file against the downstream project,
# and applies selected changes with conflict detection.
#
# Usage:
#   Interactive:  bash scripts/setup/pull-upstream.launchpad.sh
#   Via command:  /pull-launchpad
#
# Requires:
#   - .launchpad/upstream-commit file (written during init or bootstrap)
#   - 'launchpad' git remote pointing to the upstream repo
#   - Clean working tree (no uncommitted changes)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  RED='\033[0;31m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN='' YELLOW='' RED='' BOLD='' RESET=''
fi

info()  { printf "${GREEN}[OK]${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${RESET} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${RESET} %s\n" "$1" >&2; }

# ---------------------------------------------------------------------------
# Step 1: Clean Working Tree Guard
# ---------------------------------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  error "Working tree is dirty. Commit or stash your changes, then re-run."
  error "  /commit — to commit your current work"
  error "  git stash — to temporarily shelve changes"
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: Read Anchor and Fetch
# ---------------------------------------------------------------------------
ANCHOR_FILE=".launchpad/upstream-commit"

if [ ! -f "$ANCHOR_FILE" ]; then
  error "No .launchpad/upstream-commit file found."
  error "This project was likely created before the delta patching rewrite."
  error "To fix: create the file manually with the LaunchPad commit SHA your project was initialized from."
  error "  echo '<sha>' > .launchpad/upstream-commit"
  error "If unsure, use the earliest LaunchPad commit in your git log:"
  error "  git log --oneline --all | tail -1"
  exit 1
fi

OLD_SHA="$(cat "$ANCHOR_FILE" | tr -d '[:space:]')"

if ! git remote get-url launchpad >/dev/null 2>&1; then
  error "No 'launchpad' remote found."
  error "Add it with: git remote add launchpad https://github.com/thinkinghand/launchpad.git"
  exit 1
fi

echo "Fetching updates from LaunchPad..."
git fetch launchpad

NEW_SHA="$(git rev-parse launchpad/main)"

if [ "$OLD_SHA" = "$NEW_SHA" ]; then
  info "Already up to date (anchor: ${OLD_SHA:0:7})."
  exit 0
fi

echo ""
printf "${BOLD}Upstream delta: ${OLD_SHA:0:7} -> ${NEW_SHA:0:7}${RESET}\n"

# ---------------------------------------------------------------------------
# Step 3: Compute Upstream Delta
# ---------------------------------------------------------------------------
CHANGED_FILES=$(git diff --name-status "$OLD_SHA" "$NEW_SHA")

if [ -z "$CHANGED_FILES" ]; then
  info "No file changes in upstream delta."
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 4: Classify (Try-and-Report)
# ---------------------------------------------------------------------------
CLEAN_FILES=()
CONFLICTED=()
NEW_FILES=()
DELETED_FILES=()
SKIPPED=()
MODIFIED_FILES=()

# Collect files by type (here-string avoids subshell variable loss)
while IFS=$'\t' read -r status file; do
  case "$status" in
    A)
      if [ ! -f "$file" ]; then
        NEW_FILES+=("$file")
      fi
      ;;
    D)
      if [ -f "$file" ]; then
        DELETED_FILES+=("$file")
      fi
      ;;
    M)
      if [ ! -f "$file" ]; then
        SKIPPED+=("$file")
      else
        MODIFIED_FILES+=("$file")
      fi
      ;;
  esac
done <<< "$CHANGED_FILES"

# Optimistic fast-path: try all modified files at once
if [ ${#MODIFIED_FILES[@]} -gt 0 ]; then
  FULL_PATCH=$(git diff "$OLD_SHA" "$NEW_SHA" -- "${MODIFIED_FILES[@]}")
  if echo "$FULL_PATCH" | git apply -3 --check 2>/dev/null; then
    # Everything applies cleanly
    CLEAN_FILES=("${MODIFIED_FILES[@]}")
  else
    # Fall back to per-file classification
    for file in "${MODIFIED_FILES[@]}"; do
      PATCH=$(git diff "$OLD_SHA" "$NEW_SHA" -- "$file")
      if echo "$PATCH" | git apply -3 --check 2>/dev/null; then
        CLEAN_FILES+=("$file")
      else
        CONFLICTED+=("$file")
      fi
    done
  fi
fi

# ---------------------------------------------------------------------------
# Step 5: Interactive Presentation
# ---------------------------------------------------------------------------
echo ""

# Compute line stats lazily for display
FILE_STATS=$(git diff --numstat "$OLD_SHA" "$NEW_SHA")

get_stats() {
  local f="$1"
  local added removed
  added=$(echo "$FILE_STATS" | awk -v f="$f" '$3==f {print $1}')
  removed=$(echo "$FILE_STATS" | awk -v f="$f" '$3==f {print $2}')
  if [ -n "$added" ] && [ -n "$removed" ]; then
    echo "+${added}/-${removed}"
  elif [ -n "$added" ]; then
    echo "+${added}"
  else
    echo ""
  fi
}

# Build numbered list for selection
ALL_ITEMS=()
ITEM_CATEGORIES=()
INDEX=1

if [ ${#NEW_FILES[@]} -gt 0 ]; then
  printf "${BOLD}NEW (safe to add):${RESET}\n"
  for file in "${NEW_FILES[@]}"; do
    stats=$(get_stats "$file")
    printf "  [%d] %-50s (%s lines)\n" "$INDEX" "$file" "$stats"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("NEW")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#CLEAN_FILES[@]} -gt 0 ]; then
  printf "${BOLD}CLEAN (applies cleanly, local edits preserved):${RESET}\n"
  for file in "${CLEAN_FILES[@]}"; do
    stats=$(get_stats "$file")
    printf "  [%d] %-50s (%s lines)\n" "$INDEX" "$file" "$stats"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("CLEAN")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#CONFLICTED[@]} -gt 0 ]; then
  printf "${BOLD}${YELLOW}CONFLICT (needs manual resolution):${RESET}\n"
  for file in "${CONFLICTED[@]}"; do
    stats=$(get_stats "$file")
    printf "  [%d] %-50s (%s lines, patch cannot apply cleanly)\n" "$INDEX" "$file" "$stats"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("CONFLICT")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#DELETED_FILES[@]} -gt 0 ]; then
  printf "${BOLD}DELETED upstream:${RESET}\n"
  for file in "${DELETED_FILES[@]}"; do
    printf "  [%d] %s\n" "$INDEX" "$file"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("DELETED")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#SKIPPED[@]} -gt 0 ]; then
  printf "${YELLOW}Skipped (you removed these files locally):${RESET}\n"
  for file in "${SKIPPED[@]}"; do
    printf "  - %s\n" "$file"
  done
  echo ""
fi

TOTAL_ITEMS=${#ALL_ITEMS[@]}

if [ "$TOTAL_ITEMS" -eq 0 ]; then
  info "No applicable changes (all upstream changes are to files you removed)."
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  exit 0
fi

# ---------------------------------------------------------------------------
# User selection
# ---------------------------------------------------------------------------
if [ -t 0 ]; then
  printf "${BOLD}Apply which?${RESET} [a]ll, [n]ew, [c]lean, comma-separated numbers, or [q]uit: "
  read -r SELECTION

  SELECTION=$(echo "$SELECTION" | tr '[:upper:]' '[:lower:]' | tr -d ' ')

  SELECTED_INDICES=()

  case "$SELECTION" in
    q|quit|"")
      echo "No changes applied."
      exit 0
      ;;
    a|all)
      for i in $(seq 0 $((TOTAL_ITEMS - 1))); do
        SELECTED_INDICES+=("$i")
      done
      ;;
    n|new)
      for i in $(seq 0 $((TOTAL_ITEMS - 1))); do
        [ "${ITEM_CATEGORIES[$i]}" = "NEW" ] && SELECTED_INDICES+=("$i")
      done
      ;;
    c|clean)
      for i in $(seq 0 $((TOTAL_ITEMS - 1))); do
        [ "${ITEM_CATEGORIES[$i]}" = "CLEAN" ] && SELECTED_INDICES+=("$i")
      done
      ;;
    *)
      # Parse comma-separated numbers and category shortcuts
      IFS=',' read -ra PARTS <<< "$SELECTION"
      for part in "${PARTS[@]}"; do
        part=$(echo "$part" | tr -d ' ')
        case "$part" in
          n|new)
            for i in $(seq 0 $((TOTAL_ITEMS - 1))); do
              [ "${ITEM_CATEGORIES[$i]}" = "NEW" ] && SELECTED_INDICES+=("$i")
            done
            ;;
          c|clean)
            for i in $(seq 0 $((TOTAL_ITEMS - 1))); do
              [ "${ITEM_CATEGORIES[$i]}" = "CLEAN" ] && SELECTED_INDICES+=("$i")
            done
            ;;
          *)
            if [[ "$part" =~ ^[0-9]+$ ]] && [ "$part" -ge 1 ] && [ "$part" -le "$TOTAL_ITEMS" ]; then
              SELECTED_INDICES+=("$((part - 1))")
            else
              warn "Ignoring invalid selection: $part"
            fi
            ;;
        esac
      done
      ;;
  esac

  # Deduplicate
  SELECTED_INDICES=($(printf '%s\n' "${SELECTED_INDICES[@]}" | sort -un))
else
  # Non-interactive: apply all
  for i in $(seq 0 $((TOTAL_ITEMS - 1))); do
    SELECTED_INDICES+=("$i")
  done
fi

if [ ${#SELECTED_INDICES[@]} -eq 0 ]; then
  echo "No changes selected."
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 6: Apply and Update Anchor
# ---------------------------------------------------------------------------

# Backup tag for rollback
git tag -d _pre-upstream-sync 2>/dev/null || true
git tag _pre-upstream-sync

# Trap for cleanup on failure/interrupt
trap 'echo ""; warn "Interrupted. Rolling back..."; git checkout -- . 2>/dev/null; git tag -d _pre-upstream-sync 2>/dev/null || true; echo "Rolled back. Re-run to try again."' INT TERM

APPLIED_FILES=()
FAILED_FILES=()
HAS_CONFLICTS=false

for idx in "${SELECTED_INDICES[@]}"; do
  file="${ALL_ITEMS[$idx]}"
  category="${ITEM_CATEGORIES[$idx]}"

  case "$category" in
    NEW)
      mkdir -p "$(dirname "$file")"
      git show "$NEW_SHA:$file" > "$file"
      APPLIED_FILES+=("$file")
      info "Added: $file"
      ;;
    CLEAN)
      PATCH=$(git diff "$OLD_SHA" "$NEW_SHA" -- "$file")
      if echo "$PATCH" | git apply -3 2>/dev/null; then
        APPLIED_FILES+=("$file")
        info "Patched: $file"
      else
        FAILED_FILES+=("$file")
        error "Failed to apply: $file (retrieve manually: git show $NEW_SHA:$file)"
      fi
      ;;
    CONFLICT)
      PATCH=$(git diff "$OLD_SHA" "$NEW_SHA" -- "$file")
      if echo "$PATCH" | git apply -3 2>/dev/null; then
        APPLIED_FILES+=("$file")
        info "Patched (unexpectedly clean): $file"
      else
        # Try without -3 to get partial application
        warn "Conflict in: $file — resolve manually or retrieve with: git show $NEW_SHA:$file"
        FAILED_FILES+=("$file")
        HAS_CONFLICTS=true
      fi
      ;;
    DELETED)
      rm -f "$file"
      APPLIED_FILES+=("$file")
      info "Deleted: $file"
      ;;
  esac
done

# Remove trap
trap - INT TERM

echo ""

# Stage applied files
for file in "${APPLIED_FILES[@]}"; do
  git add "$file" 2>/dev/null || true
done

# Anchor update policy: advance only when all files are resolved
RESOLVED=$(( ${#APPLIED_FILES[@]} + ${#FAILED_FILES[@]} ))
if [ "$RESOLVED" -eq "$TOTAL_ITEMS" ] && [ ${#FAILED_FILES[@]} -eq 0 ]; then
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  git add "$ANCHOR_FILE"
  info "Anchor updated to ${NEW_SHA:0:7} (all files resolved)."
elif [ "$RESOLVED" -eq "$TOTAL_ITEMS" ]; then
  # All files attempted but some failed — still advance since user saw everything
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  git add "$ANCHOR_FILE"
  warn "Anchor updated to ${NEW_SHA:0:7} (${#FAILED_FILES[@]} file(s) had conflicts — resolve manually)."
else
  warn "Anchor NOT updated (${RESOLVED}/${TOTAL_ITEMS} files processed)."
  echo "  Skipped files will reappear on next sync."
  echo "  To advance manually: echo '$NEW_SHA' > $ANCHOR_FILE"
fi

echo ""
echo "Review staged changes: git diff --cached"
echo "If something went wrong: git checkout -- . && git tag -d _pre-upstream-sync"

# Exit with code 2 if there are unresolved conflicts (for Claude command handoff)
if [ "$HAS_CONFLICTS" = true ]; then
  echo ""
  echo "CONFLICTS: ${FAILED_FILES[*]}"
  echo "OLD_SHA=$OLD_SHA"
  echo "NEW_SHA=$NEW_SHA"
  exit 2
fi

exit 0
