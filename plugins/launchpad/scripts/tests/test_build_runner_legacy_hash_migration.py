"""Regression test for v2.0.1 BL-244 #1 (PR #41 cycle-12 #1 closure):
plugin-build-runner.check_ci_override now honors the v1.x legacy YAML hash
through the v2.0.x soak window.

Pre-fix shape: check_ci_override did its own raw-string compare against
_compute_hash, silently rejecting the v1.x legacy YAML hash even though
plugin-config-hash.py had a documented 5-branch migration truth table
honoring it. v1.x users with a valid LP_CONFIG_REVIEWED pin would be
refused on first v2.0 run.

Post-fix shape: check_ci_override delegates to plugin-config-hash.py
--resolve-review-state, which returns ACCEPTED for both the v2.0 hash
AND the v1.x legacy hash (with a soft-warn UX nudge for the legacy case).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import warnings
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_module(filename: str, mod_name: str):
    """Load a hyphenated CLI script via importlib."""
    src = _SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(mod_name, src)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setup_config(tmp_path: Path) -> Path:
    """Create a minimal .launchpad/config.yml with a commands section.
    Returns the repo root."""
    repo_root = tmp_path / "repo"
    (repo_root / ".launchpad").mkdir(parents=True)
    config = repo_root / ".launchpad" / "config.yml"
    config.write_text(
        "commands:\n"
        "  test:\n"
        "    - pnpm test\n"
        "  lint:\n"
        "    - eslint .\n"
        "  typecheck:\n"
        "    - tsc --noEmit\n",
        encoding="utf-8",
    )
    return repo_root


def test_v1_legacy_yaml_hash_accepted_v2_0_x(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """v1.x legacy YAML hash in LP_CONFIG_REVIEWED → check_ci_override returns 0
    (ACCEPTED) instead of 2 (refused). Per HANDSHAKE §3 5-branch truth table
    cell B (legacy match → soft-warn, non-blocking)."""
    repo_root = _setup_config(tmp_path)
    cfg_hash_mod = _load_module("plugin-config-hash.py", "plugin_config_hash")
    runner_mod = _load_module("plugin-build-runner.py", "plugin_build_runner")

    commands = cfg_hash_mod.commands_section(repo_root / ".launchpad" / "config.yml")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy_hash = cfg_hash_mod._legacy_yaml_canonical_hash(commands)

    # Sanity check: legacy hash MUST differ from new hash (otherwise no migration).
    new_hash = cfg_hash_mod.canonical_hash(commands)
    assert legacy_hash != new_hash, (
        "fixture must produce divergent hashes between schemes for the "
        "migration test to be meaningful"
    )

    monkeypatch.setenv("LP_CONFIG_REVIEWED", legacy_hash)
    rc = runner_mod.check_ci_override(repo_root)
    assert rc == 0, (
        f"v1.x legacy hash should be ACCEPTED through v2.0.x soak window; "
        f"got rc={rc}. Stderr: {capsys.readouterr().err!r}"
    )


def test_v2_0_new_hash_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """v2.0 new hash in LP_CONFIG_REVIEWED → check_ci_override returns 0."""
    repo_root = _setup_config(tmp_path)
    cfg_hash_mod = _load_module("plugin-config-hash.py", "plugin_config_hash")
    runner_mod = _load_module("plugin-build-runner.py", "plugin_build_runner")

    new_hash = cfg_hash_mod.canonical_hash(
        cfg_hash_mod.commands_section(repo_root / ".launchpad" / "config.yml")
    )
    monkeypatch.setenv("LP_CONFIG_REVIEWED", new_hash)
    assert runner_mod.check_ci_override(repo_root) == 0


def test_unset_env_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """LP_CONFIG_REVIEWED unset → REPROMPT_FIRST_TIME → check_ci_override
    returns 0 (allow unpinned interactive runs).

    Note: monkeypatch.delenv with raising=False handles cases where the
    parent environment may or may not have LP_CONFIG_REVIEWED set.
    LP_CONFIG_AUTO_REVIEW must also be unset to ensure the FIRST_TIME branch.
    """
    repo_root = _setup_config(tmp_path)
    monkeypatch.delenv("LP_CONFIG_REVIEWED", raising=False)
    monkeypatch.delenv("LP_CONFIG_AUTO_REVIEW", raising=False)
    runner_mod = _load_module("plugin-build-runner.py", "plugin_build_runner")
    assert runner_mod.check_ci_override(repo_root) == 0


def test_garbage_hash_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """LP_CONFIG_REVIEWED set to a value that matches NEITHER the v2.0 hash
    NOR the legacy hash → check_ci_override returns 2 (refuse) with the
    diagnostic mentioning both schemes."""
    repo_root = _setup_config(tmp_path)
    monkeypatch.setenv("LP_CONFIG_REVIEWED", "0" * 64)  # well-formed but wrong
    runner_mod = _load_module("plugin-build-runner.py", "plugin_build_runner")
    rc = runner_mod.check_ci_override(repo_root)
    assert rc == 2
    err = capsys.readouterr().err
    assert "REFUSE" in err
    assert "v2.0" in err and "legacy" in err, (
        f"refusal diagnostic must mention both schemes; got: {err!r}"
    )
