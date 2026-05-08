"""Phase 5 v2.1 (DA1 + DA8 + DA9) -- `dev` stage acceptance, multi-command
refuse, and LP_CONFIG_REVIEWED hash-pin coverage.

Covers Slice A surface only: argparse + check-only + skip + multi-command
refuse + hash-pin participation. Single-element execution + signal-ladder
exit codes live in `test_build_runner_sigint.py` (Slice C).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
RUNNER = str(PLUGIN_SCRIPTS / "plugin-build-runner.py")
HASH_SCRIPT = str(PLUGIN_SCRIPTS / "plugin-config-hash.py")


def _make_fixture(yaml_body: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase5-dev-"))
    (d / ".launchpad").mkdir()
    (d / ".launchpad" / "config.yml").write_text(yaml_body, encoding="utf-8")
    return d


def _run(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, env=env)


def _accepting_env(fixture: Path) -> dict:
    """Compute the current commands-section hash and seed LP_CONFIG_REVIEWED."""
    h = _run([sys.executable, HASH_SCRIPT, f"--repo-root={fixture}"])
    env = dict(os.environ)
    env["LP_CONFIG_REVIEWED"] = h.stdout.strip()
    return env


def test_dev_accepted_by_argparse_and_check_only_covers_dev():
    """DA1 + DA5: 'dev' is in VALID_STAGES so argparse accepts it AND
    `--check-only` validates `commands.dev` automatically (existing
    --check-only branch iterates VALID_STAGES)."""
    fixture = _make_fixture('commands:\n  dev: ["pnpm dev"]\n')
    try:
        env = _accepting_env(fixture)
        r = _run(
            [sys.executable, RUNNER, "--stage=dev",
             f"--repo-root={fixture}", "--check-only"],
            env=env,
        )
        assert r.returncode == 0, (
            f"--check-only --stage=dev should exit 0, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert "dev=1" in r.stderr, (
            f"--check-only summary should mention dev count; stderr: {r.stderr[:400]}"
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_empty_commands_dev_skips_silently():
    """DA1: `commands.dev: []` returns the standard skip-marker exit 0."""
    fixture = _make_fixture("commands:\n  dev: []\n")
    try:
        env = _accepting_env(fixture)
        r = _run(
            [sys.executable, RUNNER, "--stage=dev", f"--repo-root={fixture}"],
            env=env,
        )
        assert r.returncode == 0, (
            f"empty commands.dev should exit 0, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert "skipped" in r.stderr.lower(), (
            f"empty commands.dev should print skip marker; stderr: {r.stderr!r}"
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_multi_element_commands_dev_refused_at_preflight():
    """DA8: `commands.dev: ["a", "b"]` is refused with locked error message."""
    fixture = _make_fixture(
        "commands:\n  dev:\n    - \"true\"\n    - \"echo should-not-run\"\n"
    )
    try:
        env = _accepting_env(fixture)
        r = _run(
            [sys.executable, RUNNER, "--stage=dev", f"--repo-root={fixture}"],
            env=env,
        )
        assert r.returncode == 2, (
            f"multi-element commands.dev should exit 2, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert "must contain at most 1 entry" in r.stderr, (
            f"locked multi-element error not present; stderr: {r.stderr!r}"
        )
        assert "got 2" in r.stderr, (
            f"locked error should report observed N; stderr: {r.stderr!r}"
        )
        assert "concurrently" in r.stderr or "npm-run-all" in r.stderr, (
            f"locked error should suggest orchestrator tool; stderr: {r.stderr!r}"
        )
        assert "should-not-run" not in r.stderr, (
            "second command was executed despite preflight refusal"
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_lp_config_reviewed_hash_pin_includes_commands_dev():
    """DA9: mutating `commands.dev` triggers an LP_CONFIG_REVIEWED mismatch
    on subsequent runs (proof that the canonical hash includes the new
    closed-enum key)."""
    fixture = _make_fixture('commands:\n  test: ["true"]\n  dev: ["pnpm dev"]\n')
    try:
        env = _accepting_env(fixture)
        baseline_hash = env["LP_CONFIG_REVIEWED"]

        # Mutate commands.dev only -- everything else identical.
        (fixture / ".launchpad" / "config.yml").write_text(
            'commands:\n  test: ["true"]\n  dev: ["pnpm start"]\n',
            encoding="utf-8",
        )

        h2 = _run([sys.executable, HASH_SCRIPT, f"--repo-root={fixture}"])
        new_hash = h2.stdout.strip()
        assert new_hash != baseline_hash, (
            "canonical hash did not change after mutating commands.dev; "
            "hash-pin does not cover the new closed-enum key"
        )

        # Stale hash should now refuse loudly.
        r = _run(
            [sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"],
            env=env,
        )
        assert r.returncode == 2, (
            f"stale LP_CONFIG_REVIEWED after commands.dev mutation should exit 2, "
            f"got {r.returncode}. stderr: {r.stderr[:400]}"
        )
        assert "REFUSE" in r.stderr, (
            f"stale hash should refuse loudly; stderr: {r.stderr[:400]}"
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)
