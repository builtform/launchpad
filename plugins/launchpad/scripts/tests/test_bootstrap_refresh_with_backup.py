"""Refresh + backup tests (v2.1 Phase 3 Slice C).

Coverage matrix (plan section 5 + section 2.2):
  * `--refresh <path>` single-file refresh
  * `--refresh-all` blanket refresh
  * Backup directory naming `<ts>-<PID>-<rand4>` (harden C1)
  * Backup contents byte-equal pre-edit
  * `.launchpad/backups/` gitignored before first refresh write
  * Path-traversal rejection: `..`, absolute, off-inventory
  * `--refresh-all` on no-manifest project degrades to full bootstrap
    with INFO `no_manifest_to_refresh`
  * `--accept-plugin-version-drift` records drift + auto-triggers
    `--refresh-all`
  * Sealed identity (recorded `plugin_version`) preserved on drift accept
  * Symlink target rejection in `overwrite-with-backup`
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import BootstrapErrorCode, LAUNCHPAD_DIR_NAME  # noqa: E402
from lp_bootstrap.engine import run_bootstrap  # noqa: E402


def _identity():
    return {
        "pii_opt_in": True,
        "project_name": "demo",
        "email": "demo@example.com",
        "copyright_holder": "@demo",
        "repo_url": "https://github.com/demo/demo",
        "license": "MIT",
        "license_other_body": "",
    }


def _bootstrap_clean(tmp_path: Path):
    """Greenfield bootstrap a tmp project; return the result."""
    return run_bootstrap(tmp_path, mode="greenfield", identity=_identity())


# --- --refresh <path> single-file --------------------------------------

def test_refresh_single_path_creates_backup(tmp_path):
    _bootstrap_clean(tmp_path)
    target = tmp_path / "scripts" / "compound" / "build.sh"
    user_bytes = b"#!/usr/bin/env bash\n# user-edited content\n"
    target.write_bytes(user_bytes)

    result = run_bootstrap(
        tmp_path, mode="refresh",
        refresh_paths=["scripts/compound/build.sh"],
        identity=_identity(),
    )
    assert result.outcome == "success"
    assert result.backup_dir is not None
    assert (result.backup_dir / "scripts" / "compound" / "build.sh").read_bytes() == user_bytes


def test_refresh_overwrites_target_after_backup(tmp_path):
    _bootstrap_clean(tmp_path)
    target = tmp_path / "scripts" / "compound" / "build.sh"
    target.write_bytes(b"# stale\n")

    run_bootstrap(
        tmp_path, mode="refresh",
        refresh_paths=["scripts/compound/build.sh"],
        identity=_identity(),
    )
    text = target.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert "# stale" not in text


def test_refresh_only_touches_specified_path(tmp_path):
    _bootstrap_clean(tmp_path)
    other = tmp_path / "scripts" / "compound" / "lib.sh"
    pre_edit_other = other.read_bytes()

    result = run_bootstrap(
        tmp_path, mode="refresh",
        refresh_paths=["scripts/compound/build.sh"],
        identity=_identity(),
    )
    assert result.files_processed == 1
    # Other paths untouched
    assert other.read_bytes() == pre_edit_other
    # Backup dir contains only the refreshed path
    assert (result.backup_dir / "scripts" / "compound" / "build.sh").exists()
    assert not (result.backup_dir / "scripts" / "compound" / "lib.sh").exists()


# --- --refresh-all blanket refresh ----------------------------------------

def test_refresh_all_writes_all_30_paths(tmp_path):
    # v2.1 Codex PR #50 P1.A: count is 31 after restamp-history-hook
    # entry is added to INFRASTRUCTURE_FILES.
    from lp_bootstrap import INFRASTRUCTURE_FILES
    expected = len(INFRASTRUCTURE_FILES)
    _bootstrap_clean(tmp_path)
    result = run_bootstrap(
        tmp_path, mode="refresh-all", identity=_identity(),
    )
    assert result.outcome == "success"
    assert result.files_processed == expected
    assert result.files_written == expected


def test_refresh_all_no_manifest_degrades_to_full_bootstrap(tmp_path):
    """Harden A8: no manifest -> silent degrade to full bootstrap."""
    from lp_bootstrap import INFRASTRUCTURE_FILES
    expected = len(INFRASTRUCTURE_FILES)
    # No prior bootstrap; .launchpad exists but no manifest
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    result = run_bootstrap(
        tmp_path, mode="refresh-all", identity=_identity(),
    )
    assert result.outcome == "success"
    assert result.files_written == expected
    assert any("no manifest found" in w for w in result.warnings)


# --- Backup directory --------------------------------------------------

def test_backup_dir_naming_pattern(tmp_path):
    _bootstrap_clean(tmp_path)
    result = run_bootstrap(
        tmp_path, mode="refresh-all", identity=_identity(),
    )
    name = result.backup_dir.name
    # ts-PID-rand4 with rand4 = 4 hex chars
    parts = name.split("-")
    assert len(parts) == 3
    assert parts[1] == str(os.getpid())
    assert len(parts[2]) == 4


def test_backup_dir_under_launchpad_backups(tmp_path):
    _bootstrap_clean(tmp_path)
    result = run_bootstrap(
        tmp_path, mode="refresh-all", identity=_identity(),
    )
    assert result.backup_dir.parent.name == "backups"
    assert result.backup_dir.parent.parent.name == LAUNCHPAD_DIR_NAME


def test_backup_dir_added_to_gitignore_before_first_refresh(tmp_path):
    _bootstrap_clean(tmp_path)
    run_bootstrap(
        tmp_path, mode="refresh", refresh_paths=["scripts/compound/build.sh"],
        identity=_identity(),
    )
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".launchpad/backups/" in text


# --- Path validation (harden A15) -----------------------------------------

def test_refresh_rejects_double_dot(tmp_path):
    _bootstrap_clean(tmp_path)
    result = run_bootstrap(
        tmp_path, mode="refresh", refresh_paths=["../etc/passwd"],
        identity=_identity(),
    )
    assert result.outcome != "success"
    assert result.errors[0].code == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_refresh_rejects_absolute_path(tmp_path):
    _bootstrap_clean(tmp_path)
    result = run_bootstrap(
        tmp_path, mode="refresh", refresh_paths=["/etc/passwd"],
        identity=_identity(),
    )
    assert result.errors[0].code == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_refresh_rejects_off_inventory_path(tmp_path):
    _bootstrap_clean(tmp_path)
    result = run_bootstrap(
        tmp_path, mode="refresh", refresh_paths=["LICENSE"],
        identity=_identity(),
    )
    # LICENSE is a kernel file, not in INFRASTRUCTURE_TARGETS
    assert result.errors[0].code == BootstrapErrorCode.UNKNOWN_REFRESH_PATH


# --- --accept-plugin-version-drift ---------------------------------------

def test_drift_unaccepted_aborts_with_plugin_version_mismatch(tmp_path):
    """Seed a scaffold-decision recording an older plugin_version; expect abort."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    decision = {
        "schema_version": "1.1",
        "version": "1.0",
        "plugin_version": "1.0.0-test",  # different from running 2.0.0
        "identity": _identity(),
    }
    (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").write_text(
        json.dumps(decision), encoding="utf-8",
    )
    result = run_bootstrap(
        tmp_path, mode="brownfield-auto", identity=_identity(),
    )
    assert result.outcome == "plugin_version_mismatch"
    assert result.errors[0].code == BootstrapErrorCode.PLUGIN_VERSION_MISMATCH


def test_drift_accepted_records_in_scaffold_decision(tmp_path):
    """`--accept-plugin-version-drift` writes a `version_drift_log[]` entry
    and preserves the originally-sealed `plugin_version` field.

    v2.1 Codex PR #50 cycle 6 T1-4 (F9 regression-prevention): also asserts
    the on-disk `sha256` envelope is valid post-mutation. Cycle 5 left the
    hash stale because `_record_version_drift` wrote directly via
    `atomic_write_replace`; cycle 6 routes through `re_seal_decision_atomic`
    so the hash is recomputed.
    """
    import sys as _sys
    _SCRIPTS_DIR = Path(__file__).resolve().parent.parent
    if str(_SCRIPTS_DIR) not in _sys.path:
        _sys.path.insert(0, str(_SCRIPTS_DIR))
    from lp_pick_stack.decision_writer import seal_decision_payload

    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    decision = {
        "schema_version": "1.1",
        "version": "1.0",
        "plugin_version": "1.0.0-test",
        "identity": _identity(),
    }
    (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").write_text(
        json.dumps(decision), encoding="utf-8",
    )
    result = run_bootstrap(
        tmp_path, mode="brownfield-auto", identity=_identity(),
        accept_plugin_version_drift=True,
    )
    assert result.outcome == "success"
    # Drift log written
    decision_path = (
        tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
    )
    written = json.loads(decision_path.read_text(encoding="utf-8"))
    assert "version_drift_log" in written
    assert len(written["version_drift_log"]) == 1
    entry = written["version_drift_log"][0]
    assert entry["from_version"] == "1.0.0-test"
    assert "to_version" in entry
    assert "accepted_at" in entry
    # Sealed plugin_version preserved
    assert written["plugin_version"] == "1.0.0-test"

    # T1-4 / F9: hash-chain validity post-mutation. seal_decision_payload
    # over (payload-minus-sha256) MUST equal the on-disk sha256 envelope.
    on_disk_sha = written.pop("sha256", None)
    assert on_disk_sha is not None, (
        "F9 regression: sha256 missing post-drift-accept "
        "(cycle 5 wrote unsealed JSON; cycle 6 re-seals via "
        "re_seal_decision_atomic)"
    )
    resealed = seal_decision_payload(written)
    assert resealed["sha256"] == on_disk_sha, (
        "F9 regression: on-disk sha256 does not match "
        "seal_decision_payload(payload-minus-sha256). "
        "decision_validator will reject this file on next /lp-bootstrap."
    )

    # T0-2 / DA-F9.1: file mode tightened 0o644 -> 0o600 via re-seal helper.
    assert (os.stat(decision_path).st_mode & 0o777) == 0o600, (
        "DA-F9.1 contract: re_seal_decision_atomic writes mode 0o600"
    )


def test_drift_accepted_auto_triggers_refresh_all(tmp_path):
    """Drift accept on a fresh greenfield should treat the run as
    refresh-all so the manifest shas align with the new plugin's
    templates (per section 6.1)."""
    # First, do a clean greenfield bootstrap, then seed a version drift.
    _bootstrap_clean(tmp_path)
    decision = json.loads(
        (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").read_text(encoding="utf-8")
    ) if (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").is_file() else {
        "schema_version": "1.1",
        "version": "1.0",
        "plugin_version": "1.0.0-test",
        "identity": _identity(),
    }
    decision["plugin_version"] = "1.0.0-test"
    decision["schema_version"] = "1.1"
    decision["identity"] = _identity()
    (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").write_text(
        json.dumps(decision), encoding="utf-8",
    )
    result = run_bootstrap(
        tmp_path, mode="brownfield-auto", identity=_identity(),
        accept_plugin_version_drift=True,
    )
    # refresh-all -> backup_dir should be populated
    assert result.backup_dir is not None
    # v2.1 Codex PR #50 P1.A: count is 31 after restamp-history-hook entry.
    from lp_bootstrap import INFRASTRUCTURE_FILES
    assert result.files_processed == len(INFRASTRUCTURE_FILES)
