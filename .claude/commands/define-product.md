---
description: "Interactively define product requirements and tech stack"
---

# Define Product Requirements and Tech Stack

You are guiding the user through defining their product requirements (PRD) and technology choices. This command populates `docs/architecture/PRD.md` and `docs/architecture/TECH_STACK.md` through structured Q&A, then updates `CLAUDE.md` with the results.

## Step 1: Detect Mode (Create vs Update)

Read both files before doing anything else:

- `docs/architecture/PRD.md`
- `docs/architecture/TECH_STACK.md`

**Determine mode for each file independently:**

- If the file contains only HTML comments, stub headers (like `20xx-xx-xx`), or placeholder text with no real project-specific content -- **create mode**.
- If the file contains real project-specific content (actual project name, real features, specific technologies) -- **update mode**.

**If create mode:** Tell the user you will walk them through defining their project from scratch.

**If update mode:** Show a brief summary of what currently exists and ask the user what they want to update. Allow them to skip sections that are already correct.

## Step 2: Gather PRD Information

Ask these questions **one at a time**. Wait for the user's answer before asking the next question. Present each question with context about what you are looking for.

Accept "TBD" as a valid answer for any question -- write it as-is into the doc. Do not push back on TBD answers.

**In update mode:** Show the current value before each question and ask "Keep this or change it?"

**If the user provides $ARGUMENTS**, treat it as the project name and skip Q1.

### Q1: Project Name

```
What is your project called?

This will be used as the title throughout the architecture docs and in CLAUDE.md.
```

### Q2: Target Users

```
Who are the target users?

Describe the primary audience for this product. Examples:
- "Solo developers who want to ship faster"
- "Small business owners managing inventory"
- "Internal engineering teams at mid-size companies"
```

### Q3: Problem Statement

```
What problem does this project solve?

Write 2-4 sentences describing the core problem and why existing solutions fall short.
This becomes the anchor for every product decision.
```

### Q4: Core Features (MVP)

```
What are the core features for the MVP?

List 3-5 features that define the minimum viable product. Be specific about what each
feature does, not just a label.

Example:
1. User authentication with email/password and OAuth (Google)
2. Dashboard showing real-time metrics with 30-second refresh
3. CSV export of historical data with date range filtering
```

### Q5: Non-Goals

```
What will this project NOT do?

List things that are explicitly out of scope. This prevents scope creep.
Example:
- No mobile app (web-only for v1)
- No real-time collaboration (single-user editing only)
- No self-hosted option (SaaS only)
```

### Q6: Success Metrics

```
How will you measure success?

Define 2-4 concrete metrics with numbers or thresholds. Examples:
- "50 beta users within 30 days of launch"
- "Average page load under 2 seconds"
- "80% task completion rate in user testing"
```

## Step 3: Gather Tech Stack Information

After completing the PRD questions, transition:

```
Now let's define the technology stack. I'll suggest popular options for each category,
but you can choose anything. Answer "TBD" for anything you haven't decided yet.
```

Ask these questions **one at a time**, waiting for each answer:

### Q1: Frontend Framework

```
What frontend framework will you use?

Common choices:
- Next.js App Router (React, SSR/SSG, recommended for full-stack)
- Remix (React, nested routing, progressive enhancement)
- Astro (content-focused, multi-framework islands)
- SvelteKit (Svelte, compiled, lightweight)
- Nuxt (Vue-based)
- Plain React SPA (Vite + React Router)
```

### Q2: CSS Approach

```
What CSS/styling approach will you use?

Common choices:
- Tailwind CSS (utility-first, pairs well with shadcn/ui)
- CSS Modules (scoped CSS, zero runtime)
- styled-components (CSS-in-JS, runtime)
- Vanilla Extract (type-safe CSS, zero runtime)
- Plain CSS / SCSS
```

### Q3: Backend Framework

```
What backend framework will you use?

Common choices:
- FastAPI (Python, async, auto-docs, Pydantic validation)
- Express (Node.js, minimal, huge ecosystem)
- Hono (TypeScript, edge-first, lightweight)
- NestJS (TypeScript, opinionated, enterprise patterns)
- Django (Python, batteries-included)
- Next.js API Routes (if frontend is Next.js, no separate backend needed)
```

### Q4: Database

```
What database will you use?

Common choices:
- PostgreSQL + Prisma (relational, type-safe ORM, great migrations)
- PostgreSQL + Drizzle (relational, lighter ORM, SQL-like syntax)
- MongoDB + Mongoose (document store, flexible schema)
- SQLite + Drizzle (embedded, good for prototypes)
- Supabase (PostgreSQL + auth + realtime + storage)
- PlanetScale (MySQL-compatible, serverless, branching)
```

### Q5: Auth Provider

```
What authentication provider will you use?

Common choices:
- Clerk (drop-in UI components, user management, webhooks)
- NextAuth / Auth.js (open source, flexible, self-hosted)
- Auth0 (enterprise-grade, complex setups)
- Supabase Auth (if using Supabase for DB)
- Firebase Auth (Google ecosystem)
- Custom (roll your own with JWT/sessions)
```

### Q6: Hosting and Deployment

```
Where will you host and deploy?

Common choices:
- Vercel (frontend) + Railway (backend/DB)
- Vercel (frontend) + Fly.io (backend/DB)
- AWS (full stack: ECS/Lambda + RDS)
- Render (full stack, simple config)
- Cloudflare Pages + Workers (edge-first)
- Self-hosted (Docker Compose, VPS)
```

### Q7: Key Dependencies

```
Are there other critical libraries or services you know you will need?

Examples: Redis for caching, Stripe for payments, Resend for email, Pinecone for
vector search, S3 for file storage, etc.

Answer "none" or "TBD" if not sure yet.
```

## Step 4: Write PRD.md

After gathering all PRD answers, write `docs/architecture/PRD.md`:

```markdown
# [Project Name] - Product Requirements Document

**Last Updated**: [YYYY-MM-DD]
**Status**: Draft
**Version**: 1.0

## Target Users

[Q2 answer]

## Problem Statement

[Q3 answer]

## Core Features (MVP)

[Q4 answer as a numbered list with descriptions]

## Non-Goals

[Q5 answer as a bulleted list]

## Success Metrics

[Q6 answer as a bulleted list]
```

**In update mode:** Only modify sections the user chose to update. Preserve everything else.

## Step 5: Write TECH_STACK.md

Write `docs/architecture/TECH_STACK.md`:

```markdown
# [Project Name] - Tech Stack

**Last Updated**: [YYYY-MM-DD]
**Status**: Draft
**Version**: 1.0

## Frontend

- **Framework**: [Q1 answer]
- **Styling**: [Q2 answer]

## Backend

- **Framework**: [Q3 answer]
- **Language**: [Inferred from framework, e.g. Python 3.12 for FastAPI, TypeScript for Hono]

## Database

- [Q4 answer]

## Authentication

- [Q5 answer]

## Hosting & Deployment

- [Q6 answer]

## Key Dependencies

[Q7 answer as bulleted list, or "TBD" if none specified]
```

**In update mode:** Only modify sections the user chose to update. Preserve everything else.

## Step 6: Update CLAUDE.md

After writing both architecture docs, update `CLAUDE.md` in the project root:

1. **Update the "WHY -- Project Purpose" section** in CLAUDE.md. Replace the existing purpose description with 2-4 sentences derived from the problem statement and target users. Write a concise summary -- do not copy-paste the PRD verbatim.

2. **Fill in the tech stack bullet points** in the "WHAT -- Tech Stack" section. Remove the `<!-- e.g. ... -->` HTML comment hints when filling in real values:
   - **Frontend:** [framework + styling + TypeScript version if known]
   - **Backend:** [language + framework + key library like Pydantic if relevant]
   - **Database:** [database + ORM if applicable]
   - **Infrastructure:** [hosting choices]

3. **Do NOT modify** any other sections of CLAUDE.md.

## Step 7: Summary and Next Step

After all files are written, present a summary:

```
Done. Here is what was written:

**docs/architecture/PRD.md**
- Project: [name]
- [N] core features defined
- [N] non-goals defined

**docs/architecture/TECH_STACK.md**
- Frontend: [framework + styling]
- Backend: [framework]
- Database: [choice]
- Auth: [choice]
- Hosting: [choice]

**CLAUDE.md** updated with project purpose and tech stack summary.

Recommended next step: Run /define-architecture to define your app flow,
backend structure, frontend guidelines, and CI/CD pipeline.
```

## Behavioral Rules

1. **Ask one question at a time.** Never batch multiple questions into a single message.
2. **Wait for an answer before proceeding.** Do not assume or fill in answers.
3. **Accept "TBD" gracefully.** Write it literally into the docs. Do not ask follow-up questions about TBD answers.
4. **In update mode, show current values.** Let the user confirm or change each field.
5. **Do not invent information.** Only write what the user explicitly told you.
6. **Use exact answers provided.** Do not rephrase or editorialize unless the user asks you to clean up their wording.
