from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_PLUGIN = _SCRIPTS.parent
_ROUTER = _SCRIPTS / "plugin-codex-router.py"


def _frontmatter(name: str, description: str = "Fixture") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n"


def _plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "installed layout with space" / "launchpad"
    (plugin / "scripts").mkdir(parents=True)
    (plugin / "commands").mkdir()
    (plugin / "skills" / "lp-shared-skill").mkdir(parents=True)
    (plugin / "agents" / "research").mkdir(parents=True)
    shutil.copy2(_ROUTER, plugin / "scripts" / _ROUTER.name)
    (plugin / "commands" / "lp-alpha.md").write_text(
        _frontmatter("lp-alpha", "Alpha command"), encoding="utf-8"
    )
    (plugin / "skills" / "lp-shared-skill" / "SKILL.md").write_text(
        "---\n"
        "name: lp-shared-skill\n"
        "description: >\n"
        "  Folded description first line.\n"
        "  Folded description second line.\n"
        "---\n\n# Shared skill\n",
        encoding="utf-8",
    )
    (plugin / "agents" / "research" / "lp-shared-agent.md").write_text(
        _frontmatter("lp-shared-agent", "Built-in agent"), encoding="utf-8"
    )
    return plugin


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project root"
    (project / ".claude" / "skills" / "lp-project-skill").mkdir(parents=True)
    (project / ".claude" / "skills" / "lp-shared-skill").mkdir(parents=True)
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "skills" / "lp-project-skill" / "SKILL.md").write_text(
        "---\n"
        "name: lp-project-skill\n"
        "description: |\n"
        "  Literal first line.\n"
        "  Literal second line.\n"
        "---\n\n# Project skill\n",
        encoding="utf-8",
    )
    (project / ".claude" / "skills" / "lp-shared-skill" / "SKILL.md").write_text(
        _frontmatter("lp-shared-skill", "Project collision"), encoding="utf-8"
    )
    (project / ".claude" / "agents" / "lp-project-agent.md").write_text(
        _frontmatter("lp-project-agent", "Project agent"), encoding="utf-8"
    )
    (project / ".claude" / "agents" / "lp-shared-agent.md").write_text(
        _frontmatter("lp-shared-agent", "Project collision"), encoding="utf-8"
    )
    return project


def _invoke(router: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(router), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _ok(router: Path, *args: str) -> dict:
    result = _invoke(router, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _error(router: Path, *args: str) -> dict:
    result = _invoke(router, *args)
    assert result.returncode == 2, result.stdout
    return json.loads(result.stderr)["error"]


def test_installed_layout_with_space_and_block_scalars(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    router = plugin / "scripts" / _ROUTER.name

    command = _ok(router, "resolve", "command", "alpha", "--json")
    skill = _ok(router, "resolve", "skill", "lp-shared-skill", "--json")

    assert command["path"].startswith(str(plugin))
    assert skill["description"] == (
        "Folded description first line. Folded description second line."
    )
    assert "installed layout with space" in skill["path"]


def test_project_resolution_precedence_and_collision_reports(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    project = _project(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    project_args = ("--project-root", str(project), "--json")

    project_skill = _ok(
        router, "resolve", "skill", "lp-project-skill", *project_args
    )
    shared_skill = _ok(
        router, "resolve", "skill", "lp-shared-skill", *project_args
    )
    project_agent = _ok(
        router, "resolve", "agent", "lp-project-agent", *project_args
    )
    shared_agent = _ok(
        router, "resolve", "agent", "lp-shared-agent", *project_args
    )
    skill_inventory = _ok(
        router, "inventory", "--kind", "skill", *project_args
    )

    assert project_skill["origin"] == "project"
    assert project_skill["description"] == "Literal first line.\nLiteral second line."
    assert project_agent["origin"] == "project"
    assert shared_skill["origin"] == "built_in"
    assert shared_skill["collisions"][0]["origin"] == "project"
    assert shared_agent["origin"] == "built_in"
    assert shared_agent["collisions"][0]["origin"] == "project"
    assert {item["id"] for item in skill_inventory["collisions"]} == {
        "lp-shared-skill"
    }


@pytest.mark.parametrize("name", ("../lp-alpha", "lp.alpha", "/lp-alpha"))
def test_name_grammar_rejects_traversal_and_absolute_paths(
    tmp_path: Path, name: str
) -> None:
    plugin = _plugin(tmp_path)
    error = _error(
        plugin / "scripts" / _ROUTER.name,
        "resolve",
        "command",
        name,
        "--json",
    )
    assert error["code"] == "invalid_name"


@pytest.mark.parametrize("origin", ("built_in", "project"))
@pytest.mark.parametrize(
    ("case", "code"),
    (
        ("symlink", "symlink_rejected"),
        ("oversize", "oversize"),
        ("invalid_utf8", "invalid_utf8"),
        ("duplicate", "duplicate_id"),
        ("malformed", "malformed_frontmatter"),
    ),
)
def test_file_safety_negatives_per_allowed_origin(
    tmp_path: Path, origin: str, case: str, code: str
) -> None:
    plugin = _plugin(tmp_path)
    project = _project(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    root = (
        plugin / "skills"
        if origin == "built_in"
        else project / ".claude" / "skills"
    )

    if case == "duplicate":
        targets = [
            root / "one" / "lp-duplicate" / "SKILL.md",
            root / "two" / "lp-duplicate" / "SKILL.md",
        ]
        for target in targets:
            target.parent.mkdir(parents=True)
            target.write_text(_frontmatter("lp-duplicate"), encoding="utf-8")
    else:
        target = root / f"lp-{case}" / "SKILL.md"
        target.parent.mkdir(parents=True)
        if case == "symlink":
            outside = tmp_path / f"outside-{origin}.md"
            outside.write_text(_frontmatter(f"lp-{case}"), encoding="utf-8")
            os.symlink(outside, target)
        elif case == "oversize":
            target.write_text(
                _frontmatter(f"lp-{case}") + ("x" * 1_000_001),
                encoding="utf-8",
            )
        elif case == "invalid_utf8":
            target.write_bytes(b"---\nname: lp-invalid-utf8\n---\n\xff")
        else:
            target.write_text(
                f"---\nname: lp-{case}\ndescription: broken\n", encoding="utf-8"
            )

    args = ["inventory", "--kind", "skill"]
    if origin == "project":
        args.extend(["--project-root", str(project)])
    args.append("--json")
    error = _error(router, *args)
    assert error["code"] == code


def test_containment_guard_rejects_both_root_directions(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "plugin_codex_router_test", plugin / "scripts" / _ROUTER.name
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    first_root = plugin / "commands"
    second_root = tmp_path / "other-root"
    second_root.mkdir()
    first_file = first_root / "lp-alpha.md"
    second_file = second_root / "lp-beta.md"
    second_file.write_text(_frontmatter("lp-beta"), encoding="utf-8")

    with pytest.raises(module.RouterError) as first_error:
        module._safe_text(second_file, first_root)
    with pytest.raises(module.RouterError) as second_error:
        module._safe_text(first_file, second_root)
    assert first_error.value.code == "outside_root"
    assert second_error.value.code == "outside_root"


def test_relative_project_root_and_unknown_kind_have_stable_codes(
    tmp_path: Path,
) -> None:
    plugin = _plugin(tmp_path)
    router = plugin / "scripts" / _ROUTER.name

    relative = _error(
        router,
        "inventory",
        "--kind",
        "skill",
        "--project-root",
        "relative/path",
        "--json",
    )
    unsupported = _error(router, "inventory", "--kind", "widget", "--json")
    assert relative["code"] == "invalid_project_root"
    assert unsupported["code"] == "unsupported_kind"


def test_project_extension_root_symlink_is_rejected(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    project = tmp_path / "symlinked-project-extension"
    outside = tmp_path / "outside-skills"
    (project / ".claude").mkdir(parents=True)
    outside.mkdir()
    os.symlink(outside, project / ".claude" / "skills")

    error = _error(
        router,
        "inventory",
        "--kind",
        "skill",
        "--project-root",
        str(project),
        "--json",
    )
    assert error["code"] == "unsafe_root"


def test_lint_passes_current_corpus() -> None:
    payload = _ok(_ROUTER, "lint", "--json")
    assert payload["status"] == "ok"
    assert "${CLAUDE_PLUGIN_ROOT}" in payload["known_tokens"]


def test_lint_rejects_planted_unknown_host_token(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    command = plugin / "commands" / "lp-alpha.md"
    command.write_text(
        command.read_text(encoding="utf-8") + "\n${CLAUDE_UNMAPPED}\n",
        encoding="utf-8",
    )

    error = _error(router, "lint", "--json")
    assert error["code"] == "unknown_host_token"
    assert error["tokens"] == ["${CLAUDE_UNMAPPED}"]
    assert error["message"] == "add a contract row and a known-token entry"
