# Launchpad – Claude Instructions

> **Harness scope:** Full-stack monorepo with a **TypeScript/Next.js frontend** and a **Hono API backend**, managed with Turborepo and pnpm workspaces. Adapt section headers and placeholder values if your topology differs.

> **Extends `~/.claude/CLAUDE.md` (global).** Core principles, secret management, Context7, sub-agent rules, and Excalidraw notes live there and apply here automatically. This file adds **project-specific context only** — do not repeat global rules.

---

## WHY – Project Purpose

<!-- 2–4 sentences. What problem does this solve? Who are the users? What's the core value prop?   -->
<!-- This anchors every decision Claude makes — keep it here, not in a linked doc.                 -->

{{PROJECT_PURPOSE}}

---

## WHAT – Tech Stack

<!-- List primary technologies + versions only. Enough for Claude to choose the right tools.       -->
<!-- Full detail lives in docs/architecture/TECH_STACK.md — link to it, don't duplicate.           -->

- **Frontend:** Next.js 15 App Router, Tailwind CSS v4, TypeScript 5
- **Backend:** Hono (Node.js), TypeScript 5
- **Database:** PostgreSQL via Prisma (in packages/db)
- **Infrastructure:** Vercel (web), your choice (API)

> Full breakdown → `docs/architecture/TECH_STACK.md`
> Product requirements → `docs/architecture/PRD.md`

### Codebase Map

<!-- One line per top-level directory. Enough for Claude to know where to look without reading everything. -->

```
/
├── apps/web/       # Next.js 15 frontend (App Router, Tailwind v4)
├── apps/api/       # Hono API server (CORS, /health endpoint)
├── packages/db/    # Prisma schema, client singleton, migrations
├── packages/shared/# Shared TypeScript types and utilities
├── packages/ui/    # Shared React components + Tailwind config + cn() helper
├── docs/           # Architecture docs, plans, reports, experiments
│   ├── tasks/      # BACKLOG.md + sections/ (section specs from /shape-section)
│   └── skills-catalog/ # Skill usage tracking and user-facing index
├── .harness/       # Runtime directory (todos, observations, design-artifacts, screenshots)
├── .launchpad/     # Harness config (agents.yml, version, secret-patterns.txt)
└── scripts/        # Build pipeline, maintenance, agent hydration
```

> Before creating, moving, or deleting any file: check `docs/architecture/REPOSITORY_STRUCTURE.md`
> for the layout decision tree (Section 6).

---

## HOW – Development Commands

<!-- Only commands Claude needs to do meaningful work every session. No exhaustive lists.           -->
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

**Linting & formatting** are handled by ESLint + Prettier — Claude must not manually fix style.
Auto-fix command: `pnpm format`

### Definition of Done

Claude must confirm all three before closing a task:

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
| Create files without checking structure    | Read `docs/architecture/REPOSITORY_STRUCTURE.md` Section 6 | CI enforces structure compliance     |
| Use `prisma migrate dev`                   | Use `prisma migrate deploy` from `packages/db/`            | Prevents destructive dev migrations  |
| Create ` 2`/` copy`/` v2` files            | Use `docs/experiments/<topic>/` for prototypes             | Finder artifacts break CI            |
| Bypass pre-commit hooks with `--no-verify` | Fix the issue, then commit                                 | CI will catch it anyway              |

---

## Progressive Disclosure

<!-- Claude reads these only when the task is relevant — never all upfront.                       -->
<!-- Pointers only. Never copy content here — it will go stale. No inline code snippets.          -->

| Doc                                        | Read When                                           |
| ------------------------------------------ | --------------------------------------------------- |
| `docs/architecture/PRD.md`                 | Understanding feature intent or product scope       |
| `docs/architecture/APP_FLOW.md`            | Working on navigation, auth flow, or user journeys  |
| `docs/architecture/TECH_STACK.md`          | Evaluating or adding dependencies                   |
| `docs/architecture/BACKEND_STRUCTURE.md`   | Modifying API routes, services, or data models      |
| `docs/architecture/FRONTEND_GUIDELINES.md` | Building or refactoring UI components               |
| `docs/architecture/DESIGN_SYSTEM.md`       | Defining UI components or visual design decisions   |
| `docs/architecture/CI_CD.md`               | Configuring CI/CD pipelines or deployment           |
| `docs/skills-catalog/skills-index.md`      | Managing, reviewing, or auditing installed skills   |
| `docs/guides/HOW_IT_WORKS.md`              | Understanding the full pipeline workflow            |
| `docs/guides/METHODOLOGY.md`               | Understanding the harness architecture layers       |
| `.claude/skills/creating-agents/SKILL.md`  | Creating new agents or converting skills to agents  |
| `.launchpad/agents.yml`                    | Configuring review agent lists                      |
| `.harness/harness.local.md`                | Viewing or updating project-specific review context |
| `docs/tasks/BACKLOG.md`                    | Checking project backlog and deferred items         |

---

## Available Sub-Agents

Agents are organized into 6 namespace subdirectories under `.claude/agents/`:

### research/ — Read-only documentarians

| Agent                  | Purpose                                                                          |
| ---------------------- | -------------------------------------------------------------------------------- |
| `file-locator`         | Find WHERE files and components live (super Grep/Glob/LS)                        |
| `code-analyzer`        | Understand HOW specific code works with file:line precision                      |
| `pattern-finder`       | Find existing patterns and code examples to model after                          |
| `docs-locator`         | Find relevant docs by frontmatter, date-prefixed filenames, directory structure  |
| `docs-analyzer`        | Extract decisions, rejected approaches, constraints, promoted patterns from docs |
| `web-researcher`       | External documentation, API references, and best practices                       |
| `learnings-researcher` | Search docs/solutions/ for relevant past solutions by frontmatter metadata       |

### skills/

| Agent             | Purpose                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `skill-evaluator` | Evaluate generated skills against 16 quality criteria (3-pass: first-principles, baseline detection, Anthropic checklist) |

### review/ — Code review agents

| Agent                           | Purpose                                                         |
| ------------------------------- | --------------------------------------------------------------- |
| `security-auditor`              | Security vulnerabilities, auth/authz, OWASP compliance          |
| `kieran-foad-ts-reviewer`       | TypeScript code quality, patterns, and maintainability          |
| `performance-auditor`           | Performance bottlenecks, algorithmic complexity, memory usage   |
| `code-simplicity-reviewer`      | YAGNI violations, unnecessary abstractions, simplification      |
| `architecture-strategist`       | Architectural patterns, design integrity, structural compliance |
| `testing-reviewer`              | Test coverage, test quality, testing patterns                   |
| `spec-flow-analyzer`            | Spec completeness, user flow gaps, edge case discovery          |
| `schema-drift-detector`         | Unrelated schema.rb changes vs included migrations              |
| `data-migration-auditor`        | Data migration safety, rollback procedures                      |
| `data-integrity-auditor`        | Database constraints, transaction boundaries, data consistency  |
| `deployment-verification-agent` | Deployment checklists, rollback procedures (opt-in)             |
| `frontend-races-reviewer`       | JS race conditions, timing issues, DOM lifecycle (opt-in)       |
| `kieran-foad-python-reviewer`   | Python code quality (opt-in)                                    |

### document-review/ — Plan document reviewers

| Agent                           | Purpose                                                  |
| ------------------------------- | -------------------------------------------------------- |
| `adversarial-document-reviewer` | Red-team attack on plan assumptions and blind spots      |
| `coherence-reviewer`            | Internal consistency and logical flow of plan documents  |
| `feasibility-reviewer`          | Technical feasibility and resource estimation validation |
| `scope-guardian-reviewer`       | Scope creep detection and boundary enforcement           |
| `product-lens-reviewer`         | Product strategy alignment and user value assessment     |
| `security-lens-reviewer`        | Security implications in plan design decisions           |
| `design-lens-reviewer`          | Design quality and UI/UX implications (conditional)      |

### resolve/ — Automated fixers

| Agent                   | Purpose                                               |
| ----------------------- | ----------------------------------------------------- |
| `harness-todo-resolver` | Fix individual review findings from `.harness/todos/` |
| `pr-comment-resolver`   | Address PR review comments with code changes          |

### design/ — Design workflow agents

| Agent                            | Purpose                                                        |
| -------------------------------- | -------------------------------------------------------------- |
| `figma-design-sync`              | Sync implementation with Figma designs via Figma MCP           |
| `design-implementation-reviewer` | Compare live UI against Figma specs (report-only)              |
| `design-iterator`                | Iterative screenshot-analyze-improve cycles (ONE change/cycle) |
| `design-ui-auditor`              | Quick 5-check UI audit with P1/P2/P3 severity                  |
| `design-responsive-auditor`      | 6-check responsive audit with P1/P2/P3 severity                |
| `design-alignment-checker`       | 14-dimension design alignment audit against DESIGN_SYSTEM.md   |
