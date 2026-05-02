"""Rails adapter — backend MVC pillar (Ruby; orchestrate, pure-headless).

v2.0 entry in the 10-stack catalog (HANDSHAKE §11). Rails scaffolds via
`rails new <name>` (pure-headless); this adapter renders the
architecture-doc-backing data once the layer materializes.

Per Phase 0.5 handoff §1.3: load-time pure (no subprocess), `run()` returns
an AdapterOutput with `stack_id == "rails"`.
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
        language="Ruby",
        runtime="Ruby 3.3+",
        package_manager="bundler",
        frameworks=["Rails 8", "Hotwire (Turbo + Stimulus)", "Active Record"],
        database="PostgreSQL",
        ci="GitHub Actions",
    )


def describe_backend() -> BackendInfo:
    return BackendInfo(
        framework="Rails 8",
        api_style="REST",
        routes_dir="config/routes.rb",
        models_dir="app/models/",
        auth_pattern="session",
    )


def describe_frontend() -> FrontendInfo | None:
    # Rails' fullstack layer ships its own view layer (ERB + Hotwire).
    return FrontendInfo(
        framework="Hotwire (Turbo + Stimulus)",
        styling="Tailwind CSS",
        component_dir="app/views/components/",
        routing="Rails routes",
    )


def describe_app_flow() -> AppFlowInfo | None:
    return AppFlowInfo(
        entry_routes=["/", "/users/sign_in", "/dashboard"],
        auth_flow="session (Devise)",
        primary_journeys=["Sign up", "Core workflow", "Settings"],
    )


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Rails 8 monolith (Ruby + Hotwire + PostgreSQL)",
        deployment_target="Fly.io / Render / Heroku",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["bundle exec rspec"],
        typecheck=["bundle exec sorbet tc"],
        lint=["bundle exec rubocop"],
        format=["bundle exec rubocop -a"],
        build=["bundle exec rails assets:precompile"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    # Fullstack with view layer — all stages enabled by default.
    return PipelineOverrides()


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="rails",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
