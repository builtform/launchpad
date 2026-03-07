# Compound Product - Iteration Instructions

You are an autonomous coding agent working on a software project.

## Your Task

1.  Read the config at `scripts/compound/config.json`
2.  Read the PRD at `[outputDir]/prd.json` (from config)
    If any of these fields are missing from prd.json, treat them as their defaults:
    - `desiredEndState`: "" (empty — no north star available)
    - `filesNotToModify`: [] (no restrictions)
    - `manualVerification` (per task): [] (no manual checks)
    - `skipped` (per task): null (not skipped)
      Do NOT fail or abort — operate with the available data.
      2.5. Check `filesNotToModify` in prd.json. These files are OFF LIMITS.
      Before committing, verify you have NOT modified any listed file.
      If you accidentally modified a restricted file, revert it with
      `git checkout -- [file]` before committing.

           To check: run `git diff --name-only` and compare against the
           `filesNotToModify` paths. Revert any matches.

3.  Read the progress log at `[outputDir]/progress.txt` (check Codebase Patterns section first)
4.  Note the `desiredEndState` field in prd.json — this is the holistic goal.
    When making implementation decisions, ensure your work moves toward this end state,
    not just the individual task criteria. If a task's implementation could go multiple
    directions, choose the direction that best serves the desired end state.
5.  Check you're on the correct branch from PRD `branchName`. If not, switch to it or create from main.
6.  Pick the **highest priority** task where `status` is `"pending"` (or `"failed"` if no pending tasks remain)
7.  Implement that single task
8.  Run quality checks from config `qualityChecks` array
9.  Document learnings in your progress report (see "Document Learnings" section below)
10. If checks pass, commit ALL changes with message: `feat: [Task ID] - [Task Title]`
11. Update the PRD: set `status: "done"` and `passes: true` for the completed task
12. Append your progress to `[outputDir]/progress.txt`

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
in_progress ──[not applicable]──→ skipped (set skipped: "reason string")
failed ──[re-attempted]──→ in_progress
```

- Set `status: "in_progress"` BEFORE starting work on a task
- Set `status: "done"` + `passes: true` on success
- Set `status: "failed"` on failure (keep `passes: false`)
- Set `status: "skipped"` + `skipped: "[reason]"` + keep `passes: false` when genuinely inapplicable

### When to Skip a Task

Set `status: "skipped"` and `skipped: "[reason]"` ONLY when:

- The task is not applicable to the current project configuration
- A prerequisite is impossible (e.g., "no database exists for DB migration task")
- The task was already accomplished by a previous task (consolidation)

**Important**: Skipped tasks keep `passes: false`. They did not actually pass — they were
determined to be inapplicable. The `passes` field stays semantically pure: it only means
"the acceptance criteria were executed and passed." The stop condition and board.sh check
`status` (not `passes`) for completion.

Do NOT skip tasks just because they are difficult. Only skip when genuinely inapplicable.
Skipped tasks count as "complete" for the stop condition.

## Document Learnings

When completing a task, include detailed learnings in your progress report (step 12). These learnings are extracted after the run completes into `docs/solutions/compound-product/`.

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

### Manual Verification Items

If the task has a non-empty `manualVerification` array in prd.json, these items
require human testing and CANNOT be verified by the agent. When completing a task
with manual verification items:

1. Complete all `acceptanceCriteria` (machine-verifiable) — these determine `passes: true`
2. Log the `manualVerification` items in your progress report as:
   ```
   **Manual verification needed:**
   - [ ] [Item from manualVerification array]
   - [ ] [Another item]
   ```
3. Set `passes: true` based on automated criteria only.
   Manual items are logged for the human reviewer on the PR.

## Stop Condition

After completing a task, check if ALL tasks have `status: "done"` OR `status: "skipped"`.
Do NOT check `passes` for the stop condition — check `status` instead. This is because
skipped tasks keep `passes: false` (they didn't actually pass), so a passes-based check
would never reach 100%.

If ALL tasks are complete (done or skipped), reply with:

<promise>COMPLETE</promise>

If there are still tasks with `status` other than "done" or "skipped", end your response normally (another iteration will pick up the next task).

## Important

- Work on ONE task per iteration
- Commit frequently
- Keep CI green
- Read the Codebase Patterns section in progress.txt before starting
