---
name: lp-test-browser
description: Automated browser testing for UI routes affected by current changes. Dual browser tool support (agent-browser CLI primary, Playwright MCP fallback). Fully autonomous.
---

# /lp-test-browser

Automated browser testing for UI routes affected by current changes. Self-scoping, graceful skip, fully autonomous.

## Usage

```
/lp-test-browser                    → test routes affected by current branch
/lp-test-browser 123                → test routes affected by PR #123
```

**Arguments:** `$ARGUMENTS` (optional PR number)

---

## Step 0: Pipeline Skip Gate

Load `pipeline.build.test_browser` from `.launchpad/config.yml` via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-config-loader.py`.

- IF `test_browser: skipped` → exit 0 with message:
  > "Browser testing skipped per `config.yml` `pipeline.build.test_browser: skipped`. Use this for backend-only projects or when browser CI isn't wired up yet."
- ELSE proceed to Step 1.

No hard-coded detection. Backend-only projects bypass this command by configuration, not by ad-hoc file scanning.

---

## Step 1: Detect Browser Tool

1. Check `agent-browser`: `command -v agent-browser`
   - IF installed: use agent-browser (93% fewer tokens per snapshot)
   - Log: "Using agent-browser CLI (token-efficient mode)"
2. ELSE check Playwright MCP: verify MCP tools available
   - IF available: use Playwright MCP
   - Log: "Using Playwright MCP (higher token cost — install agent-browser for 93% token reduction: npm install -g agent-browser && agent-browser install)"
3. ELSE: WARN "No browser automation tool available." → skip to Step 7

## Step 2: Determine Test Scope

1. Get changed files:
   - IF PR number provided: `gh pr view [number] --json files -q '.files[].path'`
   - ELSE: `git diff --name-only origin/main...HEAD`
2. Map files to testable UI routes:

| File Pattern                       | Route(s)                                                       |
| ---------------------------------- | -------------------------------------------------------------- |
| `apps/web/src/app/**/page.tsx`     | Corresponding Next.js App Router route                         |
| `apps/web/src/app/**/layout.tsx`   | Parent route + first child route                               |
| `packages/ui/src/**`               | Pages importing that component (use Grep to find consumers)    |
| `apps/web/src/**/*.css`            | Visual regression on key pages (homepage + 2 most-used routes) |
| `apps/web/src/app/api/**/route.ts` | Skip (API route handlers — no UI)                              |
| `apps/api/**`                      | Skip (no browser test)                                         |
| `packages/db/**`                   | Skip (no browser test)                                         |
| `packages/shared/**`               | Skip (no browser test)                                         |
| `scripts/**`, `docs/**`            | Skip (no browser test)                                         |

3. Route count cap: IF >15 routes, select top 15 by specificity:
   1. Direct page changes (`page.tsx`) — highest priority
   2. Component consumer pages (found via Grep)
   3. Layout/CSS cascade pages — lowest priority (cut first)
   - WARN: "{total} routes affected, testing top 15."
4. IF zero routes mapped: "No UI routes affected — skipping browser tests." → exit

## Step 3: Verify Dev Server

- Check if dev server is running on localhost:3000
  - agent-browser: `agent-browser open http://localhost:3000 && agent-browser snapshot -i`
  - Playwright MCP: `browser_navigate url="http://localhost:3000"` then `browser_snapshot`
- IF server not responding: WARN "Dev server not running on localhost:3000. Start with 'pnpm dev'." → skip to Step 7

## Step 4: Test Each Affected Route (30s/route, 5min total)

- Clean previous screenshots: `rm -rf .harness/screenshots/ && mkdir -p .harness/screenshots/`
- For each route (abort remaining if 5min total exceeded):

  a) **Navigate** to the route
  b) **Capture** accessibility snapshot
  c) **Verify** page loaded:
  - Page title/heading present (not blank, not error page)
  - No "500 Internal Server Error" or "404 Not Found"
  - Primary content rendered (not empty/skeleton stuck)
  - Check for console errors
    d) **Test interactions** (if interactive elements found):
  - Click primary CTAs / navigation links
  - Verify navigation works
  - Fill and submit forms if present (test data)
  - Verify form validation feedback
    e) **Screenshot** for evidence → `.harness/screenshots/{route-slug}.browser-test.png`
    f) **Record** result: PASS / FAIL with details

  Per-route timeout: 30 seconds. Exceeded → FAIL with "Timeout after 30s", continue next route.

## Step 5: Write Findings to .harness/todos/

For each FAIL:

- Write `.harness/todos/{id}-browser-test-{route-slug}.md`
- YAML frontmatter: `status: pending`, `priority: P1|P2|P3`, `agent_source: test-browser`
- Body: Route, Issue Description, Console Errors, Screenshot Path, Reproduction Steps

Priority assignment:

- **P1:** page crashes, 500 errors, blank page, JS exceptions
- **P2:** broken interactions, form submission failures, missing content
- **P3:** visual regressions, layout shifts, minor styling issues

## Step 6: Close Browser (UNCONDITIONAL)

This step MUST run even if Steps 3-5 fail. Use try/finally semantics.

- agent-browser: `agent-browser close`
- Playwright MCP: `browser_close`

## Step 7: Report

```
## Browser Test Results
Routes tested: {N} (of {total} affected, capped at 15)
Passed: {pass_count}
Failed: {fail_count}
Timed out: {timeout_count}

| Route | Status | Notes |
|---|---|---|
| /dashboard | PASS | |
| /settings | FAIL | Console error: TypeError |

Findings written: {fail_count} todos in .harness/todos/
Screenshots: .harness/screenshots/
```

---

## Strict Rules

- Fully autonomous — no interactive prompts
- Always headless mode
- Write findings to `.harness/todos/` — do not attempt to fix issues
- Proceed to `/lp-ship` regardless of findings (browser failures are informational)
- Do not start the dev server — detect only
- Close browser unconditionally (try/finally)
- Max 15 routes per run
- 30s per-route timeout, 5min total step timeout
