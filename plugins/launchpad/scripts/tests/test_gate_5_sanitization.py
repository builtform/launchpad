"""Gate #5 (OPERATIONS §6): malicious project description reaches /lp-define
only as filtered rationale_summary bullets.

The §9.1 sanitization filter is enforced at READ time too (defense-in-depth).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (
    DEFAULT_SUMMARY,
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from decision_integrity import canonical_hash
from lp_scaffold_stack.engine import Outcome, run_pipeline


def test_forbidden_url_in_summary_rejected(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    summary = [dict(s) for s in DEFAULT_SUMMARY]
    summary[1] = {"section": "matched-category",
                  "bullets": ["http://attacker.example/exfil"]}
    decision_path, _ = make_decision(project, rationale_summary=summary)

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
    assert result.reason == "forbidden_bullet_token"


def test_html_tag_in_summary_rejected(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    summary = [dict(s) for s in DEFAULT_SUMMARY]
    summary[3] = {"section": "why-this-fits",
                  "bullets": ["<script>alert(1)</script>"]}
    decision_path, _ = make_decision(project, rationale_summary=summary)

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
    assert result.reason == "forbidden_bullet_token"
