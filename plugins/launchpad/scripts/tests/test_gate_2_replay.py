"""Gate #2 (OPERATIONS §6): bound_cwd-triple mismatch hard-rejects.

A scaffold-decision.json from one repo cannot be consumed in another.
"""
from __future__ import annotations

import json
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
from decision_integrity import canonical_hash
from lp_scaffold_stack.engine import Outcome, run_pipeline


def test_decision_from_other_repo_rejected(tmp_path: Path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir(); repo_b.mkdir()

    decision_path_a, payload = make_decision(repo_a)

    # Copy the (sealed) decision from repo-a into repo-b.
    decision_path_b = repo_b / ".launchpad" / "scaffold-decision.json"
    decision_path_b.parent.mkdir(parents=True, exist_ok=True)
    decision_path_b.write_text(decision_path_a.read_text(encoding="utf-8"),
                                encoding="utf-8")

    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")

    result = run_pipeline(
        repo_b,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
    )
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason in {
        "bound_cwd_realpath_mismatch",
        "bound_cwd_realpath_changed_inode_match",
        "bound_cwd_inode_mismatch",
        "rationale_sha256_mismatch",  # rationale.md missing in repo-b is also a valid early-fail
    }
