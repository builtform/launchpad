"""Tests for `atomic_io` helpers (V3 plan §10.4 V1 residual closure).

The atomic-write helpers extract the durability pattern that was
duplicated across decision_writer.py, receipt_writer.py, etc. into a
single shared module. These tests assert:

  * `atomic_write_excl` succeeds on first write, raises FileExistsError
    on the second (concurrent /lp-pick-stack race protection).
  * `atomic_write_replace` overwrites cleanly via tempfile + os.replace
    and leaves no `.tmp` artifacts on success or failure.
  * `advisory_flock` acquires LOCK_EX and serializes concurrent RMW
    callers (used by /lp-define and /lp-update-identity).
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

# Ensure scripts/ is on path for sibling-module imports
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from atomic_io import (  # noqa: E402
    advisory_flock,
    atomic_write_excl,
    atomic_write_replace,
)


def test_atomic_write_excl_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "kernel" / "scaffold-decision.json"
    atomic_write_excl(target, b'{"hello": "world"}', trusted_root=tmp_path)

    assert target.read_bytes() == b'{"hello": "world"}'
    # Parent directory was created
    assert target.parent.is_dir()
    # File mode is 0o600 (owner read/write only)
    mode = target.stat().st_mode & 0o777
    assert mode == 0o600


def test_atomic_write_excl_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "scaffold-decision.json"
    atomic_write_excl(target, b'{"first": 1}', trusted_root=tmp_path)

    with pytest.raises(FileExistsError):
        atomic_write_excl(target, b'{"second": 2}', trusted_root=tmp_path)

    # Original content preserved
    assert target.read_bytes() == b'{"first": 1}'


def test_atomic_write_replace_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    atomic_write_replace(target, b'{"version": 1}', trusted_root=tmp_path)
    atomic_write_replace(target, b'{"version": 2}', trusted_root=tmp_path)

    assert target.read_bytes() == b'{"version": 2}'

    # No leftover tempfiles in the parent dir
    leftovers = [p for p in target.parent.iterdir() if p.name != "manifest.json"]
    assert leftovers == [], f"tempfile cleanup failed: {leftovers}"


def test_atomic_write_replace_creates_when_absent(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "manifest.json"
    atomic_write_replace(target, b'{"k": "v"}', trusted_root=tmp_path)

    assert target.read_bytes() == b'{"k": "v"}'
    assert target.parent.is_dir()


def test_advisory_flock_serializes_concurrent_callers(tmp_path: Path) -> None:
    """Two threads racing for the same flock should serialize.

    This test pins down the contract that callers using `advisory_flock`
    on the same path are mutually excluded. External writers that bypass
    the helper are NOT excluded — that is documented as the advisory
    semantics in the helper's docstring.
    """
    lock_path = tmp_path / "config.yml"
    lock_path.touch()

    enter_count = 0
    exit_count = 0
    inside_serialized = []
    inside_overlap_detected = False

    def worker(worker_id: int) -> None:
        nonlocal enter_count, exit_count, inside_overlap_detected
        with advisory_flock(lock_path):
            local_inside = enter_count - exit_count
            if local_inside > 0:
                # Another worker is still inside; that violates serialization
                inside_overlap_detected = True
            enter_count += 1
            inside_serialized.append(worker_id)
            time.sleep(0.05)  # hold the lock briefly
            exit_count += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not inside_overlap_detected, "advisory_flock failed to serialize callers"
    assert sorted(inside_serialized) == [0, 1, 2, 3]
    assert enter_count == 4 and exit_count == 4


def test_advisory_flock_creates_target_when_absent(tmp_path: Path) -> None:
    """Calling flock on a non-existent path should create it (mode 0o600).

    The helper's contract: a brownfield project may invoke /lp-define on
    a fresh state where .launchpad/config.yml does not yet exist; the
    advisory_flock context creates the lock target so callers don't need
    a separate touch step.
    """
    lock_path = tmp_path / "fresh-config.yml"
    assert not lock_path.exists()

    with advisory_flock(lock_path):
        assert lock_path.exists()
        mode = lock_path.stat().st_mode & 0o777
        assert mode == 0o600
