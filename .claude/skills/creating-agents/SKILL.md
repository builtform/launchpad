---
name: creating-agents
description: "Creates new Claude Code agents or converts existing skills into agents. Produces production-grade agent definitions with 8-section body structure, least-privilege tool assignment, and registration in CLAUDE.md/AGENTS.md. Triggers on: create agent, new agent, build agent, convert skill to agent, turn this into an agent."
---

# Agent Forge

NEVER produce an agent file that looks like what Claude would generate unprompted. Every agent must have explicit tool-tier assignment, a CRITICAL block, prohibition sections, and a REMEMBER closer with role + foil.

---

## Trigger

This skill activates when:

- Creating a new agent from scratch
- Converting an existing skill into an agent
- Building a sub-agent for use in commands or workflows
- Defining a new specialized agent role

**Examples:**

- `/create-agent security-reviewer for reviewing code security`
- `"create an agent that finds unused dependencies"`
- `"convert the prd skill into a lightweight agent"`
- `"build a new agent for database migration review"`

## What This Skill Does NOT Handle

| Request                                 | Use Instead                                    |
| --------------------------------------- | ---------------------------------------------- |
| Creating skills (multi-phase workflows) | `/create-skill` + `creating-skills` skill      |
| Configuring Agent Teams                 | Manual setup — experimental feature            |
| Setting up MCP servers for agents       | `claude mcp add` directly                      |
| Modifying existing agent files          | Direct editing or `/update-skill` on the skill |
| Creating commands that wire agents      | Manual command creation                        |

---

## The Job

| Step | Phase            | Visible Output                                             |
| ---- | ---------------- | ---------------------------------------------------------- |
| 1    | Detect Mode      | Mode identified: New Agent or Skill-to-Agent Conversion    |
| 2    | Research         | Research brief from existing agents in the repo            |
| 3    | Contrarian Check | Generic vs. differentiated agent comparison                |
| 4    | Write Agent      | Agent `.md` file with 8-section body + valid frontmatter   |
| 5    | Validate         | Structure, tool permissions, and description quality check |
| 6    | Register         | CLAUDE.md + AGENTS.md updated, file summary presented      |

Every step produces a visible artifact. No step is skipped.

---

## Phase 1: Detect Mode

Parse the user's input to determine the operating mode:

**Mode A — New Agent:** The user describes a role, purpose, or task for a new agent. No existing skill referenced.

**Mode B — Skill-to-Agent Conversion:** The user references an existing skill file or says "convert," "turn into," or "extract from."

### Mode A: Extract Agent Spec

From the user's input, identify:

1. **Agent name** — kebab-case, `[domain]-[role]` pattern (e.g., `security-reviewer`, `migration-auditor`)
2. **Agent purpose** — one sentence: what the agent does
3. **Agent category** — locator, analyzer, reviewer, resolver, or evaluator
4. **Target namespace** — one of: `research/`, `review/`, `resolve/`, `design/`, `skills/`

Present the spec to the user for confirmation before proceeding.

### Mode B: Identify Source Skill

1. Verify the skill exists at `.claude/skills/<name>/SKILL.md`
2. Read the SKILL.md and all files in its `references/` directory
3. Read [references/CONVERSION-GUIDE.md](mdc:references/CONVERSION-GUIDE.md) before proceeding
4. Follow the conversion protocol to extract the agent spec
5. Present the extracted spec to the user — include which skill phases become agent responsibilities and which are discarded (orchestration logic)
6. If the skill has multi-phase orchestration, suggest which phases could become separate agents

**Output:** Confirmed mode + agent spec (name, purpose, category, namespace).

---

## Phase 2: Research Existing Agents

### For New Agents (Mode A)

Spawn one sub-agent (Sonnet):

- **pattern-finder** — Read all files in `.claude/agents/` (and subdirectories if they exist). Report the exact frontmatter schema, body section structure, tool assignments, description style, and naming patterns used by existing agents.

After the sub-agent returns, check for overlap:

1. Compare the new agent's purpose against every existing agent's `description` field
2. If overlap detected: warn the user, show a diff of responsibilities, let them decide whether to proceed, merge, or cancel

### For Conversions (Mode B)

Skip the sub-agent research wave. The existing skill files provide all needed context. Instead, read 2-3 existing agent files directly to confirm the current body structure convention.

**Output:** Research brief summarizing existing agent conventions + overlap analysis.

---

## Phase 3: Contrarian Check

Before writing the agent file, answer these questions:

1. **What would Claude produce without this skill?** Write 3-5 bullet points: the generic agent's structure, tool access, description style, and missing sections.

2. **Name every predictable pattern.** Broad tool access, job-title description, no prohibition sections, no output format template, no REMEMBER closer.

3. **How does THIS agent differ?** For each predictable pattern, state the specific enforcement:
   - Broad tools → Read [references/TOOL-TIERS.md](mdc:references/TOOL-TIERS.md) and assign the correct tier
   - Job-title description → Write a routing signal with trigger conditions
   - No prohibitions → Generate CRITICAL block + "What NOT to Do" from the agent's scope boundaries
   - No output format → Create a filled-in example showing realistic output
   - No REMEMBER → Write role + foil identity anchor

Present the contrarian comparison to the user. Proceed after confirmation.

**Output:** Generic vs. differentiated agent comparison table.

---

## Phase 4: Write the Agent File

Read [references/AGENT-TEMPLATE.md](mdc:references/AGENT-TEMPLATE.md) before writing.

Read [references/TOOL-TIERS.md](mdc:references/TOOL-TIERS.md) before assigning tools.

### Frontmatter

Write the YAML frontmatter with these fields:

| Field         | Required | Value                                                   |
| ------------- | -------- | ------------------------------------------------------- |
| `name`        | Yes      | kebab-case, matches filename                            |
| `description` | Yes      | Routing signal with trigger conditions, not a job title |
| `tools`       | Yes      | Least-privilege set from TOOL-TIERS.md                  |
| `model`       | Yes      | `inherit` (default) unless user specifies otherwise     |

Optional fields to include when relevant: `memory`, `hooks`, `color`, `maxTurns`, `isolation`, `effort`, `disallowedTools`, `skills`, `mcpServers`, `permissionMode`, `background`, `initialPrompt`.

### Body: 8-Section Structure

Write all 8 sections in this exact order. For simpler agents, sections are shorter (even one sentence) but never omitted:

1. **Identity Opener** — One sentence: "You are a specialist at [what]. Your job is to [action], NOT to [foil]."
2. **CRITICAL Block** — `## CRITICAL: YOUR ONLY JOB IS TO [scope]` + 5-7 DO NOT bullet points
3. **Core Responsibilities** — 3 numbered subsections, each with 3-5 bullet points
4. **Strategy** — Step-by-step numbered phases for how the agent executes its task
5. **Output Format** — Fenced code block with a filled-in realistic example (not placeholders)
6. **Important Guidelines** — Bolded DO rules (5-8 items)
7. **What NOT to Do** — Bullet list of 8-12 specific prohibitions
8. **REMEMBER Closer** — `## REMEMBER: You are a [role], not a [foil]` + 2-3 sentence identity anchor

### Writing Rules

- Use imperatives throughout: "Run", "Check", "Report", "Reject"
- No hedge language: remove "consider", "you might want to", "it's generally a good idea"
- The output format example must be realistic and filled-in, not a schema with placeholders
- The CRITICAL block and "What NOT to Do" must be derived from the agent's actual scope boundaries, not generic prohibitions

### File Placement

Determine the target path:

- If namespace directories exist (e.g., `.claude/agents/review/`): place in the appropriate namespace
- If namespace directories do not exist: ask the user whether to create the directory or place in flat `.claude/agents/`

Save the agent file as `.claude/agents/[namespace/]<agent-name>.md`.

**Output:** Saved agent file.

---

## Phase 5: Validate

Run these three checks on the written agent file:

### Check 1: Structure Compliance

- [ ] All 8 sections present in correct order
- [ ] Frontmatter has `name`, `description`, `tools`, `model`
- [ ] `name` is kebab-case and matches the filename
- [ ] Identity opener follows "You are a specialist at [X]. Your job is to [Y], NOT to [Z]" pattern
- [ ] CRITICAL block has 5-7 DO NOT items
- [ ] Output format contains a filled-in example (no placeholders)
- [ ] REMEMBER closer has role + foil

### Check 2: Tool Permission Audit

- [ ] Tools match the assigned tier from TOOL-TIERS.md
- [ ] No unnecessary tools granted (least-privilege)
- [ ] If `Read` is granted, the agent needs to read file contents (not just locate)
- [ ] If `Write`/`Edit` is granted, the agent's purpose requires mutation
- [ ] If `Bash` is granted, the agent needs command execution with justification
- [ ] `Agent` tool is NOT included (subagents cannot spawn subagents)

### Check 3: Description Quality

- [ ] Description reads as a routing signal, not a job title
- [ ] Description includes when to delegate to this agent
- [ ] Description is specific enough to avoid false-positive activation
- [ ] Description differentiates from existing agents' descriptions

If any check fails, fix the issue and re-validate. Present the validation report to the user.

**Output:** Validation report (all checks passed / issues found and fixed).

---

## Phase 6: Register and Present

### Update Registration Files

1. **CLAUDE.md** — Add the agent to the "Available Sub-Agents" table
2. **AGENTS.md** — Add the agent entry with name, purpose, and tools

If `.launchpad/agents.yml` exists, add the agent to the appropriate key (`review_agents`, `harden_plan_agents`, etc.) based on its namespace.

### Present to User

```
## Agent Created: <name>

### File
.claude/agents/[namespace/]<name>.md (XX lines)

### Frontmatter
name: <name>
description: <first 80 chars>...
tools: <tool list>
model: <model>

### Registration
- CLAUDE.md: Added to Available Sub-Agents table
- AGENTS.md: Added agent entry

### Test This Agent
Invoke with: "Use the <name> agent to [example task]"
Or spawn as sub-agent: Task(subagent_type="<name>", prompt="[example prompt]")
```

Ask: **"Commit these files, or adjust something first?"**

---

## Verification Gate

Before delivering, confirm every item:

- [ ] Agent file saved to `.claude/agents/[namespace/]<name>.md`
- [ ] All 8 body sections present
- [ ] Frontmatter valid with least-privilege tools
- [ ] Description is a routing signal, not a job title
- [ ] No hedge language in agent file
- [ ] Output format contains a realistic filled-in example
- [ ] CRITICAL block and "What NOT to Do" derived from actual scope
- [ ] REMEMBER closer has role + foil
- [ ] CLAUDE.md updated
- [ ] AGENTS.md updated
- [ ] No overlap with existing agents (or user approved the overlap)
- [ ] Agent file differs structurally from what Claude would produce without this skill

If any item fails, return to the relevant phase and fix before delivering.

---

NEVER produce an agent file that looks like what Claude would generate unprompted. Every agent must have explicit tool-tier assignment, a CRITICAL block, prohibition sections, and a REMEMBER closer with role + foil.
