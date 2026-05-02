"""Contracts for stack adapters.

Every concrete adapter (ts_monorepo, python_django, go_cli, generic) returns
TypedDicts defined here. The composer (polyglot.py) merges adapter outputs
against these same contracts. Unit tests in plugins/launchpad/scripts/tests/ validate every
adapter output against the contracts before the Jinja2 generator consumes it.

Without these contracts, adapters drift and StrictUndefined only catches the
drift at render time (per-stack, in production). The contracts push the check
to the static layer.
"""
from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


StackId = Literal[
    "ts_monorepo", "python_django", "go_cli", "generic",
    "astro", "fastapi", "rails", "hugo",
    "eleventy", "expo",
]


class TechStackInfo(TypedDict):
    """Backing data for docs/architecture/TECH_STACK.md."""

    language: str                   # "TypeScript", "Python", "Go", "Unknown"
    runtime: str                    # "Node.js 20", "Python 3.12", "Go 1.22", etc.
    package_manager: str            # "pnpm", "poetry", "go mod", ""
    frameworks: list[str]           # ["Next.js 15", "Hono", "Prisma"]
    database: str | None            # "PostgreSQL", None
    ci: str | None                  # "GitHub Actions", None


class BackendInfo(TypedDict):
    """Backing data for docs/architecture/BACKEND_STRUCTURE.md."""

    framework: str                  # "Hono", "Django", "Gin", "Express"
    api_style: str                  # "REST", "GraphQL", "tRPC"
    routes_dir: str                 # "apps/api/src/routes/", "myapp/urls.py"
    models_dir: str | None          # "packages/db/prisma/", "myapp/models.py", None
    auth_pattern: str | None        # "session", "JWT", "OAuth", None


class FrontendInfo(TypedDict):
    """Backing data for docs/architecture/FRONTEND_GUIDELINES.md (v1.1) and
    docs/architecture/APP_FLOW.md.

    Returns None from adapters for backend-only stacks.
    """

    framework: str                  # "Next.js 15 App Router", "React SPA"
    styling: str                    # "Tailwind CSS v4", "CSS Modules"
    component_dir: str              # "apps/web/components/"
    routing: str                    # "App Router", "React Router"


class AppFlowInfo(TypedDict):
    """Backing data for docs/architecture/APP_FLOW.md. Returns None for
    backend-only stacks (detector reports no frontend)."""

    entry_routes: list[str]         # ["/", "/signin", "/dashboard"]
    auth_flow: str | None           # "Magic link", "OAuth (GitHub)", None
    primary_journeys: list[str]     # ["Onboarding", "Purchase", "Support"]


class ProductContextInfo(TypedDict):
    """Backing data for docs/architecture/PRD.md framing. Stack-influenced
    but not stack-defined — PRD is mostly product content. This surfaces the
    tech-framing line (e.g., "TypeScript monorepo" vs "Python backend")."""

    stack_summary: str              # One-line tech summary for the PRD intro
    deployment_target: str | None   # "Vercel + Render", "AWS ECS", None


class CommandsConfig(TypedDict):
    """Backing data for config.yml `commands:` section seed.

    Every value is a list (always-array contract). Empty list = skip.
    """

    test: list[str]
    typecheck: list[str]
    lint: list[str]
    format: list[str]
    build: list[str]


class PipelineOverrides(TypedDict, total=False):
    """Stack-specific overrides to config.yml `pipeline:` defaults.

    Only fields the adapter wants to override from defaults need appear.
    Most adapters only override design/frontend-specific toggles.
    """

    design_enabled: NotRequired[bool]          # False for backend-only
    test_browser_enabled: NotRequired[bool]    # False for backend-only
    frontend_docs_enabled: NotRequired[bool]   # False for backend-only


class AdapterOutput(TypedDict):
    """Aggregated output from a single adapter. The composer iterates these
    across multiple adapters when the detector reports polyglot."""

    stack_id: StackId
    tech_stack: TechStackInfo
    backend: BackendInfo
    frontend: FrontendInfo | None
    app_flow: AppFlowInfo | None
    product_context: ProductContextInfo
    commands: CommandsConfig
    pipeline_overrides: PipelineOverrides


# Exported for adapter implementations
__all__ = [
    "StackId",
    "TechStackInfo",
    "BackendInfo",
    "FrontendInfo",
    "AppFlowInfo",
    "ProductContextInfo",
    "CommandsConfig",
    "PipelineOverrides",
    "AdapterOutput",
]
