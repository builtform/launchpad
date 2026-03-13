<!-- TEMPLATE: This file becomes README.md for new projects created from Launchpad.
     The init-project.sh script replaces all placeholders below.
     Placeholders: {{PROJECT_NAME}}, {{PROJECT_DESCRIPTION}}, {{LICENSE_TYPE}}, {{COPYRIGHT_HOLDER}}
     The original Launchpad docs are preserved at .launchpad/HOW_IT_WORKS.md and .launchpad/METHODOLOGY.md for reference. -->

# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

## Status

This project was scaffolded from [Launchpad](https://github.com/thinkinghand/launchpad) and is ready to be defined.

**Next steps:**

1. Run `/define-product` in Claude Code to define your product requirements and tech stack
2. Run `/define-architecture` to define app flow, backend structure, frontend guidelines, and CI/CD
3. Start building with `/create_plan` or `/inf`
4. Review [How It Works](.launchpad/HOW_IT_WORKS.md) for the step-by-step workflow guide and troubleshooting
5. Review [Repository Structure](docs/architecture/REPOSITORY_STRUCTURE.md) to understand the codebase layout
6. Read [Methodology](.launchpad/METHODOLOGY.md) for the full architecture, diagrams, and credits

## Commands

| Command                | Purpose                                                            |
| ---------------------- | ------------------------------------------------------------------ |
| `/define-product`      | Define product requirements and tech stack through guided Q&A      |
| `/define-architecture` | Define app flow, backend structure, frontend guidelines, and CI/CD |
| `/create_plan`         | Create a structured implementation plan for a feature              |
| `/implement_plan`      | Execute an existing implementation plan step by step               |
| `/inf`                 | Implement next feature: PRD → tasks → build → quality sweep → PR   |
| `/research_codebase`   | Deep codebase research and analysis                                |
| `/review_code`         | Review code for pattern consistency                                |
| `/commit`              | Stage changes, run quality gates, and commit                       |
| `/create-skill`        | Create a new Claude Code skill                                     |
| `/update-skill`        | Iterate on an existing skill                                       |
| `/port-skill`          | Port an external skill into Launchpad format                       |
| `/pull-launchpad`      | Pull upstream Launchpad updates                                    |

## Project Structure

```
{{PROJECT_NAME}}/
├── apps/
│   ├── web/                # Next.js 15 frontend (App Router)
│   └── api/                # Hono API server
├── packages/
│   ├── db/                 # Prisma schema, client, migrations
│   ├── shared/             # Shared TypeScript types and utilities
│   ├── ui/                 # Shared React components + Tailwind config
│   ├── eslint-config/      # Shared ESLint 9 flat config
│   └── typescript-config/  # Shared TypeScript presets
├── docs/architecture/      # PRD, tech stack, app flow, backend, frontend, CI/CD
├── scripts/                # Automation and maintenance scripts
├── .claude/                # Claude Code skills, commands, agents
├── .github/                # GitHub Actions workflows and templates
├── CLAUDE.md               # AI instructions (Claude Code)
└── AGENTS.md               # AI instructions (other AI tools)
```

## Development

```bash
pnpm install        # Install dependencies
pnpm dev            # Start dev servers (web :3000, API :3001)
pnpm build          # Build all apps and packages
pnpm test           # Run tests
pnpm typecheck      # TypeScript type check
pnpm lint           # Lint all workspaces
```

## License

{{LICENSE_TYPE}} -- see [LICENSE](LICENSE) for details.

Copyright {{COPYRIGHT_HOLDER}}.
