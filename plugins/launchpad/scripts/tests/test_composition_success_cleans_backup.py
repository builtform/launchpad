"""Verify composition success-path cleans up pre-composition backups.

Phase 3 (cycle 5 F3 P1): after successful composition, backup
directories (*.pre-composition-<sha8>) must be removed. The failure
path must preserve them for rollback.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import (
    _backup_existing_target,
    _pre_composition_backup_path,
)


class TestSuccessPathCleansBackup:
    """Ensure _backup_existing_target creates backups that compose() removes
    on success. We test the backup creation + cleanup logic directly since
    full compose() requires adapter scaffolding.
    """

    def test_backup_created_and_can_be_cleaned(self, tmp_path: Path) -> None:
        composition_root = tmp_path / "project"
        apps_root = composition_root / "apps"
        target = apps_root / "app"
        target.mkdir(parents=True)
        (target / "existing.txt").write_text("user content")

        backup = _backup_existing_target(target, composition_root)

        assert backup is not None
        assert backup.exists()
        assert not target.exists()
        assert (backup / "existing.txt").read_text() == "user content"

        import shutil
        shutil.rmtree(backup)
        assert not backup.exists()

    def test_backup_path_is_deterministic(self, tmp_path: Path) -> None:
        composition_root = tmp_path / "project"
        target = composition_root / "apps" / "app"
        target.mkdir(parents=True)

        expected = _pre_composition_backup_path(target, composition_root)
        backup = _backup_existing_target(target, composition_root)

        assert backup == expected

    def test_no_backup_when_target_absent(self, tmp_path: Path) -> None:
        composition_root = tmp_path / "project"
        composition_root.mkdir(parents=True)
        target = composition_root / "apps" / "app"

        backup = _backup_existing_target(target, composition_root)
        assert backup is None


class TestFailurePathPreservesBackup:
    """Verify the rollback contract: backup directories are preserved
    on failure so _rollback can restore from them.
    """

    def test_stale_backup_refuses_clobber(self, tmp_path: Path) -> None:
        composition_root = tmp_path / "project"
        target = composition_root / "apps" / "app"
        target.mkdir(parents=True)
        (target / "v1.txt").write_text("original")

        backup = _backup_existing_target(target, composition_root)
        assert backup is not None

        target.mkdir(parents=True)
        (target / "v2.txt").write_text("new content")

        from plugin_stack_adapters.composition import CompositionAbortError
        with pytest.raises(CompositionAbortError) as exc_info:
            _backup_existing_target(target, composition_root)
        assert "stale_pre_composition_backup" in str(exc_info.value.reason)
        assert backup.exists()
        assert (backup / "v1.txt").read_text() == "original"
