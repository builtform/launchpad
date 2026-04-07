# Skill-to-Agent Conversion Guide

> **Loaded when:** Phase 1 detects Mode B — the user wants to convert an existing skill into an agent.

Converting a skill into an agent is an extraction process, not a copy. Skills orchestrate multi-phase workflows with user interaction. Agents are single-purpose, stateless leaf nodes with prescribed output formats. The conversion must strip orchestration and preserve only the core competency.

---

## The Fundamental Difference

| Dimension        | Skill                                          | Agent                                             |
| ---------------- | ---------------------------------------------- | ------------------------------------------------- |
| Purpose          | Orchestrate a multi-phase workflow             | Execute a single focused task                     |
| User interaction | Interactive — asks questions, presents choices | Non-interactive — receives prompt, returns output |
| State            | Stateful across phases                         | Stateless — one input, one output                 |
| Tool access      | All tools (via the main session)               | Restricted to least-privilege set                 |
| Output           | Multiple artifacts across phases               | One prescribed output format                      |
| Invocation       | User invokes via slash command                 | Orchestrator spawns as sub-agent                  |
| Can spawn agents | Yes (skills run in the main session)           | No (subagents cannot spawn subagents)             |

---

## The Extraction Protocol

### Step 1: Read the Skill Fully

Read the SKILL.md and ALL files in `references/`. Map the skill's structure:

- What phases does it have?
- What does each phase produce?
- Which phases involve user interaction?
- Which phases are pure execution?
- What is the skill's core domain knowledge?

### Step 2: Identify the Core Competency

The core competency is the ONE thing the skill does that is valuable without the orchestration. Ask:

- "If this skill had only one phase, which phase would it be?"
- "What is the minimum the skill needs to produce useful output?"
- "What would a user delegate to a sub-agent from this skill?"

**Examples:**

- `creating-skills` → core competency is "evaluate a skill against quality criteria" → becomes `skill-evaluator`
- A hypothetical `code-review` skill → core competency is "identify issues in code changes" → becomes `code-reviewer`
- A hypothetical `prd` skill → core competency is "analyze requirements for completeness" → becomes `requirements-analyzer`

### Step 3: Separate Orchestration from Knowledge

Classify each skill component:

| Component Type         | Goes Into Agent? | Explanation                                                  |
| ---------------------- | ---------------- | ------------------------------------------------------------ |
| Domain knowledge       | YES              | Rules, criteria, patterns the agent needs to do its job      |
| Output format          | YES              | The prescribed structure the agent produces                  |
| Quality criteria       | YES              | What "good" looks like for this agent's output               |
| Phase orchestration    | NO               | Sequential phase logic belongs in commands                   |
| User interaction       | NO               | Agents don't ask questions — they receive prompts            |
| Sub-agent spawning     | NO               | Agents cannot spawn sub-agents                               |
| Registration logic     | NO               | File management is a command concern                         |
| Reference file loading | PARTIALLY        | Inline the essential knowledge; discard the loading protocol |

### Step 4: Handle Multi-Phase Skills

If the skill has multiple phases, determine what happens to each:

1. **Identify phases that are self-contained** — these are conversion candidates
2. **Identify phases that require user input** — these stay in commands
3. **Identify phases that spawn sub-agents** — these are orchestration and stay in commands
4. **Suggest which phases could become separate agents** — present to user

**Example breakdown for a hypothetical 5-phase skill:**

```
Phase 1: Research (spawns sub-agents)     → DISCARD (orchestration)
Phase 2: Extract (asks user questions)    → DISCARD (interactive)
Phase 3: Analyze (pure domain logic)      → EXTRACT → becomes the agent
Phase 4: Write (produces artifact)        → MERGE into agent output format
Phase 5: Validate (checks quality)        → COULD become a separate evaluator agent
```

Present this breakdown to the user: "Phases 3 and 4 become the agent. Phase 5 could become a separate evaluator. Phases 1 and 2 are orchestration that stays in commands. Do you agree?"

### Step 5: Write the Agent Spec

From the extraction, produce:

1. **Agent name** — derived from the core competency, not the skill name
2. **Agent purpose** — one sentence describing what the agent does
3. **Tool tier** — based on what the core competency requires
4. **8-section body** — following AGENT-TEMPLATE.md:
   - Identity opener: from the core competency
   - CRITICAL block: from the skill's "Does NOT Handle" table
   - Core responsibilities: from the extracted phases
   - Strategy: from the execution steps of the extracted phases
   - Output format: from the skill's output format (simplified to one artifact)
   - Important guidelines: from the skill's rules and constraints
   - What NOT to do: from the skill's exclusions + the discarded orchestration concerns
   - REMEMBER closer: role = core competency, foil = the orchestration role

### Step 6: Validate the Extraction

After writing, check:

- [ ] The agent does NOT replicate the skill's orchestration logic
- [ ] The agent's output format produces ONE artifact (not multiple phase artifacts)
- [ ] The agent does NOT ask the user questions or present choices
- [ ] The agent's tools are least-privilege for the extracted competency
- [ ] Domain knowledge from reference files is inlined (not loaded via `mdc:` protocol)
- [ ] The agent could be spawned by any command, not just the original skill's workflow

---

## Common Conversion Pitfalls

| Pitfall                             | How to Avoid                                                                |
| ----------------------------------- | --------------------------------------------------------------------------- |
| Copying the entire skill into agent | Extract only the core competency; discard orchestration                     |
| Keeping user interaction            | Replace questions with assumptions or require them in the prompt            |
| Granting all tools                  | Use the decision tree in TOOL-TIERS.md                                      |
| Multiple output artifacts           | Merge into one prescribed output format                                     |
| Including `mdc:` reference loading  | Inline the essential knowledge directly in the agent body                   |
| Naming after the skill              | Name after the core competency: `prd` skill → `requirements-analyzer` agent |
| Preserving phase numbers            | Remove phase structure; use a flat strategy section                         |

---

## When NOT to Convert

Some skills should NOT become agents:

- **Skills that are primarily interactive** — the value is in the conversation, not the output
- **Skills that orchestrate multiple sub-agents** — the skill IS the orchestrator; extracting it removes its purpose
- **Skills where the output varies significantly per invocation** — agents need prescribed output formats
- **Skills that are the only consumer of their domain knowledge** — if no command would spawn this agent, there's no need for it

If the skill falls into these categories, tell the user: "This skill's value is in its orchestration/interaction, not in a single extractable competency. It should stay as a skill."
