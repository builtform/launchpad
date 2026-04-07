# Repository Structure & File Placement

**Last Updated**: 2026-04-04
**Status**: Active
**Version**: 2.0

> **Single source of truth for where everything lives in this monorepo.**
> Before creating, moving, or deleting any file: read the Decision Tree (Section 6) and confirm the destination. If unsure, ask the user.
> CI will fail if violations are detected (`scripts/maintenance/check-repo-structure.sh`).

---

## 1. Root Whitelist

The repo root is clean and predictable. Only whitelisted files and directories belong here. The enforcement script (`scripts/maintenance/check-repo-structure.sh`) validates this on every commit.

### Allowed Files at Root

| File                                  | Purpose                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------ |
| `README.md`, `README.template.md`     | Project overview (template for downstream)                               |
| `CLAUDE.md`                           | AI agent operating rules for Claude Code                                 |
| `AGENTS.md`                           | OpenAI Codex agent configuration                                         |
| `CONTRIBUTING.md` / `.template.md`    | Contribution guidelines                                                  |
| `CODE_OF_CONDUCT.md` / `.template.md` | Code of conduct                                                          |
| `SECURITY.md` / `.template.md`        | Security policy                                                          |
| `CHANGELOG.md` / `.template.md`       | Changelog                                                                |
| `LICENSE` / `.template`               | MIT license (Thinking Hand Studio LLC)                                   |
| `package.json`                        | Root workspace config, shared devDependencies                            |
| `pnpm-workspace.yaml`                 | Workspace globs: `apps/*`, `packages/*`                                  |
| `pnpm-lock.yaml`                      | Lockfile (auto-generated, never edit)                                    |
| `turbo.json`                          | Turborepo task pipeline                                                  |
| `prettier.config.js`                  | Root Prettier config (must be at root)                                   |
| `lefthook.yml`                        | Git hook config (lint, format, structure)                                |
| `vitest.config.ts`                    | Root Vitest config with project references                               |
| `eslint.config.mjs`                   | Root ESLint 9 flat config                                                |
| `.prettierignore`                     | Prettier exclusions                                                      |
| `.env.example`                        | Template for `.env.local` — no real secrets                              |
| `.env.local`                          | Real environment variables (gitignored)                                  |
| `.env.consultant`                     | Consultant env reference (gitignored, read-only subset credentials only) |
| `.editorconfig`                       | Cross-editor indent/line-ending baseline                                 |
| `.nvmrc`                              | Pins Node.js version (22.x)                                              |
| `.gitignore`                          | Standard ignore rules                                                    |
| `.gitattributes`                      | Git attribute rules, line endings (optional — created when needed)       |
| `.worktreeinclude`                    | Claude Code worktree env file declarations (which `.env*` files to copy) |

Note: Files marked with `.template` or `.template.md` are used by `init-project.sh` to scaffold downstream projects. Agents do not create or modify template files.

### Allowed Directories at Root

| Directory                                               | Purpose                                                                      |
| ------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `apps/`                                                 | User-facing applications (web, api)                                          |
| `packages/`                                             | Shared internal libraries (db, shared, ui, eslint-config, typescript-config) |
| `scripts/`                                              | Repo-wide maintenance and automation                                         |
| `docs/`                                                 | Centralized documentation hub                                                |
| `.github/`                                              | GitHub Actions, issue/PR templates                                           |
| `.vscode/`                                              | Shared editor settings                                                       |
| `.claude/`                                              | Claude Code agents, commands, skills, hooks                                  |
| `.launchpad/`                                           | Harness metadata (downstream only — created by `init-project.sh`)            |
| `node_modules/`, `.turbo/`, `.next/`, `dist/`, `build/` | Build/cache artifacts (gitignored)                                           |
| `.git/`                                                 | Git internals                                                                |

Anything not on these lists is root clutter and must be moved.

---

## 2. Directory Tree (Constraint-Bearing Annotations Only)

This tree shows only directories and files where a **non-obvious constraint** applies. For the full file listing, run `ls -R` or see the Codebase Map in CLAUDE.md. Each app/package also contains its own `package.json`, `tsconfig.json`, and `eslint.config.mjs` extending shared workspace presets.

```
apps/
├── web/                                     # Next.js 15 App Router frontend
│   ├── src/
│   │   ├── app/                             # App Router: pages, layouts, route groups
│   │   ├── components/                      # Page-level and layout-level components
│   │   ├── features/                        # Feature-scoped modules (colocated logic, hooks, types)
│   │   ├── hooks/                           # App-specific custom React hooks
│   │   ├── lib/                             # Client-side helpers, fetchers, SDK wrappers
│   │   ├── styles/
│   │   │   └── globals.css                  # Tailwind v4 config lives here (CSS-native, no tailwind.config.ts)
│   │   └── types/                           # App-local TypeScript types (NOT shared — use packages/shared for shared types)
│   ├── public/                              # Static assets served at /
│   ├── tests/                               # Vitest tests
│   └── postcss.config.mjs                   # PostCSS integration layer for Tailwind v4

├── api/                                     # Hono API server
│   ├── src/
│   │   ├── routes/                          # Route definitions (thin — delegate to controllers)
│   │   ├── controllers/                     # Request handlers (thin — delegate to services)
│   │   ├── services/                        # Business logic (primary home for domain code)
│   │   ├── middleware/                       # Auth, logging, error handling, rate limiting
│   │   ├── db/                              # Re-exports @repo/db for the API layer (created when needed)
│   │   ├── config/                          # Env loading, constants, startup config
│   │   ├── types/                           # API-local TypeScript types (NOT shared)
│   │   └── index.ts                         # App entry point
│   └── tests/                               # Vitest tests

packages/
├── db/                                      # Canonical Prisma package — ONLY place for schema + migrations
│   ├── prisma/
│   │   ├── schema.prisma                    # Single source of truth for database schema
│   │   └── migrations/                      # Migration history (never edit manually)
│   └── src/
│       ├── client.ts                        # PrismaClient singleton
│       └── index.ts                         # Public exports

├── shared/                                  # Shared TypeScript types and pure utility functions
│   └── src/
│       ├── types/                           # Shared interfaces, enums, Zod schemas
│       ├── utils/                           # Pure utility functions (no framework deps — no React imports)
│       └── index.ts

├── ui/                                      # Shared React component library
│   └── src/
│       ├── components/                      # Shared UI components
│       └── index.ts

scripts/
├── agent_hydration/                         # AI agent context scripts
├── compound/                                # Compound Product pipeline scripts
├── hooks/                                   # Claude Code hook scripts (PostToolUse)
├── maintenance/                             # Structure checks, repo hygiene
└── setup/                                   # Project init and upstream sync

docs/                                        # See Decision Tree (Section 6.1) for routing
├── architecture/                            # System design, ADRs (decisions/ created when needed), tech stack
├── plans/                                   # Implementation plans, phased roadmaps
├── reports/                                 # Investigation reports, audits, postmortems
├── tasks/                                   # Active work: TODO.md, section specs
├── solutions/                               # Categorized learnings from compound loops
├── brainstorms/                             # Brainstorming documents
├── handoffs/                                # Session handoff documents
├── guides/                                  # How-to guides, tutorials
├── lessons/                                 # Running log (LESSONS.md — append-only)
├── experiments/                             # Exploratory notes (move to archive when done)
├── articles/                                # Long-form research
├── consultants/                             # External consultant deliverables
├── eval/                                    # Evaluation results (front_end/, back_end/)
├── ui/                                      # UI/UX design documentation
├── skills-catalog/                          # Skill index, usage tracking, catalog
└── archive/                                 # Retired docs (permanent, never delete)

.claude/
├── agents/                                  # Sub-agent definitions
├── commands/                                # Slash command definitions
├── skills/                                  # One directory per skill
│   └── <skill-name>/
│       ├── SKILL.md                         # Orchestrator (<500 lines)
│       ├── references/                      # On-demand reference files (ONE level deep only)
│       └── evals/                           # Evaluation scenarios (>=3 per skill)
├── Prompts/                                 # Reusable prompt templates
├── profiles/                                # Cognitive profiles
├── settings.json                            # Project-level hooks (committed)
└── settings.local.json                      # Local settings (gitignored)
```

---

## 3. Workspace Package Names

All packages use the `@repo/` scope.

| Package                   | Consumed By                                                    |
| ------------------------- | -------------------------------------------------------------- |
| `@repo/db`                | `apps/api` (required); `apps/web` server components (optional) |
| `@repo/shared`            | `apps/api`, `apps/web`                                         |
| `@repo/ui`                | `apps/web`                                                     |
| `@repo/eslint-config`     | All packages and apps (devDependency)                          |
| `@repo/typescript-config` | All packages and apps (devDependency)                          |

---

## 4. Key Architectural Rules

These rules encode non-obvious design decisions. Violating them breaks downstream consumers, deployments, or type safety.

### Rule 1: Prisma lives in `packages/db`, never in `apps/api`

**Wrong:**

```
apps/api/prisma/schema.prisma      <- NEVER
apps/api/src/prisma/client.ts      <- NEVER
```

**Correct:**

```
packages/db/prisma/schema.prisma   <- Single source of truth
packages/db/src/client.ts          <- PrismaClient singleton
apps/api/src/db/client.ts          <- Re-exports @repo/db
```

**Why:** Placing Prisma inside `apps/api` scopes generated `PrismaClient` types to that one app. Any future service (cron worker, webhook handler, second API) that needs DB access must either duplicate the schema or create circular imports. The canonical pattern (Prisma official Turborepo guide, create-t3-turbo, next-forge) is to centralize in `packages/db` and import via `@repo/db`.

### Rule 2: New packages require `package.json` + `tsconfig.json` + `src/index.ts`

Every shared library is a proper workspace package with `@repo/<name>` scope, extending `@repo/typescript-config`. No framework-specific code unless the package is explicitly scoped (e.g., `@repo/ui` is React-only).

### Rule 3: No Docker

No `Dockerfile`, `docker-compose.yml`, or Docker config. Infrastructure uses platform-managed deployments (Vercel, Railway).

### Rule 4: No `tooling/` directory

All repo-wide scripts live in `scripts/` with clear subdirectory naming. App-specific scripts go in `apps/<app>/scripts/`.

### Rule 5: TypeScript presets live in `packages/typescript-config`

No root `tsconfig.base.json`. Presets: `base.json` (bundler moduleResolution — for Next.js and packages), `next.json` (JSX + Next.js), `node.json` (Node16 moduleResolution — for directly-executed Node processes like Hono API via tsx).

---

## 5. The `docs/` Directory

Every subdirectory in `docs/` has a specific purpose. Do not use `docs/` as a catch-all.

| Directory              | Purpose                                                                     |
| ---------------------- | --------------------------------------------------------------------------- |
| `docs/architecture/`   | System design, ADRs, tech stack, design system, frontend/backend guidelines |
| `docs/archive/`        | Retired docs retained for reference (permanent, never delete)               |
| `docs/articles/`       | Long-form reference articles and research                                   |
| `docs/brainstorms/`    | Brainstorming documents                                                     |
| `docs/consultants/`    | External consultant deliverables and briefs                                 |
| `docs/eval/`           | Evaluation results (front_end/, back_end/)                                  |
| `docs/experiments/`    | Exploratory notes (move to archive when done)                               |
| `docs/guides/`         | How-to guides and tutorials                                                 |
| `docs/handoffs/`       | Session handoff documents                                                   |
| `docs/lessons/`        | Running log of lessons learned (LESSONS.md — append-only)                   |
| `docs/plans/`          | Implementation plans, phased roadmaps                                       |
| `docs/reports/`        | Investigation reports, audits, postmortems                                  |
| `docs/skills-catalog/` | Skill index, usage tracking, catalog                                        |
| `docs/solutions/`      | Categorized learnings from compound loops                                   |
| `docs/tasks/`          | Active work: TODO.md, section specs                                         |
| `docs/ui/`             | UI/UX design documentation                                                  |

---

## 6. Decision Tree: Where Does My File Go?

Walk through in order. Stop at the first match.

### 6.1 Documentation

- Architecture doc, ADR, tech overview → `docs/architecture/`
- ADR → `docs/architecture/decisions/ADR-<number>-<title>.md` (never delete; if superseded, update Status)
- Implementation plan or roadmap → `docs/plans/`
- Section spec (from `/shape-section`) → `docs/tasks/sections/`
- Backlog or task tracking → `docs/tasks/`
- Lessons learned → append to `docs/lessons/LESSONS.md` (append-only, never rewrite)
- Categorized solution from compound loop → `docs/solutions/`
- Brainstorming document → `docs/brainstorms/`
- Session handoff document → `docs/handoffs/`
- Investigation report, audit, postmortem → `docs/reports/YYYY-MM-DD-<topic>.md`
- UI/UX design notes → `docs/ui/ux/`
- Exploratory notes → `docs/experiments/` (move to `docs/archive/` when done)
- Article or research → `docs/articles/`
- Consultant deliverable → `docs/consultants/`
- Evaluation result → `docs/eval/front_end/` or `docs/eval/back_end/`
- Skill catalog → `docs/skills-catalog/`
- Retired doc → `docs/archive/` (permanent, never delete)
- Preserved reference from LaunchPad → `.launchpad/` (downstream only)
- **Never add docs at root** beyond the whitelist in Section 1.

**Lifecycle rules:**

- `docs/archive/` — permanent, never delete
- `docs/lessons/LESSONS.md` — append-only
- `docs/reports/` — prune after ~90 days unless referenced
- `docs/experiments/` — archive when concluded

### 6.2 Scripts

- Repo-wide maintenance → `scripts/maintenance/`
- AI agent hydration → `scripts/agent_hydration/`
- Claude Code hook → `scripts/hooks/`
- Compound Product pipeline → `scripts/compound/`
- Project init or upstream sync → `scripts/setup/`
- Frontend-specific → `apps/web/scripts/`
- Backend-specific → `apps/api/scripts/`
- **Never put scripts at the repo root.**

### 6.3 Shared types

- Used by both apps → `packages/shared/src/types/`
- Web-only → `apps/web/src/types/`
- API-only → `apps/api/src/types/`

### 6.4 Utility functions

- Framework-agnostic, shared → `packages/shared/src/utils/` (no React imports)
- Frontend-specific → `apps/web/src/lib/`
- Backend business logic → `apps/api/src/services/`
- Backend config (env loading, constants) → `apps/api/src/config/`

### 6.5 React components

- Reused across pages → `apps/web/src/components/`
- Feature-scoped → `apps/web/src/features/<feature-name>/`
- Design system (shared across apps) → `packages/ui/src/components/`
- Custom hooks → `apps/web/src/hooks/` (app-specific). For shared React hooks, add to `packages/ui/src/`

### 6.6 Database

- Schema → `packages/db/prisma/schema.prisma` (the ONLY place)
- Migration → `packages/db/prisma/migrations/` (generated by `prisma migrate`)
- PrismaClient config → `packages/db/src/client.ts`
- API DB wrapper → `apps/api/src/db/`
- **Never put Prisma schema or migrations in `apps/api/`.**

### 6.7 API routes/controllers/services

- Routes → `apps/api/src/routes/`
- Controllers → `apps/api/src/controllers/`
- Services → `apps/api/src/services/`
- Middleware → `apps/api/src/middleware/`

### 6.8 Frontend pages

- App Router page/layout → `apps/web/src/app/`
- Feature module → `apps/web/src/features/<feature-name>/`
- Global styles → `apps/web/src/styles/`
- Static assets → `apps/web/public/`

### 6.9 CI/CD and GitHub

- Actions workflow → `.github/workflows/`
- Issue template → `.github/ISSUE_TEMPLATE/`
- PR template → `.github/pull_request_template.md`

### 6.10 Experiments

- Exploratory notes → `docs/experiments/`
- **Never create `file v2.ts`, `file copy.ts`, or `file 2.ts` anywhere.** These are macOS Finder artifacts or lazy experimentation — both unacceptable in production directories.
- Prototype in `docs/experiments/`, then copy proven logic to canonical location and remove the experiment.
- **Never import from `docs/experiments/` in production code.**

### 6.11 Banned Patterns

- **No loose scripts in source trees** — no `debug.ts`, `test_script.ts`, or one-off `.sh` files inside `apps/` or `packages/src/`. Debug scripts → `apps/<app>/scripts/`.
- **No infrastructure config in apps/packages** — deployment config, CI config, and infra belong in root-level directories (`.github/`, root config files), not inside `apps/` or `packages/`.
- **No production code in experiments** — never import from `docs/experiments/` in production code.

### 6.12 New workspace package

Create `packages/<name>/` with `package.json` (`@repo/<name>`), `tsconfig.json`, `src/index.ts`. Never under `apps/`.

### 6.13 Claude Code agent, command, or skill

- Agent → `.claude/agents/`
- Command → `.claude/commands/`
- Prompt template → `.claude/Prompts/`
- Skill → `.claude/skills/<skill-name>/SKILL.md`
- Skill references → `.claude/skills/<skill-name>/references/` (one level deep only)
- Skill evals → `.claude/skills/<skill-name>/evals/`
- Profile → `.claude/profiles/`

### If none match:

**Ask the user.** Do not guess. Do not create a new top-level directory without an explicit architectural decision.

---

## 7. Maintaining This Document

When the structure changes:

1. Update this file: root whitelist (Section 1), directory tree (Section 2), docs table (Section 5), decision tree (Section 6).
2. Update `scripts/maintenance/check-repo-structure.sh` to match Section 1.
3. Update `CLAUDE.md` codebase map.
4. Update `AGENTS.md` if the change affects review scope.

If this file and any local README disagree, **this file wins**. Fix the README.

**Run structure check manually:** `bash scripts/maintenance/check-repo-structure.sh`

**Note:** `git commit --no-verify` is banned by project convention. CI catches all violations regardless.
