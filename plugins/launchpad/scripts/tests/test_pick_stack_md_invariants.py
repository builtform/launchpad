"""Command contracts for brainstorm-informed stack selection."""

from pathlib import Path
import json
import os
import re
import shutil
import subprocess

import pytest


_COMMANDS = Path(__file__).resolve().parents[2] / "commands"


def test_brainstorm_records_stack_context():
    command = (_COMMANDS / "lp-brainstorm.md").read_text(encoding="utf-8")
    assert "brainstorm_doc:" in command
    assert "# Stack-relevant constraints" in command


def test_kickoff_names_greenfield_contract():
    command = (_COMMANDS / "lp-kickoff.md").read_text(encoding="utf-8")
    step = command.split("### 0.2", 1)[1].split("### 0.3", 1)[0]
    assert "`docs/architecture/SCAFFOLD_HANDSHAKE.md` section 8" in step
    assert "greenfield-neutral" in step


def test_pick_stack_uses_confirmed_selection_contract():
    command = (_COMMANDS / "lp-pick-stack.md").read_text(encoding="utf-8")
    for token in (
        "shortlist_categories", "chosen_category_id", "category_selection_required",
        "category_choice_invalid", "validate_brainstorm_summary", "validate_answers",
        "case-insensitively", "[tag removed]", "LP_PICK_INPUT", "json.loads",
        'PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"',
    ):
        assert token in command
    for old in (
        "category_match_ambiguous_no_cluster", "ambiguity_cluster_disambiguation_required",
        "ambiguity_cluster_choice_invalid", "cluster_choice",
    ):
        assert old not in command
    snippets = re.findall(r"```bash\n(.*?)\n```", command, re.S)
    assert len(snippets) == 3
    for snippet in snippets:
        assert "LP_PICK_INPUT=$(cat <<'LP_PICK_JSON'" in snippet
        assert 'PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"' in snippet
        assert 'json.loads(os.environ["LP_PICK_INPUT"])' in snippet


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is unavailable")
def test_pick_stack_snippet_treats_hostile_description_as_data(tmp_path: Path):
    command = (_COMMANDS / "lp-pick-stack.md").read_text(encoding="utf-8")
    step = command.split("## Step 3", 1)[1].split("## Step 4", 1)[0]
    snippet = re.search(r"```bash\n(.*?)\n```", step, re.S).group(1)
    lines = snippet.splitlines()
    start = lines.index("LP_PICK_INPUT=$(cat <<'LP_PICK_JSON'")
    data = {
        "answers": {
            "Q1": "web-app", "Q2": "yes-needed", "Q3": "feature-not-core",
            "Q4": "typescript-javascript", "Q5": "node-server",
        },
        "describe": "Quotes: ''' and \"\"\", a \\ backslash, $(touch pwned), `touch pwned`\nEOF\n",
    }
    lines[start + 1] = json.dumps(data)
    result = subprocess.run(
        ["bash"], input="\n".join(lines) + "\n", text=True,
        capture_output=True, cwd=tmp_path,
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(_COMMANDS.parent)},
        timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert isinstance(json.loads(result.stdout)["candidates"], list)
    assert not (tmp_path / "pwned").exists()
