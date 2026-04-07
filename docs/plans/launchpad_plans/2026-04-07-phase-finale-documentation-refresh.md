# Phase Finale: Documentation Refresh & Init Reconciliation

**Date:** 2026-04-07
**Updated:** 2026-04-07 (v2.1 — cross-phase sync: 7 keys (not 6), 6 namespaces (not 5, added skills/), ~35 agents; v2 — sync with Phase 0 v9 confidence rubric/headless, Phase 1 v7 testing-reviewer, Phase 3 v7 document-review agents)
**Prerequisite for:** None — final phase
**Depends on:** All phases (0-11) fully implemented
**Branch:** `chore/phase-finale`
**Status:** Plan

---

## Summary

Phase Finale runs AFTER all Phases 0-11 are implemented. It reconciles documentation and scaffolding with the actual implemented state. Three workstreams:

1. **`init-project.sh` Comprehensive Update** — accumulate all structural changes from Phases 0-11 into one tested script
2. **Full Documentation Rewrite** — 5 files that need complete rewrites to reflect the new pipeline
3. **Section Updates** — 11 files that need targeted edits
4. **CE Plugin Removal** — remove dependency on compound-engineering plugin

| Workstream        | Files | Effort     |
| ----------------- | ----- | ---------- |
| init-project.sh   | 1     | Medium     |
| Full rewrites     | 5     | High       |
| Section updates   | 10    | Medium     |
| CE plugin removal | TBD   | Low-Medium |
| **Total**         | ~17+  |            |

---

## Workstream 1: `init-project.sh` Comprehensive Update

**File:** `scripts/setup/init-project.sh`

Accumulates all structural changes from Phases 0-11. Rather than per-phase incremental patches, one comprehensive update ensures the script is tested end-to-end.

### What the Script Must Create

```
.harness/
├── todos/                    # [Phase 0] CLI todo storage
├── observations/             # [Phase 0] Review agent observations
├── design-artifacts/         # [Phase 10] Approved design screenshots
├── screenshots/              # [Phase 5] Browser test screenshots
├── harness.local.md          # [Phase 0] Project-specific context
└── .gitkeep                  # structure-drift.md is generated at runtime by detect-structure-drift.sh, not by init

.launchpad/
├── agents.yml                # [Phase 0] Agent dispatch configuration
│   Keys: review_agents, review_db_agents, review_design_agents,
│          review_copy_agents, harden_plan_agents, harden_plan_conditional_agents,
│          harden_document_agents
├── init-touched-files        # [existing] Files to track for pull-launchpad
└── ...existing files...

.claude/
├── agents/
│   ├── research/             # [Phase 0] file-locator, code-analyzer, pattern-finder, docs-locator, docs-analyzer, web-researcher
│   ├── review/               # [Phase 1] security-auditor, kieran-foad-ts-reviewer, performance-auditor, testing-reviewer, etc.
│   ├── document-review/      # [Phase 3] adversarial-document-reviewer, coherence-reviewer, feasibility-reviewer, scope-guardian-reviewer, product-lens-reviewer, security-lens-reviewer, design-lens-reviewer
│   ├── resolve/              # [Phase 4] pr-comment-resolver, harness-todo-resolver
│   └── design/               # [Phase 10] figma-design-sync, design-implementation-reviewer, design-iterator, etc.
└── ...existing skills/commands...
```

### What the Script Must Update

- `auto-compound.sh` references → `build.sh` + `compound-learning.sh` [Phase 0/6]
- Add `.harness/harness.local.md` to `.launchpad/init-touched-files`
- Add `.launchpad/agents.yml` to `.launchpad/init-touched-files`

### Verification

- [ ] Fresh downstream project created with `init-project.sh`
- [ ] All `.harness/` subdirectories exist
- [ ] `harness.local.md` created with `{{PROJECT_NAME}}` placeholder
- [ ] `agents.yml` created with all 7 keys (empty arrays)
- [ ] All `.claude/agents/` namespace subdirectories created
- [ ] `.launchpad/init-touched-files` includes harness.local.md and agents.yml
- [ ] No stale `auto-compound.sh` references remain

---

## Workstream 2: Full Documentation Rewrites

These files are so heavily affected by Phases 0-11 that targeted edits would be more error-prone than rewriting from the implemented state.

### 2.1 `CLAUDE.md`

**What changes:**

- **Available Sub-Agents table:** 7 agents → ~35 agents across 6 namespaces (research/, review/, document-review/, resolve/, design/, skills/). Agent renames: codebase-locator → file-locator, codebase-analyzer → code-analyzer, codebase-pattern-finder → pattern-finder, web-search-researcher → web-researcher. New categories: 7 document-review agents [Phase 3], testing-reviewer [Phase 1]
- **Full command inventory:** /review, /ship, /harness:kickoff, /harness:define, /harness:plan, /harness:build, /brainstorm, /harden-plan, /pnf, /inf, /triage, /defer, /regenerate-backlog, /commit, /Hydrate, /shape-section, /define-product, /define-design, /define-architecture, /design-review, /design-polish, /design-onboard, /copy, /copy-review, /feature-video, /learn, /test-browser, /resolve-pr-comments, /resolve_todo_parallel
- **Codebase map:** Add `.harness/` directory tree
- **Progressive disclosure table:** Add harness.local.md, agents.yml, BACKLOG.md
- **Status contract:** Add `defined → shaped → designed/"design:skipped" → planned → hardened → approved → reviewed → built`
- **TODO.md → BACKLOG.md** reference updates

**Approach:** Rewrite from implemented code state. Read the actual agent files, command files, and directory structure to produce an accurate CLAUDE.md.

### 2.2 `AGENTS.md`

Mirror of CLAUDE.md for non-Claude AI tools. Rewrite to match CLAUDE.md changes.

### 2.3 `docs/guides/HOW_IT_WORKS.md`

**What changes:**

- **4 meta-orchestrators:** /harness:kickoff, /harness:define, /harness:plan, /harness:build
- **Tier rewrite:** Tier 2 now includes /brainstorm before /pnf, design step before planning
- **New commands throughout:** All Phase 0-11 commands wired into workflow descriptions
- **Status contract flow** with design step
- **New sections:** /review workflow, /ship workflow, /commit vs /ship distinction

**Approach:** Rewrite from the implemented meta-orchestrator commands and pipeline flow.

### 2.4 `docs/guides/METHODOLOGY.md`

**What changes:**

- **Layer 1 (Scaffold):** .harness/ directory, detect-structure-drift.sh
- **Layer 3 (Execution):** Meta-orchestrators, build.sh/compound-learning.sh split
- **Layer 4 (Quality):** Review agent fleet, DB agents, design agents, copy review
- **Layer 5 (Commit-to-Merge):** /ship vs /commit, /triage, CI gates
- **Layer 6 (Learning):** compound-learning.sh, 14 categories, 16 components
- **Mermaid diagrams:** All need updating for new pipeline flow

**Approach:** Rewrite from implemented scripts and commands.

### 2.5 `docs/skills-catalog/skills-index.md`

**What changes:**

- **From 5 to ~15+ skills:** brainstorming, document-review, frontend-design, web-design-guidelines, responsive-design, rclone, imgup, stripe-best-practices, react-best-practices (plus existing prd, tasks, commit, creating-skills, creating-agents)
- **Relationship map:** Expanded for design workflow, copy skill loading, conditional skill wiring
- **Wiring documentation:** Which commands/agents load which skills

**Approach:** Rewrite from the actual `.claude/skills/` directory contents.

---

## Workstream 3: Section Updates

These files need targeted edits, not full rewrites.

### 3.1 `README.md`

- Commands table: add all new commands from Phases 0-11
- Project structure tree: add `.harness/` directory
- Canonical files table: add harness.local.md, agents.yml, BACKLOG.md
- CE Plugin section: update or remove if capabilities are now native

### 3.2 `docs/architecture/REPOSITORY_STRUCTURE.md`

- Root whitelist: add `.harness/`, `.launchpad/agents.yml`, `.worktreeinclude` [Phase 9]
- Directory tree: add `.harness/` subtree, `.claude/agents/` subdirectories, `scripts/maintenance/` [Phase 8.5]
- Section 5 docs table: add handoffs/, guides/ entries
- Section 6 decision tree: update for agent namespaces
- TODO.md → BACKLOG.md

### 3.3 `docs/skills-catalog/CATALOG.md`

- Mark ported skills as "already included": frontend-design, web-design-guidelines, stripe-best-practices, react-best-practices

### 3.4 `docs/skills-catalog/README.md`

- Update harness skills list (now much larger)

### 3.5 `docs/README.md`

- Add missing directory entries: handoffs/, guides/

### 3.6 `.claude/settings.json`

- Add SessionStart hook (hydrate.sh) [Phase 8]
- Verify existing hooks still correct

### 3.7 `scripts/compound/iteration-claude.md`

- Update path references (auto-compound.sh → build.sh)
- Add skill loading instructions for Phase 11 (stripe/react-best-practices)

### 3.8 `docs/solutions/compound-product/README.md`

- Update script name references (auto-compound.sh → build.sh + compound-learning.sh)

### 3.9 `.github/codex-review-prompt.md`

- Update repo-specific rules for .harness/ directory
- TODO → BACKLOG reference

### 3.10 `README.template.md`

- Mirror README.md changes relevant to downstream projects

### 3.11 `docs/tasks/TODO.md` → `docs/tasks/BACKLOG.md` (Verify Only)

- Verify rename completed in Phase 8 — no action needed unless Phase 8 was skipped

---

## Workstream 4: CE Plugin Removal

Remove the compound-engineering plugin dependency from both repos. After Phases 0-11, all CE capabilities are native.

- Remove CE plugin from `.claude/settings.json` MCP servers (if present)
- Remove any `compound-engineering:` prefixed command/skill references that have been replaced by native equivalents
- Verify no remaining imports or references to the plugin

---

## Execution Order

The rewrites cascade — each file references others, so order matters:

| Step  | File                                                  | Why First                                   |
| ----- | ----------------------------------------------------- | ------------------------------------------- |
| 1     | `CLAUDE.md`                                           | Canonical source — everything references it |
| 2     | `AGENTS.md`                                           | Mirror of CLAUDE.md                         |
| 3     | `REPOSITORY_STRUCTURE.md`                             | Defines where everything lives              |
| 4     | `METHODOLOGY.md`                                      | Defines the architecture                    |
| 5     | `HOW_IT_WORKS.md`                                     | Defines the workflow                        |
| 6     | `README.md` + `README.template.md`                    | Summarizes everything above                 |
| 7     | `skills-index.md` + `CATALOG.md` + skills `README.md` | Catalogs all skills                         |
| 8     | `.claude/settings.json`                               | Hooks config                                |
| ~~9~~ | ~~Agent file renames + moves~~                        | Done by Phase 0, not Phase Finale           |
| 10    | `iteration-claude.md` + compound README               | Script references                           |
| 11    | `codex-review-prompt.md`                              | External review config                      |
| 12    | `docs/README.md`                                      | Directory index                             |
| 13    | `TODO.md` → `BACKLOG.md` rename                       | File rename                                 |
| 14    | `init-project.sh`                                     | Must be last — validates cumulative state   |
| 15    | CE plugin removal                                     | Cleanup after everything is native          |

---

## Verification

### init-project.sh

- [ ] Fresh downstream project passes structure validation
- [ ] All `.harness/` subdirectories created
- [ ] `agents.yml` has all 7 keys (review_agents, review_db_agents, review_design_agents, review_copy_agents, harden_plan_agents, harden_plan_conditional_agents, harden_document_agents)
- [ ] No stale script references

### Documentation

- [ ] CLAUDE.md agent table matches actual `.claude/agents/` contents (6 namespaces: research/, review/, document-review/, resolve/, design/, skills/)
- [ ] CLAUDE.md agent table includes testing-reviewer [Phase 1] and 7 document-review agents [Phase 3]
- [ ] CLAUDE.md command list matches actual `.claude/commands/` contents
- [ ] CLAUDE.md documents `/review` confidence rubric (0.60 threshold) and `--headless` mode [Phase 0]
- [ ] AGENTS.md mirrors CLAUDE.md (non-Claude tools version)
- [ ] HOW_IT_WORKS.md references only commands that exist
- [ ] HOW_IT_WORKS.md documents confidence rubric and headless mode in /review section
- [ ] HOW_IT_WORKS.md documents /harden-plan document-review agents (Step 3.5) and interactive deepening (Step 3.7)
- [ ] METHODOLOGY.md layer descriptions match implemented components
- [ ] REPOSITORY_STRUCTURE.md tree matches actual directory structure (includes document-review/ namespace)
- [ ] skills-index.md lists every skill in `.claude/skills/`
- [ ] README.md commands table matches implemented commands
- [ ] No references to TODO.md (replaced by BACKLOG.md)
- [ ] No references to auto-compound.sh (replaced by build.sh)
- [ ] No references to old agent names (codebase-locator, etc.)

### Phase 8.5 (Structure Drift Detection)

- [ ] `scripts/maintenance/detect-structure-drift.sh` exists and is executable
- [ ] `hydrate.sh` calls `detect-structure-drift.sh` before output
- [ ] REPOSITORY_STRUCTURE.md documents `scripts/maintenance/` directory
- [ ] `.harness/structure-drift.md` is NOT created by init (runtime-generated only)

### CE Plugin

- [ ] No compound-engineering MCP server in settings.json
- [ ] No `compound-engineering:` prefixed references in active commands
- [ ] All ported capabilities verified working natively

---

## File Change Summary

| #     | File                                        | Action                                                     | Priority |
| ----- | ------------------------------------------- | ---------------------------------------------------------- | -------- |
| 1     | `CLAUDE.md`                                 | **Full rewrite**                                           | P0       |
| 2     | `AGENTS.md`                                 | **Full rewrite**                                           | P0       |
| 3     | `docs/guides/HOW_IT_WORKS.md`               | **Full rewrite**                                           | P0       |
| 4     | `docs/guides/METHODOLOGY.md`                | **Full rewrite**                                           | P0       |
| 5     | `docs/skills-catalog/skills-index.md`       | **Full rewrite**                                           | P0       |
| ~~6~~ | ~~`.claude/agents/*.md` (7 files)~~         | ~~Rename + move~~ — Done by Phase 0, not Phase Finale      | N/A      |
| 7     | `README.md`                                 | **Section updates** — commands, structure, canonical files | P1       |
| 8     | `docs/architecture/REPOSITORY_STRUCTURE.md` | **Section updates** — .harness/, namespaces, BACKLOG       | P1       |
| 9     | `docs/skills-catalog/CATALOG.md`            | **Section updates** — mark ported skills                   | P1       |
| 10    | `docs/skills-catalog/README.md`             | **Section updates** — harness skills list                  | P1       |
| 11    | `docs/README.md`                            | **Section updates** — missing directories                  | P1       |
| 12    | `.claude/settings.json`                     | **Section updates** — new hooks                            | P1       |
| 13    | `scripts/compound/iteration-claude.md`      | **Section updates** — paths, skill loading                 | P1       |
| 14    | `docs/solutions/compound-product/README.md` | **Section updates** — script names                         | P2       |
| 15    | `.github/codex-review-prompt.md`            | **Section updates** — rules, TODO→BACKLOG                  | P2       |
| 16    | `README.template.md`                        | **Section updates** — downstream template                  | P2       |
| 17    | `docs/tasks/TODO.md`                        | **Verify** rename to `BACKLOG.md` completed in Phase 8     | P2       |
| 18    | `scripts/setup/init-project.sh`             | **Comprehensive update** — all Phase 0-11 structures       | P0       |
| 19    | `.claude/settings.json` (CE removal)        | **Edit** — remove CE plugin MCP server                     | P1       |
