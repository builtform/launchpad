---
name: lp-copy-review
description: "Dispatches copy review agents from review_copy_agents in agents.yml. Shell command — downstream projects populate the agent list."
---

# /lp-copy-review

Shell command that dispatches copy review agents for design workflow integration. In LaunchPad, this is a no-op (no copy review agents configured by default).

## Usage

```
/lp-copy-review              → dispatch copy review agents (if configured)
```

---

## Flow

### Step 1: Read Agent Configuration

- Read `.launchpad/agents.yml`
- Extract `review_copy_agents` list

### Step 2: Evaluate List

- **IF list empty or key not present:**
  - Skip silently (no copy review agents configured — this is expected in LaunchPad)
  - Return: "No copy review agents configured. Skipping copy review."
- **IF list populated:**
  - Proceed to Step 3

### Step 3: Dispatch Agents

For each agent in `review_copy_agents`:

- Dispatch in parallel (same pattern as `/lp-review` agent dispatch)
- Each agent receives: section spec, implemented component files, copy context
- Collect all findings

### Step 4: Return Findings

- Aggregate findings from all dispatched agents
- Return structured findings to the calling step (Step 2c of `/lp-plan`)
- Each finding includes: agent name, severity (P1/P2/P3), description, file:line

---

## Downstream Extension

This command is intentionally a no-op in LaunchPad. The `review_copy_agents` list starts empty. Downstream projects populate the list in their `agents.yml` to activate copy review during the design workflow.

- Downstream projects add their domain-specific copy review agents (e.g., `copy-auditor`)
