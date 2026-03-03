<!-- TEMPLATE: This file becomes README.md for new projects created from Launchpad.
     The init-project.sh script replaces all placeholders below.
     Placeholders: {{PROJECT_NAME}}, {{PROJECT_DESCRIPTION}}, {{LICENSE_TYPE}}, {{COPYRIGHT_HOLDER}}
     After running init-project.sh, review this file and customize sections as needed.
     The original Launchpad README is preserved at .launchpad/GUIDE.md for reference. -->

# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

![Node.js](https://img.shields.io/badge/Node.js-22.x-339933?logo=node.js&logoColor=white)
![pnpm](https://img.shields.io/badge/pnpm-9.x-F69220?logo=pnpm&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-{{LICENSE_TYPE}}-blue)

---

## Quick Start

```bash
corepack enable          # Enables pnpm via Corepack
pnpm install             # Install all workspace dependencies + git hooks
cp .env.example .env.local   # Configure environment variables
pnpm dev                 # Start dev servers (web :3000, API :3001)
```

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

## Project Structure

```
{{PROJECT_NAME}}/
├── apps/
│   ├── web/                # Next.js 15 App Router frontend
│   └── api/                # Hono backend service
├── packages/
│   ├── db/                 # Prisma schema, client singleton, migrations
│   ├── shared/             # Shared TypeScript types and utilities
│   ├── ui/                 # Shared React component library
│   ├── eslint-config/      # Shared ESLint 9 flat config
│   └── typescript-config/  # Shared TypeScript presets
├── scripts/
│   ├── agent_hydration/    # AI session bootstrapping
│   ├── compound/           # Autonomous execution pipeline
│   └── maintenance/        # Repo structure validation
├── docs/                   # Architecture docs, plans, reports
├── .github/                # GitHub Actions workflows, templates
├── .claude/                # Claude Code commands, skills, agents
├── CLAUDE.md               # AI instructions for Claude Code
└── AGENTS.md               # AI instructions for other AI tools
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

| Prerequisite                                                  | Version | Required | Purpose                                        |
| ------------------------------------------------------------- | ------- | -------- | ---------------------------------------------- |
| [Node.js](https://nodejs.org/)                                | 22.x+   | Yes      | JavaScript runtime                             |
| [pnpm](https://pnpm.io/)                                      | 9.x+    | Yes      | Package manager (enable via `corepack enable`) |
| [PostgreSQL](https://www.postgresql.org/)                     | 14+     | Yes      | Database                                       |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Latest  | Optional | AI development workflows                       |
| [GitHub CLI](https://cli.github.com/)                         | Latest  | Optional | PR creation from slash commands                |

### Installation

```bash
git clone <your-repo-url>
cd {{PROJECT_NAME}}
corepack enable
pnpm install
```

### Environment

```bash
cp .env.example .env.local
```

Open `.env.local` and fill in your values. At minimum, set `DATABASE_URL` to your PostgreSQL connection string.

| Variable              | Required | Description                                         |
| --------------------- | -------- | --------------------------------------------------- |
| `DATABASE_URL`        | Yes      | PostgreSQL connection string                        |
| `PORT`                | No       | API server port (default: 3001)                     |
| `NEXT_PUBLIC_API_URL` | No       | Frontend API URL (default: `http://localhost:3001`) |
| `ANTHROPIC_API_KEY`   | No       | For compound automation scripts                     |
| `OPENAI_API_KEY`      | No       | Alternative LLM provider + Codex review in CI       |
| `NODE_ENV`            | No       | Environment flag (default: `development`)           |

### Development

```bash
pnpm dev            # Start all dev servers (web :3000, API :3001)
pnpm build          # Build all apps and packages
pnpm test           # Run Vitest tests across all workspaces
pnpm typecheck      # TypeScript type check (no emit)
pnpm lint           # Run ESLint across all workspaces
pnpm format         # Format all files with Prettier
```

---

## AI Workflows

This project was scaffolded from [Launchpad](https://github.com/thinkinghand/launchpad) and includes five layers of AI-assisted development tooling, from project structure enforcement to fully autonomous feature implementation.

### Define Your Product

Before building, populate the architecture docs that give AI assistants full context about your project:

```
/define-product          # Interactive Q&A to populate PRD and tech stack docs
/define-architecture     # Interactive Q&A to populate architecture docs
```

This fills six docs in `docs/architecture/` that anchor every AI session.

### Build With AI

Choose your level of autonomy:

| Mode                 | How                                | Description                                                              |
| -------------------- | ---------------------------------- | ------------------------------------------------------------------------ |
| **Interactive**      | `/create_plan` + `/implement_plan` | You describe the feature, review the plan, approve each phase            |
| **Semi-autonomous**  | `/plan` + `/lfg` (plugin)          | AI plans and implements; you review the PR                               |
| **Fully autonomous** | `/inf`                             | Reads latest report, picks priority, generates PRD, implements, opens PR |

### Session Bootstrapping

Start each AI session with minimal context loading:

```bash
./scripts/agent_hydration/hydrate.sh    # Or use /Hydrate in Claude Code
```

For the full command reference and workflow details, see [`.launchpad/GUIDE.md`](.launchpad/GUIDE.md).

---

## Configuration

### Turborepo Pipeline

| Task        | Description                      | Caching                        |
| ----------- | -------------------------------- | ------------------------------ |
| `build`     | Build all apps and packages      | Cached (`.next/**`, `dist/**`) |
| `dev`       | Start dev servers for all apps   | Not cached, persistent         |
| `lint`      | Run ESLint across all workspaces | Cached                         |
| `test`      | Run Vitest tests                 | Cached                         |
| `typecheck` | TypeScript type checking         | Cached                         |

### Git Hooks (Lefthook)

Hooks are installed automatically by `pnpm install` and run on every commit:

| Hook               | What it runs                                    |
| ------------------ | ----------------------------------------------- |
| `prettier-fix`     | Auto-format changed files                       |
| `eslint-fix`       | Auto-fix lint issues                            |
| `typecheck`        | TypeScript type checking                        |
| `structure-check`  | Validate repo against `REPOSITORY_STRUCTURE.md` |
| `large-file-guard` | Block files over 512KB                          |

### CI/CD

GitHub Actions workflows run on every pull request:

- **CI** (`.github/workflows/ci.yml`) -- Lint, typecheck, test. Blocks merge on failure.
- **Codex Review** (`.github/workflows/codex-review.yml`) -- Automated code review with P0-P3 severity classification. Requires `OPENAI_API_KEY` in GitHub Secrets.
- **Deploy** (`.github/workflows/deploy.yml`) -- Build and deploy on push to main (configure your deployment target).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributing guide, including development setup, branch naming conventions, commit conventions, testing requirements, and the pull request process.

---

## License

{{LICENSE_TYPE}} -- see [LICENSE](LICENSE) for details.

Copyright {{COPYRIGHT_HOLDER}}.
