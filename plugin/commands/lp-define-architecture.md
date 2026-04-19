---
name: lp-define-architecture
description: "Interactively define backend structure and CI/CD pipeline"
---
# Define Architecture

You are guiding the user through defining their backend structure and CI/CD pipeline. This command populates two docs through structured Q&A:

- `docs/architecture/BACKEND_STRUCTURE.md`
- `docs/architecture/CI_CD.md`

Every question uses the **guided format**: context explaining WHY the question matters, a dynamically generated options table with "Best When" guidance and examples, a context-aware recommendation based on prior answers, and a TBD escape hatch.

---

## Step 1: Prerequisite Check

Read `docs/architecture/PRD.md` and `docs/architecture/TECH_STACK.md`. Check if they contain real content (not just HTML comments, stub headers like `20xx-xx-xx`, or placeholder text).

**If either file is still a stub**, tell the user:

```
These architecture docs depend on your product requirements and tech stack being defined first.

docs/architecture/PRD.md - [stub / has content]
docs/architecture/TECH_STACK.md - [stub / has content]

Please run /lp-define-product first, then come back to /lp-define-architecture.
```

Then STOP. Do not proceed further.

**Also check** `docs/architecture/APP_FLOW.md` (from `/lp-define-design`):

- If it has real content, load it for context (auth flow, pages/routes, navigation patterns).
- If it is a stub or missing, suggest but do not require:

```
I notice your App Flow hasn't been defined yet. I recommend running
/lp-define-design first so your backend auth strategy can reference your UX auth flow.
Would you like to continue without it, or run /lp-define-design first?
```

If the user wants to continue, proceed without APP_FLOW context.

**Also check** `docs/architecture/DESIGN_SYSTEM.md`:

- If it has real content, load it for context (component library, design philosophy).
- If it is a stub or missing, note it but do not block.

---

## Step 2: Load Context

Extract from loaded files: project name, core features, product sections (from registry), data entities (from Data Shape), frontend framework, backend framework, database choice, auth provider, hosting platform, auth flow (from APP_FLOW.md if available), and design system info (if available).

Present a brief summary to confirm context:

```
I have loaded your project context:

- Project: [name]
- Sections: [list from registry]
- Data Entities: [list from Data Shape]
- Stack: [frontend] + [backend] + [database]
- Auth: [provider]
- Hosting: [platform]
- Auth Flow: [loaded from APP_FLOW.md / not defined yet]
- Design System: [loaded / not defined yet]

I will walk you through two architecture docs with 8 questions total:
Backend Structure (5) and CI/CD (3)
— plus an open-ended catch-all at the end.
```

---

## Step 3: Detect Mode Per File

Read both target files. For each independently:

- If it contains only HTML comments, stub headers, or generic placeholder text — **create mode**.
- If it contains real project-specific content — **update mode**.

Report the status:

```
File status:
- BACKEND_STRUCTURE.md: [create / update] mode
- CI_CD.md: [create / update] mode
```

---

## Step 4: BACKEND_STRUCTURE.md (5 questions)

Tailor all questions to the backend framework and database from TECH_STACK.md.

---

### BE-1: Data Models

WHY: Data models are the foundation of your backend. Getting them right prevents painful migrations later.

```
What are your main data models?

List each entity with key fields, types, and relationships.
```

**Pre-populate from PRD Data Shape:** If PRD.md has a Data Shape section, present it and ask the user to confirm or refine:

```
Your PRD defines these data entities:

[paste Data Shape section from PRD.md]

Let's refine this into concrete data models for [database choice].
For each entity, confirm or adjust:
- Field names and types
- Required vs optional fields
- Relationships (foreign keys, join tables)
- Indexes needed for common queries
```

If PRD has no Data Shape, ask from scratch with examples tailored to the backend/database choice.

---

### BE-2: API Endpoints

WHY: A clear API surface prevents endpoint sprawl, naming inconsistencies, and duplicate functionality.

```
What are the key API endpoints?

Based on [backend framework], list the main [REST routes / GraphQL queries / tRPC procedures].
Focus on important and non-obvious endpoints, not exhaustive CRUD.
```

| Option            | Best When                               | Example                                                            |
| ----------------- | --------------------------------------- | ------------------------------------------------------------------ |
| RESTful resources | Standard CRUD APIs                      | `GET /api/projects`, `POST /api/projects`, `GET /api/projects/:id` |
| GraphQL           | Complex relationships, flexible queries | `query { projects { id, name, tasks { title } } }`                 |
| tRPC procedures   | TypeScript full-stack, type-safe        | `trpc.project.list()`, `trpc.project.create()`                     |
| Server Actions    | Next.js App Router, form-heavy          | `'use server'` functions in React components                       |
| RPC-style         | Simple APIs, internal tools             | `POST /api/rpc/createProject`, `POST /api/rpc/listProjects`        |

**Recommended:** Generate based on backend framework and data models. If Hono/Express → REST. If Next.js only → Server Actions + REST for external API. Pre-populate endpoint list from data models.

---

### BE-3: Auth Strategy

WHY: Auth token flow affects security, session management, and how your frontend communicates with the backend.

```
How do auth tokens flow through the system?
```

| Option                         | Best When                             | Example                                                           |
| ------------------------------ | ------------------------------------- | ----------------------------------------------------------------- |
| httpOnly cookies + session     | Server-rendered apps, secure          | Cookie set on login, validated per request, CSRF protection       |
| JWT in httpOnly cookie         | Stateless, API-first                  | JWT issued on login, stored in cookie, verified middleware        |
| JWT in Authorization header    | Mobile + web API, third-party clients | `Authorization: Bearer <token>`, refresh token rotation           |
| Session tokens (DB-backed)     | Simple, full control                  | Session ID in cookie, looked up in DB per request                 |
| Provider-managed (Clerk/Auth0) | Using managed auth                    | Provider handles tokens, your backend validates with provider SDK |

Ask specifically:

- Where are tokens stored? (httpOnly cookies, localStorage, etc.)
- How does the backend validate requests?
- How are roles/permissions checked?

**Reference APP_FLOW.md:** If APP_FLOW.md has been defined (from `/lp-define-design`), reference the auth flow from AF-1 to align the token strategy with the UX auth flow. For example, if the UX flow uses OAuth + magic links, the backend strategy should support those token types.

**Recommended:** Generate based on auth provider and backend framework from TECH_STACK.

---

### BE-4: External Services

WHY: Documenting external dependencies upfront prevents surprises during implementation and makes it clear what API keys are needed.

```
What third-party APIs or external services will the backend use?

For each, note: what it's used for, how it's integrated, and any rate limits or costs.
```

| Option       | Best When                        | Example                                                       |
| ------------ | -------------------------------- | ------------------------------------------------------------- |
| Payments     | Monetized product                | "Stripe — subscriptions, webhooks for payment events"         |
| Email        | Transactional or marketing email | "Resend — signup verification, password reset, notifications" |
| File storage | User uploads, media              | "S3 / Cloudflare R2 — user avatars, document uploads"         |
| AI / LLM     | AI-powered features              | "OpenAI API — text generation, embeddings for search"         |
| Search       | Full-text search                 | "Typesense / Algolia — instant search across entities"        |
| Monitoring   | Observability                    | "Sentry — error tracking, Axiom — logging"                    |

**Recommended:** Generate based on PRD features and tech stack.

---

### BE-5: Data Volume & Scaling

WHY: Understanding your expected data volume now prevents architectural decisions that don't scale. The difference between 100 users and 100,000 users affects database indexing, caching strategy, and API design.

```
What are your data volume and scaling expectations?
```

| Option                   | Best When                         | Example                                                               |
| ------------------------ | --------------------------------- | --------------------------------------------------------------------- |
| Small (< 1K users)       | MVP, internal tool, prototype     | "Hundreds of users, thousands of records, single DB instance"         |
| Medium (1K - 100K users) | Growing SaaS, established product | "Tens of thousands of users, millions of records, connection pooling" |
| Large (100K+ users)      | Scale-focused product             | "Hundreds of thousands of users, need read replicas, caching layer"   |
| Real-time heavy          | Chat, collaboration, live data    | "Thousands of concurrent connections, WebSockets, pub/sub"            |

Also ask:

- Any particularly hot tables or query patterns?
- Caching strategy needed? (Redis, CDN, in-memory)
- Background jobs? (email sending, report generation, data processing)

**Recommended:** Generate based on target users and product type. Most MVPs → Small. SaaS → Medium with plan for growth.

---

### Write BACKEND_STRUCTURE.md

Write `docs/architecture/BACKEND_STRUCTURE.md` with: header block, then sections for Data Models (formatted for SQL tables or document schemas as appropriate, with Entity Relationship Summary subsection), API Endpoints (grouped logically, each group as a table: Method, Endpoint, Description, Auth), Authentication Strategy (numbered flow), External Services (table: Service, Purpose, Integration Point), Data Volume & Scaling (expectations, caching strategy, background jobs).

In update mode, only modify sections the user chose to change.

---

## Step 4b: Update Harness Context

After writing BACKEND_STRUCTURE.md, update `.harness/harness.local.md` with architecture context:

1. Read `.harness/harness.local.md`
2. Append to the `## Review Context` section:
   - Auth strategy (from A-1)
   - Database patterns (from the data model questions)
   - External integrations mentioned
   - API patterns (REST, GraphQL, etc.)
3. Write the updated file

This enriches the review context that `/lp-review` agents use for architecture-aware findings.

---

## Step 5: CI_CD.md (3 questions)

Tailor questions to the hosting platform from TECH_STACK.md.

---

### CI-1: CI Pipeline

WHY: A CI pipeline catches bugs before they reach production. Defining it upfront prevents "it works on my machine" problems.

```
What CI pipeline will you use?
```

| Option         | Best When                       | Example                                            |
| -------------- | ------------------------------- | -------------------------------------------------- |
| GitHub Actions | GitHub repos, most common       | `.github/workflows/ci.yml`, free for public repos  |
| GitLab CI      | GitLab repos                    | `.gitlab-ci.yml`, built-in container registry      |
| CircleCI       | Complex pipelines, parallelism  | `config.yml`, caching, test splitting              |
| Vercel checks  | Next.js on Vercel, simple needs | Automatic build + preview, no config needed        |
| None yet       | Early stage, will add later     | "TBD — will add CI before first production deploy" |

Also ask: What checks should run on every PR? (lint, typecheck, tests, build, etc.)

**Recommended:** Generate based on hosting platform. Vercel → GitHub Actions + Vercel checks. AWS → GitHub Actions or CircleCI.

---

### CI-2: Deploy Strategy

WHY: A clear deployment strategy prevents "how do I ship this?" confusion and ensures safe rollbacks.

```
What is your deployment strategy?
```

| Option                 | Best When                   | Example                                                 |
| ---------------------- | --------------------------- | ------------------------------------------------------- |
| Git push to deploy     | Simple apps, Vercel/Netlify | Push to main → automatic deploy                         |
| Preview deploys per PR | Team collaboration          | Every PR gets a unique preview URL                      |
| Staging → Production   | Safety-critical apps        | PR → staging auto-deploy → manual promote to production |
| Blue-green deployment  | Zero-downtime required      | Two identical environments, swap on deploy              |
| Canary releases        | High-traffic apps           | Roll out to 5% of users first, then 100%                |

**Recommended:** Generate based on hosting platform. Vercel → Git push + preview deploys. AWS → Staging → production.

---

### CI-3: Environments

WHY: Clear environment boundaries prevent "why is staging data showing in production?" disasters.

```
What environments do you need?
```

| Option                               | Best When                   | Example                                   |
| ------------------------------------ | --------------------------- | ----------------------------------------- |
| Dev + Production                     | Simple apps, solo developer | Local dev, push to production             |
| Dev + Preview + Production           | Team development            | Local, per-PR previews, production        |
| Dev + Staging + Production           | Safety-critical             | Local, staging (mirrors prod), production |
| Dev + Preview + Staging + Production | Enterprise                  | Full pipeline with gates                  |

For each environment, note: separate databases? Feature flags? API keys? Domain?

**Recommended:** Generate based on team size and product stage. Solo → Dev + Production. Team → Dev + Preview + Production.

---

### Write CI_CD.md

Write `docs/architecture/CI_CD.md` with: header block, then sections for CI Pipeline (Provider, PR Checks as checklist, Pipeline Configuration), Deployment Strategy (Flow as numbered steps from PR to production, Rollback subsection), Environments (table: Environment, URL, Database, Notes).

In update mode, only modify sections the user chose to change.

---

## Step 6: Open-Ended Catch-All

After both files' questions are complete, ask:

```
Is there anything about your backend architecture or CI/CD that we haven't covered?
Any constraints, performance requirements, security considerations, or infrastructure preferences?

If not, just say "No, we're good" and I'll finalize the output files.
```

**No options table** — purely open-ended.

**CRITICAL behavior:** Parse the response and integrate into the appropriate architecture doc section. Do NOT create a separate "Other Notes" section. Examples:

- "We need WebSocket support" → add to BACKEND_STRUCTURE.md
- "GDPR compliance required" → add to BACKEND_STRUCTURE.md data handling section

---

## Step 7: Update README.md

After both architecture docs are written, read the current `README.md` and enrich it with architecture details. **Do not rewrite the whole file** — add to or update what `/lp-define-product` and `/lp-define-design` already wrote.

**Add or update these sections (after the Tech Stack table, before Development):**

```markdown
## Architecture

- **API:** [Backend framework] with [count] endpoint groups — [list 2-3 key groups, e.g. auth, projects, tasks]
- **Data:** [Count] core models — [list model names from BACKEND_STRUCTURE.md]
- **Deploy:** [Hosting platform] — [1-line deploy flow summary from CI_CD.md]
```

**Rules for this step:**

- Keep it concise — 3-4 bullet points max. The architecture docs have the full detail.
- Use the user's exact answers — do not embellish.
- If any section was skipped or all TBD, omit the corresponding bullet.
- Do not remove or modify any existing sections (Features, Tech Stack, Development, License).

---

## Step 8: Summary and Next Step

After all files are written and README is updated, summarize what was created for each file (key highlights and counts). Then suggest:

```
Your backend architecture and CI/CD docs are now defined.
README.md updated with architecture overview.

Next steps:
- Shape each product section: /lp-shape-section [section-name]
- Fill in any TBDs: /lp-update-spec
- When sections are shaped, plan implementation: /lp-pnf [section-name]
```

---

## Behavioral Rules

1. **Ask one question at a time.** Never batch multiple questions into a single message.
2. **Wait for each answer.** Do not assume or fill in answers.
3. **Accept "TBD" gracefully.** Write it literally into the docs. Do not push for decisions.
4. **Tailor suggestions to the tech stack.** Use PRD.md, TECH_STACK.md, and APP_FLOW.md for relevant, specific suggestions rather than generic lists.
5. **In update mode, show current values.** Let the user confirm or change each field.
6. **Do not invent information.** Only write what the user explicitly told you.
7. **Use exact answers.** Do not rephrase or editorialize unless asked.
8. **Handle files in order:** BACKEND_STRUCTURE, CI_CD.
9. **Allow skipping.** If the user wants to skip a file, accept it, write "TBD" for all its sections, and move on.
10. **If $ARGUMENTS is provided**, treat it as a signal about which file to prioritize (e.g. `/lp-define-architecture backend` focuses on BACKEND_STRUCTURE first). Still offer both files.
11. **Generate guided format dynamically.** Options tables and recommendations must reference prior answers and loaded context.
12. **Pre-populate from PRD Data Shape.** Backend data models should start from the entities already defined in PRD.md.
13. **Reference APP_FLOW.md auth flow when asking BE-3.** Align the backend token strategy with the UX auth flow defined in `/lp-define-design`.
14. **Integrate open-ended answers.** Parse the catch-all response and place information in the appropriate architecture doc sections.
