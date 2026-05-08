"""TS monorepo adapter (Next.js + Hono + Prisma + Turborepo + pnpm).

Matches the LaunchPad template's native shape. Also applies to BuiltForm
and most "modern full-stack TS" projects.

v2.1 refactor: implements `Adapter` Protocol from contracts.py with
`upstream=None` and `composes_with={}` (this adapter cannot be combined with
another stack: it is itself a Turborepo). The legacy function API
(`describe_*`, `run`) is preserved for the polyglot composer; new v2.1
dispatch sites import `ADAPTER` (the module-level Adapter instance).
"""
from __future__ import annotations

from pathlib import Path

from typing import Mapping

from .contracts import (
    _EMPTY_PACKAGE_PATHS,
    _EMPTY_WORKSPACE_MAP,
    AdapterOutput,
    AppFlowInfo,
    BackendInfo,
    CommandsConfig,
    CompositionRule,
    FrontendInfo,
    PipelineOverrides,
    ProductContextInfo,
    StackIdActive,
    TechStackInfo,
    UnwrapStrategy,
    UpstreamTemplate,
)


def describe_tech_stack() -> TechStackInfo:
    return TechStackInfo(
        language="TypeScript",
        runtime="Node.js 20+",
        package_manager="pnpm",
        frameworks=["Next.js 15 App Router", "Hono", "Prisma", "Turborepo"],
        database="PostgreSQL",
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="Hono",
        api_style="REST",
        routes_dir="apps/api/src/routes/",
        models_dir="packages/db/prisma/",
        auth_pattern="session",
    )


def describe_frontend() -> FrontendInfo | None:
    return FrontendInfo(
        framework="Next.js 15 App Router",
        styling="Tailwind CSS v4",
        component_dir="apps/web/components/",
        routing="App Router (file-based)",
    )


def describe_app_flow() -> AppFlowInfo | None:
    return AppFlowInfo(
        entry_routes=["/", "/signin", "/dashboard"],
        auth_flow=None,
        primary_journeys=["Onboarding", "Core workflow", "Settings"],
    )


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="TypeScript monorepo (Next.js 15 + Hono + Prisma + PostgreSQL)",
        deployment_target="Vercel (web) + host of choice (API)",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["pnpm test"],
        typecheck=["pnpm typecheck"],
        lint=["pnpm lint"],
        format=["pnpm format"],
        build=["pnpm build"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    # TS monorepo with frontend — all stages enabled by default.
    return PipelineOverrides()


def run() -> AdapterOutput:
    """Aggregate all adapter methods into a single AdapterOutput."""
    return AdapterOutput(
        stack_id="ts_monorepo",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )


class TsMonorepoAdapter:
    """Adapter Protocol implementation for ts_monorepo.

    This adapter has no upstream template (the LaunchPad reference shape IS
    the template) and cannot compose with another stack (Turborepo composition
    is the LaunchPad shape itself). `scaffold_into` and `apply_overlay` are
    no-ops; the kernel-renderer + plugin_default_generators emit the actual
    files.
    """

    stack_id: StackIdActive = "ts_monorepo"
    upstream: UpstreamTemplate | None = None
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = None
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict[StackIdActive, CompositionRule] = {}
    # Per Codex P1-B harden D6: ts_monorepo is a Turborepo itself; no apps/
    # wrapping in either single or composition mode (composition mode is in
    # any case rejected via the ts_monorepo + * catch-all).
    workspace_source_map_single: Mapping[str, str] = _EMPTY_WORKSPACE_MAP
    workspace_source_map_composition: Mapping[str, str] = _EMPTY_WORKSPACE_MAP
    package_workspace_paths: tuple[str, ...] = _EMPTY_PACKAGE_PATHS

    def scaffold_into(self, tempdir: Path) -> None:
        return None

    def apply_overlay(self, tempdir: Path) -> None:
        return None


ADAPTER = TsMonorepoAdapter()
