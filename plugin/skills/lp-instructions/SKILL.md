---
name: lp-instructions
description: Core LaunchPad principles, Definition of Done, and git conventions. Portable subset of CLAUDE.md that works across any project stack. Consult when planning commits, branches, or when quality standards matter.
---
# LaunchPad — Core Instructions

Universal subset of LaunchPad's conventions. Generic across project stacks (not tied to TypeScript / Prisma / Next.js specifics — those live in the project's own CLAUDE.md).

Priority A commands (`/lp-commit`, `/lp-ship`, `/lp-defer`) cross-reference this skill at the start of their flow.

---

## Core Principles

1. **Fix root causes.** Never work around errors without understanding them. Tracing an error to its origin is part of the job; patching a symptom without explanation is not.
2. **No secrets in commits.** Use `.env.local` (or project equivalent) + environment-variable reads. Secrets must never reach git history. When in doubt, refuse to commit.
3. **Production-first.** Choose the solution that scales to the production use case, not the one that's easiest locally. If production needs PostgreSQL, don't suggest SQLite.
4. **Use sub-agents for multi-step work.** Parallelize independent queries. Protect the main context window by delegating research or analysis to specialized agents. Report results back concisely.

---

## Definition of Done

Before closing any task, confirm:

- [ ] **Tests pass** — run the project's test command (e.g., `pnpm test`, `pytest`, `go test ./...`) and verify exit 0
- [ ] **Type/static checks pass** — run the project's typecheck command (e.g., `pnpm typecheck`, `mypy`, `tsc --noEmit`)
- [ ] **Lint passes** — no new lint errors compared to the starting state

If the project doesn't have one of these gates, note it explicitly rather than silently skipping.

---

## Git Conventions (branch prefixes)

LaunchPad uses semantic prefixes for feature branches. These map to conventional-commit-style types:

```
✨ feat/<topic>      # new feature
🐛 fix/<topic>       # bug fix
🧹 chore/<topic>     # maintenance, deps, config
📝 docs/<topic>      # documentation only
🔨 refactor/<topic>  # structural change, no behavior change
🧪 test/<topic>      # test-only changes
🎨 style/<topic>     # style only
🚀 perf/<topic>      # performance improvement
⚡ ci/<topic>        # CI/CD changes
```

Warn the user (don't block) if a branch doesn't match these prefixes.

---

## Never-Do Guardrails (universal)

| Don't                                                       | Do Instead                                                 | Why                                                           |
| ----------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------- |
| Inline secrets in commands                                  | Load from env or secret manager                            | Secrets in history are permanent                              |
| Bypass pre-commit hooks with `--no-verify`                  | Fix the issue and try again                                | CI will catch it anyway                                       |
| Create `<file> 2.ext` / `<file> copy.ext` / `<file> v2.ext` | Use a dedicated experiments directory                      | Finder-duplicate artifacts break tooling                      |
| `git push --force` to protected branches (main/master)      | Use `--force-with-lease` only to your own feature branches | Prevents clobbering others' work                              |
| `git merge main` (into feature branches)                    | `git merge origin/main`                                    | Keeps remote and local in sync; avoids fast-forward surprises |

Project-specific guardrails (e.g., "don't use `prisma migrate dev`") belong in the project's own CLAUDE.md, not in this skill.

---

## Scope

This skill is the portable core. Project-specific details (tech stack, codebase map, Progressive Disclosure pointers) belong in the project's own CLAUDE.md. Users who want stronger always-on enforcement can copy the relevant content here into their project CLAUDE.md — the plugin itself never writes to user files.
