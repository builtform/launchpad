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
_ORCHESTRATION_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "codex_thin_adapter"
)


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


def _record_identity(record: dict) -> dict:
    return {
        key: record[key]
        for key in ("description", "id", "kind", "origin", "path")
    }


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


def test_short_and_full_names_resolve_to_same_built_in_records(
    tmp_path: Path,
) -> None:
    plugin = _plugin(tmp_path)
    router = plugin / "scripts" / _ROUTER.name

    for kind, short_name in (
        ("command", "alpha"),
        ("skill", "shared-skill"),
        ("agent", "shared-agent"),
    ):
        short = _ok(router, "resolve", kind, short_name, "--json")
        full = _ok(router, "resolve", kind, f"lp-{short_name}", "--json")
        assert _record_identity(short) == _record_identity(full)


def test_exact_built_in_short_name_precedes_prefixed_built_in_and_project(
    tmp_path: Path,
) -> None:
    plugin = _plugin(tmp_path)
    project = _project(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    built_in = plugin / "agents" / "research" / "shared-agent.md"
    project_agent = project / ".claude" / "agents" / "shared-agent.md"
    built_in.write_text(_frontmatter("shared-agent", "Exact built-in"), encoding="utf-8")
    project_agent.write_text(
        _frontmatter("shared-agent", "Exact project"), encoding="utf-8"
    )

    resolved = _ok(
        router,
        "resolve",
        "agent",
        "shared-agent",
        "--project-root",
        str(project),
        "--json",
    )

    assert resolved["path"] == str(built_in)
    assert resolved["collisions"] == [
        {"origin": "project", "path": str(project_agent)}
    ]


@pytest.mark.parametrize("kind", ("skill", "agent"))
def test_project_short_name_collision_appears_and_clears_by_mutation(
    tmp_path: Path, kind: str
) -> None:
    plugin = _plugin(tmp_path)
    project = _project(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    short_name = f"shared-{kind}"
    project_args = ("--project-root", str(project), "--json")
    if kind == "skill":
        target = project / ".claude" / "skills" / short_name / "SKILL.md"
        target.parent.mkdir()
    else:
        target = project / ".claude" / "agents" / f"{short_name}.md"

    before = _ok(router, "resolve", kind, short_name, *project_args)
    assert before["origin"] == "built_in"
    assert all(item["path"] != str(target) for item in before["collisions"])

    target.write_text(_frontmatter(short_name, "Short collision"), encoding="utf-8")
    during = _ok(router, "resolve", kind, short_name, *project_args)
    assert during["origin"] == "built_in"
    assert {item["path"] for item in during["collisions"]} >= {str(target)}

    target.unlink()
    after = _ok(router, "resolve", kind, short_name, *project_args)
    assert _record_identity(after) == _record_identity(before)
    assert all(item["path"] != str(target) for item in after["collisions"])


def test_unknown_short_name_returns_suggestions_without_writes(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    project = _project(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    before = {
        path: path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }

    error = _error(
        router,
        "resolve",
        "skill",
        "shared-skll",
        "--project-root",
        str(project),
        "--json",
    )

    after = {
        path: path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert error["code"] == "not_found"
    assert error["suggestions"] == ["lp-shared-skill"]
    assert after == before


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
        case_id = case.replace("_", "-")
        target = root / f"lp-{case_id}" / "SKILL.md"
        target.parent.mkdir(parents=True)
        if case == "symlink":
            outside = tmp_path / f"outside-{origin}.md"
            outside.write_text(_frontmatter(f"lp-{case_id}"), encoding="utf-8")
            os.symlink(outside, target)
        elif case == "oversize":
            target.write_text(
                _frontmatter(f"lp-{case_id}") + ("x" * 1_000_001),
                encoding="utf-8",
            )
        elif case == "invalid_utf8":
            target.write_bytes(b"---\nname: lp-invalid-utf8\n---\n\xff")
        else:
            target.write_text(
                f"---\nname: lp-{case}\ndescription: broken\n", encoding="utf-8"
            )

    args = ["inventory", "--kind", "skill"]
    if origin == "built_in":
        args.append("--json")
        error = _error(router, *args)
        assert error["code"] == code
        return

    args.extend(["--project-root", str(project), "--json"])
    payload = _ok(router, *args)
    assert code in {item["code"] for item in payload["skipped"]}

    requested_id = f"lp-{case.replace('_', '-')}"
    error = _error(
        router,
        "resolve",
        "skill",
        requested_id,
        "--project-root",
        str(project),
        "--json",
    )
    assert error["code"] == code


def _plant_project_agent_problem(
    root: Path, tmp_path: Path, case: str
) -> tuple[str | None, str, list[Path]]:
    if case == "readme":
        target = root / "README.md"
        target.write_text("Project-specific agent notes.\n", encoding="utf-8")
        return None, "invalid_id", [target]
    if case == "malformed":
        target = root / "lp-malformed.md"
        target.write_text("---\nname: lp-malformed\n", encoding="utf-8")
        return "lp-malformed", "malformed_frontmatter", [target]
    if case == "invalid_utf8":
        target = root / "lp-invalid-utf8.md"
        target.write_bytes(b"---\nname: lp-invalid-utf8\n---\n\xff")
        return "lp-invalid-utf8", "invalid_utf8", [target]
    if case == "symlink":
        target = root / "lp-symlink.md"
        outside = tmp_path / "outside-agent.md"
        outside.write_text(_frontmatter("lp-symlink"), encoding="utf-8")
        os.symlink(outside, target)
        return "lp-symlink", "symlink_rejected", [target]
    targets = [
        root / "one" / "lp-duplicate.md",
        root / "two" / "lp-duplicate.md",
    ]
    for target in targets:
        target.parent.mkdir()
        target.write_text(_frontmatter("lp-duplicate"), encoding="utf-8")
    return "lp-duplicate", "duplicate_id", targets


@pytest.mark.parametrize(
    "case", ("readme", "malformed", "invalid_utf8", "symlink", "duplicate")
)
def test_project_agent_problems_are_skipped_for_unaffected_resolutions(
    tmp_path: Path, case: str
) -> None:
    plugin = _plugin(tmp_path)
    project = _project(tmp_path)
    router = plugin / "scripts" / _ROUTER.name
    agent_root = project / ".claude" / "agents"
    project_args = ("--project-root", str(project), "--json")

    before = _ok(router, "inventory", "--kind", "agent", *project_args)
    assert before["skipped"] == []

    requested_id, code, targets = _plant_project_agent_problem(
        agent_root, tmp_path, case
    )
    inventory = _ok(router, "inventory", "--kind", "agent", *project_args)
    valid_project = _ok(
        router, "resolve", "agent", "lp-project-agent", *project_args
    )
    valid_built_in = _ok(
        router, "resolve", "agent", "lp-shared-agent", *project_args
    )

    skipped = inventory["skipped"]
    assert {item["code"] for item in skipped} == {code}
    assert {item["path"] for item in skipped} == {str(path) for path in targets}
    assert valid_project["origin"] == "project"
    assert valid_project["skipped"] == skipped
    assert valid_built_in["origin"] == "built_in"
    assert valid_built_in["skipped"] == skipped
    if requested_id is not None:
        error = _error(
            router, "resolve", "agent", requested_id, *project_args
        )
        assert error["code"] == code

    for target in targets:
        target.unlink()
    after = _ok(router, "inventory", "--kind", "agent", *project_args)
    assert after["skipped"] == []


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


def test_orchestration_fixture_prepares_messy_project(tmp_path: Path) -> None:
    source_project = _ORCHESTRATION_FIXTURE / "project"
    prepared = tmp_path / "prepared fixture"
    nonce = "SECTION4_HYDRATE_NONCE_TEST"

    assert not any(path.name == ".git" for path in source_project.rglob("*"))
    assert (source_project / "CLAUDE.md").read_text(encoding="utf-8") == (
        "This is an inert test fixture and contains no instructions.\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_ORCHESTRATION_FIXTURE / "prepare_fixture.py"),
            "--output",
            str(prepared),
            "--nonce",
            nonce,
            "--plan-path",
            "docs/plans/fixture-plan.md",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "nonce": nonce,
        "plan_path": str(prepared / "docs" / "plans" / "fixture-plan.md"),
        "project_root": str(prepared),
        "seeded_diff": "CLAUDE.md",
    }
    assert nonce in (prepared / "docs" / "tasks" / "BACKLOG.md").read_text(
        encoding="utf-8"
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=prepared,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert status.stdout.splitlines() == [" M CLAUDE.md"]
    assert "# Fixture plan" in (
        prepared / "docs" / "plans" / "fixture-plan.md"
    ).read_text(encoding="utf-8")

    project_args = ("--project-root", str(prepared), "--json")
    agent = _ok(_ROUTER, "resolve", "agent", "fixture-reviewer", *project_args)
    inventory = _ok(_ROUTER, "inventory", "--kind", "agent", *project_args)
    assert agent["origin"] == "project"
    assert Path(agent["path"]).name == "fixture-reviewer.md"
    assert {item["code"] for item in agent["skipped"]} == {"invalid_id"}
    assert {Path(item["path"]).name for item in inventory["skipped"]} == {
        "README.md"
    }

    roster_text = (prepared / ".launchpad" / "agents.yml").read_text(
        encoding="utf-8"
    )
    assert "review_agents:\n  - fixture-reviewer\n" in roster_text
    assert "review_document_agents:\n  - lp-document-truth\n" in roster_text
    assert "review_document_artifacts:\n  - CLAUDE.md\n" in roster_text
    document_agent = _ok(
        _ROUTER, "resolve", "agent", "lp-document-truth", *project_args
    )
    assert document_agent["origin"] == "built_in"

    scope_filter_path = _SCRIPTS / "plugin-agent-scope-filter.py"
    spec = importlib.util.spec_from_file_location("fixture_scope_filter", scope_filter_path)
    assert spec and spec.loader
    scope_filter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scope_filter)
    filtered = scope_filter.filter_agents_by_stacks(
        ["fixture-reviewer"],
        [],
        prevalidated_project_scopes={"fixture-reviewer": "stack:any"},
        raise_on_no_match=True,
    )
    assert filtered == ["fixture-reviewer"]


def test_acceptance_fixture_prepares_distinct_probe_plugin(tmp_path: Path) -> None:
    marketplace = tmp_path / "probe marketplace"
    plugin = marketplace / "plugins" / "launchpad-pa4"
    probe_output = tmp_path / "probe-result.txt"
    nonce = "SECTION5_PA4_NONCE_TEST"
    source_skill = (_PLUGIN / "codex" / "skills" / "lp" / "SKILL.md").read_bytes()
    source_helper = (_PLUGIN / "scripts" / _ROUTER.name).read_bytes()
    source_commands = {path.name for path in (_PLUGIN / "commands").glob("*.md")}

    result = subprocess.run(
        [
            sys.executable,
            str(_ORCHESTRATION_FIXTURE / "prepare_fixture.py"),
            "--plugin-source",
            str(_PLUGIN),
            "--plugin-output",
            str(plugin),
            "--plugin-name",
            "launchpad-pa4",
            "--probe-output",
            str(probe_output),
            "--probe-nonce",
            nonce,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["invocation"] == f"$launchpad-pa4:lp zzz-probe {nonce}"
    assert payload["marketplace_name"] == "launchpad-pa4-marketplace"
    assert payload["marketplace_root"] == str(marketplace)
    assert payload["plugin_root"] == str(plugin)
    assert payload["probe_output"] == str(probe_output)

    for manifest_name in (
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
    ):
        source_manifest = json.loads(
            (_PLUGIN / manifest_name).read_text(encoding="utf-8")
        )
        probe_manifest = json.loads(
            (plugin / manifest_name).read_text(encoding="utf-8")
        )
        assert probe_manifest.pop("name") == "launchpad-pa4"
        source_manifest.pop("name")
        assert probe_manifest == source_manifest

    assert (plugin / "codex" / "skills" / "lp" / "SKILL.md").read_bytes() == (
        source_skill
    )
    assert (plugin / "scripts" / _ROUTER.name).read_bytes() == source_helper
    assert {path.name for path in (plugin / "commands").glob("*.md")} == (
        source_commands | {"lp-zzz-probe.md"}
    )
    probe_text = (plugin / "commands" / "lp-zzz-probe.md").read_text(
        encoding="utf-8"
    )
    assert nonce in probe_text
    assert str(probe_output) in probe_text
    assert "A trailing newline is allowed." in probe_text
    assert "with no trailing newline" not in probe_text
    probe_output.write_text(f"{nonce}\n", encoding="utf-8")
    assert probe_output.read_text(encoding="utf-8").strip() == nonce
    assert not (_PLUGIN / "commands" / "lp-zzz-probe.md").exists()
