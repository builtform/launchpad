# How It Works

LaunchPad is a structured AI development harness built on four meta-orchestrators that chain together specialized commands. This guide walks you through the full pipeline.

---

## The Four Meta-Orchestrators

```
/harness:kickoff → /harness:define → /harness:plan → /harness:build
     brainstorm       definition        design+plan       build+ship
```

Each orchestrator owns a phase of the lifecycle. You can run them in sequence for a full project, or invoke any one independently when resuming work.

### Status Contract

Every section progresses through a strict status chain tracked in its spec file's YAML frontmatter:

```
defined → shaped → designed / "design:skipped" → planned → hardened → approved → reviewed → built
```

Each meta-orchestrator checks this status before proceeding and refuses to run if the section is not at the expected stage.

---

## Phase 1: Kickoff

**`/harness:kickoff`** delegates to `/brainstorm` for collaborative idea exploration, then hands off to `/harness:define`.

`/brainstorm` loads the brainstorming skill, dispatches research agents when a codebase exists, guides structured dialogue, and captures a design document to `docs/brainstorms/`. It never writes code.

---

## Phase 2: Definition

**`/harness:define`** chains four commands in sequence:

1. **`/define-product`** -- Interactive Q&A producing `PRD.md` and `TECH_STACK.md`
2. **`/define-design`** -- Produces `DESIGN_SYSTEM.md`, `APP_FLOW.md`, and `FRONTEND_GUIDELINES.md`
3. **`/define-architecture`** -- Produces `BACKEND_STRUCTURE.md` and `CI_CD.md`
4. **`/shape-section [name]`** -- Deep-dive per section producing `docs/tasks/sections/[name].md` (up to 3 per session)

Each command detects existing artifacts and runs in update mode when they exist. After shaping, sections have status `shaped`.

For public-facing pages, `/shape-section` prompts to create page copy via the `web-copy` skill (if installed). Copy informs design, not the other way around.

---

## Phase 3: Planning

**`/harness:plan`** is the most complex orchestrator. It resolves the target section from the registry, checks its status, and routes to the appropriate step.

### Step 2: Design Workflow

Runs before planning so the plan incorporates concrete design decisions.

**UI detection** parses the section spec for UI keywords (component, page, layout, modal, form, dashboard, etc.) and file references containing `apps/web/` or `packages/ui/`. The user can always skip design, setting status to `"design:skipped"`.

| Sub-step                        | What happens                                                                                                                                                                                                                                                                                                                      |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **2a: Autonomous first draft**  | Loads design skills (`frontend-design`, `web-design-guidelines`, `responsive-design`) and copy context. Builds UI components following design system tokens, opens browser (agent-browser or Playwright), screenshots and self-evaluates for 3-5 auto-cycles via `design-iterator`. Presents first draft with live localhost URL. |
| **2b: Interactive refinement**  | User gives feedback, dispatches `design-iterator` (one change per iteration). Supports Figma sync (`figma-design-sync`) and systematic polish (`/design-polish`).                                                                                                                                                                 |
| **2c: Design review and audit** | Runs `/design-review` first (8 design + 4 tech dimensions, AI slop detection), then dispatches `design-ui-auditor`, `design-responsive-auditor`, `design-alignment-checker`, and optionally `design-implementation-reviewer` (Figma comparison) and `/copy-review` in parallel. Re-audit cap: 3 cycles maximum.                   |
| **2d: Walkthrough recording**   | Optional `/feature-video` -- captures screenshots of approved design, stitches into MP4+GIF, uploads via rclone or imgup.                                                                                                                                                                                                         |

### Step 3: Plan

Runs `/pnf [section]` -- research-first planning with sub-agents. Produces an implementation plan. Status becomes `planned`.

### Step 4: Harden

Runs `/harden-plan` to stress-test the plan. Modes:

- **`--full`** -- all agents (for section builds)
- **`--lightweight`** -- core agents only (standalone features)
- **`--auto`** -- auto-apply findings without prompting
- **`--interactive`** -- present each finding for accept/reject/discuss (default from `/harness:plan`)

Hardening includes a document quality pre-check (Step 2), learnings scan from `docs/solutions/` (Step 2.5), Context7 technology enrichment (Step 2.7), code-focused agent dispatch (Step 3), document-review agent dispatch (Step 3.5), and interactive deepening (Step 3.7). Status becomes `hardened`.

### Step 5: Human Approval

Presents plan summary with hardening notes and design status. Four options:

- **yes** -- sets status to `approved`, records `approved_at` and `plan_hash`, proceeds to `/harness:build`
- **revise design** -- resets to `shaped`, clears design artifacts, re-enters Step 2
- **revise plan** -- resets to `designed`, re-enters Step 3 (design preserved)
- **revise both** -- resets to `shaped`, re-enters Step 2 (everything regenerated)

---

## Phase 4: Build

**`/harness:build`** is fully autonomous. It requires status `approved` with a valid `approved_at` field.

| Step | Command                  | What happens                                                                                                                                                         |
| ---- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `/inf`                   | Full execution pipeline: report, PRD, tasks, execution loop, quality sweep                                                                                           |
| 2    | `/review`                | Multi-agent parallel review (interactive mode -- see below)                                                                                                          |
| 2.5  | `/resolve_todo_parallel` | Spawns up to 5 concurrent resolver agents, groups overlapping files sequentially, commits fixes                                                                      |
| 3    | `/test-browser`          | Maps changed files to UI routes (max 15), tests each (30s per route). Gracefully skips if no browser tool or no UI routes. Findings are informational, not blocking. |
| 4    | `/ship`                  | Quality gates, commit, push, PR creation, CI monitoring. Never merges.                                                                                               |
| 5    | `/learn`                 | 5-agent parallel research pipeline, writes structured solution doc to `docs/solutions/`                                                                              |
| 6    | Report                   | Sets status to `built`, prints summary, runs `/regenerate-backlog --stage`                                                                                           |

---

## Key Commands

### /review

Multi-agent code review with confidence-based false-positive suppression.

- Dispatches agents from `.launchpad/agents.yml` in parallel (code, DB, design, copy agents)
- Pre-dispatch secret scan on added lines using `.launchpad/secret-patterns.txt`
- Confidence scoring (0.00--1.00) per finding. Threshold: **0.60**. Findings below threshold are suppressed with an audit trail in `.harness/review-summary.md`
- Boosters: multi-agent agreement (+0.10), security concerns (+0.10), P1 floor (minimum 0.60)
- PR intent verification: findings contradicting stated PR intent are suppressed
- Writes actionable findings to `.harness/todos/`, suppressed findings to review summary
- **`--headless` mode**: identical pipeline but suppresses interactive output. Used by `/harden-plan` and `/commit`

### /ship

Autonomous shipping pipeline. Stages tracked files, runs quality gates (with 3-attempt auto-fix), generates a conventional commit, pushes, creates a PR, and enters a 3-gate monitoring loop (CI checks, Codex review, merge conflicts). **Never merges.**

### /commit

Interactive commit workflow with optional code review chain:

1. Branch guard (refuses to commit on main/master, suggests branch name)
2. Stage and review (user selects files)
3. Optional code review: `/review --headless` then `/triage` then `/resolve_todo_parallel`
4. Skill staleness audit (non-blocking)
5. Quality gates in parallel (test/typecheck/lint + pre-commit hooks)
6. Commit message generation and user approval
7. Optional PR creation with 3-gate monitoring loop (CI, human reviews, Codex review, conflicts)
8. Runs `/regenerate-backlog` after successful commit

### /test-browser

Dual browser support: agent-browser CLI (primary, 93% fewer tokens) or Playwright MCP (fallback). Self-scoping -- maps changed files to UI routes. Graceful skip when no browser tool, no dev server, or no UI routes are detected.

### /harden-plan

Stress-tests implementation plans. Dispatches code-focused agents and document-review agents. Includes learnings scan from `docs/solutions/`, Context7 technology enrichment, and interactive deepening where each finding is presented for accept/reject/discuss.

### /triage

Interactive triage of review findings in `.harness/todos/`. Presents each finding one-by-one; user sorts into fix (ready), drop (dismissed), or defer (backlog). Deferred items flow to `/regenerate-backlog`.

### /learn

Captures learnings from resolved problems. Loads the compound-docs skill, spawns 5 inline research sub-agents in parallel, writes structured YAML-frontmatter solution docs to `docs/solutions/`.

### /brainstorm

Collaborative idea exploration. Loads brainstorming skill, dispatches research agents, guides structured dialogue, captures design document to `docs/brainstorms/`. Never writes code.

### Other Commands

| Command                | Purpose                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------- |
| `/defer`               | Manually add a task to the backlog via `.harness/observations/`                       |
| `/regenerate-backlog`  | Regenerates `docs/tasks/BACKLOG.md` from deferred observations and section registry   |
| `/design-review`       | Comprehensive 8-design + 4-tech dimension quality audit with AI slop detection        |
| `/design-polish`       | Pre-ship refinement pass for alignment, spacing, copy, and interaction states         |
| `/copy`                | Reads copy brief from section spec, provides copy context for design builds           |
| `/copy-review`         | Dispatches copy review agents from `review_copy_agents` in `agents.yml`               |
| `/feature-video`       | Records design walkthrough: screenshots, MP4+GIF via ffmpeg, uploads via rclone/imgup |
| `/resolve-pr-comments` | Batch-resolves unresolved PR review comments with parallel agents                     |
| `/update-spec`         | Scans all spec files for gaps, TBDs, and cross-file inconsistencies                   |

---

## Merge Prevention

Three layers ensure no automated merge ever happens:

1. **Command prohibition** -- `/ship` and `/commit` explicitly refuse to run `gh pr merge` or `git merge main`
2. **PreToolUse hook** -- intercepts merge commands at the tool level before execution
3. **GitHub branch protection** -- server-side rules requiring approvals before merge

---

## Skills

Skills are reusable instruction sets in `.claude/skills/<name>/` that change how the AI reasons about specific problem domains. They are loaded automatically when trigger phrases appear.

| Command         | Purpose                                               |
| --------------- | ----------------------------------------------------- |
| `/create-skill` | Create a new skill using the 7-phase Meta-Skill Forge |
| `/port-skill`   | Import an external skill from GitHub or local files   |
| `/update-skill` | Iterate on an existing skill after real-world usage   |

Two tracking files in `docs/skills-catalog/` provide visibility: `skills-index.md` (all installed skills with descriptions and triggers) and `skills-usage.json` (last-used dates, updated automatically by a PostToolUse hook). A session-end hook audits for stale skills (unused for 14+ days).

---

## Quality Gates

Every change passes through:

1. **Pre-commit hooks** (Lefthook) -- formatting, linting, type checking, structure validation, large file guard
2. **CI pipeline** (GitHub Actions) -- lint, typecheck, test, build, structure check
3. **AI review** -- multi-agent confidence-scored review (P1/P2/P3 severity)

---

## Troubleshooting

**Quality gates fail and block commit.** Run `pnpm test`, `pnpm typecheck`, and `pnpm lint` manually to see the full error. Fix the root cause. Never use `--no-verify`.

**Structure check: "Non-whitelisted file at root."** Move the file using the decision tree in `docs/architecture/REPOSITORY_STRUCTURE.md` Section 7, or add it to the whitelist in `check-repo-structure.sh`.

**Structure check: "Found duplicate files."** Compare both versions with `diff`, keep the better one, delete the other. Do not auto-delete.

**`build.sh` fails: "jq / gh / lefthook not found."** Install the missing tool: `brew install jq`, `brew install gh`, or `brew install lefthook`.

**PR creation fails: "gh: not logged in."** Run `gh auth login` and verify with `gh auth status`.

**No browser tool for /test-browser.** Install agent-browser (`npm install -g agent-browser && agent-browser install`) or ensure Playwright MCP is configured.

**Loop exits early.** Check `scripts/compound/progress.txt`. Common causes: tasks too large, quality checks failing repeatedly, or context overflow. Break large tasks into smaller ones.

**Large file guard blocks commit.** Files over 500KB in tracked extensions (.ts, .js, .json, .css, .md, etc.) are rejected. Add to `.gitignore` or split into smaller files.

---

## Related

- [README](../../README.md)
- [Methodology](METHODOLOGY.md) -- architecture, diagrams, credits
- [Repository Structure](../architecture/REPOSITORY_STRUCTURE.md)
