---
name: ship
description: Autonomous shipping pipeline — quality gates, commit, PR creation, and CI monitoring. NEVER merges.
---

# /ship

Autonomous shipping command. Stages changes, runs quality gates, commits, pushes, creates PR, and monitors CI. **NEVER merges.**

Consult the `lp-instructions` skill briefly for core conventions (Definition of Done, git-push discipline).

---

## Step 0: Ensure runtime state (brownfield self-heal)

1. If `.launchpad/agents.yml` does NOT exist AND `${CLAUDE_PLUGIN_ROOT}/data/agents.yml` exists: copy plugin default to `.launchpad/agents.yml`, inform user
2. If `.harness/` doesn't exist: `mkdir -p .harness` (may be read later for review-summary.md)

---

## Step 1: Branch Guard

1. Read `protected_branches` from `.launchpad/agents.yml` (default: `[main, master]` if file missing)
2. Get current branch: `git branch --show-current`
3. IF current branch is in `protected_branches`: **REFUSE.** "Cannot ship to protected branch."

## Step 2: Stage Changes

```bash
git add -u
```

- Stages modifications + deletions of **tracked files only**
- Does NOT add untracked files (no `.env.local`, no debug artifacts, no stray files)
- This is safer than `git add -A` while remaining autonomous

## Step 3: Skill Staleness Audit (silent)

```bash
bash scripts/hooks/audit-skills.sh
```

- Log output but NEVER prompt the user (autonomous)
- Non-blocking — proceed regardless of output
- Script self-throttles (14-day cooldown)
- If script doesn't exist, skip silently

## Step 4: Quality Gates (parallel) + Auto-Fix Cycle

Run in parallel:

- **Agent A**: `pnpm test && pnpm typecheck && pnpm lint`
- **Agent B**: `lefthook run pre-commit` (includes `check-repo-structure.sh`)

IF all pass → proceed to Step 5

IF any fail → **AUTO-FIX** (max 3 attempts):

1. Read error output, diagnose root cause
2. Fix the code
3. Stage fix (`git add -u`)
4. Re-run ALL quality gates from scratch
5. IF pass → proceed to Step 5
6. IF still failing after 3 attempts → **HARD STOP.** Report what failed.

- NEVER use `--no-verify`

## Step 5: Generate Commit Message

- Auto-generate conventional commit: `type(scope): description`
- No user approval needed (autonomous)

## Step 6: Commit + Sync + Push + PR

1. `git commit` using HEREDOC format
2. Sync with main before pushing:

   ```bash
   git fetch origin main
   git merge origin/main
   ```

   - IF merge brings new changes: re-run quality gates (Step 4). IF they fail, fix before proceeding.
   - IF merge has conflicts: resolve, re-run quality gates, re-stage.
   - IF already up to date: proceed.

3. `git push -u origin HEAD`
4. IF PR already exists for current branch (`gh pr view` succeeds): skip PR creation, proceed to Step 7
5. `gh pr create` with structured body:

```
## Summary
[From commit message]

## Review Findings
[From .harness/review-summary.md if exists]

## Test Plan
[Quality gate results]
```

## Step 7: PR Monitoring Loop (max 3 cycles)

### Gate A: CI Checks

- Poll `gh pr checks` (30s intervals, max 10 waits)
- IF failed: read logs, diagnose, fix, re-run Step 4, push, restart loop

### Gate B: Codex Review (non-blocking on timeout)

- Poll for Codex comment (max 5 min)
- IF no comment: pass
- IF comment: parse findings, evaluate each (AGREE/DISAGREE)
- Auto-fix AGREE items only. Max 3 fix rounds, then stop.
- Apply sensitive file denylist: if Codex suggestion targets auth/middleware/security paths → report "Needs manual review" instead of auto-fixing.
- Skip human review gate (autonomous)

### Gate C: Conflicts

- IF not mergeable: rebase, resolve, re-run gates, force-with-lease push
- Before `--force-with-lease`: check if remote branch has commits not in local (`git log HEAD..origin/<branch>`). If diverged, abort: "Remote has commits not in local. Manual resolution required."

**Loop Exit:** All gates green on same cycle → exit

## Step 8: Report (TERMINAL)

- Print PR URL
- Print gate status
- "PR is ready for human review and merge."
- **EXIT. NEVER merge. NEVER suggest merging. NEVER offer to merge.**

---

## Rules

1. **NEVER** run `gh pr merge`
2. **NEVER** run `git merge main/master`
3. **NEVER** auto-merge
4. **NEVER** skip quality gates
5. **NEVER** use `--no-verify`
