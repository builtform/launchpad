---
name: lp-prd
description: "Generate a Product Requirements Document (PRD) for a new feature. Use when planning a feature, starting a new project, or when asked to create a PRD. Triggers on: create a prd, write prd for, plan this feature, requirements for, spec out."
---

# PRD Generator

Create detailed Product Requirements Documents that are clear, actionable, and suitable for implementation.

---

## The Job

1. Receive a feature description
2. **Detect mode:** Determine if running interactively or autonomously
3. **[Interactive only]** Ask 3-5 MCQ clarifying questions
4. **Research:** Scan codebase and documentation for relevant patterns
5. **Self-clarify:** Ask yourself 3-5 critical questions and answer them based on context + research
6. Generate a structured PRD based on your answers
7. Save to `docs/tasks/prd-[feature-name].md`

**Important:**

- **Autonomous mode:** Do NOT ask the user questions. Answer them yourself using available context.
- **Interactive mode:** Ask the MCQ questions in Step 0, then self-clarify in Step 1.
- Do NOT start implementing. Just create the PRD.

---

## Step 0: Detect Mode

Check if the request includes analysis context (JSON from analyze-report.sh, report references, or piped input).

- **If YES** → Skip to Step 0.5 (Codebase & Documentation Research). You are in autonomous mode.
- **If NO** → You are in interactive mode. Ask 3-5 clarifying questions before proceeding.

### Interactive Mode: Clarifying Questions

Present 3-5 questions with lettered options. The user responds with shorthand (e.g., "1A, 2C, 3B, 4D").

**Always ask these 3 core questions:**

1. **What is the primary goal?**
   A. Fix an existing bug or regression
   B. Add a new user-facing feature
   C. Improve performance or reliability
   D. Refactor or restructure existing code

2. **What is the scope?**
   A. Small — single file or component (< 1 hour)
   B. Medium — a few files, one feature area (1-4 hours)
   C. Large — multiple systems or cross-cutting (4+ hours, should be split)

3. **Are there files or systems that MUST NOT be modified?**
   A. No restrictions
   B. Yes — I'll specify which files/systems to avoid

**Add 1-2 context-specific questions based on the feature description:**

Examples:

- "Does this feature have a UI component?" (A. Yes / B. No / C. Unsure)
- "Are there existing patterns in the codebase to follow?" (A. Yes, follow [X] / B. No, this is novel / C. Unsure — investigate first)
- "Does this require database changes?" (A. Yes / B. No / C. Unsure)
- "What is the priority tier?" (A. P0 — blocks launch / B. P1 — needed for v1 / C. P2 — nice to have)

After receiving answers, incorporate them into the Self-Clarification step and proceed to PRD generation.

---

## Step 0.5: Codebase & Documentation Research

Before generating the PRD, research the codebase AND existing documentation to
understand patterns, prior decisions, and related files. This prevents generating
PRDs that conflict with established conventions or repeat already-documented mistakes.

### In Interactive Mode:

Spawn FOUR parallel sub-agents (2 codebase + 2 docs):

1. **file-locator** — Find all files related to the feature topic
   - Prompt: "Find all files related to [feature topic]. Include implementation files,
     tests, configs, and documentation."

2. **pattern-finder** — Find similar implementations to model after
   - Prompt: "Find existing patterns for [similar feature type]. Show code examples
     with file:line references."

3. **docs-locator** — Find all documentation related to the feature topic
   - Prompt: "Find all documents related to [feature topic]. Include plans, reports,
     learnings, architecture docs, and lessons."

4. **docs-analyzer** — Extract decisions, constraints, and rejected approaches
   - Prompt: "Analyze documentation related to [feature topic]. Extract key decisions,
     constraints, rejected approaches, promoted patterns, and warnings."

Wait for all four agents to return results before proceeding.

### In Autonomous Mode:

Do a quick inline scan instead (no sub-agents, keep it fast):

1. Glob for files matching the feature topic keywords
2. Grep for similar implementations (2-3 targeted searches)
3. Read CLAUDE.md and AGENTS.md for project conventions
4. Quick grep of docs/ for prior decisions on the topic

### Use Research Findings To:

- Reference existing files in the PRD (so the agent doesn't recreate them)
- Follow established patterns (naming, directory structure, code style)
- Populate the "Files NOT to Modify" section with related but out-of-scope files
- Note relevant conventions in the "Technical Considerations" section
- Inform the Self-Clarification answers with actual codebase knowledge
- Incorporate prior decisions and constraints from documentation (avoid repeating past mistakes)
- Reference rejected approaches so the PRD doesn't propose them again

---

## Step 1: Self-Clarification

Before generating the PRD, ask yourself these questions and write your answers. This ensures you've thought through the problem:

1. **Problem/Goal:** What problem does this solve? Why now?
2. **Core Functionality:** What are the 2-3 key actions this enables?
3. **Scope/Boundaries:** What should this explicitly NOT do?
4. **Success Criteria:** How do we verify it's working?
5. **Constraints:** What technical/time constraints exist?

### Format Your Thinking:

```
## Self-Clarification

1. **Problem/Goal:** [Your answer based on the request and codebase context]
2. **Core Functionality:** [Your answer]
3. **Scope/Boundaries:** [Your answer - be conservative, prefer smaller scope]
4. **Success Criteria:** [Your answer - must be verifiable]
5. **Constraints:** [Your answer - note any mentioned constraints like "no DB migrations"]
```

Use context from: the request, AGENTS.md, existing code patterns, and any reports/analysis provided.

---

## Step 2: PRD Structure

Generate the PRD with these sections:

### 1. Introduction/Overview

Brief description of the feature and the problem it solves.

### 2. Goals

Specific, measurable objectives (bullet list).

### 2.5. Desired End State

**This section is ALWAYS included.** It is never skipped.

A 2-4 sentence description of what the system looks like AFTER this feature
is complete. This is the holistic "north star" — distinct from individual task criteria.

Include:

- What the user can now do that they couldn't before
- How to verify the feature end-to-end (a single walkthrough)

Example:
"After implementation, users can assign priority levels (high/medium/low)
to any task from the task edit modal. Priority is displayed as a colored badge
on every task card. The dashboard can be filtered by priority level. To verify:
create a task, set it to 'high' priority, confirm the red badge appears,
and filter the dashboard to show only high-priority tasks."

### 3. Tasks

Each task needs:

- **Title:** Short descriptive name
- **Description:** What needs to be done
- **Acceptance Criteria:** Verifiable checklist of what "done" means

Each task should be small enough to implement in one focused session.

**Format:**

```markdown
### T-001: [Title]

**Description:** [What to implement]

**Acceptance Criteria:**

- [ ] Specific verifiable criterion
- [ ] Another criterion
- [ ] Quality checks pass
- [ ] **[UI tasks only]** Verify in browser
```

**Important:**

- Acceptance criteria must be verifiable, not vague. "Works correctly" is bad. "Button shows confirmation dialog before deleting" is good.
- **For any task with UI changes:** Always include browser verification as acceptance criteria.

### 4. Functional Requirements

**This section is ALWAYS included.** It is never skipped.

Numbered list of specific functionalities WITH priority tiers:

**P0 — Must Have (MVP, ship-or-die):**

- FR-1: The system must allow users to...
- FR-2: When a user clicks X, the system must...

**P1 — Should Have (needed for credible v1):**

- FR-3: The system should...

**P2 — Nice to Have (can wait for v2):**

- FR-4: The system could...

Be explicit and unambiguous. Every requirement MUST have a tier.
If a requirement is P0, the PRD should NOT be considered complete
unless all P0 items have corresponding tasks.

If ALL requirements are the same priority (e.g., a small bug fix where
everything is P0), still use the tier labels for consistency:

**P0 — Must Have:**

- FR-1: Fix the null pointer exception in auth middleware
- FR-2: Add regression test for the fix

**P1 — Should Have:**
N/A — all requirements are P0 for this fix.

**P2 — Nice to Have:**
N/A — all requirements are P0 for this fix.

### 5. Non-Goals (Out of Scope)

What this feature will NOT include. Critical for managing scope.

### 5.5. Files NOT to Modify

List specific files or directories that must not be touched during implementation.
This prevents agents from "improving" adjacent code.

**This section is ALWAYS included.** It is never skipped.

Format:

- `path/to/file.ext` — reason why it should not be modified
- `path/to/directory/` — reason

If there are no restrictions, write:
"No restrictions — all files in scope may be modified as needed for this feature."

### 6. Technical Considerations

**This section is ALWAYS included.** It is never skipped.

#### 6a. Constraints and Dependencies

- Known constraints or dependencies
- Integration points with existing systems

If none: "N/A — no known constraints or external dependencies."

#### 6b. Non-Functional Requirements

Specify measurable thresholds for performance, security, or accessibility.

| Category      | Requirement         | Threshold                        |
| ------------- | ------------------- | -------------------------------- |
| Performance   | Page load time      | < 800ms on 3G                    |
| Performance   | API response time   | < 200ms p95                      |
| Security      | Authentication      | All endpoints require auth token |
| Accessibility | Keyboard navigation | Full tab-order support           |

Only include categories relevant to this feature. If this is a simple change
with no NFR implications, write:
"N/A — this change has no measurable performance, security, or accessibility impact."

### 6.5. Edge Cases

**This section is ALWAYS included.** It is never skipped.

List edge cases with expected behavior in a structured table.

Format:
| Scenario | Expected Behavior | Fallback |
|---|---|---|
| [What could go wrong] | [What the system should do] | [Recovery action, or "N/A"] |

For simple configuration changes or cosmetic updates where no meaningful edge cases exist, write:
"N/A — this change has no user-facing logic with edge case scenarios."

Example:
| Scenario | Expected Behavior | Fallback |
|---|---|---|
| User submits form with past date | Show validation error: "Date must be in the future" | N/A |
| Email service is down | Queue email for retry, show "Email will be sent shortly" | Retry 3x, then log failure |
| File upload exceeds 10MB limit | Show error before upload starts (client-side check) | Server-side 413 response |

### 7. Success Metrics

How will success be measured?

### 8. Open Questions

Remaining questions or areas needing clarification.

### 8.5. Examples

**This section is ALWAYS included.** It is never skipped.

Provide input/output examples for API endpoints, data transformations, or
complex logic. These serve as ground truth for the implementing agent.

Format:
**Example 1: [Scenario name]**

- Input: `[request/input data]`
- Output: `[expected response/output]`

**Example 2: [Error case]**

- Input: `[invalid input]`
- Output: `[expected error response]`

For UI-only features or configuration changes, write:
"N/A — this feature has no API or data transformation logic requiring examples."

---

## Writing for Agents

The PRD reader may be an AI agent. Therefore:

- Be explicit and unambiguous
- Avoid jargon or explain it
- Provide enough detail to understand purpose and core logic
- Number requirements for easy reference
- Use concrete examples where helpful

---

## Output

- **Format:** Markdown (`.md`)
- **Location:** `docs/tasks/`
- **Filename:** `prd-[feature-name].md` (kebab-case)

---

## Example PRD

```markdown
# PRD: Task Priority System

## Introduction

Add priority levels to tasks so users can focus on what matters most.

## Goals

- Allow assigning priority (high/medium/low) to any task
- Provide clear visual differentiation between priority levels
- Enable filtering by priority

## Desired End State

After implementation, users can assign priority levels (high/medium/low)
to any task from the task edit modal. Priority is displayed as a colored badge
on every task card. The dashboard can be filtered by priority level. To verify:
create a task, set it to 'high' priority, confirm the red badge appears,
and filter the dashboard to show only high-priority tasks.

## Tasks

### T-001: Add priority field to database

**Description:** Add priority column to tasks table for persistence.

**Acceptance Criteria:**

- [ ] Add priority column: 'high' | 'medium' | 'low' (default 'medium')
- [ ] Generate and run migration successfully
- [ ] Quality checks pass

### T-002: Display priority indicator on task cards

**Description:** Show colored priority badge on each task card.

**Acceptance Criteria:**

- [ ] Each task card shows colored badge (red=high, yellow=medium, gray=low)
- [ ] Priority visible without hovering
- [ ] Quality checks pass
- [ ] Verify in browser

### T-003: Add priority selector to task edit

**Description:** Allow changing task priority in edit modal.

**Acceptance Criteria:**

- [ ] Priority dropdown in task edit modal
- [ ] Shows current priority as selected
- [ ] Saves on selection change
- [ ] Quality checks pass
- [ ] Verify in browser

## Functional Requirements

**P0 — Must Have:**

- FR-1: Add `priority` field to tasks table with enum constraint ('high' | 'medium' | 'low')
- FR-2: Display colored priority badge on each task card (red=high, yellow=medium, gray=low)
- FR-3: Include priority selector in task edit modal

**P1 — Should Have:**

- FR-4: Priority filter on the dashboard view

**P2 — Nice to Have:**
N/A — all requirements are P0/P1 for this feature.

## Non-Goals

- No priority-based notifications
- No automatic priority assignment

## Files NOT to Modify

- `src/components/Layout.tsx` — shared layout, already stable
- `src/lib/auth.ts` — auth logic is out of scope for this feature
- `packages/ui/` — shared UI library, changes require separate review

## Technical Considerations

### 6a. Constraints and Dependencies

- Requires Prisma migration for new column
- Must integrate with existing task card component (`src/components/TaskCard.tsx`)

### 6b. Non-Functional Requirements

| Category      | Requirement                | Threshold                                     |
| ------------- | -------------------------- | --------------------------------------------- |
| Performance   | Priority badge render time | No additional re-renders beyond existing card |
| Accessibility | Keyboard navigation        | Priority selector must be keyboard-accessible |
| Security      | N/A                        | N/A — no new auth or data exposure surface    |

## Edge Cases

| Scenario                                 | Expected Behavior                             | Fallback                                        |
| ---------------------------------------- | --------------------------------------------- | ----------------------------------------------- |
| Task created without explicit priority   | Default to 'medium'                           | N/A                                             |
| Bulk edit changes priority of 100+ tasks | Process in batch, show progress indicator     | Timeout after 30s, show partial success message |
| Priority filter returns zero results     | Show empty state: "No [priority] tasks found" | N/A                                             |

## Success Metrics

- Users can change priority in <2 clicks
- High-priority tasks immediately visible

## Open Questions

None — all requirements are fully specified.

## Examples

N/A — this feature has no API or data transformation logic requiring examples.
```

---

## Checklist

Before saving the PRD:

- [ ] Mode detected (interactive or autonomous) and appropriate flow followed
- [ ] Codebase & documentation research completed (Step 0.5)
- [ ] Completed self-clarification (answered all 5 questions)
- [ ] Desired End State section is present (2-4 sentences with walkthrough)
- [ ] Tasks are small and specific (completable in one session each)
- [ ] Acceptance criteria are verifiable (not vague)
- [ ] Functional requirements are numbered, unambiguous, and have P0/P1/P2 tiers
- [ ] Non-goals section defines clear boundaries
- [ ] Files NOT to Modify section is present (even if "no restrictions")
- [ ] Technical Considerations includes 6a (Constraints) and 6b (NFRs) — with N/A if not applicable
- [ ] Edge Cases section is present (table format, or N/A with reason)
- [ ] Open Questions section is present
- [ ] Examples section is present (input/output pairs, or N/A with reason)
- [ ] Saved to `docs/tasks/prd-[feature-name].md`
