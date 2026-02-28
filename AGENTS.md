# [Project Name] – Agent Instructions

> **Template scope:** Full-stack monorepo with a **TypeScript/Next.js frontend** and a **Hono API backend**, managed with Turborepo and pnpm workspaces. Adapt section headers and placeholder values if your topology differs.

> **File purpose:** `AGENTS.md` is the agent instruction file for AI coding tools that are **not** Claude Code (e.g. OpenAI Codex, Gemini Code Assist, OpenCode, Zed AI, Cursor). Claude Code uses `CLAUDE.md` instead. Keep both files in sync when updating project-wide conventions.

---

## WHY – Project Purpose

<!-- 2–4 sentences. What problem does this solve? Who are the users? What's the core value prop?   -->
<!-- This anchors every decision the agent makes — keep it here, not in a linked doc.              -->

[PROJECT_PURPOSE_PLACEHOLDER]

---

## WHAT – Tech Stack

<!-- List primary technologies + versions only. Enough for the agent to choose the right tools.    -->
<!-- Full detail lives in docs/architecture/TECH_STACK.md — link to it, don't duplicate.           -->

- **Frontend:** Next.js 15 App Router, Tailwind CSS v4, TypeScript 5
- **Backend:** Hono (Node.js), TypeScript 5
- **Database:** PostgreSQL via Prisma (in packages/db)
- **Infrastructure:** Vercel (web), your choice (API)

> Full breakdown → `docs/architecture/TECH_STACK.md`
> Product requirements → `docs/architecture/PRD.md`

### Codebase Map

<!-- One line per top-level directory. Enough for the agent to know where to look without reading everything. -->

```
/
├── apps/web/       # Next.js 15 frontend (App Router, Tailwind v4)
├── apps/api/       # Hono API server (CORS, /health endpoint)
├── packages/db/    # Prisma schema, client singleton, migrations
├── packages/shared/# Shared TypeScript types and utilities
├── packages/ui/    # Shared React components + Tailwind config + cn() helper
├── docs/           # Architecture docs, plans, reports, experiments
└── scripts/        # Compound Product pipeline, maintenance scripts
```

> Before creating, moving, or deleting any file: check `docs/architecture/REPOSITORY_STRUCTURE.md`
> for the layout decision tree (Section 7).

---

## HOW – Development Commands

<!-- Only commands the agent needs to do meaningful work every session. No exhaustive lists.        -->
<!-- If a command is only relevant for one task, put it in the relevant progressive-disclosure doc. -->

```bash
# Install
pnpm install              # installs all workspace deps + lefthook hooks

# Dev server (both apps via Turborepo)
pnpm dev                  # web on :3000, API on :3001

# Build
pnpm build                # builds all apps and packages

# Test
pnpm test                 # runs Vitest across all workspaces

# Typecheck (run before marking any task done)
pnpm typecheck            # TypeScript type check (no emit)
```

**Linting & formatting** are handled by ESLint + Prettier — the agent must not manually fix style.
Auto-fix command: `pnpm format`

### Definition of Done

The agent must confirm all three before closing a task:

- [ ] Tests pass: `pnpm test`
- [ ] Typecheck passes: `pnpm typecheck`
- [ ] No new lint errors: `pnpm lint`

---

## Git Conventions

```bash
git switch -c ✨ feat/<topic>      # new feature
git switch -c 🐛 fix/<topic>       # bug fix
git switch -c 🧹 chore/<topic>     # maintenance, deps, config
git switch -c 📝 docs/<topic>      # documentation only
git switch -c 🔨 refactor/<topic>  # structural change, no new behavior
git switch -c 🧪 test/<topic>      # test-only changes
git switch -c 🎨 style/<topic>     # style only
git switch -c 🚀 perf/<topic>      # performance improvement
git switch -c ⚡ ci/<topic>        # CI/CD changes
```

<!-- Add any project-specific branch protection rules or PR requirements here. -->

---

## Project-Specific Guardrails

<!-- Only rules that are (a) project-specific AND (b) apply to virtually every task.              -->
<!-- Explain the WHY. Provide a safe alternative — never just "don't".                            -->
<!-- Keep this table short: if a rule is only relevant for one workflow, move it to a linked doc. -->

| Don't                                      | Do Instead                                                 | Why                                  |
| ------------------------------------------ | ---------------------------------------------------------- | ------------------------------------ |
| Inline secrets in commands                 | Use `.env.local` + `process.env`                           | Secrets must never be in git history |
| Create files without checking structure    | Read `docs/architecture/REPOSITORY_STRUCTURE.md` Section 7 | CI enforces structure compliance     |
| Use `prisma migrate dev`                   | Use `prisma migrate deploy` from `packages/db/`            | Prevents destructive dev migrations  |
| Create ` 2`/` copy`/` v2` files            | Use `docs/experiments/<topic>/` for prototypes             | Finder artifacts break CI            |
| Bypass pre-commit hooks with `--no-verify` | Fix the issue, then commit                                 | CI will catch it anyway              |

---

## Progressive Disclosure

<!-- The agent reads these only when the task is relevant — never all upfront.                    -->
<!-- Pointers only. Never copy content here — it will go stale. No inline code snippets.          -->

| Doc                                        | Read When                                          |
| ------------------------------------------ | -------------------------------------------------- |
| `docs/architecture/PRD.md`                 | Understanding feature intent or product scope      |
| `docs/architecture/APP_FLOW.md`            | Working on navigation, auth flow, or user journeys |
| `docs/architecture/TECH_STACK.md`          | Evaluating or adding dependencies                  |
| `docs/architecture/BACKEND_STRUCTURE.md`   | Modifying API routes, services, or data models     |
| `docs/architecture/FRONTEND_GUIDELINES.md` | Building or refactoring UI components              |

<!-- Add project-specific docs here as they grow. Examples:                                       -->
<!--   docs/how-tos/database-migrations.md   → when running or writing migrations                 -->
<!--   docs/how-tos/deployment.md            → when deploying or configuring CI/CD                -->

---

## Quick Links

| Topic                | Location                                   |
| -------------------- | ------------------------------------------ |
| Product requirements | `docs/architecture/PRD.md`                 |
| App flow & auth      | `docs/architecture/APP_FLOW.md`            |
| Frontend patterns    | `docs/architecture/FRONTEND_GUIDELINES.md` |
| Backend structure    | `docs/architecture/BACKEND_STRUCTURE.md`   |
| Tech stack           | `docs/architecture/TECH_STACK.md`          |
