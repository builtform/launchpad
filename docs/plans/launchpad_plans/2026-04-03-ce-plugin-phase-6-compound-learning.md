# Phase 6: Compound Learning Upgrade

**Date:** 2026-04-03
**Depends on:** Phase 0 (pipeline infrastructure — `/harness:build` Step 5, `docs/solutions/` directory), Phase 3 (Step 2.5 learnings scan wiring in `/harden-plan`)
**Branch:** `feat/compound-learning`
**Status:** Plan — v4.3 (Phase 0 v9 sync: Context Analyzer reads review-summary.md for suppressed finding patterns; v4.2 — Phase 10 cascading changes: pipeline diagram step order, design_pattern category, design_system component)

---

## Decisions (All Finalized)

| Decision                     | Answer                                                                                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Command name                 | `/learn` → `.claude/commands/learn.md` (flat — "learn" matches Step 5 verb in pipeline)                                                                          |
| Skill name                   | `compound-docs` → `.claude/skills/compound-docs/SKILL.md` (process skill — documentation methodology, not domain knowledge)                                      |
| Agent name                   | `learnings-researcher` → `.claude/agents/research/learnings-researcher.md`                                                                                       |
| Agent namespace              | `research/` (alongside file-locator, code-analyzer, etc. — per Phase 0)                                                                                          |
| Agent model                  | `model: inherit` (per Phase 0)                                                                                                                                   |
| CE source: command           | `commands/workflows/compound.md` (241 lines) — medium adaptation                                                                                                 |
| CE source: skill             | `skills/compound-docs/SKILL.md` (511 lines) + `schema.yaml` + templates — heavy adaptation (Rails → TypeScript/Prisma taxonomy)                                  |
| CE source: agent             | `agents/research/learnings-researcher.md` (264 lines) — light adaptation                                                                                         |
| Sub-agents                   | 5 inline sub-agents in `/learn` command (CE's approach — not separate agent files)                                                                               |
| Category taxonomy            | 14 categories (CE's 13 with `workflow_issue` → `pipeline_issue` rename + new `design_pattern` category)                                                          |
| Component taxonomy           | 16 components (full replacement — Rails → TypeScript/Next.js/Hono/Prisma + new `design_system` component)                                                        |
| Root cause taxonomy          | 17 values (4 renames: missing_relation, missing_eager_load, concurrency_issue, missing_pipeline_step; 13 kept as-is)                                             |
| Resolution type taxonomy     | 10 values (1 rename: `workflow_improvement` → `pipeline_improvement`)                                                                                            |
| YAML validation              | Blocking gate — `/learn` will not write file if frontmatter is invalid                                                                                           |
| Existing `compound-product/` | Preserved alongside new 14-category system — different purpose (feature run learnings vs problem resolution)                                                     |
| Phase 3 Step 2.5 activation  | Phase 6 populates `docs/solutions/` — Step 2.5 becomes active automatically                                                                                      |
| Discoverability check        | One-time scaffolding verification during Phase 6 implementation (not runtime) — ensure `docs/solutions/` is referenced in CLAUDE.md progressive disclosure table |
| Secret scanning              | Before writing assembled doc, scan for API keys, tokens, passwords, connection strings — redact with `[REDACTED]` if found                                       |

---

## Purpose

Replace the basic learning extraction in `/harness:build` Step 5 (currently reads `progress.txt` and writes a simple doc) with a full compound learning system: a 5-agent parallel research pipeline that captures problems, solutions, root causes, and prevention strategies into a structured 14-category knowledge base at `docs/solutions/`.

This closes the feedback loop: Build → Ship → **Learn (Phase 6)** → next Build → Harden with past learnings (Phase 3 Step 2.5). Every build makes the next build smarter.

---

## Architecture: How Phase 6 Components Wire In

```
/harness:plan (interactive)              /harness:build (autonomous)
  │                                        │
  ├── design step                          ├── Step 1:   /inf
  ├── /pnf                                 ├── Step 2:   /review
  ├── /harden-plan                         ├── Step 2.5: /resolve_todo_parallel
  │     └── Step 2.5: Learnings Scan       ├── Step 3:   /test-browser
  └── human approval                       ├── Step 4:   /ship
       ↓ approved                          ├── Step 5:   /learn  ← UPGRADED by Phase 6
                                           │     ├── BEFORE Phase 6: compound-learning.sh (basic — reads progress.txt)
                                           │     └── AFTER Phase 6: /learn (full — 5-agent research + structured docs)
                                           │           ├── Load compound-docs skill (process methodology)
                                           │           ├── Spawn 5 inline sub-agents in parallel:
                                           │           │   ├── Context Analyzer
                                           │           │   ├── Solution Extractor
                                           │           │   ├── Related Docs Finder
                                           │           │   ├── Prevention Strategist
                                           │           │   └── Category Classifier
                                           │           ├── Assemble solution doc with validated YAML frontmatter
                                           │           ├── Write to docs/solutions/[category]/[filename].md
                                           │           └── Secret/credential scan before writing
                                           │
                                           └── Step 6:   Report

Feedback loop (crosses orchestrator boundary):
  /harness:build Step 5 (/learn) → writes to docs/solutions/
  /harness:plan (/harden-plan Step 2.5) → dispatches learnings-researcher → reads docs/solutions/
                                        → returns top 5 matches as context to harden-plan agents
```

`learnings-researcher` is dispatched by `/harden-plan` Step 2.5 (Phase 3) and operates in the interactive `/harness:plan` orchestrator — reading knowledge written by `/learn` in the autonomous `/harness:build` orchestrator. Also available standalone (e.g., "What have we learned about Prisma migrations?").

---

## Component Definitions

### 1. `/learn` Command

**File:** `.claude/commands/learn.md`
**CE source:** `commands/workflows/compound.md` (241 lines) — medium adaptation
**Called by:** `/harness:build` Step 5 (replaces `compound-learning.sh`)
**Also usable:** standalone (after any problem resolution, not just pipeline runs)

**Adaptations from CE:**

- Rename from `/workflows:compound` → `/learn` (flat, matches pipeline verb)
- Replace Rails-specific prompts with TypeScript/Next.js/Hono/Prisma context
- Adapt 14-category taxonomy (1 rename: `workflow_issue` → `pipeline_issue`)
- Replace 17 component values (full swap — Rails → LaunchPad stack)
- Adapt 17 root cause values (4 renames, 13 kept as-is):
  `missing_association` → `missing_relation` (Prisma uses "relations")
  `missing_include` → `missing_eager_load` (concept, not API name)
  `thread_violation` → `concurrency_issue` (broader — React concurrent, API races)
  `missing_workflow_step` → `missing_pipeline_step` (matches pipeline_issue rename)
  All other 13 values kept as-is (universal: missing_index, wrong_api, scope_issue,
  async_timing, memory_leak, config_error, logic_error, test_isolation,
  missing_validation, missing_permission, inadequate_documentation,
  missing_tooling, incomplete_setup)
- Adapt 10 resolution types (1 rename: `workflow_improvement` → `pipeline_improvement`)
- Load `compound-docs` skill for process methodology
- Keep 5 inline sub-agents (not extracted to separate files)
- Add secret/credential scan before writing assembled doc
- Discoverability check is a one-time scaffolding step (not runtime)

**Usage:**

```
/learn                              → capture learnings from current session
/learn "fixed the Prisma N+1"      → capture with problem description
```

**Auto-invocation:** Triggers on phrases like "that worked", "it's fixed", "the issue was", "root cause was". The command detects confirmation of a resolved problem and offers to capture learnings. Auto-invocation only applies in standalone/interactive sessions. When `/learn` is dispatched by an orchestrator (e.g., `/harness:build` Step 5), auto-invocation is suppressed — the orchestrator handles invocation.

**Flow (3 phases):**

```
Phase 1: Parallel Research (5 inline sub-agents)
  Spawn all 5 in parallel. Each returns text only — no file writes.

  1. Context Analyzer
     - Scoped context: receives problem description + module path only
     - What module/area is affected?
     - What was the original problem?
     - What environment/conditions triggered it?
     - Optional: reads .harness/review-summary.md (Phase 0 v9 confidence rubric output)
       for suppressed finding patterns that may inform the problem context
     - Returns: module name, problem summary, environment details

  2. Solution Extractor
     - Scoped context: receives code diff only
     - What was tried and failed?
     - What ultimately worked?
     - What code changes were made? (file paths, diffs)
     - Returns: failed approaches, working solution, code changes

  3. Related Docs Finder
     - Scoped context: receives module name + tags (for grep pre-filtering)
     - Are there existing docs in docs/solutions/ about this topic?
     - Would this duplicate an existing solution doc?
     - Use Grep for pre-filtering (search by module/tags in frontmatter),
       then Read only matching files — do NOT read all files sequentially
     - Returns: list of related docs (paths + summaries), duplicate flag

  4. Prevention Strategist
     - Scoped context: receives root cause description + solution summary
     - How can this be prevented in the future?
     - What test, lint rule, or process change would catch it earlier?
     - Returns: prevention recommendations, suggested safeguards

  5. Category Classifier
     - Scoped context: receives problem type + component + symptoms
     - Which of the 14 problem_type categories fits best?
     - What component, root_cause, and resolution_type values apply?
     - What severity level?
     - What tags would make this findable?
     - Returns: full YAML frontmatter field values

  Scoped context reduces token consumption by ~60-70% compared to passing
  full session context to each agent.

Phase 2: Assembly + Validation
  - Collect all Phase 1 results
  - IF Related Docs Finder flagged a duplicate:
    - When dispatched by `/harness:build` (autonomous): auto-decide — create new doc
      with `-2`, `-3` suffix. Do not prompt the user.
    - When standalone/interactive: ask user "Similar doc exists at [path].
      Update existing or create new?"
    IF update: modify existing doc instead of creating new one
  - Assemble solution document using compound-docs skill template:
    ## Troubleshooting: [Problem Title]
    ## Problem
    ## Environment
    ## Symptoms
    ## What Didn't Work
    ## Solution
    ## Why This Works
    ## Prevention
    ## Related Issues
  - Generate YAML frontmatter from Category Classifier output
  - SECURITY CATEGORY REDACTION: When Category Classifier assigns
    `security_issue`: auto-redact specific exploitation details from the
    learning document. Focus on prevention strategy only. Security-category
    learnings document prevention approaches, not reproduction steps.
  - VALIDATE YAML (BLOCKING GATE):
    All required fields present (module, date, problem_type, component,
    symptoms, root_cause, resolution_type, severity)
    All enum values match the taxonomy
    IF invalid: fix automatically, re-validate. If still invalid, warn and
    ask user for correction. Do NOT write file with invalid frontmatter.
  - SECRET SCAN before writing:
    Scan the assembled document for patterns matching API keys, tokens,
    passwords, connection strings, or credentials. If found, redact with
    `[REDACTED]` and warn the user: "Sensitive data found and redacted.
    Review the document before committing."
  - Generate filename: [sanitized-symptom]-[module]-[YYYYMMDD].md
    Sanitization: lowercase, hyphens, no special chars, max 60 chars
  - Write to: docs/solutions/[category-directory]/[filename].md

Phase 3: Post-Documentation
  - Critical pattern detection:
    IF severity is critical: ask "Should this be promoted to Required Reading
    in docs/solutions/patterns/critical-patterns.md?"
    IF yes: append pattern entry using critical pattern template
  - Report: "Learning captured: docs/solutions/[category]/[filename].md"
```

**Strict rules:**

- YAML validation is a blocking gate — never write invalid frontmatter
- 5 sub-agents run in parallel — do not sequence them
- Sub-agents return text only — the command assembles and writes the file
- Duplicate detection before writing — ask user, don't silently overwrite
- Filename sanitization: lowercase, hyphens, no special chars, max 60 chars
- Solution docs go to `docs/solutions/[category]/` — not `docs/solutions/compound-product/`
- The existing `compound-product/` directory is preserved (different purpose)

---

### 2. `compound-docs` Skill

**File:** `.claude/skills/compound-docs/SKILL.md`
**CE source:** `skills/compound-docs/SKILL.md` (511 lines) + supporting files — heavy adaptation
**Loaded by:** `/learn` command
**Category:** Process skill (same category as `brainstorming`, `document-review`)

**Supporting files:**

- `.claude/skills/compound-docs/references/yaml-schema.md` — adapted YAML schema
- `.claude/skills/compound-docs/assets/resolution-template.md` — adapted template
- `.claude/skills/compound-docs/assets/critical-pattern-template.md` — near-direct port

**Adaptations from CE:**

- Replace all Rails component values with LaunchPad 16-component taxonomy
- Rename `workflow_issue` → `pipeline_issue` across all references
- Rename 4 root cause values for Prisma/TypeScript terminology (missing_relation, missing_eager_load, concurrency_issue, missing_pipeline_step)
- Rename `workflow_improvement` → `pipeline_improvement`
- Remove `rails_version` optional field, add `stack_version` (optional, for tracking Next.js/Prisma versions)
- Keep the 7-step process — framework-agnostic documentation methodology
- Keep YAML validation as blocking gate
- Keep critical pattern template and promotion flow

**14-Category Taxonomy (adapted):**

| Category               | Directory               | What Gets Captured                                                                               |
| ---------------------- | ----------------------- | ------------------------------------------------------------------------------------------------ |
| `build_error`          | `build-errors/`         | pnpm build failures, TypeScript compilation, Turborepo errors                                    |
| `test_failure`         | `test-failures/`        | Vitest failures, flaky tests, test isolation issues                                              |
| `runtime_error`        | `runtime-errors/`       | Unhandled exceptions, 500 errors, React hydration crashes                                        |
| `performance_issue`    | `performance-issues/`   | Prisma N+1, slow API responses, bundle size, memory leaks                                        |
| `database_issue`       | `database-issues/`      | Prisma migration failures, schema drift, constraint violations                                   |
| `security_issue`       | `security-issues/`      | Auth bypasses, XSS, CSRF, secret exposure, CORS misconfig                                        |
| `ui_bug`               | `ui-bugs/`              | React rendering bugs, Tailwind CSS regressions, layout breaks                                    |
| `integration_issue`    | `integration-issues/`   | Stripe API failures, webhook issues, third-party API errors                                      |
| `logic_error`          | `logic-errors/`         | Wrong calculations, incorrect state transitions, bad conditionals                                |
| `developer_experience` | `developer-experience/` | Dev setup issues, DX friction, tooling gaps                                                      |
| `pipeline_issue`       | `pipeline-issues/`      | Harness step failures, misconfigured agents, pipeline gaps                                       |
| `best_practice`        | `best-practices/`       | Patterns to follow, architectural decisions, conventions                                         |
| `documentation_gap`    | `documentation-gaps/`   | Missing docs, outdated docs, unclear instructions                                                |
| `design_pattern`       | `design-patterns/`      | Design system violations, responsive regressions, visual design decisions, design audit findings |

**16-Component Taxonomy:**

| Component           | What It Covers                                                               |
| ------------------- | ---------------------------------------------------------------------------- |
| `nextjs_page`       | App Router pages, layouts, route handlers                                    |
| `nextjs_middleware` | Next.js middleware, auth guards                                              |
| `react_component`   | React components (client + server)                                           |
| `hono_route`        | Hono API routes, middleware                                                  |
| `prisma_schema`     | Prisma schema, models, relations                                             |
| `prisma_migration`  | Database migrations                                                          |
| `prisma_query`      | Prisma client queries, transactions                                          |
| `shared_package`    | packages/shared, packages/ui                                                 |
| `authentication`    | Auth flow, session management                                                |
| `api_integration`   | External API clients (Stripe, etc.)                                          |
| `testing`           | Vitest tests, test utilities                                                 |
| `build_config`      | Turborepo, pnpm workspace, tsconfig                                          |
| `styling`           | Tailwind CSS, design tokens                                                  |
| `documentation`     | README, docs, architecture files                                             |
| `tooling`           | Scripts, CLI tools, dev utilities                                            |
| `design_system`     | Design artifacts, design reviews, responsive audits, visual design decisions |

**7-Step Skill Process:**

```
1. Detect Confirmation — require at least two trigger indicators:
      (1) a trigger phrase ("that worked", "it's fixed", etc.) AND
      (2) `.harness/todos/` contains recently-completed items (items with
          `status: complete` modified within the current session).
      Single trigger phrase alone is insufficient.
2. Gather Context — module, symptom, investigation, root cause, solution, prevention
3. Check Existing Docs — search docs/solutions/ for duplicates
4. Generate Filename — [sanitized-symptom]-[module]-[YYYYMMDD].md
5. Validate YAML — BLOCKING GATE (all required fields, valid enum values)
6. Create Documentation — write to docs/solutions/[category]/
7. Cross-Reference + Critical Pattern Detection — link related docs, offer promotion
```

---

### 3. `learnings-researcher` Agent

**File:** `.claude/agents/research/learnings-researcher.md`
**CE source:** `agents/research/learnings-researcher.md` (264 lines) — light adaptation
**Dispatched by:** `/harden-plan` Step 2.5 (Phase 3). Also standalone.

**Adaptations from CE:**

- Keep in `research/` namespace (matches CE and Phase 0)
- Add `model: inherit` frontmatter
- Remove Rails-specific search examples
- Update component/category references to LaunchPad taxonomy
- Keep the 7-step search strategy — framework-agnostic

**Frontmatter:**

```yaml
---
name: learnings-researcher
description: Searches docs/solutions/ for relevant past solutions by YAML frontmatter metadata. Use before implementing features or fixing problems to surface institutional knowledge.
model: inherit
---
```

**7-Step Search Strategy:**

```
1. Extract Keywords — from feature description or problem statement
2. Category Narrowing — identify likely problem_type categories to search first
3. Grep Pre-Filter — parallel searches for:
   - tags matching keywords
   - title/module matching keywords
   - component matching affected area
4. Always Check Critical Patterns — read docs/solutions/patterns/critical-patterns.md
5. Read Frontmatter Only — for candidates, read only first 30 lines (frontmatter)
   to assess relevance without consuming full document tokens
6. Score and Rank — classify matches as strong/moderate/weak
   - Strong: same module + same problem_type + matching tags
   - Moderate: same component + related problem_type
   - Weak: matching tags only
7. Return Distilled Summaries — for each match:
   - File path
   - Module
   - Relevance score (strong/moderate/weak)
   - Key insight (1-2 sentences extracted from solution section)
   - Prevention recommendation (if applicable)
```

**Agent reads:** `docs/solutions/` directory. Uses Grep for pre-filtering, Read for frontmatter inspection. Does NOT read full solution documents unless relevance is strong (token efficiency).

**Tool restriction:** Read, Grep, Glob only. No Edit, Write, or Bash — this is a read-only research agent.

**Performance design:** Optimized for sub-30-second lookups. The pre-filter + frontmatter-only read strategy avoids loading hundreds of full documents. Cap at 5 returned results (matching Phase 3 Step 2.5's cap).

---

## Changes to Existing Files

### 1. Update `/harness:build` Step 5

Replace `compound-learning.sh` with `/learn`:

```
Step 5: Learn (UPGRADED by Phase 6)
  - BEFORE: Run compound-learning.sh (basic — reads progress.txt)
  - AFTER: Run /learn
    ├── 5-agent parallel research
    ├── Assemble solution doc with validated YAML
    ├── Write to docs/solutions/[category]/
    └── Secret/credential scan before writing
```

### 2. Update meta-orchestrator design doc

Note: Phase 3 and Phase 5 already edited this document (kickoff flow, harden-plan flow, Step 3). Verify the current state of Step 5 before editing — adjacent sections may have been modified by prior phases.

Update Step 5 (Learn) in the `/harness:build` flow diagram:

```
  ├── Step 5: Learn (Phase 6 — upgraded)
  │     ├── Run /learn
  │     │     ├── Load compound-docs skill
  │     │     ├── 5 parallel sub-agents → assemble solution doc
  │     │     ├── YAML validation (blocking gate)
  │     │     ├── Write to docs/solutions/[category]/
  │     │     └── Secret/credential scan before writing
  │     └── Solution captured for future /harden-plan Step 2.5 lookups
```

Update Step 2.5 note: remove "dormant until Phase 6" — it is now active.

### 3. Update `/harden-plan` Step 2.5

Phase 3's Step 2.5 currently describes the learnings scan as inline behavior ("scan docs/solutions/, match by frontmatter, skip if empty") with "dormant until Phase 6." Phase 6 upgrades this from inline scanning to agent-dispatched searching:

- Remove "dormant until Phase 6" language — Step 2.5 is now active
- Change implementation strategy: Step 2.5 now dispatches `learnings-researcher` agent instead of performing the scan inline. The agent's 7-step strategy (grep pre-filter, frontmatter-only reads, scoring) is more efficient than inline scanning, especially as `docs/solutions/` grows.
- The cap (5 most-recent, key insight only) and malformed frontmatter skip remain as specified in Phase 3 — they are constraints on the output, not the implementation

### 4. Create `docs/solutions/` category directories

Create 14 category directories with `.gitkeep`:

```
docs/solutions/
├── build-errors/.gitkeep
├── test-failures/.gitkeep
├── runtime-errors/.gitkeep
├── performance-issues/.gitkeep
├── database-issues/.gitkeep
├── security-issues/.gitkeep
├── ui-bugs/.gitkeep
├── integration-issues/.gitkeep
├── logic-errors/.gitkeep
├── developer-experience/.gitkeep
├── pipeline-issues/.gitkeep
├── best-practices/.gitkeep
├── documentation-gaps/.gitkeep
├── design-patterns/.gitkeep
├── patterns/
│   └── critical-patterns.md        (empty template with header)
├── compound-product/               (PRESERVED — existing, different purpose)
│   ├── README.md
│   ├── _template.md
│   └── patterns/promoted-patterns.md
└── README.md                       (updated — documents both systems)
```

### 5. Update `init-project.sh`

Add 14 category directories to project scaffold. Preserve `compound-product/` alongside.

### 6. Update `docs/solutions/README.md`

Document both systems:

- **Compound Learning** (Phase 6): 14-category problem resolution knowledge base, populated by `/learn`
- **Compound Product** (existing): feature run learnings from auto-compound, different schema

---

## What NOT to Port from CE

| CE Component                             | Decision | Reason                                                                                                                              |
| ---------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `rails_version` optional field           | Replaced | `stack_version` optional field (tracks Next.js/Prisma versions)                                                                     |
| 17 Rails component values                | Replaced | 16 TypeScript/Next.js/Hono/Prisma components                                                                                        |
| Rails-specific root cause values         | Renamed  | 4 values adapted for Prisma/TypeScript terminology (missing_relation, missing_eager_load, concurrency_issue, missing_pipeline_step) |
| `ce-compound-refresh` skill              | Deferred | Updating existing learnings is lower priority — create new docs first, refresh later                                                |
| Track-based templates (bug vs knowledge) | Deferred | Simplify to single template initially — add tracks if needed after real usage                                                       |
| Auto-invocation on "that worked"         | Kept     | Good UX — the command offers to capture, doesn't force it                                                                           |

---

## Verification Checklist

### Files Created

- [ ] `.claude/commands/learn.md` — 3-phase flow, 5 inline sub-agents, YAML validation gate, secret scan before writing
- [ ] `.claude/skills/compound-docs/SKILL.md` — 7-step process, 14 categories, 16 components, YAML schema
- [ ] `.claude/skills/compound-docs/references/yaml-schema.md` — adapted schema with LaunchPad taxonomies
- [ ] `.claude/skills/compound-docs/assets/resolution-template.md` — adapted template
- [ ] `.claude/skills/compound-docs/assets/critical-pattern-template.md` — near-direct port
- [ ] `.claude/agents/research/learnings-researcher.md` — `model: inherit`, 7-step search, read-only tools

### Wiring

- [ ] `/harness:build` Step 5 calls `/learn` (replaces `compound-learning.sh`)
- [ ] `/learn` loads `compound-docs` skill
- [ ] `/learn` spawns 5 inline sub-agents in parallel
- [ ] `/learn` writes to `docs/solutions/[category]/` (not `compound-product/`)
- [ ] `learnings-researcher` dispatched by `/harden-plan` Step 2.5 (Phase 3 — now active)
- [ ] `/harden-plan` Step 2.5 "dormant" language removed
- [ ] Meta-orchestrator design doc updated (Step 5 upgraded, Step 2.5 active)
- [ ] `/learn` is NOT exclusively standalone — wired into pipeline Step 5
- [ ] `learnings-researcher` is NOT exclusively standalone — wired into Step 2.5

### Taxonomy

- [ ] 14 problem_type categories (with `pipeline_issue` replacing `workflow_issue` + new `design_pattern`)
- [ ] 14 category directories created under `docs/solutions/`
- [ ] 16 component values (full LaunchPad stack replacement + `design_system`)
- [ ] 17 root_cause values (4 renames: `missing_association`→`missing_relation`, `missing_include`→`missing_eager_load`, `thread_violation`→`concurrency_issue`, `missing_workflow_step`→`missing_pipeline_step`; 13 kept as-is)
- [ ] 10 resolution_type values (1 rename: `pipeline_improvement`)
- [ ] 4 severity levels (critical, high, medium, low)
- [ ] No Rails/Ruby component values remain
- [ ] All enum values validated in YAML schema reference file

### Command Behavior

- [ ] 5 sub-agents run in parallel (not sequenced)
- [ ] Sub-agents return text only (command writes files)
- [ ] YAML validation is blocking gate (invalid frontmatter → do not write)
- [ ] Duplicate detection before writing (ask user: update existing or create new)
- [ ] Filename sanitized: lowercase, hyphens, no special chars, max 60 chars
- [ ] Secret/credential scan before writing (redact with [REDACTED] if found)
- [ ] Critical pattern promotion offered for severity: critical
- [ ] Auto-invocation on confirmation phrases ("that worked", "it's fixed")
- [ ] Existing `compound-product/` directory preserved (not overwritten)

### Agent Behavior

- [ ] 7-step search strategy with pre-filtering
- [ ] Read-only tools (Read, Grep, Glob — no Edit, Write, Bash)
- [ ] Frontmatter-only reads for candidates (first 30 lines)
- [ ] Always checks `docs/solutions/patterns/critical-patterns.md`
- [ ] Scores matches as strong/moderate/weak
- [ ] Returns max 5 results with distilled summaries
- [ ] Optimized for sub-30-second lookups
- [ ] Does NOT reference Rails, Ruby, ActiveRecord, or CE-specific patterns

### Skill Behavior

- [ ] 7-step documentation process
- [ ] YAML validation gate (step 5 — blocking)
- [ ] 14-category taxonomy with correct directory mapping (including `design_pattern` → `design-patterns/`)
- [ ] 16-component taxonomy with LaunchPad stack values (including `design_system`)
- [ ] Resolution template adapted (no Rails references)
- [ ] Critical pattern template included
- [ ] Cross-reference detection in step 7

### Prerequisites (from prior phases)

- [ ] Phase 0: `/harness:build` pipeline exists with Step 5
- [ ] Phase 0: `.claude/commands/harness/build.md` exists (created by Phase 0)
- [ ] Phase 0: `docs/solutions/compound-product/` directory exists
- [ ] Phase 3: `/harden-plan` Step 2.5 learnings scan exists (dormant → active)
- [ ] Phase 3: Step 2.5 cap (5 most-recent) and malformed frontmatter skip already specified

### Integration

- [ ] 14 category directories created with `.gitkeep`
- [ ] `docs/solutions/patterns/critical-patterns.md` created (empty template)
- [ ] `docs/solutions/README.md` updated to document both systems
- [ ] `init-project.sh` updated to scaffold 14 category directories
- [ ] `skills-index.md` updated with `compound-docs` skill
- [ ] `docs/solutions/` referenced in CLAUDE.md progressive disclosure table (one-time scaffolding check)
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                      |
| ------------ | --------------------------------------------------------- |
| Phase 7      | `/commit` workflow wiring                                 |
| Future       | `ce-compound-refresh` skill (updating existing learnings) |
| Future       | Track-based templates (bug-track vs knowledge-track)      |
| Phase Finale | Documentation refresh for all command tables              |
| Phase Finale | CE plugin removal                                         |

---

## File Change Summary

| #   | File                                                               | Change                                                                                                                    | Priority |
| --- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1   | `.claude/commands/learn.md`                                        | **Create** (adapted from CE — 5 inline sub-agents, YAML validation, secret scan)                                          | P0       |
| 2   | `.claude/skills/compound-docs/SKILL.md`                            | **Create** (heavy adaptation — 14 categories incl. design_pattern, 16 components incl. design_system, LaunchPad taxonomy) | P0       |
| 3   | `.claude/skills/compound-docs/references/yaml-schema.md`           | **Create** (adapted schema)                                                                                               | P0       |
| 4   | `.claude/skills/compound-docs/assets/resolution-template.md`       | **Create** (adapted template)                                                                                             | P0       |
| 5   | `.claude/skills/compound-docs/assets/critical-pattern-template.md` | **Create** (near-direct port)                                                                                             | P0       |
| 6   | `.claude/agents/research/learnings-researcher.md`                  | **Create** (light adaptation — read-only, 7-step search)                                                                  | P0       |
| 7   | `.claude/commands/harness/build.md`                                | **Edit** (created by Phase 0) — replace compound-learning.sh with /learn in Step 5                                        | P0       |
| 8   | `.claude/commands/harden-plan.md`                                  | **Edit** — remove "dormant" from Step 2.5, specify learnings-researcher dispatch                                          | P0       |
| 9   | `docs/reports/2026-03-30-meta-orchestrators-design.md`             | **Edit** — update Step 5 (Learn) and Step 2.5 "dormant" note                                                              | P1       |
| 10  | `docs/solutions/`                                                  | **Create** — 14 category directories (incl. `design-patterns/`) with `.gitkeep` + `patterns/critical-patterns.md`         | P1       |
| 11  | `docs/solutions/README.md`                                         | **Edit** — document both compound learning and compound product systems                                                   | P1       |
| 12  | `scripts/setup/init-project.sh`                                    | **Deferred to Phase Finale** — see Phase 0 deferral note                                                                  | P1       |
| 13  | `docs/skills-catalog/skills-index.md`                              | **Edit** — add compound-docs skill                                                                                        | P1       |
