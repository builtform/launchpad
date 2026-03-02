# Changelog

All notable changes to Launchpad will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-01

### Added

- Opinionated monorepo scaffold with Next.js App Router, Tailwind CSS, and TypeScript
- Turborepo build system with shared packages (eslint-config, typescript-config, ui, shared, db)
- CLAUDE.md and AGENTS.md — AI instruction files for Claude Code integration
- Slash commands for AI-assisted workflows: /define-product, /define-architecture, /create_plan, /implement_plan, /inf, /commit
- Compound Product Pipeline for autonomous AI execution loops
- Ralph Loop integration for fresh-context compound development
- Spec-Driven Development methodology with canonical specs
- Repository structure enforcement via check-repo-structure.sh (364-line validator)
- Lefthook pre-commit hooks for quality gates (TypeScript, ESLint, Prettier)
- Codex AI code review via GitHub Actions
- Interactive project initialization wizard (init-project.sh)
- Template system for dual-identity files (Launchpad vs new project)
- Prisma database integration with PostgreSQL
- GitHub Actions CI/CD workflows
- Comprehensive documentation: architecture, operations, and workflow guides
