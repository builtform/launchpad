---
name: tasks
description: "Convert a PRD markdown file to prd.json for execution. Triggers on: convert prd, create tasks, prd to json, generate tasks from prd."
---

# Tasks - Convert PRD to JSON Format

Converts a PRD markdown document into the prd.json format for the execution loop.

---

## The Job

1. Read the PRD markdown file
2. Extract tasks (from Tasks section or User Stories)
3. **Explode each task into granular, machine-verifiable sub-tasks**
4. Order by dependencies (schema -> backend -> UI -> tests)
5. Output to the specified prd.json location

**Autonomous mode:** Do not ask questions. Use the PRD content and any provided context (branch name, output path) to generate prd.json immediately.

---

## Critical: Agent-Testable Tasks

Every task must be **autonomously verifiable** by an AI agent without human intervention.

### The Golden Rule

Each acceptance criterion must be a **boolean check** that an agent can definitively pass or fail:

**BAD - Vague/subjective:**

- "Works correctly"
- "Review the configuration"
- "Document the findings"
- "Identify the issue"
- "Verify it looks good"

**GOOD - Machine-verifiable:**

- "Run `pnpm typecheck` - exits with code 0"
- "Navigate to /signup - page loads without console errors"
- "Click submit button - form submits and redirects to /dashboard"
- "File `src/auth/config.ts` contains `redirectUrl: '/onboarding'`"
- "API response status is 200 and body contains `{ success: true }`"

### Acceptance Criteria Patterns

Use these patterns for agent-testable criteria:

| Type           | Pattern                                             | Example                                           |
| -------------- | --------------------------------------------------- | ------------------------------------------------- |
| Command        | "Run `[cmd]` - exits with code 0"                   | "Run `pnpm test` - exits with code 0"             |
| File check     | "File `[path]` contains `[string]`"                 | "File `middleware.ts` contains `clerkMiddleware`" |
| Browser nav    | "Navigate to `[url]` - [expected result]"           | "Navigate to /login - SignIn component renders"   |
| Browser action | "Click `[element]` - [expected result]"             | "Click 'Submit' button - redirects to /dashboard" |
| Console check  | "Browser console shows no errors"                   |                                                   |
| API check      | "GET/POST `[url]` returns `[status]` with `[body]`" | "POST /api/signup returns 200"                    |

---

## Input

A PRD file created by the `prd` skill, typically at `tasks/prd-[feature-name].md`.

---

## Output Format

Create `prd.json`:

```json
{
  "project": "{{PROJECT_NAME}}",
  "branchName": "compound/[feature-name]",
  "description": "[One-line description from PRD]",
  "startedAt": null,
  "completedAt": null,
  "tasks": [
    {
      "id": "T-001",
      "title": "[Specific action verb] [specific target]",
      "description": "[1-2 sentences: what to do and why]",
      "acceptanceCriteria": [
        "Specific machine-verifiable criterion with expected outcome",
        "Another criterion with pass/fail condition",
        "Run `pnpm typecheck` - exits with code 0"
      ],
      "priority": 1,
      "status": "pending",
      "passes": false,
      "notes": ""
    }
  ]
}
```

---

## Task Granularity Rules

### Target: 8-15 tasks per PRD

PRDs should typically generate 8-15 granular tasks. If you have fewer than 6, you probably need to split tasks further.

### Split Multi-Step Tasks

**TOO BIG:**

```json
{
  "title": "Test signup flow and fix issues",
  "acceptanceCriteria": [
    "Test the signup flow",
    "Identify any issues",
    "Fix the issues",
    "Verify the fix works"
  ]
}
```

**PROPERLY SPLIT:**

```json
[
  {
    "id": "T-001",
    "title": "Navigate to signup page and capture baseline",
    "acceptanceCriteria": [
      "Navigate to /signup - page loads successfully",
      "Screenshot saved to tmp/signup-baseline.png",
      "Browser console errors logged to tmp/signup-console.log"
    ]
  },
  {
    "id": "T-002",
    "title": "Test email input field validation",
    "acceptanceCriteria": [
      "Enter 'invalid-email' in email field - error message appears",
      "Enter 'valid@example.com' - error message disappears",
      "Field has aria-invalid='true' when invalid"
    ]
  },
  {
    "id": "T-003",
    "title": "Test form submission with valid data",
    "acceptanceCriteria": [
      "Fill email: 'test@example.com', password: 'TestPass123!'",
      "Click submit button - loading state appears",
      "After submit - redirects to /onboarding OR error message appears"
    ]
  }
]
```

### One Concern Per Task

Each task should do ONE thing:

| Concern               | Separate Task |
| --------------------- | ------------- |
| Navigate to page      | T-001         |
| Check for errors      | T-002         |
| Test input validation | T-003         |
| Test form submission  | T-004         |
| Verify redirect       | T-005         |
| Implement fix         | T-006         |
| Verify fix            | T-007         |

### Investigation vs Implementation

**Never combine "find the problem" with "fix the problem"** in one task.

---

## Task Sizing

Each task must be completable in ONE iteration (~one context window).

**Right-sized tasks:**

- Check one configuration file for specific values
- Test one user interaction (click, type, submit)
- Verify one redirect or navigation
- Change one prop or configuration value
- Add one CSS rule or style change
- Test one viewport size

**Too big (split these):**

- "Test the entire signup flow" -> Split into: load page, test inputs, test submit, test redirect
- "Fix the bug" -> Split into: identify file, make change, verify change, test regression
- "Add authentication" -> Split into: schema, middleware, login UI, session handling

---

## Priority Ordering

Set priority based on dependencies:

1. **Investigation tasks** - priority 1-3 (understand before changing)
2. **Schema/database changes** - priority 4-5
3. **Backend logic changes** - priority 6-7
4. **UI component changes** - priority 8-9
5. **Verification tasks** - priority 10+

Lower priority number = executed first.

---

## Process

### Step 1: Read the PRD

Read the PRD file the user specified.

### Step 2: Extract High-Level Tasks

Look for:

- Tasks (T-001, T-002, etc.)
- User Stories (US-001, US-002, etc.)
- Functional Requirements (FR-1, FR-2, etc.)
- Any numbered/bulleted work items

### Step 3: Explode Into Granular Tasks

For each high-level task:

1. List every distinct action required
2. Separate investigation from implementation
3. Separate each verification concern
4. Ensure each has boolean pass/fail criteria

### Step 4: Order by Dependencies

Determine logical order:

1. What needs to be understood first? (investigation)
2. What needs to exist first? (database schema)
3. What depends on that? (backend logic)
4. What depends on that? (UI components)
5. What verifies everything? (browser tests)

### Step 5: Generate prd.json

Create the JSON file with all tasks having `status: "pending"` and `passes: false`.

### Step 6: Save and Summarize

Save the file immediately, then output a brief summary:

- Number of tasks created
- Task order with priorities
- Branch name
- File path saved to

**Do NOT wait for user confirmation.** Save the file and proceed.

---

## Checklist

Before saving prd.json:

- [ ] **8-15 tasks** generated (not 3-5)
- [ ] Each task does **ONE thing**
- [ ] Investigation separated from implementation
- [ ] Every criterion is **boolean pass/fail**
- [ ] No vague words: "review", "identify", "document", "verify it works"
- [ ] Commands specify expected exit code
- [ ] Browser actions specify expected result
- [ ] All tasks have `status: "pending"` and `passes: false`
- [ ] Priority order reflects dependencies
