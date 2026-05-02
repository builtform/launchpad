"""Gate #4 (OPERATIONS §6): tamper-mutation hard-rejects.

Mutating any byte after pick-stack signed it causes orchestration to
hard-reject.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.engine import Outcome, run_pipeline


def _run_after_tamper(project: Path, tampered_payload: dict, tmp_path: Path):
    decision_path = project / ".launchpad" / "scaffold-decision.json"
    decision_path.write_text(
        json.dumps(tampered_payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True),
        encoding="utf-8",
    )
    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")
    return run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
    )


@pytest.mark.parametrize("field,mutation,expected_reasons", [
    # Mutating these fields ALSO trips a field-specific rule that runs before
    # rule 13 sha256_mismatch. The gate's intent is "any tamper hard-rejects";
    # we accept either the field-specific reason OR sha256_mismatch.
    ("matched_category_id", "polyglot-next-fastapi", {"sha256_mismatch"}),
    ("nonce", "f" * 32, {"sha256_mismatch"}),
    ("generated_at", "2024-01-01T00:00:00Z",
     {"sha256_mismatch", "generated_at_expired"}),
    ("monorepo", True,
     {"sha256_mismatch", "monorepo_inconsistent_layers"}),
])
def test_tamper_each_field(tmp_path: Path, field: str, mutation, expected_reasons):
    project = tmp_path / "project"
    project.mkdir()
    _, payload = make_decision(project)
    payload[field] = mutation
    # Note: do NOT recompute sha256 — that's the WHOLE point of the gate.
    result = _run_after_tamper(project, payload, tmp_path)
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason in expected_reasons, (
        f"tamper of {field!r} produced reason={result.reason!r}; "
        f"expected one of {expected_reasons!r}"
    )


def test_tamper_sha256_field_itself(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _, payload = make_decision(project)
    payload["sha256"] = "0" * 64
    result = _run_after_tamper(project, payload, tmp_path)
    assert not result.success
    assert result.reason == "sha256_mismatch"
