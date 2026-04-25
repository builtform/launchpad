---
name: lp-build
description: Meta-orchestrator for autonomous execution pipeline. Chains /lp-inf → /lp-review → /lp-resolve-todo-parallel → /lp-test-browser → /lp-ship → compound-learning.sh.
---

# /lp-build

Autonomous execution pipeline orchestrator. Resolves target from section registry status and chains through implementation → review → resolve → test → ship → learn.

**Arguments:** `$ARGUMENTS` (optional section name)

---

## Step 0: Prerequisite & Capability Check

`/lp-build` executes commands autonomously. Before any code runs, verify the state this requires.

### 0.1 — Autonomous-mode acknowledgment

`.launchpad/autonomous-ack.md` MUST exist. Its presence is a social / review signal, not a cryptographic gate — any contributor with commit access can add it — but the file being present in the repo makes autonomous-execution authorization visible in PR diffs and git blame.

IF `.launchpad/autonomous-ack.md` does NOT exist: refuse with

> "Autonomous execution requires `.launchpad/autonomous-ack.md` to exist. This file is a visible signal that the team has acknowledged the risks of autonomous code execution. Create it with a one-paragraph acknowledgment and commit it, then re-run `/lp-build`."

Do not offer to auto-create this file. The user / team must author it consciously.

### 0.2 — Config validation + CI override check

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=<any>` once as a preflight — it validates `LP_CONFIG_REVIEWED` against the current canonical commands hash and refuses loudly on mismatch. If the preflight returns exit 2, stop immediately with the error printed by the runner.

Load `.launchpad/config.yml` via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-config-loader.py`. Required fields:

- `commands.test` — array (may be empty to skip)
- `commands.typecheck` — array (empty = skip)
- `commands.lint` — array
- `commands.build` — array

If the config itself is missing, refuse with

> "`.launchpad/config.yml` not found. Run `/lp-define` first to seed it from your detected stack."

### 0.3 — Integrity check (section + ack same-commit)

Using `${CLAUDE_PLUGIN_ROOT}/scripts/plugin_stack_adapters/autonomous_guard.py` (`section_added_with_ack`), verify that the target section was NOT introduced to `SECTION_REGISTRY.md` in the same commit as `.launchpad/autonomous-ack.md`. If it was, refuse with

> "This section was added to the registry in the same commit that introduced `.launchpad/autonomous-ack.md`. That's the exact pattern a hostile PR would use to bypass review. Refusing autonomous build. Verify the section spec is legitimate and have the ack file predate the section, then retry."

### 0.4 — Audit log entry (opens the forensic trail)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-audit-log.py --command=lp-build`. This appends one line to `.launchpad/audit.log` recording:

- ISO-8601 UTC timestamp
- Git user (repo-local `user.email` first, then `user.name`, then $USER)
- Short HEAD commit SHA
- Content hash of `commands:` section (survives rebase/amend/squash — NOT the commit SHA)
- The invoking command name

Gitignored by default. Teams who want PR visibility can opt in via `audit: { committed: true }` in `config.yml` (the `.gitignore` line is manually removed at that point — flipping the flag doesn't auto-remove).

### 0.5 — Pipeline skip gate for test_browser

Load `pipeline.build.test_browser` from `config.yml`. If it's `skipped`, Step 3 (/lp-test-browser) is skipped entirely. Backend-only projects bypass browser testing by configuration, not by ad-hoc detection.

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

| Status                             | Guard Result                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------- |
| `approved` (with `approved_at`)    | → Step 1 (inf)                                                                    |
| `approved` (without `approved_at`) | **REFUSE:** "Plan approval metadata missing. Re-run /lp-plan for human approval." |
| `reviewed`                         | → Step 4 (ship) — recovery path                                                   |
| Any other status                   | **REFUSE:** "Run /lp-plan first"                                                  |

### CASE A: Named target → registry lookup

### CASE B: No argument → find next `approved` section in registry

---

## Step 1: /lp-inf [explicit-plan-path]

- Get plan path by expanding `paths.plans_file_pattern` from `.launchpad/config.yml` (default `docs/tasks/sections/{section_name}-plan.md`) with the section name from the approved section entry.
- Run `/lp-inf --plan path/to/plan.md`
- The `--plan` flag skips `/lp-inf`'s own registry check
- Calls `build.sh` → execution loop → quality sweep

## Step 2: /lp-review

- Run `/lp-review` (interactive mode — NOT `--headless`)
- Dispatches review agents from `.launchpad/agents.yml` (`review_agents`)
- IF section status = `designed`: also dispatch `review_design_agents`
- IF section status = `"design:skipped"`: skip `review_design_agents`
- IF `"design:skipped"` but diff contains UI-relevant files: emit P2 warning
- Read PR intent context for scoring
- Confidence scoring (0.60 threshold) → suppress FPs → deduplicate → P1/P2/P3
- Write `.harness/todos/` (findings above threshold only)
- Write `.harness/review-summary.md`
- IF zero findings above threshold: skip to Step 3

## Step 2.5: /lp-resolve-todo-parallel

- Run `/lp-resolve-todo-parallel`
- Groups overlapping files → sequential
- Max 5 concurrent resolver agents
- Post-execution scope validation
- Stage only reported files → commit "fix: resolve review findings"
- Commit is DURABLE (safe from crashes)

## Step 3: /lp-test-browser (auto-dispatched, self-scoping)

> **Skip gate:** if Step 0.5 determined `pipeline.build.test_browser: skipped`, bypass this step entirely and set registry status → `reviewed` from Step 2's results.

- Run `/lp-test-browser` — maps changed files to UI routes (max 15)
- Self-scoping: detects agent-browser CLI or Playwright MCP
- Graceful skip: no browser tool, no dev server, no UI routes → skip with note
- Tests routes (30s per route, 5min total) → writes findings to `.harness/todos/`
- Browser test findings are NOT resolved by a second `/lp-resolve-todo-parallel` — they proceed to `/lp-ship` and are included in the PR description for human review
- Set registry status → `reviewed` (code reviewed + browser tested)
- **NOTE:** If `/lp-test-browser` is skipped or unavailable, `/lp-review` (Step 2) writes `reviewed` status instead.
- **Proceed to Step 4 regardless of findings** — browser failures are informational, not blocking

## Step 4: /lp-ship

- Run `/lp-ship`
- IF PR already exists: skip PR creation, proceed to monitoring
- Stage, quality gates, auto-fix, commit, push, PR creation
- PR monitoring (CI + Codex + conflicts)
- **STOPS at "all gates green" — NEVER merges**

## Step 5: /lp-learn

- Run `/lp-learn` — captures learnings from the build session
- Loads compound-docs skill, spawns 5 inline research sub-agents in parallel
- Writes structured solution doc to `docs/solutions/[category]/`
- Non-critical — failure here doesn't block shipping
- Fallback: if `/lp-learn` fails, run `bash scripts/compound/compound-learning.sh` (basic extraction)

## Step 6: Report

- Set registry status → `built` (if section)
- Print summary: what was built, review findings, PR URL
- Run `/lp-regenerate-backlog --stage` to update the project backlog
- "If the PR receives review comments, run /lp-resolve-pr-comments to address them."
