# Launchpad – Agent Instructions

> **Harness scope:** Full-stack monorepo with a **TypeScript/Next.js frontend** and a **Hono API backend**, managed with Turborepo and pnpm workspaces. Adapt section headers and placeholder values if your topology differs.

> **File purpose:** `AGENTS.md` is the cross-tool agent instruction file for AI coding CLIs that are not Claude Code. Claude Code uses `CLAUDE.md` instead. Codex reads this file for project context and runs LaunchPad through its installed plugin. Tools without a LaunchPad plugin use the bridge in "Invoking LaunchPad Workflows" below. Keep both instruction files in sync when updating project-wide conventions.

---

## WHY – Project Purpose

<!-- 2–4 sentences. What problem does this solve? Who are the users? What's the core value prop?   -->
<!-- This anchors every decision the agent makes — keep it here, not in a linked doc.              -->

{{PROJECT_PURPOSE}}

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
├── apps/web/              # Next.js 15 frontend (App Router, Tailwind v4)
├── apps/api/              # Hono API server (CORS, /health endpoint)
├── packages/db/           # Prisma schema, client singleton, migrations
├── packages/shared/       # Shared TypeScript types and utilities
├── packages/ui/           # Shared React components + Tailwind config + cn() helper
├── docs/                  # Architecture docs, plans, reports, experiments
│   ├── tasks/             # BACKLOG.md + sections/ (section specs from /lp-shape-section)
│   └── skills-catalog/    # Skill usage tracking and user-facing index
├── .harness/              # Runtime directory (todos, observations, design-artifacts, screenshots)
├── .launchpad/            # Harness config (agents.yml, version, secret-patterns.txt)
├── plugins/launchpad/     # LaunchPad plugin source (commands, agents, skills, scripts)
└── scripts/               # Build pipeline, maintenance, agent hydration
```

> Before creating, moving, or deleting any file: check `docs/architecture/REPOSITORY_STRUCTURE.md`
> for the layout decision tree (Section 6).

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

The agent must confirm all of the following before closing a task:

**TypeScript / JavaScript:**

- [ ] Tests pass: `pnpm test`
- [ ] Typecheck passes: `pnpm typecheck`
- [ ] No new lint errors: `pnpm lint`

**Python (when changes touch `*.py` or `plugins/launchpad/scripts/`):**

Note the cwd difference: `pytest` and `pyright` run **from `plugins/launchpad/scripts/`** (CI sets `working-directory` for both), while `ruff` runs **from the repo root** with an explicit `--config`. Each command below matches its CI invocation exactly; do not "simplify" them to a common form.

- [ ] Tests pass: `cd plugins/launchpad/scripts && python -m pytest -q`
- [ ] Typecheck passes: `cd plugins/launchpad/scripts && pyright` (run from `plugins/launchpad/scripts/` so pyproject.toml is discovered)
- [ ] No new lint errors, from the repo root: `ruff check --config plugins/launchpad/scripts/pyproject.toml plugins/launchpad/scripts/`
- [ ] Format check, from the repo root: `ruff format --check --config plugins/launchpad/scripts/pyproject.toml plugins/launchpad/scripts/`

> First-party import classification is pinned by an explicit `known-first-party`
> enumeration in `plugins/launchpad/scripts/pyproject.toml`, so ruff returns the
> same verdict from any invocation form. Enforced by
> `plugins/launchpad/scripts/tests/test_lint_invocation_parity.py`.

---

## Invoking LaunchPad Workflows

This project is LaunchPad-scaffolded. Most structured workflows live in `plugins/launchpad/commands/` as markdown files.

**Claude Code users** invoke these directly as slash commands (`/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build`, etc.) via the installed plugin.

**Codex users** install the LaunchPad plugin and invoke its single router as `$launchpad:lp <command>`. Apply one mapping rule: `/lp-review` on Claude Code is `$launchpad:lp review` on Codex. Run `$launchpad:lp help` to list the live command inventory. `$lp <command>` and plain-language requests loaded the router during verification, but they are conveniences and are not guaranteed.

**Gemini and other CLIs** keep the manual bridge. Instruct the AI: _"Read `plugins/launchpad/commands/lp-<name>.md` and follow the workflow."_

### Workflow access by host

| Host                  | Workflow access                                         | Specialist dispatch                                                                                  |
| --------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Claude Code           | `/lp-<command>` through the installed plugin            | Uses Claude Code's task capability                                                                   |
| Codex                 | `$launchpad:lp <command>` through the installed plugin  | Concurrent when Codex allows, sequential otherwise; the run states the mode and names failures       |
| Gemini and other CLIs | Read `plugins/launchpad/commands/lp-<name>.md` directly | Depends on the host; follow every canonical specialist instruction and disclose any unavailable step |

The commands verified on Codex, with the date they were last checked, are listed in [How It Works: Codex](docs/guides/HOW_IT_WORKS.md#codex). Every other command runs through the same router and is not yet verified there; a step may stop with a message that names what is missing.

Agent tool restrictions are advisory on Codex. Run review and PR-comment workflows in the `workspace-write` sandbox with approvals on. Settings and hooks under `.claude/` are inert on Codex, and projects scaffolded from Codex do not receive Codex hooks yet.

Codex may show host-generated `launchpad:source-command-*` entries for a few small commands. They are unsupported and nested `/lp-` commands inside them may not resolve. Use `$launchpad:lp <command>` instead.

### Configuring your tool to read this file

**Codex CLI:** `AGENTS.md` is loaded automatically. If you also want Claude Code's `CLAUDE.md` merged in, add it to `project_doc_fallback_filenames` in `~/.codex/config.toml`:

```toml
project_doc_fallback_filenames = ["AGENTS.md", "CLAUDE.md"]
```

**Gemini CLI users:** Gemini CLI reads `GEMINI.md` by default — it does NOT auto-load `AGENTS.md`. To use this file as the project context, add to `.gemini/settings.json`:

```json
{ "context": { "fileName": ["AGENTS.md"] } }
```

Gemini support remains the manual bridge. Native Gemini packaging is deferred until demand justifies it.

**Other tools** (Cursor, Windsurf, Aider, Jules, etc.) — `AGENTS.md` is the Linux Foundation's Agentic AI Foundation standard and is auto-discovered by most modern coding CLIs.

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

<!-- The agent reads these only when the task is relevant — never all upfront.                    -->
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
| `.launchpad/agents.yml`                    | Configuring review agent lists                      |
| `.harness/harness.local.md`                | Viewing or updating project-specific review context |
| `docs/tasks/BACKLOG.md`                    | Checking project backlog and deferred items         |

---

## Available Sub-Agents

Agents are organized into 6 namespace subdirectories under `plugins/launchpad/agents/`. See `CLAUDE.md` for the full agent table — the list is identical. Key namespaces:

- **research/** (7 agents) — Read-only research and documentation
- **skills/** (1 agent) — Skill quality assurance
- **review/** (16 agents): Code review with multiple specializations
  - `lp-claims-auditor`: executes and classifies repository claims (`Read, Grep, Glob, Bash`)
  - `lp-foad-go-reviewer`: proves Go correctness defects with disposable probes (`Read, Grep, Glob, Bash`)
  - `lp-document-truth`: checks recipient-facing output for false or contradictory statements (`Read, Grep, Glob, Bash`)
- **document-review/** (7 agents) — Plan document review lenses
- **resolve/** (2 agents) — Automated fixers for todos and PR comments
- **design/** (6 agents) — Design workflow (Figma sync, iteration, auditing)

**In Claude Code** these agents are dispatched via the plugin's task capability from within commands.

**In Codex** the LaunchPad router resolves the canonical agent prompt and dispatches the specialist through Codex. Independent specialists run concurrently when the host allows it and sequentially otherwise.

**In other CLIs** the agent markdown files are prompt templates. Follow each canonical dispatch instruction through the capabilities the host provides, and report any step that cannot run.

### v2.1 stack-aware dispatch

Each agent file carries a `stack_scope:` frontmatter field used by `/lp-review` and `/lp-harden-plan` to filter agents per the detected stack(s). Values: `core_pipeline` (always loaded), `stack:any` (loaded for every stack), `stack:<id>` (loaded only for a matching persisted stack or recognized stack family), `design_quality` (loaded when design artifacts exist), `skill_quality` (loaded for `/lp-create-skill` and `/lp-update-skill`). For example, `stack:go` matches both `go` and `go_cli`, while TypeScript projects drop the Go reviewer. Conditional output reviewers such as `lp-document-truth` are selected through `review_document_agents` and bypass stack filtering.
