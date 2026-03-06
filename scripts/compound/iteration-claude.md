# Compound Product - Iteration Instructions

You are an autonomous coding agent working on a software project.

## Your Task

1. Read the config at `scripts/compound/config.json`
2. Read the PRD at `[outputDir]/prd.json` (from config)
3. Read the progress log at `[outputDir]/progress.txt` (check Codebase Patterns section first)
4. Check you're on the correct branch from PRD `branchName`. If not, switch to it or create from main.
5. Pick the **highest priority** task where `status` is `"pending"` (or `"failed"` if no pending tasks remain)
6. Implement that single task
7. Run quality checks from config `qualityChecks` array
8. Document learnings in your progress report (see "Document Learnings" section below)
9. If checks pass, commit ALL changes with message: `feat: [Task ID] - [Task Title]`
10. Update the PRD: set `status: "done"` and `passes: true` for the completed task
11. Append your progress to `[outputDir]/progress.txt`

## Progress Report Format

APPEND to progress.txt (never replace, always append):

```
## [Date/Time] - [Task ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered (e.g., "this codebase uses X for Y")
  - Gotchas encountered (e.g., "don't forget to update Z when changing W")
  - Useful context (e.g., "the settings panel is in component X")
---
```

The learnings section is critical - it helps future iterations avoid repeating mistakes.

## Consolidate Patterns

If you discover a **reusable pattern** that future iterations should know, add it to the `## Codebase Patterns` section at the TOP of progress.txt:

```
## Codebase Patterns
- Example: Use `sql` template for aggregations
- Example: Always use `IF NOT EXISTS` for migrations
- Example: Export types from actions.ts for UI components
```

Only add patterns that are **general and reusable**, not task-specific details.

## Status Transitions

Update the `status` field in prd.json as you work:

```
pending ──[picked up]──→ in_progress
in_progress ──[checks pass]──→ done (also set passes: true)
in_progress ──[checks fail]──→ failed (keep passes: false)
failed ──[re-attempted]──→ in_progress
```

- Set `status: "in_progress"` BEFORE starting work on a task
- Set `status: "done"` + `passes: true` on success
- Set `status: "failed"` on failure (keep `passes: false`)

## Document Learnings

When completing a task, include detailed learnings in your progress report (step 11). These learnings are extracted after the run completes into `docs/solutions/compound-product/`.

**In your progress entry, always include:**

- **Patterns discovered** — reusable knowledge (e.g., "this codebase uses X for Y")
- **Gotchas encountered** — things that tripped you up (e.g., "don't forget to update Z when changing W")
- **Dependencies** — unexpected coupling between files or modules
- **Testing insights** — what tests exist, how to run them, what's missing

**Do NOT include:**

- Temporary debugging notes
- Obvious implementation details (the git diff shows that)

## Quality Requirements

- ALL commits must pass your project's quality checks (from config)
- Do NOT commit broken code
- Keep changes focused and minimal
- Follow existing code patterns

## Browser Testing (Required for Frontend Tasks)

For any task that changes UI, you MUST verify it works in the browser:

1. Use browser automation to navigate to the relevant page
2. Verify the UI changes work as expected
3. Take a screenshot if helpful

A frontend task is NOT complete until browser verification passes.

## Stop Condition

After completing a task, check if ALL tasks have `passes: true`.

If ALL tasks are complete and passing, reply with:

<promise>COMPLETE</promise>

If there are still tasks with `passes: false`, end your response normally (another iteration will pick up the next task).

## Important

- Work on ONE task per iteration
- Commit frequently
- Keep CI green
- Read the Codebase Patterns section in progress.txt before starting
