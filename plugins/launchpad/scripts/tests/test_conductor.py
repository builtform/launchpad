"""Conductor watch behavior in repositories with spaces in their paths."""

from __future__ import annotations

import selectors
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "plugin-conductor-watch.py"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "project with spaces"
    (folder / "inbox-author-unit").mkdir(parents=True)
    return folder


def run_watch(*roots: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--once", *(str(root) for root in roots)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def role_file(root: Path, name: str = "delivery-1.md") -> Path:
    path = root / "inbox-author-unit" / name
    path.write_text("Ready\n", encoding="utf-8")
    return path


def test_no_state_writes_baseline(root: Path) -> None:
    existing = role_file(root)
    result = run_watch(root)
    assert result.returncode == 1, result.stderr
    info = existing.stat()
    assert (root / ".watch-state").read_text() == (
        f"{info.st_mtime_ns}\t{info.st_size}\t{existing}\n"
    )
    assert "CHANGED" not in result.stdout


def test_new_delivery_fires_once(root: Path) -> None:
    assert run_watch(root).returncode == 1
    delivery = role_file(root)
    result = run_watch(root)
    assert result.returncode == 0, result.stderr
    assert f"CHANGED {delivery}\n" in result.stdout
    assert run_watch(root).returncode == 1


def test_ignores_conductor_and_temporary_files(root: Path) -> None:
    assert run_watch(root).returncode == 1
    for name in ("verdict-author-1.md", "ruling-1.md", ".delivery-2.md.tmp"):
        role_file(root, name)
    assert run_watch(root).returncode == 1
    assert (root / ".watch-state").read_text() == ""


def test_baseline_is_last_firing(root: Path) -> None:
    assert run_watch(root).returncode == 1
    role_file(root)
    assert run_watch(root).returncode == 0
    checkpoint = role_file(root, "checkpoint-2.md")
    result = run_watch(root)
    assert result.returncode == 0, result.stderr
    assert f"CHANGED {checkpoint}\n" in result.stdout
    assert run_watch(root).returncode == 1


def test_rewritten_file_fires(root: Path) -> None:
    delivery = role_file(root)
    assert run_watch(root).returncode == 1
    delivery.write_text("Ready for another review\n", encoding="utf-8")
    result = run_watch(root)
    assert result.returncode == 0, result.stderr
    assert f"CHANGED {delivery}\n" in result.stdout


def test_no_inboxes_and_empty_inbox(root: Path) -> None:
    (root / "inbox-author-unit").rmdir()
    result = run_watch(root)
    assert result.returncode == 1, result.stderr
    (root / "inbox-author-unit").mkdir()
    (root / "inbox-author-unit" / "nested-directory").mkdir()
    result = run_watch(root)
    assert result.returncode == 1, result.stderr


def test_second_root_fires(root: Path, tmp_path: Path) -> None:
    second = tmp_path / "second project with spaces"
    (second / "inbox-author-unit").mkdir(parents=True)
    assert run_watch(root, second).returncode == 1
    delivery = role_file(second)
    result = run_watch(root, second)
    assert result.returncode == 0, result.stderr
    assert f"CHANGED {delivery}\n" in result.stdout
    assert not (second / ".watch-state").exists()


def test_missing_root_exits_two(tmp_path: Path) -> None:
    result = run_watch(tmp_path / "missing root")
    assert result.returncode == 2
    assert "ROOT is not a directory" in result.stderr


def test_loop_fires_after_ready_line(root: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--interval", "0.2", str(root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=10), "watch did not announce readiness"
            line = process.stdout.readline()
        assert "watching pid=" in line
        assert f"pid={process.pid}" in line
        delivery = role_file(root)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert f"CHANGED {delivery}\n" in stdout
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
