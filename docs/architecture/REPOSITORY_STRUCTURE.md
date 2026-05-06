# Repository Structure & File Placement

**Last Updated**: 2026-05-02
**Status**: Active
**Version**: 2.0

> **Single source of truth for where everything lives in this monorepo.**
> Before creating, moving, or deleting any file: read the Decision Tree (Section 6) and confirm the destination. If unsure, ask the user.
> CI will fail if violations are detected (`scripts/maintenance/check-repo-structure.sh`).

---

## 1. Root Whitelist

The repo root is clean and predictable. Only whitelisted files and directories belong here. The enforcement script (`scripts/maintenance/check-repo-structure.sh`) validates this on every commit.

### Allowed Files at Root

| File                           | Purpose                                                                       |
| ------------------------------ | ----------------------------------------------------------------------------- |
| `README.md`                    | Project overview                                                              |
| `CLAUDE.md`                    | AI agent operating rules for Claude Code                                      |
| `AGENTS.md`                    | OpenAI Codex agent configuration                                              |
| `CONTRIBUTING.md`              | Contribution guidelines                                                       |
| `CODE_OF_CONDUCT.md`           | Code of conduct                                                               |
| `SECURITY.md`                  | Security policy                                                               |
| `CHANGELOG.md`                 | Changelog (user-authored)                                                     |
| `ROADMAP.md`                   | Roadmap of upcoming work (user-authored)                                      |
| `LICENSE` / `LICENSE.template` | MIT license (Thinking Hand Studio LLC); `.template` is kernel-renderer source |
| `package.json`                 | Root workspace config, shared devDependencies                                 |
| `pnpm-workspace.yaml`          | Workspace globs: `apps/*`, `packages/*`                                       |
| `pnpm-lock.yaml`               | Lockfile (auto-generated, never edit)                                         |
| `turbo.json`                   | Turborepo task pipeline                                                       |
| `prettier.config.js`           | Root Prettier config (must be at root)                                        |
| `lefthook.yml`                 | Git hook config (lint, format, structure)                                     |
| `vitest.config.ts`             | Root Vitest config with project references                                    |
| `eslint.config.mjs`            | Root ESLint 9 flat config                                                     |
| `.prettierignore`              | Prettier exclusions                                                           |
| `.env.example`                 | Template for `.env.local` (no real secrets)                                   |
| `.env.local`                   | Real environment variables (gitignored)                                       |
| `.env.consultant`              | Consultant env reference (gitignored, read-only subset credentials only)      |
| `.editorconfig`                | Cross-editor indent/line-ending baseline                                      |
| `.nvmrc`                       | Pins Node.js version (22.x)                                                   |
| `.gitignore`                   | Standard ignore rules                                                         |
| `.gitattributes`               | Git attribute rules, line endings (optional, created when needed)             |
| `.worktreeinclude`             | Claude Code worktree env file declarations (which `.env*` files to copy)      |
| `greptile.json`                | Greptile AI code-reviewer config (must be at root per Greptile's spec)        |

Note: v2.1 (BL-247) decommissioned the `*.template.*` root files. The v2.x kernel renderer at `plugins/launchpad/scripts/plugin_default_generators/kernel_renderer/` ships templated equivalents for `README`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY`, and `LICENSE`. `CHANGELOG.md`, `ROADMAP.md`, and `greptile.json` are now user-authored; no v2.x kernel template ships for them (v2.2 BL). See `docs/maintainers/decommission-history.md`.

### Allowed Directories at Root

| Directory                                               | Purpose                                                                        |
| ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `apps/`                                                 | User-facing applications (web, api)                                            |
| `packages/`                                             | Shared internal libraries (db, shared, ui, eslint-config, typescript-config)   |
| `scripts/`                                              | Repo-wide maintenance and automation                                           |
| `docs/`                                                 | Centralized documentation hub                                                  |
| `plugins/launchpad/`                                    | The LaunchPad plugin (commands/, agents/, skills/, .claude-plugin/plugin.json) |
| `.claude-plugin/`                                       | Marketplace manifest (marketplace.json) — points at plugins/launchpad/         |
| `.github/`                                              | GitHub Actions, issue/PR templates                                             |
| `.vscode/`                                              | Shared editor settings                                                         |
| `.claude/`                                              | Project-local Claude config (hooks/, settings.json, Prompts/, profiles/)       |
| `.launchpad/`                                           | Harness metadata — agent lists, secret patterns (upstream-synced)              |
| `.harness/`                                             | Runtime artifacts — todos, observations, design artifacts                      |
| `node_modules/`, `.turbo/`, `.next/`, `dist/`, `build/` | Build/cache artifacts (gitignored)                                             |
| `.git/`                                                 | Git internals                                                                  |

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
└── setup/                                   # v2.1 (BL-247) signpost stubs only; install via marketplace

docs/                                        # See Decision Tree (Section 6.1) for routing
├── architecture/                            # System design, ADRs (decisions/ created when needed), tech stack
├── plans/                                   # Implementation plans, phased roadmaps
├── releases/                                # Hand-authored release notes per tag (vX.Y.Z.md)
├── reports/                                 # Investigation reports, audits, postmortems
├── tasks/                                   # Active work: BACKLOG.md, section specs
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
│   ├── design/                              # Design review agents
│   │   ├── design-alignment-checker.md      # Verifies design-to-spec fidelity
│   │   ├── design-implementation-reviewer.md # Reviews design implementation quality
│   │   ├── design-iterator.md               # Iterates designs based on feedback
│   │   ├── design-responsive-auditor.md     # Audits responsive behavior across viewports
│   │   ├── design-ui-auditor.md             # Audits UI against design system tokens
│   │   └── figma-design-sync.md             # Syncs design artifacts from Figma
│   ├── research/                            # Read-only research agents
│   ├── resolve/                             # Fix agents (todos, PR comments)
│   ├── review/                              # Code review agents
│   └── skills/                              # Skill evaluation agents
├── commands/                                # Slash command definitions
│   ├── copy.md                              # Reads copy brief and provides copy context
│   ├── copy-review.md                       # Dispatches copy review agents
│   ├── design-onboard.md                    # Design onboarding flows and empty states
│   ├── design-polish.md                     # Pre-ship design refinement pass
│   ├── design-review.md                     # Comprehensive design quality audit
│   └── feature-video.md                     # Record feature video walkthrough
├── skills/                                  # One directory per skill
│   ├── frontend-design/                     # Distinctive, production-grade UI creation
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── color-and-contrast.md
│   │       ├── interaction-design.md
│   │       ├── motion-design.md
│   │       ├── responsive-design.md
│   │       ├── spatial-design.md
│   │       ├── typography.md
│   │       └── ux-writing.md
│   ├── imgup/                               # Lightweight image hosting for quick sharing
│   │   └── SKILL.md
│   ├── rclone/                              # Cloud file management via rclone
│   │   └── SKILL.md
│   ├── responsive-design/                   # Responsive-first thinking for specs
│   │   └── SKILL.md
│   ├── web-design-guidelines/               # Engineering compliance checklist for web UI
│   │   └── SKILL.md
│   └── <skill-name>/
│       ├── SKILL.md                         # Orchestrator (<500 lines)
│       ├── references/                      # On-demand reference files (ONE level deep only)
│       └── evals/                           # Evaluation scenarios (>=3 per skill)
├── Prompts/                                 # Reusable prompt templates
├── profiles/                                # Cognitive profiles
├── settings.json                            # Project-level hooks (committed)
└── settings.local.json                      # Local settings (gitignored)

.harness/                                    # Runtime workspace — everything ephemeral except harness.local.md
├── harness.local.md                         # ONLY tracked file — project review/design context for agents
├── design-artifacts/                        # Approved design screenshots (ephemeral, created on demand)
├── observations/                            # Deferred observations for backlog (ephemeral)
├── screenshots/                             # Browser test / feature-video screenshots (ephemeral)
└── todos/                                   # Review findings to triage (ephemeral)

plugins/launchpad/                           # The LaunchPad plugin source
├── .claude-plugin/plugin.json               # Plugin manifest (name, version, marketplace metadata)
├── commands/                                # /lp-* slash command markdown definitions
├── agents/                                  # Sub-agents (research/, review/, resolve/, design/, skills/, document-review/)
├── skills/                                  # Plugin skills (lp-*/SKILL.md + references/ + evals/)
├── scaffolders/                             # v2.0 per-stack pattern docs with knowledge-anchor `last_validated:` + sha256 pins
│                                            #   (astro/django/eleventy/expo/fastapi/hono/hugo/next/rails/supabase)
└── scripts/                                 # Plugin runtime — Python helpers + adapters + tests
    ├── plugin-*.py / plugin-*.sh            # Top-level plugin entry points (build runner, config hash, doc generator,
    │                                        #   prereq check, scaffold receipt loader, stack detector, v2 handshake lint, ...)
    ├── lp_pick_stack/                       # v2.0 pick-stack consumer — 5-question funnel, category match,
    │                                        #   rationale generation, brainstorm-summary frontmatter validation,
    │                                        #   sealed scaffold-decision.json write
    ├── lp_scaffold_stack/                   # v2.0 scaffold-stack consumer — decision validation (12 rules),
    │                                        #   marker consumption, layer materialization, receipt write,
    │                                        #   nonce ledger, rejection logger
    ├── plugin_stack_adapters/               # v2.0 per-stack /lp-define adapters (10 stacks: astro, next,
    │                                        #   python_django, fastapi, rails, hugo, eleventy, expo, hono,
    │                                        #   supabase + generic + polyglot composer)
    ├── _vendor/                             # Vendored Python deps (pinned, no network at runtime)
    └── tests/                               # pytest suites — adapter coverage, joint pipeline smoke,
                                             #   handshake invariants, layer materializer, build runner
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
| `docs/releases/`       | Hand-authored release notes per tagged version (`vX.Y.Z.md`)                |
| `docs/reports/`        | Investigation reports, audits, postmortems                                  |
| `docs/skills-catalog/` | Skill index, usage tracking, catalog                                        |
| `docs/solutions/`      | Categorized learnings from compound loops                                   |
| `docs/tasks/`          | Active work: BACKLOG.md, section specs                                      |
| `docs/ui/`             | UI/UX design documentation                                                  |

---

## 6. Decision Tree: Where Does My File Go?

Walk through in order. Stop at the first match.

### 6.1 Documentation

- Architecture doc, ADR, tech overview → `docs/architecture/`
- ADR → `docs/architecture/decisions/ADR-<number>-<title>.md` (never delete; if superseded, update Status)
- Implementation plan or roadmap → `docs/plans/`
- Section spec (from `/lp-shape-section`) → `docs/tasks/sections/`
- Backlog or task tracking → `docs/tasks/`
- Lessons learned → append to `docs/lessons/LESSONS.md` (append-only, never rewrite)
- Categorized solution from compound loop → `docs/solutions/`
- Brainstorming document → `docs/brainstorms/`
- Session handoff document → `docs/handoffs/`
- Investigation report, audit, postmortem → `docs/reports/YYYY-MM-DD-<topic>.md`
- Hand-authored release notes for a tag → `docs/releases/v<MAJOR>.<MINOR>.<PATCH>.md`
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
- Project init or upstream sync → `scripts/setup/` is v2.1-decommissioned (signpost stubs only); install via marketplace + `/lp-brainstorm`-pipeline (BL-247)
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

- Agent → `plugins/launchpad/agents/<namespace>/<name>.md`
- Command → `plugins/launchpad/commands/<name>.md`
- Skill → `plugins/launchpad/skills/<skill-name>/SKILL.md`
- Skill references → `plugins/launchpad/skills/<skill-name>/references/` (one level deep only)
- Skill evals → `plugins/launchpad/skills/<skill-name>/evals/`
- Prompt template → `.claude/Prompts/` (project-local, not plugin content)
- Profile → `.claude/profiles/` (project-local, not plugin content)

### 6.14 v2.0 pipeline modules (plugin-internal Python)

The v2.0 greenfield pipeline (`/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`) is implemented as Python modules under `plugins/launchpad/scripts/`. New runtime code for the pipeline goes here, not at root, not in `apps/`, not in `packages/`.

- Pick-stack consumer logic (5-question funnel, category match, rationale rendering, brainstorm-summary validation, sealed `scaffold-decision.json` write) → `plugins/launchpad/scripts/lp_pick_stack/`
- Scaffold-stack consumer logic (decision validation, marker consumption, layer materialization, receipt write, nonce ledger, rejection logger) → `plugins/launchpad/scripts/lp_scaffold_stack/`
- Per-stack `/lp-define` adapter (one of: `astro`, `next`, `python_django`, `fastapi`, `rails`, `hugo`, `eleventy`, `expo`, `hono`, `supabase`) → `plugins/launchpad/scripts/plugin_stack_adapters/<stack>_adapter.py` (or `<stack>.py` for the generic/polyglot composers)
- Pipeline-wide primitives shared across consumers (`cwd_state.py`, `path_validator.py`, `safe_run.py`, `decision_integrity.py`, `pid_identity.py`, `telemetry_writer.py`, `knowledge_anchor_loader.py`) → `plugins/launchpad/scripts/` top level
- Per-stack pattern doc with `last_validated:` knowledge anchor and sha256 pins → `plugins/launchpad/scaffolders/<stack>-pattern.md`
- Pytest suite for any of the above → `plugins/launchpad/scripts/tests/test_<area>.py`

**Bind-via-receipt rule.** Cross-cutting wiring between layers happens through `scaffold-receipt.json` and the bound_cwd triple, NOT through inter-module imports across the consumer boundary. `lp_pick_stack/` writes the sealed decision; `lp_scaffold_stack/` reads it via `plugin-scaffold-receipt-loader.py`. Adding a direct import from `lp_scaffold_stack` into `lp_pick_stack` (or vice-versa) breaks the chain-of-custody invariant — route through the receipt instead.

**Vendoring boundary.** Python dependencies for plugin runtime live under `plugins/launchpad/scripts/_vendor/` (pinned, no network at install time). `plugin_stack_adapters/_vendor/` is permitted for adapter-specific vendored deps. Never `pip install` at runtime.

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
