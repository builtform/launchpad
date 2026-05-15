"""Manifest tampering integrity tests (v2.1 Phase 3 Slice C).

Per V3 plan section 10.7 + harden A9. Tampering scenarios:
  * Edited `source_template_sha256` field by hand
  * Swapped paths between entries
  * Manifest deleted then forged with bogus shas
  * Distinct `manifest_corrupt` (parse error) vs `manifest_tampered`
    (sha mismatch) error codes
  * Non-empty `security_fields` v2.2-downgrade defense (harden B9)

Phase 11 re-runs this suite + adds cross-version cases. Slice C is the
authoritative origin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import (  # noqa: E402
    BootstrapErrorCode,
    LAUNCHPAD_DIR_NAME,
    MANIFEST_FILENAME,
)
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


def _bootstrap_clean(tmp_path: Path) -> Path:
    """Run a fresh greenfield bootstrap; return the manifest path."""
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "success"
    assert result.manifest_path is not None
    return result.manifest_path


def _read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --- Tamper: edit source_template_sha256 by hand --------------------------

def test_edited_source_template_sha_raises_manifest_tampered(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    # Tamper the first file entry's source sha
    payload["files"][0]["source_template_sha256"] = "0" * 64
    _write_manifest(manifest_path, payload)

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_tampered"
    assert result.errors[0].code == BootstrapErrorCode.MANIFEST_TAMPERED


# --- Tamper: swap path between two entries --------------------------------

def test_swapped_paths_raises_manifest_tampered(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    # Swap the source shas between files[0] and files[1]
    a = payload["files"][0]["source_template_sha256"]
    b = payload["files"][1]["source_template_sha256"]
    payload["files"][0]["source_template_sha256"] = b
    payload["files"][1]["source_template_sha256"] = a
    _write_manifest(manifest_path, payload)

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_tampered"


# --- Tamper: forged manifest with bogus shas after deletion ---------------

def test_forged_manifest_with_bogus_shas_raises_manifest_tampered(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    bogus = {
        "manifest_schema_version": "1.0",
        "plugin_version": "2.0.0",
        "last_render_timestamp": "2026-05-05T00:00:00Z",
        "files": [
            {
                "path": ".gitignore",
                "source_template_sha256": "f" * 64,
                "rendered_content_sha256": "0" * 64,
                "policy": "append-only",
                "mode": 0o644,
            },
        ],
        "security_fields": [],
    }
    _write_manifest(manifest_path, bogus)

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_tampered"


# --- Distinct: corrupt JSON vs tampered shas ------------------------------

def test_corrupt_json_raises_manifest_corrupt(tmp_path):
    _bootstrap_clean(tmp_path)
    manifest_path = tmp_path / LAUNCHPAD_DIR_NAME / MANIFEST_FILENAME
    manifest_path.write_text("{ not valid json", encoding="utf-8")

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_corrupt"
    assert result.errors[0].code == BootstrapErrorCode.MANIFEST_CORRUPT


def test_corrupt_top_level_array_raises_manifest_corrupt(tmp_path):
    _bootstrap_clean(tmp_path)
    manifest_path = tmp_path / LAUNCHPAD_DIR_NAME / MANIFEST_FILENAME
    manifest_path.write_text("[]", encoding="utf-8")
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_corrupt"


def test_corrupt_files_not_a_list_raises_manifest_corrupt(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    payload["files"] = "not-a-list"
    _write_manifest(manifest_path, payload)
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_corrupt"


def test_corrupt_file_entry_missing_field_raises_manifest_corrupt(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    # Drop a required field on first entry
    del payload["files"][0]["rendered_content_sha256"]
    _write_manifest(manifest_path, payload)
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_corrupt"


# --- Reserved security_fields v2.2-downgrade defense (harden B9) ----------

def test_non_empty_security_fields_raises_manifest_tampered(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    payload["security_fields"] = [{"signature": "fake"}]
    _write_manifest(manifest_path, payload)
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_tampered"


# --- Tamper: missing entry for a plugin-shipped path -----------------------

def test_missing_entry_for_plugin_shipped_target_raises_manifest_tampered(tmp_path):
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    # Drop one entry; cached source-template-sha cache will detect the gap
    payload["files"] = payload["files"][1:]
    _write_manifest(manifest_path, payload)
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_tampered"


def test_missing_entry_with_drift_accepted_warns_and_recovers(tmp_path):
    """v2.1.5 round-4 fix (Codex P1-A): a v2.1.4 manifest missing entries
    for v2.1.5-newly-added targets (`.nvmrc`, `.github/dependabot.yml`,
    `.github/pull_request_template.md`) must NOT brick under
    --accept-plugin-version-drift. The flag tolerates missing entries as
    warnings; --refresh-all auto-trigger realigns the manifest in the
    same run.

    Simulates the v2.1.4 → v2.1.5 upgrade scenario: drop entries from
    the manifest (mimicking v2.1.4's smaller inventory) then re-run
    with `accept_plugin_version_drift=True`. Expected: success (NOT
    manifest_tampered), the missing entries are written via the
    auto-triggered --refresh-all, and the new manifest covers the full
    current inventory."""
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    # Drop 3 entries to simulate a v2.1.4-bootstrapped project before
    # v2.1.5's INFRASTRUCTURE_FILES additions landed.
    full_entries = payload["files"]
    payload["files"] = full_entries[:-3]
    _write_manifest(manifest_path, payload)
    # WITHOUT drift flag: tampered (the existing test above pins this).
    # WITH drift flag: warn + auto-realign, run succeeds.
    result = run_bootstrap(
        tmp_path,
        mode="greenfield",
        identity=_identity(),
        accept_plugin_version_drift=True,
    )
    assert result.outcome == "success", (
        f"Codex P1-A regression: --accept-plugin-version-drift must "
        f"tolerate missing-newer-entries on cross-version upgrade. "
        f"Got outcome={result.outcome!r} errors={result.errors!r}"
    )
    # New manifest covers the full current inventory after realign.
    new_payload = _read_manifest(manifest_path)
    assert len(new_payload["files"]) == len(full_entries), (
        "after --accept-plugin-version-drift + --refresh-all auto-trigger, "
        "the manifest must list every current INFRASTRUCTURE_FILES entry"
    )


# --- Phase 11 DA3 augment: SymlinkSubstitution ----------------------------


def test_symlink_substitution_rejects_with_path_traversal(tmp_path):
    """Phase 11 DA3 augment #1. A managed file is replaced with a symlink
    pointing outside the repo; the next /lp-bootstrap run hits the
    policy.py:228 symlink rejection (PATH_TRAVERSAL_REJECTED) and aborts
    without writing through the symlink. Note: outcome falls into the
    default `render_failed` bucket because PATH_TRAVERSAL_REJECTED is not
    explicitly mapped in `_outcome_for`; the structured error code is the
    authoritative signal."""
    _bootstrap_clean(tmp_path)
    target = tmp_path / "scripts" / "compound" / "build.sh"
    assert target.is_file(), (
        "expected scripts/compound/build.sh to be a managed manifest file; "
        "manifest fixture changed?"
    )

    # Stage an attacker-writable file outside the repo and substitute a
    # symlink in place of the managed file.
    attacker = tmp_path.parent / f"attacker-{tmp_path.name}.sh"
    attacker.write_text("# attacker-controlled content\n", encoding="utf-8")
    target.unlink()
    target.symlink_to(attacker)
    assert target.is_symlink()

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    # The bootstrap aborts before any write through the symlink. The
    # error code is the canonical signal regardless of which outcome
    # bucket the engine routes to.
    assert result.outcome != "success", (
        f"expected non-success after symlink substitution; got {result.outcome!r}"
    )
    error_codes = {e.code for e in result.errors}
    assert BootstrapErrorCode.PATH_TRAVERSAL_REJECTED in error_codes, (
        f"expected PATH_TRAVERSAL_REJECTED in errors; got {error_codes!r}"
    )
    # Attacker content must not have been overwritten through the symlink.
    assert attacker.read_text(encoding="utf-8") == "# attacker-controlled content\n"


# --- Phase 11 DA3 augment: TOCTOU between sha verify and read ------------


def test_toctou_between_sha_verify_and_read_raises_manifest_tampered(tmp_path):
    """Phase 11 DA3 augment #2. Simulates a TOCTOU race where the
    manifest passed integrity-verify in a prior run but a per-file
    `source_template_sha256` is rewritten to a value that no longer
    matches the cached plugin-shipped template. The re-run reaches
    `_verify_manifest_integrity`, which calls
    `verify_source_template_shas` (`manifest_writer.py:286-299`) and
    detects the mismatch on consume -- raising MANIFEST_TAMPERED.

    Distinct from `test_edited_source_template_sha_raises_manifest_tampered`:
    that one mutates one entry; this scenario tampers a DIFFERENT entry
    AND the rendered_content_sha256 simultaneously, simulating a swap-
    after-verify attack where both the manifest hash field and the
    rendered-content claim were rewritten between bootstrap runs."""
    manifest_path = _bootstrap_clean(tmp_path)
    payload = _read_manifest(manifest_path)
    # Pick a different entry than test_edited_source_template_sha to keep
    # the surface distinct: scripts/compound/build.sh (entry index 1).
    target_entry = payload["files"][1]
    target_path = tmp_path / target_entry["path"]
    assert target_path.is_file()

    # Simulate a swap-after-verify: tamper BOTH source and rendered shas
    # simultaneously, mimicking an attacker who staged the file content
    # change AND the manifest field rewrite.
    target_entry["source_template_sha256"] = "1" * 64
    target_entry["rendered_content_sha256"] = "2" * 64
    _write_manifest(manifest_path, payload)

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "manifest_tampered", (
        f"expected manifest_tampered after TOCTOU-style double-tamper; "
        f"got {result.outcome!r}"
    )
    # The structured error code carries the integrity verdict.
    assert result.errors[0].code == BootstrapErrorCode.MANIFEST_TAMPERED
