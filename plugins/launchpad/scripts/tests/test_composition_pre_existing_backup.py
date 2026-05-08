"""v2.1 Codex PR #50 post-review P0 regression: composition pre-existing target backup.

Asserts that pre-existing `apps/<workspace>/` and package directories
are preserved via `.pre-composition-<sha8>/` backup-rename when
composition placement fails, so user data is never lost on rerun /
brownfield root composition.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plugin_stack_adapters.astro import AstroAdapter
from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
    _backup_existing_target,
    _pre_composition_backup_path,
    compose,
)
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter

pytestmark = pytest.mark.slow


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


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


def test_pre_composition_backup_path_is_deterministic(tmp_path):
    """Backup path is sibling of target with sha8(relpath) suffix."""
    composition_root = tmp_path
    target = composition_root / "apps" / "web"
    target.mkdir(parents=True)
    backup = _pre_composition_backup_path(target, composition_root)
    sha8 = hashlib.sha256(b"apps/web").hexdigest()[:8]
    assert backup.name == f"web.pre-composition-{sha8}"
    assert backup.parent == target.parent


def test_backup_existing_target_renames_atomically(tmp_path):
    composition_root = tmp_path
    target = composition_root / "apps" / "web"
    target.mkdir(parents=True)
    (target / "user-file.txt").write_text("user data\n", encoding="utf-8")

    backup = _backup_existing_target(target, composition_root)
    assert backup is not None
    assert not target.exists()
    assert backup.is_dir()
    assert (backup / "user-file.txt").read_text(encoding="utf-8") == "user data\n"


def test_backup_existing_target_returns_none_when_target_absent(tmp_path):
    composition_root = tmp_path
    target = composition_root / "apps" / "web"
    backup = _backup_existing_target(target, composition_root)
    assert backup is None


def test_backup_existing_target_refuses_stale_backup(tmp_path):
    composition_root = tmp_path
    target = composition_root / "apps" / "web"
    target.mkdir(parents=True)
    (target / "user-file.txt").write_text("user data\n", encoding="utf-8")
    # Simulate a stale backup from a prior crashed run.
    stale_backup = _pre_composition_backup_path(target, composition_root)
    stale_backup.mkdir(parents=True)
    (stale_backup / "stale.txt").write_text("stale\n", encoding="utf-8")

    with pytest.raises(CompositionAbortError) as exc_info:
        _backup_existing_target(target, composition_root)
    assert exc_info.value.reason == (
        CompositionRejectionCode.STALE_PRE_COMPOSITION_BACKUP.value
    )
    # User data still on disk untouched.
    assert (target / "user-file.txt").read_text(encoding="utf-8") == "user data\n"


def test_compose_failure_restores_pre_existing_apps_web(
    tmp_path: Path, cache_root_tmp: Path,
):
    """End-to-end: pre-existing apps/web/user-file.txt is preserved when
    composition placement fails mid-write. Asserts the user's data is
    NOT lost on a rerun where the second adapter raises."""
    project = tmp_path / "project"
    apps_web = project / "apps" / "app"
    apps_web.mkdir(parents=True)
    (apps_web / "user-file.txt").write_text("USER DATA — DO NOT LOSE\n", encoding="utf-8")
    (apps_web / "important.md").write_text("important\n", encoding="utf-8")

    def failing_fetcher(target: Path) -> None:
        raise RuntimeError("simulated upstream failure post-A-placement")

    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    b = AstroAdapter(fetcher=failing_fetcher)

    with pytest.raises(CompositionAbortError):
        compose([a, b], project)

    # P0 regression assertion: user's pre-existing files MUST survive
    # the failed composition. Rollback restored apps/app from the
    # .pre-composition-<sha8> backup.
    assert apps_web.is_dir()
    user_file = apps_web / "user-file.txt"
    assert user_file.is_file(), (
        f"P0 regression: user-file.txt was lost during failed composition. "
        f"apps/app contents: {list(apps_web.iterdir())}"
    )
    assert user_file.read_text(encoding="utf-8") == "USER DATA — DO NOT LOSE\n"
