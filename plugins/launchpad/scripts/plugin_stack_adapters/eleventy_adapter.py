"""Eleventy adapter — frontend content pillar (curate; no `npm create`).

v2.0 entry in the 10-stack catalog (HANDSHAKE §11). Eleventy is curate-mode
because there's no `npm create eleventy` analog — the scaffold copies a
knowledge-anchor pattern doc (`eleventy-pattern.md`) into the layer dir.

Per Phase 0.5 handoff §1.3: load-time pure (no subprocess), `run()` returns
an AdapterOutput with `stack_id == "eleventy"`.
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
        language="JavaScript",
        runtime="Node.js 20+",
        package_manager="pnpm",
        frameworks=["Eleventy 3"],
        database=None,
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="None (static site)",
        api_style="",
        routes_dir="src/",
        models_dir=None,
        auth_pattern=None,
    )


def describe_frontend() -> FrontendInfo | None:
    return FrontendInfo(
        framework="Eleventy 3",
        styling="CSS / template-driven",
        component_dir="src/_includes/",
        routing="File-based under src/",
    )


def describe_app_flow() -> AppFlowInfo | None:
    return AppFlowInfo(
        entry_routes=["/", "/posts/", "/about/"],
        auth_flow=None,
        primary_journeys=["Read content", "Browse archive"],
    )


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Eleventy 3 static site (Markdown + Nunjucks)",
        deployment_target="Cloudflare Pages / Netlify / GitHub Pages",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=[],
        typecheck=[],
        lint=[],
        format=["pnpm prettier --write ."],
        build=["pnpm exec eleventy"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    return PipelineOverrides(
        test_browser_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="eleventy",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
