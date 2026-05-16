"""Generic / unknown-stack adapter — the fallback.

Fires when the detector reports zero recognized manifests, or when the only
manifests present are for stacks with no concrete v1 adapter (Cargo.toml,
Gemfile, composer.json — all route here for v1, gain dedicated adapters in v1.1).

Output is deliberately sparse. `/lp-define` treats the generic path as a
prompt-the-user flow: it asks the user for language, framework, and test
command, then writes those into config.yml manually. This adapter provides
the empty scaffold the prompt fills.

v2.1 refactor (Phase 4 plan §2.1): adds `Adapter` Protocol surface alongside
the legacy `run()` function. `upstream=None` (no upstream template;
typed-fallback only). Hidden from the user-facing pick-stack menu; reachable
only via v2.2-candidate fallback routing per §3.12 verbatim INFO log
("<stack-id> detected; v2.2 ships dedicated adapter; using generic
fallback.").
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path

from .contracts import (
    _EMPTY_PACKAGE_PATHS,
    _EMPTY_WORKSPACE_MAP,
    Adapter,
    AdapterOutput,
    AdapterScaffoldError,
    AppFlowInfo,
    BackendInfo,
    CommandsConfig,
    CompositionRule,
    FrontendInfo,
    PipelineOverrides,
    ProductContextInfo,
    StackIdActive,
    TechStackInfo,
    UnwrapStrategy,
    UpstreamTemplate,
)

LOG = logging.getLogger("plugin_stack_adapters.generic")


# v2.1.4 BL-331: `generic` is now an explicit primary-stack option in
# the /lp-pick-stack manual-override menu (5 (generic, role) tuples in
# lp_pick_stack.VALID_COMBINATIONS). Pre-v2.1.4 a HIDDEN_FROM_PICK_STACK_MENU
# flag here documented the inverse — generic was reachable only via the
# v2.2-candidate fallback path. Codex PR #67 P3-A flagged the stale
# flag as misleading after BL-331; removed entirely (zero consumers
# verified via repo-wide grep). The user-facing menu surface is owned
# by /lp-pick-stack.md Step 4 + lp_pick_stack.VALID_COMBINATIONS, not
# by adapter-side flags.


def log_v22_candidate_routing(detected_stack_id: str) -> None:
    """Phase 4 §3.12 verbatim INFO log for v2.2-candidate detector routing.

    Used by lp_pick_stack when the detector reports a stack id that v2.1
    does not have a dedicated adapter for; the message is part of the
    user-facing surface so it MUST match §3.12 verbatim.
    """
    LOG.info(
        "%s detected; v2.2 ships dedicated adapter; using generic fallback.",
        detected_stack_id,
    )


_COMPOSES_WITH: dict[StackIdActive, CompositionRule] = {
    "nextjs_standalone": {
        "workspace_name": "app",
        "conflict_policy": {
            "package.json": "merge-keys",
        },
    },
    "nextjs_fastapi": {
        "workspace_name": "app",
        "conflict_policy": {
            "package.json": "merge-keys",
        },
    },
    "astro": {
        "workspace_name": "content",
        "conflict_policy": {
            "package.json": "merge-keys",
        },
    },
}


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
    # v2.1.6 BL-349 round-2 review fix (Greptile P1): the v2.1.6
    # initial scope set `static_capable=True` on the generic adapter,
    # which rendered "Static site — no backend" framing in
    # BACKEND_STRUCTURE.md for ANY project routed through `generic`.
    # That includes:
    #   * standalone Hono projects (detector emits `generic` when no
    #     monorepo signal is present);
    #   * `hono` and `supabase` v2.0 catalog ids (both routed through
    #     `generic` via lp_define_runner._single_adapter and
    #     polyglot.ADAPTERS until dedicated adapters ship);
    #   * unknown / unmodelled stacks (detector fallback path);
    #   * (post round-2) `nextjs_standalone` and `python_generic`
    #     detector emissions that re-route here.
    #
    # Calling any of those "no backend" is actively wrong; under-
    # claiming backend presence here over-corrected. Flipping to
    # `static_capable=False` restores the pre-v2.1.6 server-side
    # placeholder framing, which is the correct default when the
    # adapter genuinely doesn't know whether a backend exists — an
    # empty "Unknown" placeholder section is honest about the unknown
    # state, while "Static site — no backend" claims false negative.
    return BackendInfo(
        framework="Unknown",
        api_style="",
        routes_dir="",
        models_dir=None,
        auth_pattern=None,
        static_capable=False,
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


class GenericAdapter:
    """Adapter Protocol implementation for the typed-fallback adapter.

    No upstream; scaffold_into and apply_overlay are no-ops (the user fills
    config.yml manually via /lp-define). Composes with the three real v2.1
    adapters; rejected when paired with itself or with ts_monorepo.
    """

    stack_id: StackIdActive = "generic"
    upstream: UpstreamTemplate | None = None
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = "extra"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict[StackIdActive, CompositionRule] = _COMPOSES_WITH
    # Per Codex P1-B harden D6: generic adapter has no upstream tree; in
    # composition mode the empty tempdir maps wholesale to apps/<extra>/.
    workspace_source_map_single: Mapping[str, str] = _EMPTY_WORKSPACE_MAP
    workspace_source_map_composition: Mapping[str, str] = _EMPTY_WORKSPACE_MAP
    package_workspace_paths: tuple[str, ...] = _EMPTY_PACKAGE_PATHS

    def __init__(self, *, fetcher: Callable[[Path], None] | None = None) -> None:
        # Generic has no upstream so the fetcher kwarg is accepted for
        # interface symmetry with the other adapters but never invoked.
        self._fetcher_override = fetcher

    def scaffold_into(self, tempdir: Path) -> None:
        tempdir.mkdir(parents=True, exist_ok=True)
        return None

    def apply_overlay(self, tempdir: Path) -> None:
        return None


ADAPTER = GenericAdapter()


def assert_adapter_protocol_conformance() -> None:
    if not isinstance(ADAPTER, Adapter):
        raise AdapterScaffoldError(
            reason="adapter_protocol_drift",
            path=None,
            remediation=(
                "GenericAdapter no longer satisfies the `Adapter` Protocol; "
                "check contracts.py for shape changes."
            ),
        )


assert_adapter_protocol_conformance()
