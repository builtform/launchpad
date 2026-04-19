#!/usr/bin/env bash
# Build scripts/build-plugin.sh
#
# Transforms .claude/ (source of truth) → plugin/ (committed build artifact).
# Deterministic: same source input produces byte-identical plugin output.
#
# Phase 1 orchestrator for the LaunchPad plugin. See
# docs/reports/launchpad_reports/2026-04-18-launchpad-plugin-extraction-plan.md
# for full spec.
set -euo pipefail

# ----------------------------------------------------------------------------
# Color helpers (mirrors scripts/setup/pull-upstream.launchpad.sh:24-36 style)
# ----------------------------------------------------------------------------
if [ -t 1 ]; then
  RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; BLUE=$'\e[34m'; RESET=$'\e[0m'
else
  RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi
info()    { echo "${BLUE}›${RESET} $*"; }
ok()      { echo "${GREEN}✓${RESET} $*"; }
warn()    { echo "${YELLOW}!${RESET} $*" >&2; }
err()     { echo "${RED}✗${RESET} $*" >&2; }
heading() { echo ""; echo "${BLUE}=== $* ===${RESET}"; }

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
REPO="$(git rev-parse --show-toplevel 2>/dev/null || { err "Not in a git repo"; exit 1; })"
SRC="$REPO/.claude"
DST="$REPO/plugin"
DST_NEW="$REPO/plugin.new"
DST_OLD="$REPO/plugin.old"

if [ ! -f "$REPO/VERSION" ]; then
  err "VERSION file missing at repo root"
  exit 1
fi
VERSION=$(tr -d '[:space:]' < "$REPO/VERSION")

heading "Preflight"

# ----------------------------------------------------------------------------
# Preflight: required tools
# ----------------------------------------------------------------------------
need_tool() {
  local tool=$1 hint=${2:-}
  if ! command -v "$tool" >/dev/null 2>&1; then
    err "$tool required. ${hint:-}"
    exit 1
  fi
}
need_tool jq "Install with: brew install jq"
need_tool python3 "Install Python 3.8+"
need_tool shasum "Should ship with macOS / coreutils"
need_tool find
need_tool sed

ok "preflight: jq, python3, shasum, find, sed"

# ----------------------------------------------------------------------------
# Trap: clean up scratch on any failure
# ----------------------------------------------------------------------------
cleanup() {
  local ec=$?
  if [ $ec -ne 0 ]; then
    rm -rf "$DST_NEW" 2>/dev/null || true
    # Restore old plugin/ if the swap was partial
    if [ -d "$DST_OLD" ] && [ ! -d "$DST" ]; then
      mv "$DST_OLD" "$DST"
    fi
  fi
  rm -rf "$DST_OLD" 2>/dev/null || true
}
trap cleanup EXIT

# ----------------------------------------------------------------------------
# 1. Clean scratch
# ----------------------------------------------------------------------------
heading "Stage scratch directory"
rm -rf "$DST_NEW"
mkdir -p \
  "$DST_NEW/.claude-plugin" \
  "$DST_NEW/agents" \
  "$DST_NEW/commands" \
  "$DST_NEW/skills" \
  "$DST_NEW/hooks" \
  "$DST_NEW/bin" \
  "$DST_NEW/data"
ok "scratch dir ready: $DST_NEW"

# ----------------------------------------------------------------------------
# 2. Agents — flatten subdirs with lp- prefix, rewrite frontmatter
# ----------------------------------------------------------------------------
heading "Copy agents"
python3 "$REPO/scripts/plugin-agent-copy.py" \
  --src "$SRC/agents" \
  --dst "$DST_NEW/agents" \
  --prefix lp-

# ----------------------------------------------------------------------------
# 3. Skills — copy dirs with lp- prefix, rewrite SKILL.md frontmatter
# ----------------------------------------------------------------------------
heading "Copy skills"
python3 "$REPO/scripts/plugin-skill-copy.py" \
  --src "$SRC/skills" \
  --dst "$DST_NEW/skills" \
  --prefix lp-

# ----------------------------------------------------------------------------
# 4. Frontmatter audit (every SKILL.md has name + description)
# ----------------------------------------------------------------------------
heading "Audit skill frontmatter"
bash "$REPO/scripts/plugin-audit-frontmatter.sh" "$DST_NEW/skills"

# ----------------------------------------------------------------------------
# 5. Commands — flatten harness subdir, apply lp- prefix, rewrite cross-refs
#    Drop: pull-launchpad (template-only per §4.7)
# ----------------------------------------------------------------------------
heading "Rewrite commands"
python3 "$REPO/scripts/plugin-command-rewrites.py" \
  --src "$SRC/commands" \
  --dst "$DST_NEW/commands" \
  --prefix lp- \
  --agents-src "$SRC/agents" \
  --drop pull-launchpad

# ----------------------------------------------------------------------------
# 6. Hooks + bin — copy with executable-bit propagation
#    EXCLUDE: scripts/maintenance/* (template-only per §4.7)
# ----------------------------------------------------------------------------
heading "Copy hooks + bin"
copy_with_perms() {
  local src=$1 dst=$2
  cp "$src" "$dst"
  # Propagate git-tracked executable bit when available; else preserve source's mode
  local rel=${src#"$REPO/"}
  if git ls-tree HEAD -- "$rel" 2>/dev/null | grep -q '^100755'; then
    chmod +x "$dst"
  elif [ -x "$src" ]; then
    chmod +x "$dst"
  fi
}

copy_with_perms "$SRC/hooks/block-merges.sh"        "$DST_NEW/bin/block-merges.sh"
copy_with_perms "$REPO/scripts/agent_hydration/hydrate.sh" "$DST_NEW/bin/hydrate.sh"

for f in "$REPO/scripts/hooks/"*.sh; do
  [ -f "$f" ] && copy_with_perms "$f" "$DST_NEW/bin/$(basename "$f")"
done

# Copy scripts/compound/ contents (runtime — needed by compound-learning.sh)
mkdir -p "$DST_NEW/bin/compound"
for f in "$REPO/scripts/compound/"*; do
  [ -f "$f" ] && copy_with_perms "$f" "$DST_NEW/bin/compound/$(basename "$f")"
done

ok "copied hook + bin scripts"

# ----------------------------------------------------------------------------
# 7. Self-locating shim — make scripts resilient to missing $CLAUDE_PLUGIN_ROOT
# ----------------------------------------------------------------------------
heading "Inject self-locating shim"
bash "$REPO/scripts/plugin-inject-shim.sh" "$DST_NEW/bin"

# ----------------------------------------------------------------------------
# 8. Hooks config
# ----------------------------------------------------------------------------
heading "Write hooks.json"
cat > "$DST_NEW/hooks/hooks.json" <<'EOF'
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          { "type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/bin/hydrate.sh\"" }
        ]
      },
      {
        "matcher": "clear",
        "hooks": [
          { "type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/bin/hydrate.sh\"" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/bin/block-merges.sh\"" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          { "type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/bin/track-skill-usage.sh\"" }
        ]
      }
    ]
  }
}
EOF
ok "hooks.json written"

# ----------------------------------------------------------------------------
# 9. Config defaults: generic-only secret patterns, schema-stamped agents.yml
# ----------------------------------------------------------------------------
heading "Seed plugin/data"
bash "$REPO/scripts/plugin-filter-secret-patterns.sh" \
  "$REPO/.launchpad/secret-patterns.txt" \
  > "$DST_NEW/data/secret-patterns.txt"

# Stamp schema_version at the top of the shipped agents.yml
( echo "# schema_version: 1"; cat "$REPO/.launchpad/agents.yml" ) > "$DST_NEW/data/agents.yml"
ok "seeded plugin/data (agents.yml + secret-patterns.txt)"

# ----------------------------------------------------------------------------
# 10. Secret self-scan — refuse to ship if any shipped file matches a pattern
# ----------------------------------------------------------------------------
heading "Secret self-scan"
# Scan agents.yml only (patterns file itself trivially matches its own patterns).
# Strip blank lines and comments from pattern file before feeding to grep -E.
PATTERN_TMP=$(mktemp)
grep -Ev '^[[:space:]]*(#|$)' "$DST_NEW/data/secret-patterns.txt" > "$PATTERN_TMP" || true
if [ -s "$PATTERN_TMP" ]; then
  if grep -E -f "$PATTERN_TMP" "$DST_NEW/data/agents.yml" >/dev/null 2>&1; then
    err "potential secret in plugin/data/agents.yml — refusing to ship"
    grep -E -f "$PATTERN_TMP" "$DST_NEW/data/agents.yml" >&2 || true
    rm -f "$PATTERN_TMP"
    exit 1
  fi
fi
rm -f "$PATTERN_TMP"
ok "secret-scan: clean"

# ----------------------------------------------------------------------------
# 11. Plugin manifest — stamp version from VERSION file
# ----------------------------------------------------------------------------
heading "Stamp plugin.json version"
jq --arg v "$VERSION" '.version = $v' "$REPO/scripts/plugin.template.json" \
  > "$DST_NEW/.claude-plugin/plugin.json"
ok "plugin.json version=$VERSION"

# ----------------------------------------------------------------------------
# 12. JSON validation
# ----------------------------------------------------------------------------
heading "JSON validation"
jq empty < "$DST_NEW/.claude-plugin/plugin.json"
jq empty < "$DST_NEW/hooks/hooks.json"
ok "plugin.json + hooks.json are valid JSON"

# ----------------------------------------------------------------------------
# 13. Rewrite assertions (prefix + no double-prefix + shape)
# ----------------------------------------------------------------------------
heading "Verify rewrites"
bash "$REPO/scripts/plugin-verify-rewrites.sh" "$DST_NEW" "$REPO" "lp-"

# ----------------------------------------------------------------------------
# 14. Unquoted-variable scan — protect against paths with spaces
# ----------------------------------------------------------------------------
heading "Unquoted \$CLAUDE_PLUGIN_ROOT scan"
# Match $VAR or ${VAR} without surrounding quotes. Allow echo/info style where
# the variable is inside quoted strings.
if grep -rEn '(^|[^"\x27])\$(CLAUDE_PLUGIN_ROOT|\{CLAUDE_PLUGIN_ROOT[^}]*\})([^"\x27]|$)' "$DST_NEW/bin/" 2>/dev/null; then
  err "unquoted \$CLAUDE_PLUGIN_ROOT in plugin scripts (breaks on paths with spaces)"
  exit 1
fi
ok "no unquoted \$CLAUDE_PLUGIN_ROOT uses"

# ----------------------------------------------------------------------------
# 14.5. Plugin-level docs (README / SECURITY / CHANGELOG)
# ----------------------------------------------------------------------------
heading "Copy plugin docs"
for doc in README.md SECURITY.md CHANGELOG.md; do
  src="$REPO/scripts/plugin-templates/$doc"
  if [ -f "$src" ]; then
    cp "$src" "$DST_NEW/$doc"
  fi
done
ok "plugin docs copied"

# ----------------------------------------------------------------------------
# 15. SHA256SUMS
# ----------------------------------------------------------------------------
heading "Generate SHA256SUMS"
(
  cd "$DST_NEW"
  find . -type f -not -name SHA256SUMS | LC_ALL=C sort | xargs shasum -a 256 > SHA256SUMS
)
ok "SHA256SUMS generated ($(wc -l < "$DST_NEW/SHA256SUMS" | tr -d ' ') entries)"

# ----------------------------------------------------------------------------
# 16. Atomic swap
# ----------------------------------------------------------------------------
heading "Atomic swap"
if [ -d "$DST" ]; then
  mv "$DST" "$DST_OLD"
fi
mv "$DST_NEW" "$DST"
if [ -d "$DST_OLD" ]; then
  rm -rf "$DST_OLD"
fi
ok "plugin/ updated"

# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
heading "Summary"
agent_count=$(find "$DST/agents" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
skill_count=$(find "$DST/skills" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')
command_count=$(find "$DST/commands" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
bin_count=$(find "$DST/bin" -name '*.sh' | wc -l | tr -d ' ')
total_size=$(du -sh "$DST" | cut -f1)

echo "  version:  ${GREEN}$VERSION${RESET}"
echo "  agents:   $agent_count"
echo "  skills:   $skill_count"
echo "  commands: $command_count"
echo "  scripts:  $bin_count"
echo "  size:     $total_size"
ok "plugin built at $DST"
