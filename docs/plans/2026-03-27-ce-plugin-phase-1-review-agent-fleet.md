# Phase 1: Review Agent Fleet

**Date:** 2026-03-27
**Depends on:** Phase 0 (review agent config system)
**Branch:** `feat/review-agent-fleet`
**Status:** Plan — final

---

## Decisions (All Finalized)

| Decision                   | Answer                                                                                                                                                             |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Security agent             | `security-auditor` → `.claude/agents/review/security-auditor.md`                                                                                                   |
| TypeScript agent           | `kieran-foad-ts-reviewer` → `.claude/agents/review/kieran-foad-ts-reviewer.md`                                                                                     |
| Performance agent          | `performance-auditor` → `.claude/agents/review/performance-auditor.md`                                                                                             |
| Simplicity agent           | `code-simplicity-reviewer` → `.claude/agents/review/code-simplicity-reviewer.md`                                                                                   |
| Model                      | `model: opus` for all 4 agents                                                                                                                                     |
| Architecture doc reference | Yes — TS reviewer reads `FRONTEND_GUIDELINES.md` and `BACKEND_STRUCTURE.md`                                                                                        |
| Simplicity pass            | Double — Pass 1 in parallel with other agents, Pass 2 as dedicated final sweep after synthesis (matching CE). Logic lives in Phase 0's `/harness:review` Step 3.5. |
| Simplicity scope           | Read entire codebase, suggest changes only to current feature's changed files                                                                                      |
| Out-of-scope findings      | Written as observations to `.harness/observations/`, inert until Phase 7 triage                                                                                    |
| Protected paths            | Option C (scope + focus + protected path list)                                                                                                                     |
| Observations directory     | `.harness/observations/` — created in Phase 0 (empty), populated starting Phase 1                                                                                  |

---

## Purpose

Create 4 specialized review agents that run in parallel during `/harness:review`. These replace the single `pattern-finder` as the review fleet. After Phase 1, every `/inf` run and future `/commit` run gets security, type safety, performance, and simplicity analysis automatically.

---

## Architecture: How These Agents Fit

```
/harness:review (from Phase 0)
  │
  ├── Read .harness/harness.local.md
  ├── Get changed files list (diff scope)
  │
  ├── Pass 1 — Dispatch in parallel:
  │   ├── pattern-finder           (existing, from Phase 0)
  │   ├── security-auditor         (NEW — Phase 1)
  │   ├── kieran-foad-ts-reviewer  (NEW — Phase 1)
  │   ├── performance-auditor      (NEW — Phase 1)
  │   └── code-simplicity-reviewer (NEW — Phase 1, first pass)
  │
  ├── IF Prisma changes detected:
  │   └── (database agents — Phase 2, not yet)
  │
  ├── Synthesize findings → P1/P2/P3
  │
  ├── Pass 2 — Simplicity Final Sweep:
  │   └── code-simplicity-reviewer (second pass, with Step 3 findings as context)
  │
  └── Write to .harness/todos/ + .harness/observations/
```

---

## Agent Definitions

### 1. `security-auditor`

**File:** `.claude/agents/review/security-auditor.md`
**CE source:** `agents/review/security-sentinel.md` (114 lines)
**Adaptation:** Strip Rails/Ruby patterns, add TypeScript/Hono/Prisma-specific scanning

**Frontmatter:**

```yaml
---
name: security-auditor
description: Performs security audits for vulnerabilities, input validation, auth/authz, hardcoded secrets, and OWASP compliance in TypeScript/Next.js/Hono applications.
model: opus
---
```

**Core scanning protocol (6 areas, adapted for our stack):**

1. **Input Validation Analysis**
   - Grep for `req.body`, `req.params`, `req.query` in Hono routes
   - Check Zod/Yup schema validation on all API inputs
   - Verify type validation, length limits, format constraints
   - Check Next.js server actions for input sanitization

2. **SQL Injection / Query Safety**
   - Scan for raw Prisma queries (`$queryRaw`, `$executeRaw`)
   - Check for string interpolation in any database calls
   - Verify all user input flows through Prisma's parameterized queries
   - Flag any `prisma.$queryRawUnsafe` usage

3. **XSS Vulnerability Detection**
   - Check for `dangerouslySetInnerHTML` in React components
   - Verify CSP headers in Next.js middleware
   - Check for unescaped user content in server components
   - Scan for `innerHTML` assignments in client components

4. **Authentication & Authorization Audit**
   - Map all Hono API routes — verify auth middleware on each
   - Check Next.js middleware for route protection
   - Verify session management (token expiry, rotation)
   - Check authorization at route + resource levels (not just "is logged in" but "can access this resource")

5. **Sensitive Data Exposure**
   - Grep for `password`, `secret`, `key`, `token`, `STRIPE` in source files
   - Scan for hardcoded credentials or API keys
   - Check that `.env.local` values are never logged
   - Verify PII (emails, billing data) is never in console.log/logger output
   - Check that error responses don't leak stack traces or internal paths

6. **OWASP Top 10 Compliance**
   - Systematic check against each OWASP category
   - Document compliance status per category
   - Provide remediation steps for any gaps

**Requirements checklist (10 items):**

1. All API inputs validated and sanitized (Zod schemas)
2. No hardcoded secrets or credentials
3. Auth middleware on all API endpoints
4. Database queries use Prisma's parameterized methods (no raw SQL with user input)
5. XSS protection via React escaping + CSP headers
6. HTTPS enforced
7. CSRF protection on state-changing routes
8. Security headers configured (Next.js middleware)
9. Error messages don't leak sensitive information
10. Dependencies scanned for known vulnerabilities

**Output format (4-part report):**

1. Executive Summary — high-level risk assessment with severity ratings
2. Detailed Findings — per vulnerability: description, impact, file:line, remediation
3. Risk Matrix — categorized by P1/P2/P3
4. Remediation Roadmap — prioritized action items

**Operational guidelines:**

- Think like an attacker — assume worst case
- Provide actionable solutions, not just problem descriptions
- Pay special attention to Stripe webhook signature verification
- Check that Hono middleware chain cannot be bypassed
- Verify Next.js server/client boundary doesn't leak server-only data

---

### 2. `kieran-foad-ts-reviewer`

**File:** `.claude/agents/review/kieran-foad-ts-reviewer.md`
**CE source:** `agents/review/kieran-typescript-reviewer.md` (124 lines)
**Adaptation:** Minimal — already TypeScript-focused. Strip "Kieran" persona framing, keep principles. Add project doc references.

**Frontmatter:**

```yaml
---
name: kieran-foad-ts-reviewer
description: Reviews TypeScript code with an extremely high quality bar for type safety, modern patterns, and maintainability. Use after implementing features or modifying TypeScript code.
model: opus
---
```

**10 review principles:**

1. **Existing Code Modifications — Be Very Strict**
   - Added complexity needs strong justification
   - Prefer extracting to new modules over complicating existing ones
   - Ask: "Does this make the existing code harder to understand?"

2. **New Code — Be Pragmatic**
   - If isolated and works, acceptable
   - Flag improvements but don't block
   - Focus on testability and maintainability

3. **Type Safety Convention**
   - NEVER use `any` without strong justification and a comment explaining why
   - Leverage type inference — don't annotate what TypeScript can figure out
   - Use union types, discriminated unions, type guards
   - Prefer `satisfies` operator (TS 5+) for type checking without widening
   - Use const type parameters where applicable

4. **Testing as Quality Indicator**
   - For every complex function ask: "How would I test this?"
   - Hard-to-test code = poor structure that needs refactoring
   - If it's hard to test, what should be extracted?

5. **Critical Deletions & Regressions**
   - For each deletion verify: intentional? Breaks existing workflow? Tests that will fail? Logic moved or just removed?

6. **Naming & Clarity — The 5-Second Rule**
   - Must understand purpose from name in 5 seconds
   - Fail: `doStuff`, `handleData`, `process`
   - Pass: `validateUserEmail`, `fetchUserProfile`, `transformApiResponse`

7. **Module Extraction Signals**
   - Extract when: complex business rules, multiple concerns, external API interactions, reusable logic

8. **Import Organization**
   - Group: external libs → internal modules → types → styles
   - Named imports over default exports
   - No mixed order, no wildcard imports

9. **Modern TypeScript Patterns**
   - ES6+ features, TypeScript 5+ features
   - Immutable patterns (readonly, as const)
   - Functional patterns where appropriate

10. **Core Philosophy**
    - "Duplication > Complexity"
    - "Adding more modules is never a bad thing. Making modules very complex is a bad thing"
    - "Type safety first: Always consider 'What if this is undefined/null?'"
    - Avoid premature optimization

**Project-awareness instruction:**

```
If FRONTEND_GUIDELINES.md exists in docs/architecture/, read it for project-specific
TypeScript and React conventions. If BACKEND_STRUCTURE.md exists, read it for API
and service layer conventions. Apply these project conventions alongside the 10
principles above. Project conventions take precedence when they conflict.
```

**Review workflow (6 steps):**

1. Start with critical issues (regressions, deletions, breaking changes)
2. Type safety violations and `any` usage
3. Testability and clarity evaluation
4. Suggest specific improvements with examples
5. Be strict on existing code, pragmatic on new
6. Always explain WHY

**Output:** Structured findings with file:line references, severity (P1/P2/P3), and concrete improvement examples.

---

### 3. `performance-auditor`

**File:** `.claude/agents/review/performance-auditor.md`
**CE source:** `agents/review/performance-oracle.md` (137 lines)
**Adaptation:** Strip 1 ActiveRecord line, add Prisma-specific N+1 patterns, add Next.js-specific frontend checks.

**Frontmatter:**

```yaml
---
name: performance-auditor
description: Analyzes code for performance bottlenecks, algorithmic complexity, database queries, memory usage, and scalability in TypeScript/Next.js/Hono/Prisma applications.
model: opus
---
```

**Core analysis framework (6 dimensions):**

1. **Algorithmic Complexity**
   - Big O analysis for all algorithms
   - Flag O(n²) or worse — require explicit justification
   - Analyze best/average/worst case
   - Consider space complexity
   - Project behavior at 10x / 100x / 1000x data volumes

2. **Database Performance**
   - N+1 query detection in Prisma (nested `include` without `select`)
   - Check for missing indexes on frequently queried fields
   - Verify eager loading vs. lazy loading decisions
   - Flag `findMany()` without pagination
   - Check for unnecessary `include` depth in Prisma queries

3. **Memory Management**
   - Memory leak detection (event listeners not cleaned up, intervals not cleared)
   - Unbounded data structures (arrays that grow without limit)
   - Large object allocations in hot paths
   - React component memory (refs, subscriptions, cleanup in useEffect)

4. **Caching Opportunities**
   - Expensive computations to memoize (React.memo, useMemo, useCallback)
   - API response caching (Next.js fetch cache, revalidation strategies)
   - Static generation vs. server-side rendering decisions
   - CDN caching headers

5. **Network Optimization**
   - Minimize API round trips (batch requests, GraphQL-style selections)
   - Payload size (are we sending more data than the client needs?)
   - Unnecessary data fetching (fetching full objects when only IDs are needed)
   - Image optimization (Next.js Image component usage)

6. **Frontend Performance**
   - Bundle size impact (new dependencies, tree-shaking, dynamic imports)
   - Render-blocking resources
   - Lazy loading for below-the-fold content
   - React re-render analysis (unnecessary state updates, missing memo)
   - Server components vs. client components (are we making things client-side unnecessarily?)

**Performance benchmarks:**

- No algorithms worse than O(n log n) without explicit justification
- All database queries must use appropriate indexes
- Memory usage must be bounded and predictable
- API response times must stay under 200ms for standard operations
- Bundle size increases should remain under 5KB per feature
- Background jobs should process items in batches

**5-pass review approach:**

1. First pass: Identify obvious performance anti-patterns
2. Second pass: Analyze algorithmic complexity
3. Third pass: Check database and I/O operations
4. Fourth pass: Consider caching and optimization opportunities
5. Final pass: Project performance at scale

**Output format (5 sections):**

1. Performance Summary
2. Critical Issues (current impact + projected impact at scale + solution)
3. Optimization Opportunities (current → suggested → expected gain → complexity)
4. Scalability Assessment (data volume projections, concurrent users, resources)
5. Recommended Actions (prioritized list)

---

### 4. `code-simplicity-reviewer`

**File:** `.claude/agents/review/code-simplicity-reviewer.md`
**CE source:** `agents/review/code-simplicity-reviewer.md` (102 lines)
**Adaptation:** Add 3-layer safety (scope + focus + protected paths), add observations mechanism, update pipeline artifact paths.

**Frontmatter:**

```yaml
---
name: code-simplicity-reviewer
description: Final review pass to ensure code is as simple and minimal as possible. Identifies YAGNI violations, unnecessary complexity, and simplification opportunities within the current feature scope.
model: opus
---
```

**3-Layer Safety System:**

**Layer 1 — Scope Restriction:**

```
You have full access to the entire codebase for READING and UNDERSTANDING context.

However, you may ONLY suggest changes to files listed as "Changed Files" in your
prompt. These are the files from the current feature being built.

If you discover simplification opportunities OUTSIDE the changed files, write them
as OBSERVATIONS (not todos). Observations are informational — they will be reviewed
by a human during triage before any action is taken.
```

**Layer 2 — Focus Instruction:**

```
Focus your simplification analysis on application code in apps/ and packages/.
Files in docs/, scripts/, .claude/, and .harness/ are pipeline infrastructure —
do not apply YAGNI analysis to them.
```

**Layer 3 — Protected Paths:**

```
NEVER flag these paths for removal or simplification, even if they appear
in the changed files list:

- docs/plans/** — living reference documents consumed by /implement_plan
- docs/solutions/** — learnings consumed by docs-analyzer
- docs/reports/** — feed /inf pipeline via analyze-report.sh
- docs/tasks/sections/** — section specs consumed by /pnf
- docs/tasks/prd-*.md — consumed by analyze-report.sh for deduplication
- docs/skills-catalog/** — skills-usage.json is machine-written, consumed by hooks
- .harness/** — runtime artifacts consumed by review/resolve/learning pipeline
- scripts/compound/*.md — prompt templates consumed by shell scripts (NOT documentation)
- scripts/compound/config.json — persistent pipeline configuration
- .claude/skills/*/references/** — loaded as skill context by Claude Code
- **/.gitkeep — directory structure preservation
- *.template.md / *.template — consumed by init-project.sh
```

**6 Review Areas:**

1. **Analyze Every Line** (within scope)
   - Question necessity of each line in the changed files
   - If it doesn't directly contribute to current requirements, flag

2. **Simplify Complex Logic**
   - Break down complex conditionals
   - Replace clever code with obvious code
   - Eliminate nesting — use early returns
   - Flatten deeply nested structures

3. **Remove Redundancy**
   - Duplicate error checks
   - Repeated patterns that could consolidate
   - Defensive programming that adds no value
   - Commented-out code

4. **Challenge Abstractions**
   - Question every interface/base class/abstraction in changed files
   - Inline code used only once
   - Remove premature generalizations
   - Flag over-engineering

5. **Apply YAGNI Rigorously**
   - Remove features not explicitly required now
   - Eliminate extensibility points without clear use cases
   - Question generic solutions for specific problems
   - Remove "just in case" code

6. **Optimize for Readability**
   - Self-documenting code over comments
   - Descriptive names over explanatory comments
   - Simplify data structures to match actual usage

**Output format — two types:**

**For in-scope findings → Todo files (`.harness/todos/`):**

```markdown
## Simplification Analysis

### Core Purpose

[what the changed code needs to do]

### Unnecessary Complexity Found

- [issue with file:line — MUST be in changed files list]

### Code to Remove

- [File:lines] - [Reason]
- [Estimated LOC reduction: X]

### Simplification Recommendations

1. [Most impactful]
   - Current: [description]
   - Proposed: [simpler alternative]
   - Impact: [LOC saved, clarity improved]

### YAGNI Violations

- [feature/abstraction not needed]

### Final Assessment

Total potential LOC reduction: X%
Complexity score: [High/Medium/Low]
```

**For out-of-scope findings → Observation files (`.harness/observations/`):**

```yaml
---
status: observation
priority: p3
issue_id: "obs-{N}"
tags: [simplification]
observed_in: {file_path_outside_scope}
feature_scope: {current_feature_changed_files}
---

## Observation
{description of simplification opportunity}

## Why Not Actioned
Outside the current feature scope. Flagged for future triage.
```

**Philosophy:**

- "Perfect is the enemy of good. The simplest code that works is often the best code."
- "Every line of code is a liability."
- The litmus test: "If I delete this, does something break or does a current requirement go unmet?"

---

## Changes to `/harness:review` (Phase 0 Update)

Phase 0's `/harness:review` command needs a small update to support the simplicity reviewer's scope mechanism:

**In Step 2 (Dispatch Review Agents):**

- For `security-auditor`, `kieran-foad-ts-reviewer`, `performance-auditor`:
  Pass diff + changed file list + review context (standard prompt)
- For `code-simplicity-reviewer`:
  Pass the same PLUS explicit scope instruction: "Changed Files: {list}. You may only suggest changes to these files. Write observations for anything outside this list."

**In Step 4 (Write Todo Files):**

- Add: "Also write any observation files from the simplicity reviewer to `.harness/observations/`"

---

## Changes to `.harness/harness.local.md` Default Config

Update the `review_agents` list to include all 5 agents:

```yaml
---
review_agents:
  - pattern-finder
  - security-auditor
  - kieran-foad-ts-reviewer
  - performance-auditor
  - code-simplicity-reviewer

review_db_agents: []
---
```

---

## Changes to `init-project.sh`

Update the default `harness.local.md` template to include all 5 review agents (not just `pattern-finder`).

Also create `.harness/observations/.gitkeep` directory.

---

## Verification Checklist

- [ ] `.claude/agents/review/security-auditor.md` exists with `model: opus`
- [ ] `.claude/agents/review/kieran-foad-ts-reviewer.md` exists with `model: opus`
- [ ] `.claude/agents/review/performance-auditor.md` exists with `model: opus`
- [ ] `.claude/agents/review/code-simplicity-reviewer.md` exists with `model: opus`
- [ ] `.harness/observations/.gitkeep` exists
- [ ] `.harness/harness.local.md` lists all 5 review agents
- [ ] `/harness:review` dispatches all 5 agents in parallel
- [ ] `security-auditor` scans for Hono/Prisma/Next.js-specific vulnerabilities
- [ ] `kieran-foad-ts-reviewer` reads `FRONTEND_GUIDELINES.md` and `BACKEND_STRUCTURE.md` when they exist
- [ ] `performance-auditor` checks for Prisma N+1 patterns
- [ ] `code-simplicity-reviewer` only suggests changes to files in the changed files list
- [ ] `code-simplicity-reviewer` writes observations (not todos) for out-of-scope findings
- [ ] `code-simplicity-reviewer` respects all 3 safety layers (scope + focus + protected paths)
- [ ] Observation files land in `.harness/observations/` with correct format
- [ ] No agent references Rails, Ruby, Python, or ActiveRecord
- [ ] All agents produce findings with file:line references and P1/P2/P3 severity
- [ ] `init-project.sh` updated with new default agent list + observations directory
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To | What                                                           |
| ----------- | -------------------------------------------------------------- |
| Phase 2     | Database agents (schema-drift, data-migration, data-integrity) |
| Phase 6     | Compound learning reading validated observations               |
| Phase 7     | Triage command that validates/rejects observations             |
| Phase 9     | Documentation refresh for agent tables                         |

---

## File Change Summary

| #   | File                                                | Change                                                                         | Priority |
| --- | --------------------------------------------------- | ------------------------------------------------------------------------------ | -------- |
| 1   | `.claude/agents/review/security-auditor.md`         | **Create**                                                                     | P0       |
| 2   | `.claude/agents/review/kieran-foad-ts-reviewer.md`  | **Create**                                                                     | P0       |
| 3   | `.claude/agents/review/performance-auditor.md`      | **Create**                                                                     | P0       |
| 4   | `.claude/agents/review/code-simplicity-reviewer.md` | **Create**                                                                     | P0       |
| 5   | `.harness/observations/.gitkeep`                    | **Create**                                                                     | P0       |
| 6   | `.harness/harness.local.md`                         | **Edit** — update `review_agents` list to include all 5                        | P0       |
| 7   | `.claude/commands/harness/review.md`                | **Edit** — add scope instruction for simplicity reviewer + observations output | P0       |
| 8   | `scripts/setup/init-project.sh`                     | **Edit** — update default agent list + create observations dir                 | P1       |
| 9   | `CLAUDE.md`                                         | **Edit** — add 4 new agents to sub-agents table                                | P2       |
| 10  | `AGENTS.md`                                         | **Edit** — mirror CLAUDE.md                                                    | P2       |
