<!-- TEMPLATE: This file becomes README.md for new projects created from Launchpad.
     The init-project.sh script replaces all placeholders below.
     Placeholders: {{PROJECT_NAME}}, {{PROJECT_DESCRIPTION}}, {{LICENSE_TYPE}}, {{COPYRIGHT_HOLDER}}
     The original Launchpad docs are preserved at .launchpad/HOW_IT_WORKS.md and .launchpad/METHODOLOGY.md for reference. -->

# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

## Status

This project was built from the [LaunchPad](https://github.com/builtform/launchpad) harness and is ready to be defined.

**Next steps (four-tier workflow):**

1. **Tier 0 — Capabilities** (ongoing):
   - `/lp-create-skill [topic]` or `/lp-port-skill [source]` — create or port domain skills to enhance all subsequent commands
2. **Tier 1 — Definition** (run once):
   - `/lp-define-product` — define product requirements, tech stack, and section registry
   - `/lp-define-design` — define your design system, app flow, and frontend guidelines
   - `/lp-define-architecture` — define backend structure and CI/CD
3. **Tier 2 — Development** (per section):
   - `/lp-shape-section [name]` — deep-dive into each product section
   - `/lp-update-spec` — scan and fix spec gaps
4. **Tier 3 — Implementation** (per section):
   - `/lp-pnf [section]` — plan next feature from section spec
   - `/lp-inf` — implement next feature autonomously
5. Review [How It Works](.launchpad/HOW_IT_WORKS.md) for the step-by-step workflow guide and troubleshooting
6. Review [Repository Structure](docs/architecture/REPOSITORY_STRUCTURE.md) to understand the codebase layout
7. Read [Methodology](.launchpad/METHODOLOGY.md) for the full architecture, diagrams, and credits

## Commands

| Command                   | Purpose                                                          |
| ------------------------- | ---------------------------------------------------------------- |
| `/lp-create-skill`        | Create a new Claude Code skill                                   |
| `/lp-port-skill`          | Port an external skill into Launchpad format                     |
| `/lp-update-skill`        | Iterate on an existing skill                                     |
| `/lp-define-product`      | Define product requirements, tech stack, and section registry    |
| `/lp-define-design`       | Define design system, app flow, and frontend guidelines          |
| `/lp-define-architecture` | Define backend structure and CI/CD                               |
| `/lp-shape-section`       | Deep-dive into a product section — creates section spec          |
| `/lp-update-spec`         | Scan spec files for gaps, TBDs, and inconsistencies — fix them   |
| `/lp-pnf`                 | Plan Next Feature from section spec                              |
| `/lp-implement-plan`      | Execute an existing implementation plan step by step             |
| `/lp-inf`                 | Implement next feature: PRD → tasks → build → quality sweep → PR |
| `/lp-research-codebase`   | Deep codebase research and analysis                              |
| `/lp-review`              | Review code for pattern consistency                              |
| `/lp-commit`              | Stage changes, run quality gates, and commit                     |
| `/lp-pull-launchpad`      | Pull upstream Launchpad updates                                  |

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
