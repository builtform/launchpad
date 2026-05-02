"""Hugo adapter — frontend content (Go) pillar (orchestrate, pure-headless).

v2.0 entry in the 10-stack catalog (HANDSHAKE §11). Hugo scaffolds via
`hugo new site <name>` (pure-headless); this adapter renders the
architecture-doc-backing data once the layer materializes.

Per Phase 0.5 handoff §1.3: load-time pure (no subprocess), `run()` returns
an AdapterOutput with `stack_id == "hugo"`.
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
        language="Go",
        runtime="Hugo binary (Go 1.22+ build)",
        package_manager="hugo modules",
        frameworks=["Hugo"],
        database=None,
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    # Static site — no backend.
    return BackendInfo(
        framework="None (static site)",
        api_style="",
        routes_dir="content/",
        models_dir=None,
        auth_pattern=None,
    )


def describe_frontend() -> FrontendInfo | None:
    return FrontendInfo(
        framework="Hugo",
        styling="Hugo theme (CSS / Sass)",
        component_dir="layouts/",
        routing="Content-driven (file-based under content/)",
    )


def describe_app_flow() -> AppFlowInfo | None:
    return AppFlowInfo(
        entry_routes=["/", "/posts/", "/about/"],
        auth_flow=None,
        primary_journeys=["Read content", "Browse archive"],
    )


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Hugo static site (Go-built; content collections)",
        deployment_target="Cloudflare Pages / Netlify / GitHub Pages",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=[],
        typecheck=[],
        lint=[],
        format=[],
        build=["hugo --minify"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    # Content site — frontend docs on; design on; browser tests off
    # (no JS app surface to test).
    return PipelineOverrides(
        test_browser_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="hugo",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
