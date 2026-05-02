"""Gate #8 (OPERATIONS §6): receipt's tier1_governance_summary contains all
5 enumerated items (whitelisted_paths + lefthook_hooks + slash_commands_wired
+ architecture_docs_rendered + greenfield variant flag inferred from
scaffold-receipt presence).
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
from lp_scaffold_stack.engine import run_pipeline


def test_receipt_tier1_summary_complete(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    make_decision(project)

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
    assert result.success, result.message
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    summary = receipt["tier1_governance_summary"]
    # 4 fields per HANDSHAKE §5 schema; greenfield-variant flag is inferred
    # from receipt presence (no scaffold-receipt.json = brownfield path).
    assert "whitelisted_paths" in summary
    assert "lefthook_hooks" in summary
    assert "slash_commands_wired" in summary
    assert "architecture_docs_rendered" in summary
    # PR #41 cycle 8 #2 (Codex P1): doc-generator emits 4 docs/architecture/*
    # outputs (PRD/TECH_STACK/BACKEND_STRUCTURE/APP_FLOW), not 8.
    assert summary["architecture_docs_rendered"] == 4
    expected_hooks = {"secret-scan", "structure-drift", "typecheck", "lint"}
    assert set(summary["lefthook_hooks"]) == expected_hooks
