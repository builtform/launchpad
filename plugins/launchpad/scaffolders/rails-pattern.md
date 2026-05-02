---
stack: rails
pillar: Backend MVC (Ruby)
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: rails new <path> --skip-bundle --skip-git
scaffolder_command_pinned_version: rails@8
---

# Rails — Knowledge Anchor

## Idiomatic 2026 pattern

Rails 8 is the canonical batteries-included Ruby web framework. The 2026 idiom
ships **Solid Queue** + **Solid Cache** + **Solid Cable** as the default
adapters (replacing Redis/Sidekiq/Memcached for jobs/cache/realtime in single-
node deployments), **Hotwire** (Turbo + Stimulus) as the default frontend,
**Propshaft** as the asset pipeline (Sprockets is legacy), and Ruby 3.3+.

Canonical layout from `rails new`:

```
<app>/
  app/
    assets/
    channels/        # ActionCable channels (with Solid Cable backend)
    controllers/
    helpers/
    javascript/      # Stimulus + Turbo
    jobs/            # ActiveJob (with Solid Queue backend)
    mailers/
    models/
    views/
  bin/               # binstubs (rails, rake, dev, setup, ...)
  config/
    application.rb
    boot.rb
    cable.yml        # Solid Cable config
    credentials.yml.enc
    database.yml
    environments/
    initializers/
    queue.yml        # Solid Queue config (Rails 8 addition)
    cache.yml        # Solid Cache config (Rails 8 addition)
    routes.rb
    storage.yml
  db/
    migrate/
    schema.rb
  lib/
  log/
  public/
  test/              # default; --test=rspec for RSpec
  tmp/
  vendor/
  Gemfile
  Gemfile.lock
  Procfile.dev       # foreman process for `bin/dev`
  Dockerfile         # Rails 8 ships Kamal-ready Dockerfile by default
```

Version pins (Gemfile):

- `gem "rails", "~> 8.0"`
- `gem "pg", "~> 1.5"` (Postgres) OR `gem "sqlite3", ">= 2.1"` (default)
- `gem "puma", ">= 6.4"`
- `gem "propshaft"`
- `gem "importmap-rails"` (no Node toolchain by default; `--javascript=esbuild`
  for esbuild)
- `gem "turbo-rails"`, `gem "stimulus-rails"`
- `gem "solid_queue"`, `gem "solid_cache"`, `gem "solid_cable"`
- `gem "kamal"` (deploy)
- `gem "thruster"` (HTTP/2 + caching proxy in front of Puma)

## Scaffolder behavior

`rails new <path> --skip-bundle --skip-git` creates the full Rails 8 app
skeleton at `<path>/`. Flag effects:

- `--skip-bundle` — does NOT run `bundle install` (LaunchPad runs it as a
  separate cross-cutting wiring step so failures are isolated)
- `--skip-git` — does NOT run `git init` (LaunchPad's repo init is centralized)
- Defaults: SQLite database, importmap (no Node), Turbo + Stimulus,
  Solid Queue/Cache/Cable, Puma, Propshaft, Kamal, Thruster, Minitest

For Postgres: `rails new <path> --database=postgresql --skip-bundle --skip-git`.
For RSpec instead of Minitest: `rails new <path> --skip-test --skip-bundle
--skip-git` (LaunchPad's curate emit then adds `gem "rspec-rails"` to Gemfile).
For esbuild instead of importmap: `--javascript=esbuild` (adds Node toolchain
to the project, which LaunchPad detects and wires `package.json` into the
cross-cutting layer).

Lockfile: `Gemfile.lock` materializes during the post-scaffold `bundle install`.

## Tier-1 detection signals

- `Gemfile` at repo root with `gem "rails"`
- `bin/rails` binstub
- `config/application.rb` containing `module <AppName>` + `class Application <
Rails::Application`
- `config/routes.rb` with `Rails.application.routes.draw do`
- `db/schema.rb` (post-migration; absent on a freshly-scaffolded app until
  first migration)
- `app/controllers/application_controller.rb`

## Common pitfalls + cold-rerun gotchas

- Rails 8's Solid Queue/Cache/Cable use dedicated databases by default (not the
  primary app DB); `database.yml` declares `queue`, `cache`, `cable`
  connections. SQLite default uses separate `.sqlite3` files; Postgres requires
  manual additional database creation OR the `multi_db_setup` rake task.
- `--skip-bundle` means `Gemfile.lock` does NOT exist after `rails new`;
  `bundle install` is mandatory before `bin/rails server` will boot.
- Importmap vs esbuild: importmap is the 2026 default and ships zero Node
  toolchain; switching to esbuild later requires `bin/rails javascript:install:
esbuild` + manual `Gemfile` edit.
- Hotwire Turbo intercepts ALL link clicks and form submissions by default; opt
  out per-element with `data-turbo="false"`. Initial Hotwire integration is the
  most common source of "why isn't my JS running?" debug sessions.
- `bin/dev` requires `foreman` (or compatible) and reads `Procfile.dev`; if
  `foreman` isn't installed, `bin/dev` errors cryptically.
- Kamal deploy requires SSH access to target servers; not usable in PaaS-only
  environments without alternate deploy config.
- Active Storage local-disk variants (image processing) require `libvips` or
  `ImageMagick` system deps; missing system deps produce runtime errors not
  caught by `bundle install`.

## Version evolution

- Rails 8 (2024 H4 → stable 2025): Solid Queue/Cache/Cable as defaults; Kamal
  - Thruster as deploy stack; Authentication generator (`bin/rails generate
authentication`); native auth replacing Devise for simple cases.
- Rails 7 (2021): Hotwire as default; importmap; Active Record encrypted
  attributes; query log tags.
- Rails 6 (2019): multi-database; Action Mailbox; Action Text; Webpacker
  (since dropped).

Track upstream Rails releases via Edge Rails guides; LTS-style maintenance is
informal in Rails (each major receives 1-2y of patches).
