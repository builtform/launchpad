# Phase 7: Manual Commit Workflow

**Date:** 2026-04-03
**Source:** CE `commands/triage.md` (312 lines), existing LaunchPad `commit.md` (300 lines)
**Depends on:** Phase 0 (`.harness/todos/`, `/review`, `/resolve_todo_parallel`), Phase 1 (review agents, `.harness/observations/`)
**Branch:** `feat/commit-workflow`
**Status:** Plan — v4 (Phase 0 v9 sync: /review invoked with --headless in Step 2.5 since /triage handles presentation; v3 — meta-orchestrator split alignment + reviewer fixes)

---

## Decisions (All Finalized)

| Decision                 | Answer                                                                                                                                  |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Triage command name      | `/triage` → `.claude/commands/triage.md` (flat)                                                                                         |
| Triage actions           | 3 actions: **fix** (→ ready), **drop** (→ observations with `status: dropped`), **defer** (→ observations with `status: deferred`)      |
| Triage model             | `model: inherit` (convention — commands don't use model frontmatter; they run with the user's active model)                             |
| Triage findings cap      | MAX_FINDINGS=25 — overflow auto-deferred to observations, sorted by priority                                                            |
| Commit command           | `/commit` → `.claude/commands/commit.md` (EDIT existing file)                                                                           |
| Review trigger in commit | Always ask: "Run code review before committing?" (interactive, user decides)                                                            |
| `/ship` vs `/commit`     | Both coexist. `/ship` = autonomous (pipeline). `/commit` = interactive (manual). Phase 7 modifies `/commit` only. `/ship` is unchanged. |
| Todo status transitions  | Frontmatter only, no file renaming (per Phase 0)                                                                                        |
| `/triage` standalone use | Wired into `/commit` AND available standalone for triaging existing todos                                                               |
| Step 2 staging default   | Keep `git add -A` when user says "all" (interactive — user explicitly confirms). Do NOT change to `git add -u`.                         |
| PR monitoring cap        | Add max 3 cycles to `/commit` Step 8, matching `/ship`                                                                                  |

---

## Purpose

Upgrade the manual `/commit` workflow with optional multi-agent code review and interactive finding triage. After Phase 7, developers who commit manually get the same review agent protection as the autonomous `/harness:build` pipeline — but with human control over which findings to fix, drop, or defer.

This also creates `/triage`, an interactive command for sorting review findings into three buckets: fix now, drop (dismissed with audit trail), or defer for later. Both "drop" and "defer" populate `.harness/observations/`, feeding Phase 8's backlog system.

---

## Architecture: How Phase 7 Components Wire In

```
/commit (manual workflow — Phase 7 upgrade):
  │
  ├── Step 1:   Branch guard
  ├── Step 2:   Stage and review changes (interactive)
  ├── Step 2.5: Optional code review (NEW — Phase 7)
  │     ├── Ask: "Run code review before committing?"
  │     ├── IF yes:
  │     │     ├── Run /review --headless (dispatches review agents → .harness/todos/)
  │     │     ├── IF findings: run /triage (user sorts: fix / drop / defer)
  │     │     ├── IF any "fix" items: run /resolve_todo_parallel
  │     │     ├── IF resolver created new files: show untracked, ask to stage
  │     │     ├── Re-run secret scan on staged changes
  │     │     └── Continue to Step 3
  │     └── IF no: continue to Step 3
  │     Step 2.5 expected duration: 3-15 minutes depending on finding count.
  │     Total timeout: 20 minutes. On timeout, findings remain in .harness/todos/
  │     for manual resolution via /resolve_todo_parallel.
  ├── Step 3:   Quality gates (parallel: test + typecheck + lint + lefthook)
  ├── Step 4:   Generate commit message (conventional)
  ├── Step 5:   User approval
  ├── Step 6:   Commit
  ├── Step 7:   Offer PR creation
  └── Step 8:   PR monitoring loop (max 3 cycles, 60min timeout — matching /ship)
```

Note: Step numbering matches the existing `commit.md` (8 steps). Step 2.5 is inserted without renumbering subsequent steps.

---

## What Was NOT Ported from CE

| CE Feature                                                                 | Disposition | Rationale                                                                       |
| -------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------- |
| Haiku model enforcement (`disable-model-invocation: true`, set to Haiku)   | Excluded    | Our convention is `model: inherit`. Users can switch models themselves.         |
| File renaming on status change (`pending-p1-desc.md` → `ready-p1-desc.md`) | Excluded    | Phase 0 decided: status in YAML frontmatter only, no file renaming              |
| Status/priority in filename (`{id}-{status}-{priority}-{desc}.md`)         | Excluded    | Our todo format: `{id}-{description}.md` (status/priority in frontmatter)       |
| CE-specific triage actions (yes/next/custom)                               | Replaced    | Renamed to fix/drop/defer with different semantics                              |
| "Work Log" section in todo files                                           | Excluded    | Over-engineering — the resolver fixes the issue, the commit message has context |
| Rails-specific categories and tagging                                      | Excluded    | All CE/Rails references removed                                                 |

---

## Component Definitions

### 1. `/triage` Command

**File:** `.claude/commands/triage.md`
**CE Source:** `commands/triage.md` (312 lines) — heavy adaptation

#### Purpose

Interactive finding triage. Reads pending todos, presents each one-by-one, and routes them based on the user's decision.

#### Usage

```
/triage              → triage all pending findings in .harness/todos/
```

#### Flow

Load pending todos from `.harness/todos/` (filter `status: pending` from YAML frontmatter). Validate each file: confirm its resolved path is within `.harness/todos/` (no symlink following), confirm frontmatter has required fields (`status`, `priority`), skip with warning if malformed. Sort by priority (P1 → P2 → P3). If multiple findings reference the same `file:line`, group them and present together — user makes one decision for the group.

Grouped findings inherit the highest priority in the group for presentation and confirmation purposes. A group containing any P1 finding triggers the P1 confirmation gate for "drop" actions.

If more than MAX_FINDINGS (25) pending findings exist, present the top 25 by priority. Auto-defer the overflow to `.harness/observations/` with `status: deferred` and a note: "{N} of {total} findings shown. Remaining {overflow} auto-deferred to observations. Run `/triage` standalone to process all."

Present each finding one-by-one showing: title, priority, agent_source, problem statement, location (file:line), and proposed solution. Show progress counter ("Finding 3/12"). Wait for user decision.

If zero pending findings: "No pending findings to triage." → exit.

#### Triage Action Reference

| Action    | YAML Change                                                  | File Location                     | Effect                                           |
| --------- | ------------------------------------------------------------ | --------------------------------- | ------------------------------------------------ |
| **fix**   | `status: pending` → `status: ready`                          | Stays in `.harness/todos/`        | `/resolve_todo_parallel` picks it up             |
| **drop**  | `status: pending` → `status: dropped`, adds `dropped_date`   | Moved to `.harness/observations/` | Audit trail preserved, excluded from active work |
| **defer** | `status: pending` → `status: deferred`, adds `deferred_date` | Moved to `.harness/observations/` | Phase 8 surfaces in backlog                      |

**Drop confirmation for P1 findings:** When dropping a P1 (critical) finding, require confirmation: "This is a P1 (critical) finding. Are you sure you want to drop it? (yes/no)".

#### Path Validation

Before reading or operating on any file, validate that its resolved absolute path (`realpath`) is within `.harness/todos/` (for reads) or `.harness/observations/` (for defer/drop target). Reject any file whose path escapes these directories. Do not follow symlinks.

**Implementation test cases:**

1. Symlink in `.harness/todos/` pointing to `/etc/passwd` -- rejected (realpath resolves outside `.harness/todos/`)
2. Filename with `../` components -- caught by `realpath` validation (resolved path escapes directory)
3. Filenames with spaces, special characters, Unicode -- handled correctly (quote all paths in bash)

#### Frontmatter Validation

Validate YAML frontmatter contains required fields with expected values:

- `status`: must be one of `pending`, `ready`, `deferred`, `dropped`, `complete`
- `priority`: must be one of `P1`, `P2`, `P3`
- `agent_source`: optional string, defaults to `"unknown"` if missing or empty

Todos created before Phase 1 or by `/test-browser` may lack `agent_source`. Treat as `unknown` rather than rejecting as malformed.

If a file has missing or malformed frontmatter for required fields (`status`, `priority`), skip it with a warning: "Skipping {filename}: invalid frontmatter" and continue to the next finding.

#### Todo Frontmatter Schema

```
status: pending | ready | deferred | dropped | complete
priority: P1 | P2 | P3
agent_source?: string          # e.g., "security-auditor" — defaults to "unknown" if missing
deferred_date?: YYYY-MM-DD     # added by triage defer action
dropped_date?: YYYY-MM-DD      # added by triage drop action
```

#### Summary

After all findings processed, report:

- Fixed: {X} findings (ready for `/resolve_todo_parallel`)
- Dropped: {Y} findings (moved to observations with `status: dropped`)
- Deferred: {Z} findings (moved to observations with `status: deferred`)

Offer next steps: (1) Run `/resolve_todo_parallel` to fix approved findings, (2) Done.

#### Allowed Tools

Bash, Read, Grep, Glob, Edit, Write

#### Rules

1. Do NOT implement fixes during triage — triage is sorting only
2. Present findings in priority order (P1 first)
3. Show progress counter on every finding ("Finding 3/12")
4. Accept only: `fix`, `drop`, `defer` (case-insensitive)
5. If user enters something else, re-prompt with the three options
6. Do NOT batch-process — present one at a time, wait for decision
7. Confirm before dropping P1 findings
8. Validate file paths stay within `.harness/` directories
9. Skip files with malformed frontmatter (warn and continue)

---

### 2. `/commit` Command (Edit)

**File:** `.claude/commands/commit.md` (EDIT existing)
**Source:** Existing LaunchPad `commit.md` (300 lines) — add Step 2.5, update Step 8

#### Changes from Current `/commit`

The existing `/commit` has 8 steps (Step 1: Branch Guard through Step 8: PR Monitoring Loop). Phase 7 inserts one new step (Step 2.5) and updates one existing step (Step 8). All other steps (1, 2, 3, 4, 5, 6, 7) are preserved unchanged.

#### New Step 2.5: Optional Code Review

Inserted after Step 2 (Stage and Review) and before Step 3 (Quality Gates):

```
## Step 2.5: Optional Code Review (Phase 7)

After staging, ask: **"Run code review before committing? (yes/no)"**

Total timeout for this step: 20 minutes. If exceeded, abort the review chain
and report: "Review chain exceeded timeout. Findings written to .harness/todos/
— resolve manually with /resolve_todo_parallel."

### If yes:

1. Run /review --headless
   - Dispatches review agents from .launchpad/agents.yml against staged changes
   - Writes findings to .harness/todos/ (clears previous todos first)
   - Reports: "{N} findings ({P1} critical, {P2} important, {P3} nice-to-have)"

2. IF zero findings: "Code review passed with no findings." → continue to Step 3

3. IF findings exist: Run /triage
   - User sorts each finding: fix / drop / defer
   - Returns counts: {fixed} ready, {dropped} to observations, {deferred} to observations

4. IF any findings marked "fix": Run /resolve_todo_parallel
   - Spawns harness-todo-resolver agents for status: ready todos
     (max 5 concurrent — governed by /resolve_todo_parallel Phase 0 cap)
   - Fixes are applied to the working tree
   - IF any todos remain unresolved (timeout, too complex): inform user:
     "{N} findings could not be auto-resolved. These remain in .harness/todos/
     for manual fixing. Continue to quality gates?"

5. Re-stage changes
   - Stage resolver-reported changed files using `git add <file1> <file2> ...`
     (not `git add -u` — only stage files the resolver touched)
   - Check for untracked files: `git status --short | grep '^??'`
     IF new untracked files exist: present them to user:
     "Resolver created {N} new files: [list]. Stage these too? (yes/no)"
   - Run secret scan on resolver-touched files only:
     `git diff --cached -- <resolver-reported-files>`,
     reusing the patterns from /review Step 2.
     IF matches found: HALT and warn user before proceeding.
   - Run `git diff --cached --stat` to show final staging

6. Continue to Step 3 (Quality Gates)

### If no:

Continue to Step 3 (Quality Gates) immediately.
```

#### Changes to Step 8 (PR Monitoring Loop)

Add a maximum cycle cap: **max 3 cycles** (matching `/ship`). Add a **60-minute total wall-clock timeout**. Add a **Gate A CI polling cap of 20 retries** (10 minutes) per cycle. After 3 cycles or 60-minute timeout: "PR monitoring reached maximum cycles/timeout. Remaining issues require manual attention."

#### Steps NOT Changed

Steps 1, 2, 3, 4, 5, 6, 7 are preserved exactly as they are in the current `commit.md`. Step 2 retains `git add -A` as the default when user says "all" (interactive workflow — user explicitly confirms staging). The `Co-Authored-By: Claude <noreply@anthropic.com>` trailer in Step 6 is preserved.

Note: The existing `commit.md` Allowed Tools line lists `TodoWrite, Task` — these are pre-Phase-7 artifacts. Clean up during implementation if desired, but not a Phase 7 requirement.

---

## Changes to Existing Files

### 1. Edit `.claude/commands/commit.md`

Insert Step 2.5 (Optional Code Review) between Step 2 and Step 3. Add max 3 cycle cap to Step 8 (PR Monitoring Loop).

### 2. Edit `.claude/commands/resolve_todo_parallel.md`

Update the todo filter in Step 1 from `status: pending` to `status: pending OR status: ready`. Phase 7 introduces the `ready` status (set by `/triage` "fix" action). When called from `/harness:build` Step 2.5 (without triage), all findings remain `status: pending`. When called from `/commit` Step 2.5 (after triage), approved findings have `status: ready`. The resolver must accept both.

### 3. No changes to `docs/reports/2026-03-30-meta-orchestrators-design.md`

Deferred to Phase Finale (documentation refresh). Incremental doc patches create update churn that Phase Finale consolidates.

---

## Verification Checklist

### Files Created

- [ ] `.claude/commands/triage.md` — prose flow, 3 actions (fix/drop/defer), path validation, frontmatter validation, MAX_FINDINGS=25, P1 drop confirmation, no file renaming

### Files Edited

- [ ] `.claude/commands/commit.md` — Step 2.5 inserted, Step 8 max 3 cycles added
- [ ] `.claude/commands/resolve_todo_parallel.md` — Step 1 filter updated to accept `status: pending OR status: ready`

### Wiring

- [ ] `/triage` called by `/commit` Step 2.5 (after `/review`, before `/resolve_todo_parallel`)
- [ ] `/triage` also available standalone for triaging existing `.harness/todos/`
- [ ] `/commit` calls `/review` (Phase 0) optionally at Step 2.5
- [ ] `/commit` calls `/resolve_todo_parallel` (Phase 0) if triage marks findings as "fix"
- [ ] `/commit` is NOT auto-dispatched by `/harness:build` (manual only, `/ship` is used in pipeline)
- [ ] `/triage` is NOT exclusively standalone — wired into `/commit` Step 2.5
- [ ] `/resolve_todo_parallel` Step 1 accepts `status: pending OR status: ready`
- [ ] `/harness:build` Step 4 calls `/ship` (not `/commit`) — unchanged

### `/triage` Behavior

- [ ] Reads `.harness/todos/` for `status: pending` files only
- [ ] Validates file paths: resolved `realpath` must be within `.harness/todos/` or `.harness/observations/`
- [ ] Validates YAML frontmatter: skips malformed files with warning
- [ ] Frontmatter schema: `status` (required, enum), `priority` (required, enum), `agent_source` (optional, string, defaults to `"unknown"`), `deferred_date`/`dropped_date` (optional, YYYY-MM-DD)
- [ ] Sorts findings by priority: P1 → P2 → P3
- [ ] Groups findings referencing the same `file:line` — one decision per group
- [ ] MAX_FINDINGS=25 cap — overflow auto-deferred to observations
- [ ] Presents findings one-by-one with progress counter ("Finding {X}/{N}")
- [ ] Displays: title, priority, agent_source, problem, location, proposed solution
- [ ] Accepts only: fix, drop, defer (case-insensitive), re-prompts on invalid input
- [ ] **fix**: updates YAML `status: pending` → `status: ready` (file stays in `.harness/todos/`)
- [ ] **drop**: moves file to `.harness/observations/`, sets `status: dropped`, adds `dropped_date`
- [ ] **drop P1**: requires confirmation before proceeding
- [ ] **defer**: moves file to `.harness/observations/`, sets `status: deferred`, adds `deferred_date`
- [ ] Does NOT implement fixes — sorting only, no code changes
- [ ] Summary shows counts for each action (fixed, dropped, deferred)
- [ ] Offers next steps: `/resolve_todo_parallel` or done
- [ ] Exits gracefully when zero pending todos found
- [ ] Does NOT reference Rails, Ruby, ActiveRecord, or CE-specific patterns
- [ ] Does NOT rename files (status in frontmatter only, per Phase 0)

### `/commit` Behavior (Phase 7 Changes Only)

- [ ] Step 2.5 asks: "Run code review before committing?" (always asks, user decides)
- [ ] Step 2.5 runs `/review --headless` if user says yes
- [ ] Step 2.5 reports "Code review passed with no findings" when zero findings
- [ ] Step 2.5 runs `/triage` if review produces findings
- [ ] Step 2.5 runs `/resolve_todo_parallel` if triage marks any findings as "fix"
- [ ] Step 2.5 reports unresolved todos if resolver fails, asks user to continue
- [ ] Step 2.5 re-stages only resolver-reported files (not `git add -u`)
- [ ] Step 2.5 shows untracked files from resolver, asks user to stage
- [ ] Step 2.5 re-runs secret scan on resolver-touched files only (not full staged diff)
- [ ] Step 2.5 has 20-minute total timeout with graceful exit
- [ ] Step 8 PR monitoring loop capped at max 3 cycles (matching `/ship`)
- [ ] Step 8 has 60-minute total wall-clock timeout with graceful exit
- [ ] Step 8 Gate A CI polling capped at 20 retries (10 minutes) per cycle
- [ ] Steps 1, 2, 3, 4, 5, 6, 7 preserved unchanged
- [ ] Co-Authored-By trailer preserved in Step 6
- [ ] NEVER uses `--no-verify`
- [ ] NEVER auto-merges

### Integration

- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                                                                                        |
| ------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Phase 8      | `/Hydrate` backlog generation from `.harness/observations/` (reads `status: deferred` and `status: dropped`)                |
| Future       | Git worktree integration in `/commit` (Phase 9 covers session-level worktree isolation, not `/commit`-specific integration) |
| Phase Finale | Documentation refresh for all command tables (including meta-orchestrator design doc update)                                |
| Phase Finale | CE plugin removal                                                                                                           |

---

## File Change Summary

| #   | File                                        | Change                                                                                                                                                                     | Priority |
| --- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1   | `.claude/commands/triage.md`                | **Create** (adapted from CE — 3 actions: fix/drop/defer, path validation, frontmatter validation, MAX_FINDINGS=25, P1 drop confirmation, audit trail for all dispositions) | P0       |
| 2   | `.claude/commands/commit.md`                | **Edit** — insert Step 2.5 (optional review → triage → resolve → re-stage with secret scan), add max 3 cycles to Step 8                                                    | P0       |
| 3   | `.claude/commands/resolve_todo_parallel.md` | **Edit** — update Step 1 filter to accept `status: pending OR status: ready`                                                                                               | P0       |

**Intentionally omitted:**

- `scripts/setup/init-project.sh` — no Phase 7 scaffolding needed (`.harness/todos/` and `.harness/observations/` already exist from Phases 0-1)
- `docs/reports/2026-03-30-meta-orchestrators-design.md` — deferred to Phase Finale (documentation refresh)
