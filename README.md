# Project Template

A batteries-included monorepo template for full-stack TypeScript applications, designed for AI-first development with Claude Code, Codex, and autonomous compound loops.

![Node.js](https://img.shields.io/badge/Node.js-22.x-339933?logo=node.js&logoColor=white)
![pnpm](https://img.shields.io/badge/pnpm-9.x-F69220?logo=pnpm&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue)

---

## What Is This?

This is a **GitHub template repository**. It is not a library, not a framework, and not something you clone. You use it to create new projects with a single click.

**How to use it:**

1. Click the green **"Use this template"** button at the top of this repository (or use **"Create a new repository"** from the dropdown).
2. Name your new repository. Choose public or private.
3. GitHub creates a fresh repository with all the template files but **no git history** and **no link back to this template**.
4. Clone your new repository and start building.

Alternatively, use the GitHub CLI:

```bash
gh repo create my-new-project \
  --template OWNER/project-template \
  --private \
  --clone
```

The `--template` flag creates a clean copy. You get the full directory structure, all configuration files, CI workflows, AI agent instructions, and compound automation scripts -- with a blank commit history.

---

## Quick Start

### 1. Create your repository

Use the GitHub template button or the CLI command above.

### 2. Install dependencies

```bash
cd my-new-project
corepack enable          # Enables pnpm via Corepack
pnpm install             # Installs all workspace dependencies + sets up git hooks
```

### 3. Set up environment variables

```bash
cp .env.example .env.local
# Edit .env.local with your actual values
```

### 4. Start development

```bash
pnpm dev                 # Starts all apps via Turborepo
```

The web app runs on `http://localhost:3000` and the API on `http://localhost:3001` (ports may vary based on your configuration).

### 5. Trim what you do not need

This template is comprehensive by design. Delete what your project does not require:

| If you do not need... | Delete these        | Also remove from                                    |
| --------------------- | ------------------- | --------------------------------------------------- |
| Backend API           | `apps/api/`         | `turbo.json` tasks, `pnpm-workspace.yaml` if needed |
| Database / Prisma     | `packages/db/`      | `@repo/db` references in `apps/api/package.json`    |
| Compound automation   | `scripts/compound/` | --                                                  |
| Shared UI library     | `packages/ui/`      | `@repo/ui` references in `apps/web/package.json`    |

A dedicated `trim.sh` script for automated project customization is planned.

---

## Tech Stack

| Layer               | Technology                                                                                            |
| ------------------- | ----------------------------------------------------------------------------------------------------- |
| **Frontend**        | [Next.js 15](https://nextjs.org/) App Router, [Tailwind CSS v4](https://tailwindcss.com/), TypeScript |
| **Backend**         | [Hono](https://hono.dev/) (lightweight, edge-first TypeScript framework)                              |
| **Database**        | [Prisma](https://www.prisma.io/) ORM with PostgreSQL                                                  |
| **Monorepo**        | [Turborepo](https://turbo.build/) for task orchestration                                              |
| **Package Manager** | [pnpm](https://pnpm.io/) 9.x with workspaces                                                          |
| **Linting**         | ESLint 9 (flat config) + Prettier                                                                     |
| **Testing**         | [Vitest](https://vitest.dev/)                                                                         |
| **Git Hooks**       | [Lefthook](https://github.com/evilmartians/lefthook)                                                  |
| **CI/CD**           | GitHub Actions                                                                                        |

---

## Repository Structure

```
project-template/
|
+-- apps/                                    # User-facing applications
|   +-- web/                                 # Next.js 15 App Router frontend
|   |   +-- public/                          # Static assets served at /
|   |   +-- src/
|   |   |   +-- app/                         # App Router: pages, layouts, route groups
|   |   |   +-- components/                  # Page-level and layout-level React components
|   |   |   +-- features/                    # Feature-scoped modules (colocated logic, hooks, types)
|   |   |   +-- hooks/                       # Shared custom React hooks
|   |   |   +-- lib/                         # Client-side helpers, fetchers, SDK wrappers
|   |   |   +-- styles/                      # Global CSS, Tailwind base config
|   |   |   +-- types/                       # App-local TypeScript types
|   |   +-- tests/                           # Vitest tests for the web app
|   |   +-- next.config.ts
|   |   +-- tsconfig.json
|   |   +-- package.json
|   |
|   +-- api/                                 # Hono backend service
|       +-- src/
|       |   +-- config/                      # Env loading, app-wide constants
|       |   +-- routes/                      # Route definitions
|       |   +-- controllers/                 # Request handlers
|       |   +-- services/                    # Business logic
|       |   +-- middleware/                   # Auth, logging, error handling
|       |   +-- types/                       # API-local TypeScript types
|       |   +-- index.ts                     # App entry point
|       +-- tests/
|       +-- tsconfig.json
|       +-- package.json
|
+-- packages/                                # Shared internal libraries
|   +-- db/                                  # Prisma package (single source of DB truth)
|   +-- shared/                              # Shared TypeScript types and pure utilities
|   +-- ui/                                  # Shared React component library
|   +-- eslint-config/                       # Shared ESLint configuration
|   +-- typescript-config/                   # Shared TypeScript tsconfig presets
|
+-- scripts/                                 # Repo-wide automation scripts
|   +-- agent_hydration/
|   |   +-- hydrate.sh                       # Outputs essential docs for AI agent context
|   +-- compound/                            # Compound Product pipeline scripts
|   |   +-- auto-compound.sh                 # Full pipeline: report -> PRD -> tasks -> loop -> PR
|   |   +-- loop.sh                          # Execution loop with run archiving
|   |   +-- analyze-report.sh               # LLM-powered report analysis
|   |   +-- config.json                      # Compound pipeline configuration
|   |   +-- iteration-prompt.md              # Per-iteration instructions for the AI agent
|   |   +-- knowledge-base.md               # Accumulated patterns from compound loops
|   +-- maintenance/
|       +-- check-repo-structure.sh          # Validates repo against REPOSITORY_STRUCTURE.md
|
+-- docs/                                    # Centralized documentation hub
|   +-- architecture/                        # System design, ADRs, this structure doc
|   +-- plans/                               # Implementation plans and roadmaps
|   +-- tasks/                               # Active work tracking (TODO.md)
|   +-- reports/                             # Investigation reports, audits, postmortems
|   +-- lessons/                             # Running log of lessons learned
|   +-- solutions/                           # Categorized learnings from compound loops
|   +-- brainstorms/                         # Brainstorming documents
|   +-- experiments/                         # Exploratory notes (not production code)
|   +-- articles/                            # Long-form reference articles
|   +-- consultants/                         # External consultant deliverables
|   +-- eval/                                # Evaluation reports (front-end / back-end)
|   +-- ui/                                  # UI/UX design documentation
|   +-- archive/                             # Retired docs (permanent, read-only)
|
+-- .github/                                 # GitHub Actions workflows, issue/PR templates
|   +-- workflows/
|   |   +-- ci.yml                           # Lint, typecheck, test on every PR
|   |   +-- deploy.yml                       # Build + deploy on merge to main
|   +-- ISSUE_TEMPLATE/
|   +-- pull_request_template.md
|
+-- .claude/                                 # Claude Code configuration
|   +-- commands/                            # Slash commands (/define-product, /create_plan, etc.)
|   +-- skills/                              # Skills (prd, tasks)
|   +-- agents/                              # Sub-agent definitions
|   +-- Prompts/                             # Reusable prompt templates
|
+-- CLAUDE.md                                # AI instructions for Claude Code
+-- AGENTS.md                                # AI instructions for Codex, Gemini, Cursor, etc.
+-- CONTRIBUTING.md                          # Human contribution rules and PR process
+-- README.md                                # This file
+-- package.json                             # Root workspace config
+-- pnpm-workspace.yaml                      # Workspace globs: apps/*, packages/*
+-- turbo.json                               # Turborepo task pipeline
+-- lefthook.yml                             # Git hook config (pre-commit: lint, format, structure)
+-- vitest.config.ts                         # Root Vitest config
+-- prettier.config.js                       # Root Prettier config
+-- .nvmrc                                   # Pins Node.js version (22.x)
+-- .env.example                             # Template for .env.local
```

The full annotated structure with file placement rules lives in `docs/architecture/REPOSITORY_STRUCTURE.md`. That document includes a decision tree (Section 7) that maps every file type to its correct directory.

---

## The Four Frameworks

This template integrates four complementary approaches to AI-assisted development. Two are included directly in the template; two are external tools you install separately.

### 1. Spec-Driven Development (INCLUDED)

**What it is:** A two-phase development workflow baked into the template's slash commands and skills.

**Phase A -- Define (interactive, human-guided):**

- `/define-product` -- Walk through structured Q&A to populate `docs/architecture/PRD.md` and `docs/architecture/TECH_STACK.md`
- `/define-architecture` -- Populate `APP_FLOW.md`, `BACKEND_STRUCTURE.md`, `FRONTEND_GUIDELINES.md`, and `CI_CD.md`

**Phase B -- Build (autonomous, agent-driven):**

- `/create_plan` -- Create a detailed implementation plan from a feature description
- `/implement_plan` -- Execute an existing plan phase by phase
- `/research_codebase` -- Deep codebase research with parallel sub-agents

**The idea:** Before writing any code, fully specify what you are building via PRDs and architecture docs. This gives the AI agent complete context, reducing hallucination and scope creep. Then let the compound pipeline (below) execute the plan autonomously.

**Location:** `.claude/commands/` and `.claude/skills/`

### 2. Compound Product Pipeline (INCLUDED)

**What it is:** A full autonomous pipeline that takes a report, analyzes it for the top priority, generates a PRD, converts it to tasks, runs an execution loop, and opens a pull request.

**Origin:** Based on [Compound Product](https://github.com/snarktank/compound-product) by Ryan Carson / snarktank.

**How it works:**

```
Report --> analyze-report.sh --> Pick #1 priority --> Create branch
    --> Claude generates PRD --> Convert to prd.json --> loop.sh
    --> Iterate until all tasks pass --> Push + create PR
```

**Key scripts:**

- `scripts/compound/auto-compound.sh` -- Orchestrates the full pipeline
- `scripts/compound/loop.sh` -- Runs Claude Code repeatedly, one task per iteration, until all tasks in `prd.json` have `passes: true`
- `scripts/compound/analyze-report.sh` -- Sends a report to an LLM (Anthropic, OpenAI, OpenRouter, or AI Gateway) and returns a JSON priority analysis

**Location:** `scripts/compound/`

### 3. Ralph Pattern (INCLUDED)

**What it is:** The autonomous execution loop concept where each iteration gets a fresh AI context window. Memory persists across iterations via git commits, `progress.txt`, and `prd.json`.

**Origin:** Based on [Ralph](https://github.com/snarktank/ralph) by Geoffrey Huntley. See the [original article](https://ghuntley.com/ralph/).

**How it works:**

1. Read the current state (`prd.json`, `progress.txt`, knowledge base)
2. Pick the highest-priority incomplete task
3. Implement it
4. Run quality checks
5. Commit changes
6. Update progress log
7. If all tasks done, output `<promise>COMPLETE</promise>`
8. Otherwise, end the iteration -- the loop script starts a new one

The Ralph pattern is fully integrated into `loop.sh`, which includes archiving logic for previous runs. When the branch changes between runs, the previous `prd.json` and `progress.txt` are automatically archived.

**Location:** `scripts/compound/loop.sh`

### 4. Compound Engineering Plugin (EXTERNAL -- install separately)

**What it is:** A Claude Code plugin by Kieran Klaassen / Every that provides slash commands for planning, implementation, review, and compound learning cycles. It includes 29 agents, 22 commands, and 19 skills.

**This plugin is NOT included in the template.** You install it separately after creating your project.

**Install:**

```
/plugin marketplace add https://github.com/EveryInc/compound-engineering-plugin
/plugin install compound-engineering
```

**Commands it provides:**

- `/plan [feature]` -- Plan implementation for a feature
- `/lfg` -- Fully autonomous: plan + implement + review + commit
- `/review` -- Review recent changes and extract learnings
- `/compound` -- Full compound cycle: plan + work + review
- And more (22 commands total)

**How it integrates:** The plugin persists learnings into `CLAUDE.md` via its `/compound` step, building up project-specific knowledge over time. The template's spec-driven workflow (Phase A) pairs naturally with the plugin's execution commands (Phase B).

**GitHub:** https://github.com/EveryInc/compound-engineering-plugin

---

## AI-First Development Workflow

This template is designed to be used with AI coding assistants. Every major configuration file serves a purpose in the AI workflow.

### Session Bootstrapping

When starting a new AI session, hydrate the agent with minimal context:

```bash
./scripts/agent_hydration/hydrate.sh
```

Or use the slash command in Claude Code:

```
/Hydrate
```

The hydration script loads only **repo structure + active tasks** — the minimum needed to orient the agent. PRD, tech stack, and app READMEs are referenced in `CLAUDE.md`'s Progressive Disclosure table and loaded on-demand when a task requires them. This keeps session context lean.

### AI Instruction Files

| File        | Purpose                                                                      | Read by                                                    |
| ----------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `CLAUDE.md` | Project-specific rules, tech stack, guardrails, codebase map, slash commands | Claude Code                                                |
| `AGENTS.md` | Same structure as CLAUDE.md, adapted for other AI tools                      | OpenAI Codex, Gemini Code Assist, Cursor, Zed AI, OpenCode |

Both files are templates with placeholder values. After running `/define-product`, `CLAUDE.md` is automatically updated with your project's purpose and tech stack.

### The Full Workflow

**Phase A: Define your product (one-time setup)**

```
/define-product              # Answer questions about your product
/define-architecture         # Answer questions about your architecture
```

This populates six architecture docs that give the AI complete context about what you are building.

**Phase B: Build with compound automation**

Option 1 -- Interactive (you guide the AI):

```
/create_plan add user authentication
/implement_plan docs/plans/2026-03-01-user-auth.md
```

Option 2 -- Semi-autonomous (plugin-powered):

```
/plan add user authentication
/lfg
```

Option 3 -- Fully autonomous (compound pipeline):

```bash
# Write a report to docs/reports/ describing what needs to be done
# Then run the full pipeline:
./scripts/compound/auto-compound.sh
```

The pipeline reads the report, picks the top priority, creates a feature branch, generates a PRD, converts it to tasks, runs the execution loop, and opens a PR when done.

---

## Scripts Reference

### scripts/compound/

The compound automation pipeline. Requires: `claude` CLI, `gh` CLI, and `jq`.

| Script              | Purpose                                                                                                                                                              | Usage                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `auto-compound.sh`  | Full pipeline: find report, analyze, create PRD, convert to tasks, run loop, open PR                                                                                 | `./scripts/compound/auto-compound.sh [--dry-run]`    |
| `loop.sh`           | Execution loop with run archiving. Reads `prd.json`, iterates Claude Code until all tasks pass or max iterations reached. Archives previous runs when branch changes | `./scripts/compound/loop.sh [max_iterations]`        |
| `analyze-report.sh` | Sends a report file to an LLM and returns a JSON priority analysis. Supports Anthropic, OpenAI, OpenRouter, and AI Gateway                                           | `./scripts/compound/analyze-report.sh <report-path>` |

| File                  | Purpose                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `config.json`         | Compound pipeline configuration (reports dir, quality checks, max iterations, branch prefix)                                    |
| `iteration-prompt.md` | Instructions fed to Claude Code at each iteration: read state, pick task, implement, test, commit, update progress              |
| `knowledge-base.md`   | Accumulated patterns and learnings. Updated by agents during compound loops. Persists institutional knowledge across iterations |

### scripts/agent_hydration/

| Script       | Purpose                                                                                                                                                                 | Usage                                  |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `hydrate.sh` | Loads minimal session context (repo structure + active tasks) for AI agents. PRD, tech stack, and app READMEs are loaded on-demand via CLAUDE.md Progressive Disclosure | `./scripts/agent_hydration/hydrate.sh` |

### scripts/maintenance/

| Script                    | Purpose                                                                                                                                        | Usage                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `check-repo-structure.sh` | Validates repo against the rules in `REPOSITORY_STRUCTURE.md`. Checks for duplicate files, root clutter, loose scripts, and sandbox violations | `bash scripts/maintenance/check-repo-structure.sh` |

---

## Packages

All packages use the `@repo/` scope and are consumed via pnpm workspace dependencies.

### @repo/db (`packages/db/`)

The canonical Prisma package. Single source of truth for the database schema.

- `prisma/schema.prisma` -- Database schema (the only place Prisma schema lives)
- `prisma/migrations/` -- Migration history
- `src/client.ts` -- PrismaClient singleton
- `src/index.ts` -- Public exports

### @repo/shared (`packages/shared/`)

Shared TypeScript types and pure utility functions. No framework dependencies.

- `src/types/` -- Shared interfaces, enums, Zod schemas
- `src/utils/` -- Pure utility functions
- `src/index.ts` -- Public exports

### @repo/ui (`packages/ui/`)

Shared React component library. Intended for shadcn/ui components and custom shared UI.

- `src/components/` -- Shared UI components
- `src/styles/` -- Component-level styles
- `src/index.ts` -- Public exports
- Exports a `cn()` utility (clsx + tailwind-merge) for className composition
- Exports `tailwind.config.ts` so consuming apps can extend the shared Tailwind configuration

### @repo/eslint-config (`packages/eslint-config/`)

Shared ESLint configuration consumed by all apps and packages as a devDependency. Uses ESLint 9 flat config format with three exports:

- `base.js` -- Base rules for all TypeScript packages
- `next.js` -- Extends base with Next.js-specific rules
- `node.js` -- Extends base with Node.js-specific rules

### @repo/typescript-config (`packages/typescript-config/`)

Shared TypeScript configuration presets:

- `base.json` -- Strict baseline (target ESNext, bundler moduleResolution)
- `next.json` -- Extends base with JSX + Next.js plugin settings
- `node.json` -- Extends base with Node16 module resolution

---

## Configuration Files

### turbo.json

Turborepo task pipeline defining five tasks:

| Task        | Description                                              | Caching                        |
| ----------- | -------------------------------------------------------- | ------------------------------ |
| `build`     | Build all apps and packages (depends on upstream builds) | Cached (`.next/**`, `dist/**`) |
| `dev`       | Start dev servers for all apps                           | Not cached, persistent         |
| `lint`      | Run ESLint across all workspaces                         | Cached                         |
| `test`      | Run Vitest tests (depends on upstream builds)            | Cached                         |
| `typecheck` | TypeScript type checking (depends on upstream builds)    | Cached                         |

### lefthook.yml

Git hooks run automatically on every commit:

| Hook        | What it runs                                                   |
| ----------- | -------------------------------------------------------------- |
| `lint`      | `pnpm turbo lint --filter=[HEAD]` (lint only changed packages) |
| `format`    | `pnpm prettier --check .`                                      |
| `structure` | `bash scripts/maintenance/check-repo-structure.sh`             |

Hooks are installed automatically when you run `pnpm install`. Bypass with `git commit --no-verify` (CI will still catch violations).

### scripts/compound/config.json

Configuration for the compound automation pipeline:

```json
{
  "reportsDir": "./docs/reports",
  "outputDir": "./scripts/compound",
  "qualityChecks": ["pnpm typecheck", "pnpm test"],
  "maxIterations": 25,
  "branchPrefix": "compound/",
  "analyzeCommand": ""
}
```

| Field            | Description                                            | Default                           |
| ---------------- | ------------------------------------------------------ | --------------------------------- |
| `reportsDir`     | Directory containing report markdown files             | `./docs/reports`                  |
| `outputDir`      | Where `prd.json` and `progress.txt` are stored         | `./scripts/compound`              |
| `qualityChecks`  | Commands run after each task implementation            | `["pnpm typecheck", "pnpm test"]` |
| `maxIterations`  | Maximum loop iterations before stopping                | `25`                              |
| `branchPrefix`   | Prefix for automatically created branches              | `compound/`                       |
| `analyzeCommand` | Custom analysis script (overrides `analyze-report.sh`) | `""`                              |

### Environment Variables

Copy `.env.example` to `.env.local` and fill in your values. The `.env.local` file is gitignored and should never be committed.

```bash
cp .env.example .env.local
```

For compound automation, set at least one LLM provider key:

```bash
# Option 1: Anthropic (recommended)
ANTHROPIC_API_KEY=sk-ant-...

# Option 2: OpenAI
OPENAI_API_KEY=sk-...

# Option 3: OpenRouter
OPENROUTER_API_KEY=sk-or-...
```

---

## CI/CD

### CI Workflow (`.github/workflows/ci.yml`)

Runs on every pull request to `main` and on pushes to `main`.

**Steps:**

1. Checkout code
2. Set up pnpm 9 and Node.js (version from `.nvmrc`)
3. Install dependencies
4. Check repository structure
5. Run lint (`pnpm turbo lint`)
6. Run typecheck (`pnpm turbo typecheck`)
7. Run tests (`pnpm turbo test`)

A PR cannot merge if any step fails.

### Deploy Workflow (`.github/workflows/deploy.yml`)

Runs on pushes to `main` only.

**Steps:**

1. Checkout code
2. Set up pnpm 9 and Node.js
3. Install dependencies (frozen lockfile)
4. Build all apps and packages (`pnpm turbo build`)
5. Deploy (placeholder -- add your deployment step)

The deploy workflow uses `--frozen-lockfile` to ensure reproducible builds. You will need to add your actual deployment step (Vercel, Railway, etc.) to the workflow.

---

## Available Commands

### Development

```bash
pnpm dev          # Start all dev servers via Turborepo
pnpm build        # Build all apps and packages
pnpm lint         # Run ESLint across all workspaces
pnpm test         # Run Vitest tests
pnpm typecheck    # TypeScript type checking
pnpm format       # Format all files with Prettier
```

### Claude Code Slash Commands

| Command                | Description                                                                      |
| ---------------------- | -------------------------------------------------------------------------------- |
| `/Hydrate`             | Load minimal session context (repo structure + active tasks)                     |
| `/define-product`      | Interactive Q&A to populate PRD and tech stack docs                              |
| `/define-architecture` | Interactive Q&A to populate architecture docs                                    |
| `/create_plan`         | Create a detailed implementation plan                                            |
| `/implement_plan`      | Execute an existing implementation plan                                          |
| `/research_codebase`   | Deep codebase research with parallel sub-agents                                  |
| `/commit`              | Guided commit-to-PR workflow with branch guard, quality gates, and PR monitoring |

### Claude Code Skills

| Skill   | Trigger                                              | Description                                                      |
| ------- | ---------------------------------------------------- | ---------------------------------------------------------------- |
| `prd`   | "create a prd", "write prd for", "plan this feature" | Generate a Product Requirements Document                         |
| `tasks` | "convert prd", "create tasks", "prd to json"         | Convert a PRD markdown file to `prd.json` for the execution loop |

### Compound Engineering Plugin Commands (requires separate installation)

| Command           | Description                                          |
| ----------------- | ---------------------------------------------------- |
| `/plan [feature]` | Plan implementation for a feature                    |
| `/lfg`            | Fully autonomous: plan + implement + review + commit |
| `/review`         | Review recent changes and extract learnings          |
| `/compound`       | Full compound cycle: plan + work + review            |

### Commit Workflow (`/commit`)

The `/commit` slash command provides a guided, guardrailed commit-to-PR workflow. It handles branch management, quality enforcement, conventional commit formatting, and PR monitoring in a single flow.

**What it does:** Walks you through staging, validating, committing, pushing, and monitoring a pull request -- without ever skipping quality checks or committing directly to main.

**Step-by-step flow:**

```
1. Branch guard
   If on main, suggest a branch name based on the changes and ask for confirmation.
   Create and switch to the new branch.

2. Stage and review
   Show a summary of all changes (files, scope, affected packages).
   Ask user which files to stage.

3. Quality gates (parallel)
   Agent A: pnpm test --> pnpm typecheck --> pnpm lint
   Agent B: lefthook run pre-commit
   Any failure is a hard stop. Fix the root cause and re-run.

4. Generate commit message
   Conventional Commits format: type(scope): description
   Bullet points for non-trivial changes.

5. User approval
   Present the message. User approves or edits.

6. Commit
   Commit with Co-Authored-By trailer. Verify with git status.

7. Push and PR (optional)
   If user opts in: push branch, create PR via gh CLI with structured body.

8. PR monitoring loop (if PR was created)
   Three gates checked each cycle:
     A. CI checks (gh pr checks)
     B. Reviewer comments (gh pr view --json reviews,comments)
     C. Merge conflicts (gh pr view --json mergeable)
   All three must pass on the same cycle. Never auto-merges.
```

**Pre-commit hooks (via Lefthook):** Every commit triggers Prettier auto-fix, ESLint auto-fix, TypeScript type checking, repository structure validation, and a large file guard. These hooks cannot be bypassed by the `/commit` workflow -- it explicitly refuses `--no-verify`.

**CI pipeline:** Pull requests are validated by GitHub Actions running lint, typecheck, build, test, and structure checks in parallel. The monitoring loop in step 8 watches these checks and addresses failures automatically until all gates are green.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributing guide, including:

- Development setup
- Branch naming conventions
- Commit conventions (Conventional Commits)
- Testing requirements
- File placement rules
- Pull request process
- Verification protocol (VERIFIED / UNVERIFIED tagging)
- Safe refactoring protocol

---

## Credits and Acknowledgments

This template integrates ideas and code from three open-source projects:

- **[Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin)** by Kieran Klaassen / [Every](https://every.to/) -- The Claude Code plugin providing `/plan`, `/lfg`, `/review`, `/compound`, and 29 agents, 22 commands, 19 skills for compound development workflows.

- **[Ralph](https://github.com/snarktank/ralph)** by [Geoffrey Huntley](https://ghuntley.com/ralph/) -- The autonomous execution loop pattern where fresh AI context per iteration solves context window limitations. Memory persists via git commits and state files.

- **[Compound Product](https://github.com/snarktank/compound-product)** by Ryan Carson / [snarktank](https://github.com/snarktank) -- The full autonomous pipeline combining report analysis, PRD generation, task decomposition, execution loops, and PR automation.

---

## License

MIT
