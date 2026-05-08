"""Composition placement structural tests (Codex PR #50 P1-B harden Slice D §1).

Asserts the actual sibling `apps/<workspace>/` structure for every
composable pair, plus the security/idempotency invariants from
P1-α/β/γ/ε/θ + P2-δ + P3-ν. Replaces the lenient `is_dir()`-only
assertions in `test_composition_wrapper_pair_matrix.py` with strict
file-existence checks.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest

from plugin_stack_adapters.astro import AstroAdapter
from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
    CompositionResult,
    TMP_PARENT_DIRNAME,
    compose,
    resolve_workspace_allocation,
)
from plugin_stack_adapters.contracts import (
    Adapter,
    AdapterScaffoldError,
    UnwrapStrategy,
    UpstreamTemplate,
)
from plugin_stack_adapters.generic import GenericAdapter
from plugin_stack_adapters.nextjs_fastapi import NextjsFastapiAdapter
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter

pytestmark = pytest.mark.slow


# ----------------------- synthetic in-memory fetchers ------------------------
# Per harden P3-ε: synthetic in-memory fetcher fixtures passed via `fetcher=`
# adapter constructor override (NOT real `template_cache.fetch` network calls).


def _next_forge_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "next-forge", "engines": {"node": ">=20"}}\n',
        "turbo.json": b'{"tasks": {"build": {}}}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "apps/*"\n  - "packages/*"\n',
        "apps/app/package.json": b'{"name": "app"}\n',
        "apps/app/middleware.ts": b'export default () => null;\n',
        "packages/auth/package.json": b'{"name": "@repo/auth"}\n',
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _vinta_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "vinta-template"}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "app"\n',
        "app/package.json": b'{"name": "frontend"}\n',
        "app/pages/index.tsx": b'export default () => null;\n',
        "api/main.py": b"app = 'fastapi'\n",
        "api/requirements.txt": b"fastapi==0.115.0\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _astro_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "starlight"}\n',
        "src/content/docs/index.md": b"# docs\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


# -------------------- per-pair structural assertions ----------------------


def test_compose_nextjs_standalone_plus_astro_sibling_apps(
    tmp_path: Path, cache_root_tmp: Path
):
    """Pair: nextjs_standalone + astro.

    Strict: composition_root/apps/app/ (lifted from upstream apps/app),
    composition_root/apps/content/ (whole astro tempdir),
    composition_root/packages/auth/ (lifted from upstream packages).
    """
    project = tmp_path / "project"
    compose(
        [
            NextjsStandaloneAdapter(fetcher=_next_forge_tree),
            AstroAdapter(sub_template_id="docs", fetcher=_astro_tree),
        ],
        project,
    )
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "content" / "package.json").is_file()
    assert (project / "packages" / "auth" / "package.json").is_file()
    # Strict: NO double-nesting.
    assert not (project / "apps" / "app" / "apps").exists()


def test_compose_nextjs_standalone_plus_nextjs_fastapi_three_workspaces(
    tmp_path: Path, cache_root_tmp: Path
):
    """Pair: nextjs_standalone + nextjs_fastapi.

    Strict: app-fe (renamed primary), app (fastapi primary), api
    (fastapi additional). packages/ lifted from nextjs_standalone.
    """
    project = tmp_path / "project"
    compose(
        [
            NextjsStandaloneAdapter(fetcher=_next_forge_tree),
            NextjsFastapiAdapter(fetcher=_vinta_tree),
        ],
        project,
    )
    assert (project / "apps" / "app-fe" / "package.json").is_file()
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "api" / "main.py").is_file()
    assert (project / "packages" / "auth" / "package.json").is_file()


def test_compose_nextjs_fastapi_plus_astro_lays_three_workspaces(
    tmp_path: Path, cache_root_tmp: Path
):
    """Pair: nextjs_fastapi + astro. Strict: app/ + api/ + content/."""
    project = tmp_path / "project"
    compose(
        [
            NextjsFastapiAdapter(fetcher=_vinta_tree),
            AstroAdapter(sub_template_id="docs", fetcher=_astro_tree),
        ],
        project,
    )
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "api" / "main.py").is_file()
    assert (project / "apps" / "content" / "package.json").is_file()


def test_compose_nextjs_standalone_plus_generic_sibling_apps(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    compose(
        [
            NextjsStandaloneAdapter(fetcher=_next_forge_tree),
            GenericAdapter(),
        ],
        project,
    )
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "extra").is_dir()
    assert (project / "packages" / "auth" / "package.json").is_file()


# ---------------------- security: P1-β symlink rejection -----------------


class _EvilSymlinkAdapter:
    """Synthetic adapter that plants a symlink directly in its tempdir to
    exercise the placement-boundary symlink rejection. Bypasses the
    template_cache because shutil.copytree dereferences symlinks at
    copy time, which would obscure the test signal.
    """

    stack_id: str = "nextjs_standalone"  # closed-enum slot
    upstream: UpstreamTemplate | None = None
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = "app"
    unwrap_strategy: UnwrapStrategy = "nested_turborepo"
    composes_with: dict = {}
    additional_workspaces: tuple[str, ...] = ()
    workspace_source_map_single: dict = {}
    workspace_source_map_composition: dict = {"app": "apps/app"}
    package_workspace_paths: tuple[str, ...] = ()

    def __init__(self, *, link_outside: Path) -> None:
        self._link_outside = link_outside

    def scaffold_into(self, tempdir: Path) -> None:
        tempdir.mkdir(parents=True, exist_ok=True)
        (tempdir / "apps" / "app").mkdir(parents=True, exist_ok=True)
        (tempdir / "apps" / "app" / "package.json").write_bytes(
            b'{"name":"x"}\n'
        )
        os.symlink(
            str(self._link_outside),
            str(tempdir / "apps" / "app" / "evil"),
        )

    def apply_overlay(self, tempdir: Path) -> None:
        return None


def test_compose_rejects_symlink_in_scaffold_tree(tmp_path: Path):
    """Per harden P1-β: symlink under the source subtree raises
    CompositionAbortError(reason='symlink_in_scaffold_tree')."""
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    with pytest.raises(CompositionAbortError) as exc:
        compose([_EvilSymlinkAdapter(link_outside=outside)], project)
    assert exc.value.reason == (
        CompositionRejectionCode.SYMLINK_IN_SCAFFOLD_TREE.value
    )


# -------------- security: P1-α path traversal rejection -----------------


def test_adapter_protocol_rejects_path_traversal_in_workspace_map():
    """Per harden P1-α: import-time validator rejects '..' in adapter
    workspace_source_map values."""
    from plugin_stack_adapters.contracts import _validate_workspace_source_map

    with pytest.raises(ValueError, match="path traversal"):
        _validate_workspace_source_map(
            {"app": "../etc/passwd"},
            field_name="workspace_source_map_composition",
        )


def test_adapter_protocol_rejects_absolute_path_in_workspace_map():
    from plugin_stack_adapters.contracts import _validate_workspace_source_map

    with pytest.raises(ValueError, match="relative POSIX"):
        _validate_workspace_source_map(
            {"app": "/etc/passwd"},
            field_name="workspace_source_map_composition",
        )


# ----------------- P1-γ rollback partial-success ------------------------


def test_compose_rollback_removes_placed_workspaces_on_second_failure(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per harden P1-γ: when adapter B fails after adapter A's placement
    completed, rollback rmtrees A's placed apps/ + packages/ paths.
    """
    project = tmp_path / "project"

    def failing_fetcher(target: Path) -> None:
        raise RuntimeError("simulated upstream failure")

    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    b = AstroAdapter(fetcher=failing_fetcher)
    with pytest.raises(CompositionAbortError):
        compose([a, b], project)
    # Strict: both apps/app and packages/ rolled back.
    apps = project / "apps"
    if apps.exists():
        assert list(apps.iterdir()) == []
    packages = project / "packages"
    assert not packages.exists() or list(packages.iterdir()) == []


# ------------- P2-δ workspace_source_map mismatch validation ------------


class _ExtraKeyAdapter:
    stack_id = "generic"
    upstream = None
    manifest_schema_version = "1.0"
    workspace_name = "extra"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict = {}
    additional_workspaces = ()
    workspace_source_map_single = {}
    # 'bogus' is NOT in {primary='extra'} ∪ additional_workspaces=().
    workspace_source_map_composition = {"bogus": "bogus_path"}
    package_workspace_paths = ()

    def scaffold_into(self, td: Path) -> None:
        td.mkdir(parents=True, exist_ok=True)

    def apply_overlay(self, td: Path) -> None:
        return None


class _MissingKeyAdapter:
    stack_id = "generic"
    upstream = None
    manifest_schema_version = "1.0"
    workspace_name = "primary_ws"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict = {}
    additional_workspaces = ("api",)
    workspace_source_map_single = {}
    # missing key 'api' but additional_workspaces declares it.
    workspace_source_map_composition = {"primary_ws": "primary_ws"}
    package_workspace_paths = ()

    def scaffold_into(self, td: Path) -> None:
        td.mkdir(parents=True, exist_ok=True)

    def apply_overlay(self, td: Path) -> None:
        return None


def test_resolve_workspace_allocation_rejects_extra_source_map_key():
    """Per harden P2-δ: workspace_source_map_composition with key not in
    {primary} ∪ additional_workspaces raises mismatch."""
    with pytest.raises(CompositionAbortError) as exc:
        resolve_workspace_allocation([_ExtraKeyAdapter()])
    assert exc.value.reason == (
        CompositionRejectionCode.WORKSPACE_SOURCE_MAP_MISMATCH.value
    )


def test_resolve_workspace_allocation_rejects_missing_source_map_entry():
    """Per harden P2-δ: additional_workspaces=("api",) with no matching
    workspace_source_map_composition['api'] entry raises mismatch."""
    with pytest.raises(CompositionAbortError) as exc:
        resolve_workspace_allocation([_MissingKeyAdapter()])
    assert exc.value.reason == (
        CompositionRejectionCode.WORKSPACE_SOURCE_MAP_MISMATCH.value
    )


# --------------- P2-θ package_workspace_path collision ------------------


class _PackagesAdapter1:
    stack_id = "nextjs_standalone"
    upstream = None
    manifest_schema_version = "1.0"
    workspace_name = "ws1"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict = {"nextjs_fastapi": {
        "workspace_name": "x", "conflict_policy": {}
    }}
    additional_workspaces = ()
    workspace_source_map_single = {}
    workspace_source_map_composition = {"ws1": "ws1"}
    package_workspace_paths = ("packages",)

    def scaffold_into(self, td: Path) -> None:
        td.mkdir(parents=True, exist_ok=True)
        (td / "ws1").mkdir(parents=True, exist_ok=True)
        (td / "packages").mkdir(parents=True, exist_ok=True)

    def apply_overlay(self, td: Path) -> None:
        return None


class _PackagesAdapter2:
    stack_id = "nextjs_fastapi"
    upstream = None
    manifest_schema_version = "1.0"
    workspace_name = "ws2"
    unwrap_strategy: UnwrapStrategy = "none"
    composes_with: dict = {"nextjs_standalone": {
        "workspace_name": "y", "conflict_policy": {}
    }}
    additional_workspaces = ()
    workspace_source_map_single = {}
    workspace_source_map_composition = {"ws2": "ws2"}
    package_workspace_paths = ("packages",)  # Same as Adapter1 → collision.

    def scaffold_into(self, td: Path) -> None:
        td.mkdir(parents=True, exist_ok=True)
        (td / "ws2").mkdir(parents=True, exist_ok=True)
        (td / "packages").mkdir(parents=True, exist_ok=True)

    def apply_overlay(self, td: Path) -> None:
        return None


def test_compose_rejects_package_workspace_path_collision(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per harden P2-θ: two adapters declaring overlapping
    package_workspace_paths raise PACKAGE_WORKSPACE_PATH_COLLISION."""
    project = tmp_path / "project"
    with pytest.raises(CompositionAbortError) as exc:
        compose([_PackagesAdapter1(), _PackagesAdapter2()], project)
    assert exc.value.reason == (
        CompositionRejectionCode.PACKAGE_WORKSPACE_PATH_COLLISION.value
    )


# ----- P1-δ runtime executability fallback (static glob resolution) ---


def test_compose_nextjs_fastapi_workspace_globs_resolve_to_manifests(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per Codex PR #50 P1-B harden P1-δ Acceptable Degradation: assert
    each declared workspace_source_map_composition target resolves to a
    directory containing a workspace manifest (package.json for Node,
    main.py / requirements.txt for Python).

    This is the static-glob-resolution fallback for `pnpm install` exit
    0: the structural prereqs for a working Turborepo are in place.
    """
    project = tmp_path / "project"
    compose(
        [
            NextjsFastapiAdapter(fetcher=_vinta_tree),
            AstroAdapter(sub_template_id="docs", fetcher=_astro_tree),
        ],
        project,
    )
    # Node workspace manifests under apps/.
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "content" / "package.json").is_file()
    # Python workspace manifest (api).
    api_marker = (
        (project / "apps" / "api" / "main.py").is_file()
        or (project / "apps" / "api" / "requirements.txt").is_file()
    )
    assert api_marker, "apps/api missing both main.py and requirements.txt"


def test_compose_nextjs_standalone_packages_glob_resolves(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per harden P1-δ: the lifted `packages/<n>/` siblings each contain
    a package.json — `pnpm-workspace.yaml`'s `packages/*` glob would
    resolve to ≥1 manifest per the documented fallback."""
    project = tmp_path / "project"
    compose(
        [
            NextjsStandaloneAdapter(fetcher=_next_forge_tree),
            AstroAdapter(sub_template_id="docs", fetcher=_astro_tree),
        ],
        project,
    )
    packages_root = project / "packages"
    assert packages_root.is_dir()
    for child in packages_root.iterdir():
        if child.is_dir():
            assert (child / "package.json").is_file(), (
                f"package workspace {child} missing package.json"
            )
