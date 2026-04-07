# Phase 10: Design Workflow Import

**Date:** 2026-04-06
**Depends on:** Phase 0 (pipeline infrastructure, `.harness/` directory, `/harness:plan`, `review_design_agents` key), Phase 3 (`/harden-plan` in `/harness:plan`), Phase 5 (dual browser tool pattern -- agent-browser/Playwright)
**Branch:** `feat/design-workflow`
**Status:** Plan -- v3 (add feature-video/rclone/imgup, eliminate Phase 12)

---

## Decisions (All Finalized)

| Decision                             | Answer                                                                                                                                                                                            |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent names                          | `figma-design-sync`, `design-implementation-reviewer`, `design-iterator`, `design-ui-auditor`, `design-responsive-auditor`, `design-alignment-checker`                                            |
| Agent namespace                      | `design/` (`.claude/agents/design/`)                                                                                                                                                              |
| Skill names                          | `frontend-design`, `web-design-guidelines`, `responsive-design` (ported from BuiltForm to LaunchPad), `rclone` (process skill -- cloud file management), `imgup` (process skill -- image hosting) |
| Command names                        | `/design-review`, `/design-polish`, `/design-onboard`, `/copy` (shell), `/copy-review` (shell), `/feature-video`                                                                                  |
| Pipeline wiring                      | Step 2 of `/harness:plan` (design before planning)                                                                                                                                                |
| Status contract change               | Design moves before planning: `shaped -> designed/"design:skipped" -> planned`                                                                                                                    |
| Browser automation                   | Dual-tool: agent-browser primary, Playwright MCP fallback (Phase 5 pattern)                                                                                                                       |
| Design artifact storage              | `.harness/design-artifacts/` (git-tracked, approved screenshots) + `.harness/screenshots/` (ephemeral, gitignored)                                                                                |
| UI detection                         | Parse section spec for UI keywords + check file references in `apps/web/` or `packages/ui/` + always confirm with user                                                                            |
| `/copy` and `/copy-review`           | Shell commands in LaunchPad -- downstream projects populate with their own copy agents. BuiltForm populates in Phase 11                                                                           |
| `review_design_agents` population    | `design-ui-auditor`, `design-responsive-auditor`, `design-alignment-checker`, `design-implementation-reviewer` (conditional -- only dispatched when Figma artifacts exist)                        |
| `review_copy_agents` population      | Shell -- downstream projects populate. BuiltForm adds `copy-auditor` in Phase 11                                                                                                                  |
| `/review` design dispatch condition  | Artifact-based: check if `.harness/design-artifacts/[section]-approved.png` exists (not status-based)                                                                                             |
| `frontend-design` skill in LaunchPad | Yes -- process skill (design methodology, not domain knowledge). Same category as brainstorming, document-review                                                                                  |
| Model                                | `model: inherit` for all agents                                                                                                                                                                   |
| Branch                               | `feat/design-workflow`                                                                                                                                                                            |

---

## Purpose

Phase 10 fills the design gap in the `/harness:plan` pipeline. Before Phase 10, the design step is a placeholder -- sections go from `shaped` directly to planning (`/pnf`) with no visual design work. After Phase 10:

1. Every section with UI work goes through an interactive design workflow (autonomous first draft, interactive refinement, review and audit) before implementation planning begins
2. Design decisions are made with full context (DESIGN_SYSTEM.md, APP_FLOW.md, FRONTEND_GUIDELINES.md, section spec) and guided by 3 skills (`frontend-design`, `web-design-guidelines`, `responsive-design`)
3. Design is validated by 4 design review agents (3 auditors + 1 Figma reviewer) before proceeding to planning
4. Implementation plans (`/pnf`) are informed by concrete design artifacts, not abstract descriptions
5. The autonomous build (`/harness:build`) has a lightweight safety net -- `review_design_agents` catch implementation regressions

**Status contract reorder.** Phase 10 changes the status contract to place design before planning. The previous order was `shaped -> planned -> hardened -> designed/"design:skipped" -> approved`. The new order is `shaped -> designed/"design:skipped" -> planned -> hardened -> approved`. This means design work happens on the raw section spec (post-shaping), and implementation planning (`/pnf`) runs with concrete design artifacts already available. `/harden-plan` then stress-tests a plan that already accounts for real visual decisions.

---

## Architecture: How Phase 10 Components Wire In

Phase 10 has two integration points: the main design workflow inside `/harness:plan`, and the safety net inside `/review` during `/harness:build`.

### Integration Point 1: `/harness:plan` Step 2 -- Design Workflow

```
/harness:plan (meta-orchestrator -- Phase 0, updated by Phase 10)
  |
  +-- Step 1: Resolve target
  |
  +-- Step 2: Design Step (Phase 10)                   <-- THIS IS WHAT WE'RE BUILDING
  |     |
  |     +-- Detect UI scope:
  |     |     +-- Parse section spec for UI keywords (component, page, layout, hero, etc.)
  |     |     +-- Check if spec references files in apps/web/ or packages/ui/
  |     |     +-- IF indicators found -> "This section involves UI work. Run design? (yes/skip)"
  |     |     +-- IF no indicators -> "No UI work detected. Planning UI work? (yes/skip)"
  |     |     +-- IF user says "skip" -> writes "design:skipped" -> jump to Step 3
  |     |
  |     +-- Step 2a: Autonomous First Draft
  |     |     +-- Load: DESIGN_SYSTEM.md, APP_FLOW.md, FRONTEND_GUIDELINES.md, section spec
  |     |     +-- Load skills: frontend-design, web-design-guidelines, responsive-design
  |     |     +-- Load copy: /copy (reads copy brief from section spec if exists)
  |     |     +-- Build UI components (write TSX/CSS following design system tokens)
  |     |     +-- Open browser (agent-browser primary, Playwright fallback)
  |     |     |     +-- Requires dev server running (detect, don't start)
  |     |     +-- Screenshot -> self-evaluate -> adjust -> screenshot (3-5 auto-cycles)
  |     |     +-- Offer /design-onboard if section involves onboarding/empty states
  |     |     +-- Present first draft to user with live localhost URL
  |     |
  |     +-- Step 2b: Interactive Refinement
  |     |     +-- User gives feedback -> design-iterator auto-dispatches
  |     |     +-- User requests Figma sync -> figma-design-sync dispatches
  |     |     +-- User requests systematic polish -> /design-polish runs
  |     |     +-- Skills stay loaded: frontend-design, web-design-guidelines, responsive-design
  |     |     +-- Session guides user: "Give feedback / Run /design-polish / Provide Figma URL / Say 'looks good'"
  |     |
  |     +-- Step 2c: Design Review & Audit
  |           +-- /design-review runs first (sequential -- comprehensive 8 design + 4 tech dimensions, AI slop detection)
  |           +-- Then in parallel:
  |           |     +-- design-ui-auditor (5 quick checks)
  |           |     +-- design-responsive-auditor (6 responsive checks)
  |           |     +-- design-alignment-checker (14-dimension audit)
  |           |     +-- design-implementation-reviewer (Figma comparison -- IF Figma URL was provided during session)
  |           |     +-- /copy-review (shell -- dispatches review_copy_agents if configured)
  |           +-- Present findings
  |           +-- IF issues -> back to 2b (iterate/fix -> re-audit)
  |           +-- Re-audit cap: 3 cycles maximum. After 3 re-audit passes (Step 2c runs
  |           |     a total of 3 times), if findings remain, present to user:
  |           |     "N findings remain after 3 review cycles. Approve with known issues /
  |           |     Continue iterating / Revise approach?"
  |           +-- WHEN clean -> save approved screenshots to .harness/design-artifacts/
  |                 +-- writes "designed" -> proceed to Step 2d
  |
  |     +-- Step 2d: Design Walkthrough Recording (optional)
  |           +-- /feature-video (optional -- record design walkthrough)
  |           +-- Captures screenshots of approved design -> MP4+GIF
  |           +-- Uploads via rclone (if configured) or imgup
  |           +-- Useful for sharing design decisions with team
  |           +-- proceed to Step 3
  |
  +-- Step 3: /pnf (reads section spec + design artifacts from .harness/design-artifacts/)
  +-- Step 4: /harden-plan
  +-- Step 5: Human Approval Gate
  |     +-- "Approve and start build? (yes / revise design / revise plan / revise both)"
  |     +-- "yes" -> proceed to /harness:build
  |     +-- "revise design" -> reset status to "shaped", clear .harness/design-artifacts/,
  |     |     re-enter Step 2 (full design cycle restarts)
  |     +-- "revise plan" -> reset status to "designed" or "design:skipped" (whichever was set),
  |     |     re-enter Step 3 (/pnf). Design artifacts preserved. Plan regenerated.
  |     +-- "revise both" -> reset status to "shaped", clear .harness/design-artifacts/,
  |           re-enter Step 2. Everything regenerated.
```

### Integration Point 2: `/harness:build` -> `/review` + `/feature-video` -- Safety Net + Demo

```
/review (Phase 0, updated by Phase 10)
  +-- Dispatch review_agents (always)
  +-- IF Prisma changes: dispatch review_db_agents
  +-- IF .harness/design-artifacts/[section]-approved.png exists:
  |     dispatch review_design_agents (design-ui-auditor, design-responsive-auditor, design-alignment-checker, design-implementation-reviewer [conditional -- only if Figma artifacts exist])
  +-- IF review_copy_agents configured: dispatch review_copy_agents

/harness:build (after /ship -- optional)
  +-- /feature-video (optional -- record feature demo for PR)
  +-- Captures screenshots of built feature -> MP4+GIF via ffmpeg
  +-- Uploads via rclone (if configured) or imgup
  +-- Updates PR description with embedded video
```

The design dispatch condition is artifact-based, not status-based. This avoids coupling `/review` to the section registry -- it simply checks if approved design screenshots exist. If they do, the build should match them, so the auditors run.

### Updated Status Contract

Phase 10 reorders the status contract. The design step moves before planning:

**Before Phase 10:**

```
defined -> shaped -> planned -> hardened -> designed/"design:skipped" -> approved -> reviewed -> built
```

**After Phase 10:**

```
defined -> shaped -> designed/"design:skipped" -> planned -> hardened -> approved -> reviewed -> built
```

**Updated `/harness:plan` step order:**

```
Step 1: Resolve target
Step 2: Design Step (Phase 10)         <-- moved before /pnf
Step 3: /pnf [target]                  <-- was Step 1.5
Step 4: /harden-plan [plan-path]       <-- was Step 2
Step 5: Human Approval Gate            <-- was Step 4
```

**Resolve step routing update:**

- `"design:skipped"` or `designed` -> Step 3 (plan)
- `shaped` -> Step 2 (design)
- `planned` -> Step 4 (harden)
- `hardened` -> Step 5 (approval)

---

## Component Definitions

### AGENTS (6)

### 1. `figma-design-sync` Agent

**File:** `.claude/agents/design/figma-design-sync.md`
**CE source:** `agents/design/figma-design-sync.md` (191 lines) -- medium adaptation
**Dispatched by:** `/harness:plan` Step 2b (user provides Figma URL)
**Also usable:** Standalone (user invokes directly)

**Adaptations from CE:**

- ERB/ViewComponent examples removed -- all examples in React/TSX component patterns
- `<%= render SomeComponent.new(...) %>` replaced with JSX import/render (`<ComponentName {...props} />`)
- Wrapper pattern: parent handles max-width/padding -- adapted to React parent component composition (`<Section className="max-w-7xl mx-auto px-4">`)
- Add: loads `frontend-design` skill for creative direction context
- Add: follows Phase 5 dual browser tool pattern (agent-browser primary, Playwright fallback)
- Remove: all Ruby, Rails, Stimulus, Turbo, ViewComponent references

**Frontmatter:**

```yaml
---
name: figma-design-sync
description: "Captures Figma design intent via Figma MCP and compares against live implementation in the browser. Produces a structured diff of design-vs-implementation discrepancies and applies fixes."
model: inherit
---
```

**Core workflow (6 steps):**

```
Step 1: Design Capture via Figma MCP
  - Connect to Figma file via URL provided by user
  - Extract: colors (hex), typography (font-family, size, weight, line-height),
    spacing (padding, margin, gap), border-radius, shadows, layout structure
  - Map Figma layers to component hierarchy

Step 2: Implementation Capture via Browser
  - Open localhost URL (agent-browser primary, Playwright fallback)
  - Screenshot the target page/component
  - Extract computed styles from DOM: colors, typography, spacing, layout
  - Capture responsive behavior at key breakpoints (640, 768, 1024, 1280px)

Step 3: Systematic Comparison
  - Compare Figma intent vs implementation across 7 dimensions:
    1. Color values (exact hex match, opacity)
    2. Typography (font, size, weight, line-height, letter-spacing)
    3. Spacing (padding, margin, gap -- prefer Tailwind defaults within 2-4px)
    4. Layout (flex/grid direction, alignment, wrapping)
    5. Border radius and shadows
    6. Responsive behavior (breakpoint-specific layouts)
    7. Component hierarchy (nesting, ordering)

Step 4: Difference Documentation
  - For each discrepancy, document:
    Figma value | Implemented value | Component file:line | Severity

Step 5: Implementation Fixes
  - Apply fixes following DESIGN_SYSTEM.md tokens
  - Prefer Tailwind utility classes (use design system tokens, not arbitrary values)
  - Components should be w-full (no internal max-width -- parent controls width)
  - Mobile-first responsive patterns (base styles for mobile, sm:/md:/lg: for larger)

Step 6: Verification
  - Re-capture browser screenshots after fixes
  - Re-compare against Figma specs
  - Report remaining discrepancies (if any)
```

**Tool requirement:** Figma MCP (runtime dependency -- not configured in LaunchPad, downstream projects configure their own MCP servers), agent-browser/Playwright (Phase 5 dual tool pattern)

**Scope constraint:** Only modify files within `apps/web/src/` and `packages/ui/src/`. Do NOT modify files outside these directories (no API routes, no database schemas, no scripts, no config). If an improvement requires changes outside these directories, report it as a suggestion instead of implementing it.

**Strict rules:**

- Must reference DESIGN_SYSTEM.md tokens for all design values
- Prefer Tailwind defaults within 2-4px tolerance (don't use arbitrary pixel values when a Tailwind class is close enough)
- Mobile-first responsive patterns (base = mobile, breakpoint prefixes for larger)
- Components are w-full (no internal max-width -- parent composition controls width)
- Never inline styles -- always Tailwind utility classes or design system tokens
- Close browser unconditionally when done (try/finally)

---

### 2. `design-implementation-reviewer` Agent

**File:** `.claude/agents/design/design-implementation-reviewer.md`
**CE source:** `agents/design/design-implementation-reviewer.md` (110 lines) -- light adaptation
**Dispatched by:** `/harness:plan` Step 2c (parallel audit, conditional on Figma URL provided during session), `/review` via `review_design_agents` (safety net, conditional on Figma artifacts)
**Also usable:** Standalone (user invokes directly), `/harness:plan` Step 2b (user requests design review against Figma)

**Adaptations from CE:** Minimal -- already framework-agnostic. Add dual browser tool pattern (agent-browser primary, Playwright fallback). Remove any Rails-specific examples if present.

**Frontmatter:**

```yaml
---
name: design-implementation-reviewer
description: "Captures live implementation state and compares against Figma design specs. Produces a structured review report with severity ratings. Does NOT modify code."
model: inherit
---
```

**Core workflow (4 steps):**

```
Step 1: Capture Implementation State
  - Open target URL in browser (agent-browser primary, Playwright fallback)
  - Screenshot at key breakpoints (640, 768, 1024, 1280px)
  - Extract computed styles and layout measurements

Step 2: Retrieve Figma Specs
  - Connect to Figma file via Figma MCP
  - Extract design token values, layout specs, component hierarchy
  - Note any design annotations or developer handoff notes

Step 3: Systematic Comparison (7 dimensions)
  1. Color accuracy (hex values, opacity, gradients)
  2. Typography fidelity (font, size, weight, line-height, letter-spacing)
  3. Spacing precision (padding, margin, gap)
  4. Layout structure (flex/grid, alignment, order)
  5. Interactive states (hover, focus, active, disabled)
  6. Responsive behavior (breakpoint-specific layouts)
  7. Component hierarchy and nesting

Step 4: Generate Structured Review
  For each finding:
  - Category label
  - Severity symbol and description
  - Figma spec value vs implemented value
  - File path and line number
  - Screenshot evidence

  Severity levels:
    Pass       -- correct implementation
    Minor      -- within tolerance (1-2px, slight color shift)
    Major      -- visible deviation from design intent
    Measurements -- dimensional data for reference
```

**Report-only:** Does NOT modify code. Returns structured review text.
**Tool requirement:** Figma MCP + agent-browser/Playwright

---

### 3. `design-iterator` Agent

**File:** `.claude/agents/design/design-iterator.md`
**CE source:** `agents/design/design-iterator.md` (224 lines) -- medium adaptation
**Dispatched by:** `/harness:plan` Step 2a (autonomous self-improvement cycles) and Step 2b (user-directed iteration)
**Also usable:** Standalone

**Adaptations from CE:**

- Add: loads `frontend-design` skill for creative direction + anti-AI-slop guidance
- Add: loads `web-design-guidelines` skill for engineering compliance
- Add: loads `responsive-design` skill for mobile-first responsive patterns
- Add: dual browser tool pattern (agent-browser primary, Playwright fallback)
- Keep: competitor research capability (generic web research, not domain-specific)
- Keep: focused screenshot strategy (capture only the area being iterated)
- Keep: ONE change per iteration (isolate improvements for clear before/after comparison)
- Keep: stop when no improvement detected (diminishing returns detector)
- Remove: all Rails/ERB/ViewComponent/Stimulus/Turbo references
- Replace: all code examples with React/TSX/Tailwind equivalents

**Frontmatter:**

```yaml
---
name: design-iterator
description: "Iterative design improvement agent. Takes screenshots, analyzes design quality, implements ONE improvement per cycle, and repeats. Loads frontend-design, web-design-guidelines, and responsive-design skills for creative direction and compliance."
model: inherit
color: violet
---
```

**Core workflow:**

```
Step 1: Set Up Browser
  - Detect browser tool (agent-browser primary, Playwright fallback)
  - Navigate to target URL
  - IF no browser tool available: WARN and switch to code-only mode
    (analyze TSX/CSS files without visual feedback)

Step 2: Iteration Loop (3-5 cycles in autonomous mode (hard cap: 5), user-triggered iterations in interactive mode (one cycle per user feedback request, no upper limit on how many times the user can request iterations))
  For each iteration:
    a) Screenshot current state (focused area, not full page)
    b) Analyze against loaded skills:
       - frontend-design: creative direction, anti-AI-slop, bold aesthetic
       - web-design-guidelines: keyboard, forms, animation, layout compliance
       - responsive-design: mobile-first, breakpoints, touch targets
    c) Identify ONE highest-impact improvement
       Priority order: layout structure > typography > color/contrast > spacing > motion
    d) Implement the change (write TSX/CSS)
    e) Document what changed and why
    f) Screenshot post-change
    g) Compare before/after
    h) IF improvement detected: continue to next iteration
       IF no improvement or regression: STOP and report

Step 3: Report
  - Summary of iterations completed
  - Before/after comparison for each change
  - Remaining suggestions (if any) for user to consider
```

**Modifies code:** Yes (iterative improvements to TSX/CSS files)
**Scope constraint:** Only modify files within `apps/web/src/` and `packages/ui/src/`. Do NOT modify files outside these directories (no API routes, no database schemas, no scripts, no config). If an improvement requires changes outside these directories, report it as a suggestion instead of implementing it.
**Tool requirement:** agent-browser/Playwright (graceful degradation to code-only if neither available)

---

### 4. `design-ui-auditor` Agent

**File:** `.claude/agents/design/design-ui-auditor.md`
**Source:** BuiltForm `/audit-ui` command (3.6 KB) -- converted from command to agent
**Dispatched by:** `/harness:plan` Step 2c (parallel audit), `/review` via `review_design_agents` (safety net)

**Adaptations:**

- Command -> agent conversion (add frontmatter, examples, dispatch model)
- Remove user-facing command syntax -- agent dispatch interface
- Keep: 5 checks (visual hierarchy, density, consistency, Jobs filter, responsive)
- Keep: DESIGN_SYSTEM.md token requirement
- Keep: file:line fix format, NEW TOKEN NEEDED flags
- Add: P1/P2/P3 severity output (for `/review` integration)
- Remove: any BuiltForm-specific component references

**Frontmatter:**

```yaml
---
name: design-ui-auditor
description: "Quick UI audit: 5 checks covering visual hierarchy, density, consistency, Jobs filter, and responsive behavior. Returns findings with P1/P2/P3 severity and file:line fix locations. Does NOT modify code."
model: inherit
tools: Read, Grep, Glob
---
```

**5 Checks:**

```
1. Visual Hierarchy
   - Heading scale follows DESIGN_SYSTEM.md type ramp
   - Primary CTA is visually dominant (size, color, contrast)
   - Content sections have clear visual separation
   - Reading flow follows natural eye path (F-pattern or Z-pattern)

2. Density
   - Adequate whitespace between sections (not cramped, not wasteful)
   - Touch targets meet minimum 44x44px
   - Text line length within 45-75 characters
   - Consistent padding/margin rhythm (uses design system spacing scale)

3. Consistency
   - All colors from DESIGN_SYSTEM.md palette (no arbitrary hex values)
   - Typography uses defined font families and size scale
   - Border radius values from design system tokens
   - Interactive element styles match across the page

4. Jobs Filter (3 questions per element)
   - What job is this element doing for the user?
   - Is it the simplest way to accomplish that job?
   - Does removing it hurt the user's ability to complete their task?
   - Flag elements that fail all 3: "Element at [file:line] has no clear job"

5. Responsive
   - Layout adapts at sm/md/lg/xl breakpoints
   - No horizontal scroll at any breakpoint
   - Images and media scale proportionally
   - Navigation adapts (mobile menu, desktop nav)
```

**Output format:**

```
## UI Audit Findings

### P1 (Critical)
- [file:line] Description of issue. Fix: specific instruction.

### P2 (Important)
- [file:line] Description. Fix: instruction. NEW TOKEN NEEDED: [token-name]

### P3 (Minor)
- [file:line] Description. Fix: instruction.

### Passed
- Check 1: Visual Hierarchy -- PASS
```

**Report-only:** Does NOT modify code (returns findings as text; `/review` or orchestrator writes files)
**Tool restriction:** Read, Grep, Glob only (no Edit, no Bash)

---

### 5. `design-responsive-auditor` Agent

**File:** `.claude/agents/design/design-responsive-auditor.md`
**Source:** BuiltForm `/audit-responsive` command (4.5 KB) -- converted from command to agent
**Dispatched by:** `/harness:plan` Step 2c (parallel audit), `/review` via `review_design_agents` (safety net)

**Adaptations:** Same pattern as `design-ui-auditor`. Command-to-agent conversion with frontmatter, P1/P2/P3 severity output, BuiltForm-specific references removed.

**Frontmatter:**

```yaml
---
name: design-responsive-auditor
description: "Responsive design audit: 6 checks covering breakpoints, mobile-first patterns, touch targets, overflow, container queries, and WCAG responsive requirements. Returns findings with P1/P2/P3 severity. Does NOT modify code."
model: inherit
tools: Read, Grep, Glob
---
```

**6 Checks:**

```
1. Breakpoints
   - Uses Tailwind v4 breakpoints (sm:640, md:768, lg:1024, xl:1280, 2xl:1536)
   - No arbitrary breakpoint values (no @media (min-width: 700px))
   - Breakpoint usage is consistent across related components
   - Layout changes at breakpoints are meaningful (not cosmetic-only)

2. Mobile-First
   - Base styles target mobile (no breakpoint prefix = mobile)
   - Larger breakpoints ADD complexity (sm: md: lg: prefixes)
   - No desktop-first patterns (no max-width media queries)
   - Components render correctly with zero breakpoint prefixes

3. Touch Targets
   - All interactive elements >= 44x44px on mobile
   - Adequate spacing between touch targets (>= 8px gap)
   - No hover-only interactions (must have touch/click equivalent)
   - Form inputs have visible tap areas

4. Overflow
   - No horizontal scroll at any viewport width (320px to 2560px)
   - Long text content wraps or truncates gracefully
   - Tables have responsive strategy (scroll, stack, or collapse)
   - Images constrained with max-w-full

5. Container Queries
   - Component-level responsive behavior uses container queries where appropriate
   - Parent containers have containment context (container-type)
   - Container query breakpoints align with component needs (not page breakpoints)
   - Fallback for browsers without container query support

6. WCAG Responsive
   - Content reflows at 400% zoom (WCAG 1.4.10)
   - Text resizable to 200% without loss of content (WCAG 1.4.4)
   - No loss of information in portrait/landscape orientation
   - Focus indicators visible at all viewport sizes
```

**Output format:** Same P1/P2/P3 structure as `design-ui-auditor`.
**Report-only:** Does NOT modify code
**Tool restriction:** Read, Grep, Glob only (no Edit, no Bash)

---

### 6. `design-alignment-checker` Agent

**File:** `.claude/agents/design/design-alignment-checker.md`
**Source:** BuiltForm `ui-ux-architect` skill quick-check mode -- converted from skill to agent
**Dispatched by:** `/harness:plan` Step 2c (parallel audit), `/review` via `review_design_agents` (safety net)

**Adaptations:**

- Skill quick-check mode extracted into a full agent with frontmatter, examples
- Keep: 14-dimension audit (comprehensive design alignment check)
- Keep: Jobs Filter (3 questions per element)
- Keep: DESIGN_SYSTEM.md required (refuse if missing)
- Add: P1/P2/P3 severity output
- Remove: any BuiltForm-specific component or page references

**Frontmatter:**

```yaml
---
name: design-alignment-checker
description: "Comprehensive 14-dimension design alignment audit against DESIGN_SYSTEM.md. Covers visual hierarchy, spacing, typography, color, alignment, components, iconography, motion, empty states, loading states, error states, dark mode, density, and accessibility. Does NOT modify code."
model: inherit
tools: Read, Grep, Glob
---
```

**14 Dimensions:**

```
 1. Visual Hierarchy   -- heading scale, CTA prominence, content grouping, scan path
 2. Spacing            -- margin/padding rhythm, section separation, consistent gaps
 3. Typography         -- font families, size scale, weight usage, line-height, letter-spacing
 4. Color              -- palette adherence, contrast ratios, semantic color usage, no arbitrary hex
 5. Alignment          -- grid alignment, baseline alignment, optical alignment corrections
 6. Components         -- design system component usage, no custom recreations of existing components
 7. Iconography        -- consistent icon set, appropriate sizes, meaningful usage (not decorative noise)
 8. Motion             -- purposeful transitions, consistent duration/easing, no gratuitous animation
 9. Empty States       -- helpful messaging, clear next action, illustration/icon (not blank)
10. Loading States     -- skeleton screens or spinners, no layout shift on content load
11. Error States       -- clear error messaging, recovery instructions, inline validation
12. Dark Mode          -- if applicable: proper color token usage, no hardcoded colors, contrast maintained
13. Density            -- information density appropriate for context, adequate breathing room
14. Accessibility      -- color contrast (WCAG AA minimum), focus indicators, alt text, aria labels
```

**Jobs Filter (applied to each element flagged in any dimension):**

```
For each flagged element, ask:
  1. What job is this element doing for the user?
  2. Is it the simplest way to accomplish that job?
  3. Does removing it hurt the user's ability to complete their task?

IF element fails all 3 -> flag as "No clear job" (likely remove or rethink)
IF element passes 1+ -> keep, but fix the specific dimension violation
```

**Output format:** Same P1/P2/P3 structure as `design-ui-auditor`, with dimension labels.
**Report-only:** Does NOT modify code
**Tool restriction:** Read, Grep, Glob only (no Edit, no Bash)

---

### SKILLS (5)

### 7. `frontend-design` Skill

**File:** `.claude/skills/frontend-design/SKILL.md`
**Source:** BuiltForm `.claude/skills/frontend-design/SKILL.md` -- ported to LaunchPad
**Loaded by:** `design-iterator` (creative direction), `/design-review` (anti-pattern detection), `/design-polish` (refinement guidance), `/harness:plan` Step 2a (autonomous build context)
**Category:** Process skill (design methodology -- NOT domain knowledge). Same category as `brainstorming`, `document-review`, `compound-docs`.

**Adaptations:** Remove any BuiltForm-specific references (product name, brand colors, domain language). Keep all design principles, anti-AI-slop rules, typography/color/motion/spatial/background guidelines. These are universal process guidelines, not project-specific.

**Supporting files (ported from BuiltForm):**

- `.claude/skills/frontend-design/references/typography.md` -- font selection, type scale, hierarchy, readability
- `.claude/skills/frontend-design/references/color-and-contrast.md` -- palette construction, contrast ratios, semantic color
- `.claude/skills/frontend-design/references/spatial-design.md` -- spacing systems, layout grids, whitespace rhythm
- `.claude/skills/frontend-design/references/motion-design.md` -- transition timing, easing curves, purposeful animation
- `.claude/skills/frontend-design/references/interaction-design.md` -- affordances, feedback, state communication
- `.claude/skills/frontend-design/references/responsive-design.md` -- fluid layouts, breakpoint strategy, progressive enhancement
- `.claude/skills/frontend-design/references/ux-writing.md` -- microcopy, action labels, error messages, tone

**Key content areas:**

- Bold aesthetic direction (not generic, not safe, not "AI slop")
- Design thinking framework: purpose, tone, constraints, differentiation
- NEVER list: overused fonts (Inter for everything), cliched color schemes (blue/white SaaS), predictable layouts (hero-features-pricing-footer), AI slop patterns (gradient blobs, generic illustrations, hollow buzzwords)
- Typography: pair fonts with intent, establish clear hierarchy, readable body text
- Color: intentional palette with semantic meaning, adequate contrast, restrained usage
- Motion: purposeful transitions that communicate state changes, no gratuitous animation
- Spatial: consistent spacing rhythm, breathing room, layout grids
- Background: texture, depth, layering (not flat white on white)

---

### 8. `web-design-guidelines` Skill

**File:** `.claude/skills/web-design-guidelines/SKILL.md`
**Source:** BuiltForm `.claude/skills/web-design-guidelines/SKILL.md` -- ported to LaunchPad
**Loaded by:** `design-iterator` (engineering compliance), `/harness:plan` Step 2a (build compliance)
**Category:** Process skill (engineering compliance rules -- NOT domain knowledge)

**Adaptations:** None needed -- already framework-agnostic. Contains MUST/SHOULD/NEVER rules that apply to any web project.

**Key content areas:**

- Keyboard: all interactive elements keyboard-accessible, visible focus indicators, logical tab order
- Forms: labels on all inputs, inline validation, clear error states, submit button feedback
- Animation: `prefers-reduced-motion` respected, no auto-playing animation, purposeful motion only
- Layout: no horizontal scroll, content reflow at zoom, responsive at all viewports
- Content: text truncation strategy, long content handling, empty state designs
- Performance: lazy loading for off-screen images, optimized font loading, minimal layout shift
- Dark mode: proper token usage if applicable, no hardcoded colors
- Hydration: server/client render consistency, no hydration mismatch patterns

---

### 9. `responsive-design` Skill

**File:** `.claude/skills/responsive-design/SKILL.md`
**Source:** BuiltForm `.claude/skills/responsive-design/SKILL.md` -- ported to LaunchPad
**Loaded by:** `design-iterator` (responsive patterns), `/define-design` (Mode A -- already wired), `/shape-section` (Mode B -- already wired), `/pnf` (Mode C -- already wired), `/harness:plan` Step 2a (build context)
**Category:** Process skill (responsive methodology -- NOT domain knowledge)

**Adaptations:** None needed -- already framework-agnostic. Contains mobile-first methodology, breakpoint strategy, fluid typography, and container query patterns that apply to any web project.

**Key content areas:**

- Mobile-first: base styles target mobile, breakpoint prefixes add complexity
- Breakpoints: use Tailwind v4 breakpoints (sm:640, md:768, lg:1024, xl:1280, 2xl:1536)
- Touch targets: minimum 44x44px, adequate spacing between interactive elements
- Fluid typography: clamp() for responsive text, maintain readability across viewports
- Container queries: component-level responsive behavior, containment context
- Images: responsive images with srcset/sizes, art direction with picture element
- Tables: responsive table strategies (horizontal scroll, stack, or collapse)

---

### COMMANDS (6)

### 10. `/design-review` Command

**File:** `.claude/commands/design-review.md`
**Source:** BuiltForm `/design-review.md` (5.9 KB) -- ported to LaunchPad
**Called by:** `/harness:plan` Step 2c (comprehensive design audit)
**Also usable:** Standalone

**Adaptations:** Remove any BuiltForm-specific references (product name, specific pages, brand guidelines). Keep the 2-part structure, AI slop detection, skill loading, and structured output format.

**Loads skills:** `frontend-design`

**2-Part Structure:**

```
Part 1: Design Critique (8 dimensions)
  1. Visual Identity    -- does the design have a distinctive personality (not generic AI)?
  2. Typography         -- intentional font pairing, hierarchy, readability
  3. Color Strategy     -- palette coherence, contrast, semantic usage
  4. Spatial Design     -- whitespace rhythm, breathing room, density balance
  5. Layout             -- grid system, alignment, visual flow
  6. Motion & Interaction -- purposeful transitions, hover/focus states, feedback
  7. Content Hierarchy  -- information architecture, scanability, progressive disclosure
  8. Emotional Impact   -- does the design evoke the intended feeling? Is it memorable?

Part 2: Technical Audit (4 dimensions)
  1. Design System Compliance -- all values from DESIGN_SYSTEM.md tokens?
  2. Responsive Integrity     -- mobile-first, breakpoints, touch targets
  3. Accessibility            -- contrast ratios, focus indicators, screen reader
  4. Performance              -- image optimization, font loading, layout shift

AI Slop Detection (integrated into Part 1):
  - Flag generic gradient blobs, stock illustration style, hollow buzzwords
  - Flag overused patterns: hero-features-pricing-footer, blue/white SaaS palette
  - Flag cookie-cutter layouts that could belong to any product
  - Severity: P1 if multiple slop indicators, P2 for individual instances
```

**Output format:**

```
## Design Review

### Part 1: Design Critique
#### 1. Visual Identity
[Assessment] [Rating: Strong/Adequate/Weak/AI Slop]

... (all 8 dimensions)

### Part 2: Technical Audit
#### 1. Design System Compliance
[Assessment] [Findings with file:line]

... (all 4 dimensions)

### Summary
- Critical issues (P1): [count]
- Important issues (P2): [count]
- Minor issues (P3): [count]
- AI Slop flags: [count]
- Overall: [PASS / NEEDS ITERATION / MAJOR REVISION]
```

**Report-only:** Does NOT modify code

---

### 11. `/design-polish` Command

**File:** `.claude/commands/design-polish.md`
**Source:** BuiltForm `/design-polish.md` (7.0 KB) -- ported to LaunchPad
**Called by:** `/harness:plan` Step 2b (systematic refinement after user feedback or audit findings)
**Also usable:** Standalone

**Adaptations:** Remove any BuiltForm-specific references. Keep the 4-phase structure, skill loading, and 15-item polish checklist.

**Loads skills:** `frontend-design`

**4-Phase Structure:**

```
Phase 1: Normalize
  - Audit all design values against DESIGN_SYSTEM.md tokens
  - Replace arbitrary values with nearest design system token
  - Standardize spacing rhythm across components
  - Fix inconsistent border-radius, shadow, color usage

Phase 2: Polish
  - Refine typography hierarchy (heading scale, body text, captions)
  - Adjust whitespace for visual breathing room
  - Fine-tune color contrast and saturation
  - Add subtle depth cues (shadows, borders, backgrounds)
  - Refine interactive states (hover, focus, active, disabled)

Phase 3: Copy
  - Review all UI text (headings, labels, buttons, empty states, errors)
  - Tighten microcopy (shorter, clearer, action-oriented)
  - Ensure consistent voice and tone
  - Fix placeholder text that was never replaced

Phase 4: Harden
  - Verify responsive behavior at all breakpoints
  - Test edge cases: long text, empty content, single item, many items
  - Check accessibility: contrast, focus, screen reader
  - Verify dark mode (if applicable)
  - Performance check: image sizes, font loading, layout shift
```

**15-Item Polish Checklist:**

```
 1. All colors from design system palette
 2. Typography uses defined scale (no arbitrary font sizes)
 3. Spacing follows design system rhythm
 4. Border radius from design tokens
 5. Shadows from design tokens
 6. Interactive states complete (hover, focus, active, disabled)
 7. Icons consistent set and size
 8. Empty states designed (not blank)
 9. Loading states designed (skeleton or spinner)
10. Error states designed (message + recovery action)
11. Responsive at all breakpoints (no horizontal scroll)
12. Touch targets >= 44x44px on mobile
13. Color contrast >= 4.5:1 (WCAG AA)
14. Focus indicators visible
15. No AI slop (generic gradients, stock illustrations, hollow buzzwords)
```

**Modifies code:** Yes (applies refinements to TSX/CSS files)
**Scope constraint:** Only modify files within `apps/web/src/` and `packages/ui/src/`. Do NOT modify files outside these directories (no API routes, no database schemas, no scripts, no config). If an improvement requires changes outside these directories, report it as a suggestion instead of implementing it.

---

### 12. `/design-onboard` Command

**File:** `.claude/commands/design-onboard.md`
**Source:** BuiltForm `/design-onboard.md` (6.3 KB) -- ported to LaunchPad
**Called by:** `/harness:plan` Step 2a (conditional -- offered when section involves onboarding/empty states)
**Also usable:** Standalone

**Adaptations:** Remove any BuiltForm-specific references (product-specific onboarding flows, domain language). Keep onboarding principles, empty state design patterns, guided tour patterns, and progressive onboarding methodology.

**Key content areas:**

```
Onboarding Principles:
  - Progressive disclosure (don't overwhelm on first visit)
  - Show value before asking for input
  - Celebrate first completion (positive reinforcement)
  - Reduce time-to-first-value to minimum steps

Empty State Design:
  - Helpful messaging (explain what goes here, not just "No data")
  - Clear primary action (one CTA, not a blank page)
  - Illustration or icon (visual warmth, not blank whitespace)
  - Example content or sample data (show what success looks like)

Guided Tours:
  - Tooltips for feature discovery (non-blocking, dismissible)
  - Step-by-step walkthroughs for complex flows
  - Contextual help (appears where the user needs it)
  - Skip option always available (respect user autonomy)

Progressive Onboarding:
  - Core features first, advanced features revealed over time
  - Checklist pattern for multi-step setup
  - Progress indicators (how far along, what's next)
  - Re-engagement for abandoned onboarding flows
```

**Modifies code:** Yes (adds onboarding flows, empty states, guided tour components when used)

---

### 13. `/copy` Command (Shell)

**File:** `.claude/commands/copy.md`
**Source:** New -- LaunchPad shell command
**Called by:** `/harness:plan` Step 2a (loads copy from section spec for autonomous build)
**Also usable:** Standalone

**Purpose:** Reads copy brief from section spec (`## Copy` or `## Copy Brief` heading). If found, returns copy text as context for the design build agent. If not found, warns: "No copy brief found. Components will use placeholder text. Run web-copy skill during /shape-section to create copy." Downstream projects extend this command with their own copy agents/skills (BuiltForm populates in Phase 11 with `web-copy`, `hormozi-offer`, `hormozi-leads`, `hormozi-moneymodel`).

**Does NOT modify code** -- provides context only

---

### 14. `/copy-review` Command (Shell)

**File:** `.claude/commands/copy-review.md`
**Source:** New -- LaunchPad shell command
**Called by:** `/harness:plan` Step 2c (parallel with design auditors)
**Also usable:** Standalone

**Purpose:** Shell command that dispatches copy review agents from `review_copy_agents` in `agents.yml`. In LaunchPad, the list is empty (no copy review agents by default). BuiltForm populates in Phase 11 with `copy-auditor` agent.

**Flow:**

```
Step 1: Read Agent Configuration
  - Read .launchpad/agents.yml
  - Extract review_copy_agents list

Step 2: Evaluate List
  - IF list empty or key not present:
      Skip silently (no copy review agents configured -- this is expected in LaunchPad)
      Return: "No copy review agents configured. Skipping copy review."
  - IF list populated:
      Proceed to Step 3

Step 3: Dispatch Agents
  - For each agent in review_copy_agents:
      Dispatch in parallel (same pattern as /review agent dispatch)
      Each agent receives: section spec, implemented component files, copy context
  - Collect all findings

Step 4: Return Findings
  - Aggregate findings from all dispatched agents
  - Return structured findings to the calling step (Step 2c)
  - Each finding includes: agent name, severity (P1/P2/P3), description, file:line
```

**Shell note:** This command is intentionally a no-op in LaunchPad. The `review_copy_agents` list starts empty. Downstream projects populate the list in their `agents.yml` to activate copy review during the design workflow. BuiltForm adds `copy-auditor` in Phase 11.

**Does NOT modify code** -- dispatches agents and collects findings

---

### 15. `/feature-video` Command

**File:** `.claude/commands/feature-video.md`
**CE source:** `commands/feature-video.md` -- medium adaptation (Rails file-to-route -> Next.js App Router)
**Called by:** `/harness:plan` Step 2 (after Step 2c passes -- record design walkthrough). Also called by `/harness:build` after `/ship` (record feature demo for PR). Also standalone.

**Adaptations from CE:**

- Rails file-to-route mapping -> Next.js App Router (`app/**/page.tsx` -> routes)
- `bin/dev` -> `pnpm dev` for dev server
- Remove Stimulus/Turbo references
- Keep: ffmpeg screenshot-to-video, rclone upload, PR description update, agent-browser capture

**Dependencies:** agent-browser CLI, ffmpeg (required), rclone (optional -- for cloud upload)

**Flow:**

```
Step 1: Parse PR Context
  - Read current branch, PR description (if exists), changed files
  - Map changed files to routes (apps/web/src/app/**/page.tsx -> URL paths)

Step 2: Plan Shot List
  - Identify key routes/components affected by changes
  - Order shots for narrative flow (overview -> detail -> interaction)

Step 3: Capture Screenshots
  - Open dev server (detect running pnpm dev, don't start)
  - Navigate to each route via agent-browser
  - Capture screenshots at key breakpoints
  - Capture interaction states (hover, click, form fill) if applicable

Step 4: Convert to Video
  - Use ffmpeg to stitch screenshots into MP4 (3-5 seconds per frame)
  - Generate GIF version (lower quality, smaller size, for inline preview)
  - Output to .harness/screenshots/ (ephemeral, gitignored)

Step 5: Upload
  - IF rclone configured: upload MP4+GIF to configured remote (S3, R2, etc.)
  - ELSE: upload via imgup (quick public hosting, no setup needed)
  - Return public URLs

Step 6: Update PR Description
  - IF PR exists: append video embed to PR description
  - IF no PR: output URLs for manual inclusion
  - Format: ![Feature Demo](url) with GIF inline, MP4 link
```

**Wiring points:**

1. `/harness:plan` Step 2 -- design walkthrough after design approval (optional)
2. `/harness:build` after `/ship` -- feature demo for PR (optional)
3. Standalone

**Modifies:** PR description (via `gh pr edit`). Does NOT modify code.

---

### SKILLS (continued)

### 16. `rclone` Skill

**File:** `.claude/skills/rclone/SKILL.md`
**CE source:** `skills/rclone/SKILL.md` -- zero adaptation (100% framework-agnostic)
**Loaded by:** `/feature-video` (for cloud storage upload)
**Category:** Process skill (cloud file management -- NOT domain knowledge)

**Dependencies:** rclone binary (brew/apt/script install), cloud provider credentials

**Key content areas:**

- Setup checking: verify rclone installed, check configured remotes
- Installation guide: brew install rclone, apt install rclone, curl script
- Remote configuration: S3, Cloudflare R2, Backblaze B2, DigitalOcean Spaces, Google Drive, Dropbox
- Common operations: upload (rclone copy), sync (rclone sync), list (rclone ls/lsf), move (rclone move)
- Flags: --progress, --transfers, --checkers, --dry-run, --verbose
- Large file handling: chunked transfers, multipart uploads, bandwidth limiting
- Verification: rclone check (compare source and dest), rclone hashsum
- Troubleshooting: auth failures, permission errors, rate limiting, timeout handling

---

### 17. `imgup` Skill

**File:** `.claude/skills/imgup/SKILL.md`
**CE source:** Referenced in CE's `/workflows:work` but no standalone SKILL.md exists in CE. New lightweight skill.
**Loaded by:** `/feature-video` (alternative to rclone for quick image uploads), `/harness:plan` Step 2 (upload design screenshots for sharing)
**Category:** Process skill (image hosting -- NOT domain knowledge)

**Dependencies:** imgup CLI tool (npm install)

**Key content areas:**

- Usage guide: upload images to public hosting services
- Supported hosts: pixhost (no API key required), catbox, imagebin, beeimg
- Quick sharing: for PR descriptions and design documentation
- Output: returns public URL for embedding in markdown
- Limitations: best for screenshots and small files, no persistent storage guarantees
- Comparison with rclone: imgup is lighter (no cloud provider setup needed), rclone is better for videos and persistent storage

**Note:** Lighter alternative to rclone -- no cloud provider setup needed. Best for screenshots and small files. rclone is better for videos and persistent storage.

---

## Changes to Existing Files

### 1. Update `/harness:plan` (`.claude/commands/harness/plan.md`)

Phase 10 makes three changes to `/harness:plan`:

**a) Reorder steps -- design before planning:**

The current step order (Phase 0):

```
Step 1:   Resolve target
Step 1.5: /pnf
Step 2:   /harden-plan
Step 3:   Design step [placeholder]
Step 4:   Human Approval Gate
```

The new step order (Phase 10):

```
Step 1: Resolve target
Step 2: Design Step (3 core substeps + optional 2d recording)
Step 3: /pnf [target]
Step 4: /harden-plan [plan-path] --auto
Step 5: Human Approval Gate (yes / revise design / revise plan / revise both)
```

**b) Replace design step placeholder with full 3-substep workflow (2a/2b/2c) + optional Step 2d (feature-video recording):**

Replace the Phase 0 placeholder:

```
Step 3: Design Step [Phase 10]
  IF section has UI components:
    Dispatch design workflow (agents defined in Phase 10)
    Registry status -> "designed"
  ELSE:
    Registry status -> "design:skipped"
```

With the full Step 2 workflow described in the Architecture section above (2a/2b/2c).

**c) Update resolve step routing:**

The resolve step must route based on the new status order:

```
Resolve target:
  "hardened" -> Step 5 (approval)       [was Step 4]
  "planned" -> Step 4 (harden)          [was Step 2]
  "designed" or "design:skipped" -> Step 3 (plan)  [NEW]
  "shaped" -> Step 2 (design)           [was Step 1.5 -> plan]
  "defined"/none -> "Not shaped. Run /harness:define"
```

**Canonical file loading for Step 2a:**

```
Load these files as context for the autonomous first draft:
  1. docs/architecture/DESIGN_SYSTEM.md     (design tokens, palette, typography)
  2. docs/architecture/APP_FLOW.md          (navigation, user journeys)
  3. docs/architecture/FRONTEND_GUIDELINES.md (component patterns, file structure)
  4. Section spec file                      (what to build)
  5. .harness/design-artifacts/ (existing approved designs for visual consistency)
```

**UI detection logic:**

```
UI keyword list: component, page, layout, hero, section, card, modal, dialog,
  form, input, button, nav, sidebar, header, footer, table, list, grid,
  dashboard, chart, graph, onboarding, wizard, stepper, carousel, accordion,
  tab, panel, dropdown, tooltip, popover, badge, avatar, banner, toast,
  notification, empty state, loading, skeleton, spinner

File reference check: any path containing apps/web/ or packages/ui/

Decision:
  IF (keyword count >= 2) OR (file reference found):
    "This section involves UI work. Run design workflow? (yes/skip)"
  ELSE:
    "No UI work detected. Planning UI work anyway? (yes/skip)"
  IF user says "skip":
    Write status: "design:skipped" -> jump to Step 3
```

---

### 2. Update `/review` (`.claude/commands/review.md`)

Change the design agent dispatch condition from status-based to artifact-based:

**Before (Phase 0 -- status-based):**

```
IF section status is "designed":
  dispatch review_design_agents
```

**After (Phase 10 -- artifact-based):**

```
IF .harness/design-artifacts/[section]-approved.png exists:
  dispatch review_design_agents (design-ui-auditor, design-responsive-auditor, design-alignment-checker, design-implementation-reviewer [conditional -- only if Figma artifacts exist])
IF review_copy_agents list is non-empty in agents.yml:
  dispatch review_copy_agents in parallel
```

This decouples `/review` from the section registry. The presence of approved design screenshots is a concrete, file-system-verifiable signal that design work was done and should be preserved. The section name for the glob pattern is extracted from the current build target.

---

### 3. Update `agents.yml` (`.launchpad/agents.yml`)

Populate `review_design_agents` and add `review_copy_agents`:

```yaml
review_design_agents:
  - design-ui-auditor
  - design-responsive-auditor
  - design-alignment-checker
  - design-implementation-reviewer # conditional -- only dispatched when Figma artifacts exist

review_copy_agents: []
# Populated by downstream projects. BuiltForm adds copy-auditor in Phase 11.
```

---

### 4. Update `init-project.sh` (`scripts/setup/init-project.sh`)

Add `.harness/design-artifacts/.gitkeep` to the directory creation block:

```bash
mkdir -p .harness/design-artifacts
touch .harness/design-artifacts/.gitkeep
```

This goes alongside the existing `.harness/todos/`, `.harness/observations/`, and `.harness/screenshots/` directory creation.

---

### 5. Update `.gitignore`

Add ephemeral design media patterns:

```
# Design workflow ephemeral media (generated by design-iterator, cleaned each run)
.harness/screenshots/*.mp4
.harness/screenshots/*.gif
```

Note: `.harness/screenshots/*.png` was already added by Phase 5. `.harness/design-artifacts/` is NOT gitignored -- approved screenshots are git-tracked.

---

### 6. Update meta-orchestrator design doc (`docs/reports/2026-03-30-meta-orchestrators-design.md`)

Update the `/harness:plan` flow to reflect the new step order (design before planning) and the full Step 2 design workflow:

```
/harness:plan (Phase 0, updated by Phase 10)
  |
  +-- Step 1: Resolve target
  +-- Step 2: Design Step (Phase 10)
  |     +-- UI detection (keyword + file reference check)
  |     +-- 2a: Autonomous first draft (skills + browser + 3-5 auto-cycles)
  |     +-- 2b: Interactive refinement (design-iterator, figma-design-sync, /design-polish)
  |     +-- 2c: Design review & audit (/design-review sequential, then 4 design review agents + /copy-review in parallel)
  |     +-- Save approved screenshots to .harness/design-artifacts/
  +-- Step 3: /pnf (now informed by design artifacts)
  +-- Step 4: /harden-plan
  +-- Step 5: Human Approval Gate
  |     +-- "Approve and start build? (yes / revise design / revise plan / revise both)"
  |     +-- "yes" -> proceed to /harness:build
  |     +-- "revise design" -> reset status to "shaped", clear .harness/design-artifacts/,
  |     |     re-enter Step 2 (full design cycle restarts)
  |     +-- "revise plan" -> reset status to "designed" or "design:skipped" (whichever was set),
  |     |     re-enter Step 3 (/pnf). Design artifacts preserved. Plan regenerated.
  |     +-- "revise both" -> reset status to "shaped", clear .harness/design-artifacts/,
  |           re-enter Step 2. Everything regenerated.
```

Update the status contract diagram to show the new order: `shaped -> designed/"design:skipped" -> planned`.

Update the `/review` dispatch section to show artifact-based design agent dispatch and `review_copy_agents` dispatch.

---

### 7. Update porting report (`docs/reports/2026-03-28-porting-ce-to-launchpad.md`)

Update Phase 10 entry in the Phase Summary table:

```
| 10 | Design Workflow Import | 6 design agents (figma-design-sync, design-implementation-reviewer, design-iterator, design-ui-auditor, design-responsive-auditor, design-alignment-checker), 5 skills (frontend-design, web-design-guidelines, responsive-design, rclone, imgup), 6 commands (/design-review, /design-polish, /design-onboard, /copy, /copy-review, /feature-video), status contract reorder | Plan -- v3 |
```

Update the agent/command/skill inventory tables to include Phase 10 components. Update the status contract description to reflect the new order.

---

## What NOT to Port from CE

| CE Component                                   | Decision                                  | Reason                                                                                                                                                         |
| ---------------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend-design` skill (CE version, 43 lines) | Port BuiltForm's enhanced version instead | BuiltForm version includes 7 reference files (typography, color, spatial, motion, interaction, responsive, UX writing) -- far richer than CE's minimal version |
| `agent-browser` skill (SKILL.md, 223 lines)    | Do not port                               | Tool detection logic embedded in each agent that uses browser automation (Phase 5 pattern). No separate skill file needed.                                     |
| `imgup` skill                                  | Included in Phase 10 (v3)                 | Moved from Phase 12 -- supports `/feature-video` and design screenshot sharing                                                                                 |
| `feature-video` command                        | Included in Phase 10 (v3)                 | Moved from Phase 12 -- wired into `/harness:plan` Step 2 and `/harness:build` after `/ship`                                                                    |
| CE `frontend-design` SKILL.md (43 lines)       | Superseded                                | BuiltForm's version (with 7 reference files) is the canonical source                                                                                           |
| Rails/ERB/ViewComponent patterns               | Not ported                                | All design agents use React/TSX/Tailwind patterns exclusively                                                                                                  |
| Stimulus/Turbo references                      | Not ported                                | Not applicable to React/Next.js stack                                                                                                                          |

---

## Verification Checklist

### Files Created

- [ ] `.claude/agents/design/figma-design-sync.md` -- 6-step workflow, Figma MCP + dual browser tool, `model: inherit`, loads `frontend-design` skill
- [ ] `.claude/agents/design/design-implementation-reviewer.md` -- 4-step comparison workflow, report-only, Figma MCP + dual browser tool, `model: inherit`
- [ ] `.claude/agents/design/design-iterator.md` -- iteration loop, loads 3 skills, dual browser tool, ONE change per iteration, `model: inherit`, `color: violet`
- [ ] `.claude/agents/design/design-ui-auditor.md` -- 5 checks, P1/P2/P3 output, report-only, Read/Grep/Glob only, `model: inherit`
- [ ] `.claude/agents/design/design-responsive-auditor.md` -- 6 checks, P1/P2/P3 output, report-only, Read/Grep/Glob only, `model: inherit`
- [ ] `.claude/agents/design/design-alignment-checker.md` -- 14 dimensions + Jobs Filter, P1/P2/P3 output, report-only, Read/Grep/Glob only, `model: inherit`
- [ ] `.claude/skills/frontend-design/SKILL.md` -- design methodology, anti-AI-slop, bold aesthetic direction
- [ ] `.claude/skills/frontend-design/references/typography.md` -- font selection, type scale, hierarchy
- [ ] `.claude/skills/frontend-design/references/color-and-contrast.md` -- palette, contrast, semantic color
- [ ] `.claude/skills/frontend-design/references/spatial-design.md` -- spacing systems, layout grids
- [ ] `.claude/skills/frontend-design/references/motion-design.md` -- transitions, easing, purposeful animation
- [ ] `.claude/skills/frontend-design/references/interaction-design.md` -- affordances, feedback, states
- [ ] `.claude/skills/frontend-design/references/responsive-design.md` -- fluid layouts, breakpoints
- [ ] `.claude/skills/frontend-design/references/ux-writing.md` -- microcopy, tone, error messages
- [ ] `.claude/skills/web-design-guidelines/SKILL.md` -- MUST/SHOULD/NEVER engineering compliance
- [ ] `.claude/skills/responsive-design/SKILL.md` -- mobile-first methodology, breakpoints, touch targets
- [ ] `.claude/commands/design-review.md` -- 8 design + 4 tech dimensions, AI slop detection, loads `frontend-design`
- [ ] `.claude/commands/design-polish.md` -- 4-phase structure, 15-item checklist, loads `frontend-design`
- [ ] `.claude/commands/design-onboard.md` -- onboarding principles, empty states, guided tours
- [ ] `.claude/commands/copy.md` -- shell command, reads copy from section spec, warns if missing
- [ ] `.claude/commands/copy-review.md` -- shell command, dispatches `review_copy_agents`, skips silently if empty
- [ ] `.claude/commands/feature-video.md` -- ffmpeg + rclone/imgup + agent-browser, Next.js App Router route mapping
- [ ] `.claude/skills/rclone/SKILL.md` -- cloud storage management, setup checking, remote configuration, common operations
- [ ] `.claude/skills/imgup/SKILL.md` -- image hosting for quick sharing, pixhost/catbox/imagebin/beeimg
- [ ] `.harness/design-artifacts/.gitkeep` -- approved screenshot directory (git-tracked)

### Wiring

- [ ] `/harness:plan` Step 2 contains full design workflow (2a/2b/2c + optional 2d feature-video)
- [ ] `/harness:plan` step order is: resolve -> design -> plan -> harden -> approve
- [ ] `/harness:plan` resolve routing updated for new status order (`shaped` -> Step 2, `designed`/`"design:skipped"` -> Step 3)
- [ ] Status contract reordered: `shaped -> designed/"design:skipped" -> planned -> hardened -> approved`
- [ ] `review_design_agents` populated in `agents.yml`: `design-ui-auditor`, `design-responsive-auditor`, `design-alignment-checker`, `design-implementation-reviewer` (conditional on Figma artifacts)
- [ ] `review_copy_agents: []` added to `agents.yml`
- [ ] `/review` dispatches `review_design_agents` based on `.harness/design-artifacts/[section]-approved.png` existence (artifact-based, not status-based)
- [ ] `/review` dispatches `review_copy_agents` when list is non-empty
- [ ] `/copy` loads copy context from section spec for Step 2a
- [ ] `/copy-review` dispatches `review_copy_agents` in Step 2c
- [ ] Step 2a loads canonical files: DESIGN_SYSTEM.md, APP_FLOW.md, FRONTEND_GUIDELINES.md, section spec
- [ ] Step 2a loads 3 skills: `frontend-design`, `web-design-guidelines`, `responsive-design`
- [ ] Step 2b dispatches `design-iterator` on user feedback, `figma-design-sync` on Figma URL, `/design-polish` on polish request
- [ ] Step 2c runs `/design-review` first (sequential), then 4 design review agents + `/copy-review` run in parallel
- [ ] Approved screenshots saved to `.harness/design-artifacts/` with `[section]-approved.png` naming
- [ ] Step 5 approval gate presents 4 options: yes / revise design / revise plan / revise both
- [ ] "revise design" resets status to `shaped`, clears `.harness/design-artifacts/`, re-enters Step 2
- [ ] "revise plan" resets status to `designed` or `"design:skipped"` (whichever was set), re-enters Step 3 (design artifacts preserved)
- [ ] "revise both" resets status to `shaped`, clears `.harness/design-artifacts/`, re-enters Step 2
- [ ] `/feature-video` wired into `/harness:plan` Step 2 (after Step 2c -- optional design walkthrough recording)
- [ ] `/feature-video` wired into `/harness:build` after `/ship` (optional feature demo for PR)
- [ ] `/feature-video` loads `rclone` skill (for cloud upload) or falls back to `imgup`
- [ ] `rclone` skill loaded by `/feature-video`
- [ ] `imgup` skill loaded by `/feature-video` (alternative to rclone)

### Prerequisites (from prior phases)

- [ ] Phase 0: `/harness:plan` exists with placeholder design step
- [ ] Phase 0: `.harness/` directory structure exists
- [ ] Phase 0: `review_design_agents` key exists in `agents.yml` (empty, ready to populate)
- [ ] Phase 0: `/review` command exists with conditional agent dispatch
- [ ] Phase 0: Status contract established (Phase 10 reorders it)
- [ ] Phase 3: `/harden-plan` exists and is wired into `/harness:plan`
- [ ] Phase 5: Dual browser tool pattern established (agent-browser primary, Playwright fallback)
- [ ] Phase 5: `.harness/screenshots/` directory exists (ephemeral screenshots)

### Integration

- [ ] `.harness/design-artifacts/.gitkeep` created
- [ ] `.gitignore` updated: `.harness/screenshots/*.mp4`, `.harness/screenshots/*.gif`
- [ ] `init-project.sh` updated to create `.harness/design-artifacts/` directory
- [ ] `agents.yml` updated with `review_design_agents` population (4 agents: 3 auditors + design-implementation-reviewer conditional) and `review_copy_agents: []`
- [ ] Meta-orchestrator design doc updated with new `/harness:plan` step order and design workflow
- [ ] Porting report updated with Phase 10 components
- [ ] Status contract reorder documented in all referencing files
- [ ] CLAUDE.md progressive disclosure table updated (add design-related docs if needed)
- [ ] `docs/architecture/REPOSITORY_STRUCTURE.md` updated with `.claude/agents/design/` directory and `.harness/design-artifacts/`
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| Phase 11     | BuiltForm copy agent wrappers (`copy-writer`, `offer-architect`, `leads-strategist`, `moneymodel-architect`) |
| Phase 11     | BuiltForm `copy-auditor` agent (populates `review_copy_agents`)                                              |
| Phase 11     | BuiltForm `/copy` population (web-copy + Hormozi agents)                                                     |
| Phase 11     | BuiltForm `/copy-review` population (`copy-auditor` agent)                                                   |
| Phase 11     | BuiltForm remaining skill wiring (`stripe-best-practices`, etc.)                                             |
| Phase 11     | BuiltForm-specific design agent conversions (`audit-ui` -> `design-ui-auditor` downstream overrides, etc.)   |
| Phase Finale | Update all location-referencing docs                                                                         |
| Phase Finale | CE plugin removal                                                                                            |

**Phase 11 dependency:** Phase 11 depends on Phase 10 for:

- `/copy` command exists (Phase 11 extends it with copy skill invocations)
- `/copy-review` command exists (Phase 11 populates `review_copy_agents`)
- `review_copy_agents` key exists in `agents.yml` (Phase 11 adds `copy-auditor`)
- 4 design review agents exist (3 auditors + design-implementation-reviewer; Phase 11 may create downstream overrides)
- `frontend-design` skill exists in LaunchPad (Phase 11 wires BuiltForm-specific additions)

---

## File Change Summary

| #   | File                                                              | Change                                                                                                                                                       | Priority |
| --- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| 1   | `.claude/agents/design/figma-design-sync.md`                      | **Create** (medium adaptation from CE -- Figma MCP + dual browser tool, React/TSX patterns)                                                                  | P0       |
| 2   | `.claude/agents/design/design-implementation-reviewer.md`         | **Create** (light adaptation from CE -- report-only, Figma MCP + dual browser tool)                                                                          | P0       |
| 3   | `.claude/agents/design/design-iterator.md`                        | **Create** (medium adaptation from CE -- loads 3 skills, ONE change per iteration, dual browser tool)                                                        | P0       |
| 4   | `.claude/agents/design/design-ui-auditor.md`                      | **Create** (converted from BuiltForm command -- 5 checks, P1/P2/P3, Read/Grep/Glob only)                                                                     | P0       |
| 5   | `.claude/agents/design/design-responsive-auditor.md`              | **Create** (converted from BuiltForm command -- 6 checks, P1/P2/P3, Read/Grep/Glob only)                                                                     | P0       |
| 6   | `.claude/agents/design/design-alignment-checker.md`               | **Create** (converted from BuiltForm skill -- 14 dimensions + Jobs Filter, P1/P2/P3, Read/Grep/Glob only)                                                    | P0       |
| 7   | `.claude/skills/frontend-design/SKILL.md`                         | **Create** (ported from BuiltForm -- design methodology, anti-AI-slop, bold aesthetic)                                                                       | P0       |
| 8   | `.claude/skills/frontend-design/references/typography.md`         | **Create** (ported from BuiltForm -- font selection, type scale, hierarchy)                                                                                  | P0       |
| 9   | `.claude/skills/frontend-design/references/color-and-contrast.md` | **Create** (ported from BuiltForm -- palette, contrast, semantic color)                                                                                      | P0       |
| 10  | `.claude/skills/frontend-design/references/spatial-design.md`     | **Create** (ported from BuiltForm -- spacing systems, layout grids)                                                                                          | P0       |
| 11  | `.claude/skills/frontend-design/references/motion-design.md`      | **Create** (ported from BuiltForm -- transitions, easing, animation)                                                                                         | P0       |
| 12  | `.claude/skills/frontend-design/references/interaction-design.md` | **Create** (ported from BuiltForm -- affordances, feedback, states)                                                                                          | P0       |
| 13  | `.claude/skills/frontend-design/references/responsive-design.md`  | **Create** (ported from BuiltForm -- fluid layouts, breakpoints)                                                                                             | P0       |
| 14  | `.claude/skills/frontend-design/references/ux-writing.md`         | **Create** (ported from BuiltForm -- microcopy, tone, error messages)                                                                                        | P0       |
| 15  | `.claude/skills/web-design-guidelines/SKILL.md`                   | **Create** (ported from BuiltForm -- MUST/SHOULD/NEVER engineering compliance)                                                                               | P0       |
| 16  | `.claude/skills/responsive-design/SKILL.md`                       | **Create** (ported from BuiltForm -- mobile-first, breakpoints, touch targets)                                                                               | P0       |
| 17  | `.claude/commands/design-review.md`                               | **Create** (ported from BuiltForm -- 8 design + 4 tech dimensions, AI slop detection)                                                                        | P0       |
| 18  | `.claude/commands/design-polish.md`                               | **Create** (ported from BuiltForm -- 4-phase structure, 15-item checklist)                                                                                   | P0       |
| 19  | `.claude/commands/design-onboard.md`                              | **Create** (ported from BuiltForm -- onboarding principles, empty states)                                                                                    | P0       |
| 20  | `.claude/commands/copy.md`                                        | **Create** (new shell -- reads copy from section spec, warns if missing)                                                                                     | P0       |
| 21  | `.claude/commands/copy-review.md`                                 | **Create** (new shell -- dispatches review_copy_agents, skips if empty)                                                                                      | P0       |
| 22  | `.harness/design-artifacts/.gitkeep`                              | **Create** (approved screenshot directory, git-tracked)                                                                                                      | P0       |
| 23  | `.claude/commands/feature-video.md`                               | **Create** (medium adaptation from CE -- ffmpeg + rclone/imgup + agent-browser, Next.js App Router route mapping)                                            | P0       |
| 24  | `.claude/skills/rclone/SKILL.md`                                  | **Create** (zero adaptation from CE -- cloud storage management, 100% framework-agnostic)                                                                    | P0       |
| 25  | `.claude/skills/imgup/SKILL.md`                                   | **Create** (new lightweight skill -- image hosting for quick sharing)                                                                                        | P0       |
| 26  | `.claude/commands/harness/plan.md`                                | **Edit** (Phase 0) -- reorder steps (design before planning), replace placeholder with full design workflow (2a/2b/2c + optional 2d), update resolve routing | P0       |
| 27  | `.claude/commands/review.md`                                      | **Edit** (Phase 0) -- artifact-based design dispatch, add review_copy_agents dispatch                                                                        | P0       |
| 28  | `.launchpad/agents.yml`                                           | **Edit** (Phase 0) -- populate review_design_agents, add review_copy_agents: []                                                                              | P0       |
| 29  | `scripts/setup/init-project.sh`                                   | **Edit** -- add .harness/design-artifacts/ directory creation                                                                                                | P1       |
| 30  | `.gitignore`                                                      | **Edit** -- add .harness/screenshots/_.mp4 and .harness/screenshots/_.gif                                                                                    | P1       |
| 31  | `docs/reports/2026-03-30-meta-orchestrators-design.md`            | **Edit** -- update /harness:plan flow (step reorder, design workflow), /review dispatch, status contract                                                     | P1       |
| 32  | `docs/reports/2026-03-28-porting-ce-to-launchpad.md`              | **Edit** -- update Phase 10 entry, agent/command/skill inventories, status contract                                                                          | P1       |
| 33  | `CLAUDE.md`                                                       | **Edit** -- update progressive disclosure table if design docs are added                                                                                     | P1       |
| 34  | `docs/architecture/REPOSITORY_STRUCTURE.md`                       | **Edit** -- add .claude/agents/design/, .harness/design-artifacts/, 5 skill directories, 1 command                                                           | P1       |
