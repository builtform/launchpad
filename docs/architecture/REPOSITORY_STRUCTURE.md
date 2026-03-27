# Repository Structure & File Placement

**Last Updated**: 2026-03-01
**Status**: Active
**Version**: 1.0

> **This is the single source of truth for where everything lives in this monorepo.**
> Humans and AI assistants **must** follow this file when creating, moving, or deleting code, docs, or scripts.
>
> **Note: CI will fail if violations of the rules outlined here are detected.**

---

## 1. Purpose & Audience

- Prevent structural chaos: no random folders, no root clutter, no duplicate files.
- Make it obvious where new code, scripts, docs, and experiments belong.
- Support both:
  - **Humans** doing normal development, and
  - **AI agents** generating or editing files safely — this document must provide zero-ambiguity answers to "where does this file go?"

**Before creating, moving, or deleting any file:** read Section 7 (Decision Tree) and confirm the destination. If still unsure, ask the user rather than guessing.

---

## 2. Root Layout & Whitelist

The repository root is **clean and predictable**. Only a small, explicit set of files and directories belong here. Every item not on this list is root clutter and must be moved to a subdirectory.

`scripts/maintenance/check-repo-structure.sh` enforces this whitelist automatically on every commit and in CI.

### 2.1 Canonical Files at Root

**Documentation & Templates (each doc may have a `.template` pair for new projects):**

- `README.md` — High-level project overview for new contributors.
- `CLAUDE.md` — AI agent operating rules for Claude Code (primary AI configuration).
- `AGENTS.md` — OpenAI Codex agent configuration and review guidelines.
- `CONTRIBUTING.md` — Contribution guidelines (created by `init-project.sh` from template).
- `CONTRIBUTING.template.md` — Contribution guidelines template for new projects.
- `CODE_OF_CONDUCT.md` — Code of conduct (created by `init-project.sh` from template).
- `CODE_OF_CONDUCT.template.md` — Code of conduct template for new projects.
- `SECURITY.md` — Security policy (created by `init-project.sh` from template).
- `SECURITY.template.md` — Security policy template for new projects.
- `CHANGELOG.md` — Changelog (created by `init-project.sh` from template).
- `CHANGELOG.template.md` — Changelog template for new projects.
- `LICENSE` — MIT license (Thinking Hand Studio LLC).
- `LICENSE.template` — MIT license template for new projects.
  **Tooling & Workspace Configuration:**

- `package.json` — Root workspace config, shared `devDependencies`, and workspace scripts.
- `pnpm-workspace.yaml` — Workspace globs: `apps/*`, `packages/*`.
- `pnpm-lock.yaml` — Lockfile (auto-generated; never edit manually).
- `turbo.json` — Turborepo task pipeline (build, lint, test, dev, typecheck).
- `prettier.config.js` — Root Prettier config (must be at root for pnpm workspace-wide effect).
- `lefthook.yml` — Git hook config (pre-commit: lint, format, structure checks).
- `vitest.config.ts` — Root Vitest config with project references for all apps and packages.

**Environment & Editor:**

- `.env.example` — Template for `.env.local`; never contains real secrets.
- `.env.local` — Real environment variables; gitignored; load via `load_dotenv()` or `process.env`.
- `.env.consultant` — Consultant-facing environment variable reference; gitignored.
- `.editorconfig` — Cross-editor indent/line-ending baseline.
- `.nvmrc` — Pins Node.js version (22.x).
- `.gitignore` — Standard ignore rules.
- `.gitattributes` — Git attribute rules (line endings, binary files).

### 2.2 Allowed Directories at Root

**If a directory is not on this list, it does not belong at root.**

- `apps/` — User-facing applications (web frontend, API backend).
- `packages/` — Shared internal libraries (db, shared types, UI kit, configs).
- `scripts/` — Repository-level maintenance and automation scripts.
- `docs/` — Centralized documentation hub.
- `.github/` — GitHub Actions workflows, issue templates, PR templates.
- `.vscode/` — Shared VS Code editor settings.
- `.claude/` — Claude Code agent configuration, slash commands, and prompt libraries.
- `node_modules/` — Installed dependencies (gitignored).
- `.git/` — Git internals (never touch manually).
- `.launchpad/` — Harness metadata and preserved Launchpad reference docs (created by `init-project.sh`).
- `.turbo/` — Turborepo cache (gitignored).
- `.next/` — Next.js build output (gitignored).
- `dist/` — Build output (gitignored).
- `build/` — Build output (gitignored).

Anything else at root is root clutter and must be moved to the correct subdirectory.

---

## 3. Full Annotated Directory Tree

```
{{PROJECT_NAME}}/
│
├── apps/                                    # User-facing applications
│   ├── web/                                 # Next.js 15 App Router frontend
│   │   ├── public/                          # Static assets served at /
│   │   ├── src/
│   │   │   ├── app/                         # App Router: pages, layouts, route groups
│   │   │   ├── components/                  # Page-level and layout-level React components
│   │   │   ├── features/                    # Feature-scoped modules (colocated logic, hooks, types)
│   │   │   ├── hooks/                       # Shared custom React hooks
│   │   │   ├── lib/                         # Client-side helpers, fetchers, SDK wrappers
│   │   │   ├── styles/                      # Global CSS, Tailwind base config
│   │   │   │   └── globals.css              # Global styles and Tailwind directives
│   │   │   └── types/                       # App-local TypeScript types (not shared)
│   │   ├── tests/                           # Vitest tests for the web app
│   │   ├── eslint.config.mjs                # ESLint 9 flat config (extends @repo/eslint-config)
│   │   ├── next.config.ts                   # Next.js configuration
│   │   ├── postcss.config.mjs               # PostCSS configuration (Tailwind)
│   │   ├── tailwind.config.ts               # Tailwind CSS configuration
│   │   ├── tsconfig.json                    # Extends @repo/typescript-config/next.json
│   │   └── package.json                     # App dependencies
│   │
│   └── api/                                 # Backend service (Hono / Express / Fastify)
│       ├── src/
│       │   ├── config/                      # Env loading, app-wide constants, startup config
│       │   ├── routes/                      # Route definitions (thin — delegate to controllers)
│       │   ├── controllers/                 # Request handlers (thin — delegate to services)
│       │   ├── services/                    # Business logic (primary home for domain code)
│       │   ├── middleware/                  # Auth, logging, error handling, rate limiting
│       │   ├── types/                       # API-local TypeScript types (not shared)
│       │   └── index.ts                     # App entry point
│       ├── tests/                           # Vitest tests for the API
│       ├── eslint.config.mjs                # ESLint 9 flat config (extends @repo/eslint-config)
│       ├── tsconfig.json                    # Extends @repo/typescript-config/node.json
│       └── package.json                     # App dependencies
│
├── packages/                                # Shared internal libraries (consumed via workspace deps)
│   ├── db/                                  # Canonical Prisma package — single source of DB truth
│   │   ├── prisma/
│   │   │   ├── schema.prisma                # Single source of truth for the database schema
│   │   │   └── migrations/                  # Prisma migration history (never edit manually)
│   │   ├── src/
│   │   │   ├── client.ts                    # PrismaClient singleton (re-export or wrap here)
│   │   │   └── index.ts                     # Public package exports
│   │   ├── tsconfig.json
│   │   └── package.json                     # name: "@repo/db"
│   │
│   ├── shared/                              # Shared TypeScript types and pure utility functions
│   │   ├── src/
│   │   │   ├── types/                       # Shared interfaces, enums, Zod schemas
│   │   │   ├── utils/                       # Pure utility functions (no framework dependencies)
│   │   │   └── index.ts                     # Public package exports
│   │   ├── tsconfig.json
│   │   └── package.json                     # name: "@repo/shared"
│   │
│   ├── ui/                                  # Shared React component library (shadcn/ui + custom)
│   │   ├── src/
│   │   │   ├── components/                  # Shared UI components
│   │   │   ├── styles/                      # Component-level styles
│   │   │   └── index.ts                     # Public package exports
│   │   ├── tsconfig.json
│   │   └── package.json                     # name: "@repo/ui"
│   │
│   ├── eslint-config/                       # Shared ESLint configuration (workspace package)
│   │   ├── base.js                          # ESLint 9 flat config — shared base rules
│   │   ├── next.js                          # Extends base; adds React + Next.js rules
│   │   ├── node.js                          # Extends base; adds Node.js globals
│   │   └── package.json                     # name: "@repo/eslint-config"
│   │
│   └── typescript-config/                   # Shared TypeScript tsconfig presets
│       ├── base.json                        # Strict baseline (target ESNext, bundler moduleResolution)
│       ├── next.json                        # Extends base; adds JSX + Next.js plugin settings
│       ├── node.json                        # Extends base; adds Node16 module resolution
│       └── package.json                     # name: "@repo/typescript-config"
│
├── scripts/                                 # Repo-wide maintenance and automation scripts
│   ├── agent_hydration/
│   │   └── hydrate.sh                       # Loads minimal session context (repo structure + tasks)
│   ├── compound/                            # Compound Product pipeline scripts
│   │   ├── auto-compound.sh                 # Full pipeline: report -> PRD -> tasks -> loop -> PR
│   │   ├── loop.sh                          # Execution loop with archive support
│   │   ├── analyze-report.sh                # Report analysis script
│   │   ├── config.json                      # Pipeline configuration (reports dir, iterations, etc.)
│   │   └── iteration-claude.md              # Per-iteration task instructions for AI agent
│   ├── hooks/                               # Claude Code hook scripts
│   │   ├── track-skill-usage.sh             # PostToolUse hook — tracks skill invocation dates
│   │   └── audit-skills.sh                  # Stop hook — reports stale/unused skills
│   ├── maintenance/
│   │   └── check-repo-structure.sh          # Validates repo structure against this spec
│   └── setup/                               # Project initialization and upstream sync
│       ├── init-project.sh                  # Initializes a new project from LaunchPad template
│       └── pull-upstream.launchpad.sh       # Pulls upstream LaunchPad updates into project
│
├── docs/                                    # Centralized documentation hub (see Section 5)
│   ├── README.md                            # Index of the docs directory
│   ├── architecture/                        # System design documents
│   ├── archive/                             # Retired docs retained for reference
│   ├── articles/                            # Long-form reference articles and research
│   ├── consultants/                         # External consultant deliverables and briefs
│   ├── eval/                                # Evaluation reports (front-end and back-end)
│   │   ├── front_end/
│   │   └── back_end/
│   ├── experiments/                         # Exploratory notes (not production code)
│   ├── lessons/                             # Lessons learned (running log for humans + agents)
│   │   └── LESSONS.md
│   ├── solutions/                           # Categorized learnings from compound loops
│   ├── brainstorms/                         # Brainstorming documents for compound-engineering
│   ├── guides/                              # How-to guides and tutorials
│   │   ├── HOW_IT_WORKS.md                  # Step-by-step workflow guide
│   │   └── METHODOLOGY.md                   # Launchpad methodology — philosophy, architecture, diagrams, troubleshooting, credits
│   ├── plans/                               # Implementation plans and roadmaps
│   │   └── IMPLEMENTATION_PLAN.md
│   ├── reports/                             # Investigation reports, audits, postmortems
│   ├── tasks/                               # Active work tracking
│   │   ├── sections/                        # Section specs from /shape-section
│   │   └── TODO.md
│   └── ui/                                  # UI/UX design documentation
│       └── ux/
│           └── design_styles.md
│
├── .github/                                 # GitHub-specific configuration
│   ├── workflows/
│   │   ├── ci.yml                           # Lint, typecheck, test on every PR
│   │   └── deploy.yml                       # Deploy on merge to main
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── pull_request_template.md
│
├── .vscode/
│   └── settings.json                        # Shared editor settings (format on save, etc.)
│
├── .launchpad/                              # Harness metadata and preserved Launchpad reference docs
│   ├── METHODOLOGY.md                       # Launchpad methodology — architecture, diagrams, troubleshooting, credits
│   ├── HOW_IT_WORKS.md                      # Step-by-step workflow guide
│   └── version                              # Harness version for CLI upgrades
│
└── .claude/                                 # Claude Code configuration
    ├── agents/                              # Sub-agent definition files
    ├── commands/                            # Slash command definitions (e.g. /Hydrate, /pnf)
    ├── Prompts/                             # Reusable prompt templates
    ├── skills/                              # Skill definitions (SKILL.md + references/)
    │   └── <skill-name>/                    # One directory per skill
    │       ├── SKILL.md                     # Orchestrator (<500 lines, routes to references)
    │       ├── references/                  # On-demand reference files (one level deep only)
    │       └── evals/                       # Evaluation scenarios (≥3 per skill)
    ├── profiles/                            # Cognitive profiles (shared review infrastructure)
    │   └── PROFILE-TEMPLATE.md              # Template for building profiles
    ├── settings.json                        # Project-level hook configuration (committed)
    └── settings.local.json                  # Local Claude Code settings (gitignored)
```

---

## 4. Workspace Package Names

All packages use the `@repo/` scope. These are the canonical package names — use them exactly in `package.json` dependencies.

| Directory                    | `name` in `package.json`  | Consumed By                                                    |
| ---------------------------- | ------------------------- | -------------------------------------------------------------- |
| `packages/db`                | `@repo/db`                | `apps/api` (required); `apps/web` server components (optional) |
| `packages/shared`            | `@repo/shared`            | `apps/api`, `apps/web`                                         |
| `packages/ui`                | `@repo/ui`                | `apps/web`                                                     |
| `packages/eslint-config`     | `@repo/eslint-config`     | All packages and apps (devDependency)                          |
| `packages/typescript-config` | `@repo/typescript-config` | All packages and apps (devDependency)                          |

---

## 5. The `docs/` Directory in Detail

Every subdirectory in `docs/` has a specific purpose. Do not use `docs/` as a catch-all.

| Directory              | Purpose                                                                                    | Examples                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `docs/architecture/`   | System design, ADRs, this document, tech stack, design system, frontend/backend guidelines | `REPOSITORY_STRUCTURE.md`, `TECH_STACK.md`, `DESIGN_SYSTEM.md`, `BACKEND_STRUCTURE.md` |
| `docs/archive/`        | Retired documentation retained for historical reference; treat as read-only                | Superseded design docs, old runbooks                                                   |
| `docs/articles/`       | Long-form reference articles, research summaries, and annotated external docs              | Research summaries, annotated external docs                                            |
| `docs/consultants/`    | Deliverables, briefs, or reports from external consultants                                 | Audit reports, external review docs                                                    |
| `docs/eval/`           | Evaluation results for front-end and back-end features; structured test output             | Performance benchmarks, UX eval notes                                                  |
| `docs/experiments/`    | Exploratory notes and write-ups for experiments not yet promoted to code                   | Hypothesis docs, spike summaries                                                       |
| `docs/guides/`         | How-to guides and tutorials                                                                | Usage guides, onboarding walkthroughs                                                  |
| `docs/lessons/`        | Running log of lessons learned — populated by both humans and agents                       | `LESSONS.md` (append-only log)                                                         |
| `docs/solutions/`      | Categorized learnings from compound loops, accumulated by agents                           | YAML-frontmatter `.md` files per pattern                                               |
| `docs/brainstorms/`    | Brainstorming documents for compound-engineering                                           | Free-form brainstorm docs                                                              |
| `docs/plans/`          | Implementation plans, phased roadmaps, and step-by-step build sequences                    | `IMPLEMENTATION_PLAN.md`                                                               |
| `docs/reports/`        | Investigation reports, audits, postmortems, and one-off analyses                           | `investigation_YYYYMMDD_<topic>.md`                                                    |
| `docs/tasks/`          | Active work tracking: current TODO list and section specs                                  | `TODO.md`, `sections/`                                                                 |
| `docs/ui/`             | UI/UX design documentation, design system notes, style guides                              | `ux/design_styles.md`                                                                  |
| `docs/skills-catalog/` | Curated catalog of reusable Claude Code skills, usage tracking, and skills index           | `CATALOG.md`, `README.md`, `skills-index.md`, `skills-usage.json`                      |

**Naming convention for time-stamped reports:**

```
docs/reports/investigation_YYYYMMDD_<topic>.md
docs/reports/postmortem_YYYYMMDD_<topic>.md
docs/reports/analysis_YYYYMMDD_<topic>.md
```

**Lifecycle rules:**

- `docs/archive/` — Permanent; never delete.
- `docs/lessons/LESSONS.md` — Append-only; never rewrite history.
- `docs/reports/` — Keep if referenced by another doc or ADR; otherwise prune after ~90 days.
- `docs/experiments/` — Move to `docs/archive/` once the experiment concludes; never leave stale notes indefinitely.

---

## 6. Key Architectural Rules

These rules encode the design decisions behind this harness. Violating them breaks downstream consumers, deployments, or type safety.

### Rule 1: Prisma lives in `packages/db`, never in `apps/api`

**Wrong:**

```
apps/api/prisma/schema.prisma      ← NEVER DO THIS
apps/api/src/prisma/client.ts      ← NEVER DO THIS
```

**Correct:**

```
packages/db/prisma/schema.prisma   ← Single source of truth
packages/db/src/client.ts          ← PrismaClient singleton
apps/api/src/db/client.ts          ← Re-exports @repo/db for the API layer
```

**Why:** Placing Prisma inside `apps/api` scopes generated `PrismaClient` types to that one app. Any future service (cron worker, webhook handler, second API) that needs DB access must either duplicate the schema or create circular imports. The canonical pattern (Prisma official Turborepo guide, create-t3-turbo, next-forge) is to centralize in `packages/db` and import via `@repo/db`.

### Rule 2: New packages go in `packages/` with `package.json` and `tsconfig.json`

Every shared library must be a proper workspace package:

- Has its own `package.json` with a `@repo/<name>` package name.
- Has its own `tsconfig.json` extending the appropriate `@repo/typescript-config` preset.
- Exports its public API through `src/index.ts`.
- Never contains framework-specific code unless its scope is explicitly framework-specific (e.g. `@repo/ui` is React-only by design).

### Rule 3: No Docker

Docker is not used in this stack. Do not add `Dockerfile`, `docker-compose.yml`, or any Docker-related configuration. The infrastructure strategy uses platform-managed deployments (e.g. Vercel, Railway).

### Rule 4: `scripts/` at root is flat and discoverable

The `tooling/` directory pattern is explicitly rejected. All repo-wide scripts live directly in `scripts/` with clear subdirectory naming:

- `scripts/agent_hydration/` — AI agent context scripts.
- `scripts/compound/` — Compound Product pipeline scripts (auto-compound, loop, analysis, config).
- `scripts/hooks/` — Claude Code hook scripts (PostToolUse, Stop).
- `scripts/maintenance/` — Structure checks, lint helpers, repo hygiene.
- `scripts/setup/` — Project initialization and upstream sync scripts.

App-specific scripts belong inside the app: `apps/web/scripts/` or `apps/api/scripts/` (create as needed; they do not exist in the base harness).

### Rule 5: TypeScript Configuration

All TypeScript configuration lives in `packages/typescript-config` as named presets (`base.json`, `next.json`, `node.json`). Every app and package extends one of these via `@repo/typescript-config/*`. There is no root `tsconfig.base.json` — the workspace package is the single source of truth for TypeScript settings.

---

## 7. Decision Tree: Where Does My File Go?

When adding **any** new file, walk through this decision tree in order. Stop at the first match.

### 7.1 Is it documentation?

- Architecture document (system design, ADR, tech overview) → `docs/architecture/`
- Implementation plan or roadmap → `docs/plans/`
- Section spec (from `/shape-section`) → `docs/tasks/sections/`
- Task list or progress tracker → `docs/tasks/`
- Lessons learned (new entry) → append to `docs/lessons/LESSONS.md`
- Categorized solution or reusable pattern from a compound loop → `docs/solutions/`
- Brainstorming document for compound-engineering → `docs/brainstorms/`
- Investigation report, audit, or postmortem → `docs/reports/investigation_YYYYMMDD_<topic>.md`
- UI/UX design notes → `docs/ui/ux/`
- Exploratory notes for an experiment → `docs/experiments/`
- Article or long-form research → `docs/articles/`
- External consultant deliverable → `docs/consultants/`
- Evaluation result → `docs/eval/front_end/` or `docs/eval/back_end/`
- Skill catalog entry or recommendation → `docs/skills-catalog/CATALOG.md`
- Skill usage tracking data → `docs/skills-catalog/skills-usage.json`
- Skill index (user-facing skill reference) → `docs/skills-catalog/skills-index.md`
- Old/retired doc → `docs/archive/`
- Preserved reference guide (e.g., original README kept after `init-project.sh`) → `.launchpad/`
- **Never add documentation files at root** beyond the canonical singleton list in Section 2.1.

### 7.2 Is it a script?

- Repo-wide maintenance or structure check → `scripts/maintenance/`
- AI agent hydration or context script → `scripts/agent_hydration/`
- Claude Code hook script (PostToolUse, Stop, etc.) → `scripts/hooks/`
- Frontend-specific script → `apps/web/scripts/` (create the directory if it doesn't exist)
- Backend-specific script → `apps/api/scripts/` (create the directory if it doesn't exist)
- **Never put scripts at the repo root.**

### 7.3 Is it a shared TypeScript type or interface?

- Used by both `apps/web` and `apps/api` → `packages/shared/src/types/`
- Used only within `apps/web` → `apps/web/src/types/`
- Used only within `apps/api` → `apps/api/src/types/`

### 7.4 Is it a pure utility function?

- Framework-agnostic, used by both apps → `packages/shared/src/utils/`
- Frontend-specific → `apps/web/src/lib/`
- Backend-specific → `apps/api/src/services/` (if business logic) or `apps/api/src/config/` (if config)

### 7.5 Is it a React component?

- Reused across multiple pages or features in the web app → `apps/web/src/components/`
- Scoped to a single feature → `apps/web/src/features/<feature-name>/`
- Shared across multiple apps (design system component) → `packages/ui/src/components/`
- Custom React hook → `apps/web/src/hooks/` (app-specific) or `packages/shared/src/utils/` (framework-agnostic utility logic)

### 7.6 Is it database-related?

- Prisma schema change → `packages/db/prisma/schema.prisma` — the only place
- New migration → generated by running `prisma migrate` from `packages/db/`; lands in `packages/db/prisma/migrations/`
- PrismaClient configuration → `packages/db/src/client.ts`
- API-layer DB wrapper or helper → `apps/api/src/db/`
- **Never put a Prisma schema or migration in `apps/api/`.**

### 7.7 Is it a new API route, controller, or service?

- Route definition → `apps/api/src/routes/`
- Request handler → `apps/api/src/controllers/`
- Business logic → `apps/api/src/services/`
- Middleware (auth, logging, error) → `apps/api/src/middleware/`

### 7.8 Is it a new frontend page or layout?

- Next.js App Router page or layout → `apps/web/src/app/`
- Feature module (colocated components, hooks, and types for one feature) → `apps/web/src/features/<feature-name>/`
- Global styles → `apps/web/src/styles/`
- Static asset → `apps/web/public/`

### 7.9 Is it a CI/CD workflow or GitHub configuration?

- GitHub Actions workflow → `.github/workflows/`
- Issue template → `.github/ISSUE_TEMPLATE/`
- PR template → `.github/pull_request_template.md`

### 7.10 Is it experimental or a prototype?

- Exploratory notes → `docs/experiments/`
- Prototype code (not production) → create `docs/experiments/<topic>/` for write-ups
- **Never create `file v2.ts`, `file copy.ts`, or `file 2.ts` anywhere in the repo.**
- If you need to test a new approach against existing code, prototype in isolation; when it works, copy the proven logic into the canonical location and remove the experiment.

### 7.11 Is it a new shared workspace package?

- Create `packages/<package-name>/` with:
  - `package.json` (name: `@repo/<package-name>`)
  - `tsconfig.json` (extends the appropriate `@repo/typescript-config` preset)
  - `src/index.ts` (public exports)
- Do not add it anywhere else; do not put it under `apps/`.

### 7.12 Is it a Claude Code agent, command, or skill?

- Sub-agent definition → `.claude/agents/`
- Slash command definition → `.claude/commands/`
- Reusable prompt template → `.claude/Prompts/`
- Skill definition → `.claude/skills/<skill-name>/SKILL.md`
- Skill reference files → `.claude/skills/<skill-name>/references/` (one level deep only — reference files must NOT reference other reference files)
- Skill evaluation scenarios → `.claude/skills/<skill-name>/evals/`
- Cognitive profile → `.claude/profiles/`

### If none of the above match:

**Ask the user.** Do not guess. Do not create a new top-level directory without an explicit architectural decision.

---

## 8. Anti-Patterns (Explicitly Banned)

These patterns are detected by `scripts/maintenance/check-repo-structure.sh` and will cause CI to fail.

**Root clutter:**

- No random `.sh`, `.py`, `.ts`, or `.md` files at root beyond the canonical whitelist in Section 2.1.
- Reports → `docs/reports/`
- Scripts → `scripts/`
- Plans and notes → appropriate `docs/` subdirectory

**Duplicate files:**

- No `file 2.ts`, `file v2.ts`, `file copy.ts` anywhere in the repo.
- These are macOS Finder artifacts or lazy experimentation — both are unacceptable in production directories.
- For new approaches: prototype in `docs/experiments/`, then copy the proven logic to the canonical location.

**Misplaced Prisma:**

- No `schema.prisma` or `migrations/` outside `packages/db/prisma/`.

**Loose scripts in source directories:**

- No `debug.ts`, `test_script.ts`, or one-off `.sh` files inside `apps/` or `packages/` source trees.
- Debug scripts → `apps/<app>/scripts/` with a descriptive name.

**Sandbox violations:**

- No committed imports of files from `docs/experiments/` in production code.

**Mixed concerns:**

- No infrastructure configuration inside `apps/` or `packages/`.
- No production code in `docs/experiments/`.

---

## 9. Automated Enforcement

All checks run automatically on every commit via `lefthook.yml` and in CI via `.github/workflows/ci.yml`.

### 9.1 Pre-Commit Hooks (Local)

Config: `lefthook.yml`

| Hook        | What It Catches                                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| `lint`      | ESLint errors across all apps and packages                                                                       |
| `format`    | Prettier formatting violations                                                                                   |
| `structure` | Duplicate files, root clutter, loose scripts, Sandbox violations (`scripts/maintenance/check-repo-structure.sh`) |

**Setup (one-time after cloning):**

```bash
pnpm install   # installs lefthook automatically via postinstall
```

**Run structure check manually at any time:**

```bash
bash scripts/maintenance/check-repo-structure.sh
```

**Bypassing hooks:**
`git commit --no-verify` skips all local hooks. CI will still fail if violations exist.

### 9.2 CI Checks (PR-Level)

Config: `.github/workflows/ci.yml`
Runs on: every PR to `main`

Re-runs the full quality suite in a clean environment: lint, typecheck, tests, and structure checks. A PR cannot merge if CI fails.

---

## 10. Architecture Decision Records (ADRs)

When a significant architectural decision is made, record it permanently.

- **Location:** `docs/architecture/decisions/ADR-<number>-<title>.md`

**Template:**

```markdown
# ADR-XXX: <Decision Title>

## Status

Accepted | Superseded by ADR-YYY | Proposed

## Context

[What situation or constraint forced this decision?]

## Decision

[What did we decide?]

## Consequences

**Positive:**

- Benefit 1

**Negative:**

- Tradeoff 1

## Alternatives Considered

1. Option A — rejected because…
2. Option B — rejected because…
```

**Lifecycle:** ADRs are never deleted. If superseded, update the Status field to reference the newer ADR.

---

## 11. How to Evolve This Document

When the structure of the repository changes:

1. Update this file first: root whitelist (Section 2), directory tree (Section 3), decision tree (Section 7).
2. Update `scripts/maintenance/check-repo-structure.sh` so the `ALLOWED_DOCS`, `ALLOWED_CONFIGS`, and `ALLOWED_DIRS` arrays match Section 2.
3. Update `CLAUDE.md` codebase map so AI agents stay aligned with the new structure.
4. Update `AGENTS.md` if the change affects review scope.
5. Add a `docs/lessons/LESSONS.md` entry if the structural change carries a lesson worth capturing.

If this file and any local README disagree, **this file wins** — it is the canonical truth. Fix the README.
