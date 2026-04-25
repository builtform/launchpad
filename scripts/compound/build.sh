#!/usr/bin/env bash
# Build Pipeline — non-interactive execution
# Reads a report or section spec, creates PRD + tasks, runs execution loop, quality sweep.
# Does NOT push, create PR, or extract learnings (see /lp-ship and compound-learning.sh).
#
# Usage: scripts/compound/build.sh [--dry-run] [--ambition] [--evaluator] [--contract] [docs/tasks/sections/<section>.md]
#        scripts/compound/build.sh --plan path/to/plan.md
#
# CLI flags replace the interactive menu. No flags = defaults from config.json.
# NEVER prompts via `read`.

source "$(dirname "$0")/lib.sh"

# Check additional requirements
command -v gh >/dev/null 2>&1 || error "gh CLI not found. Install with: brew install gh"
command -v lefthook >/dev/null 2>&1 || error "lefthook not found. Install with: brew install lefthook"

# Parse arguments
DRY_RUN=false
EXPLICIT_PLAN=""
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --ambition)
      AMBITION_MODE="true"
      shift
      ;;
    --evaluator)
      EVALUATOR_ENABLED="true"
      shift
      ;;
    --contract)
      SPRINT_CONTRACT="true"
      EVALUATOR_ENABLED="true"
      shift
      ;;
    --plan)
      [[ -n "${2:-}" ]] || error "Missing value for --plan"
      EXPLICIT_PLAN="$2"
      shift 2
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

cd "$PROJECT_ROOT"

DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
git fetch origin "$DEFAULT_BRANCH" 2>/dev/null || true

# If --plan is provided, skip report/spec analysis and use the plan directly
if [ -n "$EXPLICIT_PLAN" ]; then
  log "Explicit plan mode: $EXPLICIT_PLAN"
  [ -f "$EXPLICIT_PLAN" ] || [ -f "$PROJECT_ROOT/$EXPLICIT_PLAN" ] || error "Plan file not found: $EXPLICIT_PLAN"

  # Extract plan name for logging
  PLAN_NAME=$(basename "$EXPLICIT_PLAN" .md)
  log "Using plan: $PLAN_NAME"

  # Skip to execution loop using the plan directly
  # The plan is already a PRD or task definition — pass it to the loop
  PRIORITY_ITEM="Implement $PLAN_NAME"
  BRANCH_NAME=$(git branch --show-current)
  # Guard against running on protected branches
  DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
  DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
  if [ "$BRANCH_NAME" = "$DEFAULT_BRANCH" ] || [ "$BRANCH_NAME" = "master" ]; then
    error "Cannot run --plan on protected branch '$BRANCH_NAME'. Create a feature branch first."
  fi
  log "Branch: $BRANCH_NAME"

  if [ "$DRY_RUN" = true ]; then
    log "DRY RUN - Would implement plan: $EXPLICIT_PLAN on branch: $BRANCH_NAME"
    exit 0
  fi

  # Execute the plan via AI tool
  ITERATION_PROMPT="Read the implementation plan at $EXPLICIT_PLAN.
Implement all tasks described in the plan. For each task:
1. Read the relevant code context
2. Make the required changes
3. Run pnpm typecheck and pnpm test after each significant change
4. Move to the next task

Do NOT create PRs, push, or commit. Just implement the changes."

  echo "$ITERATION_PROMPT" | ai_run 2>&1 | tee "$OUTPUT_DIR/build-execution.log"

  # Quality sweep
  log "Running quality sweep..."
  MAX_FIX_ATTEMPTS=3
  for fix_attempt in $(seq 1 $MAX_FIX_ATTEMPTS); do
    log "Quality sweep attempt $fix_attempt/$MAX_FIX_ATTEMPTS..."
    git add -u
    LEFTHOOK_OUTPUT=$(lefthook run pre-commit 2>&1) && LEFTHOOK_EXIT=0 || LEFTHOOK_EXIT=$?

    if [ "$LEFTHOOK_EXIT" -eq 0 ]; then
      log "Quality sweep passed"
      break
    fi

    log "Quality sweep failed (attempt $fix_attempt). Using $TOOL to fix..."
    echo "Fix these lefthook pre-commit failures autonomously. Do NOT ask questions. Just fix the issues and stage the changes.

Failures:
$LEFTHOOK_OUTPUT" | ai_run 2>&1 | tee "$OUTPUT_DIR/build-quality-fix.log"

    if [ "$fix_attempt" -eq "$MAX_FIX_ATTEMPTS" ]; then
      log "WARNING: Quality sweep still failing after $MAX_FIX_ATTEMPTS attempts."
    fi
  done

  log "Build complete (plan mode)."
  exit 0
fi

# Step 1: Detect section spec from positional args
SECTION_SPEC=""
for arg in "${POSITIONAL_ARGS[@]}"; do
  if [[ "$arg" == docs/tasks/sections/*.md ]] || [[ "$arg" == */docs/tasks/sections/*.md ]]; then
    if [ -f "$PROJECT_ROOT/$arg" ] 2>/dev/null || [ -f "$arg" ] 2>/dev/null; then
      SECTION_SPEC="${arg}"
      log "Using section spec as primary context: $SECTION_SPEC"
    fi
  fi
done

if [ -n "$SECTION_SPEC" ]; then
  # Section-spec mode
  log "Step 1: Section-spec mode — bypassing report analysis"

  SPEC_PATH=""
  if [ -f "$PROJECT_ROOT/$SECTION_SPEC" ]; then
    SPEC_PATH="$PROJECT_ROOT/$SECTION_SPEC"
  elif [ -f "$SECTION_SPEC" ]; then
    SPEC_PATH="$SECTION_SPEC"
  fi
  [ -f "$SPEC_PATH" ] || error "Section spec not found: $SECTION_SPEC"

  SECTION_NAME=$(basename "$SPEC_PATH" .md)
  PRIORITY_ITEM="Implement $SECTION_NAME section"
  DESCRIPTION="Implementation of the $SECTION_NAME section as defined in the section spec."
  RATIONALE="Section spec completed via /lp-shape-section — ready for implementation."
  BRANCH_NAME="${BRANCH_PREFIX}${SECTION_NAME}"
  REPORT_NAME="(section-spec: $SECTION_NAME)"
  LATEST_REPORT=""

  log "Priority item: $PRIORITY_ITEM"
  log "Branch: $BRANCH_NAME"
else
  # Report mode
  log "Step 1: Finding most recent report..."

  LATEST_REPORT=$(ls -t "$REPORTS_DIR"/*.md 2>/dev/null | head -1)
  [ -f "$LATEST_REPORT" ] || error "No reports found in $REPORTS_DIR"
  REPORT_NAME=$(basename "$LATEST_REPORT")
  log "Using report: $REPORT_NAME"

  log "Step 2: Analyzing report to pick #1 actionable priority..."

  if [ -n "$ANALYZE_COMMAND" ]; then
    # Validate analyzeCommand is an executable path, not arbitrary shell
    if [ ! -x "$ANALYZE_COMMAND" ] && ! command -v "$ANALYZE_COMMAND" >/dev/null 2>&1; then
      error "analyzeCommand '$ANALYZE_COMMAND' is not an executable file or command"
    fi
    ANALYSIS_JSON=$("$ANALYZE_COMMAND" "$LATEST_REPORT" 2>/dev/null)
  else
    ANALYSIS_JSON=$("$SCRIPT_DIR/analyze-report.sh" "$LATEST_REPORT" 2>/dev/null)
  fi

  [ -n "$ANALYSIS_JSON" ] || error "Failed to analyze report"

  PRIORITY_ITEM=$(echo "$ANALYSIS_JSON" | jq -r '.priority_item // empty')
  DESCRIPTION=$(echo "$ANALYSIS_JSON" | jq -r '.description // empty')
  RATIONALE=$(echo "$ANALYSIS_JSON" | jq -r '.rationale // empty')
  BRANCH_NAME=$(echo "$ANALYSIS_JSON" | jq -r '.branch_name // empty')

  [ -n "$PRIORITY_ITEM" ] || error "Failed to parse priority item from analysis"

  log "Priority item: $PRIORITY_ITEM"
  log "Branch: $BRANCH_NAME"
  log "Rationale: $RATIONALE"
fi

# Ensure branch has correct prefix
if [[ "$BRANCH_NAME" != "$BRANCH_PREFIX"* ]]; then
  BRANCH_NAME="${BRANCH_PREFIX}$(echo "$BRANCH_NAME" | sed "s|^[^/]*/||")"
fi

# Validate branch name
if ! git check-ref-format --branch "$BRANCH_NAME" >/dev/null 2>&1; then
  error "Invalid branch name: $BRANCH_NAME"
fi

if [ "$DRY_RUN" = true ]; then
  log "DRY RUN - Would proceed with:"
  if [ -n "$SECTION_SPEC" ]; then
    jq -n --arg spec "$SECTION_SPEC" --arg item "$PRIORITY_ITEM" --arg branch "$BRANCH_NAME" \
      '{mode:"section-spec", section_spec:$spec, priority_item:$item, branch_name:$branch}'
  else
    echo "$ANALYSIS_JSON" | jq .
  fi
  exit 0
fi

# Step 3: Create feature branch
log "Step 3: Creating feature branch..."
git switch "$DEFAULT_BRANCH"
git merge --ff-only "origin/$DEFAULT_BRANCH"
git switch -c -- "$BRANCH_NAME" 2>/dev/null || git switch -- "$BRANCH_NAME"

# Step 4: Create PRD
log "Step 4: Creating PRD..."
PRD_FILENAME="prd-$(echo "$BRANCH_NAME" | sed "s|^${BRANCH_PREFIX}||").md"
mkdir -p "$TASKS_DIR"

SECTION_SPEC_CONTEXT=""
if [ -n "$SECTION_SPEC" ]; then
  SPEC_PATH=""
  if [ -f "$PROJECT_ROOT/$SECTION_SPEC" ]; then
    SPEC_PATH="$PROJECT_ROOT/$SECTION_SPEC"
  elif [ -f "$SECTION_SPEC" ]; then
    SPEC_PATH="$SECTION_SPEC"
  fi
  if [ -n "$SPEC_PATH" ]; then
    SECTION_SPEC_CONTEXT="
## Section Spec (primary context for scope and requirements)
$(cat "$SPEC_PATH")"
    log "Injecting section spec into PRD prompt: $SPEC_PATH"
  fi
fi

ACCEPTANCE_CRITERIA=""
if [ -n "$ANALYSIS_JSON" ]; then
  ACCEPTANCE_CRITERIA="Acceptance criteria from analysis:
$(echo "$ANALYSIS_JSON" | jq -r '(.acceptance_criteria // [])[]' | sed 's/^/- /')"
fi

PRD_PROMPT="Load the prd skill. Create a PRD for: $PRIORITY_ITEM

Description: $DESCRIPTION
Rationale: $RATIONALE
${SECTION_SPEC_CONTEXT}
${ACCEPTANCE_CRITERIA}

IMPORTANT CONSTRAINTS:
- NO database migrations or schema changes
- Keep scope small - this should be completable in 2-4 hours
- Break into 3-5 high-level tasks
- Each task must be verifiable with quality checks and/or browser testing
- Follow the PRD skill template exactly
- DO NOT ask clarifying questions
- Generate the PRD immediately

Save the PRD to: docs/tasks/$PRD_FILENAME"

if [ "$AMBITION_MODE" = "true" ]; then
  PRD_PROMPT="$PRD_PROMPT

AMBITION MODE ENABLED:
- Be ambitious about scope. Push beyond the minimum viable implementation.
- Suggest AI-powered features where they add genuine value.
- Include micro-interactions, loading states, empty states, error states.
- Still keep it completable within the iteration budget."
fi

echo "$PRD_PROMPT" | ai_run 2>&1 | tee "$OUTPUT_DIR/build-prd.log"

PRD_PATH="$TASKS_DIR/$PRD_FILENAME"
[ -f "$PRD_PATH" ] || error "PRD was not created at $PRD_PATH"
log "PRD created: $PRD_PATH"

# Archive previous run
PRD_FILE="$OUTPUT_DIR/prd.json"
PROGRESS_FILE="$OUTPUT_DIR/progress.txt"
ARCHIVE_DIR="$OUTPUT_DIR/archive"

if [ -f "$PRD_FILE" ]; then
  OLD_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  if [ -n "$OLD_BRANCH" ] && [ "$OLD_BRANCH" != "$BRANCH_NAME" ]; then
    DATE=$(date +%Y-%m-%d)
    FOLDER_NAME=$(echo "$OLD_BRANCH" | sed 's|^[^/]*/||')
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$DATE-$FOLDER_NAME"
    log "Archiving previous run: $OLD_BRANCH"
    mkdir -p "$ARCHIVE_FOLDER"
    mv "$PRD_FILE" "$ARCHIVE_FOLDER/"
    [ -f "$PROGRESS_FILE" ] && mv "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"
  fi
fi

# Step 5: Convert PRD to tasks
log "Step 5: Converting PRD to prd.json..."
TASKS_PROMPT="Load the tasks skill. Convert $PRD_PATH to $OUTPUT_DIR/prd.json
Use branch name: $BRANCH_NAME
Remember: Each task must be small enough to complete in one iteration."

echo "$TASKS_PROMPT" | ai_run 2>&1 | tee "$OUTPUT_DIR/build-tasks.log"

[ -f "$OUTPUT_DIR/prd.json" ] || error "prd.json was not created"
log "Tasks created: $(jq '.tasks | length' "$OUTPUT_DIR/prd.json") tasks"

jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '.startedAt = $ts' "$OUTPUT_DIR/prd.json" > "$OUTPUT_DIR/prd.json.tmp" && mv "$OUTPUT_DIR/prd.json.tmp" "$OUTPUT_DIR/prd.json"

"$SCRIPT_DIR/board.sh" --md "$OUTPUT_DIR/prd.json" "$PROJECT_ROOT/docs/tasks/board.md" || true

# Step 5.5: Sprint Contract Negotiation (opt-in)
if [ "$SPRINT_CONTRACT" = "true" ]; then
  log "Step 5.5: Negotiating sprint contract..."
  MAX_CONTRACT_ROUNDS=3
  CONTRACT_FILE="$OUTPUT_DIR/sprint-contract.json"

  echo "$(cat "$SCRIPT_DIR/contract-prompt.md")

Read $OUTPUT_DIR/prd.json for task context.
Read $SCRIPT_DIR/grading-criteria.md for the four grading dimensions.
Write a sprint contract to $CONTRACT_FILE." | ai_run 2>&1 | tee "$OUTPUT_DIR/build-contract.log"

  for round in $(seq 1 $MAX_CONTRACT_ROUNDS); do
    echo "You are an evaluator reviewing a sprint contract. Read $CONTRACT_FILE and $SCRIPT_DIR/grading-criteria.md.
Challenge any vague criteria, missing verification steps, or untestable claims.
Write your response back to $CONTRACT_FILE with approved: true if acceptable, or approved: false with challenges array." | ai_run 2>&1 | tee -a "$OUTPUT_DIR/build-contract.log"

    APPROVED=$(jq -r '.approved // false' "$CONTRACT_FILE" 2>/dev/null || echo "false")
    if [ "$APPROVED" = "true" ]; then
      log "Sprint contract approved after $round round(s)"
      break
    fi

    if [ "$round" -lt "$MAX_CONTRACT_ROUNDS" ]; then
      echo "You are a generator revising a sprint contract after evaluator feedback. Read $CONTRACT_FILE.
Address each challenge. Write the revised contract back to $CONTRACT_FILE." | ai_run 2>&1 | tee -a "$OUTPUT_DIR/build-contract.log"
    else
      log "Sprint contract: max rounds reached, proceeding with latest version"
    fi
  done
fi

# Commit PRD and tasks
git add "$PRD_PATH"
git add -f "$OUTPUT_DIR/prd.json"
git commit -m "chore: add PRD and tasks for $PRIORITY_ITEM" || true

# Step 6: Run the loop
log "Step 6: Running execution loop (max $MAX_ITERATIONS iterations)..."
"$SCRIPT_DIR/loop.sh" "$MAX_ITERATIONS" 2>&1 | tee "$OUTPUT_DIR/build-execution.log"

# Step 6.5: Evaluator Loop (opt-in)
if [ "$EVALUATOR_ENABLED" = "true" ]; then
  log "Step 6.5: Running evaluator loop..."
  PRD_PATH="$PRD_PATH" "$SCRIPT_DIR/evaluate.sh" 2>&1 | tee "$OUTPUT_DIR/build-evaluator.log"
fi

# Step 7a: Final Quality Sweep
log "Step 7a: Running final quality sweep..."
MAX_FIX_ATTEMPTS=3
for fix_attempt in $(seq 1 $MAX_FIX_ATTEMPTS); do
  log "Quality sweep attempt $fix_attempt/$MAX_FIX_ATTEMPTS..."
  git add -u
  LEFTHOOK_OUTPUT=$(lefthook run pre-commit 2>&1) && LEFTHOOK_EXIT=0 || LEFTHOOK_EXIT=$?
  git add -u
  if ! git diff --cached --quiet; then
    git commit -m "chore: auto-fix formatting and lint issues"
  fi

  if [ "$LEFTHOOK_EXIT" -eq 0 ]; then
    log "Quality sweep passed"
    break
  fi

  log "Quality sweep failed (attempt $fix_attempt). Using $TOOL to fix..."
  echo "Fix these lefthook pre-commit failures autonomously. Do NOT ask questions.

Failures:
$LEFTHOOK_OUTPUT" | ai_run 2>&1 | tee "$OUTPUT_DIR/build-quality-fix.log"

  git add -u
  if ! git diff --cached --quiet; then
    git commit -m "chore: fix quality gate issues (attempt $fix_attempt)"
  fi

  if [ "$fix_attempt" -eq "$MAX_FIX_ATTEMPTS" ]; then
    log "WARNING: Quality sweep still failing after $MAX_FIX_ATTEMPTS attempts."
  fi
done

# Set completedAt timestamp
jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '.completedAt = $ts' "$OUTPUT_DIR/prd.json" > "$OUTPUT_DIR/prd.json.tmp" && mv "$OUTPUT_DIR/prd.json.tmp" "$OUTPUT_DIR/prd.json"

# Final board render
"$SCRIPT_DIR/board.sh" --md "$OUTPUT_DIR/prd.json" "$PROJECT_ROOT/docs/tasks/board.md" || true
BOARD_SUMMARY=$("$SCRIPT_DIR/board.sh" --summary "$OUTPUT_DIR/prd.json" 2>/dev/null || echo "")
if [ -n "$BOARD_SUMMARY" ]; then
  log "Final: $BOARD_SUMMARY"
fi

log "Build complete. Run /lp-ship to push and create PR."
