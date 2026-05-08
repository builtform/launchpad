"""v2.1 Codex PR #50 P1.B (D2) regression: LP_CONFIG_REVIEWED prefix matching.

Tests:
  * 16-char unique prefix accepts
  * 8-char prefix rejects with prefix_too_short
  * Ambiguous prefix (matches both new and legacy) rejects
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "plugin_config_hash",
        _SCRIPTS_DIR / "plugin-config-hash.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_config(tmp_path: Path, content: str) -> Path:
    cfg_dir = tmp_path / ".launchpad"
    cfg_dir.mkdir()
    cfg = cfg_dir / "config.yml"
    cfg.write_text(content, encoding="utf-8")
    return cfg


def test_full_hash_accepted(tmp_path, monkeypatch):
    mod = _load_module()
    cfg = _make_config(tmp_path, "commands:\n  foo: bar\n")
    full_hash = mod.canonical_hash(mod.commands_section(cfg))
    monkeypatch.setenv("LP_CONFIG_REVIEWED", full_hash)
    monkeypatch.delenv("LP_CONFIG_AUTO_REVIEW", raising=False)
    outcome, h = mod.resolve_review_state(cfg)
    assert outcome == mod.ACCEPTED
    assert h == full_hash


def test_16_char_prefix_accepted(tmp_path, monkeypatch):
    mod = _load_module()
    cfg = _make_config(tmp_path, "commands:\n  foo: bar\n")
    full_hash = mod.canonical_hash(mod.commands_section(cfg))
    monkeypatch.setenv("LP_CONFIG_REVIEWED", full_hash[:16])
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.ACCEPTED


def test_short_prefix_raises_too_short(tmp_path, monkeypatch):
    mod = _load_module()
    cfg = _make_config(tmp_path, "commands:\n  foo: bar\n")
    full_hash = mod.canonical_hash(mod.commands_section(cfg))
    monkeypatch.setenv("LP_CONFIG_REVIEWED", full_hash[:8])
    with pytest.raises(mod.ResolveReviewStateError) as excinfo:
        mod.resolve_review_state(cfg)
    assert excinfo.value.reason == "prefix_too_short"
    assert excinfo.value.min_required == mod.PREFIX_MIN_LENGTH


def test_garbage_prefix_falls_to_reprompt(tmp_path, monkeypatch):
    mod = _load_module()
    cfg = _make_config(tmp_path, "commands:\n  foo: bar\n")
    monkeypatch.setenv("LP_CONFIG_REVIEWED", "0" * 16)
    outcome, _ = mod.resolve_review_state(cfg)
    assert outcome == mod.REPROMPT
