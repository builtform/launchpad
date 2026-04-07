# Phase 2: Database Agent Chain

**Date:** 2026-03-28
**Updated:** 2026-04-07 (v5 — Phase 1 v7 sync: 7 default review agents including testing-reviewer; v4 — reviewer fixes; v3 — meta-orchestrator split alignment; v2 — aligned with Phase 0 v4 + Phase 1 v3)
**Depends on:** Phase 0 (review agent config), Phase 1 (review agent fleet)
**Branch:** `feat/database-agent-chain`
**Status:** Plan — v5 (Phase 1 v7 sync)

---

## Decisions (All Finalized — synced with Phase 0 v4)

| Decision              | Answer                                                                                                    |
| --------------------- | --------------------------------------------------------------------------------------------------------- |
| Schema drift agent    | `schema-drift-detector` → `.claude/agents/review/schema-drift-detector.md`                                |
| Migration agent       | `data-migration-auditor` → `.claude/agents/review/data-migration-auditor.md`                              |
| Integrity agent       | `data-integrity-auditor` → `.claude/agents/review/data-integrity-auditor.md`                              |
| Model                 | `model: inherit` for all 3 (model-agnostic, per Phase 0)                                                  |
| Schema drift approach | Ground-up rewrite for Prisma (CE's Rails version structurally incompatible)                               |
| Migration auditor     | Medium adaptation — swap Rails for Prisma/TypeScript, keep PostgreSQL SQL                                 |
| Integrity auditor     | Light adaptation — swap model validations → Prisma constraints + Zod                                      |
| Dispatch order        | Sequential-then-parallel: drift first, then migration + integrity with drift report                       |
| Trigger condition     | Only when diff touches `prisma/schema.prisma` OR `prisma/migrations/*`                                    |
| Review command        | `/review` (flat at `.claude/commands/review.md`)                                                          |
| Agent config          | `.launchpad/agents.yml` `review_db_agents` key                                                            |
| Agent reads           | DB agents read: diff + `prisma/schema.prisma` + `prisma/migrations/` + review_context. Not full codebase. |
| Harden-plan           | `schema-drift-detector` is also in `harden_plan_conditional_agents` (from Phase 1)                        |

---

## Purpose

Create 3 specialized database review agents that run conditionally during `/review` when Prisma changes are detected. These catch schema drift, unsafe migrations, and data integrity violations before they reach production. After Phase 2, every `/harness:build` run that touches the database gets automatic safety analysis (via `/review` in the autonomous `/harness:build` pipeline).

---

## Architecture: How These Agents Fit

```
/review (from Phase 0, updated in Phase 1)
  │
  ├── Dispatch ALL review_agents in parallel (7 default, from Phase 1):
  │   ├── pattern-finder
  │   ├── security-auditor
  │   ├── kieran-foad-ts-reviewer
  │   ├── performance-auditor
  │   ├── code-simplicity-reviewer
  │   ├── architecture-strategist
  │   └── testing-reviewer
  │
  ├── IF Prisma changes detected (NEW — Phase 2):
  │   │
  │   │  Trigger: changed files match prisma/schema.prisma OR prisma/migrations/*
  │   │
  │   ├── Step A: schema-drift-detector (SEQUENTIAL — runs first)
  │   │   └── Output: drift report (clean / drift-detected)
  │   │
  │   └── Step B: IN PARALLEL, with drift report as context:
  │       ├── data-migration-auditor
  │       └── data-integrity-auditor
  │
  ├── Synthesize all findings → deduplicate → P1/P2/P3
  │
  └── Write to .harness/todos/ + .harness/observations/
```

### Why Sequential-Then-Parallel?

The schema-drift-detector catches unrelated changes that leaked into the PR. If drift exists, the migration and integrity auditors would waste time analyzing changes that shouldn't be there. Running drift detection first gives downstream agents a clean picture of what the PR actually intends to change.

**Note:** Phase 0 v4's `/review` Step 4 says "Dispatch all review_db_agents in parallel." Phase 2 overrides this with sequential-then-parallel because the drift report is critical context. Update `/review` Step 4 to implement this ordering.

### Two Conditional Dispatch Paradigms

Two conditional dispatch paradigms: (1) file-pattern conditionals -- `review_db_agents` dispatched when diff touches Prisma files (deterministic, stateless); (2) status conditionals -- `review_design_agents` dispatched when section status = `designed` (stateful, depends on `/harness:plan`). Future agent categories should follow one of these established patterns.

### Also Used by `/harden-plan` (in `/harness:plan`)

`schema-drift-detector` is in `harden_plan_conditional_agents` (from Phase 1's `agents.yml` update). It runs during `/harden-plan --full` when the plan involves Prisma schema changes. The other two DB agents are NOT in harden-plan — they review code/migrations, not plans.

**Dual-purpose wiring across orchestrator boundaries:**

- In `/review`: drift detection as part of code review, output feeds migration + integrity auditors
- In `/harden-plan`: drift detection as part of plan review, findings go directly to plan synthesizer

---

## The Prisma vs Rails Problem

CE's schema-drift-detector is built for Rails (155 lines, structurally incompatible). Our version is a ground-up rewrite.

| Concept         | Rails                                | Prisma                                          |
| --------------- | ------------------------------------ | ----------------------------------------------- |
| Schema file     | `schema.rb` — auto-generated from DB | `schema.prisma` — hand-authored source of truth |
| Migrations      | Imperative Ruby scripts              | Generated SQL from `prisma migrate dev`         |
| Source of truth | Database → schema reflects it        | Schema file → database follows it               |
| Drift direction | DB state leaks into schema           | Schema and DB can diverge either way            |

---

## Agent Definitions

### 1. `schema-drift-detector`

**File:** `.claude/agents/review/schema-drift-detector.md`
**CE source:** Ground-up rewrite (CE's 155-line Rails version not adapted)
**Also used by:** `/harden-plan` (conditional — full only, IF Prisma changes)

**Frontmatter:**

```yaml
---
name: schema-drift-detector
description: Detects schema.prisma changes without corresponding migrations, migration files without schema changes, and other Prisma drift patterns.
model: inherit
---
```

**Agent reads:** `prisma/schema.prisma` + `prisma/migrations/` + git diff of Prisma files + review_context. Does NOT read entire codebase.

**Prisma Drift Patterns (4 types):**

1. **Schema change without migration** — `schema.prisma` edited but no `prisma/migrations/` in diff → P1
2. **Migration without schema change** — Migration files present but `schema.prisma` unchanged → P1
3. **Migration from another branch** — Timestamp significantly before branch creation → P2
4. **SQL ↔ schema mismatch** — Migration SQL doesn't match schema.prisma diff → P1

**Core Process (4 steps):**

1. **Identify changes** — List all Prisma-related files in diff
2. **Cross-reference** — Verify each schema change has a migration and vice versa
3. **Detect drift** — Check timestamps, SQL-schema alignment, scope creep
4. **Check SQL quality** — Transactions, large table ALTERs, DROP safety, NOT NULL defaults

**Output — expected structure:**

```markdown
## Drift Report

### Status: CLEAN | DRIFT-DETECTED

### Legitimate Changes (from this PR)

- [file path] — [description of change]

### Drifted Changes (from other branches — should be removed)

- [file path] — [description, estimated source branch/date]

### SQL Quality Concerns

- [file:line] — [issue, severity P1/P2/P3]
```

**Integration instruction:** "When dispatched by `/review`: This agent runs FIRST. Your drift report is passed to data-migration-auditor and data-integrity-auditor. Use the structured format above so downstream agents can parse legitimate vs drifted changes. When dispatched by `/harden-plan`: No downstream agents consume your report. Produce findings directly as P1/P2/P3 for the plan synthesizer."

---

### 2. `data-migration-auditor`

**File:** `.claude/agents/review/data-migration-auditor.md`
**CE source:** `data-migration-expert` (112 lines) — medium adaptation

**Frontmatter:**

```yaml
---
name: data-migration-auditor
description: Validates data migrations, backfills, and production data transformations for safety in Prisma/PostgreSQL.
model: inherit
---
```

**Agent reads:** Diff + Prisma files + drift report (from schema-drift-detector) + review_context. Uses Grep for codebase-wide reference checks (step 6).

**6 Review Areas:**

1. **Understand real data** — List affected tables, verify with SQL, never trust seed data
2. **Validate migration SQL** — Reversibility, batching, scoped UPDATEs, index maintenance
3. **Verify mapping logic** — CASE/IF branches cover all values, no silent NULLs, no swapped IDs
4. **Check observability** — Post-deploy queries, alarms, dashboards
5. **Validate rollback** — Feature flags, restore procedures, manual rollback SQL (Prisma is forward-only)
6. **Structural refactors** — Search for references to removed columns/tables in codebase

**Output:** Per-issue: file:line, description, blast radius, fix. **Refuses approval without verification + rollback plan.**

**Context instruction:** "You receive the drift report. Focus ONLY on legitimate changes."

---

### 3. `data-integrity-auditor`

**File:** `.claude/agents/review/data-integrity-auditor.md`
**CE source:** `data-integrity-guardian` (86 lines) — light adaptation

**Frontmatter:**

```yaml
---
name: data-integrity-auditor
description: Reviews database migrations, data models, and persistent data code for safety. Checks constraints, transactions, referential integrity, and privacy compliance in Prisma/PostgreSQL.
model: inherit
---
```

**Agent reads:** Diff + Prisma files + drift report + review_context.

**5 Review Areas:**

1. **Migration safety** — Reversibility, data loss scenarios, NULL handling, long-running locks
2. **Data constraints** — Prisma `@unique`/`@default`/`@@index` + Zod application-level validation, race conditions
3. **Transaction boundaries** — `prisma.$transaction()` usage, isolation levels, deadlock prevention
4. **Referential integrity** — `onDelete`/`onUpdate` actions, orphan prevention, cascade chains
5. **Privacy compliance** — PII identification, encryption, logging prevention, GDPR deletion, cascade PII fragments

**Output:** Per-issue: file:line, issue, specific data corruption scenario, P1/P2/P3, concrete fix with Prisma schema or TypeScript example.

**Context instruction:** "You receive the drift report. Focus ONLY on legitimate changes."

---

## Changes to `/review`

**Update Step 4 (Conditional DB Agents) — replace simple parallel dispatch with sequential-then-parallel:**

```
Step 4: Conditional DB Agent Dispatch
  IF changed files match prisma/schema.prisma OR prisma/migrations/*:

    Step 4a: Dispatch schema-drift-detector (SEQUENTIAL)
             Pass: diff + prisma files + review_context
             Wait for output → drift_report

    Step 4b: Dispatch IN PARALLEL with drift report:
             - data-migration-auditor (receives: diff + prisma files + review_context + drift_report)
             - data-integrity-auditor (receives: diff + prisma files + review_context + drift_report)
```

This replaces Phase 0's placeholder "Dispatch all review_db_agents in parallel" with the sequential-then-parallel pattern.

---

## Changes to `.launchpad/agents.yml`

Update `review_db_agents` from empty to populated:

```yaml
review_db_agents: # Dispatch order defined in /review Step 4, not by list order
  - schema-drift-detector
  - data-migration-auditor
  - data-integrity-auditor
```

Note: `schema-drift-detector` is ALSO in `harden_plan_conditional_agents` (added in Phase 1). It serves dual purpose: drift detection in code review (`/review` in `/harness:build`) AND plan review (`/harden-plan` in `/harness:plan`).

---

## Changes to `init-project.sh`

Update the default `.launchpad/agents.yml` template to include all 3 database agents in `review_db_agents` (currently empty `[]`).

---

## Verification Checklist

### Agents Created

- [ ] `.claude/agents/review/schema-drift-detector.md` — `model: inherit`, Prisma-native (no Rails)
- [ ] `.claude/agents/review/data-migration-auditor.md` — `model: inherit`, Prisma terms
- [ ] `.claude/agents/review/data-integrity-auditor.md` — `model: inherit`, Prisma constraints + Zod

### Wiring

- [ ] `.launchpad/agents.yml` `review_db_agents` lists all 3 agents
- [ ] `/review` Step 4 dispatches schema-drift-detector FIRST (sequential)
- [ ] `/review` Step 4 dispatches migration + integrity in parallel AFTER drift
- [ ] `/review` passes drift report as context to downstream agents
- [ ] DB agents NOT dispatched when diff has no Prisma changes
- [ ] `schema-drift-detector` also present in `harden_plan_conditional_agents`

### Agent Behavior

- [ ] `schema-drift-detector` detects all 4 drift patterns
- [ ] `schema-drift-detector` produces clean/drift-detected output with legitimate vs drifted classification
- [ ] `data-migration-auditor` includes PostgreSQL SQL verification snippets
- [ ] `data-migration-auditor` refuses approval without verification + rollback plan
- [ ] `data-migration-auditor` checks for Prisma forward-only migration rollback gap
- [ ] `data-integrity-auditor` checks Prisma schema constraints + Zod (not ActiveRecord)
- [ ] `data-integrity-auditor` checks `onDelete`/`onUpdate` (not `dependent: :destroy`)
- [ ] `data-integrity-auditor` checks `prisma.$transaction()` (not `ActiveRecord::Base.transaction`)
- [ ] `data-integrity-auditor` includes GDPR/privacy checks
- [ ] No agent references Rails, Ruby, ActiveRecord, rake tasks, or fixtures
- [ ] All agents produce P1/P2/P3 findings with file:line references
- [ ] All agents read scoped files (Prisma dir + diff), not entire codebase

### Cleanup

- [ ] `init-project.sh` updated with 3 DB agents in `agents.yml` template
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                           |
| ------------ | ---------------------------------------------- |
| Phase 3      | `spec-flow-analyzer` for `/harden-plan`        |
| Phase 4      | PR comment resolution (`/resolve-pr-comments`) |
| Phase 7      | `/commit` workflow wiring for database agents  |
| Phase Finale | Documentation refresh for agent tables         |

---

## File Change Summary

| #   | File                                              | Change                                                    | Priority |
| --- | ------------------------------------------------- | --------------------------------------------------------- | -------- |
| 1   | `.claude/agents/review/schema-drift-detector.md`  | **Create** (ground-up Prisma rewrite)                     | P0       |
| 2   | `.claude/agents/review/data-migration-auditor.md` | **Create** (adapted from CE)                              | P0       |
| 3   | `.claude/agents/review/data-integrity-auditor.md` | **Create** (adapted from CE)                              | P0       |
| 4   | `.launchpad/agents.yml`                           | **Edit** — populate `review_db_agents`                    | P0       |
| 5   | `.claude/commands/review.md`                      | **Edit** — sequential-then-parallel DB dispatch in Step 4 | P0       |
| 6   | `scripts/setup/init-project.sh`                   | **Edit** — update `agents.yml` template                   | P1       |
