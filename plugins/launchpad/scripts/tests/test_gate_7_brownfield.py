"""Gate #7 (OPERATIONS §6): brownfield cwd refused at scaffold-stack Step 0.

A brownfield cwd causes /lp-scaffold-stack to refuse before ANY validation.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.engine import Outcome, run_pipeline


def test_brownfield_refused(tmp_path: Path):
    """Drop a package.json at cwd; cwd_state classifies as brownfield."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"name": "existing"}', encoding="utf-8")

    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")

    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
    )
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason in {"cwd_state_brownfield", "cwd_state_ambiguous"}
