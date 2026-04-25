"""Generic / unknown-stack adapter — the fallback.

Fires when the detector reports zero recognized manifests, or when the only
manifests present are for stacks with no concrete v1 adapter (Cargo.toml,
Gemfile, composer.json — all route here for v1, gain dedicated adapters in v1.1).

Output is deliberately sparse. `/lp-define` treats the generic path as a
prompt-the-user flow: it asks the user for language, framework, and test
command, then writes those into config.yml manually. This adapter provides
the empty scaffold the prompt fills.
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
        language="Unknown",
        runtime="",
        package_manager="",
        frameworks=[],
        database=None,
        ci=None,
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="Unknown",
        api_style="",
        routes_dir="",
        models_dir=None,
        auth_pattern=None,
    )


def describe_frontend() -> FrontendInfo | None:
    return None


def describe_app_flow() -> AppFlowInfo | None:
    return None


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Stack to be described by user",
        deployment_target=None,
    )


def default_commands() -> CommandsConfig:
    # Empty arrays mean "silently skip." /lp-define will prompt the user to
    # fill these in; unfilled fields stay skip (non-blocking).
    return CommandsConfig(
        test=[],
        typecheck=[],
        lint=[],
        format=[],
        build=[],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    # Conservative: disable stages that assume a known stack.
    return PipelineOverrides(
        design_enabled=False,
        test_browser_enabled=False,
        frontend_docs_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="generic",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
