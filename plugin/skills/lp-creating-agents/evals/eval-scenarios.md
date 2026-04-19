# Evaluation Scenarios for creating-agents

## Scenario 1: Happy Path — New Agent from Scratch

**Input:** "Create an agent that reviews database migrations for safety — checking for destructive operations, missing rollbacks, and data integrity risks."

**Expected behavior with skill:**

1. Detects Mode A (new agent)
2. Extracts spec: name=`migration-auditor`, category=reviewer, namespace=review/, tools=Tier 2 (Read, Grep, Glob, LS)
3. Researches existing agents in `.claude/agents/` for conventions
4. Runs contrarian check — identifies that without the skill, Claude would produce a generic file with broad tools and no CRITICAL block
5. Writes 8-section agent file with migration-specific CRITICAL block, output format showing realistic migration analysis, and REMEMBER closer with "auditor, not architect" framing
6. Validates structure, tool permissions (no Write/Edit — reviewer doesn't modify), and description quality
7. Registers in CLAUDE.md and AGENTS.md

**Without skill (baseline):** Claude would produce a short markdown file with `tools: Read, Write, Edit, Bash, Grep, Glob` (overly broad), a 2-paragraph body with no CRITICAL block or output format, and no registration in CLAUDE.md/AGENTS.md.

**Key differentiators:** Tool tier enforcement (Tier 2, not Tier 5), 8-section body, realistic output format example, registration.

---

## Scenario 2: Edge Case — Skill-to-Agent Conversion of an Orchestration Skill

**Input:** "Convert the creating-skills skill into an agent."

**Expected behavior with skill:**

1. Detects Mode B (conversion)
2. Reads `.claude/skills/creating-skills/SKILL.md` and all 7 reference files
3. Loads CONVERSION-GUIDE.md
4. Identifies that creating-skills is PRIMARILY an orchestration skill (7 phases, user interaction, sub-agent spawning)
5. Extracts the core competency: "evaluate skill quality" (already exists as `skill-evaluator`)
6. Warns about overlap with existing `skill-evaluator` agent
7. Suggests phase breakdown: Phases 1-4 are orchestration (discard), Phase 5 is writing (could become writer agent), Phase 6 is evaluation (already exists), Phase 7 is registration (command concern)
8. Presents this analysis to user and asks whether to proceed, merge, or cancel

**Without skill (baseline):** Claude would copy the entire 340-line SKILL.md into an agent file, keeping the 7-phase structure, user interaction, and sub-agent spawning — all of which break agent constraints.

**Key differentiators:** Extraction vs. copy, orchestration detection, overlap warning, phase-to-agent suggestions.

---

## Scenario 3: Negative Boundary — Request That Looks Like Agent Creation but Isn't

**Input:** "Help me configure Agent Teams for my project."

**Expected behavior with skill:**

1. Recognizes this is about Agent Teams configuration, not agent creation
2. Does NOT activate — this falls under "What This Skill Does NOT Handle"
3. Responds with: "Agent Teams configuration is outside this skill's scope. Agent Teams are an experimental feature configured manually. See Claude Code docs on agent teams."

**Without skill (baseline):** Claude would attempt to create an agent file related to "teams," producing an irrelevant artifact.

**Key differentiators:** Negative boundary enforcement — the skill knows what it doesn't do.

---

## Scenario 4: Edge Case — Agent with Unusual Tool Requirements

**Input:** "Create an agent that validates code by running tests and type checks."

**Expected behavior with skill:**

1. Detects Mode A
2. Extracts spec: name=`test-validator`, category=builder, namespace=review/
3. During tool assignment, detects this requires Tier 5 (Bash needed for `pnpm test`)
4. Warns: "This agent requires Bash access (Tier 5). Bash can execute arbitrary commands. Documenting specific allowed commands in the agent file."
5. Writes agent file with `tools: Read, Bash, Grep, Glob, LS` and includes in the body: "Allowed commands: `pnpm test`, `pnpm typecheck`, `pnpm lint`. Prohibited: `git push`, `rm`, `npm publish`, network requests."
6. Adds a PreToolUse hook suggestion for Bash command validation

**Without skill (baseline):** Claude would grant `tools: Bash, Read, Write, Edit, Grep, Glob, LS` with no command restrictions documented.

**Key differentiators:** Tier 5 warning, specific command allowlist/denylist, hook suggestion.
