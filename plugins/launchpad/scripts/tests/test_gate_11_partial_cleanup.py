"""Gate #11 (OPERATIONS §6): partial-scaffold cleanup contract.

Inject safe_run failure on layer 1; assert:
  (a) pipeline exits non-zero
  (b) nonce NOT consumed (re-run-with-same-decision succeeds after fix)
  (c) materialized layer 0 state remains
  (d) scaffold-failed-<ts>.json shape matches OPERATIONS §6 schema
  (e) write-time destructive-path denylist refuses bad recovery_commands entry
  (f) re-run with same scaffold-decision.json succeeds after cause is fixed
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
    fake_run_invoker_creating,
    fake_run_invoker_failing_at,
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.cleanup_recorder import (
    CleanupRecordError,
    build_failed_payload,
)
from lp_scaffold_stack.engine import Outcome, run_pipeline
from lp_scaffold_stack.nonce_ledger import is_nonce_seen


def _two_layer_polyglot(project: Path):
    layers = [
        {"stack": "next", "role": "frontend", "path": "apps/web", "options": {}},
        {"stack": "next", "role": "frontend", "path": "apps/dashboard", "options": {}},
    ]
    # The validator requires monorepo + ≥2 layers.
    return make_decision(
        project,
        layers=layers,
        matched_category_id="polyglot-next-fastapi",  # exists in helpers' minimal catalog
        monorepo=True,
    )


def test_partial_failure_emits_scaffold_failed(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    decision_path, payload = _two_layer_polyglot(project)
    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")

    # Fail on the SECOND layer (index 1).
    invoker = fake_run_invoker_failing_at(failure_layer_index=1)
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=invoker,
    )
    # (a) Pipeline failed.
    assert not result.success
    assert result.outcome == Outcome.FAILED
    assert result.reason == "layer_materialization_failed"
    # (b) Nonce NOT consumed.
    assert is_nonce_seen(payload["nonce"], project) is False
    # (c) Layer 0 state remains.
    assert (project / "apps" / "web" / "marker.scaffolded").exists()
    # (d) scaffold-failed-<ts>.json present + valid shape.
    assert result.failed_record_path is not None
    failed = json.loads(result.failed_record_path.read_text(encoding="utf-8"))
    assert failed["reason"] == "layer_materialization_failed"
    assert failed["failed_layer_index"] == 1
    assert isinstance(failed["recovery_commands"], list)
    assert "see_recovery_doc" in failed
    assert failed["recommended_recovery_action"]


def test_destructive_path_denylist_at_write_time():
    """The cleanup_recorder.build_failed_payload refuses a recovery_commands
    entry with a destructive `path`."""
    with pytest.raises(CleanupRecordError) as exc:
        build_failed_payload(
            reason="layer_materialization_failed", failed_layer_index=0,
            materialized_files=[],
            recovery_commands=[
                {"op": "rmdir_recursive", "path": ".launchpad"},
                {"op": "rerun", "command": "/lp-scaffold-stack"},
            ],
            recommended_recovery_action="x",
        )
    assert exc.value.reason == "cleanup_destructive_path"


def test_rerun_after_fix_succeeds(tmp_path: Path):
    """After a partial failure, re-running with the same decision file
    succeeds when the underlying cause is fixed (because the nonce was
    NOT consumed)."""
    project = tmp_path / "project"
    project.mkdir()
    decision_path, payload = _two_layer_polyglot(project)
    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")

    # Run 1: fail on layer 1.
    fail_invoker = fake_run_invoker_failing_at(failure_layer_index=1)
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=fail_invoker,
    )
    assert not result.success
    # Clean up the partial layer-0 state so cross-cutting wiring doesn't
    # collide on re-run.
    import shutil
    shutil.rmtree(project / "apps", ignore_errors=True)

    # Run 2: succeed on both layers. Skip the greenfield gate because the
    # cwd now contains `.harness/observations/` from the prior failure's
    # forensic logs (a real "rerun-after-fix" is a recovery flow, not a
    # fresh greenfield invocation).
    success_invoker = fake_run_invoker_creating(
        {"npx": ["package.json"], "npm": ["package.json"]},
    )
    result2 = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=success_invoker,
        skip_greenfield_gate=True,
    )
    assert result2.success, result2.message
    assert result2.outcome == Outcome.COMPLETED
