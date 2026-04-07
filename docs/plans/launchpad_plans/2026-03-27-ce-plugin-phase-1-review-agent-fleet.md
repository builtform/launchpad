# Phase 1: Review Agent Fleet

**Date:** 2026-03-27
**Updated:** 2026-04-07 (v7 — CE v2.61.0 impact: added testing-reviewer as 7th default agent for behavioral change test coverage enforcement; v6 — Phase 10 cascading changes: review_copy_agents, review_design_agents count; v5 — reviewer fixes; v4 — meta-orchestrator split alignment; v3 — post-review: cut pattern-recognition-specialist, added OWASP gaps, centralized harden-plan agents, scoped reads, observation contract)
**Depends on:** Phase 0 (review agent config system)
**Branch:** `feat/review-agent-fleet`
**Status:** Plan — v7.1 (cross-phase sync: agents.yml template updated with harden_document_agents key, init-project.sh prose fixed to 7 defaults)

---

## Decisions (All Finalized — synced with Phase 0 v4)

| Decision                 | Answer                                                                                                                                                                                                                     |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Total agents             | 10 review agents (7 default + 3 opt-in). `pattern-recognition-specialist` cut (redundant with pattern-finder + architecture-strategist). `testing-reviewer` added (v7, from CE v2.61.0 — behavioral change test coverage). |
| Model                    | `model: inherit` for all agents (model-agnostic, per Phase 0)                                                                                                                                                              |
| Review command           | `/review` (flat at `.claude/commands/review.md`)                                                                                                                                                                           |
| Agent config             | `.launchpad/agents.yml` — `review_agents` + new `harden_plan_agents` + `harden_plan_conditional_agents` keys                                                                                                               |
| Simplicity pass          | Single pass — all reviewers run once equally                                                                                                                                                                               |
| Simplicity scope         | Read diff + 1-hop imports only. Suggest changes only to changed files.                                                                                                                                                     |
| Out-of-scope findings    | Written as observations to `.harness/observations/` by `/review` (not by the agent directly)                                                                                                                               |
| Protected paths          | Scope + focus + protected path list (expanded with security-sensitive paths)                                                                                                                                               |
| Observations directory   | `.harness/observations/` — created in Phase 0, populated starting Phase 1                                                                                                                                                  |
| Agent reads              | Scoped: diff + changed files + directly imported files (1-hop). NOT entire codebase. Use Grep/Glob for broader pattern checks.                                                                                             |
| Downstream customization | Downstream adds `agents.yml` to `.launchpad/init-touched-files` after customizing opt-in agents                                                                                                                            |

---

## Purpose

Create 10 specialized review agents. 7 run by default during `/review`, 3 are opt-in. These expand the review fleet from `pattern-finder` alone to a full multi-agent system. After Phase 1:

- Every `/harness:build` run gets security, type safety, performance, simplicity, architecture, and **test coverage** analysis
- `/harden-plan --lightweight` dispatches 3 real agents (up from 1)
- `/harden-plan --full` dispatches 6 real agents (up from 1)

---

## Architecture: How These Agents Fit

### In `/review` (code review — from `agents.yml`)

```
/review (from Phase 0)
  │
  ├── Read .launchpad/agents.yml + .harness/harness.local.md
  ├── Get changed files (diff scope)
  ├── Pre-dispatch secret scan
  │
  ├── Dispatch ALL review_agents in parallel (model: inherit):
  │   ├── pattern-finder              (existing, from Phase 0)
  │   ├── security-auditor            (NEW)
  │   ├── kieran-foad-ts-reviewer     (NEW)
  │   ├── performance-auditor         (NEW)
  │   ├── code-simplicity-reviewer    (NEW)
  │   ├── architecture-strategist     (NEW)
  │   └── testing-reviewer            (NEW — v7, behavioral change test coverage)
  │
  │   OPT-IN (if project adds to review_agents):
  │   ├── deployment-verification-agent (NEW)
  │   ├── frontend-races-reviewer     (NEW)
  │   └── kieran-foad-python-reviewer (NEW)
  │
  ├── IF Prisma changes: dispatch review_db_agents (Phase 2)
  │
  ├── Synthesize findings → deduplicate → P1/P2/P3
  │
  └── Write to .harness/todos/ + .harness/observations/
```

### In `/harden-plan` (plan review — from `agents.yml` harden keys)

```
/harden-plan (from Phase 0)
  │
  ├── Read agents.yml harden_plan_agents + harden_plan_conditional_agents
  │
  ├── ALWAYS (lightweight + full):
  │   ├── security-auditor            (NEW) ← was placeholder
  │   ├── performance-auditor         (NEW) ← was placeholder
  │   ├── pattern-finder              (existing)
  │   └── spec-flow-analyzer          [Phase 3] — still placeholder
  │
  └── CONDITIONAL (full only, from harden_plan_conditional_agents):
      ├── architecture-strategist     (NEW) ← was placeholder
      ├── code-simplicity-reviewer    (NEW) ← was placeholder
      ├── frontend-races-reviewer     (NEW) ← was placeholder
      └── schema-drift-detector       [Phase 2] — still placeholder
```

---

## Agent Definitions

### 1. `security-auditor`

**File:** `.claude/agents/review/security-auditor.md`
**CE source:** `security-sentinel` (114 lines)
**Adaptation:** Strip Rails/Ruby, add TypeScript/Hono/Prisma/Next.js scanning
**Also used by:** `/harden-plan` (always)

**Frontmatter:**

```yaml
---
name: security-auditor
description: Performs security audits for vulnerabilities, input validation, auth/authz, hardcoded secrets, and OWASP compliance in TypeScript/Next.js/Hono applications.
model: inherit
---
```

**Core scanning protocol (10 areas — full OWASP Top 10 2021 coverage):**

1. **A01: Broken Access Control** — Map all Hono routes + auth middleware. Check Next.js middleware. Verify resource-level authorization. Check for missing auth on API endpoints.
2. **A02: Cryptographic Failures** — Check password hashing, token generation, TLS enforcement, sensitive data encryption at rest.
3. **A03: Injection** — Scan for `$queryRaw`, `$executeRaw`, `$queryRawUnsafe`, `$executeRawUnsafe`, `$runCommandRaw`. Check string interpolation in DB calls. Verify Zod validation on all inputs.
4. **A04: Insecure Design** — Check for rate limiting on auth endpoints, abuse-case modeling, business logic flaws.
5. **A05: Security Misconfiguration** — CORS origin whitelisting (Hono default is permissive), security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP), Vercel deployment settings.
6. **A06: Vulnerable Components** — Flag `pnpm audit` as recommended check. Note any known-vulnerable dependency patterns.
7. **A07: Auth Failures** — Session management (expiry, rotation), CSRF protection on state-changing routes, credential stuffing protection.
8. **A08: Data Integrity** — Check for unsigned dependencies, CI pipeline integrity, `dangerouslySetInnerHTML`, unescaped user content.
9. **A09: Logging & Monitoring** — Check that security events are logged. Verify PII not in logs. Check error responses don't leak internals.
10. **A10: SSRF** — Scan for unvalidated URLs passed to server-side `fetch()`. Check URL allowlists for external API calls.

**Output:** 4-part report (Executive Summary, Detailed Findings with file:line, Risk Matrix P1/P2/P3, Remediation Roadmap).

---

### 2. `kieran-foad-ts-reviewer`

**File:** `.claude/agents/review/kieran-foad-ts-reviewer.md`
**CE source:** `kieran-typescript-reviewer` (124 lines)
**Adaptation:** Strip persona framing, add project doc references

**Frontmatter:**

```yaml
---
name: kieran-foad-ts-reviewer
description: Reviews TypeScript code with an extremely high quality bar for type safety, modern patterns, and maintainability.
model: inherit
---
```

**10 review principles:** Strict on existing code, pragmatic on new. No `any` without justification. 5-second naming rule. Module extraction signals. Import organization. Modern TS (satisfies, const type params). "Duplication > Complexity."

**Project-awareness:** Reads `FRONTEND_GUIDELINES.md` and `BACKEND_STRUCTURE.md` when they exist. Project conventions take precedence.

**Output:** Structured findings with file:line, P1/P2/P3 severity, concrete improvement examples.

---

### 3. `performance-auditor`

**File:** `.claude/agents/review/performance-auditor.md`
**CE source:** `performance-oracle` (137 lines)
**Adaptation:** Strip ActiveRecord, add Prisma N+1, add Next.js frontend checks
**Also used by:** `/harden-plan` (always)

**Frontmatter:**

```yaml
---
name: performance-auditor
description: Analyzes code for performance bottlenecks, algorithmic complexity, database queries, memory usage, and scalability in TypeScript/Next.js/Hono/Prisma applications.
model: inherit
---
```

**6 dimensions:** Algorithmic complexity (Big O), database performance (Prisma N+1, missing indexes, unbounded findMany), memory management, caching opportunities, network optimization, frontend performance (bundle size, lazy loading, server vs client components).

**Benchmarks:** No O(n²) without justification, all queries indexed, <200ms API responses, <5KB bundle per feature.

**Output:** 5-section report (Summary, Critical Issues, Optimization Opportunities, Scalability Assessment, Actions).

---

### 4. `code-simplicity-reviewer`

**File:** `.claude/agents/review/code-simplicity-reviewer.md`
**CE source:** `code-simplicity-reviewer` (102 lines)
**Adaptation:** Add 3-layer safety, observations output, update paths
**Also used by:** `/harden-plan` (conditional — full only, IF 4+ phases)

**Frontmatter:**

```yaml
---
name: code-simplicity-reviewer
description: Final review pass to ensure code is as simple and minimal as possible. Identifies YAGNI violations and simplification opportunities within the current feature scope.
model: inherit
---
```

**3-Layer Safety:**

**Layer 1 — Scope:** May only suggest changes to files in the "Changed Files" list. Out-of-scope findings returned as observations (text output — `/review` writes the files).

**Layer 2 — Focus:** Only analyze `apps/` and `packages/`. Infrastructure files (`docs/`, `scripts/`, `.claude/`, `.harness/`) are excluded from YAGNI analysis.

**Layer 3 — Protected Paths:** Never flag for removal:

```
docs/plans/**, docs/solutions/**, docs/reports/**, docs/tasks/**
.harness/**, scripts/compound/*.md, scripts/compound/config.json
.claude/skills/*/references/**, .claude/agents/**
**/.gitkeep, *.template.md, prisma/**
.env*, middleware.ts, middleware.js
**/auth/**, **/api/auth/**
lefthook.yml, .husky/**
```

**6 review areas:** Analyze every line, simplify complex logic, remove redundancy, challenge abstractions, apply YAGNI, optimize for readability.

**Output — two types:**

- In-scope findings → returned as P1/P2/P3 text (written to `.harness/todos/` by `/review`)
- Out-of-scope findings → returned as observation text (written to `.harness/observations/` by `/review`)

---

### 5. `architecture-strategist`

**File:** `.claude/agents/review/architecture-strategist.md`
**CE source:** `architecture-strategist` (67 lines)
**Adaptation:** SOLID examples for TypeScript/Next.js/Hono. Add Turborepo/monorepo awareness.
**Also used by:** `/harden-plan` (conditional — full only, IF multi-package)

**Frontmatter:**

```yaml
---
name: architecture-strategist
description: Analyzes code changes from an architectural perspective for SOLID compliance, coupling, cohesion, and design integrity in TypeScript monorepos.
model: inherit
---
```

**Review areas:** SOLID principles (TypeScript), coupling analysis (package boundaries), cohesion assessment, circular dependency detection, API contract stability (`packages/shared` types), monorepo boundary enforcement.

**Output:** Architecture overview, change assessment, compliance check, risk analysis, recommendations. P1/P2/P3.

---

### 6. `deployment-verification-agent` (opt-in)

**File:** `.claude/agents/review/deployment-verification-agent.md`
**CE source:** `deployment-verification-agent` (174 lines)
**Adaptation:** Prisma migrations, Vercel deployment awareness

**Frontmatter:**

```yaml
---
name: deployment-verification-agent
description: Produces Go/No-Go deployment checklists with verification queries, rollback procedures, and monitoring plans.
model: inherit
---
```

**When to enable:** Projects doing frequent deployments or touching production data.

---

### 7. `frontend-races-reviewer` (opt-in)

**File:** `.claude/agents/review/frontend-races-reviewer.md`
**CE source:** `julik-frontend-races-reviewer` (221 lines)
**Adaptation:** Replace Stimulus/Turbo with React/Next.js patterns
**Also used by:** `/harden-plan` (conditional — full only, IF async UI)

**Frontmatter:**

```yaml
---
name: frontend-races-reviewer
description: Reviews JavaScript and React code for race conditions, timing issues, and DOM lifecycle problems.
model: inherit
---
```

**When to enable:** Projects with complex async UI, real-time features, concurrent data operations.

---

### 8. `kieran-foad-python-reviewer` (opt-in)

**File:** `.claude/agents/review/kieran-foad-python-reviewer.md`
**CE source:** `kieran-python-reviewer` (133 lines)
**Adaptation:** Strip CE-specific references, add project doc awareness

**Frontmatter:**

```yaml
---
name: kieran-foad-python-reviewer
description: Reviews Python code with high quality bar for type hints, Pythonic patterns, and maintainability.
model: inherit
---
```

**When to enable:** Projects with Python code.

---

### 9. `testing-reviewer`

**File:** `.claude/agents/review/testing-reviewer.md`
**CE source:** `testing-reviewer` (CE v2.60.0+ — new agent with 5-check protocol)
**Adaptation:** Strip Rails test patterns, add Vitest/Jest/React Testing Library awareness
**Why added (v7):** CE's biggest insight from v2.60.0: "testing addressed" replaces binary "tests pass". Existing tests passing says nothing about whether new behavior is tested. This agent catches the gap.

**Frontmatter:**

```yaml
---
name: testing-reviewer
description: Reviews code changes to ensure behavioral changes have corresponding test coverage. Flags new branches, state mutations, and API changes with zero test additions.
model: inherit
---
```

**5-check protocol:**

1. **Test file discovery:** Before reviewing, find all existing test files related to the changed files. Map `src/foo.ts` → `src/foo.test.ts`, `__tests__/foo.test.ts`, `tests/foo.spec.ts`. Report what exists.

2. **Behavioral change detection:** Identify all behavioral changes in the diff:
   - New conditional branches (if/else, switch, ternary)
   - New state mutations (useState, store updates, database writes)
   - New/modified API endpoints (Hono routes, Next.js API routes, Server Actions)
   - New error paths (try/catch, error boundaries, validation failures)
   - New user-facing features (components, pages, form handlers)

3. **Test correspondence check:** For each behavioral change, verify a corresponding test exists or was added. A "corresponding test" must exercise the specific behavior, not just import the module.

4. **Gap classification:** For each untested behavioral change, classify as:
   - **P1 — Critical gap:** API endpoint with no test, auth logic with no test, data mutation with no test
   - **P2 — Important gap:** New UI branch with no test, error path with no test
   - **P3 — Minor gap:** Formatting logic, display-only changes

5. **"Testing addressed" assessment:** Final determination:
   - **Fully addressed:** All behavioral changes have corresponding tests
   - **Partially addressed:** Some gaps, classified above
   - **Not addressed:** Behavioral changes with zero test additions — flag as P1

**What this is NOT:**

- NOT a test quality reviewer (doesn't critique test implementation)
- NOT a coverage tool (doesn't measure line/branch coverage percentages)
- NOT prescriptive about test framework (works with Vitest, Jest, Playwright, any)

**Output:** Structured report with behavioral changes found, test mapping, gaps by priority, "testing addressed" assessment.

---

## Observation File Contract

Observations are out-of-scope findings from the simplicity reviewer. They are written by `/review` (not by the agent — agents return text, `/review` writes files).

**Filename:** `{id}-{description}.md` (same pattern as todos)

**Format:**

```yaml
---
status: observation
priority: p3
issue_id: "obs-{N}"
tags: [simplification]
observed_in: "path/to/file.ts"           # File path where issue was found
feature_scope: "auth, dashboard, api"     # Changed files list at time of review
---

## Observation

{Description of simplification opportunity}

## Why Not Actioned

Outside the current feature scope. Flagged for Phase 7 triage.
```

---

## Changes to `/review`

**Step 3 (Dispatch):**

- All agents receive: diff + changed files + files they directly import (1-hop) + review_context
- Agents use Grep/Glob for broader pattern checks — do NOT Read every file in the repo
- `code-simplicity-reviewer` additionally receives: "Changed Files: {list}. Suggest changes only to these files. Return observation text for anything outside this list."

**Step 6 (Write Outputs):**

- Standard findings → `.harness/todos/{id}-{description}.md`
- Observation text from simplicity reviewer → `.harness/observations/{id}-{description}.md`
- `/review` owns all file writes (agents return text only)

**Deduplication in Step 5 (Synthesize):**

- If multiple agents flag the same issue (same file:line, same root cause), merge into one finding
- Keep the most severe classification and the most specific remediation

---

## Changes to `.launchpad/agents.yml`

```yaml
# Code review agents — dispatched by /review
review_agents:
  - pattern-finder
  - security-auditor
  - kieran-foad-ts-reviewer
  - performance-auditor
  - code-simplicity-reviewer
  - architecture-strategist
  - testing-reviewer

# Conditional agents — only when diff touches Prisma files
review_db_agents: []

# Design review agents — dispatched when section status = "designed"
review_design_agents: [] # [Phase 10]

# Copy review agents — dispatched during design workflow
# Populated by downstream projects (e.g., BuiltForm adds copy-auditor in Phase 11)
review_copy_agents: [] # [Phase 10]

# Plan review agents — dispatched by /harden-plan (ALWAYS, both intensities)
harden_plan_agents:
  - pattern-finder
  - security-auditor
  - performance-auditor
  # - spec-flow-analyzer          # [Phase 3]

# Plan review conditional agents — dispatched by /harden-plan (FULL only)
harden_plan_conditional_agents:
  - architecture-strategist
  - code-simplicity-reviewer
  - frontend-races-reviewer
  # - schema-drift-detector       # [Phase 2]

# Document-review agents — dispatched by /harden-plan Step 3.5 [Phase 3 v7]
harden_document_agents: []

# Opt-in agents — not dispatched by default
# To enable for /review: move to review_agents
# To enable for /harden-plan: move to appropriate harden list
#   - deployment-verification-agent
#   - frontend-races-reviewer      # already in harden conditional
#   - kieran-foad-python-reviewer
```

---

## Changes to `/harden-plan`

Update `/harden-plan` (Phase 0 command) to read from `agents.yml` instead of hardcoded list:

```
Step 1: Read .launchpad/agents.yml → extract harden_plan_agents, harden_plan_conditional_agents
        Read .harness/harness.local.md (project context)
```

Remove hardcoded agent list from the command. The YAML is now the single source of truth.

---

## Changes to `init-project.sh`

Update the default `.launchpad/agents.yml` template to include all keys (review_agents with 7 defaults including testing-reviewer, review_db_agents empty, harden_plan_agents with 3, harden_plan_conditional_agents with 3, harden_document_agents empty).

---

## Verification Checklist

### Agents Created

- [ ] `.claude/agents/review/security-auditor.md` — `model: inherit`, 10 OWASP areas, no Rails/Ruby
- [ ] `.claude/agents/review/kieran-foad-ts-reviewer.md` — `model: inherit`, reads project docs
- [ ] `.claude/agents/review/performance-auditor.md` — `model: inherit`, Prisma N+1, no ActiveRecord
- [ ] `.claude/agents/review/code-simplicity-reviewer.md` — `model: inherit`, 3-layer safety
- [ ] `.claude/agents/review/architecture-strategist.md` — `model: inherit`, monorepo boundaries
- [ ] `.claude/agents/review/testing-reviewer.md` — `model: inherit`, 5-check protocol, behavioral change detection
- [ ] `.claude/agents/review/deployment-verification-agent.md` — `model: inherit`
- [ ] `.claude/agents/review/frontend-races-reviewer.md` — `model: inherit`, React patterns, no Stimulus
- [ ] `.claude/agents/review/kieran-foad-python-reviewer.md` — `model: inherit`, Python 3.10+, no Ruby

### Wiring

- [ ] `.launchpad/agents.yml` has 7 default `review_agents` (including testing-reviewer)
- [ ] `.launchpad/agents.yml` has `harden_plan_agents` key (3 agents)
- [ ] `.launchpad/agents.yml` has `harden_plan_conditional_agents` key (3 agents)
- [ ] `.launchpad/agents.yml` has 3 opt-in agents as comments
- [ ] `/review` dispatches all 7 default agents in parallel
- [ ] `/review` passes scoped reads (diff + 1-hop imports, not entire codebase)
- [ ] `/review` passes scope instruction to `code-simplicity-reviewer`
- [ ] `/review` writes observations to `.harness/observations/` (agent returns text, command writes file)
- [ ] `/review` deduplicates findings across agents in synthesis step
- [ ] `/harden-plan` reads from `agents.yml` keys (not hardcoded)
- [ ] `/harden-plan --lightweight` dispatches 3 real agents
- [ ] `/harden-plan --full` dispatches 6 real agents

### Agent Behavior

- [ ] `security-auditor` covers all 10 OWASP categories including A04 (rate limiting), A05 (CORS/headers), A10 (SSRF)
- [ ] `security-auditor` checks `$executeRawUnsafe` and `$runCommandRaw` (complete Prisma list)
- [ ] `code-simplicity-reviewer` protected paths include `.env*`, `middleware.*`, `**/auth/**`, `lefthook.yml`
- [ ] `testing-reviewer` detects behavioral changes (branches, state mutations, API endpoints, error paths)
- [ ] `testing-reviewer` maps changed files to existing test files
- [ ] `testing-reviewer` flags behavioral changes with zero corresponding test additions
- [ ] `testing-reviewer` produces "testing addressed" assessment (fully/partially/not addressed)
- [ ] All agents produce P1/P2/P3 findings with file:line references
- [ ] No agent references Rails, Ruby, ActiveRecord, Stimulus, or Turbo

### Cleanup

- [ ] `auto-compound.sh.deprecated` deleted (Phase 0 soft rollback verified)
- [ ] `init-project.sh` updated with full `agents.yml` template
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                                                                                                                                                                                                                                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 2      | Database agents (schema-drift, data-migration, data-integrity)                                                                                                                                                                                                                                                                               |
| Phase 3      | `spec-flow-analyzer` agent for `/harden-plan`                                                                                                                                                                                                                                                                                                |
| Phase 6      | Compound learning reading validated observations                                                                                                                                                                                                                                                                                             |
| Phase 7      | Triage command for observations                                                                                                                                                                                                                                                                                                              |
| Phase Finale | Documentation refresh for agent tables                                                                                                                                                                                                                                                                                                       |
| Future       | `pattern-recognition-specialist` — cut as redundant. Re-evaluate if pattern-finder proves insufficient.                                                                                                                                                                                                                                      |
| Future       | CE v2.61.0 added 13 new review agents. Evaluated all — `testing-reviewer` ported (v7). Remaining candidates for future evaluation: `adversarial-reviewer` (tries to break code), `api-contract-reviewer` (API breaking change detection), `correctness-reviewer` (logic/edge cases). Rest are redundant with existing agents or CE-specific. |

---

## File Change Summary

| #   | File                                                     | Change                                                             | Priority    |
| --- | -------------------------------------------------------- | ------------------------------------------------------------------ | ----------- |
| 1   | `.claude/agents/review/security-auditor.md`              | **Create**                                                         | P0          |
| 2   | `.claude/agents/review/kieran-foad-ts-reviewer.md`       | **Create**                                                         | P0          |
| 3   | `.claude/agents/review/performance-auditor.md`           | **Create**                                                         | P0          |
| 4   | `.claude/agents/review/code-simplicity-reviewer.md`      | **Create**                                                         | P0          |
| 5   | `.claude/agents/review/architecture-strategist.md`       | **Create**                                                         | P0          |
| 6   | `.claude/agents/review/testing-reviewer.md`              | **Create** — behavioral change test coverage (v7)                  | P0          |
| 7   | `.claude/agents/review/deployment-verification-agent.md` | **Create**                                                         | P1 (opt-in) |
| 8   | `.claude/agents/review/frontend-races-reviewer.md`       | **Create**                                                         | P1 (opt-in) |
| 9   | `.claude/agents/review/kieran-foad-python-reviewer.md`   | **Create**                                                         | P1 (opt-in) |
| 10  | `.launchpad/agents.yml`                                  | **Edit** — 7 defaults + harden keys + opt-in comments              | P0          |
| 11  | `.claude/commands/review.md`                             | **Edit** — scoped reads + scope instruction + observations + dedup | P0          |
| 12  | `.claude/commands/harden-plan.md`                        | **Edit** — read from agents.yml instead of hardcoded list          | P0          |
| 13  | `scripts/setup/init-project.sh`                          | **Edit** — full agents.yml template                                | P1          |
| 14  | `scripts/compound/auto-compound.sh.deprecated`           | **Delete**                                                         | P1          |
