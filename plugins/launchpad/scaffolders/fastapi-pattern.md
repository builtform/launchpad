---
stack: fastapi
pillar: Backend Python
type: curate
last_validated: 2026-04-30
scaffolder_command: (curate — no official CLI; manual scaffold per this doc)
scaffolder_command_pinned_version: fastapi@0.115+
---

# FastAPI — Knowledge Anchor

## Idiomatic 2026 pattern

FastAPI 0.115+ is the canonical async Python web framework, built on Starlette

- Pydantic v2 + Uvicorn. The 2026 idiom uses Python 3.12+ (3.13 preferred),
  async-first throughout, dependency-injection via `Depends()`, type-validated
  request/response models via Pydantic v2 BaseModel, and async SQLAlchemy 2.0 as
  the standard ORM with asyncpg as the Postgres driver. Project metadata lives in
  `pyproject.toml` (PEP 621) with `uv` as the canonical package manager (replaces
  pip/poetry as the 2026 default).

Canonical layout:

```
src/
  main.py          # FastAPI app + CORS + middleware + lifespan + /health
  api/
    __init__.py
    deps.py        # shared Depends() (db session, auth)
    routers/
      __init__.py
      <resource>.py
  core/
    config.py      # pydantic-settings BaseSettings
    security.py    # auth, password hashing
  db/
    __init__.py
    base.py        # SQLAlchemy DeclarativeBase
    session.py     # async engine + session factory
    models/        # ORM model modules
  schemas/         # Pydantic request/response models (per resource)
alembic/           # alembic init output
tests/
  conftest.py      # pytest-asyncio + httpx AsyncClient fixtures
  test_health.py
.env.example
.python-version    # 3.12 or 3.13
pyproject.toml
Dockerfile         # multi-stage, python:3.13-slim base
```

Version pins (in `pyproject.toml`):

- `fastapi>=0.115,<0.117`
- `uvicorn[standard]>=0.34`
- `pydantic>=2.9`
- `pydantic-settings>=2.5`
- `sqlalchemy[asyncio]>=2.0.36`
- `asyncpg>=0.30`
- `alembic>=1.14`
- `structlog>=24.4` (for structured logging)
- `httpx>=0.27` (test client)
- `pytest>=8.3`, `pytest-asyncio>=0.24`

## Scaffolder behavior

FastAPI has NO official CLI scaffolder. This is a `curate`-mode stack.
LaunchPad's curate path materializes the canonical layout via Claude using this
knowledge anchor as context. The `/lp-scaffold-stack` command, when dispatching
a `fastapi` layer, calls `knowledge_anchor_loader.read_and_verify()` on this
file, then emits a structured task descriptor that Claude consumes to write
the full layout above.

After file materialization, the cross-cutting wiring step runs `uv sync` (NOT
`pip install`); `uv` produces `uv.lock` as the deterministic lockfile.

Alembic init: `uv run alembic init alembic` produces the migrations skeleton;
the curate emit pre-fills `alembic.ini` + `alembic/env.py` so manual init isn't
required.

## Tier-1 detection signals

- `pyproject.toml` with `fastapi` in `[project.dependencies]`
- `src/main.py` (or `app/main.py`, `main.py` at root) containing `FastAPI(`
  constructor invocation
- `alembic.ini` at repo root paired with `alembic/` directory
- `uv.lock` (modern) or `poetry.lock` (legacy) or `requirements.txt` with
  fastapi pin
- `.python-version` file pinning 3.12+

## Common pitfalls + cold-rerun gotchas

- Pydantic v1 → v2 migration: `BaseModel.dict()` → `.model_dump()`,
  `BaseModel.parse_obj()` → `.model_validate()`, `Config` class → `model_config`
  ClassVar; pre-2.0 FastAPI tutorials reference deprecated v1 APIs.
- SQLAlchemy 1.x → 2.0: declarative base via `DeclarativeBase` (not
  `declarative_base()`); `relationship()` returns `Mapped[]`; `Session.execute(select(...))` (not `Session.query()`).
- Async/sync mixing: `def` route handlers run in a threadpool; `async def`
  handlers run in the event loop. Mixing async DB session with sync handler
  causes deadlocks. Standardize on `async def` throughout.
- `uvicorn` reload mode (`--reload`) does NOT survive crashes from import-time
  errors; structured logs help debug.
- Alembic autogenerate misses certain SQLAlchemy 2.0 constructs (CheckConstraint
  named, server_default expressions); review every generated migration.
- CORS middleware must be added BEFORE routes, not after; ordering matters.

## Version evolution

- FastAPI 0.115 (2024 → 2025): `Annotated[]` dependency injection promoted to
  preferred syntax over `Depends()` defaults; lifespan events stable; OpenAPI
  3.1 by default.
- FastAPI 0.110 (2024 H1): Pydantic v2 baseline (v1 dropped); WebSocket
  improvements.
- FastAPI 0.100 (2023): first Pydantic-v2-compatible release; major rewrite of
  internal validation logic.

Curate-mode means LaunchPad ships the pattern doc itself as the canonical
spec; track upstream FastAPI + Pydantic + SQLAlchemy releases at the 6-month
freshness review for breaking-change drift.
