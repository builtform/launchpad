"""Tests for lp_scaffold_stack.cleanup_recorder (Phase 3 S9)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.cleanup_recorder import (
    CLEANUP_REASONS,
    CleanupRecordError,
    DESTRUCTIVE_PATHS,
    SCHEMA_VERSION,
    build_failed_payload,
    write_scaffold_failed,
)


def _basic_recovery():
    return [
        {"op": "rmdir_recursive", "path": "apps/web"},
        {"op": "rerun", "command": "/lp-scaffold-stack"},
    ]


def test_build_payload_shape():
    payload = build_failed_payload(
        reason="layer_materialization_failed",
        failed_layer_index=1,
        materialized_files=["apps/web/package.json"],
        recovery_commands=_basic_recovery(),
        recommended_recovery_action="Remove apps/web and re-run.",
    )
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["version"] == "1.0"
    assert payload["reason"] == "layer_materialization_failed"
    assert payload["failed_layer_index"] == 1
    assert payload["materialized_files"] == ["apps/web/package.json"]
    assert payload["recovery_commands"] == _basic_recovery()
    assert payload["see_recovery_doc"].startswith("docs/troubleshooting.md")


def test_unknown_reason_rejected():
    with pytest.raises(CleanupRecordError) as exc:
        build_failed_payload(
            reason="some-bogus-reason", failed_layer_index=0,
            materialized_files=[], recovery_commands=_basic_recovery(),
            recommended_recovery_action="x",
        )
    assert exc.value.reason == "cleanup_reason_invalid"


def test_destructive_path_denylist_rejects():
    """Write-time destructive-path denylist refuses entries with forbidden paths.

    Note: `~` does NOT pass field-discipline regex `^[A-Za-z0-9_./\\-]+$`, so
    that path is rejected with `cleanup_field_discipline_failed` BEFORE the
    denylist runs. Either reason is acceptable defense — both reject WRITES.
    """
    for bad in [".", "./", "..", "/", "~", ".launchpad", ".git", ".github"]:
        with pytest.raises(CleanupRecordError) as exc:
            build_failed_payload(
                reason="layer_materialization_failed", failed_layer_index=0,
                materialized_files=[],
                recovery_commands=[
                    {"op": "rmdir_recursive", "path": bad},
                    {"op": "rerun", "command": "/lp-scaffold-stack"},
                ],
                recommended_recovery_action="x",
            )
        assert exc.value.reason in {
            "cleanup_destructive_path",
            "cleanup_field_discipline_failed",
        }, f"path={bad!r}: unexpected reason={exc.value.reason}"


def test_unknown_op_rejected():
    with pytest.raises(CleanupRecordError) as exc:
        build_failed_payload(
            reason="layer_materialization_failed", failed_layer_index=0,
            materialized_files=[],
            recovery_commands=[{"op": "delete-everything", "path": "x"}],
            recommended_recovery_action="x",
        )
    assert exc.value.reason == "cleanup_recovery_op_invalid"


def test_unknown_rerun_command_rejected():
    with pytest.raises(CleanupRecordError) as exc:
        build_failed_payload(
            reason="layer_materialization_failed", failed_layer_index=0,
            materialized_files=[],
            recovery_commands=[{"op": "rerun", "command": "/some-other-cmd"}],
            recommended_recovery_action="x",
        )
    assert exc.value.reason == "cleanup_recovery_rerun_command_invalid"


def test_field_discipline_regex_rejects_newlines():
    with pytest.raises(CleanupRecordError) as exc:
        build_failed_payload(
            reason="layer_materialization_failed", failed_layer_index=0,
            materialized_files=["apps/web\nrm -rf /"],  # newline injection
            recovery_commands=[{"op": "rerun", "command": "/lp-scaffold-stack"}],
            recommended_recovery_action="x",
        )
    assert exc.value.reason == "cleanup_field_discipline_failed"


def test_failed_layer_index_null_for_cross_cutting():
    """failed_layer_index: null is allowed for cross_cutting_wiring_collision +
    secret_scan_failed per Layer 5 spec-flow P3-LF8."""
    payload = build_failed_payload(
        reason="cross_cutting_wiring_collision",
        failed_layer_index=None,
        materialized_files=[],
        recovery_commands=[{"op": "rerun", "command": "/lp-scaffold-stack"}],
        recommended_recovery_action="x",
    )
    assert payload["failed_layer_index"] is None


def test_failed_layer_index_null_rejected_for_layer_failure():
    with pytest.raises(CleanupRecordError):
        build_failed_payload(
            reason="layer_materialization_failed",
            failed_layer_index=None,
            materialized_files=[],
            recovery_commands=[{"op": "rerun", "command": "/lp-scaffold-stack"}],
            recommended_recovery_action="x",
        )


def test_atomic_write_creates_file(tmp_path: Path):
    target, payload = write_scaffold_failed(
        reason="layer_materialization_failed", failed_layer_index=0,
        materialized_files=["apps/web/package.json"],
        recovery_commands=_basic_recovery(),
        recommended_recovery_action="Remove apps/web and re-run.",
        repo_root=tmp_path,
    )
    assert target.exists()
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk == payload


def test_distinct_reason_enum_from_section_4():
    """OPERATIONS §6 closure (Layer 9): scaffold-failed reasons are DISTINCT
    from §4 scaffold-rejection reasons."""
    # §4 reasons that must NOT appear in scaffold-failed enum:
    rejection_only = {
        "sha256_mismatch", "nonce_seen", "version_unsupported",
        "path_traversal", "bound_cwd_inode_mismatch",
        "rationale_summary_empty", "forbidden_bullet_token",
        "generated_at_expired",
    }
    assert rejection_only.isdisjoint(CLEANUP_REASONS)
