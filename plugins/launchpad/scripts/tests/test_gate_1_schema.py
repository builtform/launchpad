"""Gate #1 (OPERATIONS §6): scaffold-decision.json round-trips through both
plans without modification.

Pick-stack writes → orchestration reads → pick-stack re-validates from disk.
"""
from __future__ import annotations

import json
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


def test_decision_round_trips(tmp_path: Path):
    decision_path, payload = make_decision(tmp_path)
    on_disk = json.loads(decision_path.read_text(encoding="utf-8"))
    assert on_disk == payload


def test_full_pipeline_accepts_valid_decision(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    decision_path, payload = make_decision(project)

    # Stand up a minimal scaffolders + categories catalog in a side dir.
    plugins_root = tmp_path / "plugins-root"
    scaffolders_yml = plugins_root / "scaffolders.yml"
    categories_yml = plugins_root / "data" / "category-patterns.yml"
    write_minimal_scaffolders_yml(scaffolders_yml)
    write_minimal_categories_yml(categories_yml)

    invoker = fake_run_invoker_creating({"npm": ["package.json"]})
    result = run_pipeline(
        project, scaffolders_yml=scaffolders_yml,
        category_patterns_yml=categories_yml,
        plugins_root=plugins_root,
        run_invoker=invoker,
    )
    assert result.success, result.message
    assert result.outcome == Outcome.COMPLETED
    assert result.receipt_path is not None and result.receipt_path.exists()
