#!/usr/bin/env bash
# =============================================================================
# audit-skills.sh — Skill staleness audit hook
#
# Fires at session end (Stop hook). Reads the skill usage
# tracking file and reports which skills haven't been used recently.
#
# Behavior:
#   - Reads docs/skills-catalog/skills-usage.json
#   - If last_audit_date is less than 2 weeks ago, exits silently
#   - If >= 2 weeks (or never audited), outputs a staleness report to stdout
#   - Updates last_audit_date after reporting
#   - Does NOT auto-remove anything — informational only
#
# Staleness threshold: 14 days (2 weeks)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root
# ---------------------------------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

USAGE_FILE="$REPO_ROOT/docs/skills-catalog/skills-usage.json"
SKILLS_DIR="$REPO_ROOT/.claude/skills"

# ---------------------------------------------------------------------------
# Exit silently if usage file doesn't exist yet
# ---------------------------------------------------------------------------
if [ ! -f "$USAGE_FILE" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Require python3 for date math and JSON handling
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Run the audit check
# ---------------------------------------------------------------------------
python3 -c "
import json, sys, os
from datetime import datetime, timedelta

STALENESS_DAYS = 14
usage_file = sys.argv[1]
skills_dir = sys.argv[2]

# Load usage data
with open(usage_file, 'r') as f:
    data = json.load(f)

today = datetime.now().date()

# Check if audit is needed
last_audit = data.get('last_audit_date')
if last_audit:
    try:
        last_audit_date = datetime.strptime(last_audit, '%Y-%m-%d').date()
        if (today - last_audit_date).days < STALENESS_DAYS:
            sys.exit(0)  # Audited recently, exit silently
    except ValueError:
        pass  # Invalid date format, proceed with audit

# Discover installed skills from .claude/skills/
installed_skills = set()
if os.path.isdir(skills_dir):
    for entry in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, entry)
        skill_md = os.path.join(skill_path, 'SKILL.md')
        if os.path.isdir(skill_path) and os.path.isfile(skill_md):
            installed_skills.add(entry)

if not installed_skills:
    sys.exit(0)  # No skills installed, nothing to audit

# Build the report
usage_data = data.get('skills', {})
stale_skills = []
never_used_skills = []
recently_used_skills = []

for skill in sorted(installed_skills):
    last_used = usage_data.get(skill)
    if last_used is None:
        never_used_skills.append(skill)
    else:
        try:
            last_used_date = datetime.strptime(last_used, '%Y-%m-%d').date()
            days_ago = (today - last_used_date).days
            if days_ago >= STALENESS_DAYS:
                stale_skills.append((skill, last_used, days_ago))
            else:
                recently_used_skills.append((skill, last_used, days_ago))
        except ValueError:
            never_used_skills.append(skill)

# Only output if there are findings
if stale_skills or never_used_skills:
    print()
    print('=' * 60)
    print('  SKILL USAGE AUDIT REPORT')
    print('=' * 60)
    print()
    print(f'  Audit date: {today}')
    print(f'  Staleness threshold: {STALENESS_DAYS} days')
    print(f'  Skills installed: {len(installed_skills)}')
    print()

    if never_used_skills:
        print('  NEVER USED:')
        for skill in never_used_skills:
            print(f'    - {skill}  (no usage recorded)')
        print()

    if stale_skills:
        print('  STALE (not used in 2+ weeks):')
        for skill, last_used, days_ago in stale_skills:
            print(f'    - {skill}  (last used: {last_used}, {days_ago} days ago)')
        print()

    if recently_used_skills:
        print('  RECENTLY USED:')
        for skill, last_used, days_ago in recently_used_skills:
            print(f'    - {skill}  (last used: {last_used}, {days_ago} days ago)')
        print()

    print('  ACTION: Review stale/unused skills. Consider removing')
    print('  skills that are no longer needed to reduce prompt noise.')
    print('  No automatic changes have been made.')
    print()
    print('=' * 60)
    print()

# Update last_audit_date
data['last_audit_date'] = today.isoformat()
with open(usage_file, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" "$USAGE_FILE" "$SKILLS_DIR"
