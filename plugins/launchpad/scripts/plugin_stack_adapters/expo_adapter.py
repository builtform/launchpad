"""Expo adapter — frontend mobile (React Native) pillar (orchestrate, pure-headless).

v2.0 entry in the 10-stack catalog (HANDSHAKE §11). Expo scaffolds via
`npx create-expo-app@latest` (pure-headless); this adapter renders the
architecture-doc-backing data once the layer materializes.

Per Phase 0.5 handoff §1.3: load-time pure (no subprocess), `run()` returns
an AdapterOutput with `stack_id == "expo"`.
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
        runtime="Node.js 20+ / Expo Go runtime",
        package_manager="pnpm",
        frameworks=["Expo SDK 51", "React Native", "Expo Router"],
        database=None,
        ci="GitHub Actions / EAS Build",
    )


def describe_backend() -> BackendInfo:
    # Expo apps are typically clients; backend is a separate layer in
    # the user's monorepo (Hono/FastAPI/etc.).
    return BackendInfo(
        framework="None (client app)",
        api_style="",
        routes_dir="apps/mobile/app/",
        models_dir=None,
        auth_pattern=None,
    )


def describe_frontend() -> FrontendInfo | None:
    return FrontendInfo(
        framework="Expo SDK 51 + React Native",
        styling="StyleSheet / NativeWind",
        component_dir="apps/mobile/components/",
        routing="Expo Router (file-based under app/)",
    )


def describe_app_flow() -> AppFlowInfo | None:
    return AppFlowInfo(
        entry_routes=["/(tabs)", "/(auth)/sign-in", "/profile"],
        auth_flow=None,
        primary_journeys=["Onboarding", "Core workflow", "Profile"],
    )


def describe_product_context() -> ProductContextInfo:
    return ProductContextInfo(
        stack_summary="Expo SDK 51 mobile app (React Native + Expo Router)",
        deployment_target="EAS Build → App Store / Play Store",
    )


def default_commands() -> CommandsConfig:
    return CommandsConfig(
        test=["pnpm test"],
        typecheck=["pnpm typecheck"],
        lint=["pnpm lint"],
        format=["pnpm format"],
        build=["pnpm exec expo export"],
    )


def default_pipeline_overrides() -> PipelineOverrides:
    # Mobile target — design on (Figma sync still applies); browser tests off
    # (Expo runs in simulator/device, not a browser).
    return PipelineOverrides(
        test_browser_enabled=False,
    )


def run() -> AdapterOutput:
    return AdapterOutput(
        stack_id="expo",
        tech_stack=describe_tech_stack(),
        backend=describe_backend(),
        frontend=describe_frontend(),
        app_flow=describe_app_flow(),
        product_context=describe_product_context(),
        commands=default_commands(),
        pipeline_overrides=default_pipeline_overrides(),
    )
