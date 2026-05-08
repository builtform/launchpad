"""nextjs_fastapi adapter: wrap-and-overlay over vintasoftware/nextjs-fastapi-template.

Phase 4 plan section 2.1 + section 3.3 + section 3.4. The adapter ships a
two-workspace upstream (app/ frontend + api/ backend) and is the only v2.1
adapter that contributes more than one workspace to a composition. The
overlay aligns the upstream scripts/ tree with the LaunchPad scripts/
contract (Phase 3 infrastructure overlay) so the bootstrap manifest and
adapter scripts coexist cleanly.

Wrap-and-overlay flow:
  1. scaffold_into(tempdir): template_cache.fetch returns the cached upstream
     tree; we copy app/ + api/ + supporting top-level files into tempdir.
  2. apply_overlay(tempdir): overlay LaunchPad-aligned scripts/ entries +
     drop upstream app/scripts/ if it conflicts with the LaunchPad layout.

unwrap_strategy is "none" because the upstream is NOT itself a Turborepo;
composition.py copies app/ + api/ subdirs without the nested-Turborepo
hoist that nextjs_standalone uses.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

from .contracts import (
    _EMPTY_PACKAGE_PATHS,
    Adapter,
    AdapterScaffoldError,
    CompositionRule,
    OverlayConfig,
    StackIdActive,
    UnwrapStrategy,
    UpstreamTemplate,
)
from .pin_registry import get_pin

_REPO_URL = "https://github.com/vintasoftware/nextjs-fastapi-template"

_OVERLAY: OverlayConfig = {
    "add": [
        "scripts/compound/.gitkeep",
        "scripts/maintenance/.gitkeep",
        "scripts/agent_hydration/.gitkeep",
    ],
    "replace": [],
    "remove": [],
    "conflict_policy": {
        "package.json": "merge-keys",
        "pnpm-workspace.yaml": "merge-keys",
        ".gitignore": "append-only",
        "lefthook.yml": "merge-keys",
    },
}

_COMPOSES_WITH: dict[StackIdActive, CompositionRule] = {
    "astro": {
        "workspace_name": "content",
        "conflict_policy": {
            "package.json": "merge-keys",
            "pnpm-workspace.yaml": "merge-keys",
            "lefthook.yml": "merge-keys",
        },
    },
    "nextjs_standalone": {
        "workspace_name": "app",
        "conflict_policy": {
            "package.json": "merge-keys",
            "pnpm-workspace.yaml": "merge-keys",
            "turbo.json": "merge-keys",
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


class NextjsFastapiAdapter:
    """Adapter Protocol implementation for vintasoftware/nextjs-fastapi-template."""

    stack_id: StackIdActive = "nextjs_fastapi"
    upstream: UpstreamTemplate | None = {
        "adapter_id": "nextjs_fastapi",
        "sub_template_id": None,
    }
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = "app"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict[StackIdActive, CompositionRule] = _COMPOSES_WITH
    additional_workspaces: tuple[str, ...] = ("api",)
    # Per Codex P1-B harden D2/D3: vintasoftware/nextjs-fastapi-template lays
    # `app/` (Next.js) and `api/` (FastAPI) at upstream root. Both single
    # and composition mode wrap them under `apps/<name>/` siblings so
    # `pnpm-workspace.yaml` globs resolve.
    workspace_source_map_single: Mapping[str, str] = MappingProxyType({
        "app": "app",
        "api": "api",
    })
    workspace_source_map_composition: Mapping[str, str] = MappingProxyType({
        "app": "app",
        "api": "api",
    })
    package_workspace_paths: tuple[str, ...] = _EMPTY_PACKAGE_PATHS
    layer_stack_to_workspace: dict[str, str] = {
        "next": "app",
        "fastapi": "api",
    }

    def __init__(
        self, *, fetcher: Callable[[Path], None] | None = None
    ) -> None:
        self._fetcher_override = fetcher

    def _resolve_pin(self) -> dict:
        pin = get_pin("nextjs_fastapi")
        if pin["repo_url"] != _REPO_URL:
            raise AdapterScaffoldError(
                reason="pin_registry_repo_mismatch",
                path=None,
                remediation=(
                    f"pin_registry repo {pin['repo_url']} does not match "
                    f"adapter constant {_REPO_URL}"
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
                    f"failed to fetch {pin['repo_url']}@{pin['sha'][:8]} into "
                    f"the template cache: {exc}"
                ),
            ) from exc

        tempdir.mkdir(parents=True, exist_ok=True)
        for child in cached.iterdir():
            if child.name in {".ready", ".fetched_at", ".expected_files.json"}:
                continue
            dst = tempdir / child.name
            if child.is_dir():
                shutil.copytree(child, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(child, dst)

    def apply_overlay(self, tempdir: Path) -> None:
        for rel in _OVERLAY["add"]:
            target = tempdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text("", encoding="utf-8")


ADAPTER = NextjsFastapiAdapter()


def assert_adapter_protocol_conformance() -> None:
    if not isinstance(ADAPTER, Adapter):
        raise AdapterScaffoldError(
            reason="adapter_protocol_drift",
            path=None,
            remediation=(
                "NextjsFastapiAdapter no longer satisfies the `Adapter` "
                "Protocol; check contracts.py for shape changes."
            ),
        )


assert_adapter_protocol_conformance()
