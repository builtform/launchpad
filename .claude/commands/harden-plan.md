---
name: harden-plan
description: Stress-tests implementation plans using multiple review agents. Dispatches agents based on plan characteristics and synthesizes findings into P1/P2/P3.
---

# /harden-plan

Stress-tests an implementation plan using specialized review agents.

## Usage

```
/harden-plan [plan-path] --full          → 8 agents (section builds)
/harden-plan [plan-path] --lightweight   → 4 agents (standalone default)
/harden-plan [plan-path] --auto          → Auto-apply (used by /harness:plan)
```

**Arguments:** `$ARGUMENTS` (parse for plan path, `--full`/`--lightweight`, `--auto`)

If no intensity flag provided, default to `--lightweight`.

---

## Step 1: Read Project Context

- Read `.harness/harness.local.md` for project context
- Read the plan file at the provided path

## Step 2: Idempotency Check

- IF the plan file already contains `## Hardening Notes` → skip with message "Plan already hardened"
- This makes `/harden-plan` safe to re-run

## Step 3: Dispatch Agents (all model: inherit)

### Always dispatched (both `--full` and `--lightweight`):

| Agent                 | Purpose                | Notes                             |
| --------------------- | ---------------------- | --------------------------------- |
| `spec-flow-analyzer`  | User flow completeness | [Phase 3] — skipped until created |
| `security-auditor`    | Security review        | [Phase 1] — skipped until created |
| `performance-auditor` | Performance review     | [Phase 1] — skipped until created |
| `pattern-finder`      | Pattern consistency    | Available now                     |

### Conditional (`--full` only):

| Agent                      | Purpose               | Condition                     |
| -------------------------- | --------------------- | ----------------------------- |
| `architecture-strategist`  | Architecture review   | [Phase 1] — IF multi-package  |
| `code-simplicity-reviewer` | Complexity review     | [Phase 1] — IF 4+ phases      |
| `frontend-races-reviewer`  | Race condition review | [Phase 1] — IF async UI       |
| `schema-drift-detector`    | Schema review         | [Phase 2] — IF Prisma changes |

**Agent resolution:** Scan all `.claude/agents/` subdirectories for `{name}.md`. First match wins. If agent file not found, skip silently with a note — this handles future-phase agents gracefully.

**Note:** Phase 1 will move `/harden-plan` to read agent names from `agents.yml` keys `harden_plan_agents` and `harden_plan_conditional_agents`. For now, agent names are hardcoded above. Plan review ≠ code review — different agents for different purposes.

## Step 3.5: Document-Review Agents [Phase 3 v7]

- Read `harden_document_agents` from `.launchpad/agents.yml`
- IF not empty: dispatch all document-review agents in parallel
- These review the plan as a document (clarity, completeness, structure)
- [Phase 3] — skipped until agents are created and key is populated

## Step 4: Synthesize Findings

- Collect all agent findings
- Deduplicate overlapping concerns
- Prioritize: P1 (must fix before build), P2 (should fix), P3 (nice to have)

## Step 5: Apply or Present

### IF `--auto` (used by `/harness:plan`):

- Append `## Hardening Notes` section to the plan file automatically
- Include all findings organized by priority
- No user prompt

### IF standalone (no `--auto`):

- Present findings summary to user
- Ask: "Apply these hardening notes to the plan? (yes/no)"
- IF yes: append `## Hardening Notes` section
- IF no: exit with "Hardening notes not applied"
