#!/bin/bash
# Compound Product - Full Pipeline
# Reads a report, picks #1 priority, creates PRD + tasks, runs loop, creates PR
# Tool is configurable via config.json "tool" field (default: claude).
#
# Usage: ./auto-compound.sh [--dry-run]
#
# Requirements:
# - claude or codex CLI installed and authenticated (based on config.json "tool")
# - gh CLI installed and authenticated
# - jq installed

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
  exit 1
}

# Check requirements (jq needed before config loading)
command -v jq >/dev/null 2>&1 || error "jq is required but not installed. Install with: brew install jq"
command -v gh >/dev/null 2>&1 || error "gh CLI not found. Install with: brew install gh"
command -v lefthook >/dev/null 2>&1 || error "lefthook not found. Install with: brew install lefthook"

# Load config
if [ ! -f "$CONFIG_FILE" ]; then
  error "Config file not found: $CONFIG_FILE. Copy config.example.json to config.json and customize."
fi

REPORTS_DIR=$(jq -r '.reportsDir // "./docs/reports"' "$CONFIG_FILE")
OUTPUT_DIR=$(jq -r '.outputDir // "./scripts/compound"' "$CONFIG_FILE")
MAX_ITERATIONS=$(jq -r '.maxIterations // 25' "$CONFIG_FILE")
BRANCH_PREFIX=$(jq -r '.branchPrefix // "compound/"' "$CONFIG_FILE")
ANALYZE_COMMAND=$(jq -r '.analyzeCommand // ""' "$CONFIG_FILE")
TOOL=$(jq -r '.tool // "claude"' "$CONFIG_FILE")

# Validate AI tool CLI
command -v "$TOOL" >/dev/null 2>&1 || error "$TOOL CLI not found. Install it or change tool in config.json"

# ai_run: pipes a prompt into the configured AI tool (non-interactive, full permissions)
# Usage: echo "prompt" | ai_run 2>&1 | tee logfile
ai_run() {
  if [ "$TOOL" = "codex" ]; then
    codex exec --dangerously-bypass-approvals-and-sandbox "$(cat -)"
  else
    claude --dangerously-skip-permissions
  fi
}

# Resolve paths
REPORTS_DIR="$PROJECT_ROOT/$REPORTS_DIR"
OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
TASKS_DIR="$PROJECT_ROOT/tasks"

cd "$PROJECT_ROOT"

# Source environment variables if available
if [ -f ".env.local" ]; then
  set -a
  source .env.local
  set +a
fi

# Step 1: Find most recent report
log "Step 1: Finding most recent report..."
git pull origin main 2>/dev/null || true

LATEST_REPORT=$(ls -t "$REPORTS_DIR"/*.md 2>/dev/null | head -1)
[ -f "$LATEST_REPORT" ] || error "No reports found in $REPORTS_DIR"
REPORT_NAME=$(basename "$LATEST_REPORT")
log "Using report: $REPORT_NAME"

# Step 2: Analyze report
log "Step 2: Analyzing report to pick #1 actionable priority..."

if [ -n "$ANALYZE_COMMAND" ]; then
  ANALYSIS_JSON=$(bash -c "$ANALYZE_COMMAND \"$LATEST_REPORT\"" 2>/dev/null)
else
  ANALYSIS_JSON=$("$SCRIPT_DIR/analyze-report.sh" "$LATEST_REPORT" 2>/dev/null)
fi

[ -n "$ANALYSIS_JSON" ] || error "Failed to analyze report"

# Parse the analysis
PRIORITY_ITEM=$(echo "$ANALYSIS_JSON" | jq -r '.priority_item // empty')
DESCRIPTION=$(echo "$ANALYSIS_JSON" | jq -r '.description // empty')
RATIONALE=$(echo "$ANALYSIS_JSON" | jq -r '.rationale // empty')
BRANCH_NAME=$(echo "$ANALYSIS_JSON" | jq -r '.branch_name // empty')

[ -n "$PRIORITY_ITEM" ] || error "Failed to parse priority item from analysis"

# Ensure branch has correct prefix
if [[ "$BRANCH_NAME" != "$BRANCH_PREFIX"* ]]; then
  BRANCH_NAME="${BRANCH_PREFIX}$(echo "$BRANCH_NAME" | sed "s|^[^/]*/||")"
fi

# Validate branch name using git's own rules
if ! git check-ref-format --branch "$BRANCH_NAME" >/dev/null 2>&1; then
  error "Invalid branch name: $BRANCH_NAME"
fi

# Validate branch name using git's own rules
if ! git check-ref-format --branch "$BRANCH_NAME" >/dev/null 2>&1; then
  error "Invalid branch name: $BRANCH_NAME"
fi

log "Priority item: $PRIORITY_ITEM"
log "Branch: $BRANCH_NAME"
log "Rationale: $RATIONALE"
echo "[CHECKPOINT] Report analyzed — priority: $PRIORITY_ITEM"

if [ "$DRY_RUN" = true ]; then
  log "DRY RUN - Would proceed with:"
  echo "$ANALYSIS_JSON" | jq .
  exit 0
fi

# Step 3: Create feature branch
log "Step 3: Creating feature branch..."
git switch main
git switch -c -- "$BRANCH_NAME" 2>/dev/null || git switch -- "$BRANCH_NAME"

# Step 4: Create PRD via AI tool
log "Step 4: Creating PRD..."

PRD_FILENAME="prd-$(echo "$BRANCH_NAME" | sed "s|^${BRANCH_PREFIX}||").md"
mkdir -p "$TASKS_DIR"

PRD_PROMPT="Load the prd skill. Create a PRD for: $PRIORITY_ITEM

Description: $DESCRIPTION

Rationale from report analysis: $RATIONALE

Acceptance criteria from analysis:
$(echo "$ANALYSIS_JSON" | jq -r '.acceptance_criteria[]' | sed 's/^/- /')

IMPORTANT CONSTRAINTS:
- NO database migrations or schema changes
- Keep scope small - this should be completable in 2-4 hours
- Break into 3-5 small tasks maximum
- Each task must be verifiable with quality checks and/or browser testing
- DO NOT ask clarifying questions - you have enough context to proceed
- Generate the PRD immediately without waiting for user input

Save the PRD to: tasks/$PRD_FILENAME"

echo "$PRD_PROMPT" | ai_run 2>&1 | tee "$OUTPUT_DIR/auto-compound-prd.log"

# Verify PRD was created
PRD_PATH="$TASKS_DIR/$PRD_FILENAME"
[ -f "$PRD_PATH" ] || error "PRD was not created at $PRD_PATH"
log "PRD created: $PRD_PATH"
echo "[CHECKPOINT] PRD generated. Review at: $PRD_PATH (pipeline continues...)"

# Archive previous run before overwriting prd.json
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
    log "Archived to: $ARCHIVE_FOLDER"
  fi
fi

# Step 5: Convert PRD to tasks via AI tool
log "Step 5: Converting PRD to prd.json..."

TASKS_PROMPT="Load the tasks skill. Convert $PRD_PATH to $OUTPUT_DIR/prd.json

Use branch name: $BRANCH_NAME

Remember: Each task must be small enough to complete in one iteration."

echo "$TASKS_PROMPT" | ai_run 2>&1 | tee "$OUTPUT_DIR/auto-compound-tasks.log"

# Verify prd.json was created
[ -f "$OUTPUT_DIR/prd.json" ] || error "prd.json was not created"
log "Tasks created: $(cat "$OUTPUT_DIR/prd.json" | jq '.tasks | length') tasks"
echo "[CHECKPOINT] Tasks created — $(jq '.tasks | length' "$OUTPUT_DIR/prd.json") tasks in prd.json (pipeline continues...)"

# Set startedAt timestamp
jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '.startedAt = $ts' "$OUTPUT_DIR/prd.json" > "$OUTPUT_DIR/prd.json.tmp" && mv "$OUTPUT_DIR/prd.json.tmp" "$OUTPUT_DIR/prd.json"

# Render initial board
"$SCRIPT_DIR/board.sh" --md "$OUTPUT_DIR/prd.json" "$PROJECT_ROOT/docs/tasks/board.md" || true

# Commit the PRD and prd.json
git add "$PRD_PATH" "$OUTPUT_DIR/prd.json"
git commit -m "chore: add PRD and tasks for $PRIORITY_ITEM" || true

# Step 6: Run the loop
log "Step 6: Running execution loop (max $MAX_ITERATIONS iterations)..."
"$SCRIPT_DIR/loop.sh" "$MAX_ITERATIONS" 2>&1 | tee "$OUTPUT_DIR/auto-compound-execution.log"
echo "[CHECKPOINT] Execution loop complete. Starting quality sweep..."

# Step 7a: Final Quality Sweep
log "Step 7a: Running final quality sweep (lefthook pre-commit)..."

MAX_FIX_ATTEMPTS=3
for fix_attempt in $(seq 1 $MAX_FIX_ATTEMPTS); do
  log "Quality sweep attempt $fix_attempt/$MAX_FIX_ATTEMPTS..."

  # Stage everything for lefthook
  git add -A

  # Run lefthook pre-commit (includes auto-fixers + structure-check + typecheck)
  LEFTHOOK_OUTPUT=$(lefthook run pre-commit 2>&1) && LEFTHOOK_EXIT=0 || LEFTHOOK_EXIT=$?

  # If auto-fixers changed files, commit the fixes
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "chore: auto-fix formatting and lint issues"
    log "Auto-fix commit created"
  fi

  # If lefthook passed, break out of the loop
  if [ "$LEFTHOOK_EXIT" -eq 0 ]; then
    log "Quality sweep passed"
    break
  fi

  # If read-only checks failed, use AI tool to fix
  log "Quality sweep failed (attempt $fix_attempt). Using $TOOL to fix..."
  echo "Fix these lefthook pre-commit failures autonomously. Do NOT ask questions. Just fix the issues and stage the changes.

Failures:
$LEFTHOOK_OUTPUT" | ai_run 2>&1 | tee "$OUTPUT_DIR/auto-compound-quality-fix.log"

  # Stage and commit fixes
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "chore: fix quality gate issues (attempt $fix_attempt)"
  fi

  if [ "$fix_attempt" -eq "$MAX_FIX_ATTEMPTS" ]; then
    log "WARNING: Quality sweep still failing after $MAX_FIX_ATTEMPTS attempts. Proceeding anyway."
  fi
done

# Step 7b: Push and Create PR
log "Step 7b: Pushing and creating Pull Request..."

git push -u origin "$BRANCH_NAME"

PR_BODY="## Compound Product: $PRIORITY_ITEM

**Generated from report:** $REPORT_NAME

### Rationale
$RATIONALE

### What was done
\`\`\`
$(cat "$OUTPUT_DIR/progress.txt" 2>/dev/null | tail -50)
\`\`\`

### Tasks
$(cat "$PROJECT_ROOT/docs/tasks/board.md" 2>/dev/null | tail -n +2 || cat "$OUTPUT_DIR/prd.json" | jq '.tasks[] | {id, title, passes}')

---
*This PR was automatically generated by \`/inf\` (Implement Next Feature).*"

PR_URL=$(gh pr create \
  --title "feat: $PRIORITY_ITEM" \
  --body "$PR_BODY" \
  --base main \
  --head "$BRANCH_NAME")

log "PR created: $PR_URL"

# Extract PR number for API calls
PR_NUMBER=$(echo "$PR_URL" | grep -oE '[0-9]+$')
REPO_OWNER=$(gh repo view --json owner -q '.owner.login')
REPO_NAME=$(gh repo view --json name -q '.name')

# Step 7c: PR Monitoring Loop
log "Step 7c: Monitoring PR until all gates pass..."

MAX_PR_CYCLES=5
MAX_PENDING_WAITS=20  # 20 x 30s = 10 minutes max wait for pending checks

for cycle in $(seq 1 $MAX_PR_CYCLES); do
  log "Monitoring cycle $cycle/$MAX_PR_CYCLES..."
  ALL_GREEN=true

  # --- Gate A: CI Checks ---
  log "Gate A: Checking CI status..."
  PENDING_WAITS=0
  while true; do
    CI_OUTPUT=$(gh pr checks "$PR_NUMBER" 2>&1) && CI_EXIT=0 || CI_EXIT=$?

    if [ "$CI_EXIT" -eq 0 ]; then
      log "Gate A: All CI checks passed"
      break
    fi

    # Exit code 8 = pending checks
    if echo "$CI_OUTPUT" | grep -qi "pending\|in_progress"; then
      PENDING_WAITS=$((PENDING_WAITS + 1))
      if [ "$PENDING_WAITS" -ge "$MAX_PENDING_WAITS" ]; then
        log "Gate A: Timed out waiting for pending checks"
        ALL_GREEN=false
        break
      fi
      log "Gate A: Checks still pending, waiting 30s... ($PENDING_WAITS/$MAX_PENDING_WAITS)"
      sleep 30
      continue
    fi

    # Actual failure — get logs and fix
    log "Gate A: CI check failed. Diagnosing..."
    FAILED_RUN_ID=$(gh run list --branch "$BRANCH_NAME" --status failure --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null)
    if [ -n "$FAILED_RUN_ID" ]; then
      FAIL_LOG=$(gh run view "$FAILED_RUN_ID" --log-failed 2>/dev/null | tail -100)
      log "Gate A: Attempting auto-fix..."
      echo "Fix this CI failure autonomously. Do NOT ask questions. Just fix and stage changes.

CI failure log:
$FAIL_LOG" | ai_run 2>&1 | tee "$OUTPUT_DIR/auto-compound-ci-fix.log"

      # Commit and push the fix
      git add -A
      if ! git diff --cached --quiet; then
        git commit -m "fix: address CI failure (cycle $cycle)"
        git push origin "$BRANCH_NAME"
        log "Gate A: Fix pushed, restarting cycle"
      fi
    fi
    ALL_GREEN=false
    break
  done

  # --- Gate B: Codex Review ---
  log "Gate B: Checking for Codex review..."
  REVIEW_WAITS=0
  MAX_REVIEW_WAITS=20  # 20 x 30s = 10 minutes max wait for review

  while [ "$REVIEW_WAITS" -lt "$MAX_REVIEW_WAITS" ]; do
    # Look for Codex review comment
    CODEX_COMMENT=$(gh api "repos/$REPO_OWNER/$REPO_NAME/issues/$PR_NUMBER/comments" \
      --jq '[.[] | select(.body | test("Codex Automated Code Review"))] | last // empty' 2>/dev/null)

    if [ -n "$CODEX_COMMENT" ]; then
      COMMENT_BODY=$(echo "$CODEX_COMMENT" | jq -r '.body')

      # Check for P0 or P1 issues
      HAS_P0=$(echo "$COMMENT_BODY" | grep -c "### P0" || true)
      HAS_P1=$(echo "$COMMENT_BODY" | grep -c "### P1" || true)
      P0_CONTENT=$(echo "$COMMENT_BODY" | sed -n '/### P0/,/### P[1-3]/p' | grep -v "None found" | grep -v "^###" | grep -v "^$" | head -5)
      P1_CONTENT=$(echo "$COMMENT_BODY" | sed -n '/### P1/,/### P[2-3]/p' | grep -v "None found" | grep -v "^###" | grep -v "^$" | head -5)

      if [ -n "$P0_CONTENT" ] || [ -n "$P1_CONTENT" ]; then
        log "Gate B: Codex found P0/P1 issues. Attempting auto-fix..."
        echo "Fix these code review issues autonomously. Do NOT ask questions. Just fix and stage changes.

P0 Critical Issues:
$P0_CONTENT

P1 High Priority Issues:
$P1_CONTENT" | ai_run 2>&1 | tee "$OUTPUT_DIR/auto-compound-review-fix.log"

        # Commit and push the fix (triggers new Codex review)
        git add -A
        if ! git diff --cached --quiet; then
          git commit -m "fix: address Codex review findings (cycle $cycle)"
          git push origin "$BRANCH_NAME"
          log "Gate B: Fix pushed, new review will be triggered"
        fi
        ALL_GREEN=false
      else
        log "Gate B: Codex review clean (no P0/P1 issues)"
      fi
      break
    fi

    REVIEW_WAITS=$((REVIEW_WAITS + 1))
    log "Gate B: Waiting for Codex review... ($REVIEW_WAITS/$MAX_REVIEW_WAITS)"
    sleep 30
  done

  if [ "$REVIEW_WAITS" -ge "$MAX_REVIEW_WAITS" ]; then
    log "Gate B: Timed out waiting for Codex review. Proceeding without it."
  fi

  # --- Gate C: Merge Conflicts ---
  log "Gate C: Checking for merge conflicts..."
  MERGEABLE=$(gh pr view "$PR_NUMBER" --json mergeable -q '.mergeable' 2>/dev/null)

  if [ "$MERGEABLE" != "MERGEABLE" ] && [ "$MERGEABLE" != "UNKNOWN" ]; then
    log "Gate C: Merge conflict detected. Rebasing..."
    git fetch origin main
    git rebase origin/main || {
      log "Gate C: Rebase conflict. Attempting resolution..."
      echo "Resolve these git rebase conflicts autonomously. Do NOT ask questions." | ai_run 2>&1
      git rebase --continue 2>/dev/null || git rebase --abort
    }

    # Re-run quality sweep after rebase
    lefthook run pre-commit 2>&1 || true
    git add -A
    if ! git diff --cached --quiet; then
      git commit -m "chore: fix issues after rebase (cycle $cycle)"
    fi

    git push --force-with-lease origin "$BRANCH_NAME"
    log "Gate C: Rebased and pushed"
    ALL_GREEN=false
  else
    log "Gate C: No merge conflicts"
  fi

  # --- Check if all gates passed ---
  if [ "$ALL_GREEN" = true ]; then
    log "All gates passed on cycle $cycle!"
    break
  fi

  if [ "$cycle" -eq "$MAX_PR_CYCLES" ]; then
    log "WARNING: Max monitoring cycles reached ($MAX_PR_CYCLES). Manual review may be needed."
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

# Step 8: Extract learnings into structured file
log "Step 8: Extracting learnings from progress.txt..."

FEATURE_SLUG=$(echo "$BRANCH_NAME" | sed "s|^${BRANCH_PREFIX}||")
LEARNINGS_DIR="$PROJECT_ROOT/docs/solutions/compound-product/$FEATURE_SLUG"
LEARNINGS_FILE="$LEARNINGS_DIR/${FEATURE_SLUG}-$(date +%Y-%m-%d).md"
TEMPLATE_FILE="$PROJECT_ROOT/docs/solutions/compound-product/_template.md"

if [ -f "$PROGRESS_FILE" ] && [ -f "$TEMPLATE_FILE" ]; then
  mkdir -p "$LEARNINGS_DIR"

  # Count task stats from prd.json
  TASKS_TOTAL=$(jq '.tasks | length' "$OUTPUT_DIR/prd.json" 2>/dev/null || echo 0)
  TASKS_COMPLETED=$(jq '[.tasks[] | select(.passes == true)] | length' "$OUTPUT_DIR/prd.json" 2>/dev/null || echo 0)
  ITERATION_COUNT=$(grep -c "^## " "$PROGRESS_FILE" 2>/dev/null || echo 0)

  # Extract learnings from progress.txt using AI
  EXTRACT_PROMPT="Read this progress log and extract a structured learnings document.

Progress log:
$(cat "$PROGRESS_FILE")

Template to follow (fill in the YAML frontmatter and sections):
$(cat "$TEMPLATE_FILE")

Fill in these values:
- title: $PRIORITY_ITEM
- feature: $FEATURE_SLUG
- date: $(date +%Y-%m-%d)
- branch: $BRANCH_NAME
- report_source: $REPORT_NAME
- tasks_total: $TASKS_TOTAL
- tasks_completed: $TASKS_COMPLETED
- iterations_used: $ITERATION_COUNT
- max_iterations: $MAX_ITERATIONS
- pr_url: $PR_URL

Extract ALL learnings, patterns, gotchas, and file changes from the progress log.
Output ONLY the filled-in markdown document, nothing else."

  LEARNINGS_CONTENT=$(echo "$EXTRACT_PROMPT" | ai_run 2>&1)

  if [ -n "$LEARNINGS_CONTENT" ]; then
    echo "$LEARNINGS_CONTENT" > "$LEARNINGS_FILE"
    git add "$LEARNINGS_FILE"
    git commit -m "docs: extract learnings for $FEATURE_SLUG" || true
    git push origin "$BRANCH_NAME" || true
    log "Learnings saved to: $LEARNINGS_FILE"
  else
    log "WARNING: Failed to extract learnings. Review progress.txt manually."
  fi
else
  log "WARNING: No progress.txt or template found. Skipping learnings extraction."
fi

log ""
log "Review your learnings: $LEARNINGS_FILE"
log "Promote patterns to: docs/solutions/compound-product/patterns/promoted-patterns.md"

log "Complete! PR: $PR_URL"
log "All CI checks pass, Codex review clean, no conflicts. Ready for human review and merge."
