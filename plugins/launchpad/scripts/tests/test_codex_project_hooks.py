"""Behavioral contract tests for the repository-local Codex hooks."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
HOOK_CONFIG = REPOSITORY_ROOT / ".codex" / "hooks.json"
STRUCTURE_CHECK = (
    REPOSITORY_ROOT / "scripts" / "maintenance" / "check-repo-structure.sh"
)
HYDRATE = REPOSITORY_ROOT / "scripts" / "agent_hydration" / "hydrate.sh"
DRIFT = REPOSITORY_ROOT / "scripts" / "maintenance" / "detect-structure-drift.sh"
BLOCK_MERGES = REPOSITORY_ROOT / ".claude" / "hooks" / "block-merges.sh"
CONTRIBUTING = REPOSITORY_ROOT / "CONTRIBUTING.md"
SECURITY = REPOSITORY_ROOT / "SECURITY.md"

SESSION_COMMAND = (
    'bash "$(git rev-parse --show-toplevel)/scripts/agent_hydration/hydrate.sh" '
    '--project-root "$(git rev-parse --show-toplevel)"'
)
PRE_TOOL_COMMAND = (
    'bash "$(git rev-parse --show-toplevel)/.claude/hooks/block-merges.sh"'
)


def _copy(source: Path, root: Path, relative: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _markdown_section(path: Path, heading: str, *, level: int = 3) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "#" * level
    match = re.search(
        rf"^{marker} {re.escape(heading)}\s*$\n"
        rf"(?P<body>.*?)(?=^#{{1,{level}}} |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing documentation section: {heading}"
    return match.group("body")


def _numbered_item(section: str, number: int) -> str:
    match = re.search(
        rf"^{number}\.\s+(?P<body>.*?)(?=^\d+\.\s+|\Z)",
        section,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing numbered documentation item: {number}"
    return match.group("body")


def _normalized(text: str) -> str:
    return " ".join(text.split()).lower()


def _assert_codex_dispatch_is_trust_qualified(text: str) -> None:
    dispatch_action = re.compile(
        r"\b(?:activ(?:e|ates?|ated)|dispatch(?:es|ed)?|enabl(?:e|es|ed)|"
        r"fires?|invok(?:e|es|ed)|loads?|runs?|executes?)\b"
    )
    trust_qualification = re.compile(
        r"\bconditional\b|\bonly (?:after|if|when)\b|"
        r"\b(?:requires?|subject to)\b[^.]*\btrust|"
        r"\breviewed and trusted\b|"
        r"\b(?:does not|cannot|never)\b[^.]*\b(?:dispatch|invoke|load|run|execute)"
    )
    claims = [
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if "codex" in sentence and dispatch_action.search(sentence)
    ]

    assert claims
    assert all(trust_qualification.search(claim) for claim in claims)


def _fixture_repo(root: Path) -> Path:
    root.mkdir(parents=True)
    _copy(HOOK_CONFIG, root, ".codex/hooks.json")
    _copy(STRUCTURE_CHECK, root, "scripts/maintenance/check-repo-structure.sh")
    _copy(HYDRATE, root, "scripts/agent_hydration/hydrate.sh")
    _copy(DRIFT, root, "scripts/maintenance/detect-structure-drift.sh")
    _copy(BLOCK_MERGES, root, ".claude/hooks/block-merges.sh")
    subprocess.run(
        ["git", "init", "-q"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return root


def _configured_command(root: Path, event: str) -> str:
    payload = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    return payload["hooks"][event][0]["hooks"][0]["command"]


def _run_configured_hook(
    root: Path,
    event: str,
    *,
    input_text: str = "",
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    return subprocess.run(
        ["bash", "-c", _configured_command(root, event)],
        cwd=root,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_codex_hook_config_has_the_required_events_matchers_and_commands() -> None:
    payload = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert set(payload) == {"description", "hooks"}
    assert "reviewed and trusted" in payload["description"]
    assert payload["hooks"] == {
        "SessionStart": [
            {
                "matcher": "^(startup|resume|clear|compact)$",
                "hooks": [
                    {
                        "type": "command",
                        "command": SESSION_COMMAND,
                        "timeout": 30,
                        "statusMessage": "Loading LaunchPad project context",
                    }
                ],
            }
        ],
        "PreToolUse": [
            {
                "matcher": "^Bash$",
                "hooks": [
                    {
                        "type": "command",
                        "command": PRE_TOOL_COMMAND,
                        "timeout": 30,
                        "statusMessage": "Checking LaunchPad repository policy",
                    }
                ],
            }
        ],
    }


def test_public_docs_qualify_codex_hook_dispatch_as_trust_dependent() -> None:
    contributing = _normalized(
        _markdown_section(CONTRIBUTING, "Multi-layer merge prevention")
    )
    security = _normalized(
        _numbered_item(
            _markdown_section(SECURITY, "What the harness controls", level=2),
            1,
        )
    )

    assert "assumes all three are active" not in contributing
    assert re.search(r"configuration and handlers? are locally validated", contributing)
    assert re.search(r"project `\.codex/` layer is trusted", contributing)
    assert re.search(r"exact hook definition is reviewed and trusted", contributing)
    assert re.search(r"branch protection independently enforces", contributing)

    for document in (contributing, security):
        assert re.search(r"\bconfiguration\b", document)
        assert re.search(
            r"\blocal(?:ly)?\b[^.]*\bhandlers?\b|\bhandlers?\b[^.]*\blocal", document
        )
        assert re.search(
            r"exact (?:hook )?definition[^.]*reviewed and trusted", document
        )
        assert re.search(
            r"repository validation[^.]*\b(?:does not|cannot|but not)\b[^.]*host dispatch",
            document,
        )
        assert re.search(r"branch protection[^.]*server-side", document)
        _assert_codex_dispatch_is_trust_qualified(document)


def test_structure_validation_rejects_a_missing_required_codex_config(
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "repo")
    (root / ".codex" / "hooks.json").unlink()
    result = subprocess.run(
        ["bash", "scripts/maintenance/check-repo-structure.sh"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Required .codex/hooks.json is missing" in result.stdout


def test_structure_validation_accepts_the_required_codex_config(
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "repo")
    result = subprocess.run(
        ["bash", "scripts/maintenance/check-repo-structure.sh"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "configuration and local handlers are valid" in result.stdout
    assert "Host dispatch remains subject" in result.stdout


@pytest.mark.parametrize(
    "malformed",
    (
        "{",
        '{"hooks": {}}',
        '{"hooks": {"SessionStart": [], "PreToolUse": []}}',
    ),
)
def test_structure_validation_rejects_malformed_codex_config(
    malformed: str,
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "repo")
    (root / ".codex" / "hooks.json").write_text(malformed, encoding="utf-8")
    result = subprocess.run(
        ["bash", "scripts/maintenance/check-repo-structure.sh"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "invalid or non-portable .codex/hooks.json" in result.stdout


def test_structure_validation_rejects_unknown_codex_config_fields(
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "repo")
    hooks_path = root / ".codex" / "hooks.json"
    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    payload["disabled"] = True
    hooks_path.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        ["bash", "scripts/maintenance/check-repo-structure.sh"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "invalid or non-portable .codex/hooks.json" in result.stdout


@pytest.mark.parametrize(
    ("input_text", "expected_status"),
    (
        ('{"tool_input":{"command":"git merge main"}}', 2),
        ('{"tool_input":{"command":"git merge origin/main"}}', 0),
        ('{"tool_input":{"command":"   "}}', 2),
        ('{"tool_input":{}}', 2),
        ('{"tool_input":', 2),
        ("", 2),
    ),
)
def test_configured_pre_tool_hook_blocks_policy_and_fails_closed(
    input_text: str,
    expected_status: int,
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "repo")
    result = _run_configured_hook(root, "PreToolUse", input_text=input_text)
    assert result.returncode == expected_status


def test_codex_session_hook_ignores_hostile_claude_project_dir(
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "trusted")
    (root / "docs" / "tasks").mkdir(parents=True)
    (root / "docs" / "tasks" / "BACKLOG.md").write_text(
        "TRUSTED BACKLOG\n", encoding="utf-8"
    )
    (root / "docs" / "architecture").mkdir(parents=True)
    (root / "docs" / "architecture" / "REPOSITORY_STRUCTURE.md").write_text(
        "Fixture structure\n", encoding="utf-8"
    )
    (root / "apps" / "unlisted").mkdir(parents=True)

    hostile = tmp_path / "hostile"
    (hostile / "docs" / "tasks").mkdir(parents=True)
    (hostile / "docs" / "tasks" / "BACKLOG.md").write_text(
        "HOSTILE BACKLOG\n", encoding="utf-8"
    )
    (hostile / ".harness").mkdir()
    hostile_report = hostile / ".harness" / "structure-drift.md"
    hostile_report.write_text("HOSTILE REPORT\n", encoding="utf-8")

    result = _run_configured_hook(
        root,
        "SessionStart",
        environment={"CLAUDE_PROJECT_DIR": str(hostile)},
    )
    assert result.returncode == 0
    assert "TRUSTED BACKLOG" in result.stdout
    assert "HOSTILE BACKLOG" not in result.stdout
    assert (root / ".harness" / "structure-drift.md").is_file()
    assert hostile_report.read_text(encoding="utf-8") == "HOSTILE REPORT\n"


def test_explicit_project_root_must_own_the_hydration_script(
    tmp_path: Path,
) -> None:
    root = _fixture_repo(tmp_path / "trusted")
    other = tmp_path / "other"
    other.mkdir()
    result = subprocess.run(
        [
            "bash",
            str(root / "scripts" / "agent_hydration" / "hydrate.sh"),
            "--project-root",
            str(other),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "does not own this script" in result.stderr


def test_argument_free_hydration_preserves_claude_project_dir(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "launcher"
    launcher_script = _copy(
        HYDRATE,
        launcher,
        "scripts/agent_hydration/hydrate.sh",
    )
    claude_root = _fixture_repo(tmp_path / "claude-project")
    (claude_root / "docs" / "tasks").mkdir(parents=True)
    (claude_root / "docs" / "tasks" / "BACKLOG.md").write_text(
        "CLAUDE BACKLOG\n", encoding="utf-8"
    )

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(claude_root)
    result = subprocess.run(
        ["bash", str(launcher_script)],
        cwd=launcher,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "CLAUDE BACKLOG" in result.stdout
