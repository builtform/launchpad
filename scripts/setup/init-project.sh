#!/usr/bin/env bash
# =============================================================================
# init-project.sh — Launchpad initialization wizard
#
# Transforms a fresh Launchpad clone into your project by:
#   1. Collecting project metadata via interactive prompts (or CLI flags)
#   2. Preserving Launchpad docs as a reference guide
#   3. Swapping template files into their final positions
#   4. Replacing all placeholders with your project's values
#
# Git history detachment is intentionally left as a manual step (see output).
#
# Usage:
#   Interactive:       ./scripts/setup/init-project.sh
#   Non-interactive:   ./scripts/setup/init-project.sh --non-interactive \
#                        --name "My Project" --copyright "Acme Inc" --email "dev@acme.com"
#
# This script is safe to run only ONCE. After running, review changes with
# `git diff` and commit. You can then delete this script.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
NON_INTERACTIVE=false
PROJECT_NAME=""
PROJECT_DESCRIPTION="A project built with Launchpad"
COPYRIGHT_HOLDER=""
CONTACT_EMAIL=""
LICENSE_TYPE="MIT"
REPO_VISIBILITY="private"
TARGET_DIR=""
GITHUB_ORG=""

usage() {
  cat <<USAGE
Usage: $0 [OPTIONS]

Options:
  --non-interactive   Run without prompts (requires --name, --copyright, --email)
  --name NAME         Project name (required in non-interactive mode)
  --description DESC  Description (default: "A project built with Launchpad")
  --copyright HOLDER  Copyright holder (required in non-interactive mode)
  --email EMAIL       Contact email (required in non-interactive mode)
  --license TYPE      License type (default: MIT)
  --visibility TYPE   private or public (default: private)
  --target-dir DIR    Target directory to initialize into
  --github-org ORG    GitHub organization or username
  -h, --help          Show this help message

Examples:
  # Interactive mode
  $0

  # AI agent / CI mode
  $0 --non-interactive --name "My App" --copyright "Acme Inc" --email "dev@acme.com"
USAGE
  exit 0
}

require_value() {
  if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
    echo "Error: $1 requires a value" >&2; exit 1
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --non-interactive) NON_INTERACTIVE=true; shift ;;
    --name)         require_value "$1" "${2:-}"; PROJECT_NAME="$2"; shift 2 ;;
    --description)  require_value "$1" "${2:-}"; PROJECT_DESCRIPTION="$2"; shift 2 ;;
    --copyright)    require_value "$1" "${2:-}"; COPYRIGHT_HOLDER="$2"; shift 2 ;;
    --email)        require_value "$1" "${2:-}"; CONTACT_EMAIL="$2"; shift 2 ;;
    --license)      require_value "$1" "${2:-}"; LICENSE_TYPE="$2"; shift 2 ;;
    --visibility)   require_value "$1" "${2:-}"; REPO_VISIBILITY="$2"; shift 2 ;;
    --target-dir)   require_value "$1" "${2:-}"; TARGET_DIR="$2"; shift 2 ;;
    --github-org)   require_value "$1" "${2:-}"; GITHUB_ORG="$2"; shift 2 ;;
    -h|--help)      usage ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Validate required args in non-interactive mode
if [ "$NON_INTERACTIVE" = true ]; then
  MISSING=""
  [ -z "$PROJECT_NAME" ] && MISSING="$MISSING --name"
  [ -z "$COPYRIGHT_HOLDER" ] && MISSING="$MISSING --copyright"
  [ -z "$CONTACT_EMAIL" ] && MISSING="$MISSING --email"
  if [ -n "$MISSING" ]; then
    echo "Error: Missing required flags for --non-interactive mode:$MISSING" >&2
    exit 1
  fi
  # Same character validation as interactive mode
  if printf '%s' "$PROJECT_NAME" | grep -qE '[`$()!]|[[:cntrl:]]'; then
    echo "Error: Project name contains invalid characters. Avoid backticks, dollar signs, parentheses, exclamation marks, and control characters." >&2
    exit 1
  fi
elif [ ! -t 0 ]; then
  echo "Error: stdin is not a terminal. Use --non-interactive for AI agents / CI." >&2
  echo "Example: $0 --non-interactive --name \"My App\" --copyright \"Acme\" --email \"dev@acme.com\"" >&2
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
# Target directory support — copy harness into a different directory
# ---------------------------------------------------------------------------
if [ -n "${TARGET_DIR:-}" ]; then
  if [ ! -d "$TARGET_DIR" ]; then
    error "Target directory does not exist: $TARGET_DIR"
    exit 1
  fi
  # Guard against copy-into-self (target inside the current repo)
  _src_real="$(cd "$REPO_ROOT" && pwd -P)"
  _tgt_real="$(cd "$TARGET_DIR" && pwd -P)"
  if [ "$_tgt_real" = "$_src_real" ] || [[ "$_tgt_real" == "$_src_real"/* ]]; then
    error "Target directory is inside the source repo: $TARGET_DIR"
    exit 1
  fi
  # Require empty target directory to prevent silent overwrites
  if [ -n "$(ls -A "$TARGET_DIR" 2>/dev/null)" ]; then
    error "Target directory is not empty: $TARGET_DIR. Use an empty directory."
    exit 1
  fi
  cp -r . "$TARGET_DIR/"
  cd "$TARGET_DIR"
  REPO_ROOT="$TARGET_DIR"
  info "Working in target directory: $TARGET_DIR"
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
# Step 1 — Collect user inputs via interactive prompts (or use CLI flags)
# ---------------------------------------------------------------------------
heading "Initializing your project from Launchpad..."
echo ""

if [ "$NON_INTERACTIVE" = false ]; then
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
  echo "  4) UNLICENSED (proprietary)"
  echo "  5) Other"
  while true; do
    read -p "Select license [1]: " LICENSE_CHOICE
    LICENSE_CHOICE="${LICENSE_CHOICE:-1}"
    case "$LICENSE_CHOICE" in
      1) LICENSE_TYPE="MIT"; break ;;
      2) LICENSE_TYPE="Apache-2.0"; break ;;
      3) LICENSE_TYPE="GPL-3.0"; break ;;
      4) LICENSE_TYPE="UNLICENSED"; break ;;
      5) read -p "Enter license identifier: " LICENSE_TYPE; break ;;
      *) warn "Enter 1, 2, 3, 4, or 5." ;;
    esac
  done
  if [ "$LICENSE_TYPE" != "MIT" ] && [ "$LICENSE_TYPE" != "UNLICENSED" ]; then
    warn "Only MIT license text is included in the template. Update your LICENSE file manually for $LICENSE_TYPE."
  fi

  while true; do
    read -p "Repository visibility — private or public (required): " REPO_VISIBILITY
    REPO_VISIBILITY="$(printf '%s' "$REPO_VISIBILITY" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
    [[ "$REPO_VISIBILITY" == "private" || "$REPO_VISIBILITY" == "public" ]] && break
    warn "Please enter 'private' or 'public'."
  done

  read -p "GitHub organization or username []: " GITHUB_ORG
  GITHUB_ORG="${GITHUB_ORG:-}"
fi

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
echo "  GitHub org:       ${GITHUB_ORG:-<not set>}"
echo "  Year:             $CURRENT_YEAR"
echo ""

if [ "$NON_INTERACTIVE" = false ]; then
  read -p "This will initialize the project. Continue? [y/N] " CONFIRM
  case "$CONFIRM" in
    [yY]|[yY][eE][sS]) ;;
    *)
      warn "Aborted by user."
      exit 0
      ;;
  esac
else
  info "Non-interactive mode — auto-confirming."
fi

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
# Step 1/3 — Preserve Launchpad documentation
# ---------------------------------------------------------------------------
heading "Step 1/3 — Preserving Launchpad documentation..."

INIT_STARTED=true
mkdir -p .launchpad

# Write harness version (for future CLI upgrades via npx create-launchpad --upgrade)
echo "1.0.0" > .launchpad/version
info "Created .launchpad/version (harness v1.0.0)"

# ---------------------------------------------------------------------------
# Step 2/3 — Swap template files into their final positions
# ---------------------------------------------------------------------------
heading "Step 2/3 — Swapping template files..."

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
if [ "$REPO_VISIBILITY" = "public" ]; then
  swap_template "SECURITY.template.md"        "SECURITY.md"
else
  rm -f "SECURITY.template.md"
  info "Skipped SECURITY.md (private repository)"
fi
swap_template "CODE_OF_CONDUCT.template.md" "CODE_OF_CONDUCT.md"
swap_template "CHANGELOG.template.md"       "CHANGELOG.md"
swap_template "CONTRIBUTING.template.md"    "CONTRIBUTING.md"

# Move Launchpad-specific docs to .launchpad/ for reference
if [ -f "docs/guides/METHODOLOGY.md" ]; then
  mv "docs/guides/METHODOLOGY.md" ".launchpad/METHODOLOGY.md"
  info "Moved docs/guides/METHODOLOGY.md -> .launchpad/METHODOLOGY.md"
fi

if [ -f "docs/guides/HOW_IT_WORKS.md" ]; then
  mv "docs/guides/HOW_IT_WORKS.md" ".launchpad/HOW_IT_WORKS.md"
  info "Moved docs/guides/HOW_IT_WORKS.md -> .launchpad/HOW_IT_WORKS.md"
fi

# Update REPOSITORY_STRUCTURE.md to reflect moved files (Issue #10)
replace_in_file "docs/architecture/REPOSITORY_STRUCTURE.md" \
  '│   │   └── METHODOLOGY.md' \
  '│   │   └── *(METHODOLOGY.md moved to .launchpad/ during initialization)*'

if [ -f "docs/architecture/REPOSITORY_STRUCTURE.md" ]; then
  _repo_struct_tmp="$(mktemp)"
  sed '/\.gitattributes/d' "docs/architecture/REPOSITORY_STRUCTURE.md" > "$_repo_struct_tmp" && mv "$_repo_struct_tmp" "docs/architecture/REPOSITORY_STRUCTURE.md"
fi

# ---------------------------------------------------------------------------
# Clean up template file references from generated project files
# After swapping .template files → final files, references to the templates
# in docs and scripts are no longer valid for the generated project.
# ---------------------------------------------------------------------------

# Clean template references from REPOSITORY_STRUCTURE.md
if [ -f "docs/architecture/REPOSITORY_STRUCTURE.md" ]; then
  _rs_file="docs/architecture/REPOSITORY_STRUCTURE.md"

  # Remove the ".template pair" note from the section header
  _tmp="$(mktemp)"
  sed '/each doc may have a `\.template` pair/d' "$_rs_file" > "$_tmp" && mv "$_tmp" "$_rs_file"

  # Remove lines referencing individual template files
  for tpl in "CONTRIBUTING.template.md" "CODE_OF_CONDUCT.template.md" "CHANGELOG.template.md" "LICENSE.template" "SECURITY.template.md"; do
    _tmp="$(mktemp)"
    sed "/$(printf '%s' "$tpl" | sed 's/\./\\./g')/d" "$_rs_file" > "$_tmp" && mv "$_tmp" "$_rs_file"
  done

  info "Removed template file references from REPOSITORY_STRUCTURE.md"
fi

# Clean template entries from ALLOWED_DOCS in check-repo-structure.sh
if [ -f "scripts/maintenance/check-repo-structure.sh" ]; then
  _cs_file="scripts/maintenance/check-repo-structure.sh"

  for tpl in "README.template.md" "CONTRIBUTING.template.md" "CODE_OF_CONDUCT.template.md" "CHANGELOG.template.md" "LICENSE.template" "SECURITY.template.md"; do
    _tmp="$(mktemp)"
    sed "/\"$(printf '%s' "$tpl" | sed 's/\./\\./g')\"/d" "$_cs_file" > "$_tmp" && mv "$_tmp" "$_cs_file"
  done

  info "Removed template entries from check-repo-structure.sh ALLOWED_DOCS"
fi

# For private repos, remove SECURITY.md references from generated project
if [ "$REPO_VISIBILITY" = "private" ]; then
  # Remove SECURITY.md from REPOSITORY_STRUCTURE.md
  if [ -f "docs/architecture/REPOSITORY_STRUCTURE.md" ]; then
    _tmp="$(mktemp)"
    sed '/SECURITY\.md/d' "docs/architecture/REPOSITORY_STRUCTURE.md" > "$_tmp" && mv "$_tmp" "docs/architecture/REPOSITORY_STRUCTURE.md"
    info "Removed SECURITY.md references from REPOSITORY_STRUCTURE.md (private repo)"
  fi

  # Remove SECURITY.md from check-repo-structure.sh ALLOWED_DOCS
  if [ -f "scripts/maintenance/check-repo-structure.sh" ]; then
    _tmp="$(mktemp)"
    sed '/"SECURITY\.md"/d' "scripts/maintenance/check-repo-structure.sh" > "$_tmp" && mv "$_tmp" "scripts/maintenance/check-repo-structure.sh"
    info "Removed SECURITY.md from check-repo-structure.sh whitelist (private repo)"
  fi
fi

# Create .gitkeep in docs/guides if it's now empty (Issue B4)
if [ -d "docs/guides" ] && [ -z "$(ls -A docs/guides 2>/dev/null)" ]; then
  touch docs/guides/.gitkeep
  info "Created docs/guides/.gitkeep"
fi

# Create DESIGN_SYSTEM.md stub if it doesn't already exist
if [ ! -f "docs/architecture/DESIGN_SYSTEM.md" ]; then
  mkdir -p docs/architecture
  cat > docs/architecture/DESIGN_SYSTEM.md <<'DSSTUB'
# Design System

<!-- This document is populated by running /define-design in Claude Code.
     It captures your visual design decisions: color palette, typography, spacing,
     component conventions, responsive breakpoints, and animation guidelines.

     Until populated, this file serves as a placeholder. Do not delete it —
     /define-design expects it to exist and will fill it with your answers.

     To populate: run /define-design in Claude Code (requires PRD.md to exist first). -->

> **Status:** Stub — run `/define-design` to populate.
DSSTUB
  info "Created docs/architecture/DESIGN_SYSTEM.md stub"
fi

# Create docs/tasks/sections/ directory for /shape-section specs
mkdir -p docs/tasks/sections
if [ ! -f "docs/tasks/sections/.gitkeep" ]; then
  touch docs/tasks/sections/.gitkeep
  info "Created docs/tasks/sections/.gitkeep"
fi

# Create docs/skills-catalog/ directory and initial skill tracking files
mkdir -p docs/skills-catalog
if [ ! -f "docs/skills-catalog/skills-usage.json" ]; then
  cat > docs/skills-catalog/skills-usage.json <<'SUEOF'
{
  "last_audit_date": null,
  "skills": {}
}
SUEOF
  info "Created docs/skills-catalog/skills-usage.json"
fi
if [ ! -f "docs/skills-catalog/skills-index.md" ]; then
  cat > docs/skills-catalog/skills-index.md <<'SIEOF'
# Skills Index

A user-facing reference for all installed skills in this project. Each skill is a reusable workflow that Claude Code executes when triggered by a slash command or natural language.

---

## How Skill Tracking Works

- **Installation:** Skills are added via `/create-skill` or `/port-skill` and registered in this index, `CLAUDE.md`, `AGENTS.md`, and `skills-usage.json`.
- **Usage tracking:** `scripts/hooks/track-skill-usage.sh` fires after every skill invocation and records the date in `skills-usage.json`.
- **Staleness audit:** `scripts/hooks/audit-skills.sh` fires at session end. If 2+ weeks have passed since the last audit, it reports which skills are stale or unused.

---

## Quick Reference

No skills installed yet. Use `/create-skill` or `/port-skill` to add skills.

---

## Detailed Descriptions

No skills installed yet.
SIEOF
  info "Created docs/skills-catalog/skills-index.md stub"
fi

# Create scripts/hooks/ directory and copy hook scripts
mkdir -p scripts/hooks
if [ ! -f "scripts/hooks/track-skill-usage.sh" ]; then
  warn "scripts/hooks/track-skill-usage.sh not found — skill tracking hook unavailable"
else
  chmod +x scripts/hooks/track-skill-usage.sh
fi
if [ ! -f "scripts/hooks/audit-skills.sh" ]; then
  warn "scripts/hooks/audit-skills.sh not found — skill audit hook unavailable"
else
  chmod +x scripts/hooks/audit-skills.sh
fi

# Set up .claude/settings.json with skill tracking hooks (if not already configured)
if [ ! -f ".claude/settings.json" ]; then
  cat > .claude/settings.json <<'CSEOF'
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "bash scripts/hooks/track-skill-usage.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash scripts/hooks/audit-skills.sh"
          }
        ]
      }
    ]
  }
}
CSEOF
  info "Created .claude/settings.json with skill tracking hooks"
else
  info ".claude/settings.json already exists — verify skill tracking hooks are configured"
fi

# ---------------------------------------------------------------------------
# Step 3/3 — Fill all placeholders with user inputs
# ---------------------------------------------------------------------------
heading "Step 3/3 — Replacing placeholders..."

# --- Files that were just swapped from templates ---
TEMPLATE_TARGETS=(
  "README.md"
  "LICENSE"
  "CODE_OF_CONDUCT.md"
  "CHANGELOG.md"
  "CONTRIBUTING.md"
)
if [ "$REPO_VISIBILITY" = "public" ]; then
  TEMPLATE_TARGETS+=("SECURITY.md")
fi

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

# Replace LICENSE body for non-MIT license types (Issue #6)
if [ "$LICENSE_TYPE" = "UNLICENSED" ]; then
  cat > LICENSE <<LICEOF
UNLICENSED — Proprietary Software

Copyright (c) $CURRENT_YEAR $COPYRIGHT_HOLDER. All rights reserved.

This software and its source code are the proprietary and confidential
property of $COPYRIGHT_HOLDER. No part of this software may be
reproduced, distributed, or transmitted in any form or by any means
without the prior written permission of the copyright holder.

Unauthorized copying, modification, distribution, or use of this
software, via any medium, is strictly prohibited.
LICEOF
  info "LICENSE file set to proprietary (UNLICENSED)"
elif [ "$LICENSE_TYPE" != "MIT" ]; then
  cat > LICENSE <<LICEOF
$LICENSE_TYPE License

Copyright (c) $CURRENT_YEAR $COPYRIGHT_HOLDER

This project is licensed under the $LICENSE_TYPE license.
See https://spdx.org/licenses/$LICENSE_TYPE.html for the full text.

TODO: Replace this file with the full $LICENSE_TYPE license text.
LICEOF
  warn "LICENSE file contains a $LICENSE_TYPE placeholder. Replace with the full license text."
fi

# Replace contact email in SECURITY.md (public repos only)
if [ "$REPO_VISIBILITY" = "public" ]; then
  replace_in_file "SECURITY.md" '\[INSERT CONTACT EMAIL\]' "$CONTACT_EMAIL"
  info "Replaced [INSERT CONTACT EMAIL] in SECURITY.md"
fi

# Replace contact method in CODE_OF_CONDUCT.md
replace_in_file "CODE_OF_CONDUCT.md" '\[INSERT CONTACT METHOD\]' "$CONTACT_EMAIL"
info "Replaced [INSERT CONTACT METHOD] in CODE_OF_CONDUCT.md"

# Replace {{REPO_URL}} in CONTRIBUTING.md (uses REPO_SLUG and GITHUB_ORG)
if [ -n "$GITHUB_ORG" ]; then
  replace_in_file "CONTRIBUTING.md" '{{REPO_URL}}' "https://github.com/${GITHUB_ORG}/${REPO_SLUG}.git"
else
  replace_in_file "CONTRIBUTING.md" '{{REPO_URL}}' "https://github.com/YOUR_ORG/${REPO_SLUG}.git"
  warn "No GitHub org provided — update CONTRIBUTING.md repo URL manually."
fi
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
    # Collapse runs of 3+ blank lines into 2 (prevents leftover gaps after deletion)
    tmp="$(mktemp)"
    awk 'BEGIN{b=0} /^$/{b++;if(b<=2)print;next} {b=0;print}' "$file" > "$tmp" && mv "$tmp" "$file"
    # Remove leading blank lines
    tmp="$(mktemp)"
    sed '/./,$!d' "$file" > "$tmp" && mv "$tmp" "$file"
  fi
}
NOTICE_FILES=("README.md" "CODE_OF_CONDUCT.md" "CONTRIBUTING.md")
if [ "$REPO_VISIBILITY" = "public" ]; then
  NOTICE_FILES+=("SECURITY.md")
fi
for file in "${NOTICE_FILES[@]}"; do
  clean_template_notices "$file"
done
info "Cleaned up template notices from swapped files"

# Clean instructional HTML comments from CLAUDE.md (e.g., <!-- 2-4 sentences -->)
clean_instructional_comments() {
  local file="$1"
  if [ -f "$file" ]; then
    local tmp
    tmp="$(mktemp)"
    sed '/^<!--.*-->$/d' "$file" > "$tmp" && mv "$tmp" "$file"
  fi
}
clean_instructional_comments "CLAUDE.md"
info "Cleaned instructional comments from CLAUDE.md"

# ---------------------------------------------------------------------------
# Generate .env.local from .env.example (Issue #4)
# ---------------------------------------------------------------------------
if [ ! -f ".env.local" ] && [ -f ".env.example" ]; then
  cp .env.example .env.local
  info "Created .env.local from .env.example"

  if [ "$NON_INTERACTIVE" = false ]; then
    echo ""
    read -p "Enter DATABASE_URL (or press Enter to use default): " DB_URL
    if [ -n "$DB_URL" ]; then
      replace_in_file ".env.local" 'postgresql://user:password@localhost:5432/mydb' "$DB_URL"
      info "Updated DATABASE_URL in .env.local"
    else
      warn "Using placeholder DATABASE_URL in .env.local — update before running the API."
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Generate .env.consultant credential-sharing audit log
# ---------------------------------------------------------------------------
if [ ! -f ".env.consultant" ]; then
  cat > .env.consultant <<'ENVCON'
# ============================================================================
# .env.consultant — Credential Sharing Manifest
# ============================================================================
#
# PURPOSE: Track which environment variables/secrets were shared with
# external contractors or consultants. This file is your rotation checklist
# when an engagement ends.
#
# THIS FILE MUST NEVER CONTAIN ACTUAL SECRET VALUES.
# Only record: variable name, recipient, date shared, and status.
#
# WORKFLOW:
#   1. When you share a credential with a contractor, log it here
#   2. Share the actual value via a secure channel (1Password, EnvShare, etc.)
#   3. When the engagement ends, rotate every credential listed below
#   4. Mark each entry as [ROTATED] with the rotation date
#
# FORMAT:
#   VARIABLE_NAME | recipient | date-shared | status
#
# SECURITY:
#   - This file is gitignored — do NOT commit it
#   - Do NOT put actual values here — this is a manifest, not a vault
#   - If you need to share this file itself, use an encrypted channel
#
# ============================================================================

# Example:
# OPENAI_API_KEY       | jane@contractor.com  | 2026-03-05 | ACTIVE
# DATABASE_URL         | jane@contractor.com  | 2026-03-05 | ROTATED 2026-06-01
# STRIPE_SECRET_KEY    | bob@freelance.dev    | 2026-01-15 | ROTATED 2026-04-01
ENVCON
  info "Created .env.consultant (credential-sharing audit log)"
fi

# ---------------------------------------------------------------------------
# Post-init verification — scan for unreplaced placeholders (Issue #9)
# ---------------------------------------------------------------------------
heading "Verifying initialization..."

PLACEHOLDER_PATTERN='\{\{[A-Z_]+\}\}'
VERIFICATION_FAILED=false

while IFS= read -r match; do
  case "$match" in .launchpad/*) continue ;; esac
  case "$match" in scripts/setup/init-project.sh*) continue ;; esac
  warn "Unreplaced placeholder found: $match"
  VERIFICATION_FAILED=true
done < <(grep -rn "$PLACEHOLDER_PATTERN" --include="*.md" --include="*.ts" --include="*.tsx" --include="*.json" --include="*.yml" --include="*.sh" . 2>/dev/null | grep -v node_modules | grep -v .launchpad/ | grep -v init-project.sh || true)

if [ "$VERIFICATION_FAILED" = true ]; then
  warn "Some placeholders were not replaced. Review the files above."
else
  info "All placeholders replaced successfully"
fi

# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------
trap - EXIT

# Rename origin → launchpad (since origin currently points to the Launchpad repo)
if git remote get-url origin 2>/dev/null | grep -qi "launchpad"; then
  git remote rename origin launchpad 2>/dev/null || true
  info "Renamed 'origin' remote to 'launchpad' (upstream harness)"
else
  git remote add launchpad https://github.com/thinkinghand/launchpad.git 2>/dev/null || true
  info "Added 'launchpad' remote for upstream updates"
fi

heading "Done!"

echo ""
printf "${GREEN}Project '${BOLD}%s${RESET}${GREEN}' files initialized successfully!${RESET}\n" "$PROJECT_NAME"
echo ""
echo "The original Launchpad documentation has been saved to:"
echo "   .launchpad/METHODOLOGY.md    (Launchpad architecture, diagrams, credits)"
echo "   .launchpad/HOW_IT_WORKS.md   (step-by-step workflow guide + troubleshooting)"
echo "   .launchpad/version           (harness version: 1.0.0)"
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
echo "Next steps (four-tier workflow):"
echo "  1. Install dependencies:    pnpm install && pnpm dev"
echo "  2. Start Claude Code:       claude"
echo "  3. Tier 0 — Capabilities:  /create-skill or /port-skill"
echo "  4. Tier 1 — Definition:"
echo "     a. /define-product         (PRD + Tech Stack)"
echo "     b. /define-design          (Design System, App Flow, Frontend Guidelines)"
echo "     c. /define-architecture    (Backend Structure, CI/CD)"
echo "  5. Tier 2 — Development:    /shape-section [name]"
echo "  6. Tier 3 — Implementation: /pnf [section] then /inf"
echo "  7. See the full workflow:   .launchpad/HOW_IT_WORKS.md"
echo ""

# Self-cleanup (Issue #8)
if [ "$NON_INTERACTIVE" = true ]; then
  rm -f scripts/setup/init-project.sh
  info "Removed init-project.sh (non-interactive cleanup)"
else
  echo ""
  read -p "Remove init-project.sh? It's no longer needed. [y/N] " REMOVE_INIT
  if [[ "$REMOVE_INIT" =~ ^[yY] ]]; then
    rm -f scripts/setup/init-project.sh
    info "Removed init-project.sh"
  fi
fi
