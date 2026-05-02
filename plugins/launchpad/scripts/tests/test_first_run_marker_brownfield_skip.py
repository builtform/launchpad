"""C3: brownfield cwd → marker NOT consumed (since /lp-brainstorm never wrote
it); scaffold-stack Step 0 refuses.

Per HANDSHAKE §7 greenfield-only marker write contract.
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
from lp_scaffold_stack.marker_consumer import marker_path, marker_present


def test_brownfield_marker_not_consumed(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    # Brownfield signal: package.json present.
    (project / "package.json").write_text('{"name":"existing"}', encoding="utf-8")
    # In a real brownfield project, /lp-brainstorm would NOT have written a
    # marker (greenfield-only contract). Verify scaffold-stack refuses
    # WITHOUT a marker present.
    assert not marker_present(project)

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


def test_marker_consumption_skipped_when_brownfield_refusal_happens_first(tmp_path: Path):
    """Even if a stale marker exists in a brownfield cwd (e.g., the user
    hand-created `.launchpad/.first-run-marker` then dropped a package.json),
    the brownfield refusal at Step 0 fires BEFORE marker consumption."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"name":"existing"}', encoding="utf-8")
    lp = project / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    (lp / ".first-run-marker").write_bytes(b"")

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
    # Marker remains unconsumed because Step 0 refused before Step 2.
    assert marker_path(project).exists()
