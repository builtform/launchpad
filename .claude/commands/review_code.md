# Review Code for Pattern Consistency

You are tasked with reviewing recent code changes to verify they follow existing codebase patterns and conventions.

## When to Use

Use this command after implementing features, modifying code, or before committing — to catch inconsistencies with established patterns.

## Process

### Step 1: Identify What Changed

1. Run `git diff --name-only` (or `git diff --name-only HEAD~N` for recent commits) to see which files changed
2. Read each changed file FULLY to understand the new code
3. Create a todo list to track the review

### Step 2: Spawn Pattern Research Sub-Agents

For each significant change, spawn **codebase-pattern-finder** sub-agents in parallel to find how similar things are done elsewhere in the codebase:

- **For new components/modules**: "Find existing patterns for [component type] in [relevant directory]"
- **For new API routes/handlers**: "Find existing patterns for route handlers and middleware usage"
- **For new tests**: "Find existing test patterns for [type of test] in [relevant directory]"
- **For data access patterns**: "Find existing patterns for database queries and data transformations"
- **For error handling**: "Find existing error handling patterns in [relevant directory]"

Spawn multiple agents concurrently — one per changed area:

```
Task(subagent_type="codebase-pattern-finder", prompt="Find existing patterns for [what was changed] in [directory]")
```

### Step 3: Compare and Report

After all sub-agents complete, compare the new code against the found patterns:

```
## Pattern Consistency Review

### [Changed File 1]

**Pattern found**: [Existing pattern with file:line reference]
**New code**: [What the new code does]
**Status**: Consistent / Inconsistent

If inconsistent:
- **Difference**: [What differs]
- **Existing convention**: [Code snippet from pattern-finder]
- **Suggested alignment**: [How to match the convention]

### [Changed File 2]
...

## Summary
- X files reviewed
- Y consistent with existing patterns
- Z inconsistencies found (listed above)
```

### Step 4: Present Findings

- Present the comparison results to the user
- For each inconsistency, show both the existing pattern and the new code side by side
- Let the user decide whether to align with existing patterns or intentionally diverge

## Important Notes

- This is a **pattern consistency check**, not a general code review
- The `codebase-pattern-finder` agent is a documentarian — it shows what exists, not what should be
- Your job is to compare, not to judge — present the facts and let the user decide
- If no existing patterns are found for a given change, note it as "new pattern" rather than flagging it
- Always spawn sub-agents for the pattern research — do not try to search for patterns yourself in the main context
