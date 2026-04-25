---
name: lp-react-best-practices
description: >
  React and Next.js performance, architecture, and composition patterns.
  70 rules across 9 categories, prioritized by impact (CRITICAL > HIGH > MEDIUM > LOW).
  Enforces correct async patterns, bundle optimization, server-side performance,
  client-side data fetching, re-render optimization, rendering performance,
  JavaScript micro-optimizations, composition architecture, and advanced patterns.
  Triggers on: writing React components, reviewing Next.js code, refactoring UI,
  optimizing performance, designing component APIs.
---

<!-- ported-from: vercel-labs/agent-skills (react-best-practices + composition-patterns)
     original-author: Vercel Engineering
     port-date: 2026-04-06
     upstream-version: 1.0.0 (both skills)
     license: MIT
     merge-note: 62 rules from react-best-practices + 8 rules from composition-patterns = 70 rules in 9 categories
     note: Generic for any Next.js 15 + React 19 + Tailwind v4 + Prisma monorepo. -->

**Apply every rule in this skill when writing, reviewing, or refactoring React/Next.js code in this project. Do not skip rules based on subjective judgment.**

## Trigger

Activate this skill when:

- Writing new React components or Next.js pages/layouts/routes
- Implementing data fetching (client or server-side)
- Reviewing or refactoring existing React/Next.js code
- Optimizing bundle size, load times, or rendering performance
- Designing component APIs or refactoring component architecture
- Working with compound components, context providers, or state management patterns

Example invocations:

- "Create a new dashboard page with data fetching"
- "Refactor the Composer component to support multiple variants"
- "Optimize the project list rendering performance"

## The Job

1. **Identify applicable categories.** Scan the code change against the 9 categories below. Load the relevant reference file(s) for categories that apply.

2. **Apply rules in priority order.** CRITICAL rules block merging. HIGH rules require justification to skip. MEDIUM/LOW rules apply when relevant.

3. **Show incorrect/correct patterns.** When flagging a violation, show the incorrect pattern from the reference file and the correct alternative. Do not just name the rule.

4. **Produce a compliance summary.** After implementation or review, list which rules were applied and any that were intentionally skipped with justification.

## Rule Categories by Priority

| #   | Category                             | Impact      | Rules | Reference                                                                      |
| --- | ------------------------------------ | ----------- | ----- | ------------------------------------------------------------------------------ |
| 1   | Eliminating Waterfalls               | CRITICAL    | 5     | [references/async-patterns.md](mdc:references/async-patterns.md)               |
| 2   | Bundle Size Optimization             | CRITICAL    | 5     | [references/bundle-optimization.md](mdc:references/bundle-optimization.md)     |
| 3   | Server-Side Performance              | HIGH        | 8     | [references/server-performance.md](mdc:references/server-performance.md)       |
| 4   | Client-Side Data Fetching            | MEDIUM-HIGH | 4     | [references/client-fetching.md](mdc:references/client-fetching.md)             |
| 5   | Re-render Optimization               | MEDIUM      | 13    | [references/rerender-optimization.md](mdc:references/rerender-optimization.md) |
| 6   | Rendering Performance                | MEDIUM      | 11    | [references/rendering-performance.md](mdc:references/rendering-performance.md) |
| 7   | Component Architecture & Composition | HIGH        | 8     | [references/composition-patterns.md](mdc:references/composition-patterns.md)   |
| 8   | JavaScript Performance               | LOW-MEDIUM  | 13    | [references/js-performance.md](mdc:references/js-performance.md)               |
| 9   | Advanced Patterns                    | LOW         | 3     | [references/advanced-patterns.md](mdc:references/advanced-patterns.md)         |

## Quick Rule Index

### 1. Eliminating Waterfalls (CRITICAL)

- **async-defer-await** — Move await into branches where actually used
- **async-parallel** — Use Promise.all() for independent operations
- **async-dependencies** — Use dependency-based parallelization for partial dependencies
- **async-api-routes** — Start promises early, await late in API routes
- **async-suspense-boundaries** — Use Suspense to stream content progressively

### 2. Bundle Size Optimization (CRITICAL)

- **bundle-barrel-imports** — Import directly from source files, not barrel files
- **bundle-dynamic-imports** — Use next/dynamic for heavy components
- **bundle-defer-third-party** — Load analytics/logging after hydration
- **bundle-conditional** — Load modules only when feature is activated
- **bundle-preload** — Preload on hover/focus for perceived speed

### 3. Server-Side Performance (HIGH)

- **server-auth-actions** — Authenticate server actions like API routes
- **server-cache-react** — Use React.cache() for per-request deduplication
- **server-cache-lru** — Use LRU cache for cross-request caching
- **server-dedup-props** — Avoid duplicate serialization in RSC props
- **server-hoist-static-io** — Hoist static I/O to module level
- **server-serialization** — Minimize data passed to client components
- **server-parallel-fetching** — Restructure components to parallelize fetches
- **server-after-nonblocking** — Use after() for non-blocking operations

### 4. Client-Side Data Fetching (MEDIUM-HIGH)

- **client-swr-dedup** — Use SWR for automatic request deduplication
- **client-event-listeners** — Deduplicate global event listeners
- **client-passive-event-listeners** — Use passive listeners for scroll/touch
- **client-localstorage-schema** — Version and minimize localStorage data

### 5. Re-render Optimization (MEDIUM)

- **rerender-defer-reads** — Do not subscribe to state only used in callbacks
- **rerender-memo** — Extract expensive work into memoized components
- **rerender-memo-with-default-value** — Hoist default non-primitive props to constants
- **rerender-dependencies** — Use primitive dependencies in effects
- **rerender-derived-state** — Subscribe to derived booleans, not raw values
- **rerender-derived-state-no-effect** — Derive state during render, not in effects
- **rerender-functional-setstate** — Use functional setState for stable callbacks
- **rerender-lazy-state-init** — Pass function to useState for expensive values
- **rerender-simple-expression-in-memo** — Do not wrap simple primitives in useMemo
- **rerender-move-effect-to-event** — Put interaction logic in event handlers
- **rerender-transitions** — Use startTransition for non-urgent updates
- **rerender-use-ref-transient-values** — Use refs for transient frequent values
- **rerender-no-inline-components** — Never define components inside components

### 6. Rendering Performance (MEDIUM)

- **rendering-animate-svg-wrapper** — Animate div wrapper, not SVG element
- **rendering-content-visibility** — Use content-visibility: auto for long lists
- **rendering-hoist-jsx** — Extract static JSX outside components
- **rendering-svg-precision** — Reduce SVG coordinate precision
- **rendering-hydration-no-flicker** — Use inline script for client-only data
- **rendering-hydration-suppress-warning** — Suppress expected mismatches only
- **rendering-activity** — Use Activity component for show/hide
- **rendering-conditional-render** — Use ternary, not && for conditionals with falsy values
- **rendering-usetransition-loading** — Prefer useTransition over manual loading state
- **rendering-resource-hints** — Use React DOM resource hints for preloading
- **rendering-script-defer-async** — Use defer or async on script tags

### 7. Component Architecture & Composition (HIGH)

- **composition-avoid-boolean-props** — Use composition instead of boolean prop proliferation
- **composition-compound-components** — Structure complex components with shared context
- **composition-decouple-state** — Isolate state management in providers, not UI
- **composition-context-interface** — Define generic state/actions/meta context interfaces
- **composition-lift-state** — Move state into provider components for sibling access
- **composition-explicit-variants** — Create explicit variant components, not boolean modes
- **composition-children-over-render-props** — Use children for composition, renderX for data
- **composition-react19-apis** — Use ref as prop (no forwardRef), use() instead of useContext()

### 8. JavaScript Performance (LOW-MEDIUM)

- **js-batch-dom-css** — Avoid layout thrashing; batch writes then read
- **js-index-maps** — Build Map for repeated lookups (O(1) vs O(n))
- **js-cache-property-access** — Cache object properties in hot loops
- **js-cache-function-results** — Cache function results in module-level Map
- **js-cache-storage** — Cache localStorage/sessionStorage reads in memory
- **js-combine-iterations** — Combine multiple filter/map into one loop
- **js-length-check-first** — Check array length before expensive comparison
- **js-early-exit** — Return early from functions when result is determined
- **js-hoist-regexp** — Hoist RegExp creation outside render/loops
- **js-min-max-loop** — Use loop for min/max instead of sort (O(n) vs O(n log n))
- **js-set-map-lookups** — Use Set/Map for O(1) membership checks
- **js-tosorted-immutable** — Use toSorted() to prevent mutation bugs in React state
- **js-flatmap-filter** — Use flatMap to map and filter in one pass

### 9. Advanced Patterns (LOW)

- **advanced-event-handler-refs** — Store event handlers in refs for stable subscriptions
- **advanced-init-once** — Initialize app once per load, not per mount
- **advanced-use-latest** — useEffectEvent for stable callback refs

## Tech Stack Notes

- This project uses **React 19** — always use `use()` instead of `useContext()`, and `ref` as a regular prop (no `forwardRef`). The composition-react19-apis rule is mandatory.
- This project uses **Next.js 15 App Router** — server components are the default. Apply server-side rules to all non-`'use client'` files.
- This project uses **Tailwind CSS v4** — prefer CSS classes over inline styles for layout thrashing prevention. Use Tailwind's built-in utilities for content-visibility, animations, etc.
- **Prisma** is used for database queries — apply React.cache() deduplication for all Prisma calls in server components.

## What This Skill Does NOT Handle

- **Creative design decisions** — Use the `frontend-design` skill for aesthetics, typography, color.
- **Accessibility compliance** — Use the `web-design-guidelines` skill for a11y rules.
- **Backend API design** — This skill covers client-side and RSC patterns only, not Hono API routes.
- **Testing patterns** — This skill does not prescribe test structure or testing libraries.

## Verification

- [ ] All CRITICAL rules (categories 1-2) are applied — no waterfalls, no barrel imports, dynamic imports for heavy components
- [ ] Server components minimize serialization at RSC boundaries
- [ ] Component architecture uses composition over boolean props
- [ ] No components defined inside other components
- [ ] No state derived via useEffect when render-time derivation works
- [ ] All event listeners use passive: true when not calling preventDefault
- [ ] React 19 APIs used (use() not useContext(), ref as prop not forwardRef)

**Apply every rule in this skill when writing, reviewing, or refactoring React/Next.js code in this project. Do not skip rules based on subjective judgment.**
