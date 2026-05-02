---
stack: astro
pillar: Frontend Content/Performance
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: npm create astro@latest -- --yes --template <template>
scaffolder_command_pinned_version: astro@5
---

# Astro — Knowledge Anchor

## Idiomatic 2026 pattern

Astro 5 ships an islands-architecture frontend optimized for content-heavy sites
(blogs, marketing pages, documentation) with TypeScript-first defaults and
zero-JS-by-default rendering. The canonical 2026 layout uses `src/pages/` for
file-based routing, `src/content/` for type-safe content collections backed by
Zod schemas, `src/layouts/` for shared shells, and `src/components/` for both
`.astro` and per-framework (`.tsx`, `.vue`, `.svelte`) interactive islands. The
View Transitions API is opt-in via `<ViewTransitions />` in a layout. Tailwind v4
is the default styling integration when `--template with-tailwindcss` is used.

Key config files: `astro.config.mjs` (integrations, output mode, adapter),
`tsconfig.json` (strict mode + `astro/tsconfigs/strict` extends), `package.json`
(pinned `astro@5.x` + integration deps). Output mode defaults to `static`;
`hybrid` and `server` modes require an SSR adapter (Vercel, Netlify, Node).

Version pins: `astro@5`, `@astrojs/check@0.9+`, `@astrojs/tailwind@5+` (or
`@tailwindcss/vite@4` for Tailwind v4 native integration), `typescript@5`.

## Scaffolder behavior

`npm create astro@latest -- --yes --template <template>` runs the official
Astro CLI in non-interactive mode. Available `--template` values include
`minimal`, `blog`, `starlight` (docs), `with-tailwindcss`, `framework-react`,
`framework-vue`, `portfolio`. The scaffolder writes `astro.config.mjs`,
`package.json`, `tsconfig.json`, `src/` skeleton matching the chosen template,
`public/` for static assets, and `.gitignore`. It does NOT install dependencies
(headless flag suppresses the install prompt); the consuming `/lp-scaffold-stack`
runs `pnpm install` (or detected package manager) as a separate cross-cutting
wiring step.

No lockfile written by the scaffolder itself; lockfile materializes during the
post-scaffold install step. No `.env` written; `.env.example` is template-
dependent.

## Tier-1 detection signals

Files that indicate Astro is already present in a brownfield repo (used by
`plugin-stack-detector.py` beyond the basic manifest list):

- `astro.config.mjs` or `astro.config.ts` at repo root or under `apps/web/`
- `src/content/config.ts` (content collections schema)
- `src/pages/` directory containing `.astro` files
- `package.json` with `"astro"` in dependencies
- `.astro/` cache directory (gitignored but present after first `astro dev` run)

## Common pitfalls + cold-rerun gotchas

- `--yes` in `npm create astro@latest -- --yes --template <t>` requires the `--`
  separator before passing template flags through to `create-astro`; without it
  npm consumes the flags itself.
- Astro 5 made the View Transitions API stable but renamed `<ViewTransitions />`
  semantics; pre-5 templates may use deprecated import paths.
- Content collections moved from `src/content/config.ts` to a Content Layer API
  in 5.0; templates older than 5.0 reference the deprecated config shape.
- Tailwind v4 integration uses `@tailwindcss/vite` (not the v3
  `@astrojs/tailwind` integration); template selection determines which path
  the scaffolder picks.
- The `with-tailwindcss` template currently pins Tailwind v3 (v4 migration
  pending upstream); manual upgrade required for v4.

## Version evolution

- Astro 5 (2024 H2 → stable 2025): Content Layer API replaces collection config;
  View Transitions stabilized; sessions added; `astro:env` for type-safe env.
- Astro 4 (2023 H4): View Transitions API introduced (experimental); Vite 5
  upgrade; Picture component added.
- Astro 3 (2023 H2): View Transitions API previewed; islands rearchitected;
  hybrid output mode.

Track upstream `create-astro` releases; the scaffolder's flag set shifts with
major versions and minor releases occasionally rename templates.
