---
name: lp-ship
description: Autonomous shipping pipeline — quality gates, commit, PR creation, and CI monitoring. NEVER merges.
---

# /lp-ship

Autonomous shipping command. Stages changes, runs quality gates, commits, pushes, creates PR, and monitors CI. **NEVER merges.**

---

## Step 0: Prerequisite Check (Lite)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-ship --require=.launchpad/agents.yml,.launchpad/config.yml`.

Verify-or-refuse only. The lite helper checks both required files exist and exits 1 with a pointer to `/lp-define` if either is missing. `/lp-ship` never writes `agents.yml` or `config.yml` — those are owned by `/lp-define`.

---

## Step 1: Branch Guard

1. Read `protected_branches` from `.launchpad/agents.yml` (default: `[main, master]`)
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

- **Agent A**: use the shared build-runner for all quality stages — `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=test`, then `--stage=typecheck`, then `--stage=lint`. Reads `config.yml` `commands.*` so behavior adapts per-stack (e.g. `pnpm test` for TS, `pytest` for Python, both serial for polyglot).
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
- Do NOT add a `Co-Authored-By: Claude` (or any AI co-authorship) trailer
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

### Gate B: Advisory AI Reviews (non-blocking on timeout)

Two complementary AI reviewers post advisory comments on the PR. Both are non-blocking — if either is unavailable, missing, or quota-failed, the gate passes. Codex is the **narrow / line-level** lane; Greptile is the **wide / codebase-aware** lane.

#### Gate B1: Codex Review

- Poll for the Codex review comment (header `## Codex Automated Code Review`) for up to 5 minutes
- IF no comment: pass
- IF comment: parse P0–P3 sections, evaluate each finding (AGREE/PARTIALLY AGREE/DISAGREE)
- Auto-fix AGREE items only. Max 3 fix rounds, then stop.
- Apply sensitive file denylist: if a Codex suggestion targets auth/middleware/security paths → report "Needs manual review" instead of auto-fixing.

#### Gate B2: Greptile Review

- Poll for the Greptile review comment (header `### Greptile Summary`, posted by `greptile-apps[bot]`) for up to 5 minutes
- IF no comment: pass (Greptile may not be installed on this repo or not yet indexed)
- IF comment: parse the **Confidence Score** (1/5 to 5/5) and any inline finding tables
- Treat Greptile as a **codebase-aware second opinion**: it sees cross-file consistency, architectural drift, and convention violations Codex misses by design
- Auto-fix only findings Greptile marks high-confidence AND that align with Codex (when both agree, signal is strongest)
- DISAGREE findings (Greptile flags, Codex doesn't) → present to user without auto-fix, let them decide
- Same sensitive-file denylist applies

Both gates are skip-on-timeout. Skip human review gate (autonomous).

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
