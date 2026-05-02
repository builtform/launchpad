"""Astro adapter — frontend content / performance pillar (orchestrate).

v2.0 entry in the 10-stack catalog (HANDSHAKE §11). Astro scaffolds via
`npm create astro@latest` (pure-headless); this adapter renders the
architecture-doc-backing data once the layer materializes at `apps/web/`.

Per Phase 0.5 handoff §1.3: load-time pure (no subprocess), `run()` returns
an AdapterOutput with `stack_id == "astro"` for direct interop with the v1
adapter dispatch.
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
        frameworks=["Astro 5", "Tailwind CSS v4"],
        database=None,
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    # Astro's runtime is built-in (SSR + Astro endpoints); not a separate backend.
    return BackendInfo(
        framework="Astro endpoints (built-in)",
        api_style="REST",
        routes_dir="apps/web/src/pages/",
        models_dir=None,
        auth_pattern=None,
    )


def describe_frontend() -> FrontendInfo | None:
    return FrontendInfo(
        framework="Astro 5",
        styling="Tailwind CSS v4",
        component_dir="apps/web/src/components/",
        routing="File-based (src/pages/)",
    )


def describe_app_flow() -> AppFlowInfo | None:
    return AppFlowInfo(
        entry_routes=["/", "/about", "/blog"],
        auth_flow=None,
        primary_journeys=["Landing", "Content read", "Contact"],
    )


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Astro 5 (frontend content/performance, content collections)",
        deployment_target="Vercel / Netlify / Cloudflare Pages",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["pnpm test"],
        typecheck=["pnpm astro check"],
        lint=["pnpm lint"],
        format=["pnpm format"],
        build=["pnpm build"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    # Frontend-only: design + browser tests + frontend docs all enabled.
    return PipelineOverrides()


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="astro",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
