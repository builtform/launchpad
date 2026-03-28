#!/usr/bin/env bash
# =============================================================================
# pull-upstream.launchpad.sh — Delta patching from upstream LaunchPad
#
# Computes the diff between the last-synced LaunchPad commit and the current
# LaunchPad main, classifies each changed file via git hash comparison,
# and applies selected changes with direct file copy (no git apply).
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
CHANGED_FILES=$(git diff --no-renames --name-status "$OLD_SHA" "$NEW_SHA")

if [ -z "$CHANGED_FILES" ]; then
  info "No file changes in upstream delta."
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 3.5: Load Exclusion Manifest
# ---------------------------------------------------------------------------
# init-project.sh writes .launchpad/init-touched-files listing every file it
# customized. These files diverge by design and should not appear in sync
# results. Exclusions apply to A (added) and M (modified) only — upstream
# deletions (D) are always shown.

EXCLUDED_PATHS=()
EXCLUDED_MANIFEST=".launchpad/init-touched-files"
if [ -f "$EXCLUDED_MANIFEST" ]; then
  while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" == \#* ]] && continue
    EXCLUDED_PATHS+=("$line")
  done < "$EXCLUDED_MANIFEST"
fi

is_excluded() {
  local file="$1"
  # Glob patterns for template source files (deleted by init, never in manifest)
  case "${file##*/}" in
    *.template.md|*.template) return 0 ;;
  esac
  # Directory-level exclusions (LaunchPad-internal content, not for downstream)
  case "$file" in
    docs/reports/*|docs/plans/*|docs/skills-catalog/*) return 0 ;;
  esac
  # Check exact paths from manifest
  local p
  for p in "${EXCLUDED_PATHS[@]}"; do
    [ "$file" = "$p" ] && return 0
  done
  return 1
}

# ---------------------------------------------------------------------------
# Step 4: Classify via Dual Hash Comparison (OLD + NEW upstream)
# ---------------------------------------------------------------------------
CLEAN_FILES=()
CONFLICTED=()
NEW_FILES=()
DELETED_FILES=()
SKIPPED=()

while IFS=$'\t' read -r status file; do
  # Exclusions apply to A and M only — deletions always shown
  if [ "$status" != "D" ] && is_excluded "$file"; then
    continue
  fi

  case "$status" in
    A)
      if [ ! -f "$file" ]; then
        # Upstream added, downstream doesn't have it
        NEW_FILES+=("$file")
      else
        # Upstream added, downstream already has it — compare against NEW upstream
        NEW_HASH=$(git rev-parse "$NEW_SHA:$file" 2>/dev/null || echo "none")
        CURRENT_HASH=$(git hash-object "$file" 2>/dev/null || echo "none")
        if [ "$NEW_HASH" = "$CURRENT_HASH" ]; then
          # Already matches new upstream — silently skip
          continue
        else
          # Downstream has this file but with different content.
          # Check if upstream is purely additive — every line in downstream
          # also exists in upstream, upstream just added more. This catches
          # files copied from an older upstream version.
          REMOVED_LINES=$(diff <(cat "$file") <(git show "$NEW_SHA:$file") | grep -c '^< ' || true)
          if [ "$REMOVED_LINES" -eq 0 ]; then
            # Upstream only added lines on top of what downstream has — safe to overwrite
            CLEAN_FILES+=("$file")
          else
            # Upstream changed or removed downstream content — genuine conflict
            CONFLICTED+=("$file")
          fi
        fi
      fi
      ;;
    D)
      if [ -f "$file" ]; then
        DELETED_FILES+=("$file")
      fi
      ;;
    M)
      if [ ! -f "$file" ]; then
        # Upstream modified, downstream removed it
        SKIPPED+=("$file")
      else
        # Step A: Does downstream already match NEW upstream?
        NEW_HASH=$(git rev-parse "$NEW_SHA:$file" 2>/dev/null || echo "none")
        CURRENT_HASH=$(git hash-object "$file" 2>/dev/null || echo "none")
        if [ "$NEW_HASH" = "$CURRENT_HASH" ]; then
          # Already up to date — silently skip
          continue
        fi

        # Step B: Does downstream match OLD upstream? (never modified)
        OLD_HASH=$(git rev-parse "$OLD_SHA:$file" 2>/dev/null || echo "none")
        if [ "$OLD_HASH" = "$CURRENT_HASH" ]; then
          # Downstream never modified this file — safe to update
          CLEAN_FILES+=("$file")
        else
          # Downstream modified AND doesn't match new upstream — conflict
          CONFLICTED+=("$file")
        fi
      fi
      ;;
    *)
      warn "Unknown git status '$status' for $file — skipping"
      ;;
  esac
done <<< "$CHANGED_FILES"

# ---------------------------------------------------------------------------
# Step 5: Structured Report
# ---------------------------------------------------------------------------
echo ""

# Compute line stats lazily for display
FILE_STATS=$(git diff --numstat "$OLD_SHA" "$NEW_SHA")

get_stats() {
  local f="$1"
  local added removed
  added=$(echo "$FILE_STATS" | awk -v f="$f" '$3==f {print $1}')
  removed=$(echo "$FILE_STATS" | awk -v f="$f" '$3==f {print $2}')
  if [ -n "$added" ] && [ "$removed" != "0" ] && [ -n "$removed" ]; then
    echo "+${added}/-${removed} lines"
  elif [ -n "$added" ]; then
    echo "+${added} lines"
  else
    echo ""
  fi
}

# Box-drawing header
printf "════════════════════════════════════════════════════\n"
printf "  LaunchPad Upstream Changes\n"
printf "  ${OLD_SHA:0:7} → ${NEW_SHA:0:7}\n"
printf "════════════════════════════════════════════════════\n"
echo ""

# Build numbered list for selection
ALL_ITEMS=()
ITEM_CATEGORIES=()
INDEX=1

if [ ${#NEW_FILES[@]} -gt 0 ]; then
  printf "── NEW (upstream added, you don't have) ───────────\n"
  for file in "${NEW_FILES[@]}"; do
    stats=$(get_stats "$file")
    printf "  [%d]  %-45s %s\n" "$INDEX" "$file" "$stats"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("NEW")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#CLEAN_FILES[@]} -gt 0 ]; then
  printf "── CLEAN (upstream updated, you haven't modified) ─\n"
  for file in "${CLEAN_FILES[@]}"; do
    stats=$(get_stats "$file")
    printf "  [%d]  %-45s %s\n" "$INDEX" "$file" "$stats"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("CLEAN")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#CONFLICTED[@]} -gt 0 ]; then
  printf "── CONFLICT (both sides changed) ──────────────────\n"
  for file in "${CONFLICTED[@]}"; do
    printf "  [%d]  %-45s you customized · upstream also changed\n" "$INDEX" "$file"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("CONFLICT")
    ((INDEX++))
  done
  printf "       ℹ View upstream:  git show ${NEW_SHA:0:7}:<file>\n"
  printf "       ℹ View old:       git show ${OLD_SHA:0:7}:<file>\n"
  echo ""
fi

if [ ${#DELETED_FILES[@]} -gt 0 ]; then
  printf "── DELETED (upstream removed) ─────────────────────\n"
  for file in "${DELETED_FILES[@]}"; do
    printf "  [%d]  %s\n" "$INDEX" "$file"
    ALL_ITEMS+=("$file")
    ITEM_CATEGORIES+=("DELETED")
    ((INDEX++))
  done
  echo ""
fi

if [ ${#SKIPPED[@]} -gt 0 ]; then
  printf "── SKIPPED (upstream updated, you removed locally) ─\n"
  for file in "${SKIPPED[@]}"; do
    printf "   •  %s\n" "$file"
  done
  echo ""
fi

# Summary line
printf "════════════════════════════════════════════════════\n"
printf "  %d NEW · %d CLEAN · %d CONFLICT · %d DELETED · %d SKIPPED\n" \
  "${#NEW_FILES[@]}" "${#CLEAN_FILES[@]}" "${#CONFLICTED[@]}" "${#DELETED_FILES[@]}" "${#SKIPPED[@]}"
printf "════════════════════════════════════════════════════\n"
echo ""

TOTAL_ITEMS=${#ALL_ITEMS[@]}

if [ "$TOTAL_ITEMS" -eq 0 ]; then
  info "No applicable changes (upstream changes are to excluded or already-synced files)."
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
  # Non-interactive: report only, do not apply anything.
  # The /pull-launchpad command (Claude) handles user interaction and approval.
  echo "Non-interactive mode — report complete. Use /pull-launchpad for guided approval."
  exit 0
fi

if [ ${#SELECTED_INDICES[@]} -eq 0 ]; then
  echo "No changes selected."
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 6: Apply via Direct File Copy and Update Anchor
# ---------------------------------------------------------------------------

# Track files we create (for rollback cleanup)
CREATED_FILES=()

# Trap for cleanup on failure/interrupt
rollback() {
  echo ""
  warn "Interrupted. Rolling back..."
  git checkout -- . 2>/dev/null
  # Remove NEW files that were created during this run
  for f in "${CREATED_FILES[@]}"; do
    rm -f "$f" 2>/dev/null
  done
  echo "Rolled back. Re-run to try again."
}
trap rollback INT TERM

# Propagate executable permissions from upstream
propagate_permissions() {
  local file="$1"
  if git ls-tree "$NEW_SHA" -- "$file" | grep -q '^100755'; then
    chmod +x "$file"
  else
    chmod -x "$file"
  fi
}

APPLIED_FILES=()

SELECTED_ALL=false
if [ ${#SELECTED_INDICES[@]} -eq "$TOTAL_ITEMS" ]; then
  SELECTED_ALL=true
fi

for idx in "${SELECTED_INDICES[@]}"; do
  file="${ALL_ITEMS[$idx]}"
  category="${ITEM_CATEGORIES[$idx]}"

  case "$category" in
    NEW)
      mkdir -p "$(dirname "$file")"
      git show "$NEW_SHA:$file" > "$file"
      propagate_permissions "$file"
      CREATED_FILES+=("$file")
      APPLIED_FILES+=("$file")
      info "Added: $file"
      ;;
    CLEAN)
      git show "$NEW_SHA:$file" > "$file"
      propagate_permissions "$file"
      APPLIED_FILES+=("$file")
      info "Updated: $file"
      ;;
    CONFLICT)
      warn "Skipping CONFLICT file: $file"
      echo "  Retrieve upstream version with: git show $NEW_SHA:$file"
      ;;
    DELETED)
      rm -f -- "$file"
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

# Anchor update policy: advance only when ALL files processed AND zero CONFLICT files
if [ "$SELECTED_ALL" = true ] && [ ${#CONFLICTED[@]} -eq 0 ]; then
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  git add "$ANCHOR_FILE"
  info "Anchor updated to ${NEW_SHA:0:7} (all files resolved, zero conflicts)."
else
  if [ ${#CONFLICTED[@]} -gt 0 ]; then
    warn "Anchor NOT updated (${#CONFLICTED[@]} CONFLICT file(s) in delta)."
    echo "  Resolve conflicts and re-run, or advance manually: echo '$NEW_SHA' > $ANCHOR_FILE"
  else
    warn "Anchor NOT updated (not all files were selected)."
    echo "  Skipped files will reappear on next sync."
    echo "  To advance manually: echo '$NEW_SHA' > $ANCHOR_FILE"
  fi
fi

echo ""
echo "Review staged changes: git diff --cached"
ROLLBACK_CMD="git checkout -- ."
if [ ${#CREATED_FILES[@]} -gt 0 ]; then
  ROLLBACK_CMD="$ROLLBACK_CMD && rm -f ${CREATED_FILES[*]}"
fi
echo "If something went wrong: $ROLLBACK_CMD"

exit 0
