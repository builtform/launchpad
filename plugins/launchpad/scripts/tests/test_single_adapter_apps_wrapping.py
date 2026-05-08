"""Single-adapter mode `apps/<workspace>/` wrapping invariants.

Codex PR #50 P1-B harden Slice D §3. Asserts:

  - `nextjs_fastapi` single → `apps/app/` + `apps/api/` siblings AND
    NO `app/` / `api/` at project root.
  - `nextjs_standalone` single → preserves fork-as-project-root
    semantics (next-forge tree at root, NO new apps/ wrap).
  - `ts_monorepo` / `astro` / `generic` single → no apps/ wrapping
    (existing behavior preserved).

Plus security/idempotency/cross-FS subtests from P1-α/β/ε/ζ.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from lp_scaffold_stack.v21_adapter_dispatch import (
    dispatch_single_adapter,
    resolve_adapter,
)
from plugin_stack_adapters.astro import AstroAdapter
from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
)
from plugin_stack_adapters.contracts import ScaffoldStepFailedError
from plugin_stack_adapters.generic import GenericAdapter
from plugin_stack_adapters.nextjs_fastapi import NextjsFastapiAdapter
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter

pytestmark = pytest.mark.slow


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


def _next_forge_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "next-forge"}\n',
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


# ----------- structural invariants per adapter (D3 truth table) ---------


def test_nextjs_fastapi_single_mode_lays_apps_app_and_apps_api(
    tmp_path: Path, cache_root_tmp: Path
):
    """Strict: nextjs_fastapi single → apps/app/ + apps/api/ siblings.
    NO `app/` or `api/` at project root."""
    project = tmp_path / "project"
    adapter = NextjsFastapiAdapter(fetcher=_vinta_tree)
    dispatch_single_adapter(adapter, project)
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "apps" / "app" / "pages" / "index.tsx").is_file()
    assert (project / "apps" / "api" / "main.py").is_file()
    assert (project / "apps" / "api" / "requirements.txt").is_file()
    # Strict: NO duplicate at project root.
    assert not (project / "app").exists()
    assert not (project / "api").exists()


def test_nextjs_standalone_single_mode_preserves_fork_as_project_root(
    tmp_path: Path, cache_root_tmp: Path
):
    """nextjs_standalone single-mode is the next-forge fork-as-project
    case: empty workspace_source_map_single keeps the upstream's own
    apps/+packages/ tree at project root."""
    project = tmp_path / "project"
    adapter = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    dispatch_single_adapter(adapter, project)
    # Fork-as-root: upstream's apps/app/ + packages/ remain at project root.
    assert (project / "apps" / "app" / "package.json").is_file()
    assert (project / "packages" / "auth" / "package.json").is_file()
    assert (project / "turbo.json").is_file()


def test_ts_monorepo_single_mode_no_apps_wrap(tmp_path: Path):
    project = tmp_path / "project"
    dispatch_single_adapter(resolve_adapter("ts_monorepo"), project)
    # ts_monorepo is a no-op; project_root exists but no apps/ created.
    assert project.is_dir()
    assert not (project / "apps").exists()


def test_generic_single_mode_no_apps_wrap(tmp_path: Path):
    project = tmp_path / "project"
    dispatch_single_adapter(resolve_adapter("generic"), project)
    assert project.is_dir()
    assert not (project / "apps").exists()


def test_astro_single_mode_no_apps_wrap(tmp_path: Path, cache_root_tmp: Path):
    """Astro single-mode lays the upstream's package.json at project root,
    NOT under apps/."""
    project = tmp_path / "project"
    adapter = AstroAdapter(sub_template_id="docs", fetcher=_astro_tree)
    dispatch_single_adapter(adapter, project)
    assert (project / "package.json").is_file()
    assert not (project / "apps").exists()


# ----------- P1-ε re-run idempotency: refuse-loud on populated target -----


def test_nextjs_fastapi_single_refuses_loud_when_apps_app_pre_populated(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per harden P1-ε: re-running single-adapter dispatch over an
    existing populated apps/<workspace>/ raises
    workspace_target_already_populated."""
    project = tmp_path / "project"
    apps_app = project / "apps" / "app"
    apps_app.mkdir(parents=True)
    (apps_app / "user-content.txt").write_text("preserved\n", encoding="utf-8")
    adapter = NextjsFastapiAdapter(fetcher=_vinta_tree)
    with pytest.raises(ScaffoldStepFailedError) as exc:
        dispatch_single_adapter(adapter, project)
    assert exc.value.reason == "workspace_target_already_populated"
    # Strict: pre-existing user content preserved.
    assert (apps_app / "user-content.txt").is_file()


def test_nextjs_fastapi_single_succeeds_when_apps_app_empty_dir(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per harden P1-ε: an empty pre-existing apps/<workspace>/ does NOT
    refuse — empty placeholder is treated as benign and replaced."""
    project = tmp_path / "project"
    (project / "apps" / "app").mkdir(parents=True)  # empty placeholder
    adapter = NextjsFastapiAdapter(fetcher=_vinta_tree)
    dispatch_single_adapter(adapter, project)
    assert (project / "apps" / "app" / "package.json").is_file()


# ----------- P1-β symlink rejection on single-adapter path --------------


class _EvilSingleSymlinkAdapter:
    """Synthetic single-mode adapter that plants a symlink directly in
    tempdir to test the single-adapter path's symlink rejection.
    Bypasses template_cache (shutil.copytree dereferences symlinks).
    """

    stack_id: str = "nextjs_fastapi"  # closed-enum slot
    upstream = None
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = "app"
    unwrap_strategy = "none"
    composes_with: dict = {}
    additional_workspaces: tuple[str, ...] = ("api",)
    workspace_source_map_single: dict = {"app": "app", "api": "api"}
    workspace_source_map_composition: dict = {"app": "app", "api": "api"}
    package_workspace_paths: tuple[str, ...] = ()

    def __init__(self, *, link_outside: Path) -> None:
        self._link_outside = link_outside

    def scaffold_into(self, tempdir: Path) -> None:
        tempdir.mkdir(parents=True, exist_ok=True)
        (tempdir / "app").mkdir(parents=True, exist_ok=True)
        (tempdir / "app" / "package.json").write_bytes(b'{"name":"x"}\n')
        os.symlink(str(self._link_outside), str(tempdir / "app" / "evil"))
        (tempdir / "api").mkdir(parents=True, exist_ok=True)
        (tempdir / "api" / "main.py").write_bytes(b"\n")

    def apply_overlay(self, tempdir: Path) -> None:
        return None


def test_nextjs_fastapi_single_rejects_symlink_in_app_subtree(
    tmp_path: Path,
):
    """Per harden P1-β: symlink under tempdir/app/ raises
    symlink_in_scaffold_tree on the single-adapter dispatch path."""
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    adapter = _EvilSingleSymlinkAdapter(link_outside=outside)
    with pytest.raises(CompositionAbortError) as exc:
        dispatch_single_adapter(adapter, project)
    assert exc.value.reason == (
        CompositionRejectionCode.SYMLINK_IN_SCAFFOLD_TREE.value
    )


# ------------- P1-ζ tempdir uses .lp-tmp/ not .tmp/ ---------------------


def test_nextjs_fastapi_single_tempdir_dropped_after_success(
    tmp_path: Path, cache_root_tmp: Path
):
    """Per harden P1-ζ + P2-ε: after successful single-adapter dispatch,
    `.lp-tmp/` is fully cleaned up (no leftover tempdirs).
    """
    project = tmp_path / "project"
    adapter = NextjsFastapiAdapter(fetcher=_vinta_tree)
    dispatch_single_adapter(adapter, project)
    lp_tmp = project / ".lp-tmp"
    if lp_tmp.exists():
        leftover = list(lp_tmp.iterdir())
        assert leftover == [], f"single-adapter leaked tempdirs: {leftover}"
