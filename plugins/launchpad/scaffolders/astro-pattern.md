---
stack: astro
pillar: Frontend Content/Performance
type: orchestrate
last_validated: 2026-08-01
scaffolder_command: npm create astro@latest -- --yes --no-ai --no-install --no-git --template <template>
scaffolder_command_pinned_version: astro@7
---

# Astro — Knowledge Anchor

## Idiomatic 2026 pattern

Astro 7 ships an islands-architecture frontend optimized for content-heavy sites
(blogs, marketing pages, documentation) with TypeScript-first defaults and
zero-JS-by-default rendering. Requires Node >= 22.12.0. The canonical 2026
layout uses `src/pages/` for file-based routing, `src/content/` for type-safe
content collections declared in `src/content.config.ts` and backed by Zod 4
schemas (`src/live.config.ts` for live collections), `src/layouts/` for shared
shells, and `src/components/` for both `.astro` and per-framework (`.tsx`,
`.vue`, `.svelte`) interactive islands. View transitions are opt-in via
`<ClientRouter />` from `astro:transitions`; the old `<ViewTransitions />`
component was removed in Astro 6. Tailwind v4 via `@tailwindcss/vite` is the
styling integration used by `--template with-tailwindcss`.

Key config files: `astro.config.mjs` (integrations, output mode, adapter),
`tsconfig.json` (strict mode + `astro/tsconfigs/strict` extends), `package.json`
(pinned `astro@7.x` + integration deps). Output mode is `'static' | 'server'`
and defaults to `static`; `hybrid` was removed in Astro 5, so use per-route
`export const prerender = false` instead. `server` requires an SSR adapter
(Vercel, Netlify, Node). Astro 7 reserves `src/fetch.ts` for Advanced Routing.

Version pins: `astro@7`, `@astrojs/check@0.9+`, `@tailwindcss/vite@4` +
`tailwindcss@4`, `typescript@6`. Do NOT use `@astrojs/tailwind`; it is legacy
Tailwind 3 support only. Do NOT install `typescript@7`: `@astrojs/check@0.9.x`
declares `peerDependencies.typescript: "^5.0.0 || ^6.0.0"`, so TS 7 breaks
`astro check`.

## Scaffolder behavior

`npm create astro@latest -- --yes --no-ai --no-install --no-git --template
<template>` runs the official Astro CLI in non-interactive mode. Available
`--template` values include `basics` (the `--yes` default), `minimal`, `blog`,
`starlight` (docs), `with-tailwindcss`, `framework-react`, `framework-vue`,
`portfolio`. Other flags: `--install`/`--no-install`, `--git`/`--no-git`,
`--add <integrations>`, `--dry-run`, `--ref`, `--skip-houston`, `--fancy`.

The scaffolder writes `astro.config.mjs`, `package.json`, `tsconfig.json`
(extends `astro/tsconfigs/strict`), `src/` skeleton matching the chosen
template, `public/` for static assets, `README.md`, and `.gitignore`.

CRITICAL, and the opposite of what a bare `--yes` implies: `create-astro`
resolves install as `ctx.install ?? ctx.yes` and git as `ctx.git ?? ctx.yes`, so
`--yes` alone DOES run the dependency install AND DOES run `git init`,
`git add -A`, `git commit`. Pass `--no-install --no-git` so
`/lp-scaffold-stack` keeps ownership of the install and VCS steps. Unless
`--no-ai` is passed it also writes `AGENTS.md` plus a `CLAUDE.md` symlink to it,
which collides with the harness-authored `CLAUDE.md`.

With `--no-install`, no lockfile is written by the scaffolder; it materializes
during the post-scaffold install step. No `.env` written; `.env.example` is
template-dependent.

## Tier-1 detection signals

Files that indicate Astro is already present in a brownfield repo (used by
`plugin-stack-detector.py` beyond the basic manifest list):

- `astro.config.mjs` or `astro.config.ts` at repo root or under `apps/web/`
- `src/content.config.ts` (content collections schema; `src/live.config.ts` for
  live collections). The pre-5.0 path `src/content/config.ts` indicates a repo
  still on the legacy collections API, which was removed in Astro 6.
- `src/pages/` directory containing `.astro` files
- `package.json` with `"astro"` in dependencies
- `.astro/` cache directory (gitignored but present after first `astro dev` run)

## Common pitfalls + cold-rerun gotchas

- `--yes` in `npm create astro@latest -- --yes --template <t>` requires the `--`
  separator before passing template flags through to `create-astro`; without it
  npm consumes the flags itself.
- `<ViewTransitions />` was renamed to `<ClientRouter />` in Astro 5 and removed
  outright in Astro 6; Astro 7 also removed the `TRANSITION_*` internals.
- Content collections moved to the Content Layer API and `src/content.config.ts`
  in 5.0; the legacy API was removed entirely in 6.0. Schemas validate with
  Zod 4 as of Astro 6, which can require schema adjustments on upgrade.
- Tailwind v4 integration uses `@tailwindcss/vite` (not the v3
  `@astrojs/tailwind` integration); template selection determines which path
  the scaffolder picks.
- Astro 7's Rust `.astro` compiler is stricter: non-void elements need closing
  tags, and `compressHTML` now defaults to `'jsx'`, which can drop whitespace
  between inline elements.
- Astro 7 replaces the remark/rehype markdown pipeline by default; install
  `@astrojs/markdown-remark` to keep existing remark/rehype plugins.
- `@astrojs/db` was removed in Astro 7.
- Scaffolding on Node 18 or 20 fails; Astro 6+ requires Node >= 22.12.0.

## Version evolution

- Astro 7 (2026-06-22): Rust `.astro` compiler; Vite 8 + Rolldown; Advanced
  Routing via `src/fetch.ts`; `@astrojs/db` removed.
- Astro 6 (2026-03-10): Fonts API; CSP API; Live Content Collections
  (`src/live.config.ts`); Vite 7; Zod 4; Node 22+ minimum; `Astro.glob()` and
  `<ViewTransitions />` removed.
- Astro 5 (stable 2025): Content Layer API replaces collection config;
  `hybrid` output removed; sessions added; `astro:env` for type-safe env.
- Astro 4 (2023 H4): View Transitions API introduced (experimental); Vite 5
  upgrade; Picture component added.
- Astro 3 (2023 H2): View Transitions API previewed; islands rearchitected;
  hybrid output mode.

Track upstream `create-astro` releases; the scaffolder's flag set shifts with
major versions and minor releases occasionally rename templates.
