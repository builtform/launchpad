---
description: "Plan Next Feature — create an implementation plan from a section spec"
---

# Plan Next Feature (PNF)

You are creating a detailed implementation plan for a specific product section. This command bridges the gap between section shaping (what to build) and implementation (how to build it). It reads the section spec, detects any gaps, conducts two-wave sub-agent research, and produces an actionable implementation plan.

---

## Step 0: Prerequisite Check (Lite)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-pnf --require=.launchpad/config.yml`.

Load `config.yml` paths via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-config-loader.py` — the `paths.architecture_dir` and `paths.tasks_dir` / `paths.sections_dir` values override the LaunchPad defaults (`docs/architecture`, `docs/tasks`, `docs/tasks/sections`) so this command works in any configured brownfield layout.

All hardcoded paths in the steps below are **defaults**; the command uses the config values when present.

---

## Step 1: Identify Target Section

### If `$ARGUMENTS` is provided:

1. **Check if it matches a section in the registry:**
   - Load sections via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin_stack_adapters/section_registry.py` (`section_registry.load_sections(repo_root)`). This reads `docs/tasks/SECTION_REGISTRY.md` first and falls back to parsing `docs/architecture/PRD.md` with a deprecation warning (back-compat shim; removed in v1.1).
   - Normalize the argument to kebab-case
   - Look for a matching section name

2. **Check if it matches a section spec file:**
   - Check `$paths.sections_dir/[argument].md` (default `docs/tasks/sections/[argument].md`)

3. **Check if it's a free-form description:**
   - If it doesn't match any section or file, treat it as a free-form feature description (skip to Step 4)

### If no arguments provided:

1. Load registry via `section_registry.load_sections(repo_root)` — honors the back-compat shim.
2. Show sections that are `shaped` or `planned` (ready for planning):

```
These sections are ready for implementation planning:

| Section | Status | Spec |
|---------|--------|------|
| auth    | shaped | docs/tasks/sections/auth.md |
| dashboard | shaped | docs/tasks/sections/dashboard.md |

Which section would you like to plan? (You can also describe a feature directly.)
```

If no sections are `shaped`, suggest running `/lp-shape-section` first:

```
No sections have been shaped yet. Before planning implementation, I recommend
shaping at least one section with /lp-shape-section [name] so we have detailed
requirements to plan from.

Alternatively, you can describe a feature directly and I'll plan from your description.
```

---

## Step 2: Load Section Context

If a section spec was identified, read these files:

Paths below use `config.yml` values: `$paths.sections_dir` (default `docs/tasks/sections`), `$paths.architecture_dir` (default `docs/architecture`), `$paths.tasks_dir` (default `docs/tasks`).

- `$paths.sections_dir/[section-name].md` — **primary input** (purpose, actions, flows, UI patterns, data requirements, edge cases)
- `$paths.tasks_dir/SECTION_REGISTRY.md` — authoritative section registry (back-compat shim reads PRD if missing)
- `$paths.architecture_dir/PRD.md` — overall product context, data shape
- `$paths.architecture_dir/TECH_STACK.md` — implementation technology
- `$paths.architecture_dir/DESIGN_SYSTEM.md` — visual design decisions (if exists; v1.1 scope for generator)
- `$paths.architecture_dir/APP_FLOW.md` — routes, navigation, auth flow
- `$paths.architecture_dir/BACKEND_STRUCTURE.md` — data models, API patterns, auth strategy
- `$paths.architecture_dir/FRONTEND_GUIDELINES.md` — component architecture, state management (v1.1)

Present context summary:

```
Planning implementation for section: [section-name]

Section spec loaded:
- Purpose: [1-line from spec]
- Actions: [count] user actions defined
- Flows: [count] user flows documented
- UI Patterns: [list]
- Data: [entities with CRUD operations]
- Edge Cases: [count] identified

Tech context:
- Frontend: [framework + styling]
- Backend: [framework]
- Database: [choice]
- Components: [library from design system]
```

---

## Step 2.5: Conditional Skill Loading

After loading section context, conditionally load methodology skills that inform plan quality:

**React / Frontend gate:**

- IF section spec references frontend pages/components/UI, OR task files are in `apps/web/` or `packages/ui/`:
  - Load skill: `react-best-practices`
  - Ensures plan steps include Suspense boundaries, parallel fetching, composition patterns, bundle optimization, etc.

**Stripe / Billing gate:**

- IF section spec references payment, billing, checkout, subscription, Stripe, pricing, or webhook:
  - Load skill: `stripe-best-practices`
  - Ensures plan steps include Checkout Sessions, webhook idempotency, Prisma billing models, dynamic payment methods, etc.

Skills are loaded silently if present. Skip silently if the skill directory does not exist in `.claude/skills/`.

The loaded skills inform the plan — implementation steps will reference specific rules (e.g., "Use `Promise.all()` for the three independent data fetches per `async-parallel` rule").

---

## Step 3: Gap Detection

**Before proceeding to research, scan the section spec for completeness.**

Check for:

- TBD markers in any section
- Empty sections (header with no content)
- Missing user flows (purpose defined but no flows)
- Missing edge cases (actions defined but no edge cases)
- Missing data requirements (actions defined but no entity CRUD mapping)

**If gaps are found**, present them to the user:

```
I found some gaps in the section spec that could affect planning:

1. [Section] User Flows: TBD — no step-by-step flows defined
2. [Section] Edge Cases: empty — no edge cases identified
3. [Section] Data Requirements: missing CRUD operations for [entity]

These gaps may lead to an incomplete plan. Would you like to:
A) Fill them in now (I'll ask the relevant questions)
B) Proceed anyway (I'll make reasonable assumptions and note them)
C) Run /lp-shape-section [name] to do a full re-shape
```

If the user chooses A, ask the relevant guided questions from `/lp-shape-section` for just the missing items. If B, proceed but document assumptions clearly in the plan. If C, stop and suggest the command.

---

## Step 4: Research & Discovery

Conduct two-wave sub-agent research to understand the codebase before planning.

### Wave 1: Discovery (parallel, FAST — no Read tool)

Spawn these locator agents in parallel:

- **file-locator** — finds all files related to this section's entities, routes, and features (Glob/Grep only)
- **pattern-finder** — finds similar features and patterns we can model after (Glob/Grep only)
- **docs-locator** — finds relevant documents in `docs/solutions/`, `docs/plans/`, `docs/reports/`, `docs/lessons/` (Glob/Grep only). **Conditional**: Only spawn if these directories contain real content beyond stubs.

These agents return file paths and pattern locations. They do NOT read file contents.

**Wait for ALL Wave 1 agents to complete before proceeding.**

### Wave 2: Analysis (parallel, AFTER Wave 1 completes)

Using the specific paths discovered by Wave 1, spawn targeted analyzer agents:

- **code-analyzer** — understands how relevant code works at the paths found by locators. Focus on: existing implementations of similar features, database schema, API patterns, component structure
- **docs-analyzer** — extracts decisions, constraints, rejected approaches, and promoted patterns from documents found by docs-locator (only if docs-locator returned results)
- **web-researcher** — if the section involves unfamiliar libraries, APIs, or patterns, research current documentation and best practices

**Wait for ALL Wave 2 agents to complete.**

---

## Step 5: Present Findings & Questions

After research completes:

```
Based on my research of the codebase, here's what I found:

**Existing Implementation:**
- [What already exists that this section can build on — file:line references]
- [Patterns to follow from similar features]

**Key Decisions Needed:**
- [Design choice that affects implementation — present options]
- [Technical question that requires human judgment]

**Assumptions (from section spec gaps, if any):**
- [Any assumptions made due to TBDs in the spec]

Questions that my research couldn't answer:
1. [Specific question]
2. [Specific question]
```

Only ask questions that genuinely cannot be answered from the spec or codebase.

---

## Step 6: Plan Structure

Once aligned on approach:

```
Here's my proposed plan structure:

## Implementation Phases:
1. [Phase name] — [what it accomplishes]
2. [Phase name] — [what it accomplishes]
3. [Phase name] — [what it accomplishes]

Does this phasing make sense? Should I adjust?
```

Get feedback on structure before writing details.

---

## Step 7: Write the Plan

Plan path resolves from `paths.plans_file_pattern` in `.launchpad/config.yml` (default `docs/tasks/sections/{section_name}-plan.md`). Expand `{section_name}` with the shaped section name (kebab-case). Example for section `auth-redesign` with defaults: `docs/tasks/sections/auth-redesign-plan.md`.

Ensure the parent directory exists before writing (it does if `/lp-define` ran — it scaffolds `paths.sections_dir`).

Use this template:

````markdown
# [Section Name] Implementation Plan

## Overview

[Brief description of what we're implementing, derived from section spec purpose]

## Section Spec Reference

- **Spec file**: `docs/tasks/sections/[section-name].md`
- **Status**: shaped → planned
- **Priority**: [from registry]

## Current State Analysis

[What exists now in the codebase, key constraints discovered during research]

### Key Discoveries:

- [Important finding with file:line reference]
- [Pattern to follow]
- [Constraint to work within]

## Desired End State

[What the section should look like when complete — derived from section spec]

## What We're NOT Doing

[From section spec Scope Boundaries + any additional exclusions from planning]

## Implementation Approach

[High-level strategy and reasoning — why this approach over alternatives]

## Phase 1: [Descriptive Name]

### Overview

[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File Group]

**File**: `path/to/file.ext`
**Changes**: [Summary of changes]

```[language]
// Specific code to add/modify
```

### Success Criteria:

#### Automated Verification:

- [ ] Unit tests pass: `pnpm test`
- [ ] Type checking passes: `pnpm typecheck`
- [ ] Linting passes: `pnpm lint`

#### Manual Verification:

- [ ] [Specific feature works as described in user flows]
- [ ] [Edge case from section spec handled correctly]

---

## Phase 2: [Descriptive Name]

[Similar structure...]

---

## Testing Strategy

### Unit Tests:

- [What to test — derived from section spec data requirements]

### Integration Tests:

- [End-to-end scenarios — derived from section spec user flows]

### Edge Case Tests:

- [From section spec edge cases table]

## UI Implementation Notes

- Component library: [from DESIGN_SYSTEM.md]
- UI patterns: [from section spec]
- Responsive approach: [from FRONTEND_GUIDELINES.md]

## References

- Section spec: `docs/tasks/sections/[section-name].md`
- Design system: `docs/architecture/DESIGN_SYSTEM.md`
- Related patterns: `[file:line]`
````

---

## Step 8: Update Section Registry

After the plan is written and the user approves it, update `docs/architecture/PRD.md`:

1. Find the section in the Product Sections table
2. Update its status from `shaped` to `planned`

---

## Step 9: Review & Iterate

Present the plan location and ask for feedback:

```
I've created the implementation plan at:
docs/plans/YYYY-MM-DD-[section-name].md

PRD.md registry updated: [section-name] → planned

Please review and let me know:
- Are the phases properly scoped?
- Are the success criteria specific enough?
- Any technical details that need adjustment?
- Missing edge cases or considerations?

When ready to implement, run /lp-implement-plan or /lp-inf.
```

Iterate based on feedback until the user is satisfied.

---

## Free-Form Mode (Backward Compatibility)

If the user provides a free-form description instead of a section name, fall back to free-form mode:

1. Skip section spec loading and gap detection (Steps 2-3)
2. Use the free-form description as the basis for research
3. Conduct the same two-wave research (Step 4)
4. Follow the same interactive planning process (Steps 5-9)
5. Do NOT update the section registry (no section to update)

This ensures backward compatibility for users who haven't adopted the section registry workflow.

---

## Important Guidelines

1. **Be Skeptical** — Question vague requirements. Identify potential issues early. Don't assume — verify with code.
2. **Be Interactive** — Don't write the full plan in one shot. Get buy-in at each major step.
3. **Be Thorough** — Read all context files COMPLETELY. Include specific file paths and line numbers. Write measurable success criteria.
4. **Be Practical** — Focus on incremental, testable changes. Consider migration and rollback.
5. **No Open Questions in Final Plan** — If you encounter open questions, STOP and research or ask. The plan must be complete and actionable.
6. **Detect gaps before planning** — A plan built on incomplete specs will produce incomplete features.
7. **Use pnpm workspace commands** — Automated verification should use `pnpm test`, `pnpm typecheck`, `pnpm lint` etc.

## Sub-Agent Spawning

When spawning research sub-agents:

1. **Spawn multiple agents in parallel** for efficiency
2. **Each agent should be focused** on a specific area
3. **Provide detailed instructions** including exact directories to search
4. **Be EXTREMELY specific about directories** — use `apps/web/`, `apps/api/`, `packages/db/` etc.
5. **Request specific file:line references** in responses
6. **Wait for all agents to complete** before synthesizing
7. **Verify sub-agent results** — cross-check findings against the actual codebase
