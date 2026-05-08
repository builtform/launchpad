"""Phase 5 v2.1 (DA4 + DA6) -- `plugin-config-loader.py --get-config-value`.

Fixture-based: every test seeds its own `.launchpad/config.yml` instead of
asserting against the production tree (per cycle-1 spec-flow P2-D). Output
is JSON-encoded; the test parses stdout via `json.loads`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
LOADER = str(PLUGIN_SCRIPTS / "plugin-config-loader.py")


def _make_fixture(yaml_body: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase5-getvalue-"))
    (d / ".launchpad").mkdir()
    (d / ".launchpad" / "config.yml").write_text(yaml_body, encoding="utf-8")
    return d


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def test_top_level_key_returns_json_encoded_value():
    fixture = _make_fixture("overwrite: force\n")
    try:
        r = _run([
            sys.executable, LOADER,
            f"--repo-root={fixture}",
            "--get-config-value=overwrite",
        ])
        assert r.returncode == 0, (
            f"top-level key should exit 0, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert json.loads(r.stdout.strip()) == "force"
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_nested_key_returns_json_encoded_array():
    fixture = _make_fixture(
        'commands:\n  test:\n    - "pnpm test"\n    - "pnpm typecheck"\n'
    )
    try:
        r = _run([
            sys.executable, LOADER,
            f"--repo-root={fixture}",
            "--get-config-value=commands.test",
        ])
        assert r.returncode == 0, (
            f"nested key should exit 0, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert json.loads(r.stdout.strip()) == ["pnpm test", "pnpm typecheck"]
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_deep_nested_key_via_fixture():
    """Fixture-based deep-nested test (NOT against production config.yml).
    Exercises a 3-segment dotted path through the `pipeline` section, which
    is preserved verbatim by the loader."""
    fixture = _make_fixture(
        "pipeline:\n  greenfield:\n    skip_brainstorm: true\n"
    )
    try:
        r = _run([
            sys.executable, LOADER,
            f"--repo-root={fixture}",
            "--get-config-value=pipeline.greenfield.skip_brainstorm",
        ])
        assert r.returncode == 0, (
            f"deep nested key should exit 0, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert json.loads(r.stdout.strip()) is True
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_missing_key_exits_two():
    fixture = _make_fixture('commands:\n  test: ["pnpm test"]\n')
    try:
        r = _run([
            sys.executable, LOADER,
            f"--repo-root={fixture}",
            "--get-config-value=commands.nonexistent",
        ])
        assert r.returncode == 2, (
            f"missing key should exit 2, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert "not found" in r.stderr, (
            f"missing-key error should mention 'not found'; stderr: {r.stderr!r}"
        )
        assert "commands.nonexistent" in r.stderr, (
            f"missing-key error should echo the full path; stderr: {r.stderr!r}"
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)


def test_get_config_value_takes_precedence_over_section():
    """DA6: when both --get-config-value and --section are passed, the
    former wins (no argparse mutex; first-wins precedence)."""
    fixture = _make_fixture("overwrite: skip\n")
    try:
        r = _run([
            sys.executable, LOADER,
            f"--repo-root={fixture}",
            "--get-config-value=overwrite",
            "--section=commands",
        ])
        assert r.returncode == 0, (
            f"precedence test should exit 0, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        # If --section won, output would be a commands dict; the assertion
        # below only passes when --get-config-value won.
        assert json.loads(r.stdout.strip()) == "skip", (
            f"--get-config-value did not win precedence; stdout: {r.stdout!r}"
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)
