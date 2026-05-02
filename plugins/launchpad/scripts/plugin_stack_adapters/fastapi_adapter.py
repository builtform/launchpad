"""FastAPI adapter — backend Python pillar (curate; no official CLI).

v2.0 entry in the 10-stack catalog (HANDSHAKE §11). FastAPI is curate-mode
because there's no equivalent of `npm create` — the scaffold copies a
knowledge-anchor pattern doc (`fastapi-pattern.md`) into the layer dir.

Per Phase 0.5 handoff §1.3: load-time pure (no subprocess), `run()` returns
an AdapterOutput with `stack_id == "fastapi"`.
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
        language="Python",
        runtime="Python 3.12+",
        package_manager="uv",
        frameworks=["FastAPI", "Pydantic v2", "SQLAlchemy 2"],
        database="PostgreSQL",
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="FastAPI",
        api_style="REST",
        routes_dir="apps/api/src/routes/",
        models_dir="apps/api/src/models/",
        auth_pattern="JWT",
    )


def describe_frontend() -> FrontendInfo | None:
    # Backend-only by default; pair with Next/Astro adapter for polyglot.
    return None


def describe_app_flow() -> AppFlowInfo | None:
    return None


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="FastAPI backend (Python 3.12 + Pydantic v2 + SQLAlchemy 2)",
        deployment_target="Render / Fly.io / AWS",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["uv run pytest"],
        typecheck=["uv run mypy ."],
        lint=["uv run ruff check ."],
        format=["uv run ruff format ."],
        build=["uv build"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    return PipelineOverrides(
        design_enabled=False,
        test_browser_enabled=False,
        frontend_docs_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="fastapi",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
