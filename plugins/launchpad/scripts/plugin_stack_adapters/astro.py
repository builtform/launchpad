"""Astro adapter: 3 sub-templates (docs / blog / marketing) over withastro repos.

Phase 4 plan section 2.1 + section 3.1 + section 3.3. Replaces the legacy
`astro_adapter.py` from v2.0; the legacy `run() -> AdapterOutput` surface is
preserved here for the polyglot composer + plugin-doc-generator. The new
v2.1 surface is the `Adapter` Protocol + a sub-template selector.

Sub-templates (Phase 4 plan section 3.1):
  - docs       -> withastro/starlight@<sha>           (8.4k stars, MIT)
  - blog       -> withastro/astro@<sha>/examples/blog (parent ~51k stars, MIT)
  - marketing  -> withastro/astro@<sha>/examples/portfolio (1.1k stars, MIT)

Per harden P0.2: scaffolder method is `git_clone_depth_1` (NOT `npm_create`).
The cache fetches the upstream repo; the adapter copies the relevant
sub-tree (root for Starlight; `examples/<variant>/` for Astro examples).

Composition mode silent default: `marketing` plus an INFO log per section
3.12 verbatim catalog. "No opt-out" route to `generic` lives in
`select_sub_template_or_decline` and is consumed by lp_pick_stack /
composition.py rather than this adapter.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable, Literal

from .contracts import (
    Adapter,
    AdapterOutput,
    AdapterScaffoldError,
    AppFlowInfo,
    BackendInfo,
    CommandsConfig,
    CompositionRule,
    FrontendInfo,
    OverlayConfig,
    PipelineOverrides,
    ProductContextInfo,
    StackIdActive,
    TechStackInfo,
    UnwrapStrategy,
    UpstreamTemplate,
)
from .pin_registry import get_pin

LOG = logging.getLogger("plugin_stack_adapters.astro")

AstroSubTemplate = Literal["docs", "blog", "marketing"]
_SUB_TEMPLATES: tuple[AstroSubTemplate, ...] = ("docs", "blog", "marketing")
_DEFAULT_SUB_TEMPLATE: AstroSubTemplate = "marketing"

# Map from sub-template id to the on-cache path within the cached repo tree.
# For Starlight the sub-tree is the cache root; for Astro examples the
# sub-tree is examples/blog or examples/portfolio.
_SUB_PATHS: dict[AstroSubTemplate, str] = {
    "docs": "",
    "blog": "examples/blog",
    "marketing": "examples/portfolio",
}

_OVERLAY: OverlayConfig = {
    "add": [],
    "replace": [],
    "remove": [],
    "conflict_policy": {
        "package.json": "merge-keys",
        ".gitignore": "append-only",
    },
}

_COMPOSES_WITH: dict[StackIdActive, CompositionRule] = {
    "nextjs_standalone": {
        "workspace_name": "app",
        "conflict_policy": {
            "package.json": "merge-keys",
            "lefthook.yml": "merge-keys",
        },
    },
    "nextjs_fastapi": {
        "workspace_name": "app",
        "conflict_policy": {
            "package.json": "merge-keys",
            "lefthook.yml": "merge-keys",
        },
    },
    "generic": {
        "workspace_name": "extra",
        "conflict_policy": {
            "package.json": "merge-keys",
        },
    },
}


def select_sub_template_or_decline(
    *,
    user_choice: str | None,
    interactive: bool,
    composition_mode: bool,
    hints: dict[str, bool] | None = None,
) -> AstroSubTemplate | None:
    """Resolve the Astro sub-template selection per Phase 4 §3.1 + §3.12.

    Returns:
      - One of `_SUB_TEMPLATES` for an Astro scaffold.
      - `None` for "no opt-out" route to the generic adapter (verbatim INFO
        log "declined Astro sub-templates; using generic fallback" per
        §3.12).

    Composition mode is always silent default = `marketing` (regardless of
    interactive flag) per harden spec-flow P1-C resolution.
    """
    if composition_mode:
        LOG.info(
            "Astro defaulted to %s (composition mode); no override flag in "
            "v2.1, file v2.2 issue if needed.",
            _DEFAULT_SUB_TEMPLATE,
        )
        return _DEFAULT_SUB_TEMPLATE

    if user_choice is not None:
        if user_choice == "generic-fallback":
            LOG.info("declined Astro sub-templates; using generic fallback")
            return None
        if user_choice in _SUB_TEMPLATES:
            return user_choice  # type: ignore[return-value]
        # unrecognized user choice -> treat as decline
        LOG.info("declined Astro sub-templates; using generic fallback")
        return None

    if not interactive:
        return _DEFAULT_SUB_TEMPLATE

    if hints:
        if hints.get("docs"):
            return "docs"
        if hints.get("blog"):
            return "blog"
    return _DEFAULT_SUB_TEMPLATE


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


class AstroAdapter:
    """Adapter Protocol implementation for Astro (3 sub-templates)."""

    stack_id: StackIdActive = "astro"
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = "content"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict[StackIdActive, CompositionRule] = _COMPOSES_WITH

    def __init__(
        self,
        *,
        sub_template_id: AstroSubTemplate = _DEFAULT_SUB_TEMPLATE,
        fetcher: Callable[[Path], None] | None = None,
    ) -> None:
        if sub_template_id not in _SUB_TEMPLATES:
            raise AdapterScaffoldError(
                reason="invalid_astro_sub_template",
                path=None,
                remediation=(
                    f"sub_template_id {sub_template_id!r} not in "
                    f"{_SUB_TEMPLATES!r}"
                ),
            )
        self.sub_template_id: AstroSubTemplate = sub_template_id
        self.upstream: UpstreamTemplate | None = {
            "adapter_id": "astro",
            "sub_template_id": sub_template_id,
        }
        self._fetcher_override = fetcher

    def _resolve_pin(self) -> dict:
        pin = get_pin("astro", self.sub_template_id)
        if pin["license"] != "MIT":
            raise AdapterScaffoldError(
                reason="astro_license_drift",
                path=None,
                remediation=(
                    f"astro/{self.sub_template_id} license is "
                    f"{pin['license']!r}; expected MIT"
                ),
            )
        return pin

    def scaffold_into(self, tempdir: Path) -> None:
        pin = self._resolve_pin()
        from template_cache import fetch

        try:
            cached = fetch(
                pin["repo_url"], pin["sha"], fetcher=self._fetcher_override
            )
        except Exception as exc:
            raise AdapterScaffoldError(
                reason="template_cache_fetch_failed",
                path=tempdir,
                remediation=(
                    f"failed to fetch {pin['repo_url']}@{pin['sha'][:8]} "
                    f"(astro/{self.sub_template_id}) into the template "
                    f"cache: {exc}"
                ),
            ) from exc

        sub_path = _SUB_PATHS[self.sub_template_id]
        source_root = cached / sub_path if sub_path else cached
        if not source_root.is_dir():
            raise AdapterScaffoldError(
                reason="astro_sub_template_path_missing",
                path=source_root,
                remediation=(
                    f"sub-template path {sub_path!r} not found inside the "
                    f"cached upstream tree at {cached}"
                ),
            )

        tempdir.mkdir(parents=True, exist_ok=True)
        for child in source_root.iterdir():
            if child.name in {".ready", ".fetched_at", ".expected_files.json"}:
                continue
            dst = tempdir / child.name
            if child.is_dir():
                shutil.copytree(child, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(child, dst)

    def apply_overlay(self, tempdir: Path) -> None:
        return None


ADAPTER = AstroAdapter()


def assert_adapter_protocol_conformance() -> None:
    if not isinstance(ADAPTER, Adapter):
        raise AdapterScaffoldError(
            reason="adapter_protocol_drift",
            path=None,
            remediation=(
                "AstroAdapter no longer satisfies the `Adapter` Protocol; "
                "check contracts.py for shape changes."
            ),
        )


assert_adapter_protocol_conformance()
