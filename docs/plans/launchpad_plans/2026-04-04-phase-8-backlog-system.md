# Phase 8: Automated Backlog System

**Date:** 2026-04-04
**Depends on:** Phase 0 (`.harness/` directory, `/harness:build` pipeline, `.claude/settings.json`), Phase 1 (`.harness/observations/`), Phase 7 (`/triage` defer/drop → `.harness/observations/`, `/commit` post-commit)
**Branch:** `feat/backlog-system`
**Status:** Plan — v4 (Phase 10 cascading changes: add "designed" to status counts, remove timeout reference)

---

## Decisions (All Finalized)

| Decision             | Answer                                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------------------- |
| Backlog file         | `docs/tasks/BACKLOG.md` (replaces `docs/tasks/TODO.md`)                                                     |
| Backlog generation   | Fully auto-generated — source of truth is the inputs, not the file itself                                   |
| Backlog size target  | ≤ 1,200 characters / ~30 lines / ~300 tokens (hard constraint: 10K char hook cap)                           |
| Regeneration command | `/regenerate-backlog` — single reusable command, invoked by 3 workflow endpoints                            |
| `/Hydrate` command   | Read-only session briefing — reads BACKLOG.md, presents dashboard                                           |
| `hydrate.sh` script  | Rewritten — reads BACKLOG.md, extensible for future additions                                               |
| SessionStart hook    | Matchers: `startup`, `clear` only. Command: `bash "$CLAUDE_PROJECT_DIR/scripts/agent_hydration/hydrate.sh"` |
| `/defer` command     | Manual task addition: `/defer "description" --priority P2 --area auth`                                      |
| `/defer` ID strategy | Timestamp-based: `YYYYMMDD-HHMMSS-{slug}.md` (no sequential ID race condition)                              |
| Stale detection      | None — no time-based thresholds. Area-based grouping + session-start surfacing.                             |
| TODO.md              | Renamed to BACKLOG.md. References updated.                                                                  |

---

## Purpose

Create an automated project status system that orients developers at session start. After Phase 8:

1. Every session begins with a lean briefing: what's deferred, what areas need attention, what to work on next
2. Developers can manually defer tasks via `/defer` without editing files
3. The backlog regenerates automatically at the end of every pipeline run and manual commit

This closes the final gap in the pipeline feedback loop: Plan → Build → Ship → Learn → **Orient (Phase 8)** → next Plan or Build. The orient step feeds back into either `/harness:plan` (new section needing shaping) or `/harness:build` (re-run on existing approved plan).

---

## Architecture: How Phase 8 Components Wire In

```
Session lifecycle:
  │
  ├── SessionStart hook (startup, clear)
  │     └── hydrate.sh → cat docs/tasks/BACKLOG.md → injected as context
  │
  └── Developer reads briefing, picks next action

Backlog generation (/regenerate-backlog — single command, 3 callers):
  │
  ├── Called by: /harness:build Step 6 (Report), /commit post-Step 6, /triage post-Step 5
  │
  ├── Reads: .harness/observations/ (status: deferred items only, pre-filtered)
  ├── Reads: Section spec files in docs/tasks/sections/ (grep frontmatter for status)
  │
  ├── Writes: docs/tasks/BACKLOG.md (lean summary, ≤1,200 chars)
  └── Stages: git add docs/tasks/BACKLOG.md (when called from /harness:build)

Manual task addition:
  │
  └── /defer "description" --priority P2 --area auth
        └── Writes: .harness/observations/{timestamp}-{slug}.md
              (next /regenerate-backlog picks it up)
```

Regeneration assumes single-session, single-threaded execution. If future phases introduce parallel agent execution, regeneration must use atomic write-and-rename.

---

## Component Definitions

### 1. `BACKLOG.md` (Auto-Generated)

**File:** `docs/tasks/BACKLOG.md` (replaces `docs/tasks/TODO.md`)
**Size constraint:** ≤ 1,200 characters / ~30 lines / ~300 tokens
**Enforcement:** After generating content, check character count. If over 1,200, truncate the deferred items table (reduce row count) until within budget.

This file is the project's lean status dashboard. It is fully regenerated (overwritten) every time `/regenerate-backlog` runs. Developers should not edit it directly — use `/defer` to add tasks, `/triage` to sort findings.

#### Content Structure

```markdown
# Project Backlog

**Generated:** YYYY-MM-DD HH:MM | **Branch:** main

## Deferred Items (N total)

| P   | Area    | Description                        | Source              |
| --- | ------- | ---------------------------------- | ------------------- |
| P1  | auth    | Input validation gap in login flow | security-auditor    |
| P2  | billing | Stripe webhook retry logic         | code-review         |
| P2  | api     | Missing rate limiting on /items    | performance-auditor |
| P3  | general | Add pagination to items endpoint   | manual              |

## Section Status

3 built | 1 hardened | 2 planned | 1 designed | 1 shaped | 1 defined

## Next Actions

1. Address P1 items: /triage
2. Plan a new section: /harness:plan
3. Continue building (approved plan): /harness:build
4. Add a task: /defer "description" --priority P2
```

#### Generation Rules

1. **Deferred Items table:** Pre-filter `.harness/observations/` using `grep -l "status: deferred"` before reading full files (avoids parsing all observations). Sort by priority (P1 first). Include: priority, area (from `area` frontmatter field, default "general" if missing), description (first 50 chars of title), source (`agent_source` from frontmatter). Cap at 15 rows — if more exist, show top 15 and note "and {N} more." Skip files with malformed YAML frontmatter (warn and continue).
2. **Section Status:** Grep section spec files for status counts: `grep -rl '^status: built' docs/tasks/sections/ | wc -l` (repeat per status: built, hardened, planned, designed, shaped, defined). Phase 0 specifies status in section spec file frontmatter, not PRD.md. If `docs/tasks/sections/` is empty or missing, output "No sections defined."
3. **Next Actions:** Static template with 4 options (triage, plan, build, defer). Always present.
4. **Header:** Generated timestamp and current branch.
5. **Dropped items excluded:** `status: dropped` items are NOT shown in BACKLOG.md. The audit trail lives in `.harness/observations/` files with `status: dropped` — query them on-demand with `grep -l "status: dropped" .harness/observations/*.md`.
6. **Manually deferred items:** Items created by `/defer` have `agent_source: manual`. They appear alongside agent-generated deferrals in the same table.

---

### 2. `hydrate.sh` Script (Rewrite)

**File:** `scripts/agent_hydration/hydrate.sh`
**Previous:** 41 lines — `cat REPOSITORY_STRUCTURE.md` + `cat TODO.md` + banners + humor prompt
**New:** ~15 lines — `cat BACKLOG.md` with fallback

The script is kept as a reusable entry point for session hydration. While it currently only reads BACKLOG.md, keeping it as a script allows future additions without modifying `.claude/settings.json`. REPOSITORY_STRUCTURE.md loading is removed — handled by CLAUDE.md progressive disclosure.

#### New Script Content

```bash
#!/bin/bash
# Session Hydration — inject current project state at session start
# Called by: SessionStart hook (startup, clear) and /Hydrate command
#
# Design: Only loads the backlog dashboard. Repo structure is loaded
# on-demand via CLAUDE.md progressive disclosure.
# Extensible: add future session-start context below.

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
BACKLOG="$REPO_ROOT/docs/tasks/BACKLOG.md"

if [ -f "$BACKLOG" ]; then
  cat "$BACKLOG"
else
  echo "No backlog found. Run a workflow to generate docs/tasks/BACKLOG.md."
fi
```

All scripts use `$CLAUDE_PROJECT_DIR` for path resolution (canonical Claude Code environment variable). Avoid `git rev-parse --show-toplevel`.

---

### 3. `/Hydrate` Command (Edit)

**File:** `.claude/commands/Hydrate.md` (EDIT existing)
**Previous:** "Run scripts/agent_hydration/hydrate.sh to load minimal session context"
**New:** Read-only session briefing — reads BACKLOG.md and presents a summary

#### New Content

```markdown
# Hydrate — Session Briefing

Read `docs/tasks/BACKLOG.md` and present its contents to the user.

If BACKLOG.md does not exist, inform the user: "No backlog found. Run a workflow
(/harness:build, /commit, or /triage) to generate it."

This command is also triggered automatically at session start via the SessionStart
hook. Use it manually to re-read the backlog mid-session.
```

---

### 4. `/defer` Command (New)

**File:** `.claude/commands/defer.md`

#### Purpose

Manually add a task to the project backlog. Creates an observation file in `.harness/observations/` with the appropriate frontmatter, which is picked up by the next `/regenerate-backlog` run.

#### Usage

```
/defer "Add pagination to items endpoint" --priority P2 --area api
/defer "Fix login redirect on expired tokens"                        → defaults to P2, area "general"
/defer "Update Stripe webhook handler" --priority P1                 → defaults to area "general"
```

#### Flow

```
/defer [description] [--priority P1|P2|P3] [--area <area>]
  │
  ├── Step 1: Parse arguments
  │     ├── description: required (quoted string)
  │     ├── --priority: optional, defaults to P2
  │     ├── --area: optional, defaults to "general"
  │     └── IF no description: ask user for one
  │
  ├── Step 2: Generate observation file
  │     ├── ID: timestamp-based — YYYYMMDD-HHMMSS (no sequential scan, no race condition)
  │     ├── Slug: lowercase, hyphens, max 60 chars from description
  │     ├── Filename: {YYYYMMDD-HHMMSS}-{slug}.md
  │     └── Write to .harness/observations/{filename}
  │
  ├── Step 3: Write file content
  │     ├── YAML frontmatter:
  │     │     status: deferred
  │     │     priority: {P1|P2|P3}
  │     │     agent_source: manual
  │     │     area: {area}
  │     │     deferred_date: YYYY-MM-DD
  │     ├── Body:
  │     │     # {description}
  │     │     Manually deferred via /defer on {date}.
  │     └── No self-validation needed (deterministic output)
  │
  └── Step 4: Confirm
        └── "Deferred: '{description}' (P{n}, {area}) → .harness/observations/{filename}"
```

#### Rules

1. Description is required — prompt if missing
2. Priority defaults to P2 if not specified
3. Area defaults to "general" if not specified
4. Slug sanitization: lowercase, replace spaces/special chars with hyphens, max 60 chars
5. Timestamp-based ID: `YYYYMMDD-HHMMSS` format — eliminates race conditions with concurrent `/triage` defer actions
6. Do NOT regenerate BACKLOG.md — that happens at the next workflow endpoint

#### Allowed Tools

Bash, Read, Grep, Glob, Write

---

### 5. `/regenerate-backlog` Command (New)

**File:** `.claude/commands/regenerate-backlog.md`

#### Purpose

Single reusable command that generates `BACKLOG.md` from source data. Called by three workflow endpoints — eliminates duplication of regeneration logic.

#### Flow

```
/regenerate-backlog [--stage]
  │
  ├── Step 1: Read deferred items
  │     ├── Pre-filter: grep -l "status: deferred" .harness/observations/*.md
  │     ├── For each match: read YAML frontmatter (first 10 lines)
  │     ├── Skip files with malformed frontmatter (warn and continue)
  │     ├── Sort by priority (P1 → P2 → P3)
  │     └── Cap at 15 items (note overflow count)
  │
  ├── Step 2: Read section registry
  │     ├── Grep section spec files: grep -rl '^status: built' docs/tasks/sections/ | wc -l (repeat per status)
  │     ├── Count: built, hardened, planned, designed, shaped, defined
  │     └── Fallback: "No sections defined" if docs/tasks/sections/ empty/missing
  │
  ├── Step 3: Generate BACKLOG.md
  │     ├── Write docs/tasks/BACKLOG.md using template
  │     ├── Check character count after generation
  │     └── IF > 1,200 chars: reduce table rows until within budget
  │
  └── Step 4: Stage (conditional)
        └── IF --stage flag: git add docs/tasks/BACKLOG.md
```

#### Wiring Into Existing Commands

| Command          | Where                  | How                                                                                                      | Flag                                 |
| ---------------- | ---------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `/harness:build` | Step 6 (Report)        | After report output, call `/regenerate-backlog --stage`                                                  | `--stage` (included in build commit) |
| `/commit`        | After Step 6 (Commit)  | Call `/regenerate-backlog` (no stage — commit already made, file is unstaged artifact for next workflow) | No flag                              |
| `/triage`        | After Step 5 (Summary) | Call `/regenerate-backlog` (no stage — standalone triage doesn't commit)                                 | No flag                              |

Note: When called from `/commit`, BACKLOG.md regeneration happens after the commit is already made. The regenerated file is an unstaged change — picked up by the next workflow or follow-up commit.

#### Allowed Tools

Bash, Read, Grep, Glob, Write

---

### 6. SessionStart Hook Configuration

**File:** `.claude/settings.json` (EDIT — merge with existing hooks)

#### Complete Merged Configuration

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": ["startup", "clear"],
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/agent_hydration/hydrate.sh\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "bash scripts/hooks/track-skill-usage.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash scripts/hooks/audit-skills.sh"
          }
        ]
      }
    ]
  }
}
```

Matchers:

- `startup` — brand new session, nothing in context
- `clear` — context wiped, needs re-injection

NOT included:

- `resume` — previous context preserved, BACKLOG.md already in context from session start
- `compact` — compact summary captures the backlog briefing, re-injection would be redundant

#### Output Behavior

The hook's stdout (BACKLOG.md content, ≤1,200 chars) is injected as `additionalContext` into the session before the first prompt. The 10,000-character hook output cap provides an 8x safety margin. The hook uses `$CLAUDE_PROJECT_DIR` for reliable path resolution regardless of CWD.

---

## Changes to Existing Files

### 1. Rename `docs/tasks/TODO.md` → `docs/tasks/BACKLOG.md`

Delete the old ~240-line template file. Replace with the auto-generated lean format. Update references:

- `docs/architecture/REPOSITORY_STRUCTURE.md` (update `docs/tasks/` description)

### 2. Rewrite `scripts/agent_hydration/hydrate.sh`

Replace 41-line script with ~15-line version (see Component Definition #2 above).

### 3. Edit `.claude/commands/Hydrate.md`

Replace 3-line command with updated content (see Component Definition #3 above).

### 4. Edit `.claude/settings.json`

Replace entire file with merged configuration (see Component Definition #6 above). Preserves existing `PostToolUse` and `Stop` hooks, adds `SessionStart`.

### 5. Edit `.claude/commands/harness/build.md`

Add `/regenerate-backlog --stage` call to Step 6 (Report). Note: the actual file path for this command needs verification during implementation — the `harness/` subdirectory under `.claude/commands/` may use colon-namespaced flat files (`harness:build.md`) rather than subdirectories.

### 6. Edit `.claude/commands/commit.md`

Add `/regenerate-backlog` call after Step 6 (Commit), before Step 7 (Offer PR). No `--stage` flag — the commit is already done.

### 7. Edit `.claude/commands/triage.md`

Add `/regenerate-backlog` call after Step 5 (Summary). No `--stage` flag — standalone triage doesn't commit.

### 8. Update `docs/architecture/REPOSITORY_STRUCTURE.md`

Update `docs/tasks/` section to reference BACKLOG.md instead of TODO.md.

### 9. Update `scripts/setup/init-project.sh`

Update scaffolding: create `docs/tasks/BACKLOG.md` (empty placeholder with "No backlog generated yet" message), update `scripts/agent_hydration/hydrate.sh` to the rewritten version.

### 10. Update CLAUDE.md Progressive Disclosure Table

Add entry for BACKLOG.md:

| `docs/tasks/BACKLOG.md` | Understanding current project status, deferred items, or session orientation |

---

## Verification Checklist

### Files Created

- [ ] `.claude/commands/defer.md` — timestamp-based ID, `--area` flag, observation file writer
- [ ] `.claude/commands/regenerate-backlog.md` — single reusable command, `--stage` flag, pre-filter, 1,200-char enforcement

### Files Edited

- [ ] `scripts/agent_hydration/hydrate.sh` — rewritten from 41 lines to ~15 lines, reads BACKLOG.md only
- [ ] `.claude/commands/Hydrate.md` — read-only briefing, references BACKLOG.md
- [ ] `.claude/settings.json` — SessionStart hook added, existing hooks preserved
- [ ] `.claude/commands/harness/build.md` — `/regenerate-backlog --stage` added to Step 6 (Report)
- [ ] `.claude/commands/commit.md` — `/regenerate-backlog` added after Step 6
- [ ] `.claude/commands/triage.md` — `/regenerate-backlog` added after Step 5
- [ ] `docs/architecture/REPOSITORY_STRUCTURE.md` — TODO.md → BACKLOG.md reference
- [ ] `scripts/setup/init-project.sh` — scaffolding updated
- [ ] `CLAUDE.md` — progressive disclosure table updated with BACKLOG.md entry

### Files Renamed

- [ ] `docs/tasks/TODO.md` → `docs/tasks/BACKLOG.md`

### BACKLOG.md Behavior

- [ ] ≤ 1,200 characters enforced (truncate table rows if over budget)
- [ ] Deferred items sorted by priority, area column populated, max 15 rows
- [ ] `status: dropped` items excluded from BACKLOG.md
- [ ] Manually deferred items (`agent_source: manual`) included
- [ ] Malformed frontmatter files skipped with warning
- [ ] Section status counts include: built, hardened, planned, designed, shaped, defined
- [ ] Section spec fallback: "No sections defined" when docs/tasks/sections/ empty/missing
- [ ] Fully regenerated (overwritten) on each trigger

### `/defer` Behavior

- [ ] Timestamp-based ID: `YYYYMMDD-HHMMSS-{slug}.md` (no race condition)
- [ ] `--area` flag (defaults to "general")
- [ ] `--priority` flag (defaults to P2)
- [ ] Writes to `.harness/observations/` with standard frontmatter (includes `area` field)
- [ ] Does NOT regenerate BACKLOG.md

### `/regenerate-backlog` Behavior

- [ ] Pre-filters with `grep -l "status: deferred"` before reading full files
- [ ] Skips malformed frontmatter with warning
- [ ] Reads section spec files with targeted grep (grep -rl '^status: ...' docs/tasks/sections/)
- [ ] Enforces 1,200-char constraint on output
- [ ] `--stage` flag conditionally stages BACKLOG.md
- [ ] Single source of truth for regeneration logic (not duplicated across commands)

### SessionStart Hook

- [ ] Matchers: `startup` and `clear` only
- [ ] NOT triggered on `resume` or `compact`
- [ ] Merged with existing PostToolUse and Stop hooks
- [ ] Output stays within 10,000 character cap

### Integration

- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------------------- |
| Future       | REPOSITORY_STRUCTURE_COMPACT.md for hook-friendly pre-loading                                                       |
| Future       | Pipeline relevance detection (`/harden-plan` and `/review` cross-referencing deferred items with current work area) |
| Future       | `/backlog` command for detailed exploration (shipping history, dropped audit trail)                                 |
| Phase Finale | Documentation refresh for all command tables                                                                        |
| Phase Finale | CE plugin removal                                                                                                   |

---

## File Change Summary

| #   | File                                        | Change                                                                                     | Priority |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------------------ | -------- |
| 1   | `.claude/commands/defer.md`                 | **Create** — manual task addition with `--area` and `--priority` flags, timestamp-based ID | P0       |
| 2   | `.claude/commands/regenerate-backlog.md`    | **Create** — single reusable regeneration command with `--stage` flag                      | P0       |
| 3   | `scripts/agent_hydration/hydrate.sh`        | **Rewrite** — 41 lines → ~15 lines, reads BACKLOG.md only                                  | P0       |
| 4   | `.claude/commands/Hydrate.md`               | **Edit** — read-only briefing, references BACKLOG.md                                       | P0       |
| 5   | `.claude/settings.json`                     | **Edit** — add SessionStart hook, preserve existing hooks (complete merged JSON)           | P0       |
| 6   | `.claude/commands/harness/build.md`         | **Edit** — add `/regenerate-backlog --stage` to Step 6 (Report)                            | P0       |
| 7   | `.claude/commands/commit.md`                | **Edit** — add `/regenerate-backlog` after Step 6                                          | P0       |
| 8   | `.claude/commands/triage.md`                | **Edit** — add `/regenerate-backlog` after Step 5                                          | P0       |
| 9   | `docs/tasks/TODO.md`                        | **Rename** → `docs/tasks/BACKLOG.md` (auto-generated)                                      | P0       |
| 10  | `docs/architecture/REPOSITORY_STRUCTURE.md` | **Edit** — TODO.md → BACKLOG.md reference                                                  | P1       |
| 11  | `scripts/setup/init-project.sh`             | **Edit** — scaffolding for BACKLOG.md, update hydrate.sh                                   | P1       |
| 12  | `CLAUDE.md`                                 | **Edit** — add BACKLOG.md to progressive disclosure table                                  | P1       |
