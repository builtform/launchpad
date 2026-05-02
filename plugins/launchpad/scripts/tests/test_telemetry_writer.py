"""Tests for telemetry_writer (OPERATIONS §5).

Covers append, mode bits, opt-out, line-length cap, and atomic-rename pruning
with .prune-progress crash recovery.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from telemetry_writer import (
    MAX_LINE_BYTES,
    prune_telemetry,
    write_telemetry_entry,
)


# --- write_telemetry_entry ---

def test_write_creates_obs_dir_and_writes_jsonl(tmp_path: Path):
    target = write_telemetry_entry(
        tmp_path,
        {"command": "/lp-pick-stack", "outcome": "accepted"},
        timestamp_basename="run1",
    )
    assert target is not None
    assert target.exists()
    assert target.parent == tmp_path / ".harness" / "observations"
    line = target.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["command"] == "/lp-pick-stack"
    assert rec["outcome"] == "accepted"
    assert rec["schema_version"] == "1.0"  # auto-stamped
    assert "timestamp" in rec  # auto-stamped


def test_write_appends_to_same_file(tmp_path: Path):
    write_telemetry_entry(tmp_path, {"command": "a", "outcome": "accepted"},
                          timestamp_basename="run1")
    write_telemetry_entry(tmp_path, {"command": "b", "outcome": "completed"},
                          timestamp_basename="run1")
    target = tmp_path / ".harness" / "observations" / "v2-pipeline-run1.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_write_file_mode_0o600(tmp_path: Path):
    target = write_telemetry_entry(
        tmp_path, {"command": "x", "outcome": "accepted"},
        timestamp_basename="mode",
    )
    assert target is not None
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600


def test_write_lock_file_mode_0o600(tmp_path: Path):
    write_telemetry_entry(tmp_path, {"command": "x", "outcome": "accepted"},
                          timestamp_basename="lockmode")
    lock = tmp_path / ".harness" / "observations" / ".telemetry.lock"
    assert lock.exists()
    mode = stat.S_IMODE(os.stat(lock).st_mode)
    assert mode == 0o600


def test_write_respects_telemetry_off(tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("telemetry: off\n")
    target = write_telemetry_entry(
        tmp_path, {"command": "x", "outcome": "accepted"},
    )
    assert target is None
    # Directory was not created.
    assert not (tmp_path / ".harness" / "observations").exists()


def test_write_telemetry_local_default(tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("telemetry: local\n")
    target = write_telemetry_entry(
        tmp_path, {"command": "x", "outcome": "accepted"},
        timestamp_basename="run1",
    )
    assert target is not None


def test_write_oversize_line_rejected(tmp_path: Path):
    big_value = "x" * (MAX_LINE_BYTES + 100)
    with pytest.raises(ValueError):
        write_telemetry_entry(
            tmp_path,
            {"command": "x", "outcome": "accepted", "blob": big_value},
            timestamp_basename="big",
        )


def test_write_canonical_json(tmp_path: Path):
    """sort_keys + tight separators + ensure_ascii."""
    write_telemetry_entry(
        tmp_path,
        {"z": 1, "a": 2, "m": "café"},
        timestamp_basename="canon",
    )
    target = tmp_path / ".harness" / "observations" / "v2-pipeline-canon.jsonl"
    raw = target.read_text(encoding="utf-8").rstrip()
    # sort_keys: a before m before z (no spaces)
    assert '"a":' in raw
    assert raw.index('"a":') < raw.index('"m":') < raw.index('"z":')
    # ensure_ascii: café becomes é
    assert "\\u00e9" in raw


def test_write_rejects_non_dict(tmp_path: Path):
    with pytest.raises(TypeError):
        write_telemetry_entry(tmp_path, ["not", "a", "dict"])  # type: ignore[arg-type]


# --- prune_telemetry ---

def _fake_jsonl(path: Path, ages_in_days: list[float]) -> None:
    """Write a JSONL file with one entry per age value (days ago from now)."""
    now = datetime.now(timezone.utc)
    lines = []
    for age in ages_in_days:
        ts = (now - timedelta(days=age)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(json.dumps({
            "schema_version": "1.0",
            "command": "/lp-pick-stack",
            "outcome": "accepted",
            "timestamp": ts,
        }, sort_keys=True, separators=(",", ":")) + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def test_prune_drops_old_entries(tmp_path: Path):
    obs = tmp_path / ".harness" / "observations"
    f = obs / "v2-pipeline-old.jsonl"
    # 3 fresh, 2 old
    _fake_jsonl(f, [1.0, 5.0, 10.0, 45.0, 60.0])
    pruned = prune_telemetry(tmp_path, retention_days=30)
    assert pruned == 1
    out = f.read_text(encoding="utf-8").splitlines()
    assert len(out) == 3
    for line in out:
        rec = json.loads(line)
        ts = datetime.strptime(rec["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        age = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
        assert age <= 30


def test_prune_keeps_all_when_all_fresh(tmp_path: Path):
    obs = tmp_path / ".harness" / "observations"
    f = obs / "v2-pipeline-fresh.jsonl"
    _fake_jsonl(f, [1.0, 5.0, 10.0])
    prune_telemetry(tmp_path, retention_days=30)
    assert len(f.read_text(encoding="utf-8").splitlines()) == 3


def test_prune_atomic_rewrite_via_tmp_then_rename(tmp_path: Path):
    """Verify pruned file ends up with mode 0o600 (created via O_CREAT|O_EXCL
    on a tmp + atomic rename, not truncate-in-place)."""
    obs = tmp_path / ".harness" / "observations"
    f = obs / "v2-pipeline-x.jsonl"
    _fake_jsonl(f, [60.0])  # all old
    prune_telemetry(tmp_path, retention_days=30)
    assert f.exists()
    mode = stat.S_IMODE(os.stat(f).st_mode)
    assert mode == 0o600


def test_prune_records_progress_then_completes(tmp_path: Path):
    obs = tmp_path / ".harness" / "observations"
    _fake_jsonl(obs / "v2-pipeline-a.jsonl", [60.0])
    _fake_jsonl(obs / "v2-pipeline-b.jsonl", [60.0])
    prune_telemetry(tmp_path, retention_days=30)
    # No live .prune-progress after successful completion (renamed to .completed.<ts>).
    assert not (obs / ".prune-progress").exists()
    completed = list(obs.glob(".prune-progress.completed.*"))
    assert len(completed) == 1


def test_prune_noop_when_no_obs_dir(tmp_path: Path):
    pruned = prune_telemetry(tmp_path, retention_days=30)
    assert pruned == 0


def test_prune_noop_when_telemetry_off(tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("telemetry: off\n")
    obs = tmp_path / ".harness" / "observations"
    obs.mkdir(parents=True)
    _fake_jsonl(obs / "v2-pipeline-x.jsonl", [60.0])
    pruned = prune_telemetry(tmp_path, retention_days=30)
    assert pruned == 0
    # File untouched.
    assert (obs / "v2-pipeline-x.jsonl").exists()


def test_prune_skips_enoent_files(tmp_path: Path):
    """A file in `.prune-progress` that no longer exists is silently skipped
    (covers the OPERATIONS §5 lock-acquisition ENOENT case)."""
    obs = tmp_path / ".harness" / "observations"
    obs.mkdir(parents=True)
    # Pre-stage a progress file referencing a missing target.
    (obs / ".prune-progress").write_text("v2-pipeline-ghost.jsonl\n", encoding="utf-8")
    pruned = prune_telemetry(tmp_path, retention_days=30)
    assert pruned == 0
