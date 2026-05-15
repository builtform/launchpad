---
name: lp-commit
description: "Stage changes, run quality gates, generate a conventional commit message, and optionally create a PR with CI monitoring"
---

# Commit Workflow

You are a disciplined commit agent for a TypeScript monorepo. Follow every step in order. Never skip steps. Never use `--no-verify`.

## Arguments

`$ARGUMENTS` may contain `--skip-review` (literal flag, no value). Emergency-hotfix bypass for Step 2.5 mandatory dual-pass review. Honored ONLY when the EXACT literal token `--skip-review` appears as a whitespace-delimited token in `$ARGUMENTS`.

**Matching algorithm (pinned):** split `$ARGUMENTS` on whitespace; flag is honored iff `'--skip-review'` is in the resulting token list. Substring matches, prefix matches, value-form (`--skip-review=...`), single-dash form (`-skip-review`), and typo variants are NOT honored.

**Near-miss warning:** if `$ARGUMENTS` contains a token starting with `--skip` or `-skip` other than the exact literal, emit on stderr: `"Warning: '<token>' near-miss for review-bypass flag; use bare '--skip-review'. Treating as unset; mandatory review will run."`

**Malformed-form warning:** if `$ARGUMENTS` contains `--skip-review=*`, emit on stderr: `"Warning: '--skip-review=*' form ignored; flag is presence-only; treating as unset; mandatory review will run."`

**Idempotence:** duplicate flag is honored exactly once.

**Scope:** consumed at Step 2.5 ONLY. Steps 0, 1, 3-9 unaffected. `/lp-commit` does NOT pass `$ARGUMENTS` flags through to `/lp-review`.

**Protected-branch gate:** see Step 1 clause 4.5.

## Allowed Tools

Bash, Read, Grep, Glob, Edit, Write, TodoWrite, Task

---

## Step 0: Prerequisite Check (Lite)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-commit --require=.launchpad/agents.yml,.launchpad/config.yml`.

This is **verify-or-refuse only** — the lite helper checks each required file exists and exits 1 with a pointer to `/lp-define` when any is missing. It does NOT create missing files and does NOT run the full detect/classify/present/scaffold protocol (that's harness-level). If either `.launchpad/agents.yml` or `.launchpad/config.yml` is missing, the helper refuses; halt with the printed error and run `/lp-define` to seed them.

Both files are required: `agents.yml` defines the review-agent roster and protected branches, and `config.yml` defines the quality-gate commands the runner executes in Step 5. Without `config.yml`, the runner has no commands to dispatch and would silently exit 0 — leaving test/typecheck/lint un-run.

`/lp-define` is the authoritative seeder for both files; `/lp-commit` never writes them.

---

## Step 1: Branch Guard

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
HAS_HEAD=$(git rev-parse --verify HEAD 2>/dev/null && echo yes || echo no)
```

### Step 1.A: Initial-scaffold mode (v2.1.5 BL-338)

Initial-scaffold mode applies ONLY when `HAS_HEAD == no` (the repo genuinely has no commits yet). The mode bypasses the protected-branch reject AND the Step 2.5 mandatory dual-pass review — the same gate `--skip-review` has to satisfy with TTY confirmation + hotfix branch + audit trailer. Allowing the bypass on existing-history repos would open a wider review-skip path than `--skip-review` itself.

Per Codex/Greptile review on PR #68: `--initial-scaffold` is NOT a user-passable flag in this hardened shape. The mode triggers AUTOMATICALLY on `HAS_HEAD == no`. If a user passes `--initial-scaffold` in `$ARGUMENTS` while `HAS_HEAD == yes`, REJECT with: `"--initial-scaffold rejected: repo already has commits (HEAD exists). Initial-scaffold mode only applies to the very first commit on a freshly-initialized repo. For subsequent commits use the normal feature-branch + dual-pass review workflow, or --skip-review for hotfix branches."` Exit non-zero.

Auto-detect flow (when `HAS_HEAD == no`):

1. Prompt: **"This looks like the first commit on a freshly-initialized repo. Commit on `main` as an initial-scaffold commit? (y/N)"**
2. If `y`, proceed in initial-scaffold mode.
3. If `n`, abort with: `"aborted — create a feature branch first, then re-run /lp-commit"`. Do NOT auto-create.

In initial-scaffold mode:

- Skip Step 2.5 mandatory review (no diff base; nothing to review against)
- Allow commit on `main` (override the protected-branch reject)
- Emit a Step 7 trailer of `Initial-Scaffold: true` instead of `Mandatory-Review-Skipped: emergency-hotfix` — the latter is reserved for emergency hotfixes and would mislabel an initial-scaffold commit in the audit-trail
- Include in the commit body: `This is the initial-scaffold commit for the project. Subsequent commits MUST follow the feature-branch + dual-pass review workflow.`

After auto-detection, proceed to Step 2 directly. Skip the rest of Step 1 (branch suggestion) since the commit is intentionally landing on `main`.

### Step 1.B: Normal branch guard

(skipped if Step 1.A's initial-scaffold mode is active)

1. Read `protected_branches` from `.launchpad/agents.yml` (default: `[main, master]`)
2. IF `BRANCH` is in `protected_branches`: **Do NOT commit on a protected branch.** Instead:
3. Look at the staged or unstaged changes to infer the intent (new feature, bug fix, config change, etc.)
4. Suggest a branch name following the naming convention below
5. Ask the user: **"You are on main. I suggest creating branch `<suggested-name>`. Use this name, or provide a different one?"**
6. Once the user confirms or provides a name, create and switch to the branch:

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

### 4.5. `--skip-review` protected-branch gate

a. **Protected-branch reject:** if `$ARGUMENTS` contains `--skip-review` AND current branch is in `protected_branches` (default `[main, master]`) OR matches glob `release/*` / `releases/*` / `release-*` / `prod/*` / `production/*` / `stable/*` / `master_*` OR regex `^v[0-9]`: REJECT with `"--skip-review rejected on protected branches (current: $BRANCH). Emergency-hotfix bypass is allowed only on hotfix/* / fix/* feature branches."` Exit non-zero.

b. **Hotfix-branch interactive confirmation (TTY-guarded):** if `$ARGUMENTS` contains `--skip-review` AND current branch matches `hotfix/*` or `fix/*`:

```bash
if [[ ! -t 0 ]]; then
  echo "Error: --skip-review requires interactive TTY confirmation (got piped/redirected stdin or non-tty). To bypass review, re-run interactively without piping. Aborting." >&2
  exit 1
fi
echo "EMERGENCY HOTFIX BYPASS — type 'BYPASS REVIEW' (case-sensitive) to confirm:"
read -r CONFIRM
if [[ "$CONFIRM" != "BYPASS REVIEW" ]]; then
  echo "Confirmation phrase mismatch; aborting commit." >&2
  exit 1
fi
```

c. **CI/automation contract:** CI pipelines MUST NOT invoke `/lp-commit --skip-review`. The gate is human-only by design (interactive-only via `/lp-commit`). For CI commit paths that legitimately need to bypass review (e.g., dependabot bumps, release-tag commits), use the appropriate non-`/lp-commit` git path; `/lp-commit --skip-review` is exclusively for emergency-hotfix human invocations.

d. **Audit-trail caveat:** TTY guard is defense-in-depth against piped-stdin self-answer. It is NOT a forcing function against agentic callers in interactive TTY contexts (sibling Claude agent in interactive shell can still self-answer). The CONTRACT against agentic bypass is audit-trail-based (Step 7 `Mandatory-Review-Skipped` trailer + post-hoc `git log --grep` search). Technical blocking against agentic callers is a v2.1.x backlog item.

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

## Step 2.5: Mandatory Dual-Pass Code Review

Run BOTH `/lp-review` passes sequentially. MANDATORY (no yes/no prompt). Bypass only via `--skip-review` per the Arguments block (gated on branch + TTY per Step 1 clause 4.5).

**Sequential CONTRACT (advisory):** specialist pass MUST complete before blind pass per `/lp-review`'s caller contract. Parallel invocation is undefined behavior. v2.1.1 ships this as spec-text CONTRACT; runtime enforcement (sentinel-based mutex) is deferred to v2.1.2.

**Implementation note for sibling:** invoke specialist + blind in TWO SEPARATE Bash tool calls (specialist returns, then blind invoked). A single tool call with both passes concurrently is parallel and corrupts findings.

**`--skip-review` honored:** if the Arguments block matches AND Step 1 clause 4.5 gate passed, log on stderr: `"Mandatory dual-pass review SKIPPED — --skip-review flag invoked (emergency hotfix path; trailer written at Step 7; review must be triaged post-merge)"`. Proceed to Step 3.

**Default:** mandatory dual-pass.

Total timeout: 35 min. On timeout: surface partial state; abort commit.

### Sequential execution

1. **Specialist pass.** Run `/lp-review --headless`. Wait for completion (`.harness/todos/` populated; `.harness/review-summary.md` written with default sections).
2. **Blind pass.** Run `/lp-review --headless --no-context`. Append-mode: `.harness/todos/` is appended; `.harness/review-summary.md` gets `## --no-context (blind) findings` section appended.

### Triage and resolution

3. IF `.harness/todos/` empty: log "Dual-pass review passed — zero findings." Continue to Step 3.
4. IF findings present: run `/lp-triage` interactively.
5. IF any `fix`-marked: run `/lp-resolve-todo-parallel`.
6. Re-stage: `git add` resolver-reported files. Check untracked. Re-run secret scan. Show `git diff --cached --stat`.
7. Continue to Step 3.

**Single-cycle interactive contract:** Step 2.5 does NOT re-run dual-pass after `/lp-resolve-todo-parallel`. Subtle review-class regressions on resolver-introduced changes flow to Step 9 Gate B2/B3 post-PR.

### Failure handling

- Specialist error: STOP and surface; abort commit.
- Blind error: STOP and surface; specialist findings retained; abort commit.
- `/lp-triage` Ctrl-C: STOP. Recovery: run `/lp-triage` standalone; then re-run `/lp-commit`.
- Resolver unresolved findings: stage what was resolved; surface unresolved; ask proceed/abort.

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

Run sequentially within this agent, using `config.yml` `commands.*` (via the shared build-runner) so these work in any stack, not just TS/pnpm:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=test
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=typecheck
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=lint
```

The runner reads `.launchpad/config.yml` `commands.*` arrays. Empty arrays skip silently. Any non-zero exit stops the stage with a clear error.

Report pass/fail for each stage with exit codes.

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
EOF
)"
```

**IF `$ARGUMENTS` contained `--skip-review` AND it was honored at Step 2.5:** append the audit-trail trailer BELOW the bullet block, separated by ONE blank line:

```bash
git commit -m "$(cat <<'EOF'
type(scope): description

- bullet points if applicable

Mandatory-Review-Skipped: emergency-hotfix
EOF
)"
```

The trailer follows verb-noun convention. Value pinned to closed enum `{emergency-hotfix}` at v2.1.1; future enum extension requires schema-version bump.

**IF Step 1.A initial-scaffold mode was active (v2.1.5 BL-338):** append the `Initial-Scaffold: true` trailer instead of the `Mandatory-Review-Skipped` trailer, and include the initial-scaffold body line:

```bash
git commit -m "$(cat <<'EOF'
type(scope): description

- bullet points if applicable

This is the initial-scaffold commit for the project. Subsequent commits
MUST follow the feature-branch + dual-pass review workflow.

Initial-Scaffold: true
EOF
)"
```

The two trailers are mutually exclusive — a single commit emits at most one of them, since their bypass paths are disjoint by construction (initial-scaffold requires `HAS_HEAD == no`; `--skip-review` requires `HAS_HEAD == yes` AND a hotfix branch).

**Audit-log dual-write deferred to v2.1.2:** the trailer is the canonical audit record for v2.1.1. Reviewer-facing visibility comes from `git log --grep='Mandatory-Review-Skipped'` or `git log --grep='Initial-Scaffold'` searches.

Do NOT add a `Co-Authored-By: Claude` (or any AI co-authorship) trailer. AI attribution in commit messages is intentionally omitted from this plugin's commit format.

Run `git status` after commit to verify success.

After successful commit, run `/lp-regenerate-backlog` to update the project backlog (unstaged — picked up by next workflow).

---

## Step 8: Offer PR Creation

Ask the user: **"Push and create a PR?"**

If yes:

1. Sync with main before pushing:

```bash
git fetch origin main
git merge origin/main
```

- IF merge brings new changes: re-run quality gates by invoking the build runner once per stage:

  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=test \
    && python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=typecheck \
    && python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=lint
  ```

  IF they fail, fix before proceeding.

- IF merge has conflicts: resolve them, re-run quality gates, re-stage.
- IF merge is a no-op (already up to date): proceed.

2. Push the branch:

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

- [ ] Tests pass: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=test`
- [ ] Type check passes: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=typecheck`
- [ ] Lint passes: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=lint`
- [ ] Pre-commit hooks pass: `lefthook run pre-commit`

## Callouts for reviewers

<!-- Numbered list of specific things to look at closely. Optional but encouraged on non-trivial changes. -->
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

### Gate B2: Codex Automated Review (narrow / line-level lane)

LaunchPad ships with **two complementary AI code reviewers** on every PR. Both are advisory — neither blocks merge — and they cover different lanes:

- **Codex** (this gate B2) — line-level review on the diff, posted as a P0–P3 ranked comment by the `codex-review.yml` GitHub Action. Quota-bounded; may skip silently if `OPENAI_API_KEY` is not configured or quota is exhausted.
- **Greptile** (gate B3 below) — codebase-wide review using a pre-indexed graph of the entire repo, posted by the `greptile-apps[bot]`. Free for OSS repos under Greptile's program; covers cross-file consistency and architectural drift Codex cannot see.

Both gates are non-blocking on timeout — if either reviewer is unavailable, missing, or has not yet posted within the polling window, the gate passes.

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

### Gate B3: Greptile Automated Review (wide / codebase-aware lane)

Poll for the Greptile review comment (posted by `greptile-apps[bot]` on every PR if the App is installed and the repo is indexed):

```bash
gh api repos/{owner}/{repo}/issues/{pr_number}/comments \
  --jq '[.[] | select(.user.login == "greptile-apps[bot]")] | last'
```

- **Poll for up to 5 minutes** (10 checks, 30 seconds apart). If no Greptile comment appears within that window, pass — this gate is non-blocking on timeout (Greptile may not be installed on this repo, or the initial repo index may still be running).
- When the comment arrives, parse:
  - The **Confidence Score** (1/5 to 5/5) — Greptile's overall safety judgment for this PR
  - The **Greptile Summary** section — natural-language synthesis of what changed and any concerns
  - Any **Important Files Changed** table or inline finding callouts
- Greptile findings are **codebase-aware** by design. Where Codex would only see the diff, Greptile validated cross-file consistency, naming conventions across the repo, and architectural drift. Treat its findings as a second opinion focused on the lanes Codex cannot cover.
- Evaluation process for each Greptile finding (same as Codex):
  1. Read the referenced file and surrounding context
  2. Determine whether the issue actually exists, or is a false positive (Greptile is documented to have higher recall but higher false-positive rate than Codex)
  3. Form an opinion (AGREE / PARTIALLY AGREE / DISAGREE) with a one-sentence justification
- Where Codex (B2) and Greptile (B3) **both flag the same line**, the signal is strongest — prioritize fixing those.
- Where Greptile flags something Codex did not, weigh the cross-file evidence in Greptile's comment (it explains _why_ via its repo graph). Present to the user with "Greptile-only finding" labeling so they can judge whether the cross-file context justifies the fix.

### Gate C: Conflicts

```bash
gh pr view --json mergeable
```

- If not mergeable: rebase on main, resolve conflicts, re-run quality gates, push with `git push --force-with-lease` (only on feature branches, never main), and restart this loop.

### Loop Exit

- All gates must pass on the **same cycle** to exit the loop.
- When all gates are green, notify the user: **"All CI checks pass, no outstanding reviews, Codex and Greptile reviews clean, and no conflicts. Ready to merge."**
- **NEVER auto-merge.** The user decides when to merge.

---

## Rules

1. Never commit on `main` or `master`.
2. Never use `--no-verify`.
3. Never auto-merge a PR.
4. Never skip quality gates.
5. Fix root causes, never work around failures.
6. Always use HEREDOC for commit messages.
7. Never add a `Co-Authored-By: Claude` (or any AI co-authorship) trailer.
8. Keep the subject line under 72 characters.
9. Use imperative mood in commit descriptions.
10. If any step fails, stop and fix before continuing.
