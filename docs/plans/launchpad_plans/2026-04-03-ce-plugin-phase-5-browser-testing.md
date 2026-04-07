# Phase 5: Browser Testing

**Date:** 2026-04-03
**Depends on:** Phase 0 (pipeline infrastructure — `/harness:build` pipeline, `.harness/todos/` directory, todo file format). `/test-browser` is Step 3 of `/harness:build`.
**Branch:** `feat/browser-testing`
**Status:** Plan — v4.2 (Phase 10 cascading changes: pipeline diagram step order)

---

## Decisions (All Finalized)

| Decision                       | Answer                                                                                                                                                         |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Test command name              | `/test-browser` → `.claude/commands/test-browser.md` (flat)                                                                                                    |
| Browser tool: primary          | agent-browser CLI (93% fewer tokens than Playwright MCP — critical for multi-route testing)                                                                    |
| Browser tool: fallback         | Playwright MCP (already installed, zero setup — used when agent-browser not installed)                                                                         |
| Detection order                | agent-browser installed? → use it. Not installed? → Playwright MCP available? → use it. Neither? → skip with warning.                                          |
| CE source: test-browser        | `commands/test-browser.md` (339 lines) — heavy adaptation (agent-browser primary + Playwright fallback)                                                        |
| CE source: agent-browser skill | NOT ported as skill — tool detection logic embedded in `/test-browser` command                                                                                 |
| Pipeline wiring                | Auto-dispatched by `/harness:build` as Step 3 (self-scoping, graceful skip)                                                                                    |
| Failure handling               | Write findings to `.harness/todos/`, proceed to `/ship` (no loop back)                                                                                         |
| Interactive mode               | Removed — no "headed vs headless" prompt, no "fix now vs create todo vs skip" prompt. Fully autonomous: always headless, always writes todos.                  |
| Max routes                     | Cap at 15 routes per run. If more affected, test top 15 by specificity (direct page changes first, then component consumers, skip global CSS/layout cascades). |
| Per-route timeout              | 30 seconds per route. Total step timeout: 5 minutes.                                                                                                           |
| Dev server port                | Hardcoded to 3000 (change in command file if different). No config-file parsing.                                                                               |
| Screenshots                    | Written to `.harness/screenshots/` (gitignored directory, cleaned at start of each run)                                                                        |
| `bug-reproduction-validator`   | DEFERRED to a future phase alongside `/reproduce-bug` command — creating an unwired agent violates the "nothing standalone" rule                               |

---

## Purpose

Add automated browser testing to the `/harness:build` pipeline. After code is reviewed and review findings are fixed, `/test-browser` opens the app in a headless browser, maps changed files to affected UI routes, navigates each route, verifies rendering and interactions, captures screenshots, and reports issues as `.harness/todos/`.

This catches visual regressions, JavaScript integration bugs, CSS layout issues, and broken user flows that unit tests (`pnpm test`) and type checking (`pnpm typecheck`) cannot detect.

---

## Architecture: How Phase 5 Components Wire In

```
/harness:plan (interactive)              /harness:build (autonomous)
  │                                        │
  ├── design step                          ├── Step 1:    /inf                    (build)
  ├── /pnf                                 ├── Step 2:    /review                 (code review)
  ├── /harden-plan                         ├── Step 2.5:  /resolve_todo_parallel  (fix review findings)
  └── human approval                       ├── Step 3:    /test-browser           ← NEW (Phase 5, auto-dispatched, self-scoping)
       ↓ approved                          │     ├── Map changed files → UI routes (max 15)
                                           │     ├── IF zero routes: skip silently
                                           │     ├── IF no browser tool available: skip with warning
                                           │     ├── IF dev server not running: skip with warning
                                           │     ├── ELSE: test each route (30s timeout per route, 5min total)
                                           │     │     → write findings to .harness/todos/
                                           │     └── Proceed to Step 4 regardless of findings
                                           ├── Step 4:    /ship                   (commit+push+PR — includes browser findings in PR body)
                                           ├── Step 5:    /learn                  (extract learnings)
                                           └── Step 6:    Report
```

Browser test findings written to `.harness/todos/` are NOT resolved by a second `/resolve_todo_parallel` run — they proceed directly to `/ship` (Step 4), which includes them in the PR description for human review. This avoids an unpredictably long fix-test loop.

---

## Component Definition

### `/test-browser` Command

**File:** `.claude/commands/test-browser.md`
**CE source:** `commands/test-browser.md` (339 lines) — heavy adaptation
**Called by:** `/harness:build` Step 3 (auto-dispatched)
**Also usable:** standalone

**Adaptations from CE:**

- Add dual browser tool support: agent-browser CLI (primary) + Playwright MCP (fallback)
- Add detection logic for tool availability
- Remove interactive prompts (headed/headless mode, fix-now/create-todo/skip) — fully autonomous
- Replace Rails file-to-route mapping with Next.js App Router / monorepo patterns
- Add graceful skip when no UI routes affected, no browser tool available, or no dev server
- Write failures to `.harness/todos/` (Phase 0 format, with optional `agent_source` field) instead of interactive failure handling
- Add dev server detection (hardcoded port 3000)
- Remove human verification step (OAuth, payments, etc.) — autonomous command cannot prompt
- Add MAX_ROUTES=15 cap with specificity-based selection
- Add 30s per-route timeout and 5min total step timeout
- Write screenshots to `.harness/screenshots/` (cleaned each run)
- Add try/finally browser close semantics

**Usage:**

```
/test-browser                    → test routes affected by current branch
/test-browser 123                → test routes affected by PR #123
```

**Flow (7 steps):**

```
Step 1: Detect Browser Tool
  - Check agent-browser: command -v agent-browser
    IF installed: use agent-browser (93% fewer tokens per snapshot)
    Log: "Using agent-browser CLI (token-efficient mode)"
  - ELSE check Playwright MCP: verify mcp tools available
    IF available: use Playwright MCP
    Log: "Using Playwright MCP (higher token cost — install agent-browser
    for 93% token reduction: npm install -g agent-browser && agent-browser install)"
  - ELSE: WARN "No browser automation tool available. Install agent-browser
    (npm install -g agent-browser && agent-browser install) or configure
    Playwright MCP." → skip to Step 7 (report skip reason)

Step 2: Determine Test Scope
  - Get changed files:
    IF PR number provided: gh pr view [number] --json files -q '.files[].path'
    ELSE: git diff --name-only origin/main...HEAD
  - Map files to testable UI routes using pattern table:
    | File Pattern | Route(s) |
    |---|---|
    | apps/web/src/app/**/page.tsx | Corresponding Next.js App Router route |
    | apps/web/src/app/**/layout.tsx | Parent route + first child route |
    | packages/ui/src/** | Pages importing that component (use Grep to find consumers) |
    | apps/web/src/**/*.css, apps/web/src/styles/globals.css | Visual regression on key pages (homepage + 2 most-used routes) |
    | apps/web/src/app/api/**/route.ts | Skip (Next.js API route handlers — no UI rendering, no browser test needed) |
    | apps/api/** | Skip (no browser test — API routes) |
    | packages/db/** | Skip (no browser test — database) |
    | packages/shared/** | Skip (no browser test — shared types) |
    | scripts/** | Skip (no browser test — build scripts) |
    | docs/** | Skip (no browser test — documentation) |
  - Note on Tailwind v4: Tailwind CSS v4 uses @theme directives in CSS files
    (apps/web/src/styles/globals.css), not tailwind.config.js/ts. The CSS
    pattern above covers this. No tailwind.config.* pattern needed.
  - Route count cap: IF more than 15 routes mapped, select top 15 by specificity:
    1. Direct page changes (apps/web/src/app/**/page.tsx) — highest priority
    2. Component consumer pages (found via Grep)
    3. Layout/CSS cascade pages — lowest priority (cut first)
    WARN: "{total} routes affected, testing top 15 by specificity.
    Run /test-browser standalone to test all routes."
  - IF zero routes mapped: "No UI routes affected — skipping browser tests." → exit
  - Report: "Testing {N} routes: [list]"

Step 3: Verify Dev Server
  - Check if dev server is running on localhost:3000:
    With agent-browser: agent-browser open http://localhost:3000 && agent-browser snapshot -i
    With Playwright MCP: browser_navigate url="http://localhost:3000" then browser_snapshot
  - Port is hardcoded to 3000 (change in the command file if your project uses a different port)
  - Validate port is numeric and 1-65535. URL is always http://localhost:{port}.
  - IF server not responding:
    WARN "Dev server not running on localhost:3000. Start with 'pnpm dev'
    and run /test-browser manually."
    → skip to Step 7 (report skip reason)

Step 4: Test Each Affected Route (30s timeout per route, 5min total)
  - Clean previous screenshots: rm -rf .harness/screenshots/ && mkdir -p .harness/screenshots/
  - For each route (abort remaining routes if 5min total exceeded):
    Per-route timeout: 30 seconds. IF exceeded, record route as FAIL
    with reason "Timeout after 30s" and continue to next route.

    a) Navigate to the route
       agent-browser: agent-browser open "http://localhost:3000{route}"
       Playwright MCP: browser_navigate url="http://localhost:3000{route}"

    b) Capture accessibility snapshot
       agent-browser: agent-browser snapshot -i
       Playwright MCP: browser_snapshot

    c) Verify page loaded correctly:
       - Page title/heading present (not blank, not error page)
       - No "500 Internal Server Error" or "404 Not Found"
       - Primary content rendered (not empty/skeleton stuck)
       - Check for console errors:
         agent-browser: (check snapshot output for error indicators)
         Playwright MCP: browser_console_messages

    d) Test critical interactions (if interactive elements found):
       - Click primary CTAs / navigation links
       - Verify navigation works (no broken links)
       - Fill and submit forms if present (with test data)
       - Verify form validation feedback

    e) Capture screenshot for evidence
       agent-browser: agent-browser screenshot ".harness/screenshots/{route-slug}.browser-test.png"
       Playwright MCP: browser_take_screenshot
       (save to .harness/screenshots/ with .browser-test.png suffix)

    f) Record result: PASS / FAIL with details

Step 5: Write Findings to .harness/todos/
  - For each FAIL:
    Write to .harness/todos/{id}-browser-test-{route-slug}.md
    YAML frontmatter: status: pending, priority: P1/P2/P3
    Optional field: agent_source: test-browser
    (Note: agent_source is an optional extension to Phase 0's todo format.
    Phase 0 specifies status and priority as required fields. agent_source
    is additive — does not conflict.)
    Body: Route, Issue Description, Console Errors, Screenshot Path, Reproduction Steps
  - Priority assignment:
    P1: page crashes, 500 errors, blank page, JS exceptions
    P2: broken interactions, form submission failures, missing content
    P3: visual regressions, layout shifts, minor styling issues

Step 6: Close Browser (UNCONDITIONAL — must execute regardless of prior step failures)
  - This step MUST run even if Step 3, 4, or 5 fails or throws an error.
    Use try/finally semantics: if any prior step fails, skip to Step 6
    (close browser) then Step 7 (report the failure). Never leave orphaned
    browser processes.
  agent-browser: agent-browser close
  Playwright MCP: browser_close

Step 7: Report
  - Summary table:
    ## Browser Test Results
    Routes tested: {N} (of {total} affected, capped at 15)
    Passed: {pass_count}
    Failed: {fail_count}
    Timed out: {timeout_count}
    Skipped: {skip_count}

    | Route | Status | Notes |
    |---|---|---|
    | /dashboard | PASS | |
    | /settings | FAIL | Console error: TypeError |
    | /checkout | TIMEOUT | Exceeded 30s per-route limit |

    Findings written: {fail_count} todos in .harness/todos/
    Screenshots: .harness/screenshots/

  - IF all passed: "All {N} routes passed browser testing."
  - IF any failed: "{fail_count} issues found. Findings written to .harness/todos/ and
    will be included in the PR description by /ship."
  - IF skipped entirely: report reason (no tool, no server, no UI routes)
  - IF using Playwright MCP: note token cost warning
```

**Strict rules:**

- Fully autonomous — no interactive prompts (no headed/headless choice, no fix-now/skip choice)
- Always headless mode
- Write findings to `.harness/todos/` — do not attempt to fix issues
- Proceed to `/ship` (Step 4) regardless of findings — browser test failures are informational, not blocking
- Do not start the dev server — only detect if it's running
- Close the browser unconditionally when done (try/finally — prevent orphaned processes)
- Max 15 routes per run. Warn and link to standalone mode for more.
- 30s per-route timeout. 5min total step timeout.
- Screenshots go to `.harness/screenshots/` (cleaned each run, gitignored)

---

## Changes to Existing Files

### 1. Update `/harness:build` — add Step 3

Insert `/test-browser` as Step 3, between Step 2.5 (`/resolve_todo_parallel`) and Step 4 (`/ship`):

```
Step 3: /test-browser (auto-dispatched, self-scoping)
  - Maps changed files to UI routes (max 15)
  - IF zero routes: skip silently
  - IF no browser tool: skip with warning
  - IF dev server not running: skip with warning
  - ELSE: test routes (30s per route, 5min total), write findings to .harness/todos/
  - Proceed to Step 4 regardless of findings
  - Browser test findings included in /ship PR body
```

### 2. Update meta-orchestrator design doc

Add Step 3 to the `/harness:build` flow diagram (between Step 2.5 and Step 4):

```
  ├── Step 3: Browser Test (Phase 5)
  │     ├── Run /test-browser
  │     │     ├── Self-scoping: maps changed files to UI routes
  │     │     ├── Graceful skip: no tool, no server, no UI routes → skip
  │     │     ├── Tests up to 15 routes (30s timeout each, 5min total)
  │     │     └── Writes failures to .harness/todos/
  │     └── Proceed to Step 4 regardless of findings
```

Add to the failure handling table:

```
| Step 3 (browser test) | Browser findings in .harness/todos/ | Run /test-browser standalone |
```

Update `/ship` PR body section: note that browser test findings from `.harness/todos/` are included.

### 3. Create `.harness/screenshots/` directory

Add `.harness/screenshots/.gitkeep` and add to `.gitignore`:

```
# Browser test screenshots (generated by /test-browser, cleaned each run)
.harness/screenshots/*.png
```

`init-project.sh` update deferred to Phase Finale -- see Phase 0 deferral note.

---

## What NOT to Port from CE

| CE Component                                  | Decision            | Reason                                                                                                                                            |
| --------------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent-browser` skill (SKILL.md, 223 lines)   | Not ported as skill | Tool detection embedded in `/test-browser` command. No separate skill needed.                                                                     |
| `bug-reproduction-validator` agent (82 lines) | Deferred            | Cannot create without a wiring point. Deferred to a future phase that also creates `/reproduce-bug` command — both ship together, properly wired. |
| `/reproduce-bug` command (100 lines)          | Deferred            | CE version uses Rails-specific agents. Deferred alongside `bug-reproduction-validator`.                                                           |
| Interactive mode (headed/headless prompt)     | Removed             | `/test-browser` is autonomous in `/harness:build` — no user prompts                                                                               |
| "Fix now / Create todo / Skip" prompt         | Removed             | Fully autonomous — always writes todos, always proceeds                                                                                           |
| Human verification (OAuth, payments, SMS)     | Removed             | Autonomous command cannot prompt for human input                                                                                                  |
| Rails file-to-route mapping                   | Replaced            | Next.js App Router / monorepo patterns for LaunchPad's stack                                                                                      |
| `agent-browser install` auto-install          | Removed             | Command detects and warns — does not auto-install npm packages                                                                                    |

---

## Verification Checklist

### Files Created

- [ ] `.claude/commands/test-browser.md` — 7-step flow, dual browser tool support, self-scoping, graceful skip, autonomous (no prompts), MAX_ROUTES=15, 30s/5min timeouts, try/finally browser close

### Wiring

- [ ] `/harness:build` Step 3 auto-dispatches `/test-browser`
- [ ] `/test-browser` sits between Step 2.5 (resolve_todo_parallel) and Step 4 (ship)
- [ ] Browser test findings written to `.harness/todos/` (Phase 0 format + optional `agent_source`)
- [ ] Browser test findings included in `/ship` PR body (via .harness/todos/)
- [ ] Browser test findings NOT resolved by a second /resolve_todo_parallel (proceed to ship)
- [ ] Meta-orchestrator design doc updated with Step 3 (flow diagram + failure table + /ship PR body)

### Command Behavior

- [ ] Detects agent-browser CLI first (primary), falls back to Playwright MCP
- [ ] Logs Playwright MCP token cost warning when using fallback
- [ ] Skips silently when no UI routes affected (backend-only changes)
- [ ] Skips with warning when no browser tool available
- [ ] Skips with warning when dev server not running (port 3000, hardcoded)
- [ ] Port validated as numeric, 1-65535, URL always http://localhost:{port}
- [ ] Maps changed files to UI routes using Next.js App Router / monorepo patterns
- [ ] No `src/components/*` pattern (doesn't exist in this monorepo)
- [ ] No `*.scss` pattern (LaunchPad uses Tailwind CSS v4, no SCSS)
- [ ] No `tailwind.config.*` pattern (Tailwind v4 uses CSS-based config in globals.css)
- [ ] Tailwind v4 note: @theme directives in apps/web/src/styles/globals.css
- [ ] Route count capped at 15 with specificity-based selection
- [ ] Warns when cap is exceeded, suggests standalone mode for full test
- [ ] 30-second per-route timeout (FAIL with "Timeout" on exceed)
- [ ] 5-minute total step timeout (abort remaining routes)
- [ ] Screenshots written to `.harness/screenshots/` (not working directory root)
- [ ] Screenshot directory cleaned at start of each run
- [ ] Screenshot filenames use `.browser-test.png` suffix (matches .gitignore)
- [ ] Tests each affected route: navigate, snapshot, verify content, test interactions, screenshot
- [ ] Writes failures to `.harness/todos/` with P1/P2/P3 priority
- [ ] `agent_source` noted as optional extension to Phase 0 todo format
- [ ] Browser close is UNCONDITIONAL (try/finally — runs even if prior steps fail)
- [ ] Fully autonomous — no interactive prompts
- [ ] Always headless mode
- [ ] Does not attempt to fix issues (writes todos only)
- [ ] Does not start dev server (detect only)
- [ ] Proceeds to /ship (Step 4) regardless of findings
- [ ] Reports summary table with route-by-route results including timeout status

### Prerequisites (from prior phases)

- [ ] Phase 0: `/harness:build` pipeline exists with Step 2.5 and Step 4
- [ ] Phase 0: `.claude/commands/harness/build.md` exists (created by Phase 0)
- [ ] Phase 0: `.harness/todos/` directory exists
- [ ] Phase 0: `.harness/` directory has appropriate `.gitignore` entries
- [ ] Phase 0: Todo file format established (YAML frontmatter: status, priority)

### Integration

- [ ] `.harness/screenshots/.gitkeep` created
- [ ] `.gitignore` updated: `.harness/screenshots/*.png`
- [ ] `init-project.sh` -- **deferred to Phase Finale** (see Phase 0 deferral note)
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                                                                |
| ------------ | --------------------------------------------------------------------------------------------------- |
| Phase 6      | Compound learning system                                                                            |
| Phase 7      | `/commit` workflow wiring                                                                           |
| Future       | `bug-reproduction-validator` agent + `/reproduce-bug` command (deferred together — must ship wired) |
| Phase Finale | Documentation refresh for all command tables                                                        |
| Phase Finale | CE plugin removal                                                                                   |

---

## File Change Summary

| #   | File                                                   | Change                                                                                                                            | Priority |
| --- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1   | `.claude/commands/test-browser.md`                     | **Create** (heavy adaptation from CE — dual browser tool, autonomous, Next.js routes, MAX_ROUTES=15, timeouts, try/finally close) | P0       |
| 2   | `.claude/commands/harness/build.md`                    | **Edit** (created by Phase 0) — add Step 3 /test-browser between resolve and ship                                                 | P0       |
| 3   | `docs/reports/2026-03-30-meta-orchestrators-design.md` | **Edit** — add Step 3 to flow diagram, failure table, /ship PR body                                                               | P0       |
| 4   | `.harness/screenshots/.gitkeep`                        | **Create** — screenshot output directory                                                                                          | P1       |
| 5   | `.gitignore`                                           | **Edit** — add `.harness/screenshots/*.png`                                                                                       | P1       |
| 6   | `scripts/setup/init-project.sh`                        | **Deferred to Phase Finale** — see Phase 0 deferral note                                                                          | P1       |
| 7   | `.claude/commands/ship.md`                             | **Edit** (Phase 0) — add browser test screenshot/findings inclusion in PR body                                                    | P1       |
