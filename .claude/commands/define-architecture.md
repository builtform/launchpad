---
description: "Interactively define app architecture, backend structure, frontend guidelines, and CI/CD"
---

# Define Architecture

You are guiding the user through defining their application architecture. This command populates four docs through structured Q&A:

- `docs/architecture/APP_FLOW.md`
- `docs/architecture/BACKEND_STRUCTURE.md`
- `docs/architecture/FRONTEND_GUIDELINES.md`
- `docs/architecture/CI_CD.md`

## Step 1: Prerequisite Check

Read `docs/architecture/PRD.md` and `docs/architecture/TECH_STACK.md`. Check if they contain real content (not just HTML comments, stub headers like `20xx-xx-xx`, or placeholder text).

**If either file is still a stub**, tell the user:

```
These architecture docs depend on your product requirements and tech stack being defined first.

docs/architecture/PRD.md - [stub / has content]
docs/architecture/TECH_STACK.md - [stub / has content]

Please run /define-product first, then come back to /define-architecture.
```

Then STOP. Do not proceed further.

## Step 2: Load Context

If both files have real content, extract: project name, core features, frontend framework, backend framework, database choice, auth provider, and hosting platform.

Present a brief summary to confirm context:

```
I have loaded your project context:

- Project: [name]
- Features: [brief list]
- Stack: [frontend] + [backend] + [database]
- Auth: [provider]
- Hosting: [platform]

I will walk you through four architecture docs: App Flow, Backend Structure,
Frontend Guidelines, and CI/CD.
```

## Step 3: Detect Mode Per File

Read all four target files. For each independently:

- If it contains only HTML comments, stub headers, or generic placeholder text -- **create mode**.
- If it contains real project-specific content -- **update mode**.

Report the status:

```
File status:
- APP_FLOW.md: [create / update] mode
- BACKEND_STRUCTURE.md: [create / update] mode
- FRONTEND_GUIDELINES.md: [create / update] mode
- CI_CD.md: [create / update] mode
```

## Step 4: APP_FLOW.md

Introduce the section, then ask these questions **one at a time**, waiting for each answer. Accept "TBD" for any question. In update mode, show the current value and ask "Keep this or change it?"

### Q1: Auth Flow

```
How should authentication work in your app?

Describe the login, signup, and password reset flows.
Based on your choice of [auth provider], common patterns include:
[Provide 2-3 specific suggestions tailored to their auth provider]

What does your auth flow look like?
```

### Q2: Main User Journey

```
What is the primary user journey after logging in?

Walk me through the main workflow step by step. Your MVP features are:
[List core features from PRD.md]

Example:
1. User lands on dashboard showing [summary data]
2. User clicks "New [thing]" to start the workflow
3. User fills out [form] with [key fields]
4. System processes and shows [result]
5. User can [export/share/save] the result
```

### Q3: Pages and Routes

```
What are the main pages/routes?

List each with its path and a one-line description.
Example:
- / - Landing page (unauthenticated)
- /dashboard - Main view after login
- /projects/:id - Project detail
- /settings - User preferences
```

### Q4: Navigation Pattern

```
What navigation pattern will you use?

Options: top navbar + sidebar, top navbar only, sidebar only, bottom tabs, minimal.
What goes in the nav? Does it collapse on mobile? Breadcrumbs?
```

### Q5: Error States

```
How should errors be handled?

Cover: 404, 500, network offline, unauthorized (expired session), and empty states.
Example: "Friendly error pages with retry buttons, redirect to login on 401,
skeleton loaders for empty states."
```

### Write APP_FLOW.md

Write `docs/architecture/APP_FLOW.md` with: header (project name, date, Draft status, version 1.0), then sections for Authentication Flow (numbered steps), Main User Journey (numbered steps), Pages and Routes (table: Route, Page, Description, Auth Required), Navigation (description), Error Handling (table: Scenario, Behavior for each error type).

In update mode, only modify sections the user chose to change.

## Step 5: BACKEND_STRUCTURE.md

Tailor all questions to the backend framework and database from TECH_STACK.md.

### Q1: Data Models

```
What are your main data models?

List each entity with key fields and relationships.
Think in terms of [tables/collections] based on your [database] choice.

Example:
- User: id, email, name, role, created_at
- Project: id, name, description, owner_id (-> User), created_at
- Task: id, title, status, project_id (-> Project), assignee_id (-> User)
```

### Q2: API Endpoints

```
What are the key API endpoints?

Based on [backend framework], list the main [REST routes / GraphQL queries / tRPC procedures].
Focus on important and non-obvious endpoints, not exhaustive CRUD.

Example (REST):
- POST /api/auth/login - Authenticate user
- GET /api/projects - List user's projects
- POST /api/projects - Create new project
- GET /api/projects/:id - Get project details
```

### Q3: Auth Strategy

```
How do auth tokens flow through the system?

- Where are tokens stored? (httpOnly cookies, localStorage, etc.)
- How does the backend validate requests? (JWT verification, session lookup, etc.)
- How are roles/permissions checked?

Based on [auth provider] + [backend framework], a common pattern is:
[Suggest a specific approach for their stack]
```

### Q4: External Services

```
What third-party APIs or external services will the backend use?

Examples: Stripe (payments), Resend (email), S3 (storage), OpenAI (AI), etc.
For each, briefly note what it is used for. Answer "none" or "TBD" if not applicable.
```

### Write BACKEND_STRUCTURE.md

Write `docs/architecture/BACKEND_STRUCTURE.md` with: header block, then sections for Data Models (formatted for SQL tables or document schemas as appropriate, with Entity Relationship Summary subsection), API Endpoints (grouped logically, each group as a table: Method, Endpoint, Description, Auth), Authentication Strategy (numbered flow), External Services (table: Service, Purpose, Integration Point).

In update mode, only modify sections the user chose to change.

## Step 6: FRONTEND_GUIDELINES.md

Tailor questions to the frontend framework and CSS approach from TECH_STACK.md.

### Q1: Design System

```
What design system or component library will you use?

Common choices for [framework]:
- shadcn/ui (Tailwind-based, copy-paste, customizable)
- Radix UI (unstyled primitives)
- Material UI (Google Material Design)
- Chakra UI (accessible, themeable)
- Custom from scratch

Also note any design preferences: colors, fonts, spacing. Answer "TBD" for undecided parts.
```

### Q2: Component Architecture

```
How should components be organized?

Patterns:
- Feature-based (components/dashboard/, components/auth/)
- Atomic design (atoms, molecules, organisms)
- Hybrid (shared/ui for generic + feature folders for specific)
- Flat (single directory, clear naming)

Any naming conventions? (PascalCase files, barrel exports, co-located tests)
```

### Q3: State Management

```
What state management approach?

Options for [framework]:
- React state + Context (simple apps)
- Zustand (lightweight)
- Jotai (atomic)
- Redux Toolkit (complex state)
- TanStack Query / SWR (server state)

Most apps combine server state (TanStack Query) + local state (Zustand/React).
What is your preference?
```

### Q4: Responsive Strategy

```
What is your responsive design strategy?

- Mobile-first or desktop-first?
- Breakpoints? (e.g. Tailwind defaults: sm 640, md 768, lg 1024, xl 1280)
- Minimum supported width?
- Tablet-specific layouts needed?
- Mobile-specific behavior? (bottom sheets, swipe gestures)
```

### Write FRONTEND_GUIDELINES.md

Write `docs/architecture/FRONTEND_GUIDELINES.md` with: header block, then sections for Design System (library and preferences), Component Architecture (with Directory Structure code block showing example tree and Naming Conventions subsection), State Management (with Server State, Client State, URL State subsections), Responsive Design (bullet points: approach, breakpoints, minimum width, plus additional notes).

In update mode, only modify sections the user chose to change.

## Step 7: CI_CD.md

Tailor questions to the hosting platform from TECH_STACK.md.

### Q1: CI Pipeline

```
What CI pipeline will you use?

Options: GitHub Actions, GitLab CI, CircleCI, none yet.
What checks should run on every PR? (lint, typecheck, tests, build, etc.)
```

### Q2: Deploy Strategy

```
What is your deployment strategy?

Based on [hosting platform], common patterns include:
[Suggest 2-3 specific options for their hosting choice]

Describe the ideal flow from PR to production: preview deploys, staging, approval gates?
```

### Q3: Environments

```
What environments do you need?

Common: dev (local), preview (per-PR), staging (pre-prod), production.
For each, note differences: separate databases, feature flags, API keys, etc.
```

### Write CI_CD.md

Write `docs/architecture/CI_CD.md` with: header block, then sections for CI Pipeline (Provider, PR Checks as checklist, Pipeline Configuration), Deployment Strategy (Flow as numbered steps from PR to production, Rollback subsection), Environments (table: Environment, URL, Database, Notes).

In update mode, only modify sections the user chose to change.

## Step 8: Update README.md

After all four architecture docs are written, read the current `README.md` and enrich it with architecture details. **Do not rewrite the whole file** — add to or update what `/define-product` already wrote.

**Add or update these sections (after the Tech Stack table, before Development):**

```markdown
## Architecture

- **Pages:** [Count] routes — [list 3-5 key routes from APP_FLOW.md, e.g. `/dashboard`, `/projects/:id`, `/settings`]
- **API:** [Backend framework] with [count] endpoint groups — [list 2-3 key groups, e.g. auth, projects, tasks]
- **Data:** [Count] core models — [list model names from BACKEND_STRUCTURE.md]
- **Deploy:** [Hosting platform] — [1-line deploy flow summary from CI_CD.md]
```

**Rules for this step:**

- Keep it concise — 4-6 bullet points max. The architecture docs have the full detail.
- Use the user's exact answers — do not embellish.
- If any section was skipped or all TBD, omit the corresponding bullet.
- Do not remove or modify any existing sections (Features, Tech Stack, Development, License).

## Step 9: Summary and Next Step

After all four files are written and README is updated, summarize what was created for each file (key highlights and counts). Then suggest:

```
Your architecture docs are now defined.
README.md updated with architecture overview.

To start building, run:
  /create_plan [feature name]
to create an implementation plan for your first feature.
```

## Behavioral Rules

1. **Ask one question at a time.** Never batch multiple questions into a single message.
2. **Wait for each answer.** Do not assume or fill in answers.
3. **Accept "TBD" gracefully.** Write it literally into the docs. Do not push for decisions.
4. **Tailor suggestions to the tech stack.** Use PRD.md and TECH_STACK.md for relevant, specific suggestions rather than generic lists.
5. **In update mode, show current values.** Let the user confirm or change each field.
6. **Do not invent information.** Only write what the user explicitly told you.
7. **Use exact answers.** Do not rephrase or editorialize unless asked.
8. **Handle files in order:** APP_FLOW, BACKEND_STRUCTURE, FRONTEND_GUIDELINES, CI_CD.
9. **Allow skipping.** If the user wants to skip a file, accept it, write "TBD" for all its sections, and move on.
10. **If $ARGUMENTS is provided**, treat it as a signal about which file to prioritize (e.g. `/define-architecture backend` focuses on BACKEND_STRUCTURE first). Still offer all four files.
