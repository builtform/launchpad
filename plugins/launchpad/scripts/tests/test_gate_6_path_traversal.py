"""Gate #6 (OPERATIONS §6): path-traversal layers rejected at read-time."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.engine import Outcome, run_pipeline


def test_path_traversal_rejected(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    layers = [{"stack": "astro", "role": "frontend",
               "path": "../../etc/passwd", "options": {"template": "blog"}}]
    make_decision(project, layers=layers)

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
    assert result.reason == "path_traversal"
