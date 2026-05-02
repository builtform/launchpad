"""Gate #3 (OPERATIONS §6): nonce already-seen hard-rejects.

The same scaffold-decision.json cannot be consumed twice.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (
    fake_run_invoker_creating,
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.engine import Outcome, run_pipeline
from lp_scaffold_stack.nonce_ledger import append_nonce


def test_replay_rejected(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    decision_path, payload = make_decision(project)

    # Pre-populate the ledger with this nonce so the second consumption hits replay.
    append_nonce(payload["nonce"], project)

    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")

    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=fake_run_invoker_creating({"npm": ["package.json"]}),
    )
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason == "nonce_seen"
