# Implement Plan

You are tasked with implementing an approved technical plan from `docs/plans/`. These plans contain phases with specific changes and success criteria.

## Getting Started

When given a plan path:

- Read the plan completely and check for any existing checkmarks (- [x])
- Read the original ticket and all files mentioned in the plan
- **Read files fully** - never use limit/offset parameters, you need complete context
- Think deeply about how the pieces fit together
- Create a todo list to track your progress
- Start implementing if you understand what needs to be done

If no plan path provided, ask for one.

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. Your job is to:

- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Verify your work makes sense in the broader codebase context
- Update checkboxes in the plan as you complete sections

When things don't match the plan exactly, think about why and communicate clearly. The plan is your guide, but your judgment matters too.

If you encounter a mismatch:

- STOP and think deeply about why the plan can't be followed
- Present the issue clearly:

  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]

  How should I proceed?
  ```

## Verification Approach

After implementing a phase:

- Run the success criteria checks (usually `pnpm lint && pnpm typecheck && pnpm test` covers everything)
- Fix any issues before proceeding
- Update your progress in both the plan and your todos
- Check off completed items in the plan file itself using Edit

Don't let verification interrupt your flow - batch it at natural stopping points.

## Matching Existing Patterns

Before implementing each phase, spawn a **pattern-finder** sub-agent to find existing patterns you should follow. This ensures new code is consistent with established conventions.

**When to spawn it:**

- At the start of each phase, to find similar implementations to model after
- When creating new components, routes, services, or tests that likely have precedents
- When the plan references patterns like "follow the existing X approach"

**How to spawn it:**

```
Task(subagent_type="pattern-finder", prompt="Find existing patterns for [what you're about to implement] in [relevant directory]")
```

Use the returned code examples as your template — match the style, naming, structure, and error handling patterns exactly.

## Consulting Accumulated Knowledge

Before each phase, also consider spawning a **docs-analyzer** sub-agent to check if `docs/solutions/` contains relevant learnings for the current phase's domain. This surfaces previously documented decisions, constraints, rejected approaches, and promoted patterns that may affect your implementation.

**When to spawn it:**

- If `docs/solutions/` contains files beyond stubs (i.e., the project has accumulated learnings from previous autonomous runs)
- When the phase touches a domain where past learnings are likely (e.g., auth, data pipeline, deployment)
- When the plan references constraints or decisions that may have been documented

**How to spawn it:**

```
Task(subagent_type="docs-analyzer", prompt="Check docs/solutions/ and docs/lessons/ for any documented decisions, constraints, or promoted patterns related to [current phase's domain]")
```

Use the returned insights to avoid repeating mistakes and to follow previously promoted patterns. If the docs-analyzer finds relevant constraints or rejected approaches, factor them into your implementation.

## If You Get Stuck

When something isn't working as expected:

- First, make sure you've read and understood all the relevant code
- Consider if the codebase has evolved since the plan was written
- Present the mismatch clearly and ask for guidance

Use sub-tasks for:

- **Pattern matching**: Spawn **pattern-finder** to find similar implementations to model after
- **Targeted debugging**: Understanding unfamiliar code paths
- **Exploring unfamiliar territory**: Locating relevant files and understanding how they work

## Resuming Work

If the plan has existing checkmarks:

- Trust that completed work is done
- Pick up from the first unchecked item
- Verify previous work only if something seems off

Remember: You're implementing a solution, not just checking boxes. Keep the end goal in mind and maintain forward momentum.
