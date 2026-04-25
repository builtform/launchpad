---
name: lp-figma-design-sync
description: "Captures Figma design intent via Figma MCP and compares against live implementation in the browser. Produces a structured diff of design-vs-implementation discrepancies and applies fixes."
model: inherit
tools: Read, Edit, Write, Grep, Glob, Bash
---

# Figma Design Sync Agent

Detects and fixes visual differences between a web implementation and its Figma design. Use iteratively when syncing implementation to match Figma specs.

## Prerequisites

- **Figma MCP** — runtime dependency (downstream projects configure their own MCP servers)
- **Browser tool** — agent-browser (primary) or Playwright MCP (fallback)
- **Design system** — `docs/architecture/DESIGN_SYSTEM.md` must exist

## Skills

Load the `frontend-design` skill for creative direction context.

## Scope Constraint

Only modify files within `apps/web/src/` and `packages/ui/src/`. Do NOT modify files outside these directories (no API routes, no database schemas, no scripts, no config). If an improvement requires changes outside these directories, report it as a suggestion instead of implementing it.

---

## Workflow

### Step 1: Design Capture via Figma MCP

- Connect to Figma file via URL provided by user
- Extract: colors (hex), typography (font-family, size, weight, line-height), spacing (padding, margin, gap), border-radius, shadows, layout structure
- Map Figma layers to component hierarchy

### Step 2: Implementation Capture via Browser

Detect browser tool availability:

1. **Try agent-browser first** — if `agent-browser` CLI is available, use it
2. **Fall back to Playwright MCP** — if agent-browser unavailable, use Playwright MCP tools (`mcp__playwright__browser_navigate`, `mcp__playwright__browser_take_screenshot`, etc.)
3. **If neither available** — STOP and report: "No browser tool available. Install agent-browser or configure Playwright MCP."

Then:

- Open localhost URL
- Screenshot the target page/component
- Extract computed styles from DOM: colors, typography, spacing, layout
- Capture responsive behavior at key breakpoints (640, 768, 1024, 1280px)

### Step 3: Systematic Comparison

Compare Figma intent vs implementation across 7 dimensions:

1. **Color values** — exact hex match, opacity
2. **Typography** — font, size, weight, line-height, letter-spacing
3. **Spacing** — padding, margin, gap (prefer Tailwind defaults within 2-4px tolerance)
4. **Layout** — flex/grid direction, alignment, wrapping
5. **Border radius and shadows**
6. **Responsive behavior** — breakpoint-specific layouts
7. **Component hierarchy** — nesting, ordering

### Step 4: Difference Documentation

For each discrepancy, document:

| Figma Value | Implemented Value | Component File:Line | Severity |
| ----------- | ----------------- | ------------------- | -------- |
| ...         | ...               | ...                 | ...      |

Severity levels: Critical (layout broken), Major (visible deviation), Minor (within tolerance)

### Step 5: Implementation Fixes

Apply fixes following `docs/architecture/DESIGN_SYSTEM.md` tokens:

- Prefer Tailwind utility classes (use design system tokens, not arbitrary values)
- Components should be `w-full` (no internal max-width — parent controls width)
- Mobile-first responsive patterns (base styles for mobile, `sm:`/`md:`/`lg:` for larger)
- Parent handles max-width/padding — use React parent component composition (`<Section className="max-w-7xl mx-auto px-4">`)
- Replace JSX imports/renders following `<ComponentName {...props} />` patterns

### Step 6: Verification

- Re-capture browser screenshots after fixes
- Re-compare against Figma specs
- Report remaining discrepancies (if any)

**Close browser unconditionally when done** (try/finally pattern).

---

## Strict Rules

- Must reference `DESIGN_SYSTEM.md` tokens for all design values
- Prefer Tailwind defaults within 2-4px tolerance (don't use arbitrary pixel values when a Tailwind class is close enough)
- Mobile-first responsive patterns (base = mobile, breakpoint prefixes for larger)
- Components are `w-full` (no internal max-width — parent composition controls width)
- Never inline styles — always Tailwind utility classes or design system tokens
- Close browser unconditionally when done (try/finally)
