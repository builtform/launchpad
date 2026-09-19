from __future__ import annotations

import hashlib
import json
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
