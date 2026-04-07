---
name: harness:build
description: Meta-orchestrator for autonomous execution pipeline. Chains /inf → /review → /resolve_todo_parallel → /test-browser → /ship → compound-learning.sh.
---

# /harness:build

Autonomous execution pipeline orchestrator. Resolves target from section registry status and chains through implementation → review → resolve → test → ship → learn.

**Arguments:** `$ARGUMENTS` (optional section name)

---

## Guard: Status Check + Resolve Target

1. Read section spec file's YAML frontmatter
2. Validate registry integrity (see below)

### Registry Integrity Validation

| Status     | Expected Artifacts                               |
| ---------- | ------------------------------------------------ |
| `designed` | Design artifacts in `.harness/design-artifacts/` |
| `planned`  | Plan file exists                                 |
| `hardened` | Hardening notes section exists in plan           |
| `approved` | `approved_at` field present + plan file exists   |
| `reviewed` | `.harness/review-summary.md` exists              |

### Status Routing

| Status                             | Guard Result                                                                           |
| ---------------------------------- | -------------------------------------------------------------------------------------- |
| `approved` (with `approved_at`)    | → Step 1 (inf)                                                                         |
| `approved` (without `approved_at`) | **REFUSE:** "Plan approval metadata missing. Re-run /harness:plan for human approval." |
| `reviewed`                         | → Step 4 (ship) — recovery path                                                        |
| Any other status                   | **REFUSE:** "Run /harness:plan first"                                                  |

### CASE A: Named target → registry lookup

### CASE B: No argument → find next `approved` section in registry

---

## Step 1: /inf [explicit-plan-path]

- Get plan path from section's plan doc (identified by `approved` status)
- Run `/inf --plan path/to/plan.md`
- The `--plan` flag skips `/inf`'s own registry check
- Calls `build.sh` → execution loop → quality sweep

## Step 2: /review

- Run `/review` (interactive mode — NOT `--headless`)
- Dispatches review agents from `.launchpad/agents.yml` (`review_agents`)
- IF section status = `designed`: also dispatch `review_design_agents`
- IF section status = `"design:skipped"`: skip `review_design_agents`
- IF `"design:skipped"` but diff contains UI-relevant files: emit P2 warning
- Read PR intent context for scoring
- Confidence scoring (0.60 threshold) → suppress FPs → deduplicate → P1/P2/P3
- Write `.harness/todos/` (findings above threshold only)
- Write `.harness/review-summary.md`
- IF zero findings above threshold: skip to Step 3

## Step 2.5: /resolve_todo_parallel

- Run `/resolve_todo_parallel`
- Groups overlapping files → sequential
- Max 5 concurrent resolver agents
- Post-execution scope validation
- Stage only reported files → commit "fix: resolve review findings"
- Commit is DURABLE (safe from crashes)

## Step 3: /test-browser (auto-dispatched, self-scoping)

- Run `/test-browser` — maps changed files to UI routes (max 15)
- Self-scoping: detects agent-browser CLI or Playwright MCP
- Graceful skip: no browser tool, no dev server, no UI routes → skip with note
- Tests routes (30s per route, 5min total) → writes findings to `.harness/todos/`
- Browser test findings are NOT resolved by a second `/resolve_todo_parallel` — they proceed to `/ship` and are included in the PR description for human review
- Set registry status → `reviewed` (code reviewed + browser tested)
- **NOTE:** If `/test-browser` is skipped or unavailable, `/review` (Step 2) writes `reviewed` status instead.
- **Proceed to Step 4 regardless of findings** — browser failures are informational, not blocking

## Step 4: /ship

- Run `/ship`
- IF PR already exists: skip PR creation, proceed to monitoring
- Stage, quality gates, auto-fix, commit, push, PR creation
- PR monitoring (CI + Codex + conflicts)
- **STOPS at "all gates green" — NEVER merges**

## Step 5: /learn

- Run `/learn` — captures learnings from the build session
- Loads compound-docs skill, spawns 5 inline research sub-agents in parallel
- Writes structured solution doc to `docs/solutions/[category]/`
- Non-critical — failure here doesn't block shipping
- Fallback: if `/learn` fails, run `bash scripts/compound/compound-learning.sh` (basic extraction)

## Step 6: Report

- Set registry status → `built` (if section)
- Print summary: what was built, review findings, PR URL
- Run `/regenerate-backlog --stage` to update the project backlog
- "If the PR receives review comments, run /resolve-pr-comments to address them."
