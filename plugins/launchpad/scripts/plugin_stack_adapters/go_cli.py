"""Go CLI / Go service adapter.

Covers both Go CLIs and Go HTTP services (gin, fiber, stdlib net/http).
v1 treats them uniformly; splits if v1.1 needs it.
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
        runtime="Go 1.22+",
        package_manager="go mod",
        frameworks=[],
        database=None,
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="stdlib net/http",
        api_style="REST",
        routes_dir="cmd/",
        models_dir=None,
        auth_pattern=None,
    )


def describe_frontend() -> FrontendInfo | None:
    return None


def describe_app_flow() -> AppFlowInfo | None:
    return None


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Go service / CLI",
        deployment_target=None,
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["go test ./..."],
        typecheck=["go vet ./..."],
        lint=["golangci-lint run"],
        format=["gofmt -w ."],
        build=["go build ./..."],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    return PipelineOverrides(
        design_enabled=False,
        test_browser_enabled=False,
        frontend_docs_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="go_cli",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
