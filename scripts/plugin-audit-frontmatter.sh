#!/usr/bin/env bash
# Validate that every SKILL.md has name + description in frontmatter.
set -euo pipefail

SKILLS_DIR="${1:?usage: $0 <plugin/skills dir>}"

errors=0
while IFS= read -r -d '' skill_md; do
  if ! head -n 20 "$skill_md" | grep -Eq '^name:[[:space:]]+'; then
    echo "ERROR: $skill_md missing 'name:' in frontmatter" >&2
    errors=$((errors + 1))
  fi
  if ! head -n 20 "$skill_md" | grep -Eq '^description:[[:space:]]+'; then
    echo "ERROR: $skill_md missing 'description:' in frontmatter" >&2
    errors=$((errors + 1))
  fi
done < <(find "$SKILLS_DIR" -name 'SKILL.md' -print0)

if [ "$errors" -gt 0 ]; then
  echo "  frontmatter audit: $errors error(s)" >&2
  exit 1
fi

echo "  frontmatter audit: ok" >&2
