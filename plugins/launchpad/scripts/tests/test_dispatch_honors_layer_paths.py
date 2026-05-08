"""Verify dispatch_by_stack_ids honors layer path allocations.

Phase 2 (cycle 5 F2 P1): the validated layers[].path allocation must
flow through dispatch to adapter placement. Custom paths must produce
files at the user-specified locations, not the adapter's hardcoded
defaults.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_scaffold_stack.v21_adapter_dispatch import (
    _build_workspace_path_overrides,
    dispatch_single_adapter,
)
from plugin_stack_adapters.contracts import (
    _EMPTY_PACKAGE_PATHS,
    _EMPTY_WORKSPACE_MAP,
)


class _StubAdapter:
    """Minimal adapter that writes marker files into workspace dirs."""

    stack_id = "nextjs_fastapi"
    upstream = None
    manifest_schema_version = "1.0"
    workspace_name = "app"
    unwrap_strategy = "none"
    composes_with: dict = {}
    workspace_source_map_single: Mapping[str, str] = MappingProxyType({
        "app": "app",
        "api": "api",
    })
    workspace_source_map_composition: Mapping[str, str] = _EMPTY_WORKSPACE_MAP
    package_workspace_paths: tuple[str, ...] = _EMPTY_PACKAGE_PATHS
    additional_workspaces: tuple[str, ...] = ("api",)
    layer_stack_to_workspace: dict[str, str] = {
        "next": "app",
        "fastapi": "api",
    }

    def scaffold_into(self, tempdir: Path) -> None:
        (tempdir / "app").mkdir(parents=True, exist_ok=True)
        (tempdir / "app" / "index.ts").write_text("// next app")
        (tempdir / "api").mkdir(parents=True, exist_ok=True)
        (tempdir / "api" / "main.py").write_text("# fastapi api")

    def apply_overlay(self, tempdir: Path) -> None:
        pass


class TestBuildWorkspacePathOverrides:
    def test_returns_empty_when_no_layer_paths(self) -> None:
        adapter = _StubAdapter()
        assert _build_workspace_path_overrides(adapter, None) == {}

    def test_maps_stack_ids_to_workspace_names(self) -> None:
        adapter = _StubAdapter()
        overrides = _build_workspace_path_overrides(
            adapter, {"next": "apps/web", "fastapi": "services/api"},
        )
        assert overrides == {"app": "apps/web", "api": "services/api"}

    def test_partial_override(self) -> None:
        adapter = _StubAdapter()
        overrides = _build_workspace_path_overrides(
            adapter, {"next": "apps/web"},
        )
        assert overrides == {"app": "apps/web"}
        assert "api" not in overrides


class TestDispatchHonorsLayerPaths:
    def test_custom_paths_materialize_at_specified_locations(
        self, tmp_path: Path,
    ) -> None:
        adapter = _StubAdapter()
        layer_paths = {"next": "apps/web", "fastapi": "services/api"}
        dispatch_single_adapter(
            adapter, tmp_path, layer_paths=layer_paths,
        )
        assert (tmp_path / "apps" / "web" / "index.ts").exists()
        assert (tmp_path / "services" / "api" / "main.py").exists()
        assert not (tmp_path / "apps" / "app").exists()
        assert not (tmp_path / "apps" / "api").exists()

    def test_default_paths_when_no_overrides(self, tmp_path: Path) -> None:
        adapter = _StubAdapter()
        dispatch_single_adapter(adapter, tmp_path)
        assert (tmp_path / "apps" / "app" / "index.ts").exists()
        assert (tmp_path / "apps" / "api" / "main.py").exists()
