"""Tests for atomic-write semantics around the bootstrap sentinel + manifest
(v2.1 Phase 3 Slice A; section 5 + plan section 2.2).

Atomic primitives ride Phase 1's `atomic_io.atomic_write_replace`. The
contracts pinned here:

  * Sentinel mode is 0o600 (harden B6).
  * Sentinel snapshot round-trip (write -> read).
  * `is_pid_alive` returns False for dead PIDs and True for live PIDs.
  * Stale-sentinel-dead-PID auto-recovery surface: `read_sentinel`
    succeeds even when the recorded PID is dead; the engine layer-above
    decides recovery based on `is_pid_alive(snapshot.command_pid)`.
  * `cross_device_replace` error path: simulated by patching `os.replace`.
  * Sentinel JSON shape per section 3.6: 5 required fields, no
    `sentinel_schema_version` (harden C8).
  * `clear_sentinel` is idempotent.
  * Dedicated `.bootstrap.lock` flock target (harden B7) is the engine
    primitive's surface; ride Phase 1's `advisory_flock`.

The "manifest-not-written-on-partial-render-failure" invariant (harden B16)
is engine-level and pinned in Slice C `test_bootstrap_wiring.py`; this
file pins the lower-level write/read primitives.
"""
from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from atomic_io import advisory_flock  # noqa: E402

from lp_bootstrap import (  # noqa: E402
    BootstrapErrorCode,
    LAUNCHPAD_DIR_NAME,
    LOCK_NAME,
    SENTINEL_NAME,
)
from lp_bootstrap.sentinel import (  # noqa: E402
    BootstrapSentinelError,
    SentinelSnapshot,
    clear_sentinel,
    is_pid_alive,
    read_sentinel,
    sentinel_path,
    write_sentinel,
)


def _setup_launchpad_dir(cwd: Path) -> Path:
    d = cwd / LAUNCHPAD_DIR_NAME
    d.mkdir()
    return d


# --- Sentinel write + read round-trip -------------------------------------

def test_write_sentinel_creates_file_with_correct_path(tmp_path):
    _setup_launchpad_dir(tmp_path)
    write_sentinel(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=["a.txt", "b.txt"],
    )
    assert sentinel_path(tmp_path).is_file()


def test_sentinel_mode_is_0o600(tmp_path):
    """Harden B6: sentinel mode must be 0o600 so command_pid is not
    world-readable on shared dev hosts."""
    _setup_launchpad_dir(tmp_path)
    write_sentinel(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=[],
    )
    actual_mode = sentinel_path(tmp_path).stat().st_mode & 0o777
    assert actual_mode == 0o600


def test_write_then_read_sentinel_round_trip(tmp_path):
    _setup_launchpad_dir(tmp_path)
    write_sentinel(
        tmp_path,
        mode="brownfield-auto",
        pre_edit_manifest_sha256="a" * 64,
        target_paths=["scripts/build.sh", "lefthook.yml"],
        command_pid=42,
    )
    snap = read_sentinel(tmp_path)
    assert snap is not None
    assert snap.command_pid == 42
    assert snap.mode == "brownfield-auto"
    assert snap.pre_edit_manifest_sha256 == "a" * 64
    assert list(snap.target_paths) == ["scripts/build.sh", "lefthook.yml"]
    # No schema_version field per harden C8
    raw = json.loads(sentinel_path(tmp_path).read_text(encoding="utf-8"))
    assert "sentinel_schema_version" not in raw


def test_read_sentinel_returns_none_when_absent(tmp_path):
    _setup_launchpad_dir(tmp_path)
    assert read_sentinel(tmp_path) is None


def test_clear_sentinel_idempotent_when_absent(tmp_path):
    _setup_launchpad_dir(tmp_path)
    clear_sentinel(tmp_path)  # absent -> no-op
    write_sentinel(
        tmp_path, mode="refresh",
        pre_edit_manifest_sha256=None, target_paths=[],
    )
    assert sentinel_path(tmp_path).is_file()
    clear_sentinel(tmp_path)
    assert not sentinel_path(tmp_path).exists()
    clear_sentinel(tmp_path)  # double-clear
    assert not sentinel_path(tmp_path).exists()


# --- Sentinel JSON corruption raises MANIFEST_CORRUPT ---------------------

def test_read_sentinel_raises_manifest_corrupt_on_invalid_json(tmp_path):
    _setup_launchpad_dir(tmp_path)
    sentinel_path(tmp_path).write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(BootstrapSentinelError) as excinfo:
        read_sentinel(tmp_path)
    assert excinfo.value.reason == BootstrapErrorCode.MANIFEST_CORRUPT


def test_read_sentinel_raises_when_top_level_not_mapping(tmp_path):
    _setup_launchpad_dir(tmp_path)
    sentinel_path(tmp_path).write_text("[]", encoding="utf-8")
    with pytest.raises(BootstrapSentinelError) as excinfo:
        read_sentinel(tmp_path)
    assert excinfo.value.reason == BootstrapErrorCode.MANIFEST_CORRUPT


def test_read_sentinel_raises_on_missing_required_field(tmp_path):
    _setup_launchpad_dir(tmp_path)
    bad = {"command_pid": 1, "mode": "greenfield"}  # missing started_at, target_paths
    sentinel_path(tmp_path).write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(BootstrapSentinelError) as excinfo:
        read_sentinel(tmp_path)
    assert excinfo.value.reason == BootstrapErrorCode.MANIFEST_CORRUPT


def test_read_sentinel_raises_on_non_int_pid(tmp_path):
    _setup_launchpad_dir(tmp_path)
    bad = {
        "command_pid": "not-an-int",
        "started_at": "2026-05-05T00:00:00Z",
        "mode": "greenfield",
        "target_paths": [],
        "pre_edit_manifest_sha256": None,
    }
    sentinel_path(tmp_path).write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(BootstrapSentinelError):
        read_sentinel(tmp_path)


# --- PID liveness (section 3.5) ------------------------------------------

def test_is_pid_alive_true_for_self():
    assert is_pid_alive(os.getpid())


def test_is_pid_alive_false_for_dead_pid():
    """Stale-sentinel-dead-PID surface: PID 999999 is overwhelmingly likely
    to be dead on a typical dev host."""
    # Use a PID very unlikely to exist; if collision happens, the test is
    # informative only.
    assert not is_pid_alive(999_999)


def test_is_pid_alive_false_for_zero_or_negative():
    assert not is_pid_alive(0)
    assert not is_pid_alive(-1)


def test_stale_sentinel_dead_pid_recovery_surface(tmp_path):
    """Engine layer-above flow: read_sentinel succeeds even when PID dead."""
    _setup_launchpad_dir(tmp_path)
    write_sentinel(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=["a.txt"],
        command_pid=999_999,
    )
    snap = read_sentinel(tmp_path)
    assert snap is not None
    assert not is_pid_alive(snap.command_pid)


# --- Atomic write under simulated cross-device replace failure ------------

def test_cross_device_replace_error_path(tmp_path):
    """`os.replace` raises EXDEV on cross-device renames (macOS APFS users
    mounting external drives). Pin that the failure surfaces as an OSError
    with EXDEV so the engine maps it to CROSS_DEVICE_REPLACE."""
    target = tmp_path / "out.txt"
    err = OSError(errno.EXDEV, "Cross-device link not permitted")

    real_replace = os.replace

    def _stub_replace(src, dst):
        if str(dst) == str(target):
            raise err
        return real_replace(src, dst)

    with mock.patch.object(os, "replace", side_effect=_stub_replace):
        with pytest.raises(OSError) as excinfo:
            from atomic_io import atomic_write_replace
            atomic_write_replace(target, b"hello", mode=0o644)
        assert excinfo.value.errno == errno.EXDEV


# --- advisory_flock dedicated lock target (harden B7) ---------------------

def test_dedicated_bootstrap_lock_filename_is_distinct():
    """Harden B7: flock target is `.launchpad/.bootstrap.lock`, not the
    manifest itself or the parent directory. This pins the constant so a
    rename produces a test failure, not a silent semantic break."""
    assert LOCK_NAME == ".bootstrap.lock"
    assert SENTINEL_NAME == ".bootstrap-in-progress"
    assert LOCK_NAME != SENTINEL_NAME


def test_advisory_flock_round_trip(tmp_path):
    """advisory_flock context manager must acquire and release without error."""
    _setup_launchpad_dir(tmp_path)
    lockfile = tmp_path / LAUNCHPAD_DIR_NAME / LOCK_NAME
    with advisory_flock(lockfile):
        pass
    # Re-acquire confirms the lock was released
    with advisory_flock(lockfile):
        pass
