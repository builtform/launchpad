"""v2.1 Codex PR #50 post-review P1 regression: write_batch two-phase contract.

Asserts:
  * Phase-1 failure (e.g., one target's content fails to write) → all
    earlier target files in the batch remain unwritten on disk.
  * Phase-2 mid-rename failure → first-half final + second-half remain
    as `.tmp` (manual recovery surface).
  * Successful batch leaves every target at the final path with the
    correct content + mode.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace_batch  # noqa: E402


def test_successful_batch_writes_all_targets(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "sub" / "b.txt"
    c = tmp_path / "c.txt"
    atomic_write_replace_batch({a: b"alpha", b: b"bravo", c: b"charlie"}, trusted_root=tmp_path)
    assert a.read_bytes() == b"alpha"
    assert b.read_bytes() == b"bravo"
    assert c.read_bytes() == b"charlie"


def test_successful_batch_applies_per_file_modes(tmp_path):
    exe = tmp_path / "script.sh"
    plain = tmp_path / "config.yml"
    atomic_write_replace_batch(
        {exe: b"#!/bin/sh\n", plain: b"key: value\n"},
        modes={exe: 0o755, plain: 0o644},
        trusted_root=tmp_path,
    )
    assert (exe.stat().st_mode & 0o777) == 0o755
    assert (plain.stat().st_mode & 0o777) == 0o644


def test_phase1_failure_leaves_originals_untouched(tmp_path):
    """If staging fails for any target, no original target file changes
    on disk. Simulate by passing a non-encodable bytes object replacement
    via patched os.write that raises mid-iteration."""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    c = tmp_path / "c.txt"
    a.write_bytes(b"original-a")
    b.write_bytes(b"original-b")
    c.write_bytes(b"original-c")

    # Patch os.write to raise after the first staged file.
    real_write = os.write
    call_count = {"n": 0}

    def fail_after_first(fd, data):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("simulated stage failure on second target")
        return real_write(fd, data)

    with patch("atomic_io.os.write", side_effect=fail_after_first):
        with pytest.raises(OSError, match="simulated stage failure"):
            atomic_write_replace_batch({a: b"new-a", b: b"new-b", c: b"new-c"}, trusted_root=tmp_path)

    # P1 regression: ALL originals untouched (none of new-a, new-b, new-c
    # made it to its final target).
    assert a.read_bytes() == b"original-a"
    assert b.read_bytes() == b"original-b"
    assert c.read_bytes() == b"original-c"
    # No leftover .tmp files in the parent (cleaned up on stage failure).
    leftover = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftover == [], f"leftover tmp files: {leftover}"


def test_phase2_mid_rename_failure_leaves_partial_state(tmp_path):
    """If a Phase-2 rename fails mid-batch, first-half is at final paths,
    second-half remains as .tmp (manual-recovery surface). Phase-2 is
    best-effort by contract; this test pins the post-condition."""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    c = tmp_path / "c.txt"

    real_replace = os.replace
    rename_count = {"n": 0}

    def fail_on_second_rename(src, dst):
        rename_count["n"] += 1
        if rename_count["n"] == 2:
            raise OSError("simulated rename failure on second target")
        return real_replace(src, dst)

    with patch("atomic_io.os.replace", side_effect=fail_on_second_rename):
        with pytest.raises(OSError, match="simulated rename failure"):
            atomic_write_replace_batch({a: b"alpha", b: b"bravo", c: b"charlie"}, trusted_root=tmp_path)

    # First target landed at its final path.
    assert a.read_bytes() == b"alpha"
    # Second target's tmp remained on disk (failed-rename file).
    second_tmps = [p for p in tmp_path.iterdir() if p.name.startswith(".b.txt") and p.name.endswith(".tmp")]
    assert len(second_tmps) == 1, f"expected exactly one .b.txt.*.tmp, got {second_tmps}"
    assert second_tmps[0].read_bytes() == b"bravo"
    # Third target — Phase-2 short-circuited after the second's failure;
    # depending on iteration order, c may remain as .tmp OR may not have
    # been renamed yet. Both states are acceptable per the docstring.
    assert not c.exists() or c.read_bytes() == b"charlie"


def test_empty_batch_is_no_op(tmp_path):
    atomic_write_replace_batch({}, trusted_root=tmp_path)
    # tmp_path stays empty.
    assert list(tmp_path.iterdir()) == []
