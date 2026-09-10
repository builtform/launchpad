# Launchpad – Agent Instructions

> **Harness scope:** Full-stack monorepo with a **TypeScript/Next.js frontend** and a **Hono API backend**, managed with Turborepo and pnpm workspaces. Adapt section headers and placeholder values if your topology differs.

> **File purpose:** `AGENTS.md` is the cross-tool agent instruction file — for AI coding CLIs that are **not** Claude Code (OpenAI Codex, Gemini, Cursor, Zed AI, Windsurf, Aider, Jules, Junie, etc.). Claude Code uses `CLAUDE.md` instead. This file doubles as a **bridge to LaunchPad workflows** for tools without a Claude Code plugin — see "Invoking LaunchPad Workflows" below. Keep both files in sync when updating project-wide conventions.

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
├── .codex/               # Codex project hooks for repository policy and hydration
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

**Claude Code users** invoke released workflows directly as slash commands (`/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build`, etc.) through the installed plugin.

**Codex uses one reserved router grammar:** `$lp <command>`. Never prefix it with the plugin name and never rewrite it as `$lp-<command>`. The current v2.1.11 dogfood evidence blocks all 44 public roots because Codex CLI 0.153.4 did not authenticate bare `$lp` selection or bind a lossless authenticated argument tail. Until later evidence promotes a workflow, Codex may inspect its canonical file but must not execute it.

**Gemini and other CLIs** use the inspection-only bridge. They may read canonical workflow files to understand LaunchPad behavior. They must not execute a mutating, autonomous, or agent-dispatch workflow unless release evidence qualifies that exact host and workflow digest. Unknown hosts default to `inspect_only`.

### Workflow pointer table

| Task                                  | Claude Code   | Codex reserved form | Unsupported-host fallback                           |
| ------------------------------------- | ------------- | ------------------- | --------------------------------------------------- |
| Brainstorm a new feature              | `/lp-kickoff` | `$lp kickoff`       | Inspect `plugins/launchpad/commands/lp-kickoff.md`  |
| Define product and architecture       | `/lp-define`  | `$lp define`        | Inspect `plugins/launchpad/commands/lp-define.md`   |
| Plan and harden a feature             | `/lp-plan`    | `$lp plan`          | Inspect `plugins/launchpad/commands/lp-plan.md`     |
| Run the autonomous build pipeline     | `/lp-build`   | `$lp build`         | Inspection only; execute on a supported native host |
| Multi-agent code review               | `/lp-review`  | `$lp review`        | Inspection only; execute on a supported native host |
| Interactive commit with quality gates | `/lp-commit`  | `$lp commit`        | Inspection only; execute on a supported native host |
| Capture a learning                    | `/lp-learn`   | `$lp learn`         | Inspect `plugins/launchpad/commands/lp-learn.md`    |
| Triage review findings                | `/lp-triage`  | `$lp triage`        | Inspect `plugins/launchpad/commands/lp-triage.md`   |

See `plugins/launchpad/commands/` for the full inventory (42 workflows).

### Host-specific orchestration

Several LaunchPad workflows dispatch specialized sub-agents in parallel. Claude Code uses its native task primitive. The Codex adapter is designed to use native subagents with bounded workers, wave barriers, and cancel-and-join behavior while loading the same canonical prompts.

Do not assume Codex collapses these workflows into one generalist. The candidate contains a single router and a conditional coordinator, not generated per-command wrappers. Because the real-host routing prerequisite is blocked, no Codex multi-agent workflow is currently advertised as executable.

### Configuring your tool to read this file

**Codex CLI:** `AGENTS.md` is loaded automatically. If you also want Claude Code's `CLAUDE.md` merged in, add it to `project_doc_fallback_filenames` in `~/.codex/config.toml`:

```toml
project_doc_fallback_filenames = ["AGENTS.md", "CLAUDE.md"]
```

**Gemini CLI users:** Gemini CLI reads `GEMINI.md` by default — it does NOT auto-load `AGENTS.md`. To use this file as the project context, add to `.gemini/settings.json`:

```json
{ "context": { "fileName": ["AGENTS.md"] } }
```

Gemini support remains inspection-only and demand-driven. No Gemini execution adapter is part of the current candidate.

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
- **review/** (13 agents) — Code review with multiple specializations
- **document-review/** (7 agents) — Plan document review lenses
- **resolve/** (2 agents) — Automated fixers for todos and PR comments
- **design/** (6 agents) — Design workflow (Figma sync, iteration, auditing)

**In Claude Code** these agents are dispatched via the plugin's `Task` tool from within commands.

**In other CLIs** the agent markdown files are just plain prompt templates — your CLI won't auto-dispatch them. When a LaunchPad command instructs "dispatch N agents in parallel," your CLI runs the reviews sequentially instead. See the "Known degradation" note in the bridge section above.

### v2.1 stack-aware dispatch

Each agent file carries a `stack_scope:` frontmatter field used by `/lp-review` and `/lp-harden-plan` to filter agents per the detected stack(s). Values: `core_pipeline` (always loaded), `stack:any` (loaded for any non-empty stack list), `stack:<id>` (v2.2 forward-compat; not used at v2.1), `design_quality` (loaded when design artifacts exist), `skill_quality` (loaded for `/lp-create-skill` and `/lp-update-skill`). On a Python-only project, the TypeScript reviewer is filtered out at dispatch time.
