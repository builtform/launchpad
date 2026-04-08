---
name: regenerate-backlog
description: "Regenerates docs/tasks/BACKLOG.md from deferred observations and section registry. Called by /harness:build, /commit, and /triage."
---

# /regenerate-backlog

Generates `docs/tasks/BACKLOG.md` from source data. Single reusable command called by three workflow endpoints.

## Usage

```
/regenerate-backlog              → regenerate backlog (no staging)
/regenerate-backlog --stage      → regenerate and git add (used by /harness:build)
```

**Arguments:** `$ARGUMENTS` (parse for `--stage` flag)

---

## Flow

### Step 1: Read Deferred Items

1. Pre-filter: `grep -l "status: deferred" .harness/observations/*.md 2>/dev/null`
2. For each match: read YAML frontmatter (first 10 lines)
3. Skip files with malformed frontmatter (warn and continue)
4. Sort by priority (P1 → P2 → P3)
5. Cap at 15 items. If more: note "{N} more deferred items not shown."

### Step 2: Read Section Registry

1. Count section statuses: `grep -rl '^status: built' docs/tasks/sections/ 2>/dev/null | wc -l` (repeat per status: built, reviewed, hardened, planned, designed, shaped, defined)
2. IF `docs/tasks/sections/` empty or missing: "No sections defined."

### Step 3: Generate BACKLOG.md

Write `docs/tasks/BACKLOG.md` with this template:

```markdown
# Project Backlog

**Generated:** YYYY-MM-DD HH:MM | **Branch:** {current branch}

## Deferred Items ({N} total)

| P   | Area | Description | Source |
| --- | ---- | ----------- | ------ |
| ... | ...  | ...         | ...    |

## Section Status

{X} built | {Y} hardened | {Z} planned | ...

## Next Actions

1. Address P1 items: /triage
2. Plan a new section: /harness:plan
3. Continue building (approved plan): /harness:build
4. Add a task: /defer "description" --priority P2
```

After generation: check character count. IF >1,200 chars: reduce table rows until within budget.

### Step 4: Stage (conditional)

IF `--stage` flag: `git add docs/tasks/BACKLOG.md`
