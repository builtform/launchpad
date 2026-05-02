---
stack: eleventy
pillar: Frontend Content
type: curate
last_validated: 2026-04-30
scaffolder_command: (curate — no npm create CLI; manual scaffold per this doc)
scaffolder_command_pinned_version: "@11ty/eleventy@3"
---

# Eleventy (11ty) — Knowledge Anchor

## Idiomatic 2026 pattern

Eleventy 3 is ESM-only; the 2.x CommonJS path is removed. The canonical 2026
layout uses `src/` for content + templates with `_data/` for global data files
(JS or JSON), `_includes/` for layout chains, `_includes/layouts/` for base
layouts, `src/index.njk` (or `.md`) as the home page, and `eleventy.config.mjs`
at the repo root (note the `.mjs` extension; `.js` works only if `package.json`
declares `"type": "module"`).

JS data files are first-class: `src/_data/site.mjs` exporting an object becomes
available as `{{ site.title }}` in templates. Async data files are supported
(top-level `await` works).

Output goes to `_site/` by default; configure via `dir.output` in the config
file. Nunjucks (`.njk`) and Markdown (`.md`) are the two universal template
engines; Liquid, Handlebars, Pug, EJS are opt-in.

Version pins: `@11ty/eleventy@3.x`, Node `>=18`, optional
`@11ty/eleventy-img@5+` for image optimization, `@11ty/eleventy-fetch@5+` for
build-time API fetching.

## Scaffolder behavior

Eleventy has NO `npm create eleventy` CLI; this is a `curate`-mode stack.
LaunchPad's curate path materializes the canonical layout via Claude using this
knowledge anchor as context. The `/lp-scaffold-stack` command, when dispatching
an `eleventy` layer, calls `knowledge_anchor_loader.read_and_verify()` on this
file, then emits a structured task descriptor that Claude consumes to write:

- `package.json` with `@11ty/eleventy@3.x` + `"type": "module"` + scripts
  (`dev: eleventy --serve`, `build: eleventy`)
- `eleventy.config.mjs` with `dir.input = "src"`, `dir.output = "_site"`,
  passthrough copy for static assets
- `src/_includes/layouts/base.njk` — base HTML shell with `<main>{{ content |
safe }}</main>`
- `src/index.njk` or `src/index.md` — home page using base layout
- `src/_data/site.mjs` — site metadata (title, description, url)
- `.gitignore` with `_site/`, `node_modules/`, `.cache/`
- `README.md` with dev/build instructions

Post-scaffold install runs separately via the cross-cutting wiring step.

## Tier-1 detection signals

- `eleventy.config.mjs` / `eleventy.config.js` / `.eleventy.js` at repo root
- `_site/` build output directory (gitignored, present after first build)
- `package.json` with `"@11ty/eleventy"` in dependencies
- `src/_data/` directory containing `.mjs` / `.js` / `.json` files
- `src/_includes/` directory with template partials

## Common pitfalls + cold-rerun gotchas

- Eleventy 3 removed CommonJS support entirely; `.cjs` config files do not work.
  Pre-3 projects must rename `eleventy.config.js` → `eleventy.config.mjs` AND
  add `"type": "module"` to `package.json`.
- The legacy `.eleventy.js` filename works but is a discovery footgun;
  `eleventy.config.mjs` is the 2026 idiom.
- `dir.input` defaults to `.` (root) in older docs; canonical 2026 layout uses
  `src/` and requires explicit `dir.input` setting.
- Nunjucks template inheritance (`{% extends %}`) requires the layout path
  relative to `_includes/`, not relative to the template file.
- Async filters and shortcodes require `addAsyncFilter` / `addAsyncShortcode`
  (Eleventy 2.x introduced these as first-class; before that, Promises in
  filters silently failed).
- `eleventyComputed` data is the recommended way to derive frontmatter from
  page context (slug, date, etc.); manually computing in templates leads to
  ordering bugs.

## Version evolution

- Eleventy 3 (2024 → stable 2025): ESM-only; bundle helper for inline CSS/JS;
  i18n plugin GA; performance improvements (~2x faster builds).
- Eleventy 2 (2023): async-first APIs; serverless deferred to community;
  declarative `addPlugin` configuration.
- Eleventy 1 (2022): first stable; CommonJS-only.

Curate-mode means LaunchPad ships the pattern doc itself as the canonical
spec; track upstream Eleventy releases at the 6-month freshness review for
breaking-change drift.
