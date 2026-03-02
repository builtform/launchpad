# Launchpad

> Structure for AI coding. Best practices, pre-configured.

![Node.js](https://img.shields.io/badge/Node.js-22.x-339933?logo=node.js&logoColor=white)
![pnpm](https://img.shields.io/badge/pnpm-9.x-F69220?logo=pnpm&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue)

---

## The Problem

AI coding assistants are powerful, but they work without memory, structure, or conventions. Every time you start a new session, the AI has no idea how your project is organized, what patterns you follow, or what quality bar you expect. It generates code that works in isolation but creates maintenance debt at scale.

Developers are spending more time wrangling AI output than writing code. You get a function that passes its unit test but lives in the wrong directory, ignores your naming conventions, and introduces a dependency you already have an alternative for. Multiply that across a team and dozens of AI sessions per week, and the codebase drifts toward chaos.

The root cause is not the AI itself. It is the absence of structure around it. There is no standard way to teach an AI assistant your project's conventions, no enforcement that its output follows your rules, and no workflow that goes from specification to pull request without manual babysitting. Every new project starts from zero -- no accumulated best practices, no quality gates, no institutional knowledge.

---

## Quick Start

```bash
git clone https://github.com/thinkinghand/launchpad.git my-project
cd my-project
./scripts/setup/init-project.sh    # Interactive wizard — validates inputs, swaps templates
git diff                            # Verify the changes look correct
# Stay connected to Launchpad for future updates (recommended):
git remote rename origin launchpad
git remote add origin <your-repo-url>
git push -u origin main
pnpm install && pnpm dev
claude                              # Start building with AI
```

---

## The 5 Layers

Launchpad organizes AI-assisted development into five layers. Each layer addresses a specific failure mode of unstructured AI coding.

| Layer                         | What It Does                                             | How                                                     |
| ----------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| **1. Opinionated Scaffold**   | Enforces consistent file placement and project structure | `check-repo-structure.sh`, `REPOSITORY_STRUCTURE.md`    |
| **2. Spec-Driven Definition** | Specifies what to build before writing code              | `/define-product`, `/define-architecture`               |
| **3. Compound Execution**     | Runs AI in fresh-context loops with persistent memory    | `/inf`, `auto-compound.sh`, Ralph loop                  |
| **4. Quality Gates**          | Catches problems before they reach the repository        | Lefthook pre-commit hooks, TypeScript, ESLint, Prettier |
| **5. Commit-to-Merge**        | Prevents unreviewed code from reaching main              | `/commit` with 3-gate monitoring, Codex AI review       |

Rails did not invent MVC, ORM, or migrations. It assembled them into a coherent whole with strong opinions about how they fit together. Launchpad does the same for AI-assisted development: it takes existing patterns -- compound loops, spec-driven development, structure enforcement, quality gates -- and wires them into a single, opinionated scaffold that works out of the box.

---

## The Workflow

### Define Phase

Before writing any code, define what you are building. These AI workflow slash commands populate architecture docs that give the AI full context about your project:

- **`/define-product`** -- Structured Q&A to create your PRD, tech stack, and product vision
- **`/define-architecture`** -- Structured Q&A to define app flow, backend structure, frontend guidelines, and CI/CD

### Build Phase

With definitions in place, build features using autonomous AI loops or interactive planning:

- **`/create_plan`** -- Break a feature into an implementation plan with parallel sub-agents
- **`/implement_plan`** -- Execute an existing plan phase by phase
- **`/inf`** -- Full compound pipeline: report analysis, PRD generation, task decomposition, execution loop, quality sweep, and PR creation
- **`/research_codebase`** -- Deep codebase research with parallel sub-agents

### Commit Phase

Every change goes through quality gates before it reaches the repository:

- **`/commit`** -- Guided commit-to-PR workflow: branch guard, staging, parallel quality checks (tests, typecheck, lint, structure), Conventional Commits message, push, PR creation, and 3-gate monitoring (CI, Codex review, merge conflicts)

### Maintain Phase

Keep your project up to date with upstream Launchpad improvements:

- **`/pull-launchpad`** -- Fetch, diff, and interactively apply upstream changes to safe directories (commands, skills, scripts, workflows). Files customized during init (README, LICENSE, CLAUDE.md, AGENTS.md) are never touched.

---

## What's Inside

### Tech Stack

| Component       | Technology                                                                                |
| --------------- | ----------------------------------------------------------------------------------------- |
| Frontend        | [Next.js 15](https://nextjs.org/) App Router, [Tailwind CSS v4](https://tailwindcss.com/) |
| Backend         | [Hono](https://hono.dev/) (lightweight TypeScript framework)                              |
| Language        | TypeScript 5 (strict mode)                                                                |
| Database        | [Prisma](https://www.prisma.io/) + PostgreSQL                                             |
| Build           | [Turborepo](https://turbo.build/)                                                         |
| Package Manager | [pnpm](https://pnpm.io/) 9+ with workspaces                                               |
| Linting         | ESLint 9 (flat config), Prettier                                                          |
| Testing         | [Vitest](https://vitest.dev/)                                                             |
| Git Hooks       | [Lefthook](https://github.com/evilmartians/lefthook)                                      |
| CI/CD           | GitHub Actions                                                                            |
| AI Integration  | [Claude Code](https://docs.anthropic.com/en/docs/claude-code), `CLAUDE.md`, `AGENTS.md`   |

### Project Structure

```
launchpad/
├── apps/
│   ├── web/                # Next.js 15 App Router frontend
│   └── api/                # Hono backend service
├── packages/
│   ├── db/                 # Prisma schema, client, migrations
│   ├── shared/             # Shared TypeScript types and utilities
│   ├── ui/                 # Shared React component library
│   ├── eslint-config/      # Shared ESLint 9 flat config
│   └── typescript-config/  # Shared TypeScript presets
├── scripts/
│   ├── compound/           # Compound Product pipeline scripts
│   ├── agent_hydration/    # AI session bootstrapping
│   └── maintenance/        # Repo structure validation
├── docs/                   # Centralized documentation hub
├── .github/                # GitHub Actions workflows, templates
├── .claude/                # Claude Code commands, skills, agents
├── CLAUDE.md               # AI instructions for Claude Code
├── AGENTS.md               # AI instructions for other AI tools
└── CONTRIBUTING.md          # Human contribution rules
```

The full annotated structure with a file placement decision tree lives in [`docs/architecture/REPOSITORY_STRUCTURE.md`](docs/architecture/REPOSITORY_STRUCTURE.md).

### Packages

All packages use the `@repo/` scope and are consumed via pnpm workspace dependencies.

| Package                   | Path                          | Purpose                                                           |
| ------------------------- | ----------------------------- | ----------------------------------------------------------------- |
| `@repo/db`                | `packages/db/`                | Prisma schema, migrations, and PrismaClient singleton             |
| `@repo/shared`            | `packages/shared/`            | Shared TypeScript types and pure utility functions                |
| `@repo/ui`                | `packages/ui/`                | Shared React components, `cn()` utility, Tailwind config          |
| `@repo/eslint-config`     | `packages/eslint-config/`     | ESLint 9 flat config with `base.js`, `next.js`, `node.js` exports |
| `@repo/typescript-config` | `packages/typescript-config/` | TypeScript presets: `base.json`, `next.json`, `node.json`         |

---

## Getting Started

### Prerequisites

| Prerequisite                                                  | Version | Required    | Purpose                                        |
| ------------------------------------------------------------- | ------- | ----------- | ---------------------------------------------- |
| [Node.js](https://nodejs.org/)                                | 22.x+   | Yes         | JavaScript runtime                             |
| [pnpm](https://pnpm.io/)                                      | 9.x+    | Yes         | Package manager (enable via `corepack enable`) |
| [PostgreSQL](https://www.postgresql.org/)                     | 14+     | Yes         | Database                                       |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Latest  | Recommended | AI development workflows                       |
| [GitHub CLI](https://cli.github.com/)                         | Latest  | Optional    | PR creation from `/commit` and `/inf`          |

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/thinkinghand/launchpad.git my-project
cd my-project
```

> **Alternative:** Click the green **"Use this template"** button on GitHub to create a detached copy. This skips the init wizard's git setup but you can still add the upstream remote manually later.

**2. Initialize your project**

```bash
./scripts/setup/init-project.sh
```

The wizard prompts for your project name, description, copyright holder, contact email, and license (MIT, Apache-2.0, GPL-3.0, or Other). It validates all inputs, swaps template files into place, replaces all placeholders, updates `package.json`, and preserves the original Launchpad documentation at `.launchpad/GUIDE.md`.

**3. Set up git history**

After the init wizard completes, choose how to handle git history:

**Option A -- Stay connected (recommended)**

Keep the upstream connection so you can pull future Launchpad updates into safe directories (commands, skills, scripts, workflows):

```bash
git remote rename origin launchpad
git remote add origin <your-repo-url>
git push -u origin main
```

To pull updates later, use `/pull-launchpad` in Claude Code or run `bash scripts/setup/pull-upstream.launchpad.sh`.

**Option B -- Fresh start**

Remove all upstream history and start clean:

```bash
rm -rf .git && git init -b main && git add -A && git commit -m "Initial commit"
gh repo create my-project --private --source=. --push   # Optional
```

> **Note:** The init wizard automatically adds a `launchpad` remote. Option A preserves this; Option B removes it.

**4. Install dependencies**

```bash
corepack enable          # Enables pnpm via Corepack
pnpm install             # Installs all workspace deps + git hooks
```

**5. Configure environment**

```bash
cp .env.example .env.local
```

Open `.env.local` and set `DATABASE_URL` to your PostgreSQL connection string. AI provider keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) are only needed for compound automation scripts.

**6. Start development**

```bash
pnpm dev
```

The web app runs on `http://localhost:3000` and the API on `http://localhost:3001`.

**7. Define your product (AI workflow)**

```
/define-product              # Answer questions about your product vision and goals
/define-architecture         # Answer questions about your technical architecture
```

This populates six architecture docs that give the AI complete context about what you are building.

### Trimming What You Don't Need

This template is comprehensive by design. Delete what your project does not require:

| If you don't need... | Delete              | Also remove from                                    |
| -------------------- | ------------------- | --------------------------------------------------- |
| Backend API          | `apps/api/`         | `turbo.json` tasks, `pnpm-workspace.yaml` if needed |
| Database / Prisma    | `packages/db/`      | `@repo/db` references in `apps/api/package.json`    |
| Compound automation  | `scripts/compound/` | --                                                  |
| Shared UI library    | `packages/ui/`      | `@repo/ui` references in `apps/web/package.json`    |

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env.local` (gitignored) and fill in your values:

| Variable              | Required | Description                                                |
| --------------------- | -------- | ---------------------------------------------------------- |
| `DATABASE_URL`        | Yes      | PostgreSQL connection string                               |
| `PORT`                | No       | API server port (default: 3001)                            |
| `NEXT_PUBLIC_API_URL` | No       | Frontend API URL (default: `http://localhost:3001`)        |
| `ANTHROPIC_API_KEY`   | No       | For compound automation (`analyze-report.sh`)              |
| `OPENAI_API_KEY`      | No       | Alternative LLM provider + GitHub Secrets for Codex review |
| `NODE_ENV`            | No       | Environment flag (default: `development`)                  |

### Turborepo Pipeline

| Task        | Description                      | Caching                |
| ----------- | -------------------------------- | ---------------------- |
| `build`     | Build all apps and packages      | Cached                 |
| `dev`       | Start dev servers for all apps   | Not cached, persistent |
| `lint`      | Run ESLint across all workspaces | Cached                 |
| `test`      | Run Vitest tests                 | Cached                 |
| `typecheck` | TypeScript type checking         | Cached                 |

### Git Hooks (Lefthook)

Hooks are installed automatically by `pnpm install` and run on every commit:

| Hook               | What It Runs                                    |
| ------------------ | ----------------------------------------------- |
| `prettier-fix`     | Auto-format changed files                       |
| `eslint-fix`       | Auto-fix lint issues                            |
| `typecheck`        | TypeScript type checking                        |
| `structure-check`  | Validate repo against `REPOSITORY_STRUCTURE.md` |
| `large-file-guard` | Block files over 512KB                          |

### Compound Pipeline Config

`scripts/compound/config.json` controls the automation pipeline:

| Field           | Default                           | Description                                    |
| --------------- | --------------------------------- | ---------------------------------------------- |
| `reportsDir`    | `./docs/reports`                  | Directory containing report markdown files     |
| `outputDir`     | `./scripts/compound`              | Where `prd.json` and `progress.txt` are stored |
| `qualityChecks` | `["pnpm typecheck", "pnpm test"]` | Commands run after each task                   |
| `maxIterations` | `25`                              | Maximum loop iterations                        |
| `branchPrefix`  | `compound/`                       | Prefix for auto-created branches               |

---

## AI Workflow Commands

### Slash Commands

| Command                | Phase    | Description                                                            |
| ---------------------- | -------- | ---------------------------------------------------------------------- |
| `/Hydrate`             | --       | Load minimal session context (repo structure + active tasks)           |
| `/define-product`      | Define   | Interactive Q&A to populate PRD and tech stack docs                    |
| `/define-architecture` | Define   | Interactive Q&A to populate architecture docs                          |
| `/create_plan`         | Build    | Create a detailed implementation plan with parallel sub-agents         |
| `/implement_plan`      | Build    | Execute an existing implementation plan phase by phase                 |
| `/research_codebase`   | Build    | Deep codebase research with parallel sub-agents                        |
| `/review_code`         | Build    | Pattern consistency review of changed files                            |
| `/commit`              | Commit   | Guided commit-to-PR workflow with quality gates and PR monitoring      |
| `/inf`                 | Build    | Full compound pipeline: report to PRD to tasks to loop to PR           |
| `/pull-launchpad`      | Maintain | Pull upstream Launchpad updates into safe (non-customized) directories |

### Skills

| Skill    | Trigger Phrases                     | Description                                        |
| -------- | ----------------------------------- | -------------------------------------------------- |
| `prd`    | "create a prd", "write prd for"     | Generate a Product Requirements Document           |
| `tasks`  | "convert prd", "create tasks"       | Convert a PRD to `prd.json` for the execution loop |
| `commit` | "commit changes", "ready to commit" | Run the `/commit` workflow                         |

### Development Commands

| Command          | Description                                  |
| ---------------- | -------------------------------------------- |
| `pnpm dev`       | Start all dev servers (web :3000, API :3001) |
| `pnpm build`     | Build all apps and packages                  |
| `pnpm test`      | Run Vitest tests across all workspaces       |
| `pnpm typecheck` | TypeScript type checking                     |
| `pnpm lint`      | Run ESLint across all workspaces             |
| `pnpm format`    | Format all files with Prettier               |

---

## CI/CD

### CI Workflow

Runs on every pull request to `main`:

1. Install dependencies (cached by lockfile hash)
2. Check repository structure
3. Run lint, typecheck, and tests

A PR cannot merge if any step fails.

### Codex Review

Runs on every pull request. Posts a review as a PR comment with severity classification (P0 critical through P3 optional). Both `/inf` and `/commit` monitor for Codex findings and act on P0/P1 issues.

**Prerequisite:** Add `OPENAI_API_KEY` to your repository's GitHub Secrets.

---

## Optional: Compound Engineering Plugin

The [Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin) by Kieran Klaassen / [Every](https://every.to/) provides additional AI workflow slash commands for planning, implementation, review, and compound learning cycles. It is **not included** in Launchpad -- install it separately if you want it:

```
/plugin marketplace add https://github.com/EveryInc/compound-engineering-plugin
/plugin install compound-engineering
```

Key commands: `/plan`, `/lfg`, `/review`, `/compound`. See the [plugin repository](https://github.com/EveryInc/compound-engineering-plugin) for the full reference.

---

## Credits

Launchpad assembles ideas and code from several open-source projects:

- **[Compound Product](https://github.com/snarktank/compound-product)** by Ryan Carson / [snarktank](https://github.com/snarktank) -- The autonomous pipeline combining report analysis, PRD generation, task decomposition, execution loops, and PR automation.

- **[Ralph](https://github.com/snarktank/ralph)** by [Geoffrey Huntley](https://ghuntley.com/ralph/) -- The fresh-context execution loop pattern where memory persists via git commits and state files across AI sessions.

- **Spec-Driven Development** -- Inspired by the SDD methodology (SpecKit / AgentOS). Define canonical architecture docs before building, giving AI full project context.

- **[Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin)** by Kieran Klaassen / [Every](https://every.to/) -- External Claude Code plugin providing 29 agents, 22 commands, and 19 skills for compound development workflows (optional, installed separately).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributing guide, including development setup, branch naming conventions, commit format, testing requirements, file placement rules, and the PR process.

---

## License

MIT -- see [LICENSE](LICENSE) for details.
