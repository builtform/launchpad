---
stack: hugo
pillar: Frontend Content (Go)
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: hugo new site <path> --force
scaffolder_command_pinned_version: hugo@0.137+ (extended)
---

# Hugo — Knowledge Anchor

## Idiomatic 2026 pattern

Hugo is a Go-built static site generator with the fastest build times in the
content-site category (~thousands of pages/second). The 2026 idiom uses the
**extended** Hugo binary (Sass/SCSS support is required for theme
development); plain Hugo lacks Sass and shows runtime errors when themes
import `.scss` partials.

The canonical layout from `hugo new site`:

- `archetypes/default.md` — frontmatter template for `hugo new`
- `assets/` — pipeline-processed assets (Sass, JS, images)
- `content/` — Markdown content (organized by section: `posts/`, `pages/`)
- `data/` — TOML/YAML/JSON data files queryable via `.Site.Data`
- `i18n/` — translations
- `layouts/` — Go templates (`_default/single.html`, `_default/list.html`,
  `partials/`, `shortcodes/`)
- `static/` — passthrough static files (favicon, robots.txt)
- `themes/` — git-submodule themes (e.g., PaperMod, Doks, Hugo Bear Blog)
- `hugo.toml` (or `.yaml`/`.json`) — site config

Modules system (Hugo Modules) is the modern theme/component delivery; use
`hugo mod init <module-path>` after `hugo new site` to enable.

Version pins: hugo `0.137+` extended. Track via `hugo version`; CI pins via
`peaceiris/actions-hugo` (or equivalent) with `hugo-version: 0.137.x`,
`extended: true`.

## Scaffolder behavior

`hugo new site <path> --force` creates the site directory at `<path>` with the
canonical layout above. `--force` overwrites if the dir exists (LaunchPad scopes
this to a freshly-detected greenfield via `cwd_state`, so the flag is safe).
The scaffolder writes:

- Empty `archetypes/`, `assets/`, `content/`, `data/`, `i18n/`, `layouts/`,
  `static/`, `themes/`
- `hugo.toml` with default `baseURL`, `languageCode`, `title` placeholders

It does NOT write content, NOT install a theme, NOT initialize git, NOT create
a `package.json`. Theme selection + content seeding happens in a follow-up
manual step (or via `git submodule add` for a chosen theme).

No lockfile (Hugo has no JS dep tree). The Hugo binary itself is the only
runtime dep; LaunchPad's pre-flight check assumes the user has the extended
binary installed.

## Tier-1 detection signals

- `hugo.toml` / `hugo.yaml` / `hugo.json` / `config.toml` at repo root
- `archetypes/`, `content/`, `layouts/` directories simultaneously present
- `themes/` directory with one or more git submodules
- `public/` build output (gitignored, present after first `hugo` run)
- `resources/_gen/` — Hugo's processed-asset cache

## Common pitfalls + cold-rerun gotchas

- "extended" vs plain Hugo: themes that import `.scss` partials silently break
  on the plain binary at build time. CI must explicitly pin the extended flag.
- `hugo new site <path>` requires `<path>` to be empty OR to use `--force`. In
  a brownfield repo with files already present, the command refuses without
  `--force`; LaunchPad's greenfield gate ensures this isn't an issue.
- `hugo.toml` is the modern config name; pre-0.110 projects use `config.toml`
  and the rename is a one-shot manual edit.
- `hugo server` runs on port 1313 by default; conflicts with other dev servers
  in a polyglot monorepo require `--port <n>`.
- Hugo Modules vs git-submodule themes: 2026 idiom prefers Hugo Modules
  (`hugo mod init`), but submodule themes still work; mixing both in the same
  repo causes module-path conflicts.
- `--minify` on `hugo` build is opt-in; CI builds should pass it.

## Version evolution

- Hugo 0.137+ (2024 → 2025): improved `--printPathWarnings`, faster image
  processing, render hooks for code blocks.
- Hugo 0.120 (2023): `hugo.toml` rename from `config.toml`; experimental TOML
  v1.0 support; image processing `webp` defaults.
- Hugo 0.100+ (2022): Hugo Modules stabilized; `dart-sass` over `libsass`.

Track upstream Hugo releases; the binary's flag set is stable across minor
versions but build-time deprecation warnings shift.
