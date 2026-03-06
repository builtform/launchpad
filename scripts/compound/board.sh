#!/usr/bin/env bash
# board.sh — Kanban board renderer for prd.json
# Compatible with macOS bash 3.x (no mapfile, no bash 4+ features)
#
# Usage:
#   board.sh [prd.json]              # ASCII mode (terminal)
#   board.sh --md [prd.json] [out]   # Markdown mode (file)
#   board.sh --summary [prd.json]    # Summary mode (one-line)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Parse mode flag ──────────────────────────────────────────────
MODE="ascii"
case "${1:-}" in
  --md)      MODE="md";      shift ;;
  --summary) MODE="summary"; shift ;;
esac

# ── Resolve PRD path ─────────────────────────────────────────────
PRD="${1:-prd.json}"

# For markdown mode, optional second arg is output path
MD_OUT="${2:-$PROJECT_ROOT/docs/tasks/board.md}"

# ── Guards ───────────────────────────────────────────────────────
if [[ ! -f "$PRD" ]]; then
  echo "No prd.json found at: $PRD"
  exit 0
fi

if ! command -v jq &>/dev/null; then
  echo "jq is required but not installed."
  exit 1
fi

# ── Backward compatibility ───────────────────────────────────────
# If tasks lack 'status' field, derive from 'passes'
PRD_DATA=$(jq '
  if (.tasks | length == 0) then .
  elif (.tasks[0] | has("status")) then .
  else .tasks |= [.[] | . + {status: (if .passes then "done" else "pending" end)}]
  end
' "$PRD") || { echo "Failed to parse $PRD"; exit 0; }

# Helper: query PRD_DATA instead of file directly
prd_jq() {
  echo "$PRD_DATA" | jq "$@"
}

prd_jq_r() {
  echo "$PRD_DATA" | jq -r "$@"
}

# ── ASCII Mode ───────────────────────────────────────────────────
render_ascii() {
  NO_COLOR="${NO_COLOR:-}"
  export TERM="${TERM:-xterm}"

  # Colors
  RESET="" BOLD="" DIM="" GREEN="" YELLOW="" RED="" CYAN="" WHITE="" BG_BLUE=""
  if [[ -z "$NO_COLOR" ]]; then
    RESET=$'\033[0m'
    BOLD=$'\033[1m'
    DIM=$'\033[2m'
    GREEN=$'\033[32m'
    YELLOW=$'\033[33m'
    RED=$'\033[31m'
    CYAN=$'\033[36m'
    WHITE=$'\033[37m'
    BG_BLUE=$'\033[44m'
  fi

  # Read all data in one jq call
  DATA=$(prd_jq_r '
    def ids_by(s): [.tasks[] | select(.status == s) | .id] | join(",");
    def count_by(s): [.tasks[] | select(.status == s)] | length;
    [
      (.branchName // "unknown"),
      (.startedAt // ""),
      (.tasks | length | tostring),
      (count_by("pending") | tostring),
      (count_by("in_progress") | tostring),
      (count_by("done") | tostring),
      (count_by("failed") | tostring),
      ids_by("pending"),
      ids_by("in_progress"),
      ids_by("done"),
      ids_by("failed"),
      ([.tasks[] | select(.status == "in_progress")][0] // null | if . then "\(.id) — \(.title)" else "" end)
    ] | .[]
  ') || true

  # Parse into variables (line by line)
  i=0
  while IFS= read -r line; do
    case $i in
      0) BRANCH="$line" ;;
      1) STARTED="$line" ;;
      2) TOTAL="$line" ;;
      3) PENDING_COUNT="$line" ;;
      4) IN_PROG_COUNT="$line" ;;
      5) DONE_COUNT="$line" ;;
      6) FAILED_COUNT="$line" ;;
      7) PENDING_CSV="$line" ;;
      8) INPROG_CSV="$line" ;;
      9) DONE_CSV="$line" ;;
      10) FAILED_CSV="$line" ;;
      11) CURRENT_TASK="$line" ;;
    esac
    i=$((i + 1))
  done <<< "$DATA"

  # Split CSV into arrays (bash 3 compatible)
  IFS=',' read -ra PENDING_IDS <<< "${PENDING_CSV:-}"
  IFS=',' read -ra INPROG_IDS <<< "${INPROG_CSV:-}"
  IFS=',' read -ra DONE_IDS <<< "${DONE_CSV:-}"
  IFS=',' read -ra FAILED_IDS <<< "${FAILED_CSV:-}"

  # Handle empty arrays (bash read creates single empty element)
  if [[ -z "${PENDING_IDS[0]:-}" ]]; then PENDING_IDS=(); fi
  if [[ -z "${INPROG_IDS[0]:-}" ]]; then INPROG_IDS=(); fi
  if [[ -z "${DONE_IDS[0]:-}" ]]; then DONE_IDS=(); fi
  if [[ -z "${FAILED_IDS[0]:-}" ]]; then FAILED_IDS=(); fi

  # Elapsed time
  ELAPSED="--:--:--"
  if [[ -n "$STARTED" ]]; then
    START_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${STARTED%Z}" "+%s" 2>/dev/null || date -d "$STARTED" "+%s" 2>/dev/null || echo "")
    if [[ -n "$START_EPOCH" ]]; then
      NOW_EPOCH=$(date "+%s")
      ELAPSED_SECS=$((NOW_EPOCH - START_EPOCH))
      ELAPSED=$(printf "%02d:%02d:%02d" $((ELAPSED_SECS/3600)) $(((ELAPSED_SECS%3600)/60)) $((ELAPSED_SECS%60)))
    fi
  fi

  # Terminal width
  COLS=$(tput cols 2>/dev/null || echo 100)
  if [ "$COLS" -lt 60 ]; then COLS=60; fi

  # Progress bar
  progress_bar() {
    local done_n=$1 total_n=$2 width=30
    local pct=0 filled=0
    if [ "$total_n" -gt 0 ]; then
      pct=$((done_n * 100 / total_n))
      filled=$((done_n * width / total_n))
    fi
    local empty=$((width - filled))
    local bar=""
    local j=0
    while [ $j -lt $filled ]; do bar="${bar}█"; j=$((j+1)); done
    j=0
    while [ $j -lt $empty ]; do bar="${bar}░"; j=$((j+1)); done
    echo -n "[${bar}] ${done_n}/${total_n} (${pct}%)"
  }

  # Get task title by ID
  get_title() {
    prd_jq_r --arg id "$1" '.tasks[] | select(.id == $id) | .title'
  }

  # Header (no clear — let the caller decide)
  echo ""
  INNER=$((COLS - 4))
  printf "  ${BG_BLUE}${WHITE}${BOLD} %-${INNER}s${RESET}\n" "Kanban Board: $BRANCH"
  printf "  ${BG_BLUE}${WHITE} %-${INNER}s${RESET}\n" "Elapsed: $ELAPSED · Tasks: $TOTAL · $(date '+%H:%M:%S')"
  echo ""

  # Column config
  COL_W=22
  if [ "$COLS" -gt 100 ]; then COL_W=26; fi

  # Column headers
  printf "  ${DIM}%-${COL_W}s${RESET}" "PENDING ($PENDING_COUNT)"
  printf "  ${YELLOW}${BOLD}%-${COL_W}s${RESET}" "WORKING ($IN_PROG_COUNT)"
  printf "  ${GREEN}${BOLD}%-${COL_W}s${RESET}" "DONE ($DONE_COUNT)"
  printf "  ${RED}${BOLD}%-${COL_W}s${RESET}\n" "FAILED ($FAILED_COUNT)"

  # Separator
  printf "  ${DIM}"
  printf '%.0s─' $(seq 1 $((COL_W)))
  printf "  "
  printf '%.0s─' $(seq 1 $((COL_W)))
  printf "  "
  printf '%.0s─' $(seq 1 $((COL_W)))
  printf "  "
  printf '%.0s─' $(seq 1 $((COL_W)))
  printf "${RESET}\n"

  # Compute max rows
  MAX_ROWS=${#PENDING_IDS[@]}
  if [ ${#INPROG_IDS[@]} -gt $MAX_ROWS ]; then MAX_ROWS=${#INPROG_IDS[@]}; fi
  if [ ${#DONE_IDS[@]} -gt $MAX_ROWS ]; then MAX_ROWS=${#DONE_IDS[@]}; fi
  if [ ${#FAILED_IDS[@]} -gt $MAX_ROWS ]; then MAX_ROWS=${#FAILED_IDS[@]}; fi

  # Render task cell
  render_cell() {
    local id="$1" color="$2"
    if [[ -z "$id" ]]; then
      printf "  %-${COL_W}s" ""
      return
    fi
    local title
    title=$(get_title "$id")
    local max_t=$((COL_W - 8))
    if [ ${#title} -gt $max_t ]; then
      title="${title:0:$((max_t-2))}.."
    fi
    printf "  ${color}%-6s ${BOLD}%-$((COL_W - 8))s${RESET}" "$id" "$title"
  }

  # Render rows
  row=0
  while [ $row -lt $MAX_ROWS ]; do
    render_cell "${PENDING_IDS[$row]:-}" "$DIM"
    render_cell "${INPROG_IDS[$row]:-}" "$YELLOW"
    render_cell "${DONE_IDS[$row]:-}" "$GREEN"
    render_cell "${FAILED_IDS[$row]:-}" "$RED"
    echo ""
    row=$((row + 1))
  done

  # Footer
  echo ""
  printf "  ${BOLD}Progress:${RESET} "
  progress_bar "$DONE_COUNT" "$TOTAL"
  echo ""

  if [[ -n "${CURRENT_TASK:-}" ]]; then
    printf "  ${BOLD}Working:${RESET}  ${YELLOW}%s${RESET}\n" "$CURRENT_TASK"
  else
    printf "  ${BOLD}Working:${RESET}  ${DIM}waiting...${RESET}\n"
  fi

  echo ""
}

# ── Markdown Mode ────────────────────────────────────────────────
render_md() {
  local out="$MD_OUT"

  BRANCH=$(prd_jq_r '.branchName // "unknown"')
  TOTAL=$(prd_jq '.tasks | length')
  DONE_COUNT=$(prd_jq '[.tasks[] | select(.status == "done")] | length')
  CURRENT=$(prd_jq_r '[.tasks[] | select(.status == "in_progress")][0] // null | if . then "\(.id) — \(.title)" else "waiting..." end')

  # Progress percentage
  PCT=0
  if [ "$TOTAL" -gt 0 ]; then PCT=$((DONE_COUNT * 100 / TOTAL)); fi

  # Build progress bar (text-based for markdown)
  BAR_W=20
  local divisor=$TOTAL
  if [ "$divisor" -le 0 ]; then divisor=1; fi
  FILLED=$((DONE_COUNT * BAR_W / divisor))
  EMPTY=$((BAR_W - FILLED))
  BAR=""
  j=0; while [ $j -lt $FILLED ]; do BAR="${BAR}█"; j=$((j+1)); done
  j=0; while [ $j -lt $EMPTY ]; do BAR="${BAR}░"; j=$((j+1)); done

  # Ensure output directory exists
  mkdir -p "$(dirname "$out")" || true

  # Generate markdown
  {
    echo "# Kanban Board"
    echo ""
    echo "> **Branch:** \`$BRANCH\`  "
    echo "> **Progress:** \`[$BAR]\` **$DONE_COUNT/$TOTAL ($PCT%)**  "
    echo "> **Working:** $CURRENT  "
    echo "> **Updated:** $(date '+%H:%M:%S')  "
    echo ""
    echo "---"
    echo ""

    # Column headers
    echo "| Status | ID | Task |"
    echo "|--------|-----|------|"

    # In Progress first (most important)
    prd_jq_r '.tasks[] | select(.status == "in_progress") | "| ⚡ **WORKING** | \(.id) | \(.title) |"'

    # Pending
    prd_jq_r '.tasks[] | select(.status == "pending") | "| ⏳ Pending | \(.id) | \(.title) |"'

    # Failed
    prd_jq_r '.tasks[] | select(.status == "failed") | "| ❌ **FAILED** | \(.id) | \(.title) |"'

    # Done
    prd_jq_r '.tasks[] | select(.status == "done") | "| ✅ Done | \(.id) | \(.title) |"'

    echo ""
    echo "---"
    echo "*Auto-generated by board.sh — do not edit*"
  } > "$out"

  echo "Wrote $out"
}

# ── Summary Mode ─────────────────────────────────────────────────
render_summary() {
  TOTAL=$(prd_jq '.tasks | length')
  DONE_COUNT=$(prd_jq '[.tasks[] | select(.status == "done")] | length')
  CURRENT=$(prd_jq_r '[.tasks[] | select(.status == "in_progress")][0] // null | if . then "\(.id) — \(.title)" else "none" end')

  PCT=0
  if [ "$TOTAL" -gt 0 ]; then PCT=$((DONE_COUNT * 100 / TOTAL)); fi

  echo "$DONE_COUNT/$TOTAL tasks ($PCT%) · Working: $CURRENT"
}

# ── Route to renderer ───────────────────────────────────────────
case "$MODE" in
  ascii)   render_ascii   ;;
  md)      render_md      ;;
  summary) render_summary ;;
esac
