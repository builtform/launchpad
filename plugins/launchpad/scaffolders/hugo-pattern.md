---
stack: hugo
pillar: Frontend Content (Go)
type: orchestrate
last_validated: 2026-08-01
scaffolder_command: hugo new project <path> --force
scaffolder_command_pinned_version: hugo@0.164+ (standard edition)
---

# Hugo — Knowledge Anchor

## Idiomatic 2026 pattern

Hugo is a Go-built static site generator with the fastest build times in the
content-site category (~thousands of pages/second). The 2026 idiom uses the
**standard** Hugo binary. Upstream guidance is "use the standard edition unless
you need additional features": the extended edition only adds embedded LibSass,
which was deprecated in v0.153.0 and is scheduled for removal, and the internal
extended-version enforcement check was disabled in v0.153.2. Projects needing
Sass should install the separate `dart-sass` binary and set
`transpiler = "dartsass"`, which works on any edition. The deploy and
extended/deploy editions exist only for direct S3/GCS/Azure publishing.

The canonical layout from `hugo new project`:

- `archetypes/default.md` — frontmatter template for `hugo new`
- `assets/` — pipeline-processed assets (Sass, JS, images)
- `content/` — Markdown content (organized by section: `posts/`, `pages/`)
- `data/` — TOML/YAML/JSON data files queryable via `.Site.Data`
- `i18n/` — translations
- `layouts/` — Go templates, v0.146+ structure: `baseof.html`, `home.html`,
  `page.html`, `section.html`, `taxonomy.html`, `term.html`, `all.html` at the
  `layouts/` root, plus the reserved `_partials/`, `_shortcodes/`, `_markup/`
  subdirectories. The pre-v0.146 shape (`_default/`, `partials/`,
  `shortcodes/`) is legacy-mapped for compatibility but must NOT be generated
  for new projects.
- `static/` — passthrough static files (favicon, robots.txt)
- `themes/` — git-submodule themes (e.g., PaperMod, Doks, Hugo Bear Blog)
- `hugo.toml` (or `.yaml`/`.json`) — site config

Modules system (Hugo Modules) is the modern theme/component delivery; use
`hugo mod init <module-path>` after `hugo new project` to enable.

Version pins: hugo `0.164.x` standard (v0.158.0 is the documented floor). Track
via `hugo version`; CI pins via `peaceiris/actions-hugo@v3` (or equivalent) with
`hugo-version: 0.164.x`. Set `extended: true` only if the project still depends
on embedded LibSass, which is deprecated; prefer installing `dart-sass`.

## Scaffolder behavior

`hugo new project <path> --force` (alias: `hugo new site`) creates the project
directory at `<path>` with the canonical layout above. `--force` means "init
inside a non-empty directory"; it does NOT overwrite, and Hugo still errors if
any skeleton subdirectory or the config file already exists. `--format` selects
toml (default), yaml, or json. LaunchPad scopes this to a freshly-detected
greenfield via `cwd_state`, so the flag is safe. The scaffolder writes:

- `assets/`, `content/`, `data/`, `i18n/`, `layouts/`, `static/`, `themes/`,
  each containing only a `.gitkeep`
- `archetypes/default.md` (title/date/draft frontmatter template)
- `hugo.toml` with default `baseURL`, `locale`, `title` placeholders. Note:
  `locale` replaced `languageCode`, which was deprecated in v0.158.0.

It does NOT write content, NOT install a theme, NOT initialize git, NOT create
a `package.json`. Theme selection + content seeding happens in a follow-up
manual step (or via `git submodule add` for a chosen theme).

No lockfile (Hugo has no JS dep tree). The Hugo binary itself is the only
runtime dep; LaunchPad's pre-flight check assumes the user has the standard
binary installed (plus `dart-sass` on PATH if the chosen theme uses Sass).

## Tier-1 detection signals

- `hugo.toml` / `hugo.yaml` / `hugo.json` / legacy `config.toml` at repo root,
  or a `config/_default/` directory
- `.hugo_build.lock` at repo root
- `layouts/_partials/` or a root-level `layouts/page.html` (v0.146+ fingerprint)
- `content/**/_content.gotmpl` content adapters (v0.126+)
- `archetypes/`, `content/`, `layouts/` directories simultaneously present
- `themes/` directory with one or more git submodules
- `public/` build output (gitignored, present after first `hugo` run)
- `resources/_gen/` — Hugo's processed-asset cache

## Common pitfalls + cold-rerun gotchas

- Sass: embedded LibSass (extended edition only) was deprecated in v0.153.0.
  Themes importing `.scss` should use `transpiler = "dartsass"`, which needs the
  `dart-sass` binary on PATH in both local and CI environments. Standard edition
  plus dart-sass is the 2026 default; do not pin `extended` reflexively.
- Layout migration: projects generated before v0.146.0 use `layouts/_default/`,
  `partials/`, `shortcodes/`. Never mix the old and new layout conventions in
  one project; migrate wholesale to the `layouts/` root plus `_partials/`.
- `hugo new project <path>` requires `<path>` to be empty OR to use `--force`. In
  a brownfield repo with files already present, the command refuses without
  `--force`; LaunchPad's greenfield gate ensures this isn't an issue.
- `hugo.toml` is the modern config name (since v0.110.0, 2023-01-17); older
  projects use `config.toml` and the rename is a one-shot manual edit.
- `hugo server` runs on port 1313 by default; conflicts with other dev servers
  in a polyglot monorepo require `--port <n>`.
- Hugo Modules vs git-submodule themes: both are supported and Hugo's own quick
  start still uses `git submodule add`. Modules require Git and Go 1.18+ and add
  `go.mod`/`go.sum`. Mixing both in the same repo causes module-path conflicts.
- `--minify` on `hugo` build is opt-in; CI builds should pass it.

## Version evolution

- Hugo 0.164.0 (2026-07-06): current stable.
- Hugo 0.158.0 (2026-03-16): `languageCode` deprecated in favor of `locale`;
  `hugo new project` becomes the documented scaffolder name (`site` kept as an
  alias).
- Hugo 0.153.0 (2025-12-19): embedded LibSass deprecated in favor of Dart Sass;
  extended-version enforcement check disabled in 0.153.2.
- Hugo 0.146.0 (2025): full template-system overhaul; `layouts/_default/`
  flattened to the `layouts/` root, `partials/` to `_partials/`, `shortcodes/`
  to `_shortcodes/`, new `all.html` catch-all.
- Hugo 0.126.0 (2024): content adapters (`_content.gotmpl`).
- Hugo 0.110.0 (2023-01-17): `hugo.toml` replaces `config.toml` as the default
  config name.
- Hugo 0.56.0 (2019): Hugo Modules introduced.

Track upstream Hugo releases; the binary's flag set is stable across minor
versions but build-time deprecation warnings shift.
