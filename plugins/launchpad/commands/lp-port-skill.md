---
name: lp-port-skill
description: "Port an external skill into the project format using the 4-phase Skill Porting workflow"
---

# Port Skill

Port an external skill (from Vercel, Anthropic, community repos, or any local file) into
the project's format using the 4-phase Skill Porting workflow. The ported skill is fully
detached from its source — it becomes a native project skill, updateable with /lp-update-skill.

## Step 1: Parse Input

Extract from $ARGUMENTS:

- **Source path:** The skill to port (required — everything after "based on")

Invocation patterns:

```
/lp-port-skill based on path/to/external/SKILL.md
/lp-port-skill based on .claude/skills-inbox/react-best-practices/SKILL.md
/lp-port-skill                   # no args — prompts for source
```

## Step 2: If no arguments provided, respond with:

```
I'll help you port an external skill into the project.

Please provide the source:
- A local file path: /lp-port-skill based on path/to/SKILL.md
- A file in the skills inbox: /lp-port-skill based on .claude/skills-inbox/skill-name/SKILL.md

The ported skill will be adapted to the project's format, validated against the 16
quality criteria, and registered in CLAUDE.md, AGENTS.md, and the skills catalog
(docs/skills-catalog/skills-index.md + skills-usage.json).
After porting, use /lp-update-skill to iterate on it like any other project skill.
```

Wait for user input, then proceed.

## Step 3: Execute the Porting Workflow

Read `${CLAUDE_PLUGIN_ROOT}/skills/lp-creating-skills/references/PORTING-GUIDE.md` and follow its 4-phase workflow.

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
- Use /lp-update-skill to iterate on ported skills (same as any other project skill)
- Use /lp-create-skill to build skills from scratch instead
- The porting guide is at `${CLAUDE_PLUGIN_ROOT}/skills/lp-creating-skills/references/PORTING-GUIDE.md`

## Methodology attribution

When the ported skill operationalizes a named author's published work (book, course, article) — which is the most common porting scenario since you are adapting third-party authored material — the same framework-citation rules from `/lp-create-skill` apply. Use framework-citation form ("Based on [author]'s [framework]", "Operationalizes [author]'s methodology", "Frameworks taught by [author]", author + book title in a recommended-reading list, framework-naming with attribution). Avoid ingestion form ("faithful reading", "book-faithful", "ingested" / "books to ingest", "derived from a reading/study/pass of the book", "preserves [author]'s exact terminology/phrasing/wording", block-quote epigraphs attributed to authors, "[Author] writes / notes / explicitly states", section-level book references like "Part 5 of [Book]" or "Chapter 3", author-attributed phrase quotes). The porting guide at `${CLAUDE_PLUGIN_ROOT}/skills/lp-creating-skills/references/PORTING-GUIDE.md` and the underlying `lp-creating-skills` skill carry the full guidance + verification grep recipe.
