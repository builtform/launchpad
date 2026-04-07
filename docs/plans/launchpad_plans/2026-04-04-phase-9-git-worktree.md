# Phase 9: Git Worktree Configuration

**Date:** 2026-04-04
**Depends on:** None (configuration only — no pipeline components)
**Branch:** `feat/git-worktree`
**Status:** Plan — v1 final (reviewer fixes)

---

## Decisions (All Finalized)

| Decision                      | Answer                                                                                                                                                                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Approach                      | Configure Claude Code's native worktree support — no custom skill, script, or command                                                                                                                                           |
| CE skill ported?              | No. CE's `git-worktree` skill (302 lines) and `worktree-manager.sh` (337 lines) are superseded by Claude Code's built-in `--worktree` flag, `EnterWorktree`/`ExitWorktree` tools, and `isolation: "worktree"` on the Agent tool |
| Env file handling             | `.worktreeinclude` file (Claude Code native — uses `.gitignore` syntax, copies only gitignored files that match patterns)                                                                                                       |
| Dependency installation       | None automated. Claude runs `pnpm install` when it enters a worktree and discovers missing `node_modules`. Cost: ~1500 tokens once per worktree creation — negligible vs pipeline total                                         |
| `WorktreeCreate` hook         | Not used. Token savings (~1500) don't justify the complexity (stdout contract fragility, must reimplement `.worktreeinclude` processing, maintenance burden)                                                                    |
| `worktree.symlinkDirectories` | Not used for `node_modules`. Breaks pnpm's own symlink structure and causes Vitest/Vite tooling failures. Community consensus: never symlink `node_modules` in pnpm monorepos                                                   |
| `worktree.sparsePaths`        | Not used. LaunchPad monorepo is not large enough to need sparse checkout                                                                                                                                                        |
| Pipeline changes              | None. Worktree isolation happens at the session level (`claude --worktree`) or agent level (`isolation: "worktree"`), not at the pipeline level. `/harness:build` and `/review` remain unchanged and fully autonomous           |
| Custom `/worktree` command    | Not created. Claude Code's native `--worktree` flag and `EnterWorktree` tool cover all use cases                                                                                                                                |
| `git-worktree` skill          | Not created. Claude Code's native worktree support makes a knowledge skill redundant                                                                                                                                            |
| Worktree location             | `.claude/worktrees/` (Claude Code default)                                                                                                                                                                                      |

---

## Purpose

Configure Claude Code's native git worktree support for LaunchPad's pnpm monorepo so that worktrees created via `claude --worktree`, `EnterWorktree`, or `isolation: "worktree"` on sub-agents automatically receive the correct environment files.

This enables:

- **Parallel development**: Run `claude --worktree feature-auth` in one terminal while working on main in another
- **Isolated agent work**: Sub-agents with `isolation: "worktree"` get their own worktree automatically
- **Safe experimentation**: Worktrees with no changes are auto-cleaned on session exit

---

## Why Not Port CE's Skill

Claude Code now provides first-class worktree support that did not exist when CE's `git-worktree` skill was written:

| CE Skill Operation             | Claude Code Native Equivalent                                    |
| ------------------------------ | ---------------------------------------------------------------- |
| `worktree-manager.sh create`   | `--worktree` flag, `EnterWorktree` tool                          |
| `worktree-manager.sh cleanup`  | Auto-cleanup on session exit (no changes = auto-remove)          |
| `worktree-manager.sh switch`   | `EnterWorktree` tool                                             |
| `worktree-manager.sh copy-env` | `.worktreeinclude` file (declarative)                            |
| `worktree-manager.sh list`     | `git worktree list` (native git command)                         |
| `.gitignore` management        | Already handled by Claude Code (`.claude/worktrees/` convention) |

The only operations CE's skill provided beyond native support are `list` (trivially available via `git worktree list`) and `copy-env` for existing worktrees (niche use case). Neither justifies 639 lines of custom code.

---

## Component Definitions

### 1. `.worktreeinclude` (new file)

**File:** `.worktreeinclude` (project root)
**Purpose:** Declare which gitignored files Claude Code should copy into new worktrees.

**Content:**

```
# Environment files — copied to worktrees automatically by Claude Code
# Uses .gitignore syntax. Only files that match AND are gitignored get copied.
# Glob pattern catches future .env.* additions automatically.
.env*
apps/**/.env*
packages/**/.env*
```

**Why these patterns:**

- `.env*` — root-level glob catches `.env`, `.env.local`, `.env.consultant`, `.env.migrate`, and any future `.env.*` additions automatically
- `apps/**/.env*` — catches any future env files in `apps/web/`, `apps/api/`
- `packages/**/.env*` — catches any future env files in `packages/db/`, `packages/shared/`

**Why not just `**/.env\*`?** Scoped patterns (`apps/**`, `packages/**`) prevent accidentally copying env files from unexpected locations (e.g., inside `node_modules/`or`.claude/worktrees/`itself). Though`.worktreeinclude`only copies gitignored files (and`node_modules` contents aren't individually gitignored), explicit scoping is defensive and self-documenting.

### 2. `.gitignore` update

**File:** `.gitignore` (project root)
**Change:** Add `.claude/worktrees/` entry.

```
# Claude Code worktrees (isolated parallel development sessions)
.claude/worktrees/
```

**Why:** Claude Code creates worktrees at `.claude/worktrees/<name>/`. These are ephemeral working directories that should never be committed. Claude Code's docs recommend adding this entry.

### 3. `scripts/setup/init-project.sh` update

**File:** `scripts/setup/init-project.sh`
**Change:** Scaffold `.worktreeinclude` and `.gitignore` entry for new downstream projects.

After the existing `docs/tasks/sections/` scaffolding block, add:

```bash
# Create .worktreeinclude for Claude Code worktree env file copying
if [ ! -f ".worktreeinclude" ]; then
  cat > .worktreeinclude <<'WTEOF'
# Environment files — copied to worktrees automatically by Claude Code
# Uses .gitignore syntax. Only files that match AND are gitignored get copied.
# Glob pattern catches future .env.* additions automatically.
.env*
apps/**/.env*
packages/**/.env*
WTEOF
  info "Created .worktreeinclude (Claude Code worktree env file declarations)"
fi

# Ensure .claude/worktrees/ is gitignored
if ! grep -q '\.claude/worktrees/' .gitignore 2>/dev/null; then
  printf '\n# Claude Code worktrees (isolated parallel development sessions)\n.claude/worktrees/\n' >> .gitignore
  info "Added .claude/worktrees/ to .gitignore"
fi
```

**Note:** Both the LaunchPad `.worktreeinclude` and the `init-project.sh` scaffold use the `.env*` glob pattern. Downstream projects can add project-specific scoped patterns (e.g., `config/**/.env*`) as needed.

---

## Changes to Existing Files

| File                            | Change                                               | Lines |
| ------------------------------- | ---------------------------------------------------- | ----- |
| `.gitignore`                    | Add `.claude/worktrees/` entry                       | +2    |
| `scripts/setup/init-project.sh` | Add `.worktreeinclude` scaffold + `.gitignore` entry | +15   |

---

## Verification Checklist

### Files Created

- [ ] `.worktreeinclude` exists at project root
- [ ] Contains `.env*` glob pattern (catches all root-level env files including future additions)
- [ ] Contains scoped glob patterns: `apps/**/.env*`, `packages/**/.env*`
- [ ] Uses `.gitignore` syntax (comments with `#`, one pattern per line)

### .gitignore

- [ ] `.claude/worktrees/` entry present in `.gitignore`
- [ ] Entry has a descriptive comment

### init-project.sh

- [ ] `.worktreeinclude` scaffolding added (creates file if not exists)
- [ ] `.gitignore` update added (appends if not already present)
- [ ] Base `.worktreeinclude` uses `.env*` glob pattern (same as LaunchPad)
- [ ] Idempotent — running twice does not duplicate entries

### Functional Verification (Implementation Time)

- [ ] `claude --worktree test-phase-9` creates a worktree at `.claude/worktrees/test-phase-9/`
- [ ] `.env.local` is automatically copied into the worktree
- [ ] `.env.consultant` is automatically copied into the worktree (if it exists)
- [ ] Worktree is excluded from git tracking (`.gitignore` works)
- [ ] Exiting the worktree session with no changes auto-cleans the worktree

---

## What This Does NOT Include

| Item                                                | Reason                                                                                                                                                                              |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CE's `git-worktree` skill (302 lines)               | Superseded by Claude Code native worktree support                                                                                                                                   |
| CE's `worktree-manager.sh` (337 lines)              | Superseded by Claude Code native worktree support                                                                                                                                   |
| Custom `/worktree` command                          | Native `--worktree` flag and `EnterWorktree` tool cover all use cases                                                                                                               |
| `WorktreeCreate` hook                               | Token savings (~1500/worktree) don't justify complexity (stdout contract, reimplementing `.worktreeinclude` parsing)                                                                |
| `WorktreeRemove` hook                               | No custom cleanup logic needed                                                                                                                                                      |
| `worktree.symlinkDirectories`                       | Breaks pnpm symlink structure; community consensus against it for `node_modules`                                                                                                    |
| `worktree.sparsePaths`                              | Monorepo not large enough to benefit                                                                                                                                                |
| `enableGlobalVirtualStore` in `pnpm-workspace.yaml` | Experimental, has concurrent install bugs (pnpm#10018) and ESM issues (pnpm#9618). Not appropriate for a template repo. Plain `pnpm install` with warm store (5-15s) is sufficient. |
| Pipeline changes to `/harness:build` or `/review`   | Worktree isolation is a session-level decision (`claude --worktree`), not a pipeline-level decision. Adding flags would break autonomous operation.                                 |

---

## File Change Summary

| File                            | Status   | Lines Changed |
| ------------------------------- | -------- | ------------- |
| `.worktreeinclude`              | **NEW**  | 7             |
| `.gitignore`                    | Modified | +2            |
| `scripts/setup/init-project.sh` | Modified | +15           |
