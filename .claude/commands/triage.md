---
name: triage
description: Interactive triage of review findings in .harness/todos/. Sorts each finding into fix (ready), drop (dismissed), or defer (backlog) with audit trail.
---

# /triage

Interactive finding triage. Reads pending todos, presents each one-by-one, and routes based on user decision.

## Usage

```
/triage              → triage all pending findings in .harness/todos/
```

---

## Flow

0. **Ensure runtime state (brownfield self-heal):** `mkdir -p .harness/todos .harness/observations`. If `.harness/todos/` is empty or missing after mkdir: **HALT** with message "No findings to triage. Run /lp-review first to generate findings."
1. Load pending todos from `.harness/todos/` (filter `status: pending` from YAML frontmatter)
2. Validate each file:
   - Confirm resolved path is within `.harness/todos/` (no symlink following)
   - Confirm frontmatter has required fields (`status`, `priority`)
   - Skip with warning if malformed: "Skipping {filename}: invalid frontmatter"
3. Sort by priority (P1 → P2 → P3)
4. Group findings referencing the same `file:line` — present together, one decision per group
5. IF more than 25 pending findings: present top 25, auto-defer overflow to `.harness/observations/` with `status: deferred`
6. IF zero pending findings: "No pending findings to triage." → exit

Present each finding showing: title, priority, agent_source, problem statement, location (file:line), proposed solution. Show progress counter ("Finding 3/12"). Wait for user decision.

## Triage Actions

| Action    | YAML Change                                                  | File Location                     | Effect                                           |
| --------- | ------------------------------------------------------------ | --------------------------------- | ------------------------------------------------ |
| **fix**   | `status: pending` → `status: ready`                          | Stays in `.harness/todos/`        | `/resolve-todo-parallel` picks it up             |
| **drop**  | `status: pending` → `status: dropped`, adds `dropped_date`   | Moved to `.harness/observations/` | Audit trail preserved, excluded from active work |
| **defer** | `status: pending` → `status: deferred`, adds `deferred_date` | Moved to `.harness/observations/` | Phase 8 surfaces in backlog                      |

**Drop confirmation for P1:** When dropping a P1 (critical) finding, require confirmation: "This is a P1 (critical) finding. Are you sure you want to drop it? (yes/no)"

## Frontmatter Validation

- `status`: must be one of `pending`, `ready`, `deferred`, `dropped`, `complete`
- `priority`: must be one of `P1`, `P2`, `P3`
- `agent_source`: optional string, defaults to `"unknown"` if missing

## Summary

After all findings processed:

- Fixed: {X} findings (ready for `/resolve-todo-parallel`)
- Dropped: {Y} findings (moved to observations)
- Deferred: {Z} findings (moved to observations)

Run `/regenerate-backlog` to update the project backlog with new deferrals.

Offer next steps: (1) Run `/resolve-todo-parallel` to fix approved findings, (2) Done.

---

## Rules

1. Do NOT implement fixes during triage — sorting only
2. Present findings in priority order (P1 first)
3. Show progress counter on every finding
4. Accept only: `fix`, `drop`, `defer` (case-insensitive)
5. If user enters something else, re-prompt with the three options
6. Do NOT batch-process — one at a time
7. Confirm before dropping P1 findings
8. Validate file paths stay within `.harness/` directories
9. Skip files with malformed frontmatter (warn and continue)
