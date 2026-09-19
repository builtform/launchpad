from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_PLUGIN = _SCRIPTS.parent


def _copy_plugin(tmp_path: Path) -> Path:
    target = tmp_path / "installed plugin copy"
    shutil.copytree(
        _PLUGIN,
        target,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    return target


def _run(plugin: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(plugin / "scripts" / "plugin-codex-router.py"), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _canonical_hashes(plugin: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for dirname in ("commands", "agents", "skills"):
        hashes.update(
            {
                f"{dirname}/{path}": digest
                for path, digest in _hashes(plugin / dirname).items()
            }
        )
    return hashes


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0] == "---":
        try:
            end = lines.index("---", 1)
        except ValueError:
            return text.strip()
        return "\n".join(lines[end + 1 :]).strip()
    return text.strip()


def _duplicate_bodies(plugin: Path) -> list[tuple[str, str]]:
    canonical: dict[str, list[str]] = {}
    for dirname in ("commands", "agents", "skills"):
        for path in (plugin / dirname).rglob("*.md"):
            body = _body(path)
            if body:
                canonical.setdefault(body, []).append(str(path.relative_to(plugin)))

    duplicates: list[tuple[str, str]] = []
    for path in (plugin / "codex").rglob("*.md"):
        body = _body(path)
        for source in canonical.get(body, []):
            duplicates.append((str(path.relative_to(plugin)), source))
    return duplicates


def _ids(payload: dict) -> set[str]:
    return {item["id"] for item in payload["items"]}


def _named_canonical_references(plugin: Path) -> dict[str, list[str]]:
    contract_path = (
        plugin
        / "codex"
        / "skills"
        / "lp"
        / "references"
        / "host-adapter-contract.md"
    )
    skill_path = plugin / "codex" / "skills" / "lp" / "SKILL.md"
    contract = contract_path.read_text(encoding="utf-8")
    skill = skill_path.read_text(encoding="utf-8")

    grammar_example = next(
        line
        for line in skill.splitlines()
        if "Both `review` and `lp-review` resolve" in line
    )
    skill_without_exceptions = skill.replace(grammar_example, "").replace(
        "plugin-codex-router.py", ""
    )
    command_ids = {
        path.stem for path in (plugin / "commands").glob("*.md")
    }
    script_names = {
        path.name
        for path in (plugin / "scripts").iterdir()
        if path.is_file() and path.suffix in {".py", ".sh"}
    }

    def found(text: str, candidates: set[str]) -> list[str]:
        return sorted(
            candidate
            for candidate in candidates
            if re.search(
                rf"(?<![a-z0-9-]){re.escape(candidate)}(?![a-z0-9-])",
                text,
            )
        )

    return {
        "contract_commands": found(contract, command_ids),
        "contract_scripts": found(contract, script_names),
        "skill_commands": found(skill_without_exceptions, command_ids),
        "skill_scripts": found(skill_without_exceptions, script_names),
    }


def test_codex_tree_contains_no_canonical_body_copy() -> None:
    assert not (_PLUGIN / "codex" / "commands").exists()
    assert _duplicate_bodies(_PLUGIN) == []


def test_single_source_guard_detects_and_clears_both_mutations(tmp_path: Path) -> None:
    plugin = _copy_plugin(tmp_path)
    copied = plugin / "codex" / "skills" / "lp" / "references" / "probe.md"
    canonical = plugin / "commands" / "lp-hydrate.md"

    copied.write_text(_body(canonical), encoding="utf-8")
    assert _duplicate_bodies(plugin)
    copied.unlink()
    assert _duplicate_bodies(plugin) == []


def test_adapter_names_no_canonical_command_or_script(tmp_path: Path) -> None:
    plugin = _copy_plugin(tmp_path)
    contract = (
        plugin
        / "codex"
        / "skills"
        / "lp"
        / "references"
        / "host-adapter-contract.md"
    )
    skill = plugin / "codex" / "skills" / "lp" / "SKILL.md"
    assert _named_canonical_references(plugin) == {
        "contract_commands": [],
        "contract_scripts": [],
        "skill_commands": [],
        "skill_scripts": [],
    }

    contract_before = contract.read_text(encoding="utf-8")
    contract.write_text(
        contract_before + "\nRun lp-hydrate with plugin-config-loader.py.\n",
        encoding="utf-8",
    )
    mutated_contract = _named_canonical_references(plugin)
    assert mutated_contract["contract_commands"] == ["lp-hydrate"]
    assert mutated_contract["contract_scripts"] == ["plugin-config-loader.py"]
    contract.write_text(contract_before, encoding="utf-8")
    assert not any(_named_canonical_references(plugin).values())

    skill_before = skill.read_text(encoding="utf-8")
    skill.write_text(
        skill_before + "\nRun lp-hydrate with plugin-config-loader.py.\n",
        encoding="utf-8",
    )
    mutated_skill = _named_canonical_references(plugin)
    assert mutated_skill["skill_commands"] == ["lp-hydrate"]
    assert mutated_skill["skill_scripts"] == ["plugin-config-loader.py"]
    skill.write_text(skill_before, encoding="utf-8")
    assert not any(_named_canonical_references(plugin).values())


def test_dispatch_contract_distinguishes_named_and_inline_tasks() -> None:
    contract = (
        _PLUGIN
        / "codex"
        / "skills"
        / "lp"
        / "references"
        / "host-adapter-contract.md"
    ).read_text(encoding="utf-8")
    skill = (_PLUGIN / "codex" / "skills" / "lp" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for text in (contract, skill):
        assert "named specialist" in text
        assert "inline subagent task" in text
        assert "without inventing an agent name" in text or (
            "do not invent an agent name" in text
        )


def test_live_inventory_tracks_additions_and_removals_without_other_writes(
    tmp_path: Path,
) -> None:
    plugin = _copy_plugin(tmp_path)
    before = _hashes(plugin)

    command = plugin / "commands" / "lp-zzz-probe.md"
    skill = plugin / "skills" / "lp-zzz-probe" / "SKILL.md"
    agent = plugin / "agents" / "research" / "lp-zzz-probe.md"
    command.write_text(
        "---\nname: lp-zzz-probe\ndescription: Probe command\n---\n\n# Probe\n",
        encoding="utf-8",
    )
    skill.parent.mkdir()
    skill.write_text(
        "---\nname: lp-zzz-probe\ndescription: Probe skill\n---\n\n# Probe\n",
        encoding="utf-8",
    )
    agent.write_text(
        "---\nname: lp-zzz-probe\ndescription: Probe agent\n---\n\n# Probe\n",
        encoding="utf-8",
    )
    after_add = _hashes(plugin)
    added = {
        str(command.relative_to(plugin)),
        str(skill.relative_to(plugin)),
        str(agent.relative_to(plugin)),
    }
    assert set(after_add) - set(before) == added
    assert {path: after_add[path] for path in before} == before

    canonical_before_operations = _canonical_hashes(plugin)
    assert "lp-zzz-probe" in _ids(
        _run(plugin, "inventory", "--kind", "command", "--json")
    )
    assert "lp-zzz-probe" in _ids(
        _run(plugin, "inventory", "--kind", "skill", "--json")
    )
    assert "lp-zzz-probe" in _ids(
        _run(plugin, "inventory", "--kind", "agent", "--json")
    )
    _run(plugin, "resolve", "command", "lp-zzz-probe", "--json")
    _run(plugin, "resolve", "skill", "lp-zzz-probe", "--json")
    _run(plugin, "resolve", "agent", "lp-zzz-probe", "--json")
    _run(plugin, "lint", "--json")
    assert _canonical_hashes(plugin) == canonical_before_operations

    command.unlink()
    skill.unlink()
    agent.unlink()
    assert "lp-zzz-probe" not in _ids(
        _run(plugin, "inventory", "--kind", "command", "--json")
    )
    assert "lp-zzz-probe" not in _ids(
        _run(plugin, "inventory", "--kind", "skill", "--json")
    )
    assert "lp-zzz-probe" not in _ids(
        _run(plugin, "inventory", "--kind", "agent", "--json")
    )
