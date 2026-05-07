"""v2.1 Codex PR #50 P1.3 (D9.2) regression: decision_validator v1.1 envelope.

Tests:
  * v1.1 envelope shape (plugin_version, stacks, identity)
  * `kernel_seed_pending` 3-state acceptance (true/false/absent)
  * mutual exclusion (pending=true + render_state present = REJECT)
  * forge-on-fresh chain validation (`migration_origin_sha256` + .pre-migration)
  * `mark_kernel_seeded()` idempotency + ratchet-key strip
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_scaffold_stack.decision_validator import (  # noqa: E402
    Rejected,
    _compute_migration_origin_sha,
    _validate_v1_1_envelope,
    mark_kernel_seeded,
)


def _valid_v11_decision() -> dict:
    return {
        "schema_version": "1.1",
        "plugin_version": "2.1.0",
        "stacks": ["nextjs_standalone"],
        "identity": {
            "pii_opt_in": False,
            "project_name": "demo",
            "email": "a@b.c",
            "copyright_holder": "X",
            "repo_url": "https://github.com/x/y",
            "license": "MIT",
        },
        "kernel_render_state": [
            {"path": "LICENSE", "rendered_content_sha256": "0" * 64},
        ],
    }


def test_v11_clean_decision_accepts(tmp_path):
    rej = _validate_v1_1_envelope(_valid_v11_decision(), tmp_path)
    assert rej is None


def test_v11_missing_plugin_version_rejects(tmp_path):
    payload = _valid_v11_decision()
    del payload["plugin_version"]
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "v1_1_plugin_version_invalid"


def test_v11_missing_stacks_rejects(tmp_path):
    payload = _valid_v11_decision()
    payload["stacks"] = []
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "v1_1_stacks_invalid"


def test_v11_unknown_stack_id_rejects(tmp_path):
    payload = _valid_v11_decision()
    payload["stacks"] = ["not_in_active_enum"]
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "v1_1_stack_id_unknown"


def test_v11_missing_identity_keys_rejects(tmp_path):
    payload = _valid_v11_decision()
    del payload["identity"]["email"]
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "v1_1_identity_missing_keys"
    assert "email" in rej.extra.get("missing_fields", [])


def test_v11_kernel_seed_pending_with_state_rejects(tmp_path):
    payload = _valid_v11_decision()
    payload["kernel_seed_pending"] = True
    # state is already present -> mutual exclusion violation
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "kernel_seed_pending_with_state"


def test_v11_kernel_seed_pending_without_origin_rejects(tmp_path):
    payload = _valid_v11_decision()
    del payload["kernel_render_state"]
    payload["kernel_seed_pending"] = True
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "kernel_seed_pending_without_migration_provenance"


def test_v11_kernel_seed_pending_with_chain_validation(tmp_path):
    # Compose a backup, compute its sha, write both files.
    (tmp_path / ".launchpad").mkdir()
    backup = {
        "schema_version": "1.1",
        "plugin_version": "2.0.1",
        "stacks": ["nextjs_standalone"],
        "identity": {
            "pii_opt_in": False,
            "project_name": "demo",
            "email": "a@b.c",
            "copyright_holder": "X",
            "repo_url": "https://github.com/x/y",
            "license": "MIT",
        },
    }
    backup_path = (
        tmp_path / ".launchpad" / "scaffold-decision.json.pre-migration"
    )
    backup_path.write_text(json.dumps(backup), encoding="utf-8")
    sha = _compute_migration_origin_sha(backup)

    payload = dict(backup)
    payload["kernel_seed_pending"] = True
    payload["migration_origin_sha256"] = sha
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert rej is None


def test_v11_forge_attack_with_fabricated_origin_rejects(tmp_path):
    # No backup file at all = forge attempt.
    payload = _valid_v11_decision()
    del payload["kernel_render_state"]
    payload["kernel_seed_pending"] = True
    payload["migration_origin_sha256"] = "f" * 64
    rej = _validate_v1_1_envelope(payload, tmp_path)
    assert isinstance(rej, Rejected)
    assert rej.reason == "kernel_seed_pending_without_migration_provenance"


def test_mark_kernel_seeded_idempotent_when_already_sealed():
    decision = _valid_v11_decision()
    state = decision["kernel_render_state"]
    sealed = mark_kernel_seeded(decision, state)
    # No pending key, no origin, kernel_render_state preserved.
    assert "kernel_seed_pending" not in sealed
    assert "migration_origin_sha256" not in sealed
    assert sealed["kernel_render_state"] == state


def test_mark_kernel_seeded_strips_ratchet_keys():
    decision = _valid_v11_decision()
    del decision["kernel_render_state"]
    decision["kernel_seed_pending"] = True
    decision["migration_origin_sha256"] = "abc"
    new_state = [{"path": "LICENSE", "rendered_content_sha256": "1" * 64}]
    sealed = mark_kernel_seeded(decision, new_state)
    assert "kernel_seed_pending" not in sealed
    assert "migration_origin_sha256" not in sealed
    assert sealed["kernel_render_state"] == new_state


def test_mark_kernel_seeded_does_not_mutate_input():
    decision = _valid_v11_decision()
    original = dict(decision)
    new_state = [{"path": "LICENSE", "rendered_content_sha256": "x" * 64}]
    mark_kernel_seeded(decision, new_state)
    # Input mapping unchanged.
    assert decision == original
