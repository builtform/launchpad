"""Python/Django adapter.

Covers Django + Postgres deployments. Also a reasonable fallback for
Flask/FastAPI-backed projects that still have a pyproject.toml with a
recognizable web framework.
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
        runtime="Python 3.11+",
        package_manager="poetry",
        frameworks=["Django"],
        database="PostgreSQL",
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="Django",
        api_style="REST (Django REST Framework)",
        routes_dir="myapp/urls.py",
        models_dir="myapp/models.py",
        auth_pattern="session (Django auth)",
    )


def describe_frontend() -> FrontendInfo | None:
    # Django can ship server-rendered templates + HTMX, but that's a v1.1
    # adapter refinement. v1 treats Django as backend-only — no FrontendInfo.
    return None


def describe_app_flow() -> AppFlowInfo | None:
    # Backend-only — no user-journey surface worth scaffolding.
    return None


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Python/Django backend with PostgreSQL",
        deployment_target=None,
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["pytest"],
        typecheck=[],
        lint=["ruff check ."],
        format=["ruff format ."],
        build=["python manage.py collectstatic --noinput"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    return PipelineOverrides(
        design_enabled=False,
        test_browser_enabled=False,
        frontend_docs_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="python_django",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
