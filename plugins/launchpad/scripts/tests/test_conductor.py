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


def run_watch(*roots: Path, interval: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--once", *([f"--interval={interval}"] if interval is not None else []), *(str(root) for root in roots)],
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


PLUGIN = SCRIPT.parent.parent
TEMPLATES = PLUGIN / "templates/conductor"


def test_command_prerequisites_resume_and_join_cases() -> None:
    text = (PLUGIN / "commands/lp-conductor.md").read_text(encoding="utf-8")
    assert "name: lp-conductor" in text
    assert "## Step 0" in text
    assert "plugin-prereq-check.sh" in text
    assert "--mode=lite" in text
    assert "resume" in text
    assert "refuse a repository or root path" in text
    for character in ("double quote", "dollar sign", "backtick", "backslash"):
        assert character in text
    normalized = " ".join(text.split())
    for case in ("Nothing yet", "A plan is approved", "An Implementer is mid-build"):
        assert case in normalized


def test_templates_require_native_reviews() -> None:
    for name in ("author-handoff.md", "protocol-author.md"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "/lp-harden-plan" in text
        assert "lp-code-simplicity-reviewer" in text
    for name in ("implementer-handoff.md", "protocol-implementer.md"):
        assert "/lp-review" in (TEMPLATES / name).read_text(encoding="utf-8")


def test_continue_prompts_have_one_section_blank() -> None:
    for name in ("author-handoff.md", "implementer-handoff.md"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        prompt = text.split("## CONTINUE prompt", 1)[1].split("```", 2)[1]
        assert prompt.count("<n>") == 1


def test_public_command_templates_and_script() -> None:
    paths = [PLUGIN / "commands/lp-conductor.md", SCRIPT, *TEMPLATES.glob("*.md")]
    assert len(paths) == 6
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for forbidden in ("\u2014", "/" + "Users/", "/" + "home/"):
            assert forbidden not in text, f"{path.name}: {forbidden!r}"


@pytest.mark.parametrize("contents", [b"invalid state", b"\xff", b"1\tbad\t/path\n"])
def test_corrupt_state_rebaselines(root: Path, contents: bytes) -> None:
    delivery = role_file(root)
    (root / ".watch-state").write_bytes(contents)
    result = run_watch(root)
    assert result.returncode == 1, result.stderr
    assert "CHANGED" not in result.stdout
    info = delivery.stat()
    assert (root / ".watch-state").read_text() == (
        f"{info.st_mtime_ns}\t{info.st_size}\t{delivery}\n"
    )


@pytest.mark.parametrize("interval", ["0", "-0.5", "nan", "inf", "-inf", "not-a-number"])
def test_invalid_interval_exits_two(root: Path, interval: str) -> None:
    result = run_watch(root, interval=interval)
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "--interval" in result.stderr


def test_state_write_filesystem_error_exits_two(root: Path) -> None:
    (root / ".watch-state").mkdir()
    result = run_watch(root)
    assert result.returncode == 2
    assert "watch error:" in result.stderr



def test_author_close_requires_answered_and_folded_stops() -> None:
    command = " ".join((PLUGIN / "commands/lp-conductor.md").read_text().split())
    protocol = " ".join((TEMPLATES / "protocol-author.md").read_text().split())
    assert all(token in command for token in (
        "Never write CLOSE", "any Author stop", "matching ruling",
        "plan-affecting ruling", "folded into the delivery", "CONTINUE instead",
    ))
    assert "Fold every answered plan-affecting ruling" in protocol


def test_checkpoint_verifies_complete_section_range() -> None:
    command = " ".join((PLUGIN / "commands/lp-conductor.md").read_text().split())
    protocol = " ".join((TEMPLATES / "protocol-implementer.md").read_text().split())
    assert all(token in command for token in (
        "previous verified head", "last verified checkpoint head", "ancestor",
        'git diff --stat "<previous>..<head>"', "including every fix commit",
        "all changed files in that range",
    ))
    assert "previous verified head" in protocol and "handoff base head" in protocol


def test_every_command_and_prompt_path_is_validated() -> None:
    command = " ".join((PLUGIN / "commands/lp-conductor.md").read_text().split())
    policy = command.split("## Path safety", 1)[1].split("## Step 0", 1)[0]
    assert all(token in policy for token in (
        "any other path placed in a command or prompt", "double quote",
        "dollar sign", "backtick", "backslash", "after physical resolution",
        "resolved plugin root before Step 0", "working directories",
        "plan and source paths", "handoff", "protocol", "inbox", "resume mode",
    ))
