---
stack: django
pillar: Backend Python
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: django-admin startproject <name>
scaffolder_command_pinned_version: django@5.1+
---

# Django — Knowledge Anchor

## Idiomatic 2026 pattern

Django 5.1+ is the canonical batteries-included Python web framework. The 2026
idiom uses Python 3.12+, async views where appropriate (DB drivers still
mostly sync), the new `STORAGES` setting (replaces deprecated `DEFAULT_FILE_STORAGE`

- `STATICFILES_STORAGE`), `LoginRequiredMiddleware` as default auth gate, and
  `pyproject.toml` (PEP 621) for project metadata with `uv` as package manager.

Canonical layout from `django-admin startproject <name>`:

```
<name>/
  manage.py
  <name>/
    __init__.py
    settings.py        # site-wide settings (split into base/dev/prod for prod use)
    urls.py            # root URLConf
    asgi.py            # ASGI entry (preferred over wsgi.py for async)
    wsgi.py
```

Production-grade idiom adds:

```
<name>/
  apps/                # custom app modules per resource
    <resource>/
      __init__.py
      apps.py
      models.py
      admin.py
      urls.py
      views.py
      serializers.py   # if using DRF
      migrations/
  config/
    settings/
      __init__.py
      base.py
      dev.py
      prod.py
      test.py
    urls.py
    asgi.py
    wsgi.py
  templates/           # if using Django templates (not API-only)
  static/
  media/
  pyproject.toml
  Dockerfile
  .env.example
  manage.py
```

Version pins:

- `django>=5.1,<5.3`
- `psycopg[binary]>=3.2` (psycopg3, NOT psycopg2)
- `gunicorn>=23.0` or `uvicorn[standard]>=0.34` (ASGI)
- `whitenoise>=6.7` (static file serving in container deploys)
- `django-environ>=0.11` (env var parsing)
- `djangorestframework>=3.15` (if API)
- `pytest-django>=4.9`, `pytest>=8.3`

## Scaffolder behavior

`django-admin startproject <name>` creates the `<name>/` directory with the
basic `manage.py` + `<name>/{settings,urls,asgi,wsgi,__init__}.py` skeleton.
The scaffolder writes ONLY the framework skeleton — no Postgres config, no
templates dir, no per-app modules, no Dockerfile. Production-grade
restructuring (settings split, apps/ dir, etc.) is a follow-up cross-cutting
wiring step performed by the curate-flavored layer of the orchestrator.

LaunchPad's `/lp-scaffold-stack` for Django:

1. Runs `django-admin startproject <name>` via `safe_run`
2. Performs post-scaffold customization to settings.py: enable
   `psycopg`-compatible Postgres, add `WhiteNoiseMiddleware`, switch to
   pyproject.toml-managed deps via `uv init --python 3.13` + `uv add django ...`
3. Writes Dockerfile, `.env.example`, basic `apps/` skeleton (empty)

Django does NOT create a lockfile of its own; `uv.lock` materializes from
`uv add`.

## Tier-1 detection signals

- `manage.py` at repo root containing `django.core.management.execute_from_command_line`
- `<project>/settings.py` containing `INSTALLED_APPS = [` with `'django.contrib.admin'`
- `<project>/urls.py` with `urlpatterns = [`
- `*/migrations/0001_initial.py` files
- `pyproject.toml` with `django` in `[project.dependencies]`

## Common pitfalls + cold-rerun gotchas

- `django-admin startproject` creates the project at `<name>/`; running from
  inside an existing dir requires `django-admin startproject <name> .` (note
  the trailing `.`). LaunchPad's greenfield gate ensures the cwd is empty.
- Django 5.x dropped Python 3.10 support; 3.12+ required.
- `psycopg2` is legacy; 2026 idiom uses `psycopg` (psycopg3) — the package name
  collision is a frequent source of confusion.
- `STATICFILES_STORAGE` + `DEFAULT_FILE_STORAGE` settings are deprecated; use
  the unified `STORAGES = {"default": {...}, "staticfiles": {...}}` dict.
- `LoginRequiredMiddleware` (Django 5.1+) gates ALL views by default; opt out
  per-view with `@login_not_required` decorator or settings exclusion list.
- Async views work but the ORM is still sync-by-default; mixing `await` with
  sync ORM calls inside async views deadlocks. Use `sync_to_async()` wrappers
  or stay sync.
- `migrate` requires the database to exist; LaunchPad's pre-flight assumes
  user has created the local Postgres DB OR uses sqlite for first-run.

## Version evolution

- Django 5.1 (2024 H3 → 2025): `LoginRequiredMiddleware`; new generic
  composite-PK support; query-set explain improvements.
- Django 5.0 (2023 H4): unified `STORAGES`; Form `field_group_template`;
  database-computed default values.
- Django 4.2 (LTS, 2023 H2): supported through April 2026; psycopg3 support
  added; in-memory file uploads.

Track upstream Django releases at the 6-month freshness review; LTS releases
(4.2, 5.2) are the safe long-running pins for production deployments.
