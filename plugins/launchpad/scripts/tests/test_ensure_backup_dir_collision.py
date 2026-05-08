"""Verify _ensure_backup_dir uses random suffix to prevent collisions.

Phase 5 (cycle 5 F5 P2): two invocations within one second must
produce distinct directories, not silently reuse the same one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_update_identity.engine import _ensure_backup_dir


class TestEnsureBackupDirCollision:
    def test_two_invocations_produce_distinct_dirs(self, tmp_path: Path) -> None:
        a = _ensure_backup_dir(tmp_path)
        b = _ensure_backup_dir(tmp_path)
        assert a != b
        assert a.exists()
        assert b.exists()

    def test_dir_name_has_random_suffix(self, tmp_path: Path) -> None:
        d = _ensure_backup_dir(tmp_path)
        parts = d.name.split("-")
        assert len(parts) >= 3, (
            f"expected <ts>-<pid>-<rand> format, got {d.name!r}"
        )

    def test_exist_ok_false_raises_on_pre_existing(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        import secrets
        monkeypatch.setattr(secrets, "token_hex", lambda n: "dead")
        _ensure_backup_dir(tmp_path)
        with pytest.raises(FileExistsError):
            _ensure_backup_dir(tmp_path)
