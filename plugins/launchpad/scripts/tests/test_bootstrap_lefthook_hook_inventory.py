"""v2.1 Codex PR #50 P1.A (D1) regression: restamp-history-hook inventory.

Tests:
  * INFRASTRUCTURE_FILES contains the restamp-history-hook entry
  * HOOK_CLASSIFICATIONS keys are subset of INFRASTRUCTURE_TARGETS (drift gate)
  * downstream wrapper template accepts `wip(...)` subjects + rejects unknown prefixes
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def test_restamp_history_hook_in_infrastructure_files():
    from lp_bootstrap import INFRASTRUCTURE_FILES, INFRASTRUCTURE_TARGETS
    assert "scripts/hooks/restamp-history-hook.py" in INFRASTRUCTURE_TARGETS


def test_hook_classifications_subset_of_targets():
    from lp_bootstrap import HOOK_CLASSIFICATIONS, INFRASTRUCTURE_TARGETS
    assert set(HOOK_CLASSIFICATIONS.keys()) <= INFRASTRUCTURE_TARGETS


def test_hook_classifications_includes_commit_msg():
    from lp_bootstrap import HOOK_CLASSIFICATIONS
    assert (
        HOOK_CLASSIFICATIONS["scripts/hooks/restamp-history-hook.py"]
        == "commit-msg"
    )


def test_lefthook_template_points_at_downstream_path():
    template_path = (
        _SCRIPTS_DIR
        / "plugin_default_generators"
        / "infrastructure"
        / "lefthook.yml.j2"
    )
    text = template_path.read_text(encoding="utf-8")
    assert "scripts/hooks/restamp-history-hook.py" in text


def test_downstream_template_introduces_subject_allowlist():
    template_path = (
        _SCRIPTS_DIR
        / "plugin_default_generators"
        / "infrastructure"
        / "scripts"
        / "hooks"
        / "restamp-history-hook.py.j2"
    )
    text = template_path.read_text(encoding="utf-8")
    # Allowlist regex names the conventional-commit prefix list + `wip`.
    assert "feat" in text and "fix" in text and "chore" in text and "wip" in text


def test_downstream_wrapper_accepts_wip_slice_prefix(tmp_path):
    """End-to-end: invoke the rendered downstream wrapper with a wip(slice-x): subject."""
    template_path = (
        _SCRIPTS_DIR
        / "plugin_default_generators"
        / "infrastructure"
        / "scripts"
        / "hooks"
        / "restamp-history-hook.py.j2"
    )
    # The .j2 template happens to be valid Python (no Jinja2 substitutions in
    # the body). For this test we read it as Python source directly.
    rendered = tmp_path / "restamp-history-hook.py"
    rendered.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    rendered.chmod(0o755)

    msg_file = tmp_path / "COMMIT_MSG"
    msg_file.write_text("wip(slice-a): test subject\n", encoding="utf-8")

    # Skip upstream-hook delegation by pointing at a non-existent path so the
    # graceful-degrade branch fires (exit 0 on prefix accepted).
    result = subprocess.run(
        [
            sys.executable,
            str(rendered),
            str(msg_file),
            "--upstream-hook",
            str(tmp_path / "no-such-upstream.py"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_downstream_wrapper_rejects_unknown_prefix(tmp_path):
    template_path = (
        _SCRIPTS_DIR
        / "plugin_default_generators"
        / "infrastructure"
        / "scripts"
        / "hooks"
        / "restamp-history-hook.py.j2"
    )
    rendered = tmp_path / "restamp-history-hook.py"
    rendered.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    rendered.chmod(0o755)

    msg_file = tmp_path / "COMMIT_MSG"
    msg_file.write_text("garbage: this is not a conventional commit\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(rendered), str(msg_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 65
