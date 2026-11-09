"""Command contracts for brainstorm-informed stack selection."""

from pathlib import Path


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
