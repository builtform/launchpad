# Port Skill

Port an external skill (from Vercel, Anthropic, community repos, or any local file) into
the project's format using the 4-phase Skill Porting workflow. The ported skill is fully
detached from its source — it becomes a native project skill, updateable with /update-skill.

## Step 1: Parse Input

Extract from $ARGUMENTS:

- **Source path:** The skill to port (required — everything after "based on")

Invocation patterns:

```
/port-skill based on path/to/external/SKILL.md
/port-skill based on .claude/skills-inbox/react-best-practices/SKILL.md
/port-skill                   # no args — prompts for source
```

## Step 2: If no arguments provided, respond with:

```
I'll help you port an external skill into the project.

Please provide the source:
- A local file path: /port-skill based on path/to/SKILL.md
- A file in the skills inbox: /port-skill based on .claude/skills-inbox/skill-name/SKILL.md

The ported skill will be adapted to the project's format, validated against the 16
quality criteria, and registered in CLAUDE.md, AGENTS.md, and the skills catalog
(docs/skills-catalog/skills-index.md + skills-usage.json).
After porting, use /update-skill to iterate on it like any other project skill.
```

Wait for user input, then proceed.

## Step 3: Execute the Porting Workflow

Read `.claude/skills/creating-skills/references/PORTING-GUIDE.md` and follow its 4-phase workflow.

- The guide handles all 4 phases
- This command does NOT implement the phases — it delegates entirely
- Pass the resolved source path to the guide

## Parameter Extraction Rules

When parsing user input:

1. **Everything after "based on"** is the source file path
2. **If no "based on" is present**, prompt the user (Step 2 above)

Examples:

| Input                                                         | Source Path                                          |
| ------------------------------------------------------------- | ---------------------------------------------------- |
| `based on path/to/SKILL.md`                                   | `path/to/SKILL.md`                                   |
| `based on .claude/skills-inbox/react-best-practices/SKILL.md` | `.claude/skills-inbox/react-best-practices/SKILL.md` |
| (empty)                                                       | (prompt user)                                        |

## Important Notes

- After porting, the skill is fully detached from its upstream source
- Use /update-skill to iterate on ported skills (same as any other project skill)
- Use /create-skill to build skills from scratch instead
- The porting guide is at `.claude/skills/creating-skills/references/PORTING-GUIDE.md`
