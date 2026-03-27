# Compound Engineering Plugin Gap Analysis

**Date:** 2026-03-26
**Plugin Version:** 2.35.2
**Plugin Location:** `~/.claude/plugins/cache/every-marketplace/compound-engineering/2.35.2/`
**Goal:** Identify all CE plugin capabilities not covered by LaunchPad/BuiltForm, document how they're wired, and plan internalization so the plugin can be removed.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [How the Plugin Orchestrates Everything](#how-the-plugin-orchestrates-everything)
3. [Gap Inventory (21 Items)](#gap-inventory)
   - [Review Agents (7)](#review-agents)
   - [Workflow Agents (4)](#workflow-agents)
   - [Skills (5)](#skills)
   - [Commands (5)](#commands)
4. [What's Already Covered](#whats-already-covered)
5. [What's Not Applicable](#whats-not-applicable)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

The Compound Engineering plugin provides 29 agents, 22 commands, and 19 skills. After auditing both LaunchPad and BuiltForm, **21 capabilities** represent genuine gaps. The rest are either already covered internally (often with more rigorous implementations) or irrelevant to our TypeScript/Next.js stack (Ruby/Rails/Python-specific, Every-company-specific).

**Key insight:** The plugin's power comes not from individual agents but from how it **wires them into workflow orchestration commands** (`/workflows:review`, `/workflows:work`, `/workflows:plan`). Our codebases already have equivalent workflow commands (`/review_code`, `/inf`, `/pnf`) but they dispatch fewer specialized agents. The primary work is: (1) port the agent definitions, (2) wire them into our existing workflow commands, (3) add the missing standalone commands.

**Destination mapping:**

- **Agents and /commands** → LaunchPad (flows downstream to all projects)
- **Skills** → BuiltForm (domain-specific, not upstream)

---

## How the Plugin Orchestrates Everything

### The Configuration Hub: `compound-engineering.local.md`

The plugin uses a per-project config file (`compound-engineering.local.md`) with YAML frontmatter that declares which review agents to run. The `setup` skill generates this based on tech stack:

```yaml
# compound-engineering.local.md (TypeScript stack default)
review_agents:
  - kieran-typescript-reviewer
  - code-simplicity-reviewer
  - security-sentinel
  - performance-oracle
```

### Workflow Command Dispatch Pattern

All workflow commands follow the same pattern:

1. Read `compound-engineering.local.md` to get `review_agents` list
2. Spawn each agent as a parallel `Task` sub-agent
3. Collect results and synthesize

### The Three Master Orchestrators

| Command             | Our Equivalent             | What It Dispatches That We Don't                                                                                                                                                                                          |
| ------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/workflows:review` | `/review_code`             | `security-sentinel`, `performance-oracle`, `kieran-typescript-reviewer`, `code-simplicity-reviewer`, `architecture-strategist` + conditional: `schema-drift-detector`, `data-migration-expert`, `data-integrity-guardian` |
| `/workflows:work`   | `/inf` + `/implement_plan` | `figma-design-sync` (design-impl-reviewer), `git-worktree` isolation, `agent-browser` screenshots                                                                                                                         |
| `/workflows:plan`   | `/pnf`                     | `/deepen-plan` as follow-up (parallel per-section research enhancement)                                                                                                                                                   |

### The Autonomous Pipeline Commands

`/lfg` and `/slfg` chain: plan → deepen-plan → work → test-browser → feature-video → resolve_parallel. Our `/inf` covers plan → work → commit but misses browser testing, video recording, and parallel comment resolution.

---

## Gap Inventory

### Review Agents

#### 1. `security-sentinel`

**What it does:** Elite AppSec specialist performing 6 scanning protocols — input validation, SQL injection, XSS, auth/authz audit, sensitive data exposure, OWASP Top 10 compliance. Produces executive summary + risk matrix + remediation roadmap.

**How it's wired in the plugin:**

- **`/workflows:review`** — dispatched in parallel with all other `review_agents` (default for ALL tech stacks)
- **`/workflows:compound`** — auto-dispatched when a solved problem is categorized as `security_issue`
- **`setup` skill** — included in default config for Rails, Python, TypeScript, and General stacks

**Plugin file:** `agents/review/security-sentinel.md`

**Invocation pattern:**

```
Task security-sentinel("Review the following changes for security vulnerabilities: {diff}")
```

**Criticality:** CRITICAL (BuiltForm has Stripe payments + user auth)
**Difficulty:** Medium — agent definition is self-contained, needs wiring into `/review_code`

---

#### 2. `kieran-typescript-reviewer`

**What it does:** Opinionated TS reviewer enforcing 10 principles — no `any` without justification, type inference over explicit types, the "5-second naming rule," modern TS 5+ features (`satisfies`, const type params), duplication > complexity philosophy. Reviews prioritize: critical issues → type safety → testability → improvements.

**How it's wired in the plugin:**

- **`/workflows:review`** — dispatched in parallel (default for TypeScript stack)
- **`setup` skill** — auto-configured for TypeScript projects

**Plugin file:** `agents/review/kieran-typescript-reviewer.md`

**Invocation pattern:**

```
Task kieran-typescript-reviewer("Review TypeScript code changes: {diff}")
```

**Criticality:** High (both codebases are 100% TypeScript)
**Difficulty:** Medium — need to adapt conventions to our specific TS patterns

---

#### 3. `performance-oracle`

**What it does:** Performance expert analyzing 6 dimensions — algorithmic complexity (Big O), database performance (N+1, index verification), memory management (leak detection), caching opportunities, network optimization (round trips, payloads), frontend performance (bundle size, render-blocking, lazy loading). Enforces benchmarks: no worse than O(n log n) without justification, API < 200ms, bundle < 5KB per feature.

**How it's wired in the plugin:**

- **`/workflows:review`** — dispatched in parallel (default for ALL tech stacks)
- **`/workflows:compound`** — auto-dispatched for `performance_issue` category
- **`setup` skill** — included in all stack defaults

**Plugin file:** `agents/review/performance-oracle.md`

**Invocation pattern:**

```
Task performance-oracle("Analyze performance of: {diff}")
```

**Criticality:** High (user-facing SaaS app)
**Difficulty:** Medium — self-contained agent definition

---

#### 4. `code-simplicity-reviewer`

**What it does:** YAGNI specialist that ruthlessly simplifies. 6-step analysis: question every line's necessity, simplify complex logic (early returns, flatten nesting), remove redundancy, challenge abstractions (inline single-use code), apply YAGNI rigorously, optimize for readability. Produces LOC reduction percentage and complexity score. Notable: never flags `docs/plans/` or `docs/solutions/` for removal.

**How it's wired in the plugin:**

- **`/workflows:review`** — has its own DEDICATED step (Section 4), separate from parallel agent dispatch. Always runs.
- **`/workflows:compound`** — runs on any code-heavy issue
- **`setup` skill** — included in ALL stack defaults

**Plugin file:** `agents/review/code-simplicity-reviewer.md`

**Invocation pattern:**

```
Task code-simplicity-reviewer("Review for unnecessary complexity: {diff}")
```

**Criticality:** Medium
**Difficulty:** Easy — straightforward agent definition

---

#### 5. `architecture-strategist`

**What it does:** Evaluates code changes for architectural compliance using a 4-step approach — understand system architecture, analyze change context, identify violations (SOLID, circular deps, boundary respect), consider long-term implications. Detects: inappropriate intimacy, leaky abstractions, dependency rule violations, inconsistent patterns, missing boundaries.

**How it's wired in the plugin:**

- **`/workflows:review`** — dispatched in parallel when listed in `review_agents` (default for General stack only; must be manually added for TypeScript)
- **`setup` skill** — included in General stack default

**Plugin file:** `agents/review/architecture-strategist.md`

**Invocation pattern:**

```
Task architecture-strategist("Evaluate architectural impact of: {diff}")
```

**Criticality:** Medium
**Difficulty:** Medium

---

#### 6. `schema-drift-detector`

**What it does:** Prevents accidental inclusion of unrelated schema changes in PRs. Cross-references `schema.rb`/Prisma schema changes against included migrations. Detects: extra columns not in any PR migration, extra indexes, version mismatches. Provides fix instructions. Must run BEFORE `data-migration-expert` and `data-integrity-guardian`.

**How it's wired in the plugin:**

- **`/workflows:review`** — **conditionally** dispatched only when PR contains migrations, schema files, or data backfills. Runs FIRST among database agents.
- Not in any default `review_agents` list — purely conditional trigger

**Plugin file:** `agents/review/schema-drift-detector.md`

**Invocation pattern:**

```
# Conditional check in /workflows:review
if PR files match db/migrate/* OR schema.rb OR prisma/schema.prisma:
    Task schema-drift-detector("Check schema drift: {migration_files}")
    # Then: data-migration-expert
    # Then: data-integrity-guardian
```

**Criticality:** High (BuiltForm uses Prisma with `migrate deploy`)
**Difficulty:** Medium — needs adaptation from Rails schema.rb to Prisma schema.prisma

---

#### 7. `data-integrity-guardian`

**What it does:** Database design and data governance expert focused on ACID properties, GDPR/CCPA compliance, and production safety. Reviews 5 dimensions: migration reversibility/data loss, data constraints (model+DB level), transaction boundaries (isolation levels, deadlock detection), referential integrity (cascade behaviors, orphan prevention), privacy compliance (PII, encryption, retention, audit trails, anonymization).

**How it's wired in the plugin:**

- **`/workflows:compound`** — auto-dispatched for `database_issue` category
- **`/workflows:review`** — dispatched conditionally after `schema-drift-detector` (migration chain)
- **`setup` skill** — only in "Comprehensive" review tier

**Plugin file:** `agents/review/data-integrity-guardian.md`

**Invocation pattern:**

```
Task data-integrity-guardian("Review data integrity of: {migration_files}")
```

**Criticality:** High (BuiltForm has Stripe billing data)
**Difficulty:** Medium

---

### Workflow Agents

#### 8. `pr-comment-resolver`

**What it does:** Takes a single PR review comment, analyzes the requested change, plans resolution, implements the fix, verifies it addresses the comment, and produces a structured resolution report. Designed to be spawned N times in parallel (one per unresolved comment).

**How it's wired in the plugin:**

- **`/resolve_parallel` command** — spawns N parallel instances, one per unresolved PR comment
- **`/resolve_todo_parallel` command** — spawns N parallel instances, one per unresolved TODO
- **`resolve-pr-parallel` skill** — fetches unresolved threads via GraphQL, spawns resolvers, commits, resolves threads via GraphQL mutation

**Plugin file:** `agents/workflow/pr-comment-resolver.md`

**Invocation pattern:**

```
# For each unresolved comment:
Task pr-comment-resolver("Resolve this PR comment: {comment_body}\nFile: {file_path}\nLine: {line}")
```

**Criticality:** High (major workflow efficiency gain)
**Difficulty:** Medium — needs GraphQL scripts for GitHub API

---

#### 9. `bug-reproduction-validator`

**What it does:** Systematically reproduces bug reports. Extracts repro steps, reviews code, sets up test cases, executes reproduction (at least twice), tests edge cases. Classifies as: Confirmed Bug, Cannot Reproduce, Not a Bug, Environmental Issue, Data Issue, or User Error.

**How it's wired in the plugin:**

- **Standalone invocation only** — not auto-wired into any workflow command
- Referenced in `orchestrating-swarms` skill as an example workflow agent
- Uses `agent-browser` CLI for UI bugs

**Plugin file:** `agents/workflow/bug-reproduction-validator.md`

**Invocation pattern:**

```
Task bug-reproduction-validator("Reproduce this bug: {bug_report}")
```

**Criticality:** Medium
**Difficulty:** Easy — self-contained agent

---

#### 10. `git-history-analyzer`

**What it does:** Git archaeology specialist. Uses `git log --follow`, `git blame -w -C -C -C`, `git log --grep`, `git shortlog -sn`, `git log -S"pattern"`. Produces timeline of file evolution, contributor-to-domain mappings, historical issues/fixes, and change patterns.

**How it's wired in the plugin:**

- **`/deepen-plan` command** — spawned alongside `best-practices-researcher`, `framework-docs-researcher`, and `repo-research-analyst` for per-section research
- **`setup` skill** — listed in "Comprehensive" review tier
- Referenced in `orchestrating-swarms` as a research agent

**Plugin file:** `agents/research/git-history-analyzer.md`

**Invocation pattern:**

```
Task git-history-analyzer("Trace the evolution of {file_or_pattern}")
```

**Criticality:** Medium
**Difficulty:** Medium — git-command-heavy agent

---

#### 11. `design-implementation-reviewer`

**What it does:** Pixel-fidelity reviewer that compares live UI against design specs. Captures implementation screenshots via `agent-browser` at multiple viewports and interactive states, retrieves design specs, conducts systematic comparison (typography, colors, spacing, responsiveness, accessibility), provides actionable CSS fixes.

**How it's wired in the plugin:**

- **Standalone invocation only** — not hard-wired into commands
- Can be added to `review_agents` config
- Uses proactively after writing/modifying HTML/CSS/React components

**Plugin file:** `agents/design/design-implementation-reviewer.md`

**Invocation pattern:**

```
Task design-implementation-reviewer("Compare implementation at {url} against design spec: {spec}")
```

**Criticality:** Medium (complements our `/define-design` and `ui-ux-architect`)
**Difficulty:** Medium — depends on `agent-browser`

---

### Skills (→ BuiltForm destination)

#### 12. `agent-browser`

**What it does:** CLI browser automation using Vercel's headless Chromium. Ref-based element selection (`@e1`, `@e2`). Commands: navigate, snapshot (accessibility tree with refs), click, fill, select, scroll, screenshot, PDF, wait, semantic locators, parallel sessions via `--session`.

**How it's wired in the plugin:**

- **Foundation dependency** for 6+ other capabilities: `test-browser`, `feature-video`, `bug-reproduction-validator`, `design-iterator`, `design-implementation-reviewer`, `figma-design-sync`
- Referenced in 13 files across the plugin

**Plugin file:** `skills/agent-browser/SKILL.md`

**Install:** `npm install -g agent-browser && agent-browser install`

**Criticality:** High (prerequisite for browser testing and design verification)
**Difficulty:** Easy — well-documented npm package, skill is a usage guide

---

#### 13. `git-worktree`

**What it does:** Manages git worktrees for isolated parallel development. Creates from main, lists, switches, cleans up. Auto-copies `.env` files. Stores worktrees in `.worktrees/` directory.

**How it's wired in the plugin:**

- **`/workflows:review`** — offers worktree if not on target branch
- **`/workflows:work`** — always offers worktree vs. live branch choice
- Includes a bash script: `scripts/worktree-manager.sh` (338 lines) handling create/list/switch/copy-env/cleanup

**Plugin file:** `skills/git-worktree/SKILL.md` + `scripts/worktree-manager.sh`

**Criticality:** Medium
**Difficulty:** Easy — git-native feature, script is portable

---

#### 14. `resolve-pr-parallel`

**What it does:** Resolves all unresolved PR review comments using parallel sub-agents. Fetches unresolved threads via GraphQL, groups by type, spawns one `pr-comment-resolver` per thread, commits, resolves threads via GraphQL mutation, verifies.

**How it's wired in the plugin:**

- **`/resolve_parallel` command** — invokes this skill's pattern
- Includes two helper scripts:
  - `scripts/get-pr-comments` (68 lines) — GraphQL query via `gh api graphql` to fetch unresolved threads
  - `scripts/resolve-pr-thread` (24 lines) — GraphQL mutation via `gh api graphql` to resolve a thread

**Plugin file:** `skills/resolve-pr-parallel/SKILL.md` + `scripts/get-pr-comments` + `scripts/resolve-pr-thread`

**Criticality:** High
**Difficulty:** Medium — needs GraphQL scripts (provided by plugin)

---

#### 15. `gemini-imagegen`

**What it does:** Image generation/editing via Google Gemini API. Text-to-image, editing with reference images, multi-turn refinement, custom aspect ratios (1:1, 16:9, 9:16, 21:9), resolutions (1K-4K).

**How it's wired in the plugin:**

- **Standalone skill** — triggered by description matching
- Includes 5 Python scripts: `generate_image.py`, `edit_image.py`, `compose_images.py`, `multi_turn_chat.py`, `gemini_images.py`

**Plugin file:** `skills/gemini-imagegen/SKILL.md` + `scripts/*.py` + `requirements.txt`

**Dependencies:** `GEMINI_API_KEY`, Python, `google-genai>=1.0.0`, `Pillow>=10.0.0`

**Criticality:** Low
**Difficulty:** Easy — self-contained with provided scripts

---

#### 16. `agent-native-architecture`

**What it does:** Comprehensive design guide for building agent-first applications. 5 core principles (Parity, Granularity, Composability, Emergent Capability, Improvement Over Time). Interactive intake menu with 13 options routing to 14 reference documents covering architecture patterns, MCP tool design, system prompt design, testing, mobile patterns, self-modification, and more.

**How it's wired in the plugin:**

- **`/agent-native-audit` command** — audits apps against these principles
- **`/deepen-plan`** — spawns sub-agent with this skill for agent/tool plan sections
- Includes 14 reference documents totaling ~175KB

**Plugin file:** `skills/agent-native-architecture/SKILL.md` + `references/*.md` (14 files)

**Criticality:** Low
**Difficulty:** Medium — large reference corpus to port

---

### Commands (→ LaunchPad destination)

#### 17. `test-browser`

**What it does:** E2E browser tests on PR-affected pages. Verifies `agent-browser` installation, maps changed files to routes (Next.js patterns), tests each page with snapshots/interactions/screenshots, pauses for human verification on OAuth/payment flows, handles failures with fix-now/create-todo/skip.

**How it's wired in the plugin:**

- **`/lfg` and `/slfg`** — referenced as post-implementation test step
- **`/workflows:review`** — offered as optional browser testing step (Section 8)

**Plugin file:** `commands/test-browser.md`

**Invocation:** `/test-browser [PR number | branch name | 'current']`

**Dependencies:** `agent-browser` skill, `gh` CLI, running dev server

**Criticality:** High
**Difficulty:** Easy — command file references agent-browser

---

#### 18. `deepen-plan`

**What it does:** Enhances an existing plan with parallel per-section research. Parses plan, discovers ALL available skills and spawns sub-agents per match, searches `docs/solutions/` for learnings, launches per-section research agents (Explore + Context7 + WebSearch), runs ALL review agents in parallel (40+ agents is fine), synthesizes and enhances each section.

**How it's wired in the plugin:**

- **`/lfg` and `/slfg`** — referenced as plan enhancement step
- **`/workflows:plan`** — offered as follow-up after initial planning

**Plugin file:** `commands/deepen-plan.md`

**Invocation:** `/deepen-plan [path to plan file]`

**Dependencies:** Context7 MCP, WebSearch, all available skills/agents (dynamically discovered)

**Criticality:** Medium
**Difficulty:** Easy — command file, but needs adaptation for our plan format

---

#### 19. `feature-video`

**What it does:** Records video walkthrough of a feature for PR docs. Maps changed files to routes, plans shot list with user confirmation, records via agent-browser screenshots, converts to MP4+GIF via ffmpeg, uploads via rclone to R2, updates PR description.

**How it's wired in the plugin:**

- **`/lfg` and `/slfg`** — referenced as post-implementation documentation step

**Plugin file:** `commands/feature-video.md`

**Invocation:** `/feature-video [PR number | 'current'] [base URL]`

**Dependencies:** `agent-browser`, `ffmpeg`, `rclone` (R2), `gh` CLI

**Criticality:** Low
**Difficulty:** Medium — multiple external tool dependencies

---

#### 20. `changelog`

**What it does:** Generates changelogs from recent merges. Analyzes PRs merged in last 24h (daily) or 7 days (weekly). Formats as: Breaking Changes, New Features, Bug Fixes, Other Improvements, Shoutouts. Supports optional Discord webhook posting.

**How it's wired in the plugin:**

- **Standalone command** — not part of any automated workflow

**Plugin file:** `commands/changelog.md`

**Invocation:** `/changelog [daily | weekly | number of days]`

**Dependencies:** `gh` CLI

**Criticality:** Low
**Difficulty:** Easy — simple command file

---

#### 21. `resolve_todo_parallel` / `resolve_parallel`

**What it does:** Two related commands. `resolve_parallel` resolves code TODO comments in parallel. `resolve_todo_parallel` resolves file-based todos from `todos/*.md`. Both spawn one `pr-comment-resolver` agent per item.

**How it's wired in the plugin:**

- **`/lfg` and `/slfg`** — referenced as resolution steps
- **`/workflows:review`** — available for review resolution
- **`/triage` command** — references for triage resolution

**Plugin files:** `commands/resolve_parallel.md` + `commands/resolve_todo_parallel.md`

**Dependencies:** `pr-comment-resolver` agent, TodoWrite tool, Git

**Criticality:** Medium (resolve_parallel is High for PR workflow)
**Difficulty:** Medium — needs the `pr-comment-resolver` agent first

---

## What's Already Covered

These CE plugin capabilities have internal equivalents:

| CE Capability                    | LaunchPad/BuiltForm Equivalent                   | Assessment                                                     |
| -------------------------------- | ------------------------------------------------ | -------------------------------------------------------------- |
| `brainstorming` skill            | `/define-product`, `/shape-section`              | Ours is more structured                                        |
| `create-agent-skills` skill      | `creating-skills` (7-phase Meta-Skill Forge)     | **Ours is superior**                                           |
| `document-review` skill          | `/update-spec`                                   | Different approach, same intent                                |
| `frontend-design` skill          | `/define-design` + BuiltForm's `frontend-design` | **Ours is deeper** (BuiltForm)                                 |
| `workflows:brainstorm`           | `/shape-section` + `/define-product`             | Covered                                                        |
| `workflows:plan`                 | `/pnf`                                           | Covered (ours integrates section registry)                     |
| `workflows:work`                 | `/inf` + `/implement_plan`                       | Covered                                                        |
| `workflows:review`               | `/review_code`                                   | Covered (but dispatches fewer agents — **gap in agent count**) |
| `workflows:compound`             | `/memory-report`                                 | Both capture learnings                                         |
| `repo-research-analyst`          | `codebase-analyzer`                              | Covered                                                        |
| `learnings-researcher`           | `docs-analyzer`                                  | Covered                                                        |
| `pattern-recognition-specialist` | `codebase-pattern-finder`                        | Covered                                                        |
| `framework-docs-researcher`      | `web-search-researcher`                          | Covered                                                        |
| `spec-flow-analyzer`             | `/pnf` gap detection                             | Covered                                                        |
| `lint` workflow agent            | Quality gates in `/commit`                       | Covered                                                        |
| `skill-evaluator` (ours)         | No CE equivalent                                 | **We're ahead**                                                |

---

## What's Not Applicable

Skip these entirely — wrong language/company:

| CE Capability            | Why Skip                            |
| ------------------------ | ----------------------------------- |
| `dhh-rails-style`        | Ruby/Rails                          |
| `dhh-rails-reviewer`     | Ruby/Rails                          |
| `kieran-rails-reviewer`  | Ruby/Rails                          |
| `kieran-python-reviewer` | Python                              |
| `dspy-ruby`              | Ruby                                |
| `ankane-readme-writer`   | Ruby gem style                      |
| `andrew-kane-gem-writer` | Ruby                                |
| `every-style-editor`     | Every-company-specific              |
| `rclone`                 | Cloud sync, not core                |
| `figma-design-sync`      | Figma API dependent, no Figma usage |
| `setup` skill            | Plugin infrastructure               |
| `report-bug` command     | Plugin-specific                     |
| `deploy-docs` command    | Plugin-specific                     |

---

## Implementation Roadmap

### Phase 1: Review Agent Suite (Wire into `/review_code`)

**Destination:** LaunchPad `agents/` directory
**Wiring point:** Update `/review_code` command to dispatch these in parallel

| Item | Agent                        | Priority | Est. Effort         |
| ---- | ---------------------------- | -------- | ------------------- |
| 1    | `security-sentinel`          | Critical | 1 agent file + wire |
| 2    | `kieran-typescript-reviewer` | High     | 1 agent file + wire |
| 3    | `performance-oracle`         | High     | 1 agent file + wire |
| 4    | `code-simplicity-reviewer`   | Medium   | 1 agent file + wire |
| 5    | `architecture-strategist`    | Medium   | 1 agent file + wire |

**Also needed:** A config mechanism (like CE's `compound-engineering.local.md`) to let downstream projects declare which review agents to run. Alternatively, detect tech stack from `package.json`/`Gemfile` presence.

### Phase 2: Database Review Agents (Conditional in `/review_code`)

**Destination:** LaunchPad `agents/` directory
**Wiring point:** Conditional dispatch in `/review_code` when PR touches Prisma schema/migrations

| Item | Agent                     | Priority | Est. Effort                |
| ---- | ------------------------- | -------- | -------------------------- |
| 6    | `schema-drift-detector`   | High     | Adapt from Rails to Prisma |
| 7    | `data-integrity-guardian` | High     | 1 agent file + wire        |
| 8    | `data-migration-expert`   | Medium   | 1 agent file + wire        |

### Phase 3: PR Workflow (New command + agent)

**Destination:** LaunchPad `agents/` + `commands/` directories

| Item | Capability                  | Priority | Est. Effort                      |
| ---- | --------------------------- | -------- | -------------------------------- |
| 9    | `pr-comment-resolver` agent | High     | 1 agent file                     |
| 10   | `/resolve-parallel` command | High     | 1 command file + GraphQL scripts |

### Phase 4: Browser Testing (New skill + command)

**Destination:** BuiltForm (skill), LaunchPad (command)

| Item | Capability              | Priority | Est. Effort                |
| ---- | ----------------------- | -------- | -------------------------- |
| 11   | `agent-browser` skill   | High     | Port SKILL.md to BuiltForm |
| 12   | `/test-browser` command | High     | 1 command file             |

### Phase 5: Plan Enhancement + Utility Commands

**Destination:** LaunchPad `commands/` directory

| Item | Capability                             | Priority | Est. Effort          |
| ---- | -------------------------------------- | -------- | -------------------- |
| 13   | `/deepen-plan` command                 | Medium   | 1 command file       |
| 14   | `git-worktree` skill                   | Medium   | Skill + shell script |
| 15   | `design-implementation-reviewer` agent | Medium   | 1 agent file         |
| 16   | `bug-reproduction-validator` agent     | Medium   | 1 agent file         |
| 17   | `git-history-analyzer` agent           | Medium   | 1 agent file         |

### Phase 6: Nice-to-Haves

| Item | Capability                            | Priority | Est. Effort            |
| ---- | ------------------------------------- | -------- | ---------------------- |
| 18   | `julik-frontend-races-reviewer` agent | Medium   | 1 agent file           |
| 19   | `/changelog` command                  | Low      | 1 command file         |
| 20   | `/feature-video` command              | Low      | 1 command file         |
| 21   | `gemini-imagegen` skill               | Low      | Skill + Python scripts |

---

## Key Wiring Patterns to Replicate

### Pattern 1: Parallel Review Agent Dispatch

The CE plugin's `/workflows:review` reads a config, then spawns all agents in parallel:

```
# Pseudocode from CE's review workflow
for agent in review_agents:
    Task {agent}("Review these changes: {diff_context}")
# Wait for all, then synthesize
```

**Our equivalent:** Update `/review_code` to accept a `review_agents` list (from project config or detected stack) and dispatch them in parallel via the Agent tool.

### Pattern 2: Conditional Database Agent Chain

```
# Pseudocode from CE's review workflow
if changed_files match "prisma/schema.prisma" OR "prisma/migrations/*":
    Task schema-drift-detector(...)     # FIRST
    Task data-migration-expert(...)     # SECOND
    Task data-integrity-guardian(...)   # THIRD (parallel with #2)
```

### Pattern 3: Parallel Comment Resolution

```
# From /resolve_parallel
unresolved = fetch_unresolved_threads(PR_number)  # GraphQL
for thread in unresolved:
    Task pr-comment-resolver("Resolve: {thread.body}\nFile: {thread.path}")
# Commit all fixes, then resolve threads via GraphQL mutation
```

### Pattern 4: Plan Deepening (Per-Section Research)

```
# From /deepen-plan
for section in plan.sections:
    Task Explore("Research best practices for: {section.title}")
    Task framework-docs-researcher("Find docs for: {section.technologies}")
    Task git-history-analyzer("Trace history of: {section.affected_files}")
# Merge research into each section
```

---

## Dependencies to Install

Before implementing, these external tools are needed:

| Tool             | Required For             | Install                                           |
| ---------------- | ------------------------ | ------------------------------------------------- |
| `agent-browser`  | Items 11, 12, 15, 16, 20 | `npm i -g agent-browser && agent-browser install` |
| `gh` CLI         | Items 10, 12, 17, 19, 20 | Already installed (used by `/commit`)             |
| `ffmpeg`         | Item 20 only             | `brew install ffmpeg`                             |
| `GEMINI_API_KEY` | Item 21 only             | Environment variable                              |

---

## Next Steps

1. Decide on config mechanism: per-project `launchpad.local.md` with `review_agents` YAML, or auto-detect from tech stack
2. Start with Phase 1 (review agents) — highest ROI, wires into existing `/review_code`
3. Port the `agent-browser` skill to BuiltForm and `/test-browser` command to LaunchPad in parallel
4. Progressively work through phases, validating each capability before moving to next
