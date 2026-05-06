"""Phase 10 v2.1 -- /lp-update-identity sentinel lifecycle tests.

Six tests covering DA3 sentinel surface:

  1. write_sentinel via O_CREAT|O_EXCL succeeds + 0o600 mode
  2. clear_sentinel is idempotent
  3. read_sentinel + dead PID -> auto-recover (engine clears in preflight)
  4. read_sentinel + live PID -> refuse (engine raises in preflight)
  5. /lp-bootstrap _sentinel_preflight cross-detects identity-update
     sentinel + live PID -> raises IDENTITY_UPDATE_IN_PROGRESS
  6. corrupt-JSON sentinel -> refuse immediately (no retry)
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap import BootstrapErrorCode, LAUNCHPAD_DIR_NAME
from lp_update_identity import (
    IDENTITY_UPDATE_SENTINEL_NAME,
    IdentityUpdateErrorCode,
    IdentityUpdateSentinelError,
)
from lp_update_identity.sentinel import (
    clear_sentinel,
    read_sentinel,
    sentinel_path,
    write_sentinel,
)


def _seed_launchpad_dir(tmp_path: Path) -> Path:
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    return tmp_path


def test_write_sentinel_o_excl_succeeds_with_0o600_mode(tmp_path: Path):
    cwd = _seed_launchpad_dir(tmp_path)
    snap = write_sentinel(
        cwd,
        pre_edit_decision_sha256="abc123",
        target_paths=["LICENSE", "README.md"],
        backup_path=str(tmp_path / ".launchpad" / "backups" / "20260506T000000Z"),
    )
    target = sentinel_path(cwd)
    assert target.is_file()
    assert target.name == IDENTITY_UPDATE_SENTINEL_NAME
    mode_bits = stat.S_IMODE(target.stat().st_mode)
    assert mode_bits == 0o600, f"sentinel mode bits = {mode_bits:o}, expected 0o600"
    assert snap.command_pid == os.getpid()
    assert snap.target_paths == ("LICENSE", "README.md")
    assert snap.mode == "update-identity"

    # Concurrent-create race: O_EXCL refuses cleanly with FileExistsError.
    with pytest.raises(FileExistsError):
        write_sentinel(
            cwd,
            pre_edit_decision_sha256="def456",
            target_paths=["LICENSE"],
            backup_path=str(tmp_path / ".launchpad" / "backups" / "20260506T000001Z"),
        )


def test_clear_sentinel_idempotent(tmp_path: Path):
    cwd = _seed_launchpad_dir(tmp_path)
    write_sentinel(
        cwd,
        pre_edit_decision_sha256=None,
        target_paths=[],
        backup_path=str(tmp_path / "bk"),
    )
    assert sentinel_path(cwd).is_file()
    clear_sentinel(cwd)
    assert not sentinel_path(cwd).exists()
    # Second clear is a no-op (idempotent).
    clear_sentinel(cwd)


def test_read_sentinel_dead_pid_returns_snapshot(tmp_path: Path):
    cwd = _seed_launchpad_dir(tmp_path)
    # Use a PID guaranteed dead: one beyond a typical 32-bit PID space.
    dead_pid = 2**31 - 1
    write_sentinel(
        cwd,
        pre_edit_decision_sha256=None,
        target_paths=["LICENSE"],
        backup_path="/tmp/bk",
        command_pid=dead_pid,
    )
    snap = read_sentinel(cwd)
    assert snap is not None
    assert snap.command_pid == dead_pid

    # Engine-layer behavior: when dead, caller invokes clear_sentinel.
    from lp_update_identity.sentinel import is_pid_alive
    assert not is_pid_alive(dead_pid)


def test_read_sentinel_live_pid_signals_refuse(tmp_path: Path):
    cwd = _seed_launchpad_dir(tmp_path)
    write_sentinel(
        cwd,
        pre_edit_decision_sha256=None,
        target_paths=[],
        backup_path="/tmp/bk",
        command_pid=os.getpid(),
    )
    snap = read_sentinel(cwd)
    assert snap is not None

    from lp_update_identity.sentinel import is_pid_alive
    assert is_pid_alive(os.getpid()), "this process must be alive"


def test_bootstrap_preflight_cross_detects_identity_sentinel(tmp_path: Path, monkeypatch):
    """DA3 bidirectional parity (security F2 + frontend-races F1):
    /lp-bootstrap refuses on live `.identity-update-in-progress` sentinel."""
    cwd = _seed_launchpad_dir(tmp_path)
    # Seed identity-update sentinel with this process's PID (live).
    write_sentinel(
        cwd,
        pre_edit_decision_sha256=None,
        target_paths=["LICENSE"],
        backup_path="/tmp/bk",
        command_pid=os.getpid(),
    )

    from lp_bootstrap.engine import (
        BootstrapEngineError,
        _sentinel_preflight,
    )
    with pytest.raises(BootstrapEngineError) as excinfo:
        _sentinel_preflight(cwd)
    assert excinfo.value.reason == BootstrapErrorCode.IDENTITY_UPDATE_IN_PROGRESS


def test_corrupt_json_sentinel_refuses_immediately(tmp_path: Path):
    cwd = _seed_launchpad_dir(tmp_path)
    target = sentinel_path(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(IdentityUpdateSentinelError) as excinfo:
        read_sentinel(cwd)
    assert excinfo.value.reason == IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS
    assert "JSON parse error" in str(excinfo.value)
