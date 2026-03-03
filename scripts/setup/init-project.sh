#!/usr/bin/env bash
# =============================================================================
# init-project.sh — Interactive Launchpad initialization wizard
#
# Transforms a fresh Launchpad clone into your project by:
#   1. Collecting project metadata via interactive prompts
#   2. Preserving Launchpad docs as a reference guide
#   3. Swapping template files into their final positions
#   4. Replacing all placeholders with your project's values
#
# Git history detachment is intentionally left as a manual step (see output).
#
# Usage: ./scripts/setup/init-project.sh
#
# This script is safe to run only ONCE. After running, review changes with
# `git diff` and commit. You can then delete this script.
# =============================================================================

set -euo pipefail

if [ ! -t 0 ]; then
  echo "Error: init-project.sh must be run interactively (stdin is not a terminal)." >&2
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  echo "Error: do not run init-project.sh as root." >&2
  exit 1
fi

INIT_STARTED=false
cleanup() {
  if [ "$INIT_STARTED" = true ] && [ -d ".launchpad" ]; then
    rm -rf .launchpad
    git checkout -- . 2>/dev/null || true
    echo ""
    echo "Initialization failed. Changes have been rolled back."
    echo "Re-run the script to try again."
  fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Color helpers (disabled when stdout is not a terminal)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  RED='\033[0;31m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN=''
  YELLOW=''
  RED=''
  BOLD=''
  RESET=''
fi

info()    { printf "${GREEN}[OK]${RESET} %s\n" "$1"; }
warn()    { printf "${YELLOW}[WARN]${RESET} %s\n" "$1"; }
error()   { printf "${RED}[ERROR]${RESET} %s\n" "$1" >&2; }
heading() { printf "\n${BOLD}%s${RESET}\n" "$1"; }

# ---------------------------------------------------------------------------
# Verify we are running from the repo root
# ---------------------------------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "package.json" ] || [ ! -f "CLAUDE.md" ]; then
  error "This script must be run from the Launchpad repository root."
  error "Expected to find package.json and CLAUDE.md in: $REPO_ROOT"
  exit 1
fi

# ---------------------------------------------------------------------------
# Idempotency guard — prevent double-run
# ---------------------------------------------------------------------------
if [ -d ".launchpad" ]; then
  error "This project has already been initialized (found .launchpad/ directory)."
  error "init-project.sh should only run once."
  exit 1
fi

# ---------------------------------------------------------------------------
# Clean worktree guard — prevent data loss on rollback
# ---------------------------------------------------------------------------
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
  error "Working tree has uncommitted changes."
  error "Please commit or stash your changes before running init-project.sh."
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 1 — Collect user inputs via interactive prompts
# ---------------------------------------------------------------------------
heading "Initializing your project from Launchpad..."
echo ""

while true; do
  read -p "Project name (required): " PROJECT_NAME
  if [ -z "$PROJECT_NAME" ]; then
    warn "Project name is required."
    continue
  fi
  if printf '%s' "$PROJECT_NAME" | grep -qE '[`$()!]|[[:cntrl:]]'; then
    warn "Project name contains invalid characters. Avoid backticks, dollar signs, parentheses, exclamation marks, and control characters."
    continue
  fi
  break
done

read -p "Description (one line) [A project built with Launchpad]: " PROJECT_DESCRIPTION
PROJECT_DESCRIPTION="${PROJECT_DESCRIPTION:-A project built with Launchpad}"

while true; do
  read -p "Copyright holder (required): " COPYRIGHT_HOLDER
  [ -n "$COPYRIGHT_HOLDER" ] && break
  warn "Copyright holder is required."
done

while true; do
  read -p "Contact email (required): " CONTACT_EMAIL
  [ -n "$CONTACT_EMAIL" ] && break
  warn "Contact email is required."
done

echo ""
echo "License options:"
echo "  1) MIT"
echo "  2) Apache-2.0"
echo "  3) GPL-3.0"
echo "  4) Other"
while true; do
  read -p "Select license [1]: " LICENSE_CHOICE
  LICENSE_CHOICE="${LICENSE_CHOICE:-1}"
  case "$LICENSE_CHOICE" in
    1) LICENSE_TYPE="MIT"; break ;;
    2) LICENSE_TYPE="Apache-2.0"; break ;;
    3) LICENSE_TYPE="GPL-3.0"; break ;;
    4) read -p "Enter license identifier: " LICENSE_TYPE; break ;;
    *) warn "Enter 1, 2, 3, or 4." ;;
  esac
done
if [ "$LICENSE_TYPE" != "MIT" ]; then
  warn "Only MIT license text is included in the template. Update your LICENSE file manually for $LICENSE_TYPE."
fi

while true; do
  read -p "Repository visibility — private or public (required): " REPO_VISIBILITY
  REPO_VISIBILITY="$(printf '%s' "$REPO_VISIBILITY" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
  [[ "$REPO_VISIBILITY" == "private" || "$REPO_VISIBILITY" == "public" ]] && break
  warn "Please enter 'private' or 'public'."
done

CURRENT_YEAR="$(date +%Y)"

# ---------------------------------------------------------------------------
# Summary & confirmation
# ---------------------------------------------------------------------------
echo ""
heading "Configuration summary:"
echo "  Project name:     $PROJECT_NAME"
echo "  Description:      $PROJECT_DESCRIPTION"
echo "  Copyright holder: $COPYRIGHT_HOLDER"
echo "  Contact email:    $CONTACT_EMAIL"
echo "  License:          $LICENSE_TYPE"
echo "  Repository:       $REPO_VISIBILITY"
echo "  Year:             $CURRENT_YEAR"
echo ""

read -p "This will initialize the project. Continue? [y/N] " CONFIRM
case "$CONFIRM" in
  [yY]|[yY][eE][sS]) ;;
  *)
    warn "Aborted by user."
    exit 0
    ;;
esac

echo ""

# ---------------------------------------------------------------------------
# Helper: sed-safe escaping for replacement strings
# Escapes &, \, /, and | so they are treated literally by sed.
# ---------------------------------------------------------------------------
sed_escape() {
  printf '%s' "$1" | sed -e 's/[&\\/|]/\\&/g'
}

# ---------------------------------------------------------------------------
# Helper: replace a placeholder in a file (portable, no sed -i)
# Usage: replace_in_file <file> <pattern> <replacement>
# ---------------------------------------------------------------------------
replace_in_file() {
  local file="$1"
  local pattern="$2"
  local replacement
  replacement="$(sed_escape "$3")"
  if [ -f "$file" ]; then
    assert_not_symlink "$file"
    local tmp
    tmp="$(mktemp)"
    sed "s|${pattern}|${replacement}|g" "$file" > "$tmp" && mv "$tmp" "$file"
  fi
}

# ---------------------------------------------------------------------------
# Helper: abort if a file is a symlink (safety guard)
# ---------------------------------------------------------------------------
assert_not_symlink() {
  if [ -L "$1" ]; then
    error "Symlink detected: $1 — aborting for safety."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Step 1/4 — Preserve Launchpad README as a guide
# ---------------------------------------------------------------------------
heading "Step 1/4 — Preserving Launchpad documentation..."

INIT_STARTED=true
mkdir -p .launchpad

if [ -f "README.md" ] && [ ! -f ".launchpad/GUIDE.md" ]; then
  cp README.md .launchpad/GUIDE.md

  # Prepend a header note to the guide
  GUIDE_HEADER="> **Archived reference.** This is the original Launchpad documentation, preserved for reference.
> Your project's README is now at the repository root. For the full Launchpad workflow
> and available commands, refer to this file.

---

"
  TMPFILE="$(mktemp)"
  printf '%s' "$GUIDE_HEADER" | cat - .launchpad/GUIDE.md > "$TMPFILE"
  mv "$TMPFILE" .launchpad/GUIDE.md

  info "Saved README.md -> .launchpad/GUIDE.md"
else
  if [ -f ".launchpad/GUIDE.md" ]; then
    warn ".launchpad/GUIDE.md already exists — skipping."
  else
    warn "README.md not found — skipping guide preservation."
  fi
fi

# Write scaffold version (for future CLI upgrades via npx create-launchpad --upgrade)
echo "1.0.0" > .launchpad/version
info "Created .launchpad/version (scaffold v1.0.0)"

# ---------------------------------------------------------------------------
# Step 2/4 — Swap template files into their final positions
# ---------------------------------------------------------------------------
heading "Step 2/4 — Swapping template files..."

swap_template() {
  local template="$1"
  local target="$2"

  if [ -f "$template" ]; then
    assert_not_symlink "$template"
    rm -f "$target"
    mv "$template" "$target"
    info "$template -> $target"
  else
    warn "$template not found — skipping."
  fi
}

swap_template "README.template.md"          "README.md"
swap_template "LICENSE.template"            "LICENSE"
swap_template "SECURITY.template.md"        "SECURITY.md"
swap_template "CODE_OF_CONDUCT.template.md" "CODE_OF_CONDUCT.md"
swap_template "CHANGELOG.template.md"       "CHANGELOG.md"
swap_template "CONTRIBUTING.template.md"    "CONTRIBUTING.md"

# ---------------------------------------------------------------------------
# Step 3/4 — Fill all placeholders with user inputs
# ---------------------------------------------------------------------------
heading "Step 3/4 — Replacing placeholders..."

# --- Files that were just swapped from templates ---
TEMPLATE_TARGETS=(
  "README.md"
  "LICENSE"
  "SECURITY.md"
  "CODE_OF_CONDUCT.md"
  "CHANGELOG.md"
  "CONTRIBUTING.md"
)

# --- AI instruction files ---
AI_FILES=(
  "CLAUDE.md"
  "AGENTS.md"
)

# --- Other files with {{PROJECT_NAME}} placeholders ---
OTHER_FILES=(
  "apps/web/src/app/layout.tsx"
  "scripts/agent_hydration/hydrate.sh"
  "docs/architecture/REPOSITORY_STRUCTURE.md"
  "docs/architecture/CI_CD.md"
  ".claude/skills/tasks/SKILL.md"
  ".claude/commands/define-product.md"
)

# Combine all files that need {{PROJECT_NAME}} replacement
ALL_PROJECT_NAME_FILES=( "${TEMPLATE_TARGETS[@]}" "${AI_FILES[@]}" "${OTHER_FILES[@]}" )

# Replace {{PROJECT_NAME}} everywhere
for file in "${ALL_PROJECT_NAME_FILES[@]}"; do
  replace_in_file "$file" '{{PROJECT_NAME}}' "$PROJECT_NAME"
done
info "Replaced {{PROJECT_NAME}} in ${#ALL_PROJECT_NAME_FILES[@]} files"

# Derive repo slug from project name (lowercase kebab-case) — used for package.json, CONTRIBUTING.md, and completion output
REPO_SLUG="$(printf '%s' "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')"

# Update package.json name
if [ -f "package.json" ] && command -v node >/dev/null 2>&1; then
  node -e "const p=require('./package.json'); p.name='${REPO_SLUG}'; require('fs').writeFileSync('package.json', JSON.stringify(p, null, 2) + '\n')"
  info "Updated package.json name to '${REPO_SLUG}'"
fi

# Replace [Project Name] in AI instruction files and define-product command
for file in "${AI_FILES[@]}" ".claude/commands/define-product.md"; do
  replace_in_file "$file" '\[Project Name\]' "$PROJECT_NAME"
done
info "Replaced [Project Name] in AI instruction files"

# Replace {{PROJECT_DESCRIPTION}} in README and layout.tsx
replace_in_file "README.md" '{{PROJECT_DESCRIPTION}}' "$PROJECT_DESCRIPTION"
replace_in_file "apps/web/src/app/layout.tsx" '{{PROJECT_DESCRIPTION}}' "$PROJECT_DESCRIPTION"
info "Replaced {{PROJECT_DESCRIPTION}} in README.md and layout.tsx"

# Replace {{LICENSE_TYPE}} in README
replace_in_file "README.md" '{{LICENSE_TYPE}}' "$LICENSE_TYPE"
info "Replaced {{LICENSE_TYPE}} in README.md"

# Replace {{COPYRIGHT_HOLDER}} in README
replace_in_file "README.md" '{{COPYRIGHT_HOLDER}}' "$COPYRIGHT_HOLDER"
info "Replaced {{COPYRIGHT_HOLDER}} in README.md"

# Replace copyright holder in LICENSE
# The template uses [YOUR NAME OR ORGANIZATION] as the placeholder
replace_in_file "LICENSE" '\[YOUR NAME OR ORGANIZATION\]' "$COPYRIGHT_HOLDER"
info "Replaced copyright holder in LICENSE"

# Replace {{YEAR}} in LICENSE
replace_in_file "LICENSE" '{{YEAR}}' "$CURRENT_YEAR"
info "Replaced {{YEAR}} with $CURRENT_YEAR in LICENSE"

# Replace contact email in SECURITY.md
replace_in_file "SECURITY.md" '\[INSERT CONTACT EMAIL\]' "$CONTACT_EMAIL"
info "Replaced [INSERT CONTACT EMAIL] in SECURITY.md"

# Replace contact method in SECURITY.md and CODE_OF_CONDUCT.md
replace_in_file "SECURITY.md" '\[INSERT CONTACT METHOD\]' "$CONTACT_EMAIL"
replace_in_file "CODE_OF_CONDUCT.md" '\[INSERT CONTACT METHOD\]' "$CONTACT_EMAIL"
info "Replaced [INSERT CONTACT METHOD] in SECURITY.md and CODE_OF_CONDUCT.md"

# Replace {{REPO_URL}} in CONTRIBUTING.md (uses REPO_SLUG computed above)
replace_in_file "CONTRIBUTING.md" '{{REPO_URL}}' "https://github.com/YOUR_ORG/${REPO_SLUG}.git"
info "Replaced {{REPO_URL}} in CONTRIBUTING.md"

# Update the "Launchpad" title references in CLAUDE.md and AGENTS.md
# Replace the header line that says "Launchpad" with the project name
replace_in_file "CLAUDE.md" '# Launchpad – Claude Instructions' "# ${PROJECT_NAME} – Claude Instructions"
replace_in_file "AGENTS.md" '# Launchpad – Agent Instructions' "# ${PROJECT_NAME} – Agent Instructions"
info "Updated titles in CLAUDE.md and AGENTS.md"

# Update the WHY section description in CLAUDE.md and AGENTS.md
# Replace the {{PROJECT_PURPOSE}} placeholder with the user's description
replace_in_file "CLAUDE.md" '{{PROJECT_PURPOSE}}' "$PROJECT_DESCRIPTION"
replace_in_file "AGENTS.md" '{{PROJECT_PURPOSE}}' "$PROJECT_DESCRIPTION"
info "Updated WHY section in CLAUDE.md and AGENTS.md"

# Remove template notices from swapped files (clean up HTML comments)
clean_template_notices() {
  local file="$1"
  if [ -f "$file" ]; then
    local tmp
    tmp="$(mktemp)"
    sed '/^> \*\*Template notice:\*\*/,/^> Remove this notice/d' "$file" > "$tmp" && mv "$tmp" "$file"
    tmp="$(mktemp)"
    sed '/<!-- TEMPLATE:/,/-->/d' "$file" > "$tmp" && mv "$tmp" "$file"
  fi
}
for file in "README.md" "SECURITY.md" "CODE_OF_CONDUCT.md" "CONTRIBUTING.md"; do
  clean_template_notices "$file"
done
info "Cleaned up template notices from swapped files"

# ---------------------------------------------------------------------------
# Step 4/4 — Completion
# ---------------------------------------------------------------------------
trap - EXIT

git remote add launchpad https://github.com/thinkinghand/launchpad.git 2>/dev/null || true
info "Added 'launchpad' remote for upstream updates"

heading "Step 4/4 — Done!"

echo ""
printf "${GREEN}Project '${BOLD}%s${RESET}${GREEN}' files initialized successfully!${RESET}\n" "$PROJECT_NAME"
echo ""
echo "The original Launchpad documentation has been saved to:"
echo "   .launchpad/GUIDE.md   (workflow reference)"
echo "   .launchpad/version    (scaffold version: 1.0.0)"
echo ""
printf "${YELLOW}${BOLD}Next: set up your git history${RESET}\n"
echo ""
echo "Your project files have been customized. Run 'git diff' to verify,"
echo "then choose one of these options:"
echo ""
printf "${BOLD}  Option 1 — Fresh start (no upstream connection):${RESET}\n"
echo "    rm -rf .git && git init -b main && git add -A && git commit -m \"Initial commit\""
echo ""
printf "${BOLD}  Option 2 — Stay connected (recommended, enables upstream updates):${RESET}\n"
echo "    git remote rename origin launchpad"
echo "    git remote add origin <your-repo-url>"
echo "    git push -u origin main"
echo ""
echo "  To pull updates later:"
echo "    - In Claude Code: /pull-launchpad"
echo "    - Or manually:    bash scripts/setup/pull-upstream.launchpad.sh"
echo ""
printf "${BOLD}  (Optional) Create a GitHub repository and push:${RESET}\n"
echo "    gh repo create \"$REPO_SLUG\" --$REPO_VISIBILITY --source=. --push"
echo ""
echo "Next steps:"
echo "  1. Install dependencies:    pnpm install && pnpm dev"
echo "  2. Start Claude Code:       claude"
echo "  3. Define your product:     /define-product"
echo "  4. See the full workflow:   .launchpad/GUIDE.md"
echo ""
