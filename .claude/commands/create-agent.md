---
name: create-agent
description: "Create a new Claude Code agent or convert an existing skill into an agent"
---

# Create Agent

Create a new Claude Code agent or convert an existing skill into an agent. This command is a thin interactive wrapper that parses user input and invokes the `creating-agents` skill.

## Initial Response

When this command is invoked:

1. **Check if parameters were provided**:

   Parse the input to extract:
   - **Agent description:** The role or purpose (everything before "from skill")
   - **Source skill:** Optional existing skill to convert (everything after "from skill")

   Invocation patterns:

   ```
   /create-agent security-reviewer for reviewing code security
   /create-agent database migration auditor
   /create-agent dependency checker from skill dependency-analysis
   /create-agent                    # no args — prompts for details
   ```

2. **If parameters provided**:
   - Extract agent description and optional source skill
   - If source skill specified ("from skill ..."):
     - Verify `.claude/skills/<skill-name>/SKILL.md` exists
     - Read the skill files immediately
     - Set mode to **Skill-to-Agent Conversion** (Mode B)
   - If no source skill:
     - Set mode to **New Agent** (Mode A)
   - Proceed to invoke the `creating-agents` skill with the extracted parameters

3. **If no parameters provided**, respond with:

   ```
   I'll help you create a new Claude Code agent using the Agent Forge methodology.

   First, which type of agent creation?

   **A) New agent from scratch** — describe what the agent should do
   **B) Convert an existing skill** — extract an agent from a skill's core competency

   Examples:
   - `/create-agent security-reviewer for reviewing code security` (new agent)
   - `/create-agent migration auditor from skill database-migrations` (convert skill)
   - `/create-agent` (I'll walk you through it)

   The agent will be registered in CLAUDE.md and AGENTS.md automatically.
   ```

   Wait for user input, then parse and proceed.

4. **After parsing, invoke the creating-agents skill**:

   Read the skill definition at `.claude/skills/creating-agents/SKILL.md` and follow its 6-phase workflow.
   - The skill handles all 6 phases autonomously
   - This command does NOT implement the phases — it delegates entirely
   - Pass the extracted agent description, mode (A or B), and source skill path to the skill

## Parameter Extraction Rules

When parsing user input, apply these rules:

1. **Everything before "from skill"** is the agent description
2. **Everything after "from skill"** is treated as a skill name (kebab-case directory in `.claude/skills/`)
3. **Quoted strings** are treated as a single token (e.g., `"migration auditor"`)
4. **If no "from skill" is present**, the entire input is the agent description with no source skill (Mode A)

Examples:

| Input                                              | Description                         | Source Skill          | Mode |
| -------------------------------------------------- | ----------------------------------- | --------------------- | ---- |
| `security-reviewer for code security`              | security-reviewer for code security | (none)                | A    |
| `migration auditor from skill database-migrations` | migration auditor                   | `database-migrations` | B    |
| `dependency checker`                               | dependency checker                  | (none)                | A    |
| (empty)                                            | (prompt user)                       | (prompt user)         | —    |

## Important Notes

- This command is interactive — it requires human input for agent name approval, tool tier confirmation, and namespace directory decisions
- The skill handles research, contrarian analysis, writing, validation, and registration
- For creating skills (multi-phase workflows), use `/create-skill` instead
- For updating existing agents, edit the agent file directly
- The creating-agents skill is located at `.claude/skills/creating-agents/SKILL.md`
