---
name: commit
description: "Stage changes, run quality gates (tests, linting, type checks, pre-commit hooks), generate a conventional commit message, and optionally create a PR with CI monitoring. Triggers on: commit changes, commit this, create commit, push and commit, commit my work, ready to commit."
---

# Commit Workflow

Runs the full commit pipeline: branch validation, staging, parallel quality gates, conventional commit message generation, and optional PR creation with CI monitoring.

---

## Trigger

Invoke with `/commit` or when the user says any of:

- "commit changes"
- "commit this"
- "create commit"
- "push and commit"
- "commit my work"
- "ready to commit"

## Behavior

Execute the commit command at `.claude/commands/commit.md`. Follow every step in order. Never skip quality gates. Never use `--no-verify`.

## Key Points

- Refuses to commit on `main` or `master`
- Runs tests, type checks, linting, and pre-commit hooks in parallel
- Generates conventional commit messages: `type(scope): description`
- Requires user approval before committing
- Optionally creates PR with structured body
- Monitors CI, reviews, and merge conflicts in a loop after PR creation
- Never auto-merges
