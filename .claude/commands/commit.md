# Commit Workflow

You are a disciplined commit agent for a TypeScript monorepo. Follow every step in order. Never skip steps. Never use `--no-verify`.

## Allowed Tools

Bash, Read, Grep, Glob, Edit, Write, TodoWrite, Task

---

## Step 1: Branch Guard

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
```

- If `BRANCH` is `main` or `master`: **Do NOT commit on main.** Instead:
  1. Look at the staged or unstaged changes to infer the intent (new feature, bug fix, config change, etc.)
  2. Suggest a branch name following the naming convention below
  3. Ask the user: **"You are on main. I suggest creating branch `<suggested-name>`. Use this name, or provide a different one?"**
  4. Once the user confirms or provides a name, create and switch to the branch:

```bash
git switch -c <branch-name>
```

Branch naming convention:

```
✨ feat/<topic>      - new feature
🐛 fix/<topic>       - bug fix
🧹 chore/<topic>     - maintenance, deps, config
📝 docs/<topic>      - documentation only
🔨 refactor/<topic>  - structural change, no new behavior
🧪 test/<topic>      - test-only changes
🎨 style/<topic>     - style only
🚀 perf/<topic>      - performance improvement
⚡ ci/<topic>        - CI/CD changes
```

- If the branch name does not match one of these prefixes, warn the user but do not block.

---

## Step 2: Stage and Review

1. Run `git status` (never use `-uall`).
2. Run `git diff --stat` and `git diff --staged --stat` to see what changed.
3. Present a concise summary of changes to the user:
   - Files added, modified, deleted
   - Approximate scope (which apps/packages affected)
4. Ask the user: **"Should I stage all changes, or do you want to select specific files?"**
5. Stage files according to user preference. Default to `git add -A` if user says "all".
6. After staging, run `git diff --cached --stat` to confirm what will be committed.

---

## Step 2.5: Optional Code Review

After staging, ask: **"Run code review before committing? (yes/no)"**

Total timeout for this step: 20 minutes. If exceeded, report: "Review chain exceeded timeout. Findings in .harness/todos/ — resolve with /resolve_todo_parallel."

### If yes:

1. Run `/review --headless` — dispatches review agents, writes findings to `.harness/todos/`
2. IF zero findings: "Code review passed." → continue to Step 3
3. IF findings: Run `/triage` — user sorts each finding (fix/drop/defer)
4. IF any findings marked "fix": Run `/resolve_todo_parallel` (max 5 concurrent agents)
5. Re-stage: `git add` resolver-reported files. Check for untracked files — ask to stage. Re-run secret scan on resolver-touched files. Show `git diff --cached --stat`.
6. Continue to Step 3

### If no:

Continue to Step 3 immediately.

---

## Step 3: Skill Staleness Audit

Run the skill staleness audit before committing:

```bash
bash scripts/hooks/audit-skills.sh
```

- If the audit outputs a staleness report, present it to the user as an informational notice.
- This is **non-blocking** — proceed to the next step regardless of output.
- The script self-throttles (runs the full check only once every 14 days).
- The script may update `docs/skills-catalog/skills-usage.json` (`last_audit_date`). Re-stage if modified:

```bash
git diff --quiet docs/skills-catalog/skills-usage.json || git add docs/skills-catalog/skills-usage.json
```

---

## Step 4: Quality Gates (Parallel)

Run these two groups in **parallel** using two sub-agents:

### Agent A: Tests and Type Checks

Run sequentially within this agent:

```bash
pnpm test
pnpm typecheck
pnpm lint
```

Report pass/fail for each command with exit codes.

### Agent B: Pre-commit Hooks

```bash
lefthook run pre-commit
```

Report pass/fail with full output on failure.

### Handling Failures

- **Any failure is a hard stop.** Do not proceed to commit.
- Diagnose the root cause. Fix the issue. Re-run the failing check.
- **NEVER suggest `--no-verify` or skipping hooks.** The hooks exist for a reason.
- **NEVER work around test failures.** Fix the actual bug.
- After fixing, re-run ALL quality gates from scratch to confirm nothing else broke.

---

## Step 5: Generate Commit Message

Generate a conventional commit message following this format:

```
type(scope): description
```

Rules:

- `type` is one of: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`
- `scope` is the affected app or package (e.g., `web`, `api`, `db`, `shared`, `ui`, `config`)
  - If changes span multiple packages, use the most significant one or omit scope
- `description` is imperative mood, lowercase, no period, under 72 characters total
- For non-trivial changes, add bullet points below the subject line explaining what and why

Example:

```
feat(web): add user profile settings page

- Add profile form component with validation
- Connect to /api/profile endpoint for persistence
- Include avatar upload with client-side resize
```

---

## Step 6: User Approval

Present the commit message to the user. Ask: **"Approve this commit message, or provide edits?"**

- If the user edits: apply their changes exactly.
- If approved: proceed to commit.

---

## Step 7: Commit

Create the commit using a HEREDOC to preserve formatting:

```bash
git commit -m "$(cat <<'EOF'
type(scope): description

- bullet points if applicable

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

Run `git status` after commit to verify success.

---

## Step 8: Offer PR Creation

Ask the user: **"Push and create a PR?"**

If yes:

1. Push the branch:

```bash
git push -u origin HEAD
```

2. Create the PR with structured body:

```bash
gh pr create --title "type(scope): description" --body "$(cat <<'EOF'
## Summary

- [Bullet point describing the change]
- [Another bullet point if needed]

## Changes

- `path/to/file` - what changed and why

## Test Plan

- [ ] Tests pass: `pnpm test`
- [ ] Type check passes: `pnpm typecheck`
- [ ] Lint passes: `pnpm lint`
- [ ] Pre-commit hooks pass: `lefthook run pre-commit`
EOF
)"
```

3. Print the PR URL for the user.

---

## Step 9: PR Monitoring Loop (max 3 cycles, 60min timeout)

After PR creation, enter the three-gate monitoring loop. Run all three gates on each cycle. Maximum 3 cycles. Maximum 60-minute total wall-clock timeout. Gate A CI polling capped at 20 retries (10 minutes) per cycle. After max cycles or timeout: "PR monitoring reached maximum cycles/timeout. Remaining issues require manual attention."

### Gate A: CI Checks

```bash
gh pr checks
```

- If checks are still pending (exit code 8): wait 30 seconds and re-check. Do not attempt to diagnose pending checks.
- If any check fails: read the CI logs with `gh run view <run-id> --log-failed`, diagnose the failure, fix locally, re-run quality gates (Step 4), push the fix, and restart this loop.

### Gate B1: Human Reviews

```bash
gh pr view --json latestReviews,comments
```

- If there are change requests: address each comment, make the fix, re-run quality gates (Step 4), commit, push, and restart this loop.

### Gate B2: Codex Automated Review

Poll for the Codex review comment (posted by the `codex-review.yml` GitHub Action):

```bash
gh api repos/{owner}/{repo}/issues/{pr_number}/comments \
  --jq '[.[] | select(.body | test("Codex Automated Code Review"))] | last'
```

- **Poll for up to 5 minutes** (10 checks, 30 seconds apart). If no Codex comment appears within that window, pass — this gate is non-blocking on timeout.
- When the comment arrives, parse **all** severity sections (P0, P1, P2, P3) from the body.
- If every section says "None found" or is empty: pass.
- If any findings exist, **evaluate each one independently** before presenting to the user:

#### Evaluation Process

For each finding in the Codex comment:

1. **Read the referenced file and line number** using the Read tool. Include surrounding context (±10 lines) to understand the code in situ.
2. **Determine accuracy:** Does the issue Codex describes actually exist in the code? Check for false positives — Codex may misread intent, miss context from other files, or flag patterns that are intentional.
3. **Assess severity:** Does Codex's severity rating (P0–P3) match the actual impact? A P0 may really be a P2 style nit, or a P2 may hide a genuine P0 bug.
4. **Form an opinion** for the finding — one of:
   - **AGREE** — the issue exists and the severity is appropriate.
   - **PARTIALLY AGREE** — the issue exists but the severity should be adjusted, or the description is misleading.
   - **DISAGREE** — the finding is a false positive, irrelevant, or the code is correct as-is.
5. **Write a one-sentence justification** explaining the opinion.

#### Presentation

Present all findings to the user grouped by Codex severity, with the agent's evaluation alongside each one:

```
## Codex Review Findings

### P0 — Critical
| # | File | Codex Description | Agent Opinion | Justification |
|---|------|-------------------|---------------|---------------|
| 1 | `path/to/file:42` | ... | AGREE | ... |

### P1 — High
| # | File | Codex Description | Agent Opinion | Justification |
|---|------|-------------------|---------------|---------------|
| 2 | `path/to/file:88` | ... | DISAGREE | ... |

### P2 — Medium
(same table format)

### P3 — Low
(same table format)
```

Omit any severity group that has no findings.

#### Verdict

After the tables, provide a **Verdict** section:

1. **Fix now** — list the finding numbers that should be addressed before merge, with a brief justification for each (e.g., "genuine null-pointer risk", "security implication").
2. **Defer or ignore** — list the finding numbers that should be skipped, with a brief justification for each (e.g., "false positive — variable is validated upstream", "style preference, not a bug").

#### User Decision

Ask: **"Should I fix the recommended issues, or do you want to adjust the list?"**

- If the user approves the recommended list: fix those issues, re-run quality gates (Step 4), commit, push, and restart this loop.
- If the user adjusts the list: fix only the user-specified issues, re-run quality gates (Step 4), commit, push, and restart this loop.
- If the user declines all fixes: note the user's decision and pass.

### Gate C: Conflicts

```bash
gh pr view --json mergeable
```

- If not mergeable: rebase on main, resolve conflicts, re-run quality gates, push with `git push --force-with-lease` (only on feature branches, never main), and restart this loop.

### Loop Exit

- All gates must pass on the **same cycle** to exit the loop.
- When all gates are green, notify the user: **"All CI checks pass, no outstanding reviews, Codex review clean, and no conflicts. Ready to merge."**
- **NEVER auto-merge.** The user decides when to merge.

---

## Rules

1. Never commit on `main` or `master`.
2. Never use `--no-verify`.
3. Never auto-merge a PR.
4. Never skip quality gates.
5. Fix root causes, never work around failures.
6. Always use HEREDOC for commit messages.
7. Always include the `Co-Authored-By` trailer.
8. Keep the subject line under 72 characters.
9. Use imperative mood in commit descriptions.
10. If any step fails, stop and fix before continuing.
