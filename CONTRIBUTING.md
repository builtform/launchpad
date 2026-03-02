# Contributing to Launchpad

Thank you for your interest in contributing to Launchpad. This document defines the branching model, coding standards, testing requirements, and PR process. Read it before making changes.

---

## Table of Contents

1. [Required Reading](#1-required-reading)
2. [Prerequisites](#2-prerequisites)
3. [Development Setup](#3-development-setup)
4. [Branch Naming](#4-branch-naming)
5. [Commit Conventions](#5-commit-conventions)
6. [Code Style](#6-code-style)
7. [Testing](#7-testing)
8. [File Placement](#8-file-placement)
9. [Pull Request Process](#9-pull-request-process)
10. [AI Workflow](#10-ai-workflow)
11. [Verification Protocol](#11-verification-protocol)
12. [Safe Refactoring](#12-safe-refactoring)
13. [Documentation](#13-documentation)
14. [Issue Reporting](#14-issue-reporting)

---

## 1. Required Reading

Before contributing, familiarize yourself with:

- `CLAUDE.md` -- AI agent operating rules and project-specific guardrails
- `docs/architecture/REPOSITORY_STRUCTURE.md` -- where every file type belongs (single source of truth)
- `.env.example` -- required environment variables

---

## 2. Prerequisites

- **Node.js** 22.x (pinned in `.nvmrc`)
- **pnpm** 9+ (install via `corepack enable`)
- **TypeScript** 5.x (installed as a workspace dependency)
- **Git** 2.x+

---

## 3. Development Setup

```bash
# Clone the repository
git clone https://github.com/thinkinghand/launchpad.git
cd launchpad

# Install all workspace dependencies and set up lefthook git hooks
pnpm install

# Copy environment template and fill in values
cp .env.example .env.local

# Start dev servers (all apps via Turborepo)
pnpm dev
```

Secrets live only in `.env.local` at the repo root. This file is gitignored. Never inline secrets in commands or commit them to the repository.

---

## 4. Branch Naming

No direct pushes to `main`. All work happens on branches; maintainers merge.

```bash
git switch main && git pull origin main
git switch -c feat/<topic>
```

Branch prefixes:

| Prefix             | Use for                                   |
| ------------------ | ----------------------------------------- |
| `feat/<topic>`     | New feature                               |
| `fix/<topic>`      | Bug fix                                   |
| `chore/<topic>`    | Maintenance, dependency updates, config   |
| `docs/<topic>`     | Documentation only                        |
| `refactor/<topic>` | Code change with no functional difference |
| `test/<topic>`     | Test-only changes                         |
| `style/<topic>`    | Formatting, style -- no logic change      |
| `perf/<topic>`     | Performance improvement                   |
| `ci/<topic>`       | CI/CD changes                             |

---

## 5. Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Examples:

```
feat(web): add user profile page
fix(api): correct auth token expiry handling
chore(deps): upgrade typescript to 5.5
docs(architecture): update decision tree in REPOSITORY_STRUCTURE.md
```

Keep the subject line under 72 characters. Do not reference AI assistants in commit messages.

---

## 6. Code Style

Formatting and linting are enforced automatically. Do not manually fix style issues that tooling handles.

| Tool       | Scope                       | Run              |
| ---------- | --------------------------- | ---------------- |
| ESLint     | TypeScript / JavaScript     | `pnpm lint`      |
| Prettier   | All files                   | `pnpm format`    |
| TypeScript | Type checking (strict mode) | `pnpm typecheck` |
| Vitest     | Unit and integration tests  | `pnpm test`      |

Configuration:

- **ESLint** uses flat config (ESLint 9) shared via `packages/eslint-config/`.
- **TypeScript** runs in strict mode. Shared presets live in `packages/typescript-config/`.
- **Prettier** handles all formatting. Auto-fix with `pnpm format`.

Pre-commit hooks (via lefthook) run lint, format, and structure checks on every commit. They are installed automatically when you run `pnpm install`. Do not bypass them with `--no-verify`; CI will fail regardless.

---

## 7. Testing

Run the full quality suite before opening a PR:

```bash
pnpm typecheck        # TypeScript type check (no emit)
pnpm lint             # ESLint across all workspaces
pnpm test             # Vitest unit and integration tests
pnpm format --check   # Prettier formatting check
```

All four must pass locally. CI re-runs the same suite in a clean environment and blocks merging on failure.

Write tests for new behavior. Place them next to the code they test or in the app's `tests/` directory.

---

## 8. File Placement

Before creating, moving, or deleting any file, read the decision tree in `docs/architecture/REPOSITORY_STRUCTURE.md` (Section 7). It maps every file type to the correct directory.

Key rules:

- Do not place files at the repository root unless they are on the whitelist in REPOSITORY_STRUCTURE.md.
- Do not create `file 2.ts`, `file v2.ts`, or `file copy.ts` variants anywhere. Use `docs/experiments/<topic>/` for prototypes.
- Shared TypeScript types go in `packages/shared/src/types/`. App-local types stay in the app's own `types/` directory.
- Database schema and migrations live in `packages/db/prisma/` -- never in `apps/api/`.
- Repo-wide scripts go in `scripts/maintenance/` or `scripts/agent_hydration/`. App-specific scripts go inside the app directory.

CI enforces the structure on every PR via `scripts/maintenance/check-repo-structure.sh`. When uncertain, ask rather than guessing.

---

## 9. Pull Request Process

1. Push your branch and open a PR against `main`.
2. Fill out the PR template in `.github/pull_request_template.md`. Include a summary of what changed and why, a link to the relevant issue, and manual test evidence using the VERIFIED/UNVERIFIED format (see Section 11).
3. CI must pass before the PR is reviewed. Fix failures promptly.
4. Maintainers merge. Do not merge your own PR.

PRs that omit test evidence, break CI, or contain files in incorrect locations will be sent back for revision.

---

## 10. AI Workflow

Launchpad ships with built-in AI development workflows for contributors using [Claude Code](https://claude.ai/claude-code) or similar tools.

### Slash Commands

| Command                | Purpose                                                       |
| ---------------------- | ------------------------------------------------------------- |
| `/commit`              | Guided commit workflow with quality gates and Codex review    |
| `/inf`                 | Implement next feature: autonomous pipeline from report to PR |
| `/define-product`      | Populate PRD and tech stack docs through guided Q&A           |
| `/define-architecture` | Populate architecture docs (requires PRD + tech stack first)  |
| `/create_plan`         | Create a structured implementation plan                       |
| `/implement_plan`      | Execute an existing plan step by step                         |
| `/research_codebase`   | Deep codebase research and analysis                           |

### Automation Scripts

| Script                              | Purpose                                     |
| ----------------------------------- | ------------------------------------------- |
| `scripts/compound/auto-compound.sh` | Full pipeline: report to PRD to tasks to PR |
| `scripts/compound/loop.sh`          | Execution loop with archive support         |

These commands and scripts are optional. You can contribute to Launchpad using a standard Git workflow without any AI tooling.

---

## 11. Verification Protocol

When making claims about system state, test results, or performance in a PR description or issue, tag them explicitly:

- `VERIFIED` -- you ran the command and saw the output
- `UNVERIFIED` -- you have not run this yet, or it is an assumption

Example:

```
VERIFIED: pnpm test passes (12 tests, 0 failures) -- run 2026-02-25
UNVERIFIED: behavior under concurrent load -- command to verify: pnpm test:load
```

Never state specific counts, timings, or success claims without evidence. Mark assumptions as UNVERIFIED and specify the command that would verify them.

---

## 12. Safe Refactoring

Use this protocol any time you are moving files, renaming directories, or removing duplicates.

1. Tag the current state: `git tag -a backup-before-refactor-$(date +%Y%m%d) -m "pre-refactor state"`
2. Compare duplicates before deleting -- check size, timestamps, and `git diff`.
3. Use `git mv` instead of `mv` to preserve file history.
4. One logical change per commit. Update all imports, then verify build and tests pass before moving on.
5. Never auto-delete based on filename patterns. When uncertain, move to `docs/archive/` instead.

To recover: `git checkout backup-before-refactor-YYYYMMDD -- path/to/file.ts`

---

## 13. Documentation

Update docs whenever behavior, scripts, or interfaces change.

| What changed          | Where to document it                                                                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| Architecture decision | `docs/architecture/decisions/ADR-<n>-<title>.md` (use template in REPOSITORY_STRUCTURE.md Section 10) |
| Lessons learned       | Append to `docs/lessons/LESSONS.md` -- never rewrite history                                          |
| Investigation result  | `docs/reports/investigation_YYYYMMDD_<topic>.md`                                                      |
| Temporary script      | Archive after use; do not leave one-off scripts in `scripts/`                                         |

---

## 14. Issue Reporting

When reporting a bug or blocker, include:

- The exact commands run
- Timestamps
- Raw output (not paraphrased)
- Environment details (OS, Node version, relevant package versions)

This applies both to GitHub issues and to comments in PRs. Vague reports delay resolution.

For security vulnerabilities, do not open a public issue. Follow the process in `SECURITY.md`.

---

## License

By contributing to Launchpad, you agree that your contributions will be licensed under the [MIT License](LICENSE).
