"""C2 (Layer 5 P1-DM5-2): a scaffold-decision.json with version "0.x-test"
read by a v2.0-final consumer (EXPECTED_DECISION_VERSION={"1.0"}) hard-rejects
with version_unsupported + seen_version field + remediation hint.

Simulates the post-bump v2.0.0 ship state by passing
expected_versions=frozenset({"1.0"}) explicitly.
"""
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


def test_rc_version_rejected_at_post_bump(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    # Anti-version: keep at "0.x-test" to test post-bump rejection. After the
    # v2.0.0 coordinated bump the writer constants ship "1.0", but old user-
    # tree decision files stamped during pre-ship dev MUST still hard-reject
    # with version_unsupported + remediation hint (HANDSHAKE §10 user-tree
    # carve-out + §4 rule 1).
    make_decision(project, version="0.x-test")

    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")

    # Simulate the post-bump v2.0.0 final consumer.
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        expected_versions=frozenset({"1.0"}),
    )
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason == "version_unsupported"
    # Remediation hint surfaces in the message.
    assert "delete" in (result.message or "").lower()
    assert ".launchpad/scaffold-decision.json" in (result.message or "")
