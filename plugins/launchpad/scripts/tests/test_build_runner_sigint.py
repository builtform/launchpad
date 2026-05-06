"""Phase 5 v2.1 (DA2 + DA7) -- /lp-build dev-stage SIGINT integration tests.

These tests cover the WIRING from `plugin-build-runner.py --stage=dev`
through `safe_run_long_shell` -- they do NOT re-test the SIGINT/SIGTERM/
SIGKILL ladder itself (Phase 4's `test_sigint_propagation.py` already does).

Both tests are POSIX-only (DA3 REFUSE on non-POSIX) and `pytest.mark.slow`
mirroring `test_sigint_propagation.py`. Per cycle-1 frontend-races P2-F +
product P2-E, the SIGINT-forwarding deadline is CI-flake-tolerant (3s)
even though the production target stays at 1s in `safe_run_long` defaults.
"""
from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
RUNNER = str(PLUGIN_SCRIPTS / "plugin-build-runner.py")
HASH_SCRIPT = str(PLUGIN_SCRIPTS / "plugin-config-hash.py")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX-only per Phase 5 DA3 + Phase 4 §8",
    ),
]


def _make_fixture(yaml_body: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase5-sigint-"))
    (d / ".launchpad").mkdir()
    (d / ".launchpad" / "config.yml").write_text(yaml_body, encoding="utf-8")
    return d


def _accepting_env(fixture: Path) -> dict:
    h = subprocess.run(
        [sys.executable, HASH_SCRIPT, f"--repo-root={fixture}"],
        capture_output=True, text=True,
    )
    env = dict(os.environ)
    env["LP_CONFIG_REVIEWED"] = h.stdout.strip()
    return env


def test_dev_stage_sigint_forwarded_child_exits_within_grace(tmp_path: Path):
    """SIGINT delivered to the runner is forwarded to the child via
    safe_run_long_shell's process-group ladder; child exits within 3s
    (CI-flake-tolerant; production target stays 1s in safe_run_long
    defaults)."""
    fixture = _make_fixture('commands:\n  dev:\n    - "sleep 30"\n')
    try:
        env = _accepting_env(fixture)
        runner_proc = subprocess.Popen(
            [sys.executable, RUNNER, "--stage=dev", f"--repo-root={fixture}"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        # Give the runner time to spawn the child sleep.
        time.sleep(1.0)
        # Deliver SIGINT to the runner's process group; safe_run_long_shell
        # ladders to the descendant sleep.
        os.killpg(runner_proc.pid, signal.SIGINT)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if runner_proc.poll() is not None:
                break
            time.sleep(0.05)
        assert runner_proc.poll() is not None, (
            "runner did not exit within 3s after SIGINT; "
            "safe_run_long_shell wiring did not propagate signal"
        )
        # SafeRunInterrupted -> exit 130 per DA2.
        assert runner_proc.returncode == 130, (
            f"expected exit 130 on SIGINT-after-cleanup, got "
            f"{runner_proc.returncode}"
        )
    finally:
        try:
            if runner_proc.poll() is None:
                runner_proc.kill()
                runner_proc.wait(timeout=2.0)
        except Exception:
            pass
        shutil.rmtree(fixture, ignore_errors=True)


def test_dev_stage_sigkill_ladder_handles_hung_child(tmp_path: Path):
    """A child that traps SIGINT + SIGTERM exhausts the safe_run_long
    grace window; the SIGKILL ladder still terminates it. Phase 5
    inherits the ladder verbatim from Phase 4 -- this test verifies the
    runner exit-code translation (SafeRunTimedOut -> 137) survives the
    wiring path."""
    # A python command that traps SIGINT + SIGTERM and sleeps; only SIGKILL
    # can stop it. Quote-safe within the YAML string body.
    trap_script = textwrap.dedent("""\
        python3 -c "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"
    """).strip()

    fixture = _make_fixture(
        f'commands:\n  dev:\n    - {trap_script!r}\n'
    )
    try:
        env = _accepting_env(fixture)
        # Tighten the SIGINT/SIGTERM grace so the test runs in a few seconds.
        env["LAUNCHPAD_SIGINT_TIMEOUT_S"] = "0.5"
        runner_proc = subprocess.Popen(
            [sys.executable, RUNNER, "--stage=dev", f"--repo-root={fixture}"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        time.sleep(1.5)  # let the child trap-handler take effect
        os.killpg(runner_proc.pid, signal.SIGINT)

        # Worst-case: ~0.5s SIGINT grace + 3.0s SIGTERM grace + 1.0s SIGKILL
        # poll = ~4.5s; pad to 8s for CI flake tolerance.
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if runner_proc.poll() is not None:
                break
            time.sleep(0.1)
        assert runner_proc.poll() is not None, (
            "runner did not exit even after the SIGKILL ladder; "
            "safe_run_long_shell did not terminate the trapped child"
        )
        # SafeRunInterrupted (after cleanup) -> 130 is the expected outcome
        # for the SIGINT path even when the child needed SIGKILL to die.
        # SafeRunTimedOut (psutil still reports survivors) -> 137. Either
        # is acceptable proof that the wiring translates correctly.
        assert runner_proc.returncode in (130, 137), (
            f"expected exit 130 or 137, got {runner_proc.returncode}"
        )
    finally:
        try:
            if runner_proc.poll() is None:
                runner_proc.kill()
                runner_proc.wait(timeout=2.0)
        except Exception:
            pass
        shutil.rmtree(fixture, ignore_errors=True)
