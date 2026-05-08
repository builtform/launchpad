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

## Step 4.6: Mandatory Dual-Pass Code Review (Autonomous)

After Step 4 quality gates pass, run BOTH `/lp-review` passes sequentially. MANDATORY. `/lp-ship` does NOT honor `--skip-review`.

**Pre-conditions:** Step 4's quality gates AND its 3-attempt auto-fix loop MUST pass before Step 4.6 runs. If Step 4 hard-stops, Step 4.6 is skipped; ship aborts.

**Sequential CONTRACT (advisory):** specialist pass MUST complete before blind pass per `/lp-review`'s caller contract. Spec-text only at v2.1.1 (runtime enforcement is deferred to v2.1.2). Invoke specialist + blind in TWO SEPARATE Bash tool calls.

**Total timeout:** 90 minutes (per-round budget ~25-30 min).

**Aggregate cap (post-flight):**

- Snapshot `STEP46_BASE_SHA = git rev-parse HEAD` at Step 4.6 entry.
- Hard caps: 50 files OR 500 LOC delta from `STEP46_BASE_SHA`. LOC formula: `insertions + deletions` from `git diff --shortstat $STEP46_BASE_SHA..HEAD`.
- Cap is checked AFTER each round's resolver completes. Pre-flight projection deferred to v2.1.2.

### Sequential dual-pass

1. **Specialist pass.** Run `/lp-review --headless`.
2. **Blind pass.** Run `/lp-review --headless --no-context`.

Both passes write to `.harness/todos/`; `.harness/review-summary.md` is overwritten by specialist and appended-to by blind.

### Auto-fix loop (max 3 rounds)

Initialize: `PREV_RESOLVER_SHA=""` (no resolver commit yet at round 1 entry).

For each round (1, 2, 3):

1. Read `.harness/todos/` for pending P1+ findings. Validate frontmatter: `priority ∈ {P1,P2,P3}`, `status ∈ {pending,ready,deferred,dropped,complete}`, `agent_source` matches `[a-z0-9-]+(-blind)?`. Malformed → log + treat as `priority: P1, status: pending`.
2. **Sensitive-file denylist check.** For each finding, check the file path against the inline denylist below. Denylisted findings excluded from auto-fix.

   **Sensitive-file denylist patterns** (inline; Claude interprets via prose-style judgment — comprehensive helper-based matching is deferred to v2.1.2):
   - `**/auth/**`, `**/auth.*` — authentication code (incl. files named auth.ts/py, dirs named auth/)
   - `**/middleware/**`, `**/middleware.*` — middleware code
   - `**/security/**`, `**/security.*` — security code
   - `**/secrets/**`, `**/credentials/**` — secret-handling code
   - `**/.env*` — environment files
   - `**/jwt/**`, `**/oauth/**`, `**/session/**` — token/session management
   - `**/crypto/**`, `**/encryption/**`, `**/keys/**` — cryptography
   - `**/permissions/**`, `**/iam/**`, `**/rbac/**`, `**/acl/**` — access control
   - `prisma/schema.prisma`, `**/migrations/**` — database schema + migrations
   - `lefthook.yml`, `.semgrep/**`, `.github/workflows/**`, `.claude/settings.json`, `**/CODEOWNERS` — CI + governance
   - `**/Dockerfile*`, `**/docker-compose*`, `**/*.tf` — infrastructure-as-code

   **Match semantics (advisory; PATH-BASED, NOT INTENT-BASED):** Claude interprets these patterns by examining the file's PATH SEGMENTS, not the file's purpose or location-in-test-tree. Worked examples:
   - `apps/api/src/auth/handler.ts` matches `**/auth/**` (segment `auth/` is in path)
   - `apps/web/src/auth.ts` matches `**/auth.*` (basename starts with `auth.`)
   - `tests/fixtures/lp-phase2/auth/synthetic.ts` matches `**/auth/**` (segment `auth/` is in path; the fact that it's under `tests/fixtures/` does NOT exempt it — match is path-based)
   - `apps/auth-readme.md` does NOT match (no `auth` segment in path; basename is `auth-readme.md` not `auth.<ext>`)

   **Failure mode is safe:**
   - Under-matching is acceptable (defers to manual review = safer)
   - Over-matching is acceptable (manual review is conservative)

   **Comprehensive helper-based matching deferred to v2.1.2:** proper `fnmatch.fnmatchcase` + `**` glob expansion + path normalization + symlink rejection requires Python helper with correctness tests. v2.1.1 accepts prose-style judgment as the trade-off for shipping today.

3. **Staged-diff scope check.** Verify finding's frontmatter `file:` field is in `git diff --name-only $STEP46_BASE_SHA..HEAD`. Out-of-scope findings deferred to manual review.
4. **Resolver-rejected handling.** A finding is "resolver-rejected" iff after `/lp-resolve-todo-parallel` completes, `status` remains `pending` in `.harness/todos/*.md`. Frontmatter status is the canonical structured signal — no parsing of resolver stdout required. Resolver-rejected findings treated as denylisted for loop termination.
5. IF zero non-denylisted, in-scope, fixable P1+ findings remain: BREAK; proceed to Step 5. Log: `"Step 4.6 dual-pass completed in {round} round(s)."`
6. Run `/lp-resolve-todo-parallel` on the eligible subset.
7. **Resolver-completion check.** Verify resolver Step 5 commit succeeded:

   ```bash
   RESOLVER_SHA=$(git log --format=%H --grep='fix: resolve review findings' "$STEP46_BASE_SHA..HEAD" | head -1)
   if [ -z "$RESOLVER_SHA" ] || [ "$RESOLVER_SHA" = "$PREV_RESOLVER_SHA" ]; then
     # Either resolver was invoked (per step 6) but committed nothing, OR no new commit since previous round.
     # This is a HARD STOP — resolver-without-new-commit indicates resolver-internal failure or pre-commit-hook block.
     # Both require human investigation.
     echo "HARD STOP: resolver invoked but produced no new commit since $PREV_RESOLVER_SHA"
     exit non_zero
   fi
   PREV_RESOLVER_SHA="$RESOLVER_SHA"
   ```

8. Re-stage: `git add` resolver-reported files.
9. Re-run Step 4 quality gates (test/typecheck/lint via `plugin-build-runner.py` + `lefthook run pre-commit`). Combined cap: 3 Step 4.6 rounds × up to 3 Step 4 attempts each = 9 total Step 4 invocations max. (Bypassing Step 4's nested loop is deferred to v2.1.2; v2.1.1 accepts the wider combined cap. Step 4's modifications ARE counted toward the 50/500 aggregate cap since they touch HEAD between `$STEP46_BASE_SHA` and HEAD.)
10. Aggregate-cap check (post-flight): `git diff --shortstat $STEP46_BASE_SHA..HEAD` → if >50 files OR >500 LOC: HARD STOP.
11. Re-run BOTH `/lp-review` passes (specialist then blind, two separate Bash tool calls). Increment round counter.

### Hard stop on exhaustion

After round 3, IF non-denylisted P1+ findings remain (or aggregate cap fired):

1. Print path `.harness/review-summary.md` + `head -n 20` of file. Append: `"Run cat .harness/review-summary.md for full output."`
2. Inspect git log: `git log --oneline $STEP46_BASE_SHA..HEAD --grep="fix: resolve review findings"`.
3. Print recovery options:

   ```
   Step 4.6 exhausted 3 auto-fix rounds; review findings remain. Aborting ship.

   {N} resolver commits exist on branch since Step 4.6 entry ($STEP46_BASE_SHA).

   Recovery:
     /lp-commit                                # interactive triage via /lp-triage
     git reset --soft $STEP46_BASE_SHA         # unstage resolver commits to start over

   Findings: .harness/todos/
   ```

4. EXIT non-zero. Do NOT auto-rollback.

### Sensitive-file findings remain → NOT a hard stop

If only denylisted-or-scope-deferred findings remain: Step 4.6 PASSES. Findings surfaced in Step 6 PR body per the `## Mandatory Review Findings` section.

### Failure handling

Specialist/blind error → STOP, abort. Resolver error → STOP, surface, abort. Step 4 re-run failure → HARD STOP. Aggregate cap fired → HARD STOP, surface diff-stat, abort.

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

## Mandatory Review Findings

<!-- LP-CASE: {clean|denylisted-only|p2p3-deferred|combo} schema=1 -->

[Read from .harness/todos/ + .harness/review-summary.md at Step 4.6 PASS exit. Hard-stop exits abort ship before Step 5; PR body N/A.]

[CASE: clean — .harness/todos/ empty]
"Specialist + blind dual-pass completed; 0 findings above 0.60 confidence threshold."

[CASE: denylisted-only — only deferred findings remain]
"The following P1+ findings live in sensitive files OR reference files outside the staged diff and were excluded from autonomous auto-fix. Human reviewer: please evaluate manually before merge:

- {coarse-module}/* — {N} P{level} finding(s) deferred to manual review
  (Detailed file:line in local .harness/review-summary.md; redacted from public PR body to limit disclosure)

<!-- LP-INTERNAL: sensitive-redaction-applied; full detail at .harness/review-summary.md -->"

[CASE: p2p3-deferred — only P2/P3 findings remain]
"P2/P3 findings deferred to manual triage; run /lp-triage post-merge.
{count} P2 + {count} P3 findings in .harness/todos/."

[CASE: combo — both denylisted and P2/P3 deferred sections]
<!-- LP-CASE-PART: denylisted-only -->
[denylisted-only block above]
<!-- LP-CASE-PART: p2p3-deferred -->
[p2p3-deferred block above]

## Test Plan
[Quality gate results]
```

**Section-marker contract:** the OUTER `<!-- LP-CASE: ... -->` marker appears EXACTLY ONCE at the section top, set to one of `{clean, denylisted-only, p2p3-deferred, combo}`. For combo case, the inner `<!-- LP-CASE-PART: ... -->` markers delimit the sub-blocks; do NOT emit a duplicate inner `<!-- LP-CASE: combo ... -->` marker.

**Sensitive-file redaction:** denylisted findings render `coarse-module = first path segment matching a denylist pattern + "*"` (e.g., `auth/*`, NOT full repo path).

**Truncation:** if section >30 KB, truncate to top-50 by priority+confidence; footer line `"… {N} additional findings deferred to manual triage."`

**Section name:** plain `## Mandatory Review Findings` (NOT `(Phase 4.6 dual-pass)`).

## Step 7: PR Monitoring Loop (max 3 cycles)

### Gate A: CI Checks

- Poll `gh pr checks` (30s intervals, max 10 waits)
- IF failed: read logs, diagnose, fix, re-run Step 4, push, restart loop

### Gate B: Advisory AI Reviews (non-blocking on timeout)

Two complementary AI reviewers post advisory comments on the PR. Both are non-blocking — if either is unavailable, missing, or quota-failed, the gate passes. Codex is the **narrow / line-level** lane; Greptile is the **wide / codebase-aware** lane. Sub-gate numbering matches `/lp-commit`'s monitoring loop (B1 = human review, skipped in autonomous mode; B2 = Codex; B3 = Greptile) so the two flows can be reasoned about with one mental model.

#### Gate B1: Human Reviews

Skipped in autonomous mode. `/lp-ship` does not block on human approval — that decision belongs to the user at merge time.

#### Gate B2: Codex Review

- Poll for the Codex review comment (header `## Codex Automated Code Review`) for up to 5 minutes
- IF no comment: pass
- IF comment: parse P0–P3 severity sections, evaluate each finding (AGREE / PARTIALLY AGREE / DISAGREE)
- Auto-fix only AGREE findings at P0 or P1 severity. Max 3 fix rounds, then stop.
- Apply sensitive file denylist: if a Codex suggestion targets auth/middleware/security paths → report "Needs manual review" instead of auto-fixing.

#### Gate B3: Greptile Review

- Poll for the Greptile review comment (header `### Greptile Summary`, posted by `greptile-apps[bot]`) for up to 5 minutes
- IF no comment: pass (Greptile may not be installed on this repo, not yet indexed, or this PR's author is in `greptile.json` `excludeAuthors`)
- IF comment: parse two distinct signals:
  - **Confidence Score** (1/5 to 5/5) — Greptile's overall verdict on the PR. Treat 5/5 as "no findings worth acting on"; 4/5 means "merge after addressing the called-out finding"; ≤3/5 warrants pause and full triage.
  - **Per-finding severity** in the inline tables (P0 / P1 / P2) — these are Greptile's per-issue ratings, the same scale Codex uses
- Auto-fix criteria (must satisfy ALL):
  1. Finding severity is **P0 or P1** in Greptile's inline table (not P2 / nitpicks)
  2. Codex (Gate B2) flagged the **same file and line** OR Greptile's finding makes a cross-file claim that Codex by design cannot make (e.g., "this name does not match the convention used by the other 12 callers in `apps/api/`"). Single-file findings Greptile alone flagged are presented to user, not auto-fixed.
  3. Same sensitive-file denylist as B2
- Max 3 fix rounds combined across B2 + B3, then stop.
- Greptile-only findings that don't meet the auto-fix criteria → present to user with "Greptile-only finding, manual review" labeling.

All three sub-gates are skip-on-timeout.

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
6. **NEVER** skip mandatory dual-pass review (no `--skip-review` flag exists on `/lp-ship`; emergency-hotfix bypass is interactive-only via `/lp-commit`)
