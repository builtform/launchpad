---
name: harness:plan
description: Meta-orchestrator for interactive planning pipeline. Chains design → /pnf → /harden-plan → human approval based on section registry status.
---

# /harness:plan

Interactive planning pipeline orchestrator. Resolves target from section registry status and chains through design → plan → harden → approval.

**Arguments:** `$ARGUMENTS` (optional section name or free-text description)

---

## Guard: Status Check

1. Read section spec file's YAML frontmatter `status:` field
2. Validate registry integrity (see below)
3. IF status is `approved` or beyond → **REFUSE:** "Already approved. Run /harness:build"

### Registry Integrity Validation

Before proceeding, validate expected artifacts exist for current status:

| Status     | Expected Artifacts                                                                         |
| ---------- | ------------------------------------------------------------------------------------------ |
| `designed` | Design artifacts in `.harness/design-artifacts/` (or `"design:skipped"` with no artifacts) |
| `planned`  | Plan file exists                                                                           |
| `hardened` | Hardening notes section exists in plan                                                     |
| `approved` | `approved_at` field present + plan file exists                                             |

Refuse with descriptive error if inconsistent (e.g., "Status is 'approved' but approved_at field missing. Re-run /harness:plan for human approval.").

---

## Step 1: Resolve Target

### CASE A: Named target or no argument → registry lookup

Look up section in `docs/tasks/sections/{section-name}.md`:

| Current Status                   | Route To                          |
| -------------------------------- | --------------------------------- |
| `hardened`                       | Step 5 (approval)                 |
| `planned`                        | Step 4 (harden)                   |
| `designed` or `"design:skipped"` | Step 3 (plan)                     |
| `shaped`                         | Step 2 (design)                   |
| `defined` or no status           | "Not shaped. Run /harness:define" |
| No section found                 | → CASE B                          |

### CASE B: Free-text → Step 2

If no matching section or free-text provided, start from Step 2 (design check).

---

## Step 2: Design Step [Phase 10]

Check if section has UI components by examining the section spec for files matching:

- `apps/web/**/*.tsx`
- `packages/ui/**`
- Any `.css` or `.html` file

### IF section has UI components:

- Dispatch design workflow (agents defined in Phase 10)
- Set registry status → `designed`

### IF no UI components:

- Set registry status → `"design:skipped"` (quoted in YAML to avoid colon ambiguity)

**Note:** Design runs before `/pnf` so the plan incorporates design decisions.

---

## Step 3: /pnf [target]

- Run `/pnf` with the section target
- Produces implementation plan
- Set registry status → `planned`

---

## Step 4: /harden-plan [plan-path] --auto

- Determine intensity:
  - CASE A (section build): `--full` (8 agents when available)
  - CASE B (standalone feature): `--lightweight` (4 agents when available)
- Pass `--auto` for automatic application (no user prompt)
- `/harden-plan` is idempotent: skips if "## Hardening Notes" already exists
- Set registry status → `hardened`

---

## Step 5: Human Approval Gate

Present plan summary to user:

- Plan content (key sections)
- Hardening notes
- Design status (`designed` or `"design:skipped"`)

Ask: **"Approve this plan for build? (yes/no/revise)"**

### IF yes:

- Set registry status → `approved`
- Write `approved_at: <ISO-8601 timestamp>` to section spec frontmatter
- Write `plan_hash: <short hash of plan file at approval time>` to section spec frontmatter

### IF revise:

- Reset status to `shaped` (re-enters design → plan → harden → approval cycle)
- Return to Step 2

### IF no:

- Exit with "Plan not approved"
