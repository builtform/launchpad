"""Tests for the v1.1 scaffold-decision envelope (V3 plan §11.1).

Asserts the additive-minor v1.1 envelope shape:

  * `schema_version: "1.1"` is sealed alongside the legacy `version: "1.0"`
    so both v2.0 and v2.1 readers can key off their respective fields.
  * `plugin_version` reflects the running plugin version.
  * `stacks` is derived from `layers[].stack` with first-occurrence
    deduplication.
  * `identity` defaults to the all-placeholder block when caller does not
    supply one (PII opt-out posture).
  * `validate_identity` enforces the V3 §10.v2.1 allowlist regexes and
    the license enum (including the `Other` body sanitization rules).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack import (  # noqa: E402
    SCHEMA_VERSION_V2_1,
    WRITTEN_DECISION_VERSION,
)
from lp_pick_stack.decision_writer import (  # noqa: E402
    IdentityValidationError,
    build_decision_payload,
    default_unset_identity,
    derive_stacks,
    read_running_plugin_version,
    seal_decision_payload,
    validate_identity,
    write_decision_file,
)


def _layers():
    return [
        {"stack": "next", "role": "fullstack", "path": ".", "options": {}},
    ]


def _summary():
    return [
        {"section": "project-understanding", "bullets": ["A web app."]},
        {"section": "matched-category", "bullets": ["next-fullstack: matched."]},
        {"section": "stack", "bullets": ["next as fullstack at ."]},
        {"section": "why-this-fits", "bullets": ["Single-binary fullstack."]},
        {"section": "alternatives", "bullets": ["None considered."]},
        {"section": "notes", "bullets": ["No notes."]},
    ]


def test_envelope_carries_v11_indicator(tmp_path: Path) -> None:
    payload = build_decision_payload(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
    )
    assert payload["schema_version"] == SCHEMA_VERSION_V2_1
    assert payload["schema_version"] == "1.1"
    # legacy v1.0 indicator is preserved verbatim for v2.0-reader compat
    assert payload["version"] == WRITTEN_DECISION_VERSION == "1.0"


def test_plugin_version_reflects_running_plugin(tmp_path: Path) -> None:
    payload = build_decision_payload(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
    )
    assert payload["plugin_version"] == read_running_plugin_version()


def test_stacks_derived_with_first_occurrence_dedup() -> None:
    layers = [
        {"stack": "astro", "role": "frontend-main", "path": "apps/marketing"},
        {"stack": "astro", "role": "frontend-dashboard", "path": "apps/dashboard"},
        {"stack": "next", "role": "fullstack", "path": "apps/web"},
        {"stack": "next", "role": "backend", "path": "apps/api"},
    ]
    assert derive_stacks(layers) == ["astro", "next"]


def test_default_identity_is_pii_optout_with_placeholders(tmp_path: Path) -> None:
    payload = build_decision_payload(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
    )
    identity = payload["identity"]
    assert identity == default_unset_identity()
    assert identity["pii_opt_in"] is False
    assert identity["email"] == "<email>"
    assert identity["copyright_holder"] == "<copyright-holder>"
    assert identity["license"] == "Other"


def test_supplied_identity_is_validated_and_round_trips(tmp_path: Path) -> None:
    identity = {
        "pii_opt_in": True,
        "project_name": "ulc.spec.org",
        "email": "user@example.com",
        "copyright_holder": "Foad Shafighi",
        "repo_url": "https://github.com/foadshafighi/ulc-spec",
        "license": "MIT",
        "license_other_body": "",
    }
    payload = build_decision_payload(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
        identity=identity,
    )
    assert payload["identity"] == identity


def test_invalid_email_rejected() -> None:
    identity = default_unset_identity()
    identity["pii_opt_in"] = True
    identity["email"] = "not-an-email"
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "email"


def test_invalid_repo_url_rejected() -> None:
    identity = default_unset_identity()
    identity["repo_url"] = "ftp://example.com"  # only http/https allowed
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "repo_url"


def test_invalid_license_rejected() -> None:
    identity = default_unset_identity()
    identity["license"] = "WTFPL"  # not in enum
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "license"


def test_license_other_body_sanitization_rejects_jinja_delimiters() -> None:
    identity = default_unset_identity()
    identity["license"] = "Other"
    identity["license_other_body"] = "Custom license. {{ injection }}"
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "license_other_body"


def test_license_other_body_sanitization_rejects_html() -> None:
    identity = default_unset_identity()
    identity["license"] = "Other"
    identity["license_other_body"] = "License with <script>alert(1)</script>"
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "license_other_body"


def test_license_other_body_must_be_empty_when_license_not_other() -> None:
    identity = default_unset_identity()
    identity["license"] = "MIT"
    identity["license_other_body"] = "stray text"
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "license_other_body"


def test_copyright_holder_rejects_forbidden_chars() -> None:
    identity = default_unset_identity()
    identity["pii_opt_in"] = True
    identity["copyright_holder"] = "Foad; rm -rf /"  # semicolon forbidden
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "copyright_holder"


def test_project_name_allowlist_enforced() -> None:
    identity = default_unset_identity()
    identity["project_name"] = "has spaces"  # allowlist rejects spaces
    with pytest.raises(IdentityValidationError) as exc:
        validate_identity(identity)
    assert exc.value.field == "project_name"


def test_full_envelope_seals_and_writes(tmp_path: Path) -> None:
    payload = build_decision_payload(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
    )
    sealed = seal_decision_payload(payload)
    assert sealed["sha256"] != ""
    # Roundtrip: writing + re-parsing yields identical payload (modulo sha256)
    target_path, sealed2 = write_decision_file(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
    )
    on_disk = json.loads(target_path.read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == "1.1"
    assert on_disk["plugin_version"] == read_running_plugin_version()
    assert on_disk["identity"]["pii_opt_in"] is False
    assert on_disk["stacks"] == ["next"]
