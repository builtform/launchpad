# Create Skill

Create a new Claude Code skill using the 7-phase Meta-Skill Forge methodology. This command is a thin interactive wrapper that parses user input and invokes the `creating-skills` skill.

## Initial Response

When this command is invoked:

1. **Check if parameters were provided**:

   Parse the input to extract:
   - **Skill topic:** The primary subject (everything before "based on")
   - **Context files:** Optional source material (everything after "based on")

   Invocation patterns:

   ```
   /create-skill frontend development with focus on React and Tailwind
   /create-skill "API testing" based on docs/articles/api-testing-guide.md
   /create-skill code review based on docs/articles/review-methodology.pdf
   /create-skill                    # no args — prompts for topic
   ```

2. **If parameters provided**:
   - Extract skill topic and optional context files
   - If context files specified ("based on ..."):
     - Read the files immediately and fully
     - Assess document size (10 pages or fewer vs more than 10 pages)
   - Proceed to invoke the `creating-skills` skill with the extracted parameters

3. **If no parameters provided**, respond with:

   ```
   I'll help you create a new Claude Code skill using the Meta-Skill Forge methodology.

   Please provide:
   1. The skill topic — what should this skill teach Claude to do?
   2. (Optional) Source material — any documents, articles, or guides to base the skill on

   Examples:
   - `/create-skill frontend development with focus on React and Tailwind`
   - `/create-skill "API testing" based on docs/articles/api-testing-guide.md`
   - `/create-skill code review` (no source material — I'll extract your expertise directly)

   Tip: If you have a long article, book, or course you want to encode as a skill, use "based on [file]" and the workflow will distill it automatically.
   ```

   Wait for user input, then parse and proceed.

4. **After parsing, invoke the creating-skills skill**:

   Read the skill definition at `.claude/skills/creating-skills/SKILL.md` and follow its 7-phase workflow.
   - The skill handles all 7 phases autonomously
   - This command does NOT implement the phases — it delegates entirely
   - Pass the extracted topic and context file paths to the skill

## Parameter Extraction Rules

When parsing user input, apply these rules:

1. **Everything before "based on"** is the skill topic
2. **Everything after "based on"** is treated as a file path (or comma-separated file paths)
3. **Quoted strings** are treated as a single topic token (e.g., `"API testing"`)
4. **If no "based on" is present**, the entire input is the skill topic with no context files

Examples:

| Input                                        | Topic                | Context Files             |
| -------------------------------------------- | -------------------- | ------------------------- |
| `frontend development`                       | frontend development | (none)                    |
| `"API testing" based on docs/guide.md`       | API testing          | `docs/guide.md`           |
| `code review based on docs/a.md, docs/b.pdf` | code review          | `docs/a.md`, `docs/b.pdf` |
| (empty)                                      | (prompt user)        | (prompt user)             |

## Important Notes

- This command is interactive (Phase A) — it requires human domain expertise during the skill creation process
- The skill handles research, extraction, contrarian analysis, writing, evaluation, and shipping
- For iterating on existing skills, use `/update-skill` instead
- The creating-skills skill is located at `.claude/skills/creating-skills/SKILL.md`
