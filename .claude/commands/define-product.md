---
description: "Interactively define product requirements and tech stack"
---

# Define Product Requirements and Tech Stack

You are guiding the user through defining their product requirements (PRD) and technology choices. This command populates `docs/architecture/PRD.md` and `docs/architecture/TECH_STACK.md` through structured Q&A, then updates `CLAUDE.md` and `README.md` with the results.

Every question uses the **guided format**: context explaining WHY the question matters, a dynamically generated options table with "Best When" guidance and examples, a context-aware recommendation based on prior answers, and a TBD escape hatch.

---

## Step 1: Detect Mode (Create vs Update)

Read both files before doing anything else:

- `docs/architecture/PRD.md`
- `docs/architecture/TECH_STACK.md`

**Determine mode for each file independently:**

- If the file contains only HTML comments, stub headers (like `20xx-xx-xx`), or placeholder text with no real project-specific content — **create mode**.
- If the file contains real project-specific content (actual project name, real features, specific technologies) — **update mode**.

**If create mode:** Tell the user you will walk them through defining their project from scratch. Mention there are 15 questions organized in 4 groups: Vision, Roadmap, Data Shape, and Tech Stack — plus a success metrics question and an open-ended catch-all at the end.

**If update mode:** Show a brief summary of what currently exists and ask the user what they want to update. Allow them to skip sections that are already correct.

---

## Step 2: Gather Product Information

Ask these questions **one at a time**. Wait for the user's answer before asking the next question.

Accept "TBD" as a valid answer for any question — write it as-is into the doc. Do not push back on TBD answers.

**In update mode:** Show the current value before each question and ask "Keep this or change it?"

**If the user provides $ARGUMENTS**, treat it as the project name and skip V-1.

**IMPORTANT — Guided Format:** For every question below, you MUST dynamically generate:

1. A brief explanation of WHY this question matters (1-2 sentences)
2. The question itself
3. An options table with columns: Option | Best When | Example
4. A **Recommended** pick with reasoning that references the user's previous answers
5. A note: **If unsure:** Answer "TBD" — you can fill this in later with `/update-spec`.

The options tables shown below are starting points. Adapt them based on what you learn from prior answers. Add or remove options as appropriate. The recommendation MUST reference prior answers (e.g., "Since you're building for developers and chose React, I'd recommend...").

---

### Group 1 — Product Vision

#### V-1: Project Name

WHY: This name appears in every architecture doc, CLAUDE.md, and README.md. Pick something clear.

```
What is your project called?
```

This is the one question that does NOT need an options table — it is always a free-text answer.

---

#### V-2: Problem & Competitive Gap

WHY: This is the anchor for every product decision. A clear problem statement prevents scope creep and helps AI agents understand what "done" looks like.

```
What problem does this project solve, and why do existing solutions fall short?

Write 2-4 sentences describing the core problem and the gap in current solutions.
```

| Option                              | Best When                                      | Example                                                                                     |
| ----------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Existing tools are too complex      | Users are overwhelmed by feature-bloated tools | "Project managers waste hours in Jira's complex UI when they just need a simple task board" |
| No good solution exists             | You're creating a new category                 | "There's no tool that combines AI code review with deployment automation"                   |
| Current solutions are too expensive | Pricing is a key differentiator                | "Enterprise analytics tools cost $50k+/yr, pricing out small teams"                         |
| Existing tools lack integration     | Your value is connecting things                | "Designers use Figma, devs use GitHub, but there's no bridge between design specs and code" |

**Recommended:** Generate dynamically based on V-1 context.

---

#### V-3: Target Users

WHY: User type drives every UX decision — developer tools need different patterns than consumer apps.

```
Who are the primary users of this product?
```

| Option         | Best When                          | Example                                                          |
| -------------- | ---------------------------------- | ---------------------------------------------------------------- |
| Developers     | Building dev tools, CLIs, APIs     | "Full-stack developers who ship side projects"                   |
| Business users | SaaS for non-technical teams       | "Marketing managers tracking campaign ROI"                       |
| Consumers      | B2C product                        | "People who want to track their fitness goals"                   |
| Internal teams | Internal tooling                   | "Our support team handling customer tickets"                     |
| Mixed          | Platform serving multiple personas | "Both restaurant owners (manage menu) and diners (browse/order)" |

**Recommended:** Generate dynamically based on V-2 problem statement.

---

### Group 2 — Product Roadmap

#### R-1: Product Sections

WHY: This creates the **section registry** — a living table in PRD.md that tracks every major area of your product through definition, shaping, planning, and implementation. Each section can later be deep-dived with `/shape-section`.

```
What are the major sections or areas of your product?

List every distinct section a user would interact with. Think of these as the top-level
areas in your navigation or the major screens/pages of your product.
```

| Option                  | Best When                              | Example                                               |
| ----------------------- | -------------------------------------- | ----------------------------------------------------- |
| Auth section            | Almost every app needs this            | "Sign up, log in, password reset, OAuth"              |
| Dashboard / Home        | Product has a main overview view       | "Metrics overview, recent activity, quick actions"    |
| Core feature section(s) | The primary thing users DO in your app | "Editor", "Kanban board", "Chat", "Feed"              |
| Settings / Profile      | Users need to configure preferences    | "Account settings, notification preferences, billing" |
| Admin / Management      | Multi-tenant or role-based access      | "User management, role assignment, audit logs"        |
| Landing / Marketing     | Public-facing pages                    | "Homepage, pricing, about, blog"                      |

**Recommended:** Generate dynamically. Suggest sections based on V-2 (problem) and V-3 (users). For example, if the user is building a project management tool, suggest: Auth, Dashboard, Projects, Tasks, Team, Settings.

**IMPORTANT — Section name normalization:** When recording sections, normalize all names to **kebab-case** (e.g., "User Auth" becomes `user-auth`, "Dashboard Settings" becomes `dashboard-settings`). This kebab-case ID will be used consistently in filenames, registry entries, and command arguments.

---

#### R-2: MVP Scope

WHY: Not everything needs to ship in v1. Marking sections as MVP vs Post-MVP prevents scope creep and focuses implementation on what matters most.

```
Which of those sections are in the MVP?

For each section you listed, mark it as:
- MVP — must ship in v1
- Post-MVP — planned but not for initial release
- Not planned — out of scope for now
```

Present the user's R-1 sections as a list and ask them to categorize each one. Generate a recommendation for each section based on dependency patterns (e.g., "Auth is almost always MVP because other sections depend on it").

---

#### R-3: Non-Goals

WHY: Explicit non-goals prevent scope creep and help AI agents avoid building things you don't want.

```
What will this project NOT do?

List things that are explicitly out of scope. Be specific.
```

| Option                  | Best When                      | Example                                                 |
| ----------------------- | ------------------------------ | ------------------------------------------------------- |
| Platform limitation     | Focusing on one platform first | "No mobile app — web-only for v1"                       |
| Feature boundary        | Avoiding complexity            | "No real-time collaboration — single-user editing only" |
| Business model boundary | Keeping scope tight            | "No marketplace — we sell direct only"                  |
| Integration boundary    | Avoiding dependency sprawl     | "No third-party plugin system — built-in features only" |
| Scale boundary          | Optimizing for current stage   | "No multi-tenant — single-tenant for v1"                |

**Recommended:** Generate based on R-1 sections and R-2 MVP choices. Sections marked "Not planned" should be suggested as non-goals.

---

### Group 3 — Data Shape

#### D-1: Data Entities & Relationships

WHY: Understanding your data model early prevents architectural dead-ends. This shapes database choice, API design, and backend structure. The entities you define here will be referenced in `/shape-section` and `/define-architecture`.

```
What are the main data entities in your product, and how do they relate?

For each entity, list 3-5 key fields. Then describe the relationships between them
(belongs-to, has-many, many-to-many).
```

| Option                       | Best When                  | Example                                                                        |
| ---------------------------- | -------------------------- | ------------------------------------------------------------------------------ |
| Simple CRUD entities         | Basic data management app  | "User (email, name, role), Post (title, body, status), Comment (text, author)" |
| Hierarchical entities        | Tree-structured data       | "Organization → Team → Member, with role-based permissions at each level"      |
| Event/timeline entities      | Activity tracking, logging | "Event (type, timestamp, actor, payload), Stream (name, filters)"              |
| Relational with many-to-many | Complex relationships      | "Student ↔ Course (enrollment), Course ↔ Instructor (assignment)"              |
| Document-style entities      | Flexible/nested data       | "Form (schema, fields[]), Submission (form_id, answers{})"                     |

**Recommended:** Generate based on R-1 sections. For each section, suggest the entities it likely needs. For example, if sections include "projects" and "tasks", suggest: User, Project (name, description, status), Task (title, assignee, priority, due_date), with Project has-many Tasks, User has-many Tasks.

---

### Group 4 — Tech Stack

Transition message:

```
Now let's define the technology stack. I'll suggest options with context-aware
recommendations based on your product shape. Answer "TBD" for anything you haven't
decided yet.
```

#### TS-1: Frontend Framework

WHY: Your frontend framework determines your development patterns, deployment options, and available component libraries.

```
What frontend framework will you use?
```

| Option                 | Best When                                | Example                       |
| ---------------------- | ---------------------------------------- | ----------------------------- |
| Next.js App Router     | Full-stack React, SSR/SSG, API routes    | Most common for SaaS products |
| Remix                  | Progressive enhancement, nested routing  | Good for content-heavy apps   |
| Astro                  | Content-focused, multi-framework islands | Blogs, marketing sites, docs  |
| SvelteKit              | Compiled, lightweight, great DX          | Performance-critical apps     |
| Nuxt                   | Vue ecosystem                            | Teams with Vue experience     |
| Plain React SPA (Vite) | Client-side only, no SSR needed          | Internal tools, dashboards    |

**Recommended:** Generate based on V-3 (users) and D-1 (data complexity). For developer tools, lean toward Next.js or SvelteKit. For content sites, suggest Astro. For complex data apps, suggest Next.js App Router.

---

#### TS-2: CSS / Styling Approach

WHY: Styling approach affects build performance, developer experience, and component library compatibility.

```
What CSS/styling approach will you use?
```

| Option            | Best When                               | Example                            |
| ----------------- | --------------------------------------- | ---------------------------------- |
| Tailwind CSS      | Rapid prototyping, pairs with shadcn/ui | Most popular for new projects      |
| CSS Modules       | Scoped CSS, zero runtime overhead       | Performance-critical apps          |
| styled-components | CSS-in-JS, dynamic theming              | Apps with heavy runtime theming    |
| Vanilla Extract   | Type-safe CSS, zero runtime             | Large codebases with strict typing |
| Plain CSS / SCSS  | Simple projects, no build tooling       | Small projects or legacy stacks    |

**Recommended:** Generate based on TS-1. If Next.js → recommend Tailwind CSS. If Astro → recommend Tailwind or plain CSS.

---

#### TS-3: Backend Framework

WHY: Your backend handles data persistence, business logic, and API design.

```
What backend framework will you use?
```

| Option                              | Best When                                    | Example                             |
| ----------------------------------- | -------------------------------------------- | ----------------------------------- |
| Next.js API Routes / Server Actions | Frontend is Next.js, simple API needs        | No separate backend needed          |
| Hono                                | TypeScript, edge-first, lightweight          | Microservices, edge deployments     |
| Express                             | Node.js, minimal, huge ecosystem             | When you need max flexibility       |
| NestJS                              | TypeScript, opinionated, enterprise patterns | Large teams, complex domains        |
| FastAPI                             | Python, async, auto-docs, Pydantic           | ML/AI backends, data-heavy APIs     |
| Django                              | Python, batteries-included                   | Rapid prototyping, admin interfaces |

**Recommended:** Generate based on TS-1 and D-1. If Next.js frontend with simple data → suggest Next.js API Routes. If complex entities with many relationships → suggest a dedicated backend like Hono or FastAPI.

---

#### TS-4: Database

WHY: Database choice affects data integrity, query patterns, scaling, and ORM options.

```
What database will you use?
```

| Option               | Best When                                          | Example                               |
| -------------------- | -------------------------------------------------- | ------------------------------------- |
| PostgreSQL + Prisma  | Relational data, type-safe ORM, great migrations   | Most SaaS products                    |
| PostgreSQL + Drizzle | Relational, lighter ORM, SQL-like syntax           | When you want more SQL control        |
| Supabase             | PostgreSQL + auth + realtime + storage, all-in-one | Rapid prototyping with real-time      |
| MongoDB + Mongoose   | Document store, flexible schema                    | Unstructured or rapidly changing data |
| SQLite + Drizzle     | Embedded, single-file, zero config                 | Prototypes, local-first apps          |
| PlanetScale          | MySQL-compatible, serverless, branching            | Serverless deployments                |

**Recommended:** Generate based on D-1 (entities and relationships). Many relationships → PostgreSQL. Flexible/nested data → MongoDB. Simple prototype → SQLite.

---

#### TS-5: Auth Provider

WHY: Authentication is security-critical. Choosing the right provider saves weeks of implementation and avoids security pitfalls.

```
What authentication provider will you use?
```

| Option                | Best When                                        | Example                             |
| --------------------- | ------------------------------------------------ | ----------------------------------- |
| Clerk                 | Drop-in UI components, user management, webhooks | Fastest to implement                |
| NextAuth / Auth.js    | Open source, flexible, self-hosted               | When you need full control          |
| Supabase Auth         | Already using Supabase for DB                    | All-in-one Supabase stack           |
| Auth0                 | Enterprise-grade, complex auth flows             | B2B with SSO/SAML requirements      |
| Firebase Auth         | Google ecosystem, mobile + web                   | Cross-platform apps                 |
| Custom (JWT/sessions) | Full control, no vendor lock-in                  | When you have specific requirements |

**Recommended:** Generate based on TS-1 and TS-4. If Next.js + Supabase → suggest Supabase Auth. If Next.js + PostgreSQL → suggest Clerk or NextAuth.

---

#### TS-6: Hosting & Deployment

WHY: Hosting affects cost, performance, scaling, and deployment complexity.

```
Where will you host and deploy?
```

| Option                     | Best When                                    | Example                     |
| -------------------------- | -------------------------------------------- | --------------------------- |
| Vercel + Railway           | Next.js frontend + separate backend/DB       | Most common modern stack    |
| Vercel + Fly.io            | Next.js + globally distributed backend       | Low-latency worldwide       |
| Vercel only                | Next.js with API routes, no separate backend | Simplest deployment         |
| AWS (ECS/Lambda + RDS)     | Full control, enterprise requirements        | When you need AWS ecosystem |
| Render                     | Full stack, simple config, fair pricing      | Simpler alternative to AWS  |
| Cloudflare Pages + Workers | Edge-first, globally distributed             | Performance-critical apps   |

**Recommended:** Generate based on TS-1 and TS-3. If Next.js with API routes → suggest Vercel only. If separate backend → suggest Vercel + Railway or Fly.io.

---

### Group 5 — Success Metrics

#### SM-1: Success Metrics

WHY: Concrete metrics make "done" measurable. They guide feature prioritization and help you know when to ship.

```
How will you measure success?

Define 2-4 concrete metrics with numbers or thresholds.
```

| Option              | Best When                   | Example                                    |
| ------------------- | --------------------------- | ------------------------------------------ |
| Adoption metrics    | Early-stage, proving demand | "50 beta users within 30 days of launch"   |
| Engagement metrics  | Retention matters           | "Weekly active users > 60% of signups"     |
| Performance metrics | Speed is a feature          | "Average page load under 2 seconds"        |
| Business metrics    | Revenue-driven              | "$1k MRR within 3 months"                  |
| Quality metrics     | Reliability matters         | "99.9% uptime, <1% error rate"             |
| User satisfaction   | UX-focused                  | "80% task completion rate in user testing" |

**Recommended:** Generate based on V-3 (users) and V-2 (problem). Consumer apps → adoption + engagement. B2B SaaS → business metrics + quality. Dev tools → adoption + performance.

---

### Open-Ended Catch-All

#### OE-1: Anything Else?

After all guided questions are complete, ask:

```
Is there anything about your product that we haven't covered? Any thoughts, constraints,
or decisions you'd like to capture?

If not, just say "No, we're good" and I'll generate the output files.
```

**No options table** for this question — it is purely open-ended.

**CRITICAL behavior:** If the user provides additional information, you MUST parse it and integrate it into the appropriate sections of the output documents. Do NOT create a separate "Other Notes" or "Additional" section. Examples:

- "We need HIPAA compliance" → add to a relevant section in PRD.md (e.g., constraints or requirements)
- "We're using Stripe for payments" → add to TECH_STACK.md under Key Dependencies
- "The CEO wants dark mode" → note in PRD.md features or reference for `/define-design`
- "We have a tight deadline of 3 months" → add to PRD.md as a constraint

If the user says "No" or "We're good", proceed directly to writing output files.

---

## Step 3: Write PRD.md

After gathering all answers, write `docs/architecture/PRD.md`:

```markdown
# [Project Name] — Product Requirements Document

**Last Updated**: [YYYY-MM-DD]
**Status**: Draft
**Version**: 1.0

## Target Users

[V-3 answer]

## Problem Statement

[V-2 answer]

## Product Sections

| Section           | MVP      | Status  | Spec |
| ----------------- | -------- | ------- | ---- |
| [kebab-case-name] | [Yes/No] | defined | —    |
| [kebab-case-name] | [Yes/No] | defined | —    |

## Data Shape

### Entities

[D-1 entities with key fields]

### Relationships

[D-1 relationships]

## Non-Goals

[R-3 answer as a bulleted list]

## Success Metrics

[SM-1 answer as a bulleted list]
```

**In update mode:** Only modify sections the user chose to update. Preserve everything else.

**IMPORTANT:** The Product Sections table is the **section registry**. Status values progress through: `defined` → `shaped` (after `/shape-section`) → `planned` (after `/pnf`) → `built` (after `/inf` or manual) → `shipped` (set manually by the user). At this point, all sections start as `defined`.

---

## Step 4: Write TECH_STACK.md

Write `docs/architecture/TECH_STACK.md`:

```markdown
# [Project Name] — Tech Stack

**Last Updated**: [YYYY-MM-DD]
**Status**: Draft
**Version**: 1.0

## Frontend

- **Framework**: [TS-1 answer]
- **Styling**: [TS-2 answer]

## Backend

- **Framework**: [TS-3 answer]
- **Language**: [Inferred from framework, e.g. Python 3.12 for FastAPI, TypeScript for Hono]

## Database

- [TS-4 answer]

## Authentication

- [TS-5 answer]

## Hosting & Deployment

- [TS-6 answer]
```

**In update mode:** Only modify sections the user chose to update. Preserve everything else.

---

## Step 5: Update CLAUDE.md

After writing both architecture docs, update `CLAUDE.md` in the project root:

1. **Update the "WHY — Project Purpose" section** in CLAUDE.md. Replace the existing purpose description with 2-4 sentences derived from the problem statement and target users. Write a concise summary — do not copy-paste the PRD verbatim.

2. **Fill in the tech stack bullet points** in the "WHAT — Tech Stack" section. Remove the `<!-- e.g. ... -->` HTML comment hints when filling in real values:
   - **Frontend:** [framework + styling + TypeScript version if known]
   - **Backend:** [language + framework + key library like Pydantic if relevant]
   - **Database:** [database + ORM if applicable]
   - **Infrastructure:** [hosting choices]

3. **Do NOT modify** any other sections of CLAUDE.md.

---

## Step 6: Update README.md

After updating CLAUDE.md, rewrite `README.md` in the project root to reflect the product that was just defined. Replace the entire file with content derived from the Q&A answers. Use this structure:

````markdown
# [Project Name]

[Problem statement — 2-3 sentences from V-2, written as a product pitch, not a problem description]

## Features

[MVP sections from R-1/R-2 as a bulleted list — short, scannable descriptions]

## Tech Stack

| Layer        | Technology                     |
| ------------ | ------------------------------ |
| **Frontend** | [framework + styling]          |
| **Backend**  | [framework]                    |
| **Database** | [database + ORM if applicable] |
| **Auth**     | [provider]                     |
| **Hosting**  | [platform]                     |

## Development

```bash
pnpm install   # Install dependencies
pnpm dev       # Start dev servers (web :3000, API :3001)
pnpm build     # Build all apps and packages
pnpm test      # Run tests
pnpm typecheck # TypeScript type check
pnpm lint      # Lint all workspaces
```

## License

[Keep existing license line from the current README.md]
````

**Rules for this step:**

- Use the user's exact words from the Q&A — do not embellish or add information they did not provide.
- If any answer was "TBD", write "TBD" in the README too.
- Omit sections that are entirely TBD (e.g., if all tech stack answers are TBD, omit the Tech Stack table).
- Preserve the existing License section from the current README.md verbatim.
- Do not add badges, shields, or links to the upstream template. This is the project's README now, not a template.

---

## Step 7: Summary and Next Step

After all files are written, present a summary:

```
Done. Here is what was written:

**docs/architecture/PRD.md**
- Project: [name]
- [N] product sections registered (section registry created)
- [N] MVP sections, [N] post-MVP
- [N] data entities defined
- [N] non-goals defined

**docs/architecture/TECH_STACK.md**
- Frontend: [framework + styling]
- Backend: [framework]
- Database: [choice]
- Auth: [choice]
- Hosting: [choice]

**CLAUDE.md** updated with project purpose and tech stack summary.
**README.md** updated with product description, features, and tech stack.

Recommended next step: Run `/define-design` to define your design system, app flow,
and frontend guidelines, then `/define-architecture` to define your backend structure
and CI/CD pipeline.

After that, use `/shape-section [name]` to deep-dive into each product section.
```

---

## Behavioral Rules

1. **Ask one question at a time.** Never batch multiple questions into a single message.
2. **Wait for an answer before proceeding.** Do not assume or fill in answers.
3. **Accept "TBD" gracefully.** Write it literally into the docs. Do not ask follow-up questions about TBD answers.
4. **In update mode, show current values.** Let the user confirm or change each field.
5. **Do not invent information.** Only write what the user explicitly told you.
6. **Use exact answers provided.** Do not rephrase or editorialize unless the user asks you to clean up their wording.
7. **Generate guided format dynamically.** Options tables and recommendations must reference prior answers — do not just repeat the static examples from this prompt. Adapt, add, or remove options based on context.
8. **Normalize section names to kebab-case.** Always convert user input like "User Auth" to `user-auth` in the registry and all references.
9. **Integrate open-ended answers.** Parse the catch-all response and place information in the appropriate document sections — never create an "Other" dump section.
