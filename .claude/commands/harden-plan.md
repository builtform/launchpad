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

Read agent names from `.launchpad/agents.yml`:

### Always dispatched (both `--full` and `--lightweight`):

Read `harden_plan_agents` from `agents.yml`. Dispatch all listed agents in parallel.

Current defaults: `pattern-finder`, `security-auditor`, `performance-auditor` (+ `spec-flow-analyzer` when created in Phase 3).

### Conditional (`--full` only):

Read `harden_plan_conditional_agents` from `agents.yml`. Dispatch all listed agents in parallel.

Current defaults: `architecture-strategist`, `code-simplicity-reviewer`, `frontend-races-reviewer` (+ `schema-drift-detector` when created in Phase 2).

**Agent resolution:** Scan all `.claude/agents/` subdirectories for `{name}.md`. First match wins. If agent file not found, skip silently with a note — this handles future-phase agents gracefully.

**Note:** The YAML is the single source of truth. Plan review ≠ code review — different agents for different purposes.

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
