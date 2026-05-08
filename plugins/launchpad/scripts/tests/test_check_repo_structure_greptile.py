"""v2.1 Codex PR #50 P1.C (D3) regression: .greptile.json whitelist.

Tests:
  * Both root and template scripts whitelist `.greptile.json`
  * The hidden-file regex accepts `.greptile.json` as common config
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_root_script_lists_greptile_json():
    script = REPO_ROOT / "scripts" / "maintenance" / "check-repo-structure.sh"
    text = script.read_text(encoding="utf-8")
    assert '".greptile.json"' in text


def test_template_script_lists_greptile_json():
    template = (
        REPO_ROOT
        / "plugins"
        / "launchpad"
        / "scripts"
        / "plugin_default_generators"
        / "infrastructure"
        / "scripts"
        / "maintenance"
        / "check-repo-structure.sh.j2"
    )
    text = template.read_text(encoding="utf-8")
    assert '".greptile.json"' in text


def test_root_script_has_greptile_in_hidden_regex():
    script = REPO_ROOT / "scripts" / "maintenance" / "check-repo-structure.sh"
    text = script.read_text(encoding="utf-8")
    assert "greptile\\.json" in text


def test_template_script_has_greptile_in_hidden_regex():
    template = (
        REPO_ROOT
        / "plugins"
        / "launchpad"
        / "scripts"
        / "plugin_default_generators"
        / "infrastructure"
        / "scripts"
        / "maintenance"
        / "check-repo-structure.sh.j2"
    )
    text = template.read_text(encoding="utf-8")
    assert "greptile\\.json" in text
