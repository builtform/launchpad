"""Phase 7 §4.9 — lefthook commit-msg restamp-history injection-defense.

Per Layer 7 closure (test plan strip-back appendix retained item) +
OPERATIONS §0 Layer 9 P3-2 closure: the commit-msg hook MUST be wired to
a Python script (not shell) so subject-line injection-defenses are
enforceable. This test exercises the script directly with two attack
inputs: literal `\\n` and literal `\\r\\n` in the commit subject.

Acceptance per handoff §4.9:
  - Hook exits non-zero on injection.
  - NO line written to `.harness/observations/restamp-history.jsonl`.
  - Both `\\n` and `\\r\\n` cases must reject.

Sub-test bonus: a CLEAN subject line should be ACCEPTED — exit 0 + JSONL
line written with the canonical fields (`schema_version`, `timestamp`,
`pid`, `pid_start_time`, `subject`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
RESTAMP_HOOK_SCRIPT = (
    _REPO_ROOT / "plugins" / "launchpad" / "scripts"
    / "plugin-restamp-history-hook.py"
)


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-restamp-injection-"))
    os.chmod(d, 0o700)
    return d


def _invoke_hook(repo_root: Path, commit_msg: str) -> subprocess.CompletedProcess:
    """Write commit_msg to a tmpfile inside repo_root and invoke the hook."""
    msg_path = repo_root / "COMMIT_EDITMSG"
    msg_path.write_bytes(commit_msg.encode("utf-8"))
    return subprocess.run(
        [
            sys.executable, str(RESTAMP_HOOK_SCRIPT),
            str(msg_path),
            "--repo-root", str(repo_root),
        ],
        capture_output=True, timeout=30, check=False,
    )


def _restamp_jsonl(repo_root: Path) -> Path:
    return repo_root / ".harness" / "observations" / "restamp-history.jsonl"


def test_hook_script_exists_and_is_python():
    """Pre-flight: the hook script lives at the expected path AND has a
    `#!/usr/bin/env python3` shebang.

    Per OPERATIONS §0 Layer 9 P3-2 closure: shell-wired commit-msg hooks
    are out of scope; Python-wiring is the contract.
    """
    assert RESTAMP_HOOK_SCRIPT.is_file(), (
        f"hook script not found: {RESTAMP_HOOK_SCRIPT}"
    )
    first_line = RESTAMP_HOOK_SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert "python" in first_line.lower(), (
        f"hook script shebang is not Python: {first_line!r}"
    )


def test_hook_lefthook_yml_wired():
    """Pre-flight: `lefthook.yml` at repo root has a `commit-msg.commands.
    restamp-history` entry pointing at the Python hook."""
    lefthook = _REPO_ROOT / "lefthook.yml"
    assert lefthook.is_file()
    text = lefthook.read_text(encoding="utf-8")
    assert "commit-msg:" in text, "lefthook.yml missing commit-msg block"
    assert "restamp-history:" in text, (
        "lefthook.yml missing restamp-history command"
    )
    assert "plugin-restamp-history-hook.py" in text, (
        "lefthook.yml restamp-history not wired to the Python hook"
    )


def test_clean_subject_accepted():
    """Clean subject line accepted; JSONL entry written with canonical fields."""
    tmp = _make_tempdir()
    try:
        rv = _invoke_hook(tmp, "chore: clean commit subject\n")
        assert rv.returncode == 0, (
            f"clean subject rejected: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')!r}"
        )
        log = _restamp_jsonl(tmp)
        assert log.exists(), "restamp-history.jsonl not written"
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        for required in ("schema_version", "timestamp", "pid",
                         "pid_start_time", "subject"):
            assert required in entry, (
                f"entry missing required field {required!r}: {entry!r}"
            )
        assert entry["subject"] == "chore: clean commit subject"
        # Mode should be 0o600 user-only.
        mode = log.stat().st_mode & 0o777
        assert mode == 0o600, f"restamp-history.jsonl mode {oct(mode)} != 0o600"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize(
    "case_name,commit_msg",
    [
        ("lf_in_subject", "chore: subject\nwith LF injection\n"),
        ("crlf_in_subject", "chore: subject\r\nwith CRLF injection\n"),
        ("lone_cr_in_subject", "chore: subject\rwith lone CR injection\n"),
    ],
)
def test_injection_rejected_no_jsonl_written(case_name, commit_msg):
    """`\\n`, `\\r\\n`, and lone `\\r` in the commit subject all reject the
    hook AND skip the JSONL write."""
    tmp = _make_tempdir()
    try:
        rv = _invoke_hook(tmp, commit_msg)
        assert rv.returncode != 0, (
            f"[{case_name}] hook accepted injection (expected reject): "
            f"stdout={rv.stdout!r}, stderr={rv.stderr!r}"
        )
        # No JSONL line.
        log = _restamp_jsonl(tmp)
        if log.exists():
            content = log.read_text(encoding="utf-8")
            assert content.strip() == "", (
                f"[{case_name}] JSONL line written despite injection: "
                f"{content!r}"
            )
        # stderr surfaces the rejection reason.
        stderr = rv.stderr.decode("utf-8", errors="replace")
        assert "REJECTED" in stderr or "injection-rejected" in stderr, (
            f"[{case_name}] stderr does not mention rejection: {stderr!r}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
