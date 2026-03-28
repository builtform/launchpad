# Phase 0: Review Agent Configuration & Pipeline Restructure

**Date:** 2026-03-27
**Prerequisite for:** Phase 1 (Review Agent Fleet)
**Branch:** `feat/review-agent-config`
**Status:** Plan — final

---

## Decisions (All Finalized)

| Decision               | Answer                                                                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Config file            | `.harness/harness.local.md`                                                                                                                                  |
| Config format          | YAML frontmatter + markdown body                                                                                                                             |
| YAML keys              | `review_agents`, `review_db_agents`                                                                                                                          |
| Review command         | `/harness:review` → `.claude/commands/harness/review.md`                                                                                                     |
| Build script           | `build.sh` (was `auto-compound.sh` Steps 1-7a)                                                                                                               |
| Ship script            | `ship.sh` (was `auto-compound.sh` Steps 7b-7c)                                                                                                               |
| Learning script        | `compound-learning.sh` (was `auto-compound.sh` Step 8)                                                                                                       |
| Todo directory         | `.harness/todos/` (git-tracked)                                                                                                                              |
| Todo file pattern      | `{id}-{status}-{priority}-{description}.md`                                                                                                                  |
| Resolver agent         | `harness-todo-resolver` (in `resolve/` namespace)                                                                                                            |
| Resolve command        | `/resolve_todo_parallel` (flat, no namespace)                                                                                                                |
| Cumulative fix history | `review-history.md` in `$OUTPUT_DIR`, read by `compound-learning.sh`                                                                                         |
| Wiring points          | `/inf` (autonomous), `/commit` deferred to Phase 7                                                                                                           |
| Old `review_code.md`   | Deleted after migration                                                                                                                                      |
| Old `auto-compound.sh` | Replaced by `build.sh` + `ship.sh` + `compound-learning.sh`                                                                                                  |
| Agent namespaces       | 5 subdirs: `research/`, `review/`, `resolve/`, `design/`, `skills/`                                                                                          |
| Agent renames          | `codebase-locator`→`file-locator`, `codebase-analyzer`→`code-analyzer`, `codebase-pattern-finder`→`pattern-finder`, `web-search-researcher`→`web-researcher` |

---

## Purpose

1. Create a per-project config system for review agent dispatch
2. Split `auto-compound.sh` into three focused scripts
3. Create `/harness:review` command with multi-agent parallel dispatch
4. Create `harness-todo-resolver` agent and `/resolve_todo_parallel` command
5. Rewire `/inf` to orchestrate: build → review → resolve → ship → learn
6. Establish `.harness/` as the runtime directory for all harness artifacts
7. Namespace all agents into subdirectories and rename for clarity

---

## Architecture: How `/inf` Works After Phase 0

```
/inf (Claude Code session)
  │
  ├── Step 1: Section registry check (find planned section)
  │
  ├── Step 2: Run build.sh (headless)
  │     └── Analyze report/section spec → PRD → tasks →
  │         execution loop → optional evaluator → quality sweep
  │     └── Returns when code is built and clean on feature branch
  │
  ├── Step 3: /harness:review (in session — full agent capabilities)
  │     └── Read .harness/harness.local.md
  │     └── Dispatch review agents in parallel via Agent tool
  │     └── Conditionally dispatch DB agents if Prisma changes detected
  │     └── Synthesize findings as P1/P2/P3
  │     └── Write findings to .harness/todos/ (diagnose only, no fixing)
  │
  ├── Step 4: /resolve_todo_parallel (in session)
  │     └── Read all pending todos from .harness/todos/
  │     └── Spawn one harness-todo-resolver agent per todo (parallel)
  │     └── Each agent: reads todo → finds code → implements fix → reports
  │     └── Commit all fixes together
  │     └── Rename todo files from pending to complete
  │
  ├── Step 5: Run ship.sh (headless)
  │     └── git push → gh pr create
  │     └── PR monitoring loop (max 5 cycles):
  │         Gate A: CI checks (auto-fix failures via ai_run)
  │         Gate B: Codex review (auto-fix P0/P1 via ai_run)
  │         Gate C: Merge conflicts (rebase + resolve)
  │     └── Cumulative review-history.md across fix cycles
  │
  ├── Step 6: Run compound-learning.sh (headless)
  │     └── Read progress.txt + review-history.md + .harness/todos/*-complete-*
  │     └── Extract structured learnings to docs/solutions/
  │
  └── Done
```

### How This Mirrors CE

```
CE /lfg:                           Our /inf:
  /workflows:plan                    build.sh
  /deepen-plan                         (plan + build + quality sweep)
  /workflows:work                    ↓
  /workflows:review           →      /harness:review (diagnose → todos)
  /resolve_todo_parallel      →      /resolve_todo_parallel (fix → commit)
                                     ship.sh (push + PR + monitor)
                                     compound-learning.sh (extract learnings)
```

---

## The Config File: `.harness/harness.local.md`

```yaml
---
# Review agents dispatched on every /harness:review run.
# Add agents as they become available in .claude/agents/.
review_agents:
  - pattern-finder

# Database review agents dispatched only when the diff touches
# prisma/schema.prisma or prisma/migrations/*.
review_db_agents: []
---
## Review Context

<!-- This context is injected into every review agent's prompt.
Enriched automatically by /define-product and /define-architecture. -->

{{PROJECT_NAME}} — TypeScript monorepo (Next.js 15 + Hono + Prisma + PostgreSQL).
```

---

## Change Map

### P0 — Core Infrastructure (must ship together)

#### 1. Create `.harness/` directory structure

```
.harness/
└── todos/          # Review findings (populated by /harness:review)
```

- Add `.harness/` to `ALLOWED_DIRS` in `check-repo-structure.sh`
- Add `.harness/todos/.gitkeep` so the directory is tracked
- Document in `REPOSITORY_STRUCTURE.md`
- `init-project.sh` creates this directory structure

#### 2. Namespace and rename agents

Create 5 subdirectories under `.claude/agents/` and move/rename existing agents:

```
.claude/agents/
├── research/
│   ├── file-locator.md           (renamed from codebase-locator.md)
│   ├── code-analyzer.md          (renamed from codebase-analyzer.md)
│   ├── pattern-finder.md         (renamed from codebase-pattern-finder.md)
│   ├── docs-locator.md           (moved, name unchanged)
│   ├── docs-analyzer.md          (moved, name unchanged)
│   └── web-researcher.md         (renamed from web-search-researcher.md)
├── review/
│   └── .gitkeep                  (Phases 1-2 agents go here)
├── resolve/
│   └── harness-todo-resolver.md  (created in this phase)
├── design/
│   └── .gitkeep                  (Phase 5 agents go here)
└── skills/
    └── skill-evaluator.md        (moved, name unchanged)
```

**Files that need agent name updates (4 renames):**

| File                                                       | What to Update                                                                                                                                               |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.claude/commands/research_codebase.md`                    | `codebase-locator`→`file-locator`, `codebase-analyzer`→`code-analyzer`, `codebase-pattern-finder`→`pattern-finder`, `web-search-researcher`→`web-researcher` |
| `.claude/commands/pnf.md`                                  | Same 4 renames + `docs-locator`, `docs-analyzer` (names unchanged but verify references)                                                                     |
| `.claude/commands/implement_plan.md`                       | `codebase-pattern-finder`→`pattern-finder`, `docs-analyzer` (unchanged)                                                                                      |
| `.claude/skills/creating-skills/SKILL.md`                  | All research agent references                                                                                                                                |
| `.claude/skills/creating-skills/references/METHODOLOGY.md` | Agent reference table                                                                                                                                        |
| `.harness/harness.local.md`                                | `pattern-finder` as default review agent (already updated above)                                                                                             |
| `CLAUDE.md`                                                | Sub-agents table                                                                                                                                             |
| `AGENTS.md`                                                | Sub-agents table                                                                                                                                             |
| `docs/guides/HOW_IT_WORKS.md`                              | Agent references                                                                                                                                             |
| `.launchpad/METHODOLOGY.md`                                | Agent reference table                                                                                                                                        |

Delete old flat agent files after confirming new namespaced files work.

---

#### 3. Create `.harness/harness.local.md`

Config file as shown above. `{{PROJECT_NAME}}` replaced by `init-project.sh`.

#### 3. Create `/harness:review` command

**New file:** `.claude/commands/harness/review.md`

```
Step 0: Read Configuration
  - Read .harness/harness.local.md
  - Parse YAML: extract review_agents, review_db_agents
  - Extract markdown body as review_context
  - If file missing: fall back to codebase-pattern-finder only
    (warn: "No harness.local.md found — using default agent only.")

Step 1: Determine Diff Scope
  - Get changed files: git diff --name-only origin/main...HEAD
  - Check for Prisma changes → db_changes = true/false

Step 2: Dispatch Review Agents (Parallel)
  - For EACH agent in review_agents:
      Spawn Agent(subagent_type=agent_name) with:
        diff + file list + review_context
      Each agent returns findings with severity (P1/P2/P3)

  - IF db_changes AND review_db_agents is not empty:
      Spawn schema-drift-detector FIRST (sequential)
      Wait for its output
      THEN spawn remaining db agents in parallel
        with schema-drift output as additional context

Step 3: Synthesize Findings
  - Deduplicate across agents (same issue from multiple agents)
  - Apply severity rubric:
    P1 (Critical): security vulnerabilities, data corruption,
                    breaking API contracts, crashes
    P2 (Important): performance regressions, pattern inconsistencies,
                     missing error handling, architectural concerns
    P3 (Nice-to-have): style preferences, minor refactoring,
                        documentation gaps

Step 3.5: Simplicity Final Sweep (Double-Pass)
  - Check if code-simplicity-reviewer is in review_agents
  - IF YES: dispatch code-simplicity-reviewer AGAIN (Pass 2)
    Pass it: the original diff + changed file list + review_context
             + the synthesized findings from Step 3
    Prompt: "Other review agents found these issues: {Step 3 findings}.
             With this full picture, identify additional simplification
             opportunities that only become visible when considering
             all findings together. This is your second pass —
             focus on what you missed the first time."
  - Merge Pass 2 findings into the existing synthesis
  - IF NO: skip this step

Step 4: Write Todo Files
  - For EACH finding, create .harness/todos/{id}-pending-{priority}-{description}.md
  - YAML frontmatter: status, priority, issue_id, tags, agent_source
  - Body: Problem Statement, Findings (file:line), Proposed Solution
  - Do NOT fix anything — diagnose only

Step 5: Report
  - Present summary: {N} findings ({P1} critical, {P2} important, {P3} nice-to-have)
  - List P1 findings prominently
  - Note: "Run /resolve_todo_parallel to fix these findings."
```

#### 4. Create `harness-todo-resolver` agent

**New file:** `.claude/agents/harness-todo-resolver.md`

An agent that reads a single todo file, understands the problem and proposed solution, finds the relevant code, implements the fix, and produces a resolution report. Designed to be spawned N times in parallel (one per todo).

Key constraints:

- Fix ONLY the issue described in the todo — no scope creep
- If the proposed solution seems wrong, implement a better fix but document why
- Return: files changed, what was fixed, any concerns

#### 5. Create `/resolve_todo_parallel` command

**New file:** `.claude/commands/resolve_todo_parallel.md`

```
Step 1: Read all pending todos from .harness/todos/*-pending-*.md
Step 2: Group by dependency (if any todo references another)
Step 3: Spawn one harness-todo-resolver agent per todo (parallel)
        Dependency-blocked todos wait for their dependencies
Step 4: Collect all agent results
Step 5: git add -A && git commit -m "fix: resolve review findings"
Step 6: Rename todo files from pending to complete
        (change filename: {id}-pending-{p}-{desc}.md → {id}-complete-{p}-{desc}.md)
        Update YAML frontmatter: status: pending → status: complete
Step 7: Report: "{N} findings resolved, {M} files changed"
```

#### 6. Split `auto-compound.sh` into `build.sh`

**New file:** `scripts/compound/build.sh`
**Source:** `auto-compound.sh` Steps 1-7a (everything through quality sweep)

Contains:

- Report/section-spec analysis and priority selection
- Feature branch creation
- PRD generation via `ai_run`
- Task conversion
- Optional sprint contract negotiation
- Execution loop (`loop.sh`)
- Optional evaluator (Playwright)
- Quality sweep (lefthook, up to 3 fix attempts)

Does NOT contain: push, PR creation, monitoring, learnings extraction.
Exits 0 when code is built and clean.

#### 7. Create `ship.sh`

**New file:** `scripts/compound/ship.sh`
**Source:** `auto-compound.sh` Steps 7b-7c (push, PR, monitoring)

Contains:

- `git push -u origin $BRANCH_NAME`
- PR creation via `gh pr create` with structured body
- PR monitoring loop (max 5 cycles):
  - Gate A: CI checks (poll, auto-fix via `ai_run`)
  - Gate B: Codex review (poll, auto-fix P0/P1 via `ai_run`)
  - Gate C: Merge conflicts (rebase, resolve via `ai_run`)
- **Cumulative fix history** (`review-history.md`):
  - Created at start of monitoring loop
  - Each fix cycle appends: findings + diff of fix applied
  - Passed to each subsequent `ai_run` call so AI doesn't repeat failed fixes
- Accepts P2 findings as input (from `/harness:review`) for PR description injection
- Writes findings to file, includes via `cat` with length guard (max 2000 chars)

#### 8. Create `compound-learning.sh`

**New file:** `scripts/compound/compound-learning.sh`
**Source:** `auto-compound.sh` Step 8 (learnings extraction)

Contains:

- Read `progress.txt` + `review-history.md` + `.harness/todos/*-complete-*`
- Extract structured learnings via `ai_run` using template
- Write to `docs/solutions/compound-product/[feature]/[feature]-YYYY-MM-DD.md`
- Commit and push

This is the basic version. Phase 6 upgrades it to CE's full 5-agent, 13-category system.

#### 9. Rewire `/inf`

**File:** `.claude/commands/inf.md`
**Change type:** Major rewrite

Current: thin wrapper that calls `auto-compound.sh`.
New: full orchestrator following the architecture diagram above (Steps 1-6).

Key details:

- Step 2 (`build.sh`) runs via Bash tool
- Steps 3-4 (`/harness:review`, `/resolve_todo_parallel`) run in session
- Step 5 (`ship.sh`) runs via Bash tool, receives P2 findings as argument/file
- Step 6 (`compound-learning.sh`) runs via Bash tool

#### 10. Delete `auto-compound.sh`

After confirming `build.sh` + `ship.sh` + `compound-learning.sh` work correctly, delete the old monolithic script. Update any references.

#### 11. Delete `.claude/commands/review_code.md`

Replaced by `.claude/commands/harness/review.md`.

---

### P1 — Enrichment Hooks

#### 12. Enrich config from `/define-product`

**File:** `.claude/commands/define-product.md`
**Change:** Add Step 6b — updates Review Context in `.harness/harness.local.md` with product name, target users, external services, data sensitivity.

#### 13. Enrich config from `/define-architecture`

**File:** `.claude/commands/define-architecture.md`
**Change:** Add Step 4b — appends auth strategy, database patterns, external integrations, API patterns, deployment target to Review Context.

---

### P2 — Documentation Updates

#### 14. Update `CLAUDE.md`

- Progressive disclosure: add `.harness/harness.local.md` row
- Sub-agents table: update all agent names (4 renames) and add `harness-todo-resolver`
- Update `/review_code` → `/harness:review` references
- Update agent namespace structure in codebase map

#### 15. Update `AGENTS.md`

- Mirror CLAUDE.md changes

#### 16. Update `HOW_IT_WORKS.md`

- Replace `/review_code` with `/harness:review`
- Add `/resolve_todo_parallel` to command table
- Add "Review Agent Configuration" subsection
- Update `/inf` description to reflect new pipeline

#### 17. Update `METHODOLOGY.md`

- Update command reference table
- Update Layer 3 (Implementation) to reflect build/ship/learn split
- Update Layer 4 (Quality Gates) to include review agents

#### 18. Update `README.template.md`

- Update command table

#### 19. Update `REPOSITORY_STRUCTURE.md`

- Add `.harness/` directory with subdirectories
- Add `.claude/commands/harness/` to tree
- Update `.claude/agents/` to show namespace subdirectories (`research/`, `review/`, `resolve/`, `design/`, `skills/`)
- Remove `review_code.md` from tree
- Update decision tree

#### 20. Update `init-project.sh`

- Create `.harness/` directory structure
- Create `.harness/harness.local.md` with defaults
- Create `.harness/todos/.gitkeep`
- Create `.claude/agents/` namespace subdirectories with `.gitkeep` files
- Update any references to `auto-compound.sh` → `build.sh`

#### 21. Update `check-repo-structure.sh`

- Add `.harness/` to `ALLOWED_DIRS`
- Remove `launchpad.local.md` from `ALLOWED_DOCS` (no longer at root)

#### 22. Update all cross-references

- Search codebase for `review_code` → update to `harness:review`
- Search codebase for `auto-compound.sh` → update to `build.sh`/`ship.sh`/`compound-learning.sh`
- Search codebase for old agent names → update to new names (4 renames)
- Update `loop.sh` if it references `auto-compound.sh`

---

## Verification Checklist

- [ ] `.harness/` directory exists with `todos/` subdirectory
- [ ] `.harness/harness.local.md` exists with valid YAML
- [ ] `.claude/agents/` has 5 namespace subdirectories: `research/`, `review/`, `resolve/`, `design/`, `skills/`
- [ ] 7 existing agents moved to correct namespaces with correct renames
- [ ] Old flat agent files deleted from `.claude/agents/` root
- [ ] `.claude/commands/harness/review.md` exists and works
- [ ] `.claude/agents/resolve/harness-todo-resolver.md` exists
- [ ] `.claude/commands/resolve_todo_parallel.md` exists
- [ ] `build.sh` runs and exits after quality sweep (no push/PR)
- [ ] `ship.sh` runs: push → PR → monitoring loop with fix history
- [ ] `compound-learning.sh` runs: extracts learnings to `docs/solutions/`
- [ ] `/inf` orchestrates full pipeline: build → review → resolve → ship → learn
- [ ] `/harness:review` reads config and dispatches `pattern-finder`
- [ ] `/harness:review` writes findings to `.harness/todos/`
- [ ] `/harness:review` falls back gracefully when config is missing
- [ ] `/harness:review` detects Prisma changes for `review_db_agents`
- [ ] `/resolve_todo_parallel` reads todos, spawns resolvers, commits fixes
- [ ] Completed todos renamed from `pending` to `complete` (not deleted)
- [ ] `ship.sh` maintains cumulative `review-history.md` across fix cycles
- [ ] `compound-learning.sh` reads `review-history.md` + completed todos
- [ ] `check-repo-structure.sh` passes with `.harness/` present
- [ ] `init-project.sh` generates `.harness/` directory and config
- [ ] `/pull-launchpad` does NOT overwrite `.harness/` contents
- [ ] `.claude/commands/review_code.md` is deleted
- [ ] `auto-compound.sh` is deleted
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass
- [ ] No remaining references to `review_code` or `auto-compound.sh`
- [ ] No remaining references to old agent names (`codebase-locator`, `codebase-analyzer`, `codebase-pattern-finder`, `web-search-researcher`)

---

## What This Does NOT Include

| Deferred To | What                                                                         |
| ----------- | ---------------------------------------------------------------------------- |
| Phase 1     | Review agent definitions (security, typescript, performance, simplicity)     |
| Phase 2     | Database agent definitions (schema-drift, data-migration, data-integrity)    |
| Phase 3     | PR comment resolution agent + `/resolve-parallel` command                    |
| Phase 4     | `/deepen-plan` command                                                       |
| Phase 5     | `/test-browser` command                                                      |
| Phase 6     | Compound learning system upgrade (5-agent, 13-category, `/harness:compound`) |
| Phase 7     | Manual `/commit` workflow with triage                                        |
| Phase 8     | Automated backlog system (TODO.md → BACKLOG.md)                              |

---

## File Change Summary

| #   | File                                                       | Change                                                   | Priority |
| --- | ---------------------------------------------------------- | -------------------------------------------------------- | -------- |
| 1   | `.harness/todos/.gitkeep`                                  | **Create**                                               | P0       |
| 2   | `.harness/harness.local.md`                                | **Create**                                               | P0       |
| 3   | `.claude/agents/research/file-locator.md`                  | **Move+Rename** (from agents/codebase-locator.md)        | P0       |
| 4   | `.claude/agents/research/code-analyzer.md`                 | **Move+Rename** (from agents/codebase-analyzer.md)       | P0       |
| 5   | `.claude/agents/research/pattern-finder.md`                | **Move+Rename** (from agents/codebase-pattern-finder.md) | P0       |
| 6   | `.claude/agents/research/docs-locator.md`                  | **Move** (from agents/docs-locator.md)                   | P0       |
| 7   | `.claude/agents/research/docs-analyzer.md`                 | **Move** (from agents/docs-analyzer.md)                  | P0       |
| 8   | `.claude/agents/research/web-researcher.md`                | **Move+Rename** (from agents/web-search-researcher.md)   | P0       |
| 9   | `.claude/agents/skills/skill-evaluator.md`                 | **Move** (from agents/skill-evaluator.md)                | P0       |
| 10  | `.claude/agents/review/.gitkeep`                           | **Create** (empty, for Phase 1-2)                        | P0       |
| 11  | `.claude/agents/resolve/harness-todo-resolver.md`          | **Create**                                               | P0       |
| 12  | `.claude/agents/design/.gitkeep`                           | **Create** (empty, for Phase 5)                          | P0       |
| 13  | `.claude/commands/harness/review.md`                       | **Create**                                               | P0       |
| 14  | `.claude/commands/resolve_todo_parallel.md`                | **Create**                                               | P0       |
| 15  | `scripts/compound/build.sh`                                | **Create** (from auto-compound.sh)                       | P0       |
| 16  | `scripts/compound/ship.sh`                                 | **Create** (from auto-compound.sh)                       | P0       |
| 17  | `scripts/compound/compound-learning.sh`                    | **Create** (from auto-compound.sh)                       | P0       |
| 18  | `.claude/commands/inf.md`                                  | **Rewrite** — full pipeline orchestrator                 | P0       |
| 19  | `scripts/compound/auto-compound.sh`                        | **Delete**                                               | P0       |
| 20  | `.claude/commands/review_code.md`                          | **Delete**                                               | P0       |
| 21  | 7 old flat agent files in `.claude/agents/`                | **Delete** (after move to namespaces)                    | P0       |
| 22  | `.claude/commands/define-product.md`                       | **Edit** — add Step 6b                                   | P1       |
| 23  | `.claude/commands/define-architecture.md`                  | **Edit** — add Step 4b                                   | P1       |
| 24  | `CLAUDE.md`                                                | **Edit** — agent renames + namespace + review refs       | P2       |
| 25  | `AGENTS.md`                                                | **Edit** — mirror CLAUDE.md                              | P2       |
| 26  | `docs/guides/HOW_IT_WORKS.md`                              | **Edit**                                                 | P2       |
| 27  | `.launchpad/METHODOLOGY.md`                                | **Edit**                                                 | P2       |
| 28  | `README.template.md`                                       | **Edit**                                                 | P2       |
| 29  | `docs/architecture/REPOSITORY_STRUCTURE.md`                | **Edit** — add .harness/ + agent namespaces              | P2       |
| 30  | `scripts/setup/init-project.sh`                            | **Edit** — create .harness/ + agent namespace dirs       | P2       |
| 31  | `scripts/maintenance/check-repo-structure.sh`              | **Edit** — add .harness/ to ALLOWED_DIRS                 | P2       |
| 32  | `.claude/commands/research_codebase.md`                    | **Edit** — 4 agent renames                               | P2       |
| 33  | `.claude/commands/pnf.md`                                  | **Edit** — agent name refs                               | P2       |
| 34  | `.claude/commands/implement_plan.md`                       | **Edit** — agent name refs                               | P2       |
| 35  | `.claude/skills/creating-skills/SKILL.md`                  | **Edit** — agent name refs                               | P2       |
| 36  | `.claude/skills/creating-skills/references/METHODOLOGY.md` | **Edit** — agent table                                   | P2       |
| 37  | All other files referencing old names                      | **Edit** — cross-reference sweep                         | P2       |
