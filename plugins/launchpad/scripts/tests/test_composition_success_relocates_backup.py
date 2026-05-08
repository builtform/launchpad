"""v2.1 Codex PR #50 cycle 6 F8: composition success-path atomically relocates
backups to `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>/`.

Cycle 5's `shutil.rmtree` cleanup PERMANENTLY DELETED user code on brownfield
runs. Cycle 6 replaces deletion with atomic relocation; this test asserts the
relocation contract directly via `_relocate_backups_to_launchpad`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import (
    _backup_existing_target,
    _relocate_backups_to_launchpad,
)


def _seed_target(composition_root: Path, relpath: str, content: str) -> Path:
    target = composition_root / relpath
    target.mkdir(parents=True)
    (target / "user-file.txt").write_text(content, encoding="utf-8")
    return target


def test_relocate_returns_none_when_backups_empty(tmp_path: Path) -> None:
    """T1-6 + DA-F8.6: greenfield path produces no backup dir entry."""
    composition_root = tmp_path / "project"
    composition_root.mkdir()
    final = _relocate_backups_to_launchpad([], composition_root)
    assert final is None
    backups_root = composition_root / ".launchpad" / "backups"
    assert not backups_root.exists()


def test_relocate_moves_backup_to_launchpad_backups(tmp_path: Path) -> None:
    """DA-F8.1+DA-F8.3+DA-F8.5: success-path atomic relocation contract.

      1. Original `.pre-composition-<sha8>/` does NOT exist after relocation
      2. `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>/` exists with
         user content byte-identical to pre-relocation source
      3. `_manifest.json` present with required schema fields
      4. Mode 0o700 on the per-operation backup subdir (T2-5)
    """
    composition_root = tmp_path / "project"
    composition_root.mkdir()
    target = _seed_target(composition_root, "apps/app", "USER DATA — DO NOT LOSE")
    backup = _backup_existing_target(target, composition_root)
    assert backup is not None
    assert backup.exists()
    assert not target.exists()

    # Simulate the rest of compose() — new scaffold materialized at target.
    target.mkdir()
    (target / "new-scaffold.txt").write_text("new content", encoding="utf-8")

    final = _relocate_backups_to_launchpad([(target, backup)], composition_root)
    assert final is not None

    # 1. Original `.pre-composition-<sha8>/` is gone
    assert not backup.exists()

    # 2. Final backup dir contains the relpath subtree
    relocated = final / "apps" / "app" / "user-file.txt"
    assert relocated.is_file()
    assert relocated.read_text(encoding="utf-8") == "USER DATA — DO NOT LOSE"

    # 3. Manifest schema check
    manifest_path = final / "_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert "created_at" in manifest
    assert "composition_run_id" in manifest
    assert manifest["caller"] == "/lp-scaffold-stack"
    assert "plugin_version" in manifest
    assert isinstance(manifest["targets"], list)
    assert len(manifest["targets"]) == 1
    entry = manifest["targets"][0]
    assert entry["original_path"] == "apps/app"
    assert entry["file_count"] == 1
    assert entry["size_bytes"] > 0

    # 4. Mode 0o700 preserved across the atomic-rename commit
    assert (os.stat(final).st_mode & 0o777) == 0o700

    # 5. New scaffold at original target untouched
    assert (target / "new-scaffold.txt").is_file()
    assert not (target / "user-file.txt").exists()


def test_relocate_handles_multi_target(tmp_path: Path) -> None:
    """Multi-target relocation places each under its own relpath subdir
    and the manifest enumerates both."""
    composition_root = tmp_path / "project"
    composition_root.mkdir()
    target1 = _seed_target(composition_root, "apps/app", "content-1")
    target2 = _seed_target(composition_root, "packages/auth", "content-2")
    backup1 = _backup_existing_target(target1, composition_root)
    backup2 = _backup_existing_target(target2, composition_root)
    assert backup1 is not None and backup2 is not None
    target1.mkdir()
    target2.mkdir()

    final = _relocate_backups_to_launchpad(
        [(target1, backup1), (target2, backup2)], composition_root,
    )
    assert final is not None
    assert (final / "apps" / "app" / "user-file.txt").read_text(
        encoding="utf-8"
    ) == "content-1"
    assert (final / "packages" / "auth" / "user-file.txt").read_text(
        encoding="utf-8"
    ) == "content-2"
    manifest = json.loads((final / "_manifest.json").read_text(encoding="utf-8"))
    relpaths = sorted(t["original_path"] for t in manifest["targets"])
    assert relpaths == ["apps/app", "packages/auth"]
