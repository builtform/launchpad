#!/bin/bash
# Repository Structure Compliance Checker
#
# This script enforces the repository structure rules defined in
# docs/architecture/REPOSITORY_STRUCTURE.md
#
# Used by:
# - Pre-commit hooks (fast local feedback)
# - CI/CD workflows (safety net for bypassed hooks)
#
# Exit codes:
# 0 = All checks passed
# 1 = Violations found

set -e

ERRORS=0
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "🔍 Checking repository structure compliance..."
echo ""

# ============================================================================
# Check 1: Duplicate Files (macOS Finder artifacts)
# ============================================================================
echo "📋 Checking for duplicate files..."

# Check for duplicate files (with and without extensions)
DUPLICATES=$(find "$REPO_ROOT" \
  \( -name "* 2.*" -o -name "* 2" -o -name "* v2.*" -o -name "* v2" -o -name "* copy.*" -o -name "* copy" -o -name ".* 2" \) \
  ! -path "*/node_modules/*" \
  ! -path "*/.git/*" \
  ! -path "*/.venv/*" \
  ! -path "*/.next/*" \
  ! -path "*/.turbo/*" \
  ! -path "*/data/*" \
  2>/dev/null || true)

# Also check for duplicate directories
DUPLICATE_DIRS=$(find "$REPO_ROOT" -type d \
  \( -name "* 2" -o -name "* v2" -o -name "* copy" \) \
  ! -path "*/node_modules/*" \
  ! -path "*/.git/*" \
  ! -path "*/.venv/*" \
  ! -path "*/.next/*" \
  ! -path "*/.turbo/*" \
  ! -path "*/data/*" \
  2>/dev/null || true)

# Combine results
DUPLICATES=$(printf "%s\n%s" "$DUPLICATES" "$DUPLICATE_DIRS" | grep -v '^$' || true)

if [ -n "$DUPLICATES" ]; then
  echo "❌ Found duplicate files (macOS Finder artifacts):"
  echo "$DUPLICATES" | sed 's/^/   /'
  echo ""
  echo "   ⚠️  MANUAL REVIEW REQUIRED - DO NOT AUTO-DELETE"
  echo ""
  echo "   Process for handling duplicates:"
  echo "   1. Compare both versions (original and ' 2'/' v2'/' copy' duplicate)"
  echo "   2. Determine which is more accurate/complete/recent"
  echo "   3. Keep the better version"
  echo "   4. Delete the inferior version"
  echo "   5. If duplicate was better, rename it to remove suffix"
  echo ""
  echo "   Comparison methods:"
  echo "   - Code/config files: Use 'diff', check file size, modification dates"
  echo "   - When uncertain: Ask maintainer for review"
  echo ""
  ERRORS=$((ERRORS + 1))
else
  echo "   ✅ No duplicate files found"
fi

echo ""

# ============================================================================
# Check 2: Non-Whitelisted Root Files
# ============================================================================
echo "📋 Checking for non-whitelisted root files..."

# Define whitelist (must match REPOSITORY_STRUCTURE.md Section 1)
ALLOWED_DOCS=(
  "README.md"
  "README.template.md"
  "CLAUDE.md"
  "CONTRIBUTING.md"
  "CONTRIBUTING.template.md"
  "CODE_OF_CONDUCT.md"
  "CODE_OF_CONDUCT.template.md"
  "AGENTS.md"
  "SECURITY.md"
  "SECURITY.template.md"
  "CHANGELOG.md"
  "CHANGELOG.template.md"
  "LICENSE"
  "LICENSE.template"
)

ALLOWED_CONFIGS=(
  ".gitignore"
  ".gitattributes"
  ".editorconfig"
  ".nvmrc"
  ".env.example"
  ".env.local"
  ".env.consultant"
  "package.json"
  "pnpm-lock.yaml"
  "pnpm-workspace.yaml"
  "turbo.json"
  "prettier.config.js"
  ".prettierignore"
  "eslint.config.mjs"
  "lefthook.yml"
  "vitest.config.ts"
  "tsconfig.json"
  ".worktreeinclude"
  ".DS_Store"
)

ALLOWED_DIRS=(
  "apps"
  "packages"
  "scripts"
  "docs"
  ".github"
  ".vscode"
  ".claude"
  ".launchpad"
  "node_modules"
  ".git"
  ".next"
  ".turbo"
  "dist"
  "build"
)

# Get all items at root (excluding hidden files starting with .)
ROOT_ITEMS=$(find "$REPO_ROOT" -maxdepth 1 -mindepth 1 ! -name ".*" -printf "%f\n" 2>/dev/null || \
             find "$REPO_ROOT" -maxdepth 1 -mindepth 1 ! -name ".*" -exec basename {} \; 2>/dev/null)

# Get hidden config files at root (starting with .)
HIDDEN_ROOT_ITEMS=$(find "$REPO_ROOT" -maxdepth 1 -name ".*" ! -name ".git" ! -name ".." ! -name "." -printf "%f\n" 2>/dev/null || \
                    find "$REPO_ROOT" -maxdepth 1 -name ".*" ! -name ".git" ! -name ".." ! -name "." -exec basename {} \; 2>/dev/null)

VIOLATIONS_FOUND=0

# Check each root item
while IFS= read -r item; do
  [ -z "$item" ] && continue

  # Skip if it's a directory and it's allowed
  if [ -d "$REPO_ROOT/$item" ]; then
    if [[ " ${ALLOWED_DIRS[@]} " =~ " ${item} " ]]; then
      continue
    else
      echo "   ❌ Non-whitelisted directory at root: $item"
      VIOLATIONS_FOUND=1
    fi
  fi

  # Skip if it's a file and it's allowed
  if [ -f "$REPO_ROOT/$item" ]; then
    if [[ " ${ALLOWED_DOCS[@]} " =~ " ${item} " ]] || [[ " ${ALLOWED_CONFIGS[@]} " =~ " ${item} " ]]; then
      continue
    else
      echo "   ❌ Non-whitelisted file at root: $item"
      VIOLATIONS_FOUND=1
    fi
  fi
done <<< "$ROOT_ITEMS"

# Check hidden files
while IFS= read -r item; do
  [ -z "$item" ] && continue

  if [ -f "$REPO_ROOT/$item" ]; then
    if [[ " ${ALLOWED_CONFIGS[@]} " =~ " ${item} " ]]; then
      continue
    else
      # Allow common hidden config files
      if [[ "$item" =~ ^\.(env\.|editorconfig|gitignore|gitattributes|prettierrc|prettierignore|nvmrc) ]]; then
        continue
      fi
      echo "   ❌ Non-whitelisted hidden file at root: $item"
      VIOLATIONS_FOUND=1
    fi
  fi
done <<< "$HIDDEN_ROOT_ITEMS"

if [ $VIOLATIONS_FOUND -eq 1 ]; then
  echo ""
  echo "   Fix: Move these files to appropriate subdirectories"
  echo "   See: docs/architecture/REPOSITORY_STRUCTURE.md Section 1"
  echo ""
  ERRORS=$((ERRORS + 1))
else
  echo "   ✅ All root files are whitelisted"
fi

echo ""

# ============================================================================
# Check 3: Scripts at Root
# ============================================================================
echo "📋 Checking for loose scripts at root..."

# Find potential script files
POTENTIAL_SCRIPTS=$(find "$REPO_ROOT" -maxdepth 1 \( -name "*.sh" -o -name "*.py" \) ! -name ".*" 2>/dev/null || true)

# Filter out config files (e.g. prettier.config.js is a config, not a script)
LOOSE_SCRIPTS=""
while IFS= read -r script; do
  [ -z "$script" ] && continue
  filename=$(basename "$script")

  # Skip if it's in allowed configs
  if [[ " ${ALLOWED_CONFIGS[@]} " =~ " ${filename} " ]]; then
    continue
  fi

  LOOSE_SCRIPTS="$LOOSE_SCRIPTS$script
"
done <<< "$POTENTIAL_SCRIPTS"

if [ -n "$LOOSE_SCRIPTS" ]; then
  echo "   ❌ Found script files at root:"
  echo "$LOOSE_SCRIPTS" | sed 's/^/      /'
  echo ""
  echo "   Fix: Move scripts to scripts/ directory"
  echo "   - Repo-wide scripts → scripts/maintenance/ or scripts/agent_hydration/"
  echo "   - Frontend scripts → apps/web/scripts/"
  echo "   - Backend scripts → apps/api/scripts/"
  echo ""
  ERRORS=$((ERRORS + 1))
else
  echo "   ✅ No loose scripts at root"
fi

echo ""

# ============================================================================
# Check 4: Loose files in apps/web and apps/api (warn-only)
# ============================================================================
echo "📋 Checking for loose files in apps/web and apps/api..."

flag_loose_top_level() {
  local base=$1
  local hits=""

  # Allowed filenames at the top level of an app directory
  local allowed_names=(
    "README.md"
    ".env.example"
    "package.json" "pnpm-lock.yaml"
    "tsconfig.json" "jest.config.js" "jest.config.ts" "jest.config.mjs" "vitest.config.js" "vitest.config.ts"
    "next.config.js" "next.config.ts" "next.config.mjs" "next-env.d.ts" "postcss.config.js" "postcss.config.mjs" "tailwind.config.js" "tailwind.config.ts"
    ".eslintrc" ".eslintrc.js" ".eslintrc.cjs" ".eslintrc.json" "eslint.config.mjs"
    ".prettierrc" ".prettierrc.js" ".prettierrc.json"
  )

  local files
  files=$(find "$base" -maxdepth 1 -type f \( -name "*.sh" -o -name "*.py" -o -name "*.md" -o -name "*.ipynb" -o -name "*.ts" -o -name "*.tsx" \) 2>/dev/null || true)

  while IFS= read -r file; do
    [ -z "$file" ] && continue
    local name
    name=$(basename "$file")

    # Skip allowed names
    if [[ " ${allowed_names[@]} " =~ " ${name} " ]]; then
      continue
    fi

    hits="$hits$file
"
  done <<< "$files"

  echo "$hits"
}

LOOSE_WARNINGS=""

# apps/web
if [ -d "$REPO_ROOT/apps/web" ]; then
  hits=$(flag_loose_top_level "$REPO_ROOT/apps/web")
  [ -n "$hits" ] && LOOSE_WARNINGS="$LOOSE_WARNINGS\napps/web:\n$hits"
fi

# apps/api
if [ -d "$REPO_ROOT/apps/api" ]; then
  hits=$(flag_loose_top_level "$REPO_ROOT/apps/api")
  [ -n "$hits" ] && LOOSE_WARNINGS="$LOOSE_WARNINGS\napps/api:\n$hits"
fi

if [ -n "$LOOSE_WARNINGS" ]; then
  echo "   ⚠️  Found loose files at app roots:"
  echo -e "$LOOSE_WARNINGS"
  echo ""
  echo "   Guidance:"
  echo "   • Scripts (.sh) → scripts/ subdirectory at repo root"
  echo "   • Docs (.md except README.md) → docs/ subdirectory"
  echo "   • Notebooks (.ipynb) → docs/experiments/ or docs/archive/"
  echo "   • Source code (.ts, .tsx) → src/app/, src/components/, src/lib/ subdirectories"
  echo ""
  # Warn-only for now; to make this blocking, increment ERRORS.
else
  echo "   ✅ No loose files in apps/web or apps/api roots"
fi

echo ""

# ============================================================================
# Check 5: Sandbox Protocol - No imports from experiments/ in production code
# ============================================================================
echo "📋 Checking for production code importing from experiments/..."

EXPERIMENT_IMPORTS=""

# Check files in apps/ only (no services/ in this repo)
if [ -d "$REPO_ROOT/apps" ]; then
  EXPERIMENT_IMPORTS=$(grep -rn \
    --include="*.py" \
    --include="*.ts" \
    --include="*.tsx" \
    --include="*.js" \
    --include="*.jsx" \
    -E "(from experiments|import experiments)" \
    "$REPO_ROOT/apps" 2>/dev/null || true)
fi

if [ -n "$EXPERIMENT_IMPORTS" ]; then
  echo "   ❌ Found production code importing from experiments/:"
  echo "$EXPERIMENT_IMPORTS" | sed 's/^/      /'
  echo ""
  echo "   ⚠️  SANDBOX PROTOCOL VIOLATION"
  echo ""
  echo "   The Sandbox Protocol allows temporary imports from experiments/"
  echo "   for local testing, but you MUST NOT commit them."
  echo ""
  echo "   Fix:"
  echo "   1. If your experiment is complete, copy the logic to the canonical file"
  echo "   2. Revert the import back to the production module"
  echo "   3. Archive or delete the experiment file"
  echo ""
  echo "   See: CLAUDE.md (Sandbox Protocol)"
  echo ""
  ERRORS=$((ERRORS + 1))
else
  echo "   ✅ No imports from experiments/ in production code"
fi

echo ""


# ============================================================================
# Summary
# ============================================================================
if [ $ERRORS -eq 0 ]; then
  echo "✅ All repository structure checks passed!"
  echo ""
  exit 0
else
  echo "❌ Repository structure violations found: $ERRORS check(s) failed"
  echo ""
  echo "📖 Complete structure rules: docs/architecture/REPOSITORY_STRUCTURE.md"
  echo ""
  echo "Quick fixes:"
  echo "  - Duplicate files: Compare first, then delete inferior version"
  echo "  - Move root files to proper directories (see Section 1 whitelist)"
  echo "  - Move scripts to scripts/ subdirectories"
  echo ""
  exit 1
fi
