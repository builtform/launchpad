---
stack: fastapi
pillar: Backend Python
type: curate
last_validated: 2026-08-01
scaffolder_command: (curate; `uvx fastapi-new` exists but emits only a minimal single-file app, so LaunchPad scaffolds the layered layout per this doc)
scaffolder_command_pinned_version: fastapi@0.141.x (Starlette 1.x requires fastapi>=0.133)
---

# FastAPI — Knowledge Anchor

## Idiomatic 2026 pattern

FastAPI 0.141+ is the canonical async Python web framework, built on Starlette
1.x, Pydantic v2, and Uvicorn. The 2026 idiom uses Python 3.13+ (3.14
preferred), async-first throughout, dependency injection via `Depends()` with
`Annotated[]`, type-validated request/response models via Pydantic v2
`BaseModel`, and async SQLAlchemy 2.0 as the standard ORM with asyncpg as the
Postgres driver. Project metadata lives in `pyproject.toml` (PEP 621) with `uv`
as the canonical package manager (replacing pip/poetry as the 2026 default).

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
.python-version    # 3.13 or 3.14
pyproject.toml
Dockerfile         # multi-stage, python:3.14-slim base
```

Version pins (in `pyproject.toml`):

- `fastapi[standard]>=0.141,<0.142`. Do NOT cap below 0.133: earlier releases
  pin `starlette<1.0.0`, which is unsatisfiable alongside Starlette 1.x.
- `starlette>=1.3` (transitive via fastapi; pinned explicitly to document the
  1.x break)
- `uvicorn[standard]>=0.52`
- `pydantic>=2.13`
- `pydantic-settings>=2.14`
- `sqlalchemy[asyncio]>=2.0.51,<2.1` (2.1 is still beta as of 2026-07)
- `asyncpg>=0.31`
- `alembic>=1.18`
- `structlog>=26.1` (for structured logging)
- `httpx>=0.28,<1.0` (test client; `fastapi[standard]` caps `<1.0`)
- `pytest>=9.1`, `pytest-asyncio>=1.4` (1.0 removed the `event_loop` fixture;
  use `loop_scope`)

## Scaffolder behavior

FastAPI has no official CLI scaffolder that emits a layered layout.
`uvx fastapi-new <name>` (published under the `fastapi` org) creates only a
minimal uv-configured single-file app, and `fastapi-cli` itself provides just
`fastapi dev` / `fastapi run`. This is therefore a `curate`-mode stack.
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

- `pyproject.toml` with `fastapi` in the `[project]` `dependencies` array
- `src/main.py` (or `app/main.py`, `main.py` at root) containing `FastAPI(`
  constructor invocation
- `alembic.ini` at repo root paired with `alembic/` directory
- `uv.lock` (modern) or `poetry.lock` (legacy) or `requirements.txt` with
  fastapi pin
- `.python-version` file pinning 3.13+ (FastAPI requires Python >=3.10)

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
- Middleware must be registered before the app starts serving, and relative
  middleware order matters. For CORS specifically, `allow_credentials=True`
  forbids `["*"]` in `allow_origins` / `allow_methods` / `allow_headers`.
- Starlette 1.0 (2026-03-22) removed `on_startup`/`on_shutdown` params,
  `@app.on_event()`, `@app.route()`, `@app.websocket_route()`,
  `add_event_handler()`, and `Jinja2Templates(**env_options)`. FastAPI
  re-implemented `on_event` and the middleware/exception-handler decorators for
  backwards compatibility (0.128.3+), so FastAPI-level code still works, but any
  code importing those idioms from `starlette` directly breaks. Use `lifespan`
  unconditionally.
- pytest-asyncio 1.0 removed the `event_loop` fixture; 2024-era `conftest.py`
  snippets that override it fail on import. Use `loop_scope` or
  `asyncio_mode = "auto"`.

## Version evolution

- FastAPI 0.141 (2026-07): `app.frontend()` static/SPA serving; SSE + JSONL
  streaming response fixes.
- FastAPI 0.133 (2026-02-24): first release supporting Starlette 1.0+ (the
  `starlette<1.0.0` cap was dropped here).
- FastAPI 0.128.3 (2026-02): `on_event` re-implemented inside FastAPI ahead of
  Starlette 1.0 removing it.
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
