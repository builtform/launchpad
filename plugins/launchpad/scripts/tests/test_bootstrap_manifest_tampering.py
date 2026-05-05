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
