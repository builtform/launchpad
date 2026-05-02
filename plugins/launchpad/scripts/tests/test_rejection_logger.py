"""Tests for lp_scaffold_stack.rejection_logger (Phase 3 S8).

Layer 8/9 hardened protocol: 2-part stderr, microsec+pid filename, no lock,
ENOENT/EROFS fallback.
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.rejection_logger import (
    REJECTION_FILENAME_PREFIX,
    REJECTION_FILENAME_SUFFIX,
    SCHEMA_VERSION,
    write_rejection,
)


def test_write_success(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="sha256_mismatch", stderr=err)
    assert target is not None
    assert target.name.startswith(REJECTION_FILENAME_PREFIX)
    assert target.name.endswith(REJECTION_FILENAME_SUFFIX)
    body = json.loads(target.read_text(encoding="utf-8").strip())
    assert body["reason"] == "sha256_mismatch"
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["pid"] == os.getpid()
    assert "pid_start_time" in body


def test_two_part_stderr(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="path_traversal",
                              field_name="layers[0].path", stderr=err)
    out = err.getvalue()
    # Part 1: reason + hint (BEFORE path).
    assert "reason: path_traversal" in out
    # Part 2: log path (AFTER write).
    assert "log written to:" in out
    assert str(target) in out
    # Part 1 line precedes Part 2 line.
    lines = out.strip().splitlines()
    assert lines[0].startswith("reason:")
    assert lines[1].startswith("log written to:") or lines[1].startswith("forensic log")


def test_microsec_pid_filename(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="nonce_seen", stderr=err)
    name = target.name
    # Format: scaffold-rejection-<ISO-microsec>.<pid>.jsonl
    assert f".{os.getpid()}.jsonl" in name
    # microsec presence: ".XXXXXX"
    assert "." in name and "Z" in name


def test_field_name_in_payload(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="path_traversal",
                              field_name="layers[0].path", stderr=err)
    body = json.loads(target.read_text(encoding="utf-8").strip())
    assert body["field_name"] == "layers[0].path"


def test_seen_version_in_payload(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="version_unsupported",
                              seen_version="9.99", stderr=err)
    body = json.loads(target.read_text(encoding="utf-8").strip())
    assert body["seen_version"] == "9.99"


def test_no_lock_file_created(tmp_path: Path):
    """Layer 8 simplification: no .scaffold-rejection.lock at v2.0."""
    err = io.StringIO()
    write_rejection(tmp_path, reason="sha256_mismatch", stderr=err)
    assert not (tmp_path / ".harness" / "observations" / ".scaffold-rejection.lock").exists()


def test_file_mode_0o600(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="sha256_mismatch", stderr=err)
    import stat
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_unknown_reason_falls_back_to_default_hint(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(tmp_path, reason="some_unknown_reason", stderr=err)
    out = err.getvalue()
    assert "some_unknown_reason" in out
    assert target is not None


def test_enoent_fallback_to_stderr(tmp_path: Path, monkeypatch):
    """When mkdir / open fails with ENOENT, the reason still surfaces to
    stderr as JSONL-fallback."""
    err = io.StringIO()
    # Make the .harness path un-writable by pre-creating it as a file.
    obs_root = tmp_path / ".harness"
    obs_root.write_bytes(b"oops, this is a file")
    target = write_rejection(tmp_path, reason="sha256_mismatch", stderr=err)
    assert target is None
    out = err.getvalue()
    assert "reason: sha256_mismatch" in out
    assert "JSONL-fallback" in out or "forensic log unavailable" in out


def test_extra_fields_passed_through(tmp_path: Path):
    err = io.StringIO()
    target = write_rejection(
        tmp_path, reason="bound_cwd_inode_mismatch",
        extra={"expected_ino": 12345, "actual_ino": 67890},
        stderr=err,
    )
    body = json.loads(target.read_text(encoding="utf-8").strip())
    assert body["expected_ino"] == 12345
    assert body["actual_ino"] == 67890
