# BACKLOG

> Central backlog for deferred and active work. Populated by developers and AI agents as the project evolves.

---

## How to Use This File

### Adding a new task

Copy the Standard Task Format below into the correct priority section. Required fields:
`Task ID`, `Priority`, `Status`, `Area`, `Date`, `Location`, `Current Behavior`, `Desired Behavior`.

Task IDs are sequential integers zero-padded to three digits: `BL-001`, `BL-002`, etc.

### Marking a task complete

Remove the task entry from this file and append a one-line summary to `docs/tasks/PROGRESS.md`:

```
COMPLETED BL-XXX - Short title (YYYY-MM-DD)
```

### Priority levels

| Level | Label    | Meaning                                      |
| ----- | -------- | -------------------------------------------- |
| P0    | Critical | Blocks MVP or fixes a live defect — do first |
| P1    | High     | Important for the near-term roadmap          |
| P2    | Medium   | Good to have in the next phase               |
| P3    | Low      | Cleanup, refactor, polish                    |

### Status values

| Value       | Meaning                               |
| ----------- | ------------------------------------- |
| TODO        | Not started                           |
| NEXT        | Candidate for the upcoming sprint     |
| IN_PROGRESS | Currently being worked on             |
| BLOCKED     | Waiting on another task or dependency |

### Referencing related work

Use `Blocked By` for task dependencies. Link PRs, issues, and related files in the `Notes` field.

---

## AI Agent Instructions

At session start, summarize all P0 tasks then all P1 tasks. For each show: Task ID, title, Area, Status. Then ask the user which task (if any) to focus on.

During a session, when a new task emerges that is separate from current work: recognize it, ask the user whether to capture it, add a minimal entry using the format below, then return to the current task.

When implementing a task: always revalidate whether the proposed fix still makes sense before applying it. The codebase may have changed since the task was written.

---

## Legend

**Area** (customize for your project — these are common starting points):

- `Frontend` - Web app (Next.js)
- `Backend` - API service
- `DB` - Database schema, migrations
- `Auth` - Authentication, authorization
- `Infra` - Deployment, CI/CD, infrastructure
- `Testing` - Test infrastructure, QA
- `Docs` - Documentation

---

## Standard Task Format

```markdown
#### BL-XXX - Short, descriptive title

- **Priority**: P0 | P1 | P2 | P3
- **Status**: TODO | NEXT | IN_PROGRESS | BLOCKED
- **Area**: Frontend | Backend | DB | Auth | Infra | Testing | Docs
- **Blocked By**: BL-YYY (only if Status is BLOCKED)

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: file path, module, route, or command where the issue was found
- **Scenario**: Brief description of what was being done when this was discovered

**Current Behavior**

Short description of what is happening right now.

**Desired Behavior**

Short description of what is wanted instead.

**Proposed Fix** (revalidate before implementing)

Outline the fix that seemed correct when this task was created.
Future implementers must verify this is still the best approach.

**Notes**

Extra context, links to PRs, issues, logs, or external docs.
```

---

## Backlog

### P0 - Critical

<!-- EXAMPLE (delete when adding real tasks):
#### BL-001 - Example: Fix authentication middleware crash on expired tokens

- **Priority**: P0
- **Status**: TODO
- **Area**: Auth

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `apps/api/src/middleware/auth.ts`
- **Scenario**: During manual QA, a request with an expired JWT caused a 500 instead of a 401.

**Current Behavior**

Expired JWT throws an unhandled exception and returns HTTP 500.

**Desired Behavior**

Expired JWT is caught, returns HTTP 401 with a clear error message.

**Proposed Fix** (revalidate before implementing)

Wrap the `jwt.verify()` call in a try/catch and return a 401 response on `TokenExpiredError`.

**Notes**

Related issue: #12.
-->

---

### P1 - High

<!-- EXAMPLE (delete when adding real tasks):
#### BL-002 - Example: Add database index on users.email for login performance

- **Priority**: P1
- **Status**: TODO
- **Area**: DB

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `packages/db/prisma/schema.prisma`, `User` model
- **Scenario**: Load testing showed login queries taking 200ms+ on a table with 10k rows.

**Current Behavior**

No index on `users.email`; every login triggers a full table scan.

**Desired Behavior**

Login queries run in under 10ms with a unique index on `users.email`.

**Proposed Fix** (revalidate before implementing)

Add `@@index([email])` (or `@unique`) to the `User` model in `packages/db/prisma/schema.prisma` and generate a migration.

**Notes**

Follow the migration protocol in `docs/operations/PRISMA_MIGRATION_GUIDE.md`.
-->

---

### P2 - Medium

<!-- EXAMPLE (delete when adding real tasks):
#### BL-003 - Example: Add pagination to the /api/items list endpoint

- **Priority**: P2
- **Status**: TODO
- **Area**: Backend

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `apps/api/src/routes/items.ts`
- **Scenario**: As the items table grows the endpoint response time increases noticeably.

**Current Behavior**

`GET /api/items` returns all rows with no limit.

**Desired Behavior**

Endpoint accepts `page` and `pageSize` query params; defaults to page 1, size 20.

**Proposed Fix** (revalidate before implementing)

Add Prisma `skip`/`take` and return a `{ data, total, page, pageSize }` envelope.

**Notes**

Frontend will need a corresponding update to consume the paginated response.
-->

---

### P3 - Low

<!-- EXAMPLE (delete when adding real tasks):
#### BL-004 - Example: Standardize error response shape across all API routes

- **Priority**: P3
- **Status**: TODO
- **Area**: Backend

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `apps/api/src/` — multiple route files
- **Scenario**: Code review revealed inconsistent error shapes: some return `{ error }`, others return `{ message }`.

**Current Behavior**

Error responses have inconsistent field names across routes.

**Desired Behavior**

All error responses use `{ error: { code, message } }`.

**Proposed Fix** (revalidate before implementing)

Create a shared `errorResponse()` helper in `packages/shared/src/utils/` and replace inline error objects.

**Notes**

Low risk; pure refactor with no functional change.
-->
