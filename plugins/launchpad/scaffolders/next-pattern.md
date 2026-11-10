---
stack: next
pillar: Frontend App
type: orchestrate
last_validated: 2026-11-10
scaffolder_command: npx create-next-app@latest --no-agents-md --typescript --eslint --tailwind --app
scaffolder_command_pinned_version: create-next-app@16
---

# Next.js — Knowledge Anchor

## Idiomatic 2026 pattern

Next.js 16 ships React 19.2 (19.3 from 16.4) + the App Router as the canonical
paradigm; the Pages Router remains supported but new projects use App Router
exclusively. Server Actions are stable; Server Components are the default rendering mode with `"use
client"` opt-in for interactivity. Turbopack is the default bundler for both
`next dev` and `next build`; opt out with `--webpack`. Caching is opt-in via
Cache Components and the `"use cache"` directive, so dynamic code runs at
request time by default. From 16.4 `create-next-app` enables Cache Components in
new App Router projects (the framework default only in Next 17); pass
`--no-cache-components` to opt out.

The canonical 2026 layout: `src/app/` (or `app/` at root) containing
`layout.tsx`, `page.tsx`, route segments as nested folders, `loading.tsx` /
`error.tsx` / `not-found.tsx` per segment, `route.ts` for API handlers. `app/
api/` is the convention for HTTP route handlers. `proxy.ts` at root for request
interception (renamed from `middleware.ts` in Next 16, runs on the Node.js
runtime). `next.config.ts` is the template default; `.mjs`/`.js` remain
supported.

Tailwind v4 ships as the styling default with CSS-first config: there is no
`tailwind.config.*` file. Theme tokens live in `@theme inline` inside
`app/globals.css`. Under the default Turbopack bundler the scaffold wires
Tailwind through `@tailwindcss/turbopack` (a `turbopack.rules` entry in
`next.config.ts`) and writes no `postcss.config.mjs`; `postcss.config.mjs` +
`@tailwindcss/postcss` is the Rspack/manual path.
ESLint uses flat config importing `eslint-config-next/core-web-vitals` and
`eslint-config-next/typescript`.

Version pins written by the scaffolder: `next@16`, `react@19.3.0`,
`react-dom@19.3.0`, `typescript@^5`, `tailwindcss@4.3.3`,
`@tailwindcss/turbopack@4.3.3` (exact pins as of 16.4.6, previously `^4`; Tailwind
4.3.4 breaks on Node before 20.19 / 22.12), `eslint@^9` (flat config),
`@types/node@^20`, `@types/react@^19`. Ecosystem
latest runs ahead of several of these (`typescript@7.x`, `eslint@10.x`,
`@types/node@26.x`); moving past the scaffolded pins is a deliberate choice, not
a default. Minimum Node.js is 20.9; minimum TypeScript is 5.1.

## Scaffolder behavior

`npx create-next-app@latest --no-agents-md --typescript --eslint --tailwind
--app` runs the official Next CLI in non-interactive mode. Flag effects:

- No `--yes`: with any `--` flag on the command line and `CI` unset, the CLI
  skips every prompt and applies its hardcoded recommended defaults to options
  not passed explicitly, so output is reproducible even on a machine that has
  run the CLI before. `--yes` would instead fill those options from previously
  saved preferences (source layout, React Compiler, Cache Components). Never
  pass `--reset-preferences`: that flag is a standalone mode which prompts
  "Would you like to reset the saved preferences?" and exits 0 without
  scaffolding (unchanged since 16.0.0)
- `--no-agents-md` suppresses the `AGENTS.md` the CLI writes by default in Next
  16.2+. Versions 16.2 and 16.3 also wrote a `CLAUDE.md` that would collide with
  the harness-authored `CLAUDE.md`; 16.4.0 dropped it. Separately, `next dev`
  creates or updates the `AGENTS.md` rules block when it detects a coding agent,
  unless `agentRules: false` is set in `next.config.ts`
- `--typescript` writes `tsconfig.json` and `.tsx` skeleton
- `--eslint` writes `eslint.config.mjs` (flat config) importing
  `eslint-config-next/core-web-vitals` + `eslint-config-next/typescript`
- `--tailwind` configures Tailwind v4 (the `@tailwindcss/turbopack` loader rule
  in `next.config.ts` under Turbopack) + writes `globals.css` with `@import
"tailwindcss";`
- `--app` selects App Router (vs Pages Router)

Turbopack needs no flag in Next 16: it is the default for dev and build, and
`create-next-app` always scaffolds for it (`--rspack` selects Rspack). Since
16.2.0 the CLI no longer declares `--turbopack` or `--webpack`; its parser
silently ignores unknown flags, so `--webpack` does NOT produce a webpack
project (the official CLI docs page still lists both). The opt-out is at run
time: `next dev --webpack` / `next build --webpack`.

Writes `next.config.ts`, `package.json`, `tsconfig.json`, `next-env.d.ts`,
`eslint.config.mjs`, `app/layout.tsx`, `app/page.tsx`,
`app/globals.css`, `app/favicon.ico`, `public/`, `.gitignore`, `README.md`. No
`tailwind.config.*` is written, and no `postcss.config.mjs` under Turbopack.
`next.config.ts` carries the Tailwind `turbopack.rules` entry plus, by default,
`cacheComponents: true` and `partialPrefetching: true`. Without
`--no-agents-md` it also writes `AGENTS.md` (and `CLAUDE.md` on 16.2 and 16.3).
The CLI runs `npm install` (or detected pm) by default;
the headless run accepts that without a prompt. Lockfile produced (`package-lock.json`
unless yarn/pnpm/bun detected).

`--src-dir` controls whether `app/` lives at root or under `src/`; not in our
default flag set (defaults to root-level `app/`).

## Tier-1 detection signals

- `next.config.ts` / `next.config.mjs` / `next.config.js` at repo root
- `app/` directory with `layout.tsx` (App Router) or `pages/` directory with
  `_app.tsx` (Pages Router)
- `package.json` with `"next"` in dependencies
- `.next/` build cache (gitignored)
- `proxy.ts` at root (Next 16+ request interception), or legacy `middleware.ts`
  (deprecated but still functional)
- `eslint.config.mjs` importing `eslint-config-next/*` (Next 16 fingerprint)

## Common pitfalls + cold-rerun gotchas

- React 19 brings breaking changes (removed APIs: `propTypes`, `defaultProps` on
  function components, `forwardRef` no longer needed for ref-as-prop); upgrades
  from <15 require a codemod.
- Turbopack is the default for dev AND build in Next 16. Custom webpack configs
  require `next dev --webpack` / `next build --webpack`.
- Server Actions require a `"use server"` directive at module top OR per-export.
  Form actions implicitly inherit this.
- The `eslint.config.mjs` flat-config replaced `.eslintrc.json` in Next 15;
  pre-15 projects need a manual migration on upgrade.
- Tailwind v4's `@import "tailwindcss";` replaces the v3 directive triplet
  (`@tailwind base; @tailwind components; @tailwind utilities;`); migration is
  one-shot.
- `app/globals.css` is imported in `app/layout.tsx`; deleting that import
  silently breaks Tailwind without an error.
- `next lint` was removed in Next 16 and `next build` no longer lints. Migrate
  with `npx @next/codemod@canary next-lint-to-eslint-cli .` and run `eslint`
  from package scripts instead.
- `params`, `searchParams`, `cookies()`, `headers()`, and `draftMode()` are
  async-only in Next 16. Sync access is removed, not deprecated.
- Every parallel-route slot now requires an explicit `default.js` or the build
  fails.

## Version evolution

- Next 16 (2025-10-21): Turbopack default for dev and build; Cache Components /
  `"use cache"` replaces implicit caching; `middleware.ts` renamed to
  `proxy.ts`; `next lint` removed; Node 20.9+ minimum; AMP removed.
- Next 16.4 (2026-10-06): `create-next-app` enables Cache Components by default
  and scaffolds React 19.3.0, Tailwind via `@tailwindcss/turbopack`, and
  `AGENTS.md` only (no `CLAUDE.md`); `eslint-config-next` supports ESLint 10.
- Next 15 (2024 H4 → stable 2025): React 19 baseline; Turbopack stable for dev,
  preview-stable for build; async `cookies()`/`headers()`/`params`/`searchParams`;
  `next.config.ts` TypeScript config.
- Next 14 (2023 H4): Server Actions stable; partial pre-rendering preview;
  `next/og` image generation.
- Next 13 (2022 H4): App Router introduced; Server Components; Streaming SSR.

Track upstream `create-next-app` releases; the App Router has stabilized but
flag defaults shift with each major.
