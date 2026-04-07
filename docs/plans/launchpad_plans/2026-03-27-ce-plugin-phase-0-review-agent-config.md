# Phase 0: Review Agent Configuration & Pipeline Restructure

**Date:** 2026-03-27
**Updated:** 2026-04-07 (v9 — CE v2.61.0 impact: confidence rubric, headless review mode, intent verification added to `/review`; v8 — Phase 12 eliminated, feature-video/rclone/imgup moved to Phase 10, Phase 11 scope updated with stripe/react-best-practices; v7 — Phase 10 cascading changes: status reorder, step reorder, design-artifacts dir, review_copy_agents, timeout removal, Phase 10/11 scope updates; v6 final — reviewer fixes)
**Prerequisite for:** Phase 1 (Review Agent Fleet)
**Branch:** `feat/review-agent-config`
**Status:** Plan — v9.1 (cross-phase sync: headless caller list corrected, init-project.sh key list updated to 7, YAML keys decision table updated)
**Design:** [Meta-Orchestrator Design v4](../reports/2026-03-30-meta-orchestrators-design.md)

---

## Decisions (All Finalized)

| Decision                 | Answer                                                                                                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Agent config file        | `.launchpad/agents.yml` (upstream-synced, agent names only)                                                                                                                                |
| Project context file     | `.harness/harness.local.md` (project-specific, excluded from sync)                                                                                                                         |
| Config format            | YAML for agent lists, markdown for project context                                                                                                                                         |
| YAML keys                | `review_agents`, `review_db_agents`, `review_design_agents`, `review_copy_agents`, `harden_plan_agents`, `harden_plan_conditional_agents`, `harden_document_agents`                        |
| Review command           | `/review` → `.claude/commands/review.md` (flat, replaces `review_code.md`)                                                                                                                 |
| Ship command             | `/ship` → `.claude/commands/ship.md` (autonomous shipping, uses `git add -u` not `git add -A`)                                                                                             |
| Ship vs Commit           | `/ship` = autonomous (pipeline). `/commit` = interactive (manual). Both coexist until Phase 7.                                                                                             |
| Meta-orchestrators       | `/harness:kickoff`, `/harness:define`, `/harness:plan`, `/harness:build` (4 orchestrators in `harness/` namespace)                                                                         |
| Build script             | `build.sh` (from `auto-compound.sh` Steps 1-7a)                                                                                                                                            |
| Learning script          | `compound-learning.sh` (from `auto-compound.sh` Step 8)                                                                                                                                    |
| Shared functions         | `lib.sh` — extracted `ai_run`, scoped env loading, config reading                                                                                                                          |
| Todo directory           | `.harness/todos/` (git-tracked)                                                                                                                                                            |
| Todo file pattern        | `{id}-{description}.md` (status/priority in YAML frontmatter only)                                                                                                                         |
| Resolver agent           | `harness-todo-resolver` (in `resolve/` namespace)                                                                                                                                          |
| Resolve command          | `/resolve_todo_parallel` (flat)                                                                                                                                                            |
| Agent namespaces         | 6 subdirs: `research/`, `review/`, `resolve/`, `design/`, `document-review/`, `skills/`                                                                                                    |
| Agent renames            | `codebase-locator`→`file-locator`, `codebase-analyzer`→`code-analyzer`, `codebase-pattern-finder`→`pattern-finder`, `web-search-researcher`→`web-researcher`                               |
| Agent model              | `model: inherit` for all agents across all phases (model-agnostic)                                                                                                                         |
| Agent resolution         | `/review` scans all `.claude/agents/` subdirectories for `{name}.md`. First match wins.                                                                                                    |
| CE plugin coexistence    | CE plugin stays installed through all phases. Local commands take precedence. Plugin removed at Phase Finale.                                                                              |
| Harden-plan in Phase 0   | Passthrough — only `pattern-finder` exists. Full hardening activates as Phase 1-3 agents are created.                                                                                      |
| Namespace rule           | `harness:*` = meta-orchestrators only. Everything else is flat.                                                                                                                            |
| Merge prevention         | 3-layer: command prohibition + PreToolUse hook + GitHub branch protection                                                                                                                  |
| Old `review_code.md`     | Deleted after migration                                                                                                                                                                    |
| Old `auto-compound.sh`   | Renamed to `.deprecated` until Phase 1 verified                                                                                                                                            |
| Review confidence rubric | 6-tier scoring (0.00-1.00), 0.60 suppression threshold, 6 FP categories, multi-agent agreement boost (+0.10). Applied in `/review` Step 5 synthesis. CE v2.60.0 reports ~49% FP reduction. |
| Review headless mode     | `/review --headless` suppresses interactive output, skips report, returns structured findings. Enables programmatic invocation by `/harden-plan` (Phase 3), `/commit` Step 2.5 (Phase 7).  |
| Intent verification      | `/review` Step 5 reads PR context (title, body, linked issue via `gh pr view`) and suppresses findings that contradict stated intent. Only active when a PR exists for current branch.     |

---

## Pipeline Overview

```
/harness:kickoff → /harness:define → /harness:plan → /harness:build → /harness:plan → /harness:build → ...
  (brainstorm)    (define + shape)   (interactive)    (autonomous)     (section 2)     (section 2)
```

**Phase 0 builds the right half:** `/harness:plan` orchestrates the interactive planning pipeline (design → pnf → harden → approval), and `/harness:build` orchestrates the autonomous execution pipeline (inf → review → fix → test → ship → learn). The left half (kickoff + define) already exists as individual commands; Phase 0 wraps them in orchestrators.

### How This Maps to CE

```
CE /lfg:                           Our Pipeline:
  /workflows:plan                    /pnf (already exists)         → /harness:plan
  /deepen-plan                       /harden-plan (Phase 3 agents, → /harness:plan
                                       but command created here)
  /workflows:work               →    /inf (build.sh — build only)  → /harness:build
  /workflows:review              →    /review (diagnose → todos)    → /harness:build
  /resolve_todo_parallel         →    /resolve_todo_parallel (fix)  → /harness:build
                                      /ship (quality gates + commit → /harness:build
                                        + push + PR + monitor)
                                      compound-learning.sh          → /harness:build
                                        (extract learnings)
```

---

## Purpose

1. Create a two-file config system: `.launchpad/agents.yml` (agent list, synced) + `.harness/harness.local.md` (project context, local)
2. Split `auto-compound.sh` into `build.sh` + `compound-learning.sh` + shared `lib.sh`
3. Create `/review` command with multi-agent parallel dispatch, secret scanning, confidence rubric (0.60 threshold, ~49% FP reduction), intent verification, and headless mode for programmatic callers
4. Create `/ship` command for autonomous shipping (quality gates + commit + PR + monitoring, never merges)
5. Create `harness-todo-resolver` agent and `/resolve_todo_parallel` command
6. Create 4 meta-orchestrators: `/harness:kickoff`, `/harness:define`, `/harness:plan`, `/harness:build`
7. Create `/harden-plan` command (infrastructure only — agents added in Phases 1-3)
8. Keep `/inf` as build-only with explicit-path mode for orchestrator use
9. Establish `.harness/` as the runtime directory for harness artifacts
10. Namespace all agents into subdirectories and rename for clarity
11. Add merge prevention hook to `.claude/settings.json`

---

## Section Registry Status Contract

| #   | Status             | Meaning                  | Written By             | Orchestrator      | Triggers (Next Command) | Boundary?               |
| --- | ------------------ | ------------------------ | ---------------------- | ----------------- | ----------------------- | ----------------------- |
| 1   | `defined`          | In PRD registry, no spec | `/define-product`      | `/harness:define` | `/shape-section`        | No — internal to define |
| 2   | `shaped`           | Section spec exists      | `/shape-section`       | `/harness:define` | `/pnf`                  | **YES — define → plan** |
| 3a  | `designed`         | UI work done             | design step [Phase 10] | `/harness:plan`   | `/pnf`                  | No — internal to plan   |
| 3b  | `"design:skipped"` | No UI in scope           | design step [Phase 10] | `/harness:plan`   | `/pnf`                  | No — internal to plan   |
| 4   | `planned`          | Plan exists              | `/pnf`                 | `/harness:plan`   | `/harden-plan`          | No — internal to plan   |
| 5   | `hardened`         | Plan stress-tested       | `/harden-plan`         | `/harness:plan`   | approve plan            | No — internal to plan   |
| 6   | `approved`         | Human approved plan      | human approval gate    | `/harness:plan`   | `/inf`                  | **YES — plan → build**  |

`approved` attestation: When `/harness:plan` writes `approved`, it MUST also write `approved_at: <ISO-8601 timestamp>` and `plan_hash: <short hash of plan file>`. `/harness:build` guard validates BOTH `status: approved` AND `approved_at` are present. Bare `approved` without attestation → refuse with "Plan approval metadata missing. Re-run /harness:plan for human approval."

| 7 | `reviewed` | Code reviewed + browser tested | `/test-browser` (or `/review` if `/test-browser` skipped) | `/harness:build` | `/ship` | No — internal to build |
| 8 | `built` | Shipped via PR | Report step | `/harness:build` | (done) | — |

**Cross-orchestrator boundaries:** `shaped` (define → plan), `approved` (plan → build).

**Downstream use:** `/review` reads section status. If `designed` → dispatch `review_design_agents`. If `"design:skipped"` → skip design review agents. [Phase 10 overrides this to artifact-based dispatch: IF `.harness/design-artifacts/[section]-approved.png` exists. See Phase 10 plan.]

**Quoting rule:** Always quote `"design:skipped"` in YAML frontmatter to avoid colon ambiguity. Write `status: "design:skipped"`, not `status: design:skipped`.

### State Machine Diagram

```
defined → shaped → designed/"design:skipped" → planned → hardened → approved → reviewed → built
                     ↑                                                              |
                     |                        (revise)                              |
                     └──────────────────────────────────────────────────────────────┘
                  resets to "shaped"
             (re-enters design → plan → harden → approval)
```

Valid transitions are forward-only. The one backward transition occurs via "revise" in the approval gate, which resets status to `shaped` and re-enters the design → plan → harden → approval cycle.

### Section Registry Format

- **Format:** YAML frontmatter in each section spec file (e.g., `docs/tasks/sections/{section-name}.md`), with a `status` field
- **Read API:** Grep for `^status:` in the section spec file
- **Write API:** Edit tool to update the `status:` line in frontmatter
- **Additional fields:** `approved_at` (ISO-8601 timestamp), `plan_hash` (short hash) — written when status is `approved`
- **Error handling:** If section spec file not found or `status:` line missing, treat as `defined`

### Registry Integrity Validation

Both `/harness:plan` and `/harness:build` validate expected artifacts exist for current status before proceeding:

| Status     | Expected Artifacts                                                                         |
| ---------- | ------------------------------------------------------------------------------------------ |
| `designed` | Design artifacts in `.harness/design-artifacts/` (or `"design:skipped"` with no artifacts) |
| `planned`  | Plan file exists                                                                           |
| `hardened` | Hardening notes section exists in plan                                                     |
| `approved` | `approved_at` field present + plan file exists                                             |
| `reviewed` | `.harness/review-summary.md` exists                                                        |

Refuse with descriptive error if inconsistent (e.g., "Status is 'approved' but approved_at field missing. Re-run /harness:plan for human approval.").

---

## Architecture: How `/harness:plan` Works After Phase 0

```
/harness:plan [target]
  │
  ├── Guard: Status Check
  │     ├── "approved"+ → REFUSE: "Already approved. Run /harness:build"
  │     ├── Validate registry integrity (see Registry Integrity Validation)
  │     └── Otherwise → proceed
  │
  ├── Step 1: Resolve Target
  │     ├── CASE A: Named target or no argument → registry lookup
  │     │     ├── "hardened" → Step 5 (approval)
  │     │     ├── "planned" → Step 4 (harden)
  │     │     ├── "designed"/"design:skipped" → Step 3 (plan)
  │     │     ├── "shaped" → Step 2 (design)
  │     │     ├── "defined"/none → "Not shaped. Run /harness:define"
  │     │     └── Nothing → ask what to plan (CASE B)
  │     └── CASE B: Free-text → Step 2
  │
  ├── Step 2: Design Step [Phase 10]
  │     ├── IF section has UI components:
  │     │     ├── Dispatch design workflow (agents defined in Phase 10)
  │     │     └── Registry status → "designed"
  │     └── ELSE:
  │           └── Registry status → "design:skipped"
  │
  ├── Step 3: /pnf [target]
  │     └── Produces plan → registry status → "planned"
  │
  ├── Step 4: /harden-plan [plan-path] --auto
  │     ├── Section: --full (8 agents when available)
  │     ├── Feature: --lightweight (4 agents when available)
  │     ├── --auto: auto-apply findings
  │     ├── Idempotent: skips if "## Hardening Notes" exists
  │     └── Registry status → "hardened"
  │
  └── Step 5: Human Approval Gate
        ├── Present plan summary (plan + hardening notes + design status)
        ├── Ask: "Approve this plan for build? (yes/no/revise)"
        ├── IF yes → registry status → "approved"
        │     ├── Write approved_at: <ISO-8601 timestamp>
        │     └── Write plan_hash: <short hash of plan file at approval time>
        ├── IF revise → return to relevant step (status reset to "shaped")
        └── IF no → exit with "Plan not approved"
```

## Architecture: How `/harness:build` Works After Phase 0

```
/harness:build [target]
  │
  ├── Guard: Status Check + Resolve Target
  │     ├── Non-"approved" and non-"reviewed" → REFUSE:
  │     │     "Plan approval metadata missing. Re-run /harness:plan for human approval."
  │     │     (if status = "approved" but approved_at missing)
  │     │     OR "Run /harness:plan first" (if not approved/reviewed)
  │     ├── Validate registry integrity (see Registry Integrity Validation)
  │     ├── CASE A: Named target → registry lookup
  │     │     ├── "reviewed" → Step 4 (ship)
  │     │     ├── "approved" (with approved_at) → Step 1 (inf)
  │     │     └── Any other status → "Run /harness:plan first"
  │     └── CASE B: No argument → find next "approved" section
  │
  ├── Step 1: /inf [explicit-plan-path]
  │     ├── Plan path comes from section's plan doc (identified by "approved" status)
  │     ├── Passes --plan flag → skips inf's own registry check
  │     └── Calls build.sh → execution loop → quality sweep
  │
  ├── Step 2: /review
  │     ├── Dispatch review agents from .launchpad/agents.yml (review_agents)
  │     ├── IF section status = "designed": also dispatch review_design_agents
  │     ├── IF section status = "design:skipped": skip review_design_agents
  │     ├── IF "design:skipped" but diff contains UI-relevant files (.tsx, .css,
  │     │     .html in apps/web/ or packages/ui/): emit P2 warning finding
  │     ├── Read PR intent context (title, body, linked issue) for scoring
  │     ├── Confidence scoring (0.60 threshold) → suppress FPs → deduplicate → P1/P2/P3
  │     ├── Write .harness/todos/ (findings above threshold only)
  │     ├── Write .harness/review-summary.md (includes suppressed findings for audit)
  │     └── IF zero findings above threshold: skip to Step 2.5
  │
  ├── Step 2.5: /resolve_todo_parallel
  │     ├── Group overlapping files → sequential
  │     ├── Max 5 concurrent resolver agents
  │     ├── Post-execution scope validation: verify modified files are within scope
  │     │     (files referenced in todo + 1-hop imports). Revert out-of-scope changes
  │     │     before committing. Mirror Phase 4's pr-comment-resolver Step 4 pattern.
  │     ├── Stage only reported files → commit "fix: resolve review findings"
  │     └── Commit is DURABLE (safe from crashes)
  │
  ├── Step 3: /test-browser [Phase 5]
  │     ├── Browser testing on pages affected by current PR
  │     └── Registry status → "reviewed" (code reviewed + browser tested)
  │     NOTE: If /test-browser is skipped or unavailable, /review writes "reviewed".
  │
  ├── Step 4: /ship
  │     ├── IF PR already exists for current branch: skip PR creation,
  │     │     proceed to monitoring (Gate A/B/C). Prevents double PR on recovery.
  │     ├── Stage remaining changes (git add -u, tracked files only)
  │     ├── Quality gates (test, typecheck, lint, lefthook)
  │     ├── Auto-fix cycle (max 3 attempts) if gates fail
  │     ├── Auto-generate conventional commit (second commit on branch)
  │     ├── Push → PR creation (idempotent — skips if PR exists)
  │     ├── PR monitoring (max 3 cycles): CI + Codex + conflicts
  │     └── STOPS at "all gates green" — NEVER merges
  │
  ├── Step 5: compound-learning.sh
  │     └── Extract learnings → docs/solutions/
  │
  └── Step 6: Report
        └── Registry status → "built" (if section)
```

### How `/harness:kickoff` Works

```
/harness:kickoff
  ├── Load brainstorming skill
  ├── Open-ended dialogue → docs/brainstorms/YYYY-MM-DD-[project].md
  └── "Run /harness:define to define your product."
```

### How `/harness:define` Works

```
/harness:define
  ├── Step 1: /define-product (fresh or update mode based on artifact existence)
  ├── Step 2: /define-design
  ├── Step 3: /define-architecture
  ├── Step 4: Shape sections (ask which, run /shape-section internally, cap 3 per session)
  └── "Run /harness:plan [section] to start planning."
```

### How `/inf` Works After Phase 0

```
/inf [--dry-run] [SECTION_SPEC_PATH]
/inf --plan path/to/plan.md          ← NEW: explicit plan path, skips registry
  ├── IF --plan flag provided: skip registry check, use plan directly
  ├── ELSE: section registry check (same as today)
  └── Run build.sh $ARGUMENTS [path]
```

---

## The Config Files

### `.launchpad/agents.yml` (upstream-synced)

```yaml
# Code review agents — dispatched by /review
review_agents:
  - pattern-finder

# DB agents — only when diff touches Prisma files
review_db_agents: []

# Design review agents — dispatched by /review when section status = "designed"
# Populated in Phase 10 when design agents are created
review_design_agents: [] # [Phase 10]

# Copy review agents — dispatched during design workflow
# Populated by downstream projects (e.g., BuiltForm adds copy-auditor in Phase 11)
review_copy_agents: [] # [Phase 10]

# Document-review agents — dispatched by /harden-plan Step 3.5 [Phase 3 v7]
harden_document_agents: []

# Protected branches — read by /ship, /commit, /resolve-pr-comments
protected_branches:
  - main
  - master
```

### Secret Scan Patterns

Secret scanning patterns stored in `.launchpad/secret-patterns.txt` (one pattern per line). All commands that perform secret scanning (`/review`, `/commit`, `/brainstorm`, `/learn`) read from this file.

### `.harness/` Gitignore Policy

Git-tracked (audit value):

- `.harness/todos/`
- `.harness/observations/`
- `.harness/design-artifacts/` (approved design screenshots)

Gitignored (ephemeral):

- `.harness/screenshots/*.png`
- `.harness/structure-drift.md`
- `.harness/review-summary.md` (includes suppressed findings audit trail — regenerated each `/review` run)

Specific `.gitignore` entries to add:

```gitignore
# .harness/ ephemeral artifacts
.harness/screenshots/*.png
.harness/structure-drift.md
.harness/review-summary.md
```

Use specific entries, not a directory-level blanket ignore.

### `.harness/harness.local.md` (project-specific)

```markdown
## Review Context

<!-- Enriched by /define-product and /define-architecture. -->

{{PROJECT_NAME}} — TypeScript monorepo (Next.js 15 + Hono + Prisma + PostgreSQL).
```

---

## Change Map

### P0 — Core Infrastructure (must ship together)

#### 1. Create `.harness/` directory structure

```
.harness/
├── todos/              # Review findings (populated by /review)
├── observations/       # Out-of-scope findings (populated starting Phase 1)
└── design-artifacts/   # Approved design screenshots (populated by Phase 10 design step)
```

- Add `.harness/todos/.gitkeep`, `.harness/observations/.gitkeep`, and `.harness/design-artifacts/.gitkeep`
- Document in `REPOSITORY_STRUCTURE.md`
- `init-project.sh` creates this structure

#### 2. Namespace and rename agents

Create 6 subdirectories under `.claude/agents/` and move/rename:

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
├── document-review/
│   └── .gitkeep                  (Phase 3 v7 document-review agents go here)
├── resolve/
│   └── harness-todo-resolver.md  (created in this phase)
├── design/
│   └── .gitkeep                  (Phase 10 agents go here)
└── skills/
    └── skill-evaluator.md        (moved, name unchanged)
```

**Files that need agent name updates (4 renames):**

| File                                                       | What to Update                                                                |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `.claude/commands/research_codebase.md`                    | All 4 renames                                                                 |
| `.claude/commands/pnf.md`                                  | Same 4 renames + verify `docs-locator`, `docs-analyzer` refs                  |
| `.claude/commands/implement_plan.md`                       | `codebase-pattern-finder`→`pattern-finder`                                    |
| `.claude/skills/creating-skills/SKILL.md`                  | All research agent references                                                 |
| `.claude/skills/creating-skills/references/METHODOLOGY.md` | Agent reference table                                                         |
| `CLAUDE.md`                                                | Sub-agents table                                                              |
| `AGENTS.md`                                                | Sub-agents table                                                              |
| `docs/guides/HOW_IT_WORKS.md`                              | Agent references                                                              |
| `.launchpad/METHODOLOGY.md`                                | Agent reference table                                                         |
| `.claude/skills/prd/SKILL.md`                              | `codebase-locator`→`file-locator`, `codebase-pattern-finder`→`pattern-finder` |
| `docs/skills-catalog/skills-index.md`                      | Old agent name references                                                     |
| `scripts/compound/loop.sh`                                 | `auto-compound.sh` reference in user-facing message                           |

Delete old flat agent files after confirming namespaced files work.

---

#### 3. Create `.launchpad/agents.yml`

Agent list config. Synced from upstream. Not in `init-touched-files`. Includes `protected_branches` list and `harden_plan_agents`/`harden_plan_conditional_agents` keys (populated in Phase 1).

#### 3b. Create `.launchpad/secret-patterns.txt`

Secret scanning patterns (one per line). Read by `/review`, `/commit`, `/brainstorm`, `/learn`. Synced from upstream.

#### 4. Create `.harness/harness.local.md`

Project context. `{{PROJECT_NAME}}` replaced by `init-project.sh`. Added to `.launchpad/init-touched-files`.

#### 5. Create `/review` command

**New file:** `.claude/commands/review.md` (flat, replaces `review_code.md`)

```
Usage:
  /review                    → interactive mode (default)
  /review --headless         → programmatic mode (no interactive output, no report)

Step 0: Read Configuration
  - Read .launchpad/agents.yml → extract review_agents, review_db_agents, review_design_agents, review_copy_agents
  - Validate each agent name: must match [a-z0-9-]+, must resolve to file in .claude/agents/
  - Skip with warning if file not found (handles [Phase N] agents gracefully)
  - Read .harness/harness.local.md → extract review_context
  - If agents.yml missing: fall back to pattern-finder only, warn user

Step 1: Determine Diff Scope
  - git diff --name-only origin/main...HEAD
  - Check for Prisma changes → db_changes = true/false

Step 1.5: Read PR Intent Context (best-effort)
  - IF a PR exists for current branch (gh pr view --json title,body,labels):
    Extract PR title, body, linked issue number/description
    Store as intent_context for Step 5 confidence scoring
  - IF no PR exists: intent_context = empty (scoring proceeds without it)
  - NEVER fail on this step — purely supplementary context

Step 2: Pre-dispatch Secret Scan (best-effort)
  - Read patterns from .launchpad/secret-patterns.txt (one pattern per line)
  - Scan only added lines (+ prefix) in diff for:
    API keys: sk-, rk_live_, ghp_, gho_, ghs_, AKIA
    Secrets: password\s*=, token\s*=, secret\s*=, client_secret
    Auth: Bearer\s+[A-Za-z0-9._\-]+
    PEM: -----BEGIN .* PRIVATE KEY-----
    Connection strings: ://[^@]+@[^/]+
    .env file additions
  - IF matches: HALT and warn user
  - Note: best-effort scan. For comprehensive detection, integrate gitleaks/trufflehog.

Step 3: Dispatch Review Agents (parallel, all model: inherit)
  - Each agent receives: diff + file list + review_context
  - Prompt: "Review this code diff for issues in your domain."

Step 4: Conditional DB Agents
  - IF db_changes AND review_db_agents not empty:
    Dispatch all review_db_agents in parallel

Step 4.5: Conditional Design Agents
  - Read section status from registry
  - IF status = "designed" AND review_design_agents not empty:
    Dispatch all review_design_agents in parallel [Phase 10]
    [Phase 10 overrides this to artifact-based dispatch: IF .harness/design-artifacts/[section]-approved.png exists. See Phase 10 plan.]
  - IF status = "design:skipped": skip design agents entirely
  - IF "design:skipped" but diff contains UI-relevant files (.tsx, .css, .html
    in apps/web/ or packages/ui/): emit P2 warning finding

Step 5: Confidence Scoring & Synthesis
  Runs AFTER all agents return findings, BEFORE writing to .harness/todos/.

  Step 5a: Collect raw findings from all agents

  Step 5b: Deduplicate — merge overlapping findings across agents
    - Same file:line + same concern → merge into single finding
    - Track which agents flagged each finding (for multi-agent boost)

  Step 5c: Confidence Scoring (per finding)
    Score each finding 0.00-1.00 using a 6-tier rubric:

    | Tier | Range | Meaning |
    |------|-------|---------|
    | Certain | 0.90-1.00 | Verified bug, security vulnerability with proof |
    | High | 0.75-0.89 | Strong evidence, clear code path to failure |
    | Moderate | 0.60-0.74 | Reasonable concern, would benefit from review |
    | Low | 0.40-0.59 | Possible issue, limited evidence |
    | Speculative | 0.20-0.39 | Theoretical concern, no concrete evidence |
    | Noise | 0.00-0.19 | Generic advice, style preference, not actionable |

    False-positive suppression — suppress (< 0.60) findings matching:
    1. Pre-existing issues: finding describes code unchanged in this diff
    2. Style nitpicks: formatting, naming preferences with no functional impact
    3. Intentional patterns: code follows a documented project convention
    4. Handled-elsewhere: concern is addressed in another file/layer
    5. Code restatement: finding just describes what the code does, not a problem
    6. Generic advice: "consider using X" without specific evidence of need

    Boosters:
    - Multi-agent agreement: 2+ agents flag same issue → +0.10
    - Security/data concern: finding involves auth, secrets, PII → +0.10
    - P1 floor: any finding classified P1 by agent → minimum 0.60 (never auto-suppressed)

    Intent verification (only when intent_context is available):
    - IF finding contradicts stated PR intent (e.g., PR says "remove feature X",
      finding says "feature X is missing") → suppress with note
    - IF finding aligns with PR intent → no change

  Step 5d: Filter — suppress findings below 0.60 threshold
    - Suppressed findings are NOT written to .harness/todos/
    - Suppressed findings ARE logged in .harness/review-summary.md under
      "## Suppressed Findings ({N})" with score and suppression reason
    - This provides audit trail without noise in the todo queue

  Step 5e: Prioritize remaining findings → P1/P2/P3

Step 6: Write Outputs
  - Clear .harness/todos/ (idempotent on retry)
  - For EACH finding (above 0.60 threshold):
    .harness/todos/{id}-{description}.md
    YAML: status (pending), priority, agent_source, confidence (0.00-1.00)
    Body: Problem, Findings (file:line), Proposed Solution
  - Write .harness/review-summary.md
    Sections: ## Findings ({N}), ## Suppressed Findings ({M}), ## Stats
    Stats: total raw findings, suppressed count, suppression rate, agent agreement count
  - IF zero findings above threshold: write "Clean review" to summary, report, exit

Step 7: Report (SKIPPED in --headless mode)
  - "{N} findings ({P1} critical, {P2} important, {P3} nice-to-have)"
  - "{M} findings suppressed (below 0.60 confidence threshold)"
  - IF --headless: skip this step entirely. Callers read .harness/todos/ and
    .harness/review-summary.md directly for structured results.
```

**Headless Mode Contract:**
When invoked with `--headless`, `/review` behaves identically through Steps 0-6 but:

- Suppresses all interactive output (no progress messages, no user prompts)
- Skips Step 7 (Report)
- Returns silently — callers read `.harness/todos/` and `.harness/review-summary.md`
- Used by: `/harden-plan` [Phase 3], `/commit` Step 2.5 [Phase 7]
- NOT used by: `/harness:build` (uses normal interactive mode for visibility)

#### 6. Create `/ship` command

**New file:** `.claude/commands/ship.md` (flat, autonomous shipping)

```
Step 1: Branch Guard
  - Read protected_branches from .launchpad/agents.yml (default: [main, master])
  - IF current branch is in protected_branches: REFUSE. "Cannot ship to protected branch."

Step 2: Stage Changes
  - git add -u (stages modifications + deletions of tracked files only)
  - Does NOT add untracked files (no .env.local, no debug artifacts, no stray files)
  - This is safer than git add -A while remaining autonomous

Step 3: Quality Gates (parallel) + Auto-Fix Cycle
  - Agent A: pnpm test && pnpm typecheck && pnpm lint
  - Agent B: lefthook run pre-commit (includes check-repo-structure.sh)
  - IF all pass → proceed to Step 4
  - IF any fail → AUTO-FIX (max 3 attempts):
    1. Read error output, diagnose root cause
    2. Fix the code
    3. Stage fix (git add -u)
    4. Re-run ALL quality gates from scratch
    5. IF pass → proceed to Step 4
    6. IF still failing after 3 attempts → HARD STOP. Report what failed.
  - NEVER use --no-verify
  - ~90-95% of builds ship autonomously; ~5-10% need human intervention

Step 4: Generate Commit Message
  - Auto-generate conventional commit: type(scope): description
  - Include Co-Authored-By: Claude <noreply@anthropic.com>
  - No user approval (autonomous)

Step 5: Commit + Push + PR
  - git commit (HEREDOC format)
  - git push -u origin HEAD
  - IF PR already exists for current branch: skip PR creation, proceed to Step 6 monitoring.
    This prevents double PR creation on recovery after /learn failure.
  - gh pr create with structured body:
    ## Summary (from commit)
    ## Review Findings (from .harness/review-summary.md if exists)
    ## Test Plan (gate results)

Step 6: PR Monitoring Loop (max 3 cycles)
  Gate A: CI Checks
    - Poll gh pr checks (30s intervals, max 10 waits)
    - IF failed: read logs, diagnose, fix, re-run Step 3, push, restart loop

  Gate B: Codex Review (non-blocking on timeout)
    - Poll for Codex comment (max 5 min)
    - IF no comment: pass
    - IF comment: parse findings, evaluate each (AGREE/DISAGREE)
    - Auto-fix AGREE items only. Max 3 fix rounds, then stop.
    - Apply Phase 4's sensitive file denylist and security-weakening detection
      to Codex auto-fix. If Codex suggestion targets auth/middleware/security
      paths → report "Needs manual review" instead of auto-fixing.
    - Skip human review gate (autonomous)

  Gate C: Conflicts
    - IF not mergeable: rebase, resolve, re-run gates, force-with-lease push
    - Before --force-with-lease: check if remote branch has commits not in
      local (git log HEAD..origin/branch). If diverged, abort:
      "Remote has commits not in local. Manual resolution required."

  Loop Exit: all gates green on same cycle → exit

Step 7: Report (TERMINAL)
  - Print PR URL
  - Print gate status
  - "PR is ready for human review and merge."
  - EXIT. NEVER merge. NEVER suggest merging. NEVER offer to merge.

Rules:
  1. NEVER run gh pr merge
  2. NEVER run git merge main/master
  3. NEVER auto-merge
  4. NEVER skip quality gates
  5. NEVER use --no-verify
```

#### 7. Create `harness-todo-resolver` agent

**New file:** `.claude/agents/resolve/harness-todo-resolver.md`

**Frontmatter:** `model: inherit`

Reads a single todo, finds relevant code, implements the fix, returns files changed list.

**Tool permissions:** Read, Edit, Write, Grep, Glob, Bash (for `pnpm test`/`pnpm typecheck` only). Deny: `gh` commands, network access beyond localhost.

Constraints:

- Fix ONLY the described issue — no scope creep
- Return: **list of files changed**, what was fixed, any concerns

#### 8. Create `/resolve_todo_parallel` command

**New file:** `.claude/commands/resolve_todo_parallel.md`

```
Step 1: Read pending todos (.harness/todos/ where YAML status: pending)
        IF none: "0 findings to resolve" → exit

Step 2: Parse file:line refs → group overlapping files → sequential within group

Step 3: Spawn harness-todo-resolver agents (max 5 concurrent)

Step 4: Collect results (changed file lists + reports)

Step 4.5: Scope validation
        For each resolver agent, verify modified files are within scope
        (files referenced in todo + 1-hop imports). Revert out-of-scope
        changes before committing. Mirror Phase 4's pr-comment-resolver
        Step 4 pattern.

Step 5: Stage ONLY reported files (explicit git add per file, no git add -A)
        Commit: "fix: resolve review findings"
        This commit is DURABLE — safe from session crashes.
        /ship will add its own commit on top (two-commit strategy).
        If the repo uses squash-merge, both fold into one on main.

Step 6: Update todo YAML: status → complete

Step 7: Report "{N} resolved, {M} files changed"
```

#### 9. Extract shared functions into `lib.sh`

**New file:** `scripts/compound/lib.sh`

Extract from `auto-compound.sh`:

- `ai_run` function — supports claude, codex, gemini
- Scoped `.env.local` sourcing (only API keys, not all vars)
- `config.json` reading helpers
- `TOOL` and `MODEL` variable setup

All scripts source this: `source "$(dirname "$0")/lib.sh"`

#### 10. Split `auto-compound.sh` into `build.sh`

**New file:** `scripts/compound/build.sh`

Contains: report analysis, branch creation, PRD generation, task conversion, optional sprint contract, execution loop, optional evaluator, quality sweep.

**Non-interactive:** CLI flags replace the interactive menu:

- `--ambition`, `--evaluator`, `--contract`
- No flags = defaults from `config.json`
- NEVER prompts via `read`

Does NOT contain: push, PR, monitoring, learnings.

#### 11. Create `compound-learning.sh`

**New file:** `scripts/compound/compound-learning.sh`

Basic version: reads `progress.txt`, extracts learnings, writes to `docs/solutions/`. Phase 6 upgrades to full system.

#### 12. Create `/harden-plan` command

**New file:** `.claude/commands/harden-plan.md`

```
Usage:
  /harden-plan [plan-path] --full          → 8 agents (section builds)
  /harden-plan [plan-path] --lightweight   → 4 agents (standalone default)
  /harden-plan [plan-path] --auto          → Auto-apply (used by /harness:plan)

Step 1: Read .harness/harness.local.md (project context)

Step 2: Idempotency check — IF "## Hardening Notes" exists → skip

Step 3: Dispatch agents (all model: inherit)
  ALWAYS (both intensities):
    spec-flow-analyzer     [Phase 3]
    security-auditor       [Phase 1]
    performance-auditor    [Phase 1]
    pattern-finder

  CONDITIONAL (full only):
    architecture-strategist   [Phase 1] — IF multi-package
    code-simplicity-reviewer  [Phase 1] — IF 4+ phases
    frontend-races-reviewer   [Phase 1] — IF async UI
    schema-drift-detector     [Phase 2] — IF Prisma changes

Step 4: Synthesize → P1/P2/P3

Step 5: IF --auto: append "## Hardening Notes" automatically
        IF standalone: ask "Apply?" (yes/no)

Note: Phase 1 moves /harden-plan to read from agents.yml keys
      harden_plan_agents and harden_plan_conditional_agents.
      Plan review ≠ code review — different agents for different purposes.
      [Phase N] agents are silently skipped until created.
```

#### 13. Create `/harness:kickoff` meta-orchestrator

**New file:** `.claude/commands/harness/kickoff.md`

Loads brainstorming skill, open-ended dialogue, captures to `docs/brainstorms/`. Prompts user to run `/harness:define`.

#### 14. Create `/harness:define` meta-orchestrator

**New file:** `.claude/commands/harness/define.md`

Steps: `/define-product` → `/define-design` → `/define-architecture` → shape sections (internal, cap 3 per session). Each `/define-*` step detects existing artifacts and enters update mode if they exist.

Accepts targeted mode: `/harness:define product`, `/harness:define design`, `/harness:define architecture`.

#### 15. Create `/harness:plan` meta-orchestrator

**New file:** `.claude/commands/harness/plan.md`

Interactive planning pipeline orchestrator following the `/harness:plan` architecture diagram above. Resolves target from registry status, chains: design → pnf → harden → approval.

Guards:

- On `approved`+ section → refuses with "Already approved. Run /harness:build"
- Validates registry integrity (see Registry Integrity Validation)

Passes `--full`/`--lightweight` to `/harden-plan` based on CASE A (section) vs CASE B (feature). Passes `--auto` to `/harden-plan` for automatic application.

Design step [Phase 10] (Step 2): Checks if section has UI components. If yes, dispatches design workflow (agents defined in Phase 10) and sets status to `designed`. If no, sets status to `"design:skipped"`. Skip design when zero files in the section spec match `apps/web/**/*.tsx`, `packages/ui/**`, or any `.css`/`.html` file. Otherwise dispatch design agents. Design runs before `/pnf` so the plan incorporates design decisions.

Human approval gate: Presents plan summary, asks for approval. On approval, writes `approved` status with `approved_at` (ISO-8601 timestamp) and `plan_hash` (short hash of plan file).

#### 16. Create `/harness:build` meta-orchestrator

**New file:** `.claude/commands/harness/build.md`

Autonomous execution pipeline orchestrator following the `/harness:build` architecture diagram above. Resolves target from registry status, chains: inf → review → resolve → test-browser → ship → learn.

Guards:

- On non-`approved` section → refuses with "Run /harness:plan first"
- On `approved` without `approved_at` → refuses with "Plan approval metadata missing. Re-run /harness:plan for human approval."
- Validates registry integrity (see Registry Integrity Validation)
- On `reviewed` section → routes directly to Step 4 (ship) — recovery path

Passes plan path to `/inf` via `--plan` flag (plan path comes from the section's plan doc, identified by `approved` status). Sets `reviewed` status after Step 3 (`/test-browser`). Sets `built` status after Step 6.

`/review` dispatches `review_design_agents` when section status = `designed`, skips them when `"design:skipped"`.

#### 17. Update `/inf` (build-only + explicit-path mode)

**File:** `.claude/commands/inf.md`

Changes:

- Replace `auto-compound.sh` with `build.sh`
- **Add `--plan` flag:** "If `--plan path/to/plan.md` is provided, skip Section Registry Check and pass the plan directly to build.sh."
- Keep `--dry-run` and `[SECTION_SPEC_PATH]` passthrough
- Downstream interface preserved — no existing args change

#### 18. Deprecate `auto-compound.sh`

**Rename:** `auto-compound.sh` → `auto-compound.sh.deprecated`

Keep until Phase 1 verified. Delete in separate commit.

#### 19. Delete `.claude/commands/review_code.md`

Replaced by `.claude/commands/review.md`.

#### 20. Add merge prevention hook

**File:** `.claude/settings.json`

Add to existing hooks (matching the existing `{matcher, hooks: [{type, command}]}` structure):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'echo \"$CLAUDE_TOOL_INPUT\" | grep -qiE \"(gh pr merge|git merge (main|master)|git push.*(origin\\s+main|origin\\s+master|HEAD:main|HEAD:master)|gh pr review --approve)\" && echo \"BLOCKED: Merge commands are prohibited. The pipeline stops at PR creation.\" && exit 1 || exit 0'"
          }
        ]
      }
    ]
  }
}
```

Note: This is best-effort (Layer 1 of 3). The regex can be bypassed via indirection. GitHub branch protection (Layer 3) is the true enforcement — documented in HOW_IT_WORKS.md as a recommended setup step.

---

### P1 — Enrichment Hooks

#### 21. Enrich config from `/define-product`

**File:** `.claude/commands/define-product.md`
**Change:** Add Step 6b — updates `.harness/harness.local.md` with product name, target users, external services, data sensitivity.

#### 22. Enrich config from `/define-architecture`

**File:** `.claude/commands/define-architecture.md`
**Change:** Add Step 4b — appends auth strategy, database patterns, external integrations, API patterns.

---

### P2 — Documentation & Support Updates

#### 23. Update `CLAUDE.md`

- Sub-agents table: update all agent names (4 renames) + add `harness-todo-resolver`
- Progressive disclosure: add `.launchpad/agents.yml` and `.harness/harness.local.md`
- Add `/harness:kickoff`, `/harness:define`, `/harness:plan`, `/harness:build`, `/review`, `/ship`, `/harden-plan`, `/resolve_todo_parallel`
- Update meta-orchestrators count: 4 (not 3)
- Remove `/review_code` references
- Update agent namespace structure in codebase map

#### 24. Update `AGENTS.md` — mirror CLAUDE.md

#### 25. Update `HOW_IT_WORKS.md`

- Add 4 meta-orchestrators + pipeline flow
- Replace `/review_code` with `/review`
- Update `/inf` description (build-only)
- Add "Review Agent Configuration" subsection
- Add recommended GitHub branch protection setup (Layer 4 of merge prevention)

#### 26. Update `METHODOLOGY.md` — command table + layers

#### 27. Update `README.template.md` — command table

#### 28. Update `REPOSITORY_STRUCTURE.md`

- Add `.harness/` (todos/, observations/, design-artifacts/)
- Add `.launchpad/agents.yml`
- Add `.claude/commands/harness/` (kickoff, define, plan, build)
- Add `.claude/commands/review.md`, `ship.md`, `harden-plan.md`
- Update `.claude/agents/` namespace subdirectories
- Remove `review_code.md`

#### 29. Update `init-project.sh`

**Note:** `init-project.sh` accumulates changes across all phases (0-11). Rather than updating incrementally per-phase (which leaves it in a partially-correct state between phases), defer the comprehensive `init-project.sh` update to **Phase Finale**. During Phases 0-11, any `.harness/` or `.launchpad/` structures needed for testing can be created manually or via the commands themselves. Phase Finale will reconcile all accumulated changes into one tested `init-project.sh` update.

Phase Finale `init-project.sh` update must include:

- Create `.harness/` (todos/, observations/, design-artifacts/)
- Create `.harness/harness.local.md` with `{{PROJECT_NAME}}`
- Create `.launchpad/agents.yml` with all keys (review_agents, review_db_agents, review_design_agents, review_copy_agents, harden_plan_agents, harden_plan_conditional_agents, harden_document_agents)
- Add `.harness/harness.local.md` to `.launchpad/init-touched-files`
- Create `.claude/agents/` namespace subdirectories
- Update `auto-compound.sh` → `build.sh` references

#### 30. Update `check-repo-structure.sh`

- Add `.harness` to hidden-directory whitelist (explicit validation)

#### 31. Update `.gitignore`

- Add `review-history.md`
- Add `auto-compound.sh.deprecated`
- Add `.harness/screenshots/*.png`
- Add `.harness/structure-drift.md`
- Add `.harness/review-summary.md`

#### 32. Update `evaluate.sh`

- Source `lib.sh` instead of checking `ai_run` export

#### 33. Cross-reference sweep

- `review_code` → `review`
- `auto-compound.sh` → `build.sh`/`compound-learning.sh`/`lib.sh`
- Old agent names → new names (4 renames) — includes `prd/SKILL.md`, `skills-index.md`
- `loop.sh` references to `auto-compound.sh`
- Note: CE plugin `compound-engineering:resolve_todo_parallel` stays installed. Local `/resolve_todo_parallel` command takes precedence. Plugin removed at Phase Finale.

---

## Failure Handling

### `/harness:plan` Failures

| Step              | Failure               | Recovery                                                                                       |
| ----------------- | --------------------- | ---------------------------------------------------------------------------------------------- |
| Step 2 (design)   | Design incomplete     | Re-run `/harness:plan` — status "shaped", routes to Step 2                                     |
| Step 3 (pnf)      | No plan generated     | Re-run `/harness:plan` — no plan, re-enters Step 3                                             |
| Step 4 (harden)   | Plan already hardened | Re-run — harden detects "Hardening Notes", skips (idempotent)                                  |
| Step 5 (approval) | Not approved          | Re-run `/harness:plan` — status "hardened", routes to Step 5. On "revise", resets to "shaped". |
| Session crash     | Various               | Durable artifacts enable resume. Status routing re-enters at correct step.                     |

**Guard:** `/harness:plan` on `approved`+ section → refuses with "Already approved. Run /harness:build"

### `/harness:build` Failures

| Step                  | Failure               | Recovery                                                                     |
| --------------------- | --------------------- | ---------------------------------------------------------------------------- |
| Step 1 (inf)          | Branch + partial code | Re-run `/harness:build` — status "approved", re-enters at Step 1 (inf)       |
| Step 2 (review)       | Code on branch        | Run `/review` standalone                                                     |
| Step 2.5 (resolve)    | Partial fixes         | Run `/resolve_todo_parallel` standalone                                      |
| Step 3 (test-browser) | Tests fail            | Re-run — non-blocking [Phase 5]                                              |
| Step 4 (ship)         | Code reviewed         | Run `/ship` standalone. Status "reviewed" → Step 4 on re-run                 |
| Step 5 (learn)        | PR created            | Run `compound-learning.sh` directly. Non-critical.                           |
| Session crash         | Various               | Durable artifacts enable resume. Run individual commands from failure point. |

**Guard:** `/harness:build` on non-`approved` section → refuses with "Run /harness:plan first". On `approved` without `approved_at` → refuses with "Plan approval metadata missing. Re-run /harness:plan for human approval."

**Key:** After ship failure, do NOT re-run full `/harness:build` — the `reviewed` status routes directly to Step 4 (ship).

---

## Downstream Migration

When downstream projects pull these changes via `/pull-launchpad`:

**Flows automatically (NEW files):**

- `.launchpad/agents.yml`
- `.claude/agents/` namespace subdirectories + renamed agents
- `.claude/commands/harness/` (kickoff, define, plan, build)
- `.claude/commands/review.md`, `ship.md`, `harden-plan.md`, `resolve_todo_parallel.md`
- `scripts/compound/build.sh`, `compound-learning.sh`, `lib.sh`

**Requires manual action:**

- `.harness/` directory must be created (re-run `init-project.sh --target-dir .` or create manually)
- `.harness/harness.local.md` must be created with project-specific context
- Old agent references in downstream-only commands/skills must be updated (4 renames)
- If downstream customized `auto-compound.sh`, migrate to `build.sh`

**Excluded from sync:**

- `.harness/harness.local.md` (in `init-touched-files`)
- `docs/reports/`, `docs/plans/` (already excluded)

---

## Verification Checklist

### Infrastructure

- [ ] **FIRST ACTION:** Deploy PreToolUse merge prevention hook to `.claude/settings.json` before any other Phase 0 work
- [ ] `.harness/todos/.gitkeep` exists
- [ ] `.harness/observations/.gitkeep` exists
- [ ] `.launchpad/agents.yml` exists with valid YAML (includes `review_design_agents: []`, `review_copy_agents: []`)
- [ ] `.harness/design-artifacts/.gitkeep` exists
- [ ] `.harness/harness.local.md` exists with project context
- [ ] `.claude/agents/` has 6 namespace subdirectories (research, review, document-review, resolve, design, skills)
- [ ] 7 existing agents moved with correct renames
- [ ] Old flat agent files deleted

### Commands & Agents

- [ ] `.claude/commands/review.md` exists (flat, not in harness/)
- [ ] `.claude/commands/ship.md` exists (flat)
- [ ] `.claude/commands/harden-plan.md` exists (flat)
- [ ] `.claude/commands/harness/kickoff.md` exists
- [ ] `.claude/commands/harness/define.md` exists
- [ ] `.claude/commands/harness/plan.md` exists
- [ ] `.claude/commands/harness/build.md` exists
- [ ] `.claude/commands/resolve_todo_parallel.md` exists
- [ ] `.claude/agents/resolve/harness-todo-resolver.md` exists with `model: inherit`

### Scripts

- [ ] `scripts/compound/lib.sh` exists with `ai_run` + scoped env loading
- [ ] `build.sh` sources `lib.sh`, non-interactive, accepts CLI flags
- [ ] `compound-learning.sh` sources `lib.sh`, reads `progress.txt`
- [ ] `evaluate.sh` updated to source `lib.sh`

### Pipeline — `/harness:plan`

- [ ] `plan.md` exists in `.claude/commands/harness/`
- [ ] Resolves target from registry status (2 cases: named/registry or free-text)
- [ ] Guard: refuses `approved`+ sections with "Already approved. Run /harness:build"
- [ ] Status "shaped" → Step 2 (design)
- [ ] Status "designed"/"design:skipped" → Step 3 (pnf)
- [ ] Status "planned" → Step 4 (harden)
- [ ] Status "hardened" → Step 5 (approval)
- [ ] Design skip criteria: zero files match `apps/web/**/*.tsx`, `packages/ui/**`, `.css`/`.html`
- [ ] `/harden-plan` skips if "Hardening Notes" already exists (idempotent)
- [ ] `/harden-plan --auto` auto-applies without prompting
- [ ] Design step (Step 2): conditional on UI components [Phase 10]
- [ ] Design step (Step 2): sets status to `designed` or `"design:skipped"`
- [ ] Approval gate: human approval required before `approved` status
- [ ] Approval writes `approved_at` (ISO-8601) and `plan_hash` (short hash)
- [ ] Registry integrity validation before proceeding
- [ ] Status routing covers all plan-phase statuses

### Pipeline — `/harness:build`

- [ ] `build.md` exists in `.claude/commands/harness/`
- [ ] Guard: refuses non-`approved` sections with "Run /harness:plan first"
- [ ] Guard: refuses `approved` without `approved_at` with "Plan approval metadata missing"
- [ ] Guard: validates registry integrity (artifacts match status)
- [ ] Status "approved" → Step 1 (inf)
- [ ] Status "reviewed" → Step 4 (ship) — ship-failure recovery works
- [ ] `/inf [explicit-path]` skips registry check
- [ ] `/review` validates agent names ([a-z0-9-]+, file exists)
- [ ] `/review` pre-scans diff for secrets (added lines only, reads from `.launchpad/secret-patterns.txt`)
- [ ] `/review` reads PR intent context (Step 1.5) — graceful when no PR exists
- [ ] `/review` confidence rubric scores each finding 0.00-1.00
- [ ] `/review` suppresses findings below 0.60 threshold
- [ ] `/review` applies 6 FP categories (pre-existing, style nitpick, intentional, handled-elsewhere, restatement, generic)
- [ ] `/review` boosts multi-agent agreement (+0.10) and security concerns (+0.10)
- [ ] `/review` P1 findings have a 0.60 floor (never auto-suppressed)
- [ ] `/review` intent verification suppresses findings contradicting PR context
- [ ] `/review` writes suppressed findings to review-summary.md (audit trail)
- [ ] `/review` todo YAML includes `confidence` field (0.00-1.00)
- [ ] `/review --headless` suppresses all interactive output
- [ ] `/review --headless` skips Step 7 (Report)
- [ ] `/review --headless` writes to .harness/todos/ and review-summary.md normally
- [ ] `/review` clears todos before writing (idempotent on retry)
- [ ] `/review` handles zero findings gracefully (including when all suppressed)
- [ ] `/review` conditionally dispatches DB agents on Prisma changes
- [ ] `/review` dispatches `review_design_agents` when section status = `designed` [Phase 10]
- [ ] `/review` skips design agents when section status = `"design:skipped"`
- [ ] `/review` emits P2 warning if `"design:skipped"` but diff contains UI-relevant files
- [ ] `/resolve_todo_parallel` groups same-file todos for sequential execution
- [ ] `/resolve_todo_parallel` enforces max 5 concurrent agents
- [ ] `/resolve_todo_parallel` validates scope post-execution (reverts out-of-scope changes)
- [ ] `/resolve_todo_parallel` stages only reported files (no `git add -A`)
- [ ] `/resolve_todo_parallel` commits fixes ("fix: resolve review findings") — durable commit
- [ ] `/test-browser` writes `reviewed` status (or `/review` writes it if browser testing skipped)
- [ ] `/ship` is idempotent for PR creation (skips if PR exists for branch)
- [ ] `/ship` uses `git add -u` (NOT `git add -A`)
- [ ] `/ship` runs full quality gates with auto-fix cycle (max 3 attempts)
- [ ] `/ship` auto-generates conventional commit
- [ ] `/ship` monitors PR (max 3 cycles): CI + Codex + conflicts
- [ ] `/ship` auto-fixes Codex AGREE items (max 3 fix rounds, respects sensitive file denylist)
- [ ] `/ship` checks for remote divergence before force-with-lease push
- [ ] `/ship` NEVER merges (verify with manual test)
- [ ] `/ship` refuses to ship to protected branches (reads from `agents.yml` `protected_branches`)
- [ ] inf → review → resolve → test-browser → ship → learn → report flow works end-to-end

### Pipeline — `/harness:define`

- [ ] Runs `/define-product` → `/define-design` → `/define-architecture` in sequence
- [ ] Detects existing artifacts → update mode (not overwrite)
- [ ] Shapes sections internally (cap 3 per session)
- [ ] Targeted mode works: `/harness:define product`

### Pipeline — `/harness:kickoff`

- [ ] Loads brainstorming skill
- [ ] Captures to `docs/brainstorms/`
- [ ] Prompts to run `/harness:define`

### Merge Prevention

- [ ] PreToolUse hook in `.claude/settings.json` blocks `gh pr merge`
- [ ] PreToolUse hook blocks `git merge main/master`
- [ ] PreToolUse hook blocks `git push` to protected branches (origin main/master, HEAD:main/master)
- [ ] PreToolUse hook blocks `gh pr review --approve`
- [ ] PreToolUse hook does NOT false-match branches containing "main" as substring
- [ ] `/ship` Step 7 says "NEVER merge"
- [ ] `protected_branches` list in `.launchpad/agents.yml` read by branch-guarding commands
- [ ] GitHub branch protection documented in HOW_IT_WORKS.md

### Cleanup

- [ ] `.gitignore` includes `.harness/screenshots/*.png`, `.harness/structure-drift.md`, `.harness/review-summary.md`
- [ ] `.gitignore` includes `review-history.md`
- [ ] `auto-compound.sh` renamed to `.deprecated`
- [ ] `review_code.md` deleted
- [ ] `check-repo-structure.sh` validates `.harness/`
- [ ] `init-project.sh` creates `.harness/` (todos/, observations/, design-artifacts/) + `.launchpad/agents.yml`
- [ ] `/pull-launchpad` does NOT overwrite `.harness/harness.local.md`
- [ ] `/pull-launchpad` DOES sync `.launchpad/agents.yml`
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass
- [ ] No remaining references to `review_code`, `auto-compound.sh`, old agent names

---

## What This Does NOT Include

| Deferred To  | What                                                                                                                                                                                                                                                                                                                   |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1      | Review agent definitions (8 agents: security, TS, performance, simplicity, architecture, deployment, frontend-races, python)                                                                                                                                                                                           |
| Phase 2      | Database agent definitions (schema-drift, data-migration, data-integrity)                                                                                                                                                                                                                                              |
| Phase 3      | Workflow layers: `/brainstorm` skill content, `/harden-plan` agents (spec-flow-analyzer + 7 document-review agents), `document-review` skill. `/harden-plan` uses `/review --headless` for programmatic invocation.                                                                                                    |
| Phase 4      | PR comment resolution: `pr-comment-resolver` agent + `/resolve-pr-comments` command                                                                                                                                                                                                                                    |
| Phase 5      | Browser testing + bug reproduction                                                                                                                                                                                                                                                                                     |
| Phase 6      | Compound learning upgrade (5-agent, 14-category) + `learnings-researcher` agent                                                                                                                                                                                                                                        |
| Phase 7      | Manual `/commit` workflow with triage. `/commit` Step 2.5 uses `/review --headless`. Review default flipped to on (viable due to confidence rubric).                                                                                                                                                                   |
| Phase 8      | Automated backlog system                                                                                                                                                                                                                                                                                               |
| Phase 9      | Git worktree workflow                                                                                                                                                                                                                                                                                                  |
| Phase 10     | Design workflow import (6 agents + 5 skills + 6 commands + pipeline wiring) — provides `review_design_agents` population, `review_copy_agents` key, design step implementation, `.harness/design-artifacts/` directory, `/feature-video`, `rclone`/`imgup` skills                                                      |
| Phase 11     | BuiltForm copy agent wrappers + remaining skill wiring + port `stripe-best-practices` and `react-best-practices` to LaunchPad                                                                                                                                                                                          |
| ~~Phase 12~~ | Eliminated -- `feature-video`, `rclone`, `imgup` moved to Phase 10; `changelog`, `generate_command` not ported (low priority utilities); `builtform-style-editor` not ported (covered by Phase 10 design review workflow); `agent-native-reviewer`/`agent-native-audit` not ported (covered by existing review agents) |
| Future       | Cross-model agent dispatch (pending benchmarks)                                                                                                                                                                                                                                                                        |
| Future       | Cost estimation / telemetry                                                                                                                                                                                                                                                                                            |
| Phase Finale | Documentation refresh                                                                                                                                                                                                                                                                                                  |

---

## File Change Summary

| #     | File                                                | Change                                                                                                      | Priority |
| ----- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | -------- |
| 1     | `.harness/todos/.gitkeep`                           | **Create**                                                                                                  | P0       |
| 2     | `.harness/observations/.gitkeep`                    | **Create**                                                                                                  | P0       |
| 2b    | `.harness/design-artifacts/.gitkeep`                | **Create**                                                                                                  | P0       |
| 3     | `.launchpad/agents.yml`                             | **Create** — includes `review_design_agents: []`, `review_copy_agents: []` [Phase 10], `protected_branches` | P0       |
| 3b    | `.launchpad/secret-patterns.txt`                    | **Create** — secret scan patterns (one per line)                                                            | P0       |
| 4     | `.harness/harness.local.md`                         | **Create**                                                                                                  | P0       |
| 5     | `.claude/agents/research/file-locator.md`           | **Move+Rename**                                                                                             | P0       |
| 6     | `.claude/agents/research/code-analyzer.md`          | **Move+Rename**                                                                                             | P0       |
| 7     | `.claude/agents/research/pattern-finder.md`         | **Move+Rename**                                                                                             | P0       |
| 8     | `.claude/agents/research/docs-locator.md`           | **Move**                                                                                                    | P0       |
| 9     | `.claude/agents/research/docs-analyzer.md`          | **Move**                                                                                                    | P0       |
| 10    | `.claude/agents/research/web-researcher.md`         | **Move+Rename**                                                                                             | P0       |
| 11    | `.claude/agents/research/skill-evaluator.md`        | **Move**                                                                                                    | P0       |
| 12    | `.claude/agents/review/.gitkeep`                    | **Create**                                                                                                  | P0       |
| 13    | `.claude/agents/resolve/harness-todo-resolver.md`   | **Create**                                                                                                  | P0       |
| 14    | `.claude/agents/document-review/.gitkeep`           | **Create** — Phase 3 v7 agents go here                                                                      | P0       |
| 14b   | `.claude/agents/design/.gitkeep`                    | **Create**                                                                                                  | P0       |
| 15    | `.claude/commands/review.md`                        | **Create** — flat, replaces review_code.md                                                                  | P0       |
| 16    | `.claude/commands/ship.md`                          | **Create** — autonomous shipping                                                                            | P0       |
| 17    | `.claude/commands/harden-plan.md`                   | **Create** — plan stress-testing                                                                            | P0       |
| 18    | `.claude/commands/harness/kickoff.md`               | **Create** — meta-orchestrator                                                                              | P0       |
| 19    | `.claude/commands/harness/define.md`                | **Create** — meta-orchestrator                                                                              | P0       |
| 20    | `.claude/commands/harness/plan.md`                  | **Create** — meta-orchestrator (interactive planning pipeline)                                              | P0       |
| 21    | `.claude/commands/harness/build.md`                 | **Create** — meta-orchestrator (autonomous execution pipeline)                                              | P0       |
| 22    | `.claude/commands/resolve_todo_parallel.md`         | **Create**                                                                                                  | P0       |
| 23    | `scripts/compound/lib.sh`                           | **Create** — shared functions                                                                               | P0       |
| 24    | `scripts/compound/build.sh`                         | **Create** — non-interactive                                                                                | P0       |
| 25    | `scripts/compound/compound-learning.sh`             | **Create** — basic version                                                                                  | P0       |
| 26    | `.claude/commands/inf.md`                           | **Edit** — build-only + explicit-path mode                                                                  | P0       |
| 27    | `scripts/compound/auto-compound.sh`                 | **Rename** → `.deprecated`                                                                                  | P0       |
| 28    | `.claude/commands/review_code.md`                   | **Delete**                                                                                                  | P0       |
| 29    | 7 old flat agent files                              | **Delete**                                                                                                  | P0       |
| 30    | `scripts/compound/evaluate.sh`                      | **Edit** — source lib.sh                                                                                    | P0       |
| 31    | `.claude/settings.json`                             | **Edit** — add merge prevention hook                                                                        | P0       |
| 32    | `.claude/commands/define-product.md`                | **Edit** — add Step 6b                                                                                      | P1       |
| 33    | `.claude/commands/define-architecture.md`           | **Edit** — add Step 4b                                                                                      | P1       |
| 34    | `CLAUDE.md`                                         | **Edit** — agents + commands + namespace + 4 meta-orchestrators                                             | P2       |
| 35    | `AGENTS.md`                                         | **Edit** — mirror CLAUDE.md                                                                                 | P2       |
| 36    | `docs/guides/HOW_IT_WORKS.md`                       | **Edit** — 4 meta-orchestrators + pipeline + branch protection                                              | P2       |
| 37    | `.launchpad/METHODOLOGY.md`                         | **Edit** — layers + commands                                                                                | P2       |
| 38    | `README.template.md`                                | **Edit** — command table                                                                                    | P2       |
| 39    | `docs/architecture/REPOSITORY_STRUCTURE.md`         | **Edit** — full tree update (add `plan.md` to `.claude/commands/harness/`)                                  | P2       |
| 40    | `scripts/setup/init-project.sh`                     | **Deferred to Phase Finale** — comprehensive update after all phases implemented                            | P2       |
| 41    | `scripts/maintenance/check-repo-structure.sh`       | **Edit** — .harness whitelist                                                                               | P2       |
| 42    | `.gitignore`                                        | **Edit** — review-history.md + .deprecated                                                                  | P2       |
| 43    | `.claude/skills/prd/SKILL.md`                       | **Edit** — agent name refs                                                                                  | P2       |
| 44    | `docs/skills-catalog/skills-index.md`               | **Edit** — agent name refs                                                                                  | P2       |
| 45    | `scripts/compound/loop.sh`                          | **Edit** — `auto-compound.sh` reference                                                                     | P2       |
| 46-49 | Agent name cross-references (4 command/skill files) | **Edit**                                                                                                    | P2       |
| 50    | All other files referencing old names               | **Edit** — sweep                                                                                            | P2       |
