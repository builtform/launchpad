---
stack: eleventy
pillar: Frontend Content
type: curate
last_validated: 2026-08-01
scaffolder_command: (curate — no npm create CLI; manual scaffold per this doc)
scaffolder_command_pinned_version: "@11ty/eleventy@3"
---

# Eleventy (11ty) — Knowledge Anchor

## Idiomatic 2026 pattern

Eleventy 3 supports both ESM and CommonJS. CJS was not removed and upstream
states it will keep working; ESM is simply the recommended default for new
projects. The canonical 2026 layout uses `src/` for content + templates with
`_data/` for global data files (JS or JSON), `_includes/` for layout chains,
`_includes/layouts/` for base layouts, `src/index.njk` (or `.md`) as the home
page, and `eleventy.config.js` at the repo root alongside `"type": "module"` in
`package.json` (what the official eleventy-base-blog starter does).
`eleventy.config.mjs` is an equally valid alternative when you do not want to
set `"type": "module"`.

JS data files are first-class: `src/_data/site.mjs` exporting an object becomes
available as `{{ site.title }}` in templates. Async data files are supported
(top-level `await` works).

Output goes to `_site/` by default; configure via `dir.output` in the config
file. Bundled in core: HTML, Markdown (`.md`), Liquid (`.liquid`), Nunjucks
(`.njk`) and JavaScript (`.11ty.js`); Liquid is the default preprocessor for
HTML and Markdown. Handlebars, Mustache, EJS, HAML and Pug were unbundled in v3
and now require official plugins; WebC, TypeScript, JSX and MDX were never core.

Version pins: `@11ty/eleventy@3.x` (3.1.x current), Node `>=18`, optional
`@11ty/eleventy-img@6.x` for image optimization (7.x is ESM-only and requires
Node >= 22, so stay on 6.x unless the project targets Node 22+),
`@11ty/eleventy-fetch@5+` for build-time API fetching.

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

- `.eleventy.js` / `eleventy.config.js` / `eleventy.config.mjs` /
  `eleventy.config.cjs` at repo root (Eleventy resolves them in that order)
- `_site/` build output directory (gitignored, present after first build)
- `package.json` with `"@11ty/eleventy"` in dependencies
- `_data/` directory (at repo root or under the configured `dir.input`, which
  defaults to `.`) containing `.mjs` / `.cjs` / `.js` / `.json` files
- `_includes/` directory with template partials and layouts

## Common pitfalls + cold-rerun gotchas

- Do NOT "migrate" an existing CommonJS Eleventy project to ESM as part of a v3
  upgrade. `eleventy.config.cjs` is a first-class supported config filename and
  `module.exports` configs still work. ESM is a preference, not a requirement.
- Mixing formats is the real footgun: with `"type": "module"` set, a `.js`
  config or data file using `module.exports` throws. Use `.cjs` to mark
  individual files as CommonJS.
- `.eleventy.js` is still checked FIRST in the config resolution order, so a
  stray legacy `.eleventy.js` silently wins over a new `eleventy.config.js`.
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

- Build Awesome / Eleventy 4 (alpha as of 2026-07): the project was rebranded to
  "Build Awesome" on 2026-03-03 and the repo moved to `11ty/buildawesome`; the
  npm package is still `@11ty/eleventy`. v4 raises the Node minimum, removes
  `setDataDeepMerge(false)` and the `slug` filter, and swaps Nunjucks for the
  `@11ty/nunjucks` fork. Do not pin to 4.x until stable.
- Eleventy 3 (stable 2024-10-02): full ESM support added while KEEPING
  CommonJS; plain-text bundler built into core; Handlebars, Mustache, EJS, HAML
  and Pug unbundled into plugins; Node 18 minimum.
- Eleventy 2 (2023): async-first APIs including `addAsyncFilter`; bundled i18n
  plugin; serverless deferred to community; declarative `addPlugin`.
- Eleventy 1 (2022): first stable; CommonJS-only.

Curate-mode means LaunchPad ships the pattern doc itself as the canonical
spec; track upstream Eleventy releases at the 6-month freshness review for
breaking-change drift.
