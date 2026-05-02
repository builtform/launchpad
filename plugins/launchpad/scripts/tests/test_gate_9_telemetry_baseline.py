"""Gate #9 (OPERATIONS §6): telemetry baseline schema validation.

Every JSONL line under opt-in mode validates required fields + outcome enum
+ asserts no description/free_text fields leaked.
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

VALID_OUTCOMES = {"completed", "failed", "aborted",
                   "accepted", "manual_override"}
FORBIDDEN_FIELDS = {"description", "free_text", "q1_text", "raw_prompt"}
REQUIRED_FIELDS = {"command", "timestamp", "outcome", "time_seconds", "schema_version"}


def _read_telemetry_lines(repo_root: Path) -> list[dict]:
    obs = repo_root / ".harness" / "observations"
    if not obs.exists():
        return []
    out: list[dict] = []
    for f in sorted(obs.glob("v2-pipeline-*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            out.append(json.loads(line))
    return out


def test_telemetry_baseline_completed(tmp_path: Path):
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
    assert result.success
    lines = _read_telemetry_lines(project)
    assert lines, "telemetry should have written at least one entry"
    for line in lines:
        for fld in REQUIRED_FIELDS:
            assert fld in line, f"missing required field {fld!r} in {line}"
        assert line["outcome"] in VALID_OUTCOMES
        for forbidden in FORBIDDEN_FIELDS:
            assert forbidden not in line, f"forbidden free-text field {forbidden!r} leaked"
        assert line["command"] == "/lp-scaffold-stack"
        # Greenfield-path: completed entries carry install_seconds + secret_scan_passed.
        if line["outcome"] == "completed":
            assert "install_seconds" in line
            assert "secret_scan_passed" in line


def test_telemetry_baseline_aborted(tmp_path: Path):
    """An aborted run still produces a structured telemetry entry."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"x":1}', encoding="utf-8")  # brownfield

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
    lines = _read_telemetry_lines(project)
    aborted_lines = [l for l in lines if l["outcome"] == "aborted"]
    assert aborted_lines
    for line in aborted_lines:
        assert line["reason"] in {"cwd_state_brownfield", "cwd_state_ambiguous"}
