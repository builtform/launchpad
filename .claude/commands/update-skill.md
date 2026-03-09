# Update Skill

Iterate on an existing Claude Code skill after real-world usage reveals gaps or new requirements. Reuses the Meta-Skill Forge evaluation and improvement phases, skipping Phase 1 by reading the existing skill files as context.

## Step 1: Parse Input

Extract from `$ARGUMENTS`:

- **Skill name:** First token (kebab-case, matches directory in `.claude/skills/`)
- **Change description:** Everything after the skill name (optional)

```
/update-skill creating-skills improve the extraction rounds
/update-skill commit add Greptile review support
/update-skill prd                    # prompts for change details
/update-skill                        # prompts for skill name
```

## Step 2: Resolve Skill

**If parameters provided:**

1. Verify `.claude/skills/<skill-name>/SKILL.md` exists.
2. If not found, list available skills (all directories in `.claude/skills/` with their SKILL.md description) and ask the user to confirm.
3. Read the existing SKILL.md and ALL files in `.claude/skills/<skill-name>/references/` fully. These serve as Phase 1 context.
4. If no change description was provided, ask: "What needs to change? What gaps did you discover?"

**If no parameters provided**, respond with:

```
I'll help you update an existing skill. Which skill do you want to improve?

Available skills:
[List all directories in .claude/skills/ with their SKILL.md description]

Please provide:
1. The skill name (directory name in .claude/skills/)
2. What needs to change -- what gaps did you discover?

Examples:
- `/update-skill commit add Greptile review support`
- `/update-skill prd improve the edge case detection`
- `/update-skill creating-skills` (I'll ask what needs to change)
```

## Step 3: Delta Analysis

The existing skill files ARE the Phase 1 context -- no sub-agent research wave needed.

**3a: Summarize** the current skill (architecture tier, line count, reference files, triggers, phases).

**3b: Classify impact** by comparing the user's reported gaps against existing content:

| Impact Tier      | What Changed                               | Phases to Re-run  |
| ---------------- | ------------------------------------------ | ----------------- |
| **Scope**        | Triggers, boundaries, does/does-not-do     | 2 + 3 + 5 + 6 + 7 |
| **Structure**    | Phases, reference files, architecture tier | 4 + 5 + 6 + 7     |
| **Content**      | Wording, rules, reference material         | 5 + 6 + 7         |
| **Registration** | Only CLAUDE.md/AGENTS.md or eval scenarios | 7 only            |

Present the classification with rationale. Get user confirmation before proceeding.

## Step 4: Execute Relevant Phases

Load `.claude/skills/creating-skills/SKILL.md` and execute ONLY the phases from Step 3b. Follow the same protocols, sub-agents, and quality gates.

**Adaptations for updates (vs new skill creation):**

- **Phase 2 (Extraction):** Pre-populate rounds with existing answers. Only ask questions where gaps indicate the answer changed.
- **Phase 3 (Contrarian):** Compare updated scope against the existing contrarian frame. Only re-derive invalidated patterns.
- **Phase 4 (Architecture):** Present current tier alongside recommended new tier. Explain file additions/removals if tier changes.
- **Phase 5 (Write):** Read reference templates from `.claude/skills/creating-skills/references/` before writing. Apply surgical edits -- do not rewrite unchanged sections. Preserve existing voice and structure unless the change targets them.
- **Phase 6 (Validate):** Read `.claude/skills/creating-skills/references/QUALITY-GATES.md`. Spawn `skill-evaluator` sub-agent (Sonnet) with access to BOTH old and new versions. Any gate that previously passed must still pass (regression check).
- **Phase 7 (Ship):** Update CLAUDE.md/AGENTS.md if triggers, scope, or agents changed. Update eval scenarios to cover new behavior.

## Step 5: Present Changes

```
## Skill Updated: <name>

### Changes Made
- [what changed and why]

### Files Modified
- .claude/skills/<name>/SKILL.md -- [what changed]
- .claude/skills/<name>/references/FILE.md -- [if applicable]

### Regression Check
- [PASS / FAIL] -- [old vs new comparison summary]

### CLAUDE.md / AGENTS.md
- [Updated / No changes needed]
```

Ask: **"Commit these changes, or adjust something first?"**

## Verification Gate

Confirm every item before delivering:

- [ ] All modified skill files saved
- [ ] SKILL.md still under 500 lines
- [ ] All reference files still independently loadable
- [ ] No hedge language introduced
- [ ] Evaluation PASS with no regressions
- [ ] CLAUDE.md/AGENTS.md entries accurate
- [ ] Eval scenarios cover new behavior
- [ ] Output still differs structurally from baseline Claude

If any item fails, return to the relevant phase and fix before delivering.

## Important Notes

- This command is interactive (Phase A) -- requires human input about what gaps emerged
- The existing skill files serve as Phase 1 context (no sub-agent research needed)
- For creating new skills from scratch, use `/create-skill` instead
- The `skill-evaluator` sub-agent validates against the same quality criteria as new skills, plus a regression check against the previous version
