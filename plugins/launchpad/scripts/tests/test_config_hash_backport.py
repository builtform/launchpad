"""KAT pair for the plugin-config-hash.py JSON canonicalization backport.

Per HANDSHAKE §3:
  - Divergence KAT: _legacy_yaml_canonical_hash(fixture) != canonical_hash(fixture)
    proves the migration actually changed the output (otherwise no migration).
  - Cross-platform Linux KAT: canonical_hash output is consistent across Linux
    runners. (macOS leg per BL-233 deferred to v2.2; KAT runs on whatever
    platform Phase -1 dev happens — Darwin in this case — and the determinism
    of json.dumps + sort_keys is platform-independent.)
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_config_hash():
    """Load plugin-config-hash.py via importlib (hyphenated filename)."""
    src = _SCRIPTS / "plugin-config-hash.py"
    spec = importlib.util.spec_from_file_location("plugin_config_hash", src)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Pinned fixture — covers nested dict, list, str, int, None.
FIXTURE_COMMANDS = {
    "test": ["pnpm test"],
    "lint": ["eslint .", "pnpm prettier --check"],
    "build": ["turbo build"],
    "typecheck": ["tsc --noEmit"],
    "format": ["pnpm prettier --write"],
}


def test_divergence_kat_yaml_vs_json():
    """Migration must change the output: legacy YAML hash != new JSON hash."""
    mod = _load_config_hash()
    json_hash = mod.canonical_hash(FIXTURE_COMMANDS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yaml_hash = mod._legacy_yaml_canonical_hash(FIXTURE_COMMANDS)
    assert json_hash != yaml_hash


def test_legacy_emits_deprecation_warning():
    mod = _load_config_hash()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        mod._legacy_yaml_canonical_hash(FIXTURE_COMMANDS)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_canonical_hash_cross_module_equality():
    """The v1 module (this backport) and v2 module (decision_integrity.py)
    must produce identical bytes for the same payload."""
    mod_v1 = _load_config_hash()
    from decision_integrity import canonical_hash as v2_canonical_hash
    assert mod_v1.canonical_hash(FIXTURE_COMMANDS) == v2_canonical_hash(FIXTURE_COMMANDS)


def test_canonical_hash_deterministic():
    """Same input → same hash across calls (cross-platform parity proxy on
    a single host; the macOS KAT-leg matrix is BL-233 deferred)."""
    mod = _load_config_hash()
    h1 = mod.canonical_hash(FIXTURE_COMMANDS)
    h2 = mod.canonical_hash(FIXTURE_COMMANDS)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


# --- 5-branch LP_CONFIG_REVIEWED truth table ---

def test_review_unset_no_auto_review_reprompts(monkeypatch, tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("commands:\n  test: [pnpm test]\n")
    monkeypatch.delenv("LP_CONFIG_REVIEWED", raising=False)
    monkeypatch.delenv("LP_CONFIG_AUTO_REVIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)
    mod = _load_config_hash()
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.REPROMPT_FIRST_TIME


def test_review_matches_new_hash_accepted(monkeypatch, tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("commands:\n  test: [pnpm test]\n")
    mod = _load_config_hash()
    new_hash = mod.canonical_hash(mod.commands_section(cfg))
    monkeypatch.setenv("LP_CONFIG_REVIEWED", new_hash)
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.ACCEPTED


def test_review_matches_legacy_hash_accepted(monkeypatch, tmp_path: Path, capsys):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("commands:\n  test: [pnpm test]\n")
    mod = _load_config_hash()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = mod._legacy_yaml_canonical_hash(mod.commands_section(cfg))
    monkeypatch.setenv("LP_CONFIG_REVIEWED", legacy)
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.ACCEPTED
    # Soft-warn was emitted to stderr.
    captured = capsys.readouterr()
    assert "v2.0 changed how config-review" in captured.err


def test_review_neither_match_reprompts(monkeypatch, tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("commands:\n  test: [pnpm test]\n")
    monkeypatch.setenv("LP_CONFIG_REVIEWED", "0" * 64)
    mod = _load_config_hash()
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.REPROMPT


def test_auto_review_in_ci_accepted(monkeypatch, tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("commands:\n  test: [pnpm test]\n")
    monkeypatch.delenv("LP_CONFIG_REVIEWED", raising=False)
    monkeypatch.setenv("LP_CONFIG_AUTO_REVIEW", "1")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    mod = _load_config_hash()
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.ACCEPTED


def test_auto_review_outside_ci_rejected(monkeypatch, tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "config.yml"
    cfg.parent.mkdir()
    cfg.write_text("commands:\n  test: [pnpm test]\n")
    monkeypatch.delenv("LP_CONFIG_REVIEWED", raising=False)
    monkeypatch.setenv("LP_CONFIG_AUTO_REVIEW", "1")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    mod = _load_config_hash()
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.REPROMPT_AUTO_REVIEW_OUTSIDE_CI
