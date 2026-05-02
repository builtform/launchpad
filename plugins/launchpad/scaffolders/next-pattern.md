---
stack: next
pillar: Frontend App
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: npx create-next-app@latest --yes --typescript --eslint --tailwind --app --turbopack
scaffolder_command_pinned_version: create-next-app@15
---

# Next.js — Knowledge Anchor

## Idiomatic 2026 pattern

Next.js 15 ships React 19 + the App Router as the canonical paradigm; the Pages
Router remains supported but new projects use App Router exclusively. Server
Actions are stable; Server Components are the default rendering mode with `"use
client"` opt-in for interactivity. Turbopack is the stable bundler for dev and
build (replacing webpack as the recommended path).

The canonical 2026 layout: `src/app/` (or `app/` at root) containing
`layout.tsx`, `page.tsx`, route segments as nested folders, `loading.tsx` /
`error.tsx` / `not-found.tsx` per segment, `route.ts` for API handlers. `app/
api/` is the convention for HTTP route handlers. `middleware.ts` at root for
edge middleware. `next.config.ts` (TypeScript config) replaced `.mjs`/`.js`.

Tailwind v4 ships as the styling default; `tailwind.config.ts` lives at root.
ESLint uses the `next/core-web-vitals` flat-config preset.

Version pins: `next@15`, `react@19`, `react-dom@19`, `typescript@5`,
`tailwindcss@4`, `eslint@9` (flat config), `@types/node@22`, `@types/react@19`.

## Scaffolder behavior

`npx create-next-app@latest --yes --typescript --eslint --tailwind --app
--turbopack` runs the official Next CLI in non-interactive mode. Flag effects:

- `--yes` accepts all defaults for any prompt not explicitly answered
- `--typescript` writes `tsconfig.json` and `.tsx` skeleton
- `--eslint` writes `eslint.config.mjs` (flat config) with `next/core-web-vitals`
- `--tailwind` configures Tailwind v4 + writes `globals.css` with `@import
"tailwindcss";`
- `--app` selects App Router (vs Pages Router)
- `--turbopack` enables Turbopack for `next dev`

Writes `next.config.ts`, `package.json`, `tsconfig.json`, `eslint.config.mjs`,
`postcss.config.mjs`, `app/layout.tsx`, `app/page.tsx`, `app/globals.css`,
`public/`, `.gitignore`. The CLI runs `npm install` (or detected pm) by default;
the headless `--yes` flag accepts that. Lockfile produced (`package-lock.json`
unless yarn/pnpm/bun detected).

`--src-dir` controls whether `app/` lives at root or under `src/`; not in our
default flag set (defaults to root-level `app/`).

## Tier-1 detection signals

- `next.config.ts` / `next.config.mjs` / `next.config.js` at repo root
- `app/` directory with `layout.tsx` (App Router) or `pages/` directory with
  `_app.tsx` (Pages Router)
- `package.json` with `"next"` in dependencies
- `.next/` build cache (gitignored)
- `middleware.ts` at root (edge middleware presence)

## Common pitfalls + cold-rerun gotchas

- React 19 brings breaking changes (removed APIs: `propTypes`, `defaultProps` on
  function components, `forwardRef` no longer needed for ref-as-prop); upgrades
  from <15 require a codemod.
- Turbopack stability flag: `--turbopack` enables for dev only by default; Next
  15 stabilized Turbopack for builds with `next build --turbopack`.
- Server Actions require a `"use server"` directive at module top OR per-export.
  Form actions implicitly inherit this.
- The `eslint.config.mjs` flat-config replaced `.eslintrc.json` in Next 15;
  pre-15 projects need a manual migration on upgrade.
- Tailwind v4's `@import "tailwindcss";` replaces the v3 directive triplet
  (`@tailwind base; @tailwind components; @tailwind utilities;`); migration is
  one-shot.
- `app/globals.css` is imported in `app/layout.tsx`; deleting that import
  silently breaks Tailwind without an error.

## Version evolution

- Next 15 (2024 H4 → stable 2025): React 19 baseline; Turbopack stable for dev,
  preview-stable for build; async `cookies()`/`headers()`/`params`/`searchParams`;
  `next.config.ts` TypeScript config.
- Next 14 (2023 H4): Server Actions stable; partial pre-rendering preview;
  `next/og` image generation.
- Next 13 (2022 H4): App Router introduced; Server Components; Streaming SSR.

Track upstream `create-next-app` releases; the App Router has stabilized but
flag defaults shift with each major.
