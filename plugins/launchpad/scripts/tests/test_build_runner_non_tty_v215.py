"""BL-340 v2.1.5: plugin-build-runner.py detects when a command exits 0
but bailed silently on a non-TTY interactive prompt. Without this,
commands like `pnpm astro check` (prompts to auto-install dev-deps,
exits 0 on non-TTY) would silently false-pass the build pipeline.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_build_runner():
    """Load the build-runner module (hyphenated filename → import-by-path)."""
    spec = importlib.util.spec_from_file_location(
        "plugin_build_runner", _SCRIPTS / "plugin-build-runner.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bl340_detects_continue_yes_no_prompt(tmp_path: Path) -> None:
    """A command printing the canonical pnpm-style `Continue? Yes / No`
    prompt then exiting 0 must be reported as a false-pass."""
    mod = _load_build_runner()
    # Use a shell command that prints the prompt pattern and exits 0.
    cmd = "echo 'Continue? Yes / No'; exit 0"
    rc, detected = mod._run_cmd_with_prompt_detection(cmd, tmp_path)
    assert rc == 0
    assert detected == "Continue? Yes / No"


def test_bl340_clean_command_passes(tmp_path: Path) -> None:
    """A command with clean output and exit 0 reports no prompt detection."""
    mod = _load_build_runner()
    cmd = "echo 'all good'; exit 0"
    rc, detected = mod._run_cmd_with_prompt_detection(cmd, tmp_path)
    assert rc == 0
    assert detected is None


def test_bl340_failed_command_reports_exit_code(tmp_path: Path) -> None:
    """A command exiting non-zero passes the exit code through unchanged."""
    mod = _load_build_runner()
    cmd = "echo 'something'; exit 7"
    rc, detected = mod._run_cmd_with_prompt_detection(cmd, tmp_path)
    assert rc == 7
    # detected is irrelevant when rc != 0; the caller short-circuits on rc.


def test_bl340_prompt_patterns_set() -> None:
    """The closed enum of prompt-bail patterns covers the canonical
    pnpm + npm prompt shapes."""
    mod = _load_build_runner()
    patterns = mod._PROMPT_BAIL_PATTERNS
    assert "Continue? Yes / No" in patterns
    assert "[Y/n]" in patterns or "[y/N]" in patterns
    assert any("install" in p.lower() for p in patterns)
