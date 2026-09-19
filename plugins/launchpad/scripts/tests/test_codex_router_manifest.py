from __future__ import annotations

import json
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_PLUGIN = _SCRIPTS.parent


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_manifests_share_full_identity() -> None:
    claude = _json(_PLUGIN / ".claude-plugin" / "plugin.json")
    codex = _json(_PLUGIN / ".codex-plugin" / "plugin.json")

    shared_fields = (
        "name",
        "description",
        "version",
        "author",
        "license",
        "homepage",
        "repository",
    )
    assert {field: codex[field] for field in shared_fields} == {
        field: claude[field] for field in shared_fields
    }
    assert codex["skills"] == "./codex/skills/"


def test_codex_manifest_exposes_only_router_skill_directory() -> None:
    codex = _json(_PLUGIN / ".codex-plugin" / "plugin.json")
    skill_root = (_PLUGIN / codex["skills"]).resolve(strict=True)
    directories = {path.name for path in skill_root.iterdir() if path.is_dir()}

    assert directories == {"lp"}
    assert (skill_root / "lp" / "SKILL.md").is_file()
    assert not (_PLUGIN / "codex" / "commands").exists()


def test_contract_covers_helper_known_host_tokens() -> None:
    contract = (
        _PLUGIN
        / "codex"
        / "skills"
        / "lp"
        / "references"
        / "host-adapter-contract.md"
    ).read_text(encoding="utf-8")

    for token in (
        "${CLAUDE_PLUGIN_ROOT}",
        "AskUserQuestion",
        "allowed-tools",
        "mcp__*",
        "subagent_type",
    ):
        assert token in contract
