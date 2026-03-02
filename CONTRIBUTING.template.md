# Contributing to {{PROJECT_NAME}}

<!-- TEMPLATE: This is a template file for new projects created from Launchpad.
     The init-project.sh script will process this file and replace placeholders.
     Placeholders: {{PROJECT_NAME}}, {{REPO_URL}}
     Remove this comment block once the file reflects your project. -->

Thank you for your interest in contributing to {{PROJECT_NAME}}. This document covers everything you need to get started: prerequisites, development setup, coding standards, and the pull request process.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Prerequisites](#2-prerequisites)
3. [Development Setup](#3-development-setup)
4. [Branch Naming](#4-branch-naming)
5. [Commit Conventions](#5-commit-conventions)
6. [Code Style](#6-code-style)
7. [Testing](#7-testing)
8. [Pull Request Process](#8-pull-request-process)
9. [File Placement](#9-file-placement)
10. [Documentation](#10-documentation)
11. [Issue Reporting](#11-issue-reporting)

---

## 1. Getting Started

Before contributing, read:

- `README.md` -- project overview and quick start
- `docs/architecture/REPOSITORY_STRUCTURE.md` -- where every file type belongs

<!-- Add any additional required reading specific to your project here. -->

---

## 2. Prerequisites

- **Node.js** 22.x (pinned in `.nvmrc`)
- **pnpm** 9+ (install via `corepack enable`)
- **Git** 2.x+

<!-- Add additional prerequisites here (e.g., Docker, Python, specific CLI tools). -->

---

## 3. Development Setup

```bash
# Clone the repository
git clone {{REPO_URL}}
cd {{PROJECT_NAME}}

# Install all workspace dependencies
pnpm install

# Copy environment template and fill in values
cp .env.example .env.local

# Start development servers
pnpm dev
```

Secrets live only in `.env.local` at the repo root. This file is gitignored. Never inline secrets in commands or commit them to the repository.

---

## 4. Branch Naming

No direct pushes to `main`. All work happens on branches.

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
```

Keep the subject line under 72 characters.

---

## 6. Code Style

Formatting and linting are enforced automatically. Do not manually fix style issues that tooling handles.

| Tool       | Scope                   | Run              |
| ---------- | ----------------------- | ---------------- |
| ESLint     | TypeScript / JavaScript | `pnpm lint`      |
| Prettier   | All files               | `pnpm format`    |
| TypeScript | Type checking           | `pnpm typecheck` |

<!-- Add additional tools here (e.g., Ruff for Python, Stylelint for CSS). -->

Pre-commit hooks (via lefthook) run lint and format checks on every commit. They are installed automatically when you run `pnpm install`. Do not bypass them with `--no-verify`.

---

## 7. Testing

Run the full quality suite before opening a PR:

```bash
pnpm typecheck        # TypeScript type check (no emit)
pnpm lint             # ESLint across all workspaces
pnpm test             # Unit and integration tests
pnpm format --check   # Prettier formatting check
```

All checks must pass locally. CI re-runs the same suite and blocks merging on failure.

Write tests for new behavior. Place them next to the code they test or in the app's `tests/` directory.

<!-- Customize this section with your project's specific testing strategy,
     coverage thresholds, or additional test commands. -->

---

## 8. Pull Request Process

1. Push your branch and open a PR against `main`.
2. Include a summary of what changed and why, and link to the relevant issue if one exists.
3. CI must pass before the PR is reviewed. Fix failures promptly.
4. Maintainers review and merge. Do not merge your own PR unless you are a sole maintainer.

<!-- Add specific PR template requirements, review criteria, or approval
     thresholds for your project here. -->

---

## 9. File Placement

Before creating, moving, or deleting any file, check `docs/architecture/REPOSITORY_STRUCTURE.md` for the canonical location of each file type.

Key rules:

- Do not place files at the repository root unless explicitly allowed.
- Do not create `file 2.ts`, `file v2.ts`, or `file copy.ts` variants. Use a dedicated experiments or prototypes directory for exploratory work.
- Shared code belongs in `packages/`. App-specific code stays in the app directory.

<!-- Customize these rules to match your project's directory conventions. -->

---

## 10. Documentation

Update docs whenever behavior, scripts, or interfaces change.

| What changed          | Where to document it                   |
| --------------------- | -------------------------------------- |
| Architecture decision | `docs/architecture/decisions/`         |
| New feature           | Update `README.md` and relevant guides |
| API change            | Update API documentation               |
| Configuration change  | Update `.env.example` and docs         |

<!-- Add project-specific documentation conventions here. -->

---

## 11. Issue Reporting

When reporting a bug, include:

- The exact commands run
- Raw output (not paraphrased)
- Environment details (OS, Node version, relevant package versions)
- Steps to reproduce

For security vulnerabilities, do not open a public issue. Follow the process in `SECURITY.md`.

---

## License

By contributing to {{PROJECT_NAME}}, you agree that your contributions will be licensed under the project's license. See `LICENSE` for details.
