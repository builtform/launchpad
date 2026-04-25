"""TS monorepo adapter (Next.js + Hono + Prisma + Turborepo + pnpm).

Matches the LaunchPad template's native shape. Also applies to BuiltForm
and most "modern full-stack TS" projects.
"""
from .contracts import (
    AdapterOutput,
    AppFlowInfo,
    BackendInfo,
    CommandsConfig,
    FrontendInfo,
    PipelineOverrides,
    ProductContextInfo,
    TechStackInfo,
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
