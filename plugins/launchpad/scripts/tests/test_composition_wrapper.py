"""Composition wrapper sequential render + rollback tests.

Phase 4 plan section 3.6 + section 2.2 row. Covers the sequential render +
rollback + same-FS contract; both canonical hot-paths are smoke-tested in
Slice H.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pytest

from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionResult,
    compose,
    resolve_workspace_allocation,
)
from plugin_stack_adapters.contracts import StackIdActive
from plugin_stack_adapters.generic import GenericAdapter
from plugin_stack_adapters.nextjs_fastapi import NextjsFastapiAdapter
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter
from plugin_stack_adapters.astro import AstroAdapter

pytestmark = pytest.mark.slow


def _next_forge_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "next-forge"}\n',
        "turbo.json": b'{"tasks": {}}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "apps/*"\n',
        "apps/app/package.json": b'{"name": "app"}\n',
        "apps/app/middleware.ts": b'export default () => null;\n',
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _vinta_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "vinta"}\n',
        "app/package.json": b'{"name": "frontend"}\n',
        "api/main.py": b"app = 'fastapi'\n",
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


def test_compose_single_nextjs_standalone_places_under_apps(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    adapter = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    result = compose([adapter], project)
    assert isinstance(result, CompositionResult)
    assert (project / "apps" / "app").is_dir()
    assert (project / "apps" / "app" / "package.json").is_file()


def test_compose_writes_no_residual_tmp_dirs(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    adapter = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    compose([adapter], project)
    tmp_root = project / ".lp-tmp"
    leftover = list(tmp_root.iterdir()) if tmp_root.exists() else []
    assert leftover == [], f"composition leaked tmp dirs: {leftover}"


def test_compose_two_adapters_lays_down_both_workspaces(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    b = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    result = compose([a, b], project)
    assert "app" in result.workspaces
    assert "content" in result.workspaces
    assert (project / "apps" / "app").is_dir()
    assert (project / "apps" / "content").is_dir()


def test_compose_canonical_pair_nextjs_standalone_plus_astro(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    result = compose(
        [
            NextjsStandaloneAdapter(fetcher=_next_forge_tree),
            AstroAdapter(sub_template_id="docs", fetcher=_astro_tree),
        ],
        project,
    )
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "content" / "package.json").is_file()
    assert len(result.placed_paths) == 2


def test_compose_canonical_pair_nextjs_standalone_plus_nextjs_fastapi_app_collision(
    tmp_path: Path, cache_root_tmp: Path, caplog
):
    project = tmp_path / "project"
    with caplog.at_level(
        logging.INFO, logger="plugin_stack_adapters.composition"
    ):
        result = compose(
            [
                NextjsStandaloneAdapter(fetcher=_next_forge_tree),
                NextjsFastapiAdapter(fetcher=_vinta_tree),
            ],
            project,
        )
    assert "app-fe" in result.workspaces
    assert "api" in result.workspaces
    assert (project / "apps" / "app-fe").is_dir()
    assert any(
        "Renamed first 'app' workspace to 'app-fe'" in rec.getMessage()
        for rec in caplog.records
    )


def test_compose_rolls_back_on_second_adapter_failure(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    failing_called = {"n": 0}

    def failing_fetcher(target: Path) -> None:
        failing_called["n"] += 1
        raise RuntimeError("simulated upstream failure")

    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    b = AstroAdapter(fetcher=failing_fetcher)

    with pytest.raises(CompositionAbortError):
        compose([a, b], project)

    apps = project / "apps"
    if apps.exists():
        leftover = list(apps.iterdir())
        assert leftover == [], (
            f"composition placed workspaces despite rollback: {leftover}"
        )
    tmp_root = project / ".lp-tmp"
    if tmp_root.exists():
        leftover_tmp = list(tmp_root.iterdir())
        assert leftover_tmp == [], (
            f"composition leaked rendered tempdirs: {leftover_tmp}"
        )


def test_compose_secrets_warning_logs_on_rollback_rmtree_failure(
    tmp_path: Path, cache_root_tmp: Path, caplog, monkeypatch
):
    project = tmp_path / "project"

    import shutil as _shutil

    original_rmtree = _shutil.rmtree

    def flaky_rmtree(path, *args, **kwargs):
        # Fail only on the composition tempdir for the first adapter so the
        # rollback path triggers the secrets-warning log; the cache layer
        # cleanup of its own .tmp.<uuid> dirs falls through to the real
        # rmtree.
        if "lp-nextjs_standalone-" in str(path):
            raise OSError("simulated cleanup failure")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(
        "plugin_stack_adapters.composition.shutil.rmtree", flaky_rmtree
    )

    def failing_fetcher(target: Path) -> None:
        raise RuntimeError("boom")

    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    b = AstroAdapter(fetcher=failing_fetcher)

    with caplog.at_level(
        logging.ERROR, logger="plugin_stack_adapters.composition"
    ):
        with pytest.raises(CompositionAbortError):
            compose([a, b], project)

    assert any(
        "secrets" in rec.getMessage().lower()
        for rec in caplog.records
    ), [r.getMessage() for r in caplog.records]


def test_compose_atomically_places_workspaces_via_os_replace(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    adapter = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    compose([adapter], project)
    workspace = project / "apps" / "content"
    assert workspace.is_dir()
    # Empty .tmp/ after placement implies os.replace ran (rename, not copy).
    tmp_root = project / ".lp-tmp"
    if tmp_root.exists():
        assert list(tmp_root.iterdir()) == []


def test_compose_replaces_existing_workspace_directory(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    apps = project / "apps" / "content"
    apps.mkdir(parents=True)
    (apps / "stale.txt").write_text("stale\n", encoding="utf-8")

    adapter = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    compose([adapter], project)

    assert not (apps / "stale.txt").exists()
    assert (apps / "package.json").is_file()


def test_resolve_workspace_allocation_two_distinct_workspaces():
    a = NextjsStandaloneAdapter()
    b = AstroAdapter()
    mapping, logs = resolve_workspace_allocation([a, b])
    assert "app" in mapping
    assert "content" in mapping
    assert logs == []


def test_resolve_workspace_allocation_collision_renames_first_to_app_fe():
    a = NextjsStandaloneAdapter()
    b = NextjsFastapiAdapter()
    mapping, logs = resolve_workspace_allocation([a, b])
    assert "app-fe" in mapping
    assert "app" in mapping
    assert "api" in mapping
    assert any("app-fe" in m for m in logs)


def test_resolve_workspace_allocation_three_workspaces_for_fastapi_plus_astro():
    a = NextjsFastapiAdapter()
    b = AstroAdapter()
    mapping, logs = resolve_workspace_allocation([a, b])
    assert {"app", "api", "content"}.issubset(mapping.keys())
    assert logs == []


def test_compose_canonical_hot_path_two_workspaces_for_fastapi_plus_astro(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    result = compose(
        [
            NextjsFastapiAdapter(fetcher=_vinta_tree),
            AstroAdapter(sub_template_id="docs", fetcher=_astro_tree),
        ],
        project,
    )
    workspaces = set(result.workspaces.keys())
    assert {"app", "api", "content"}.issubset(workspaces)


def test_compose_returns_composition_result_with_placed_paths(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    b = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    result = compose([a, b], project)
    assert len(result.placed_paths) == 2
    for p in result.placed_paths:
        assert p.exists()
        assert p.parent.name == "apps"


def test_compose_creates_apps_root_under_composition_root(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project-fresh"
    adapter = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    compose([adapter], project)
    assert (project / "apps").is_dir()


def test_compose_writes_workspace_dir_when_workspace_name_set():
    a = NextjsStandaloneAdapter()
    assert a.workspace_name == "app"
    b = AstroAdapter()
    assert b.workspace_name == "content"
    c = NextjsFastapiAdapter()
    assert c.workspace_name == "app"
    d = GenericAdapter()
    assert d.workspace_name == "extra"
