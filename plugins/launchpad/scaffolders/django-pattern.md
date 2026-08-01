---
stack: django
pillar: Backend Python
type: orchestrate
last_validated: 2026-08-01
scaffolder_command: django-admin startproject <name>
scaffolder_command_pinned_version: django@6.0+
---

# Django — Knowledge Anchor

## Idiomatic 2026 pattern

Django 6.0 is the canonical batteries-included Python web framework; Django 5.2
is the current LTS (supported to April 2028). The 2026 idiom uses Python 3.12+
(6.0's floor; 3.13 recommended), async views and the native async ORM methods
(`aget`, `acreate`, `afirst`, `async for`), the unified `STORAGES` setting
(added in 4.2; `DEFAULT_FILE_STORAGE` and `STATICFILES_STORAGE` were REMOVED in
5.1), `LoginRequiredMiddleware` as an opt-in project-wide auth gate, built-in
CSP via `ContentSecurityPolicyMiddleware` + `SECURE_CSP` (6.0), the built-in
Tasks framework for background jobs (6.0), and `pyproject.toml` (PEP 621) for
project metadata with `uv` as package manager.

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

- `django>=6.0,<6.1` (current stable) or `django>=5.2,<5.3` (LTS track, to April
  2028). Django 5.1 and 4.2 are both EOL. Note 6.1 lands August 2026.
- `psycopg[binary]>=3.3` (psycopg3, NOT psycopg2; Django 6.0's own floor is
  3.1.12, and it requires PostgreSQL 14+)
- `gunicorn>=26.0` or `uvicorn[standard]>=0.52` (ASGI)
- `whitenoise>=6.12` (static file serving in container deploys)
- `django-environ>=0.14` (env var parsing)
- `djangorestframework>=3.17` (if API; 3.17 is the first series declaring
  Django 6.0 support)
- `pytest-django>=4.12` (first series declaring Django 6.0 support), `pytest>=9.1`

## Scaffolder behavior

`django-admin startproject <name>` creates the `<name>/` directory with the
basic `manage.py` + `<name>/{settings,urls,asgi,wsgi,__init__}.py` skeleton.
As of Django 6.0, `startproject`/`startapp` create the target directory if it
does not already exist, and the `DEFAULT_AUTO_FIELD` line is no longer written
to the templates (it now defaults to `BigAutoField`).
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
- Django 6.0 requires Python 3.12+ (supports 3.12/3.13/3.14). Django 5.2 still
  supports 3.10 through 3.14; 5.1 and earlier are EOL.
- `psycopg2` is legacy; 2026 idiom uses `psycopg` (psycopg3) — the package name
  collision is a frequent source of confusion.
- `STATICFILES_STORAGE` + `DEFAULT_FILE_STORAGE` were REMOVED in Django 5.1
  (deprecated in 4.2); setting them today is silently inert. Use the unified
  `STORAGES = {"default": {...}, "staticfiles": {...}}` dict.
- `LoginRequiredMiddleware` (Django 5.1+) is NOT in the default `MIDDLEWARE`.
  You must add it explicitly, after `AuthenticationMiddleware`. Only once
  enabled does it gate all views; opt out per-view with `@login_not_required`.
  Assuming it is on by default leaves views unauthenticated.
- Async views work but there is still no async database backend. Calling the
  sync ORM from an async context raises `SynchronousOnlyOperation`, it does not
  deadlock. Prefer the native async ORM methods (`aget`, `acreate`, `afirst`,
  `async for`) or wrap sync code in `sync_to_async()`.
- `migrate` requires the database to exist; LaunchPad's pre-flight assumes
  user has created the local Postgres DB OR uses sqlite for first-run.

## Version evolution

- Django 6.0 (2025-12-03, current stable): built-in Tasks/background-jobs
  framework (`django.tasks`, `TASKS` setting); template partials
  (`{% partialdef %}`); built-in CSP (`ContentSecurityPolicyMiddleware`,
  `SECURE_CSP`); modernized email API; `AsyncPaginator`; `DEFAULT_AUTO_FIELD`
  now defaults to `BigAutoField` and is no longer written to templates;
  Python 3.12+ required.
- Django 5.2 (2025-04, LTS to April 2028): `CompositePrimaryKey`; automatic
  model imports in `shell`.
- Django 5.1 (2024-08, EOL 2025-12-03): `LoginRequiredMiddleware`;
  `{% querystring %}` tag; removed `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE`.
- Django 5.0 (2023-12): Form `field_group_template`; database-computed default
  values.
- Django 4.2 (LTS, 2023-04, EOL 2026-04-07): introduced the unified `STORAGES`
  setting; psycopg3 support.

Track upstream Django releases at the 6-month freshness review. Django 5.2 is
the only currently supported LTS (to April 2028); 4.2 LTS went EOL 2026-04-07.
Next releases: 6.1 in August 2026, 6.2 LTS in April 2027.
