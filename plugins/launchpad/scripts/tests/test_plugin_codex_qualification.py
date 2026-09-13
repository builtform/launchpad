"""Section 10 runtime qualification and implementation-closure tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
QUALIFICATION_PATH = SCRIPTS / "plugin-codex-qualification.py"
EVIDENCE_PATH = PLUGIN_ROOT / "codex" / "support-evidence.json"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


qualification = _load("plugin_codex_qualification_tests", QUALIFICATION_PATH)


def _evidence_digest(release: Any) -> str:
    return qualification._SUPPORT.evidence_digest(
        qualification._SUPPORT.evidence_bytes(release)
    )


def _candidate_receipt(release: Any) -> dict[str, object]:
    results = [
        {"id": item, "status": "PASS", "detail": item}
        for item in sorted(qualification._CANDIDATE_LIFECYCLE_PASS)
    ]
    results.extend(
        {"id": item, "status": "BLOCKED", "detail": item}
        for item in sorted(qualification._CANDIDATE_LIFECYCLE_BLOCKED)
    )
    return {
        "schema_version": 1,
        "overall": "BLOCKED",
        "runtime_payload_digest": release.runtime.runtime_payload_digest,
        "evidence_digest": _evidence_digest(release),
        "codex_home": "/private/tmp/lp-codex-section10-fixture",
        "hosts": {
            "claude": "2.1.258 (Claude Code)",
            "codex": "codex-cli 0.153.4",
        },
        "host_state_allowlist_version": qualification.HOST_STATE_ALLOWLIST_VERSION,
        "results": results,
    }


def _router_receipt(runtime_payload_digest: str) -> dict[str, object]:
    blocked = {
        "app-server-argument-tail-binding",
        "bare-lp-authenticated-routing",
        "cli-bare-lp-binding",
        "plugin-hook-ingress",
    }
    probes = (
        "app-server-argument-tail-binding",
        "app-server-typed-skill-selection",
        "bare-lp-authenticated-routing",
        "cli-bare-lp-binding",
        "codex-version",
        "internal-plugin-discovery",
        "plugin-hook-ingress",
        "sealed-install",
    )
    return {
        "codex_home": "/private/tmp/lp-codex-router-fixture",
        "runtime_payload_digest": runtime_payload_digest,
        "results": [
            {
                "probe": probe,
                "result": "BLOCKED" if probe in blocked else "PASS",
                "detail": "codex-cli 0.153.4" if probe == "codex-version" else probe,
            }
            for probe in probes
        ],
    }


def _lifecycle_receipt() -> dict[str, object]:
    passed = (
        "claude-current-strict-validation",
        "claude-current-validation",
        "claude-user-invocable-runtime-discovery",
        "codex-plugin-cleanup",
        "codex-plugin-install-list",
        "codex-plugin-update-disable",
        "host-versions",
        "installed-root-and-dual-manifest",
        "openai-yaml-omission",
        "typed-skill-input",
    )
    blocked = ("duplicate-skill-resolution", "enforcement-boundaries")
    return {
        "overall": "BLOCKED",
        "fixture": "/fixture",
        "codex_home": "/private/tmp/lp-codex-lifecycle-fixture",
        "results": [
            {
                "id": identifier,
                "status": "PASS",
                "detail": (
                    "codex-cli 0.153.4; 2.1.258 (Claude Code)"
                    if identifier == "host-versions"
                    else identifier
                ),
            }
            for identifier in passed
        ]
        + [
            {"id": identifier, "status": "BLOCKED", "detail": identifier}
            for identifier in blocked
        ],
    }


def test_production_manifest_is_exact_projection_and_runtime_matches_section9() -> None:
    assert qualification._MANIFEST.sync_manifest(PLUGIN_ROOT, PLUGIN_ROOT, write=False)
    candidate = qualification.build_candidate()
    assert (
        candidate.runtime.runtime_payload_digest
        == qualification.SECTION9_RUNTIME_PAYLOAD_DIGEST
    )
    assert len(candidate.runtime.runtime_files) == 166
    assert candidate.runtime.stage == "test_candidate"
    assert candidate.runtime.release_stage == "dogfood"


def test_expected_release_qualifies_blocked_support_without_promotion() -> None:
    release = qualification.build_expected_release()
    assert release.runtime.stage == "release"
    assert release.runtime.release_stage == "dogfood"
    assert release.runtime.qualification_ids == (qualification.QUALIFICATION_ID,)
    assert all(item.base_support_state == "blocked" for item in release.runtime.support)
    assert all(
        item.qualification_ids == (qualification.QUALIFICATION_ID,)
        for item in release.compatibility_predicates
    )
    assert release.qualifications[0].receipt_ids == tuple(
        sorted(qualification.QUALIFICATION_RECEIPT_IDS)
    )
    assert "artifact_digest" not in qualification._SUPPORT.bundle_as_dict(release)


def test_committed_release_evidence_is_exact_generated_output() -> None:
    release, raw = qualification._checked_release()
    summary = qualification.qualification_summary(release, evidence_raw=raw)
    assert summary["status"] == "pass"
    assert summary["supported_roots"] == 0
    assert summary["blocked_roots"] == 44
    assert summary["beta_release_acceptance"] == "blocked"
    assert len(summary["runtime_payload_digest"]) == 64
    assert len(summary["evidence_digest"]) == 64


def test_hand_editing_release_evidence_fails_check(tmp_path: Path) -> None:
    staged = tmp_path / "launchpad"
    shutil.copytree(
        PLUGIN_ROOT,
        staged,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    evidence = staged / "codex" / "support-evidence.json"
    value = json.loads(evidence.read_text(encoding="utf-8"))
    value["qualifications"][0]["receipt_ids"][0] = "hand-edited-receipt"
    evidence.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(qualification.QualificationError) as raised:
        qualification.check_release(plugin_root=staged, evidence_path=evidence)
    assert raised.value.code == "INTEGRITY_MISMATCH"


def test_format_only_release_evidence_rewrite_fails_raw_byte_check(
    tmp_path: Path,
) -> None:
    staged = tmp_path / "launchpad"
    shutil.copytree(
        PLUGIN_ROOT,
        staged,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    evidence = staged / "codex" / "support-evidence.json"
    value = json.loads(evidence.read_text(encoding="utf-8"))
    evidence.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(qualification.QualificationError) as raised:
        qualification.check_release(plugin_root=staged, evidence_path=evidence)
    assert raised.value.code == "INTEGRITY_MISMATCH"


def test_generate_release_writes_deterministic_raw_byte_attestation(
    tmp_path: Path,
) -> None:
    staged = tmp_path / "launchpad"
    shutil.copytree(
        PLUGIN_ROOT,
        staged,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    report = qualification._ACCEPTANCE.build_report(plugin_root=staged)
    expected = qualification.build_expected_release(staged, acceptance_report=report)
    report_path = tmp_path / "acceptance.json"
    router_path = tmp_path / "router.json"
    lifecycle_path = tmp_path / "lifecycle.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    router_path.write_text(
        json.dumps(_router_receipt(expected.runtime.runtime_payload_digest)),
        encoding="utf-8",
    )
    lifecycle_path.write_text(json.dumps(_lifecycle_receipt()), encoding="utf-8")
    evidence = staged / "codex" / "support-evidence.json"

    summary = qualification.generate_release(
        plugin_root=staged,
        acceptance_report_path=report_path,
        router_receipt_path=router_path,
        lifecycle_receipt_path=lifecycle_path,
        output_path=evidence,
    )

    raw = evidence.read_bytes()
    assert raw == qualification._SUPPORT.evidence_bytes(expected)
    assert summary["evidence_digest"] == hashlib.sha256(raw).hexdigest()
    assert qualification.check_release(plugin_root=staged, evidence_path=evidence)


def test_acceptance_report_cannot_promote_a_root() -> None:
    report = qualification._ACCEPTANCE.build_report()
    report["corpus"]["classifications"][0]["base_support_state"] = "supported"
    with pytest.raises(qualification.QualificationError) as raised:
        qualification.validate_acceptance_report(report)
    assert raised.value.code == "UNVERIFIED_SUPPORT_ADVERTISED"


def test_candidate_lifecycle_receipt_binds_exact_release_and_blockers() -> None:
    release = qualification.check_release()
    receipt = _candidate_receipt(release)
    result = qualification.validate_candidate_lifecycle_receipt(
        receipt,
        release=release,
        codex_version="0.153.4",
        claude_version="2.1.258",
        expected_evidence_digest=_evidence_digest(release),
    )
    assert result == {
        "status": "pass",
        "overall_support": "blocked",
        "runtime_payload_digest": release.runtime.runtime_payload_digest,
        "evidence_digest": _evidence_digest(release),
        "advertised_capability_families": [],
    }

    receipt["results"][-1]["status"] = "PASS"
    with pytest.raises(qualification.QualificationError) as raised:
        qualification.validate_candidate_lifecycle_receipt(
            receipt,
            release=release,
            codex_version="0.153.4",
            claude_version="2.1.258",
            expected_evidence_digest=_evidence_digest(release),
        )
    assert raised.value.code == "HOST_RECEIPT_INVALID"


def test_candidate_lifecycle_rejects_personal_codex_state() -> None:
    release = qualification.check_release()
    receipt = _candidate_receipt(release)
    receipt["codex_home"] = "/Users/example/.codex"
    with pytest.raises(qualification.QualificationError) as raised:
        qualification.validate_candidate_lifecycle_receipt(
            receipt,
            release=release,
            codex_version="0.153.4",
            claude_version="2.1.258",
            expected_evidence_digest=_evidence_digest(release),
        )
    assert raised.value.code == "HOST_RECEIPT_INVALID"


def test_completed_candidate_lifecycle_binds_detached_artifact_digest() -> None:
    release = qualification.check_release()
    receipt = _candidate_receipt(release)
    artifact_digest = "a" * 64
    receipt["schema_version"] = 2
    receipt["artifact_digest"] = artifact_digest

    result = qualification.validate_candidate_lifecycle_receipt(
        receipt,
        release=release,
        codex_version="0.153.4",
        claude_version="2.1.258",
        expected_evidence_digest=_evidence_digest(release),
        artifact_digest=artifact_digest,
    )
    assert result["artifact_digest"] == artifact_digest

    with pytest.raises(qualification.QualificationError) as raised:
        qualification.validate_candidate_lifecycle_receipt(
            receipt,
            release=release,
            codex_version="0.153.4",
            claude_version="2.1.258",
            expected_evidence_digest=_evidence_digest(release),
            artifact_digest="b" * 64,
        )
    assert raised.value.code == "HOST_RECEIPT_INVALID"


def test_release_package_surface_is_manifest_plus_bare_lp_router(
    tmp_path: Path,
) -> None:
    release = qualification.check_release()
    package = tmp_path / "release-package"
    package.mkdir()
    qualification._MANIFEST.project_package(
        release,
        PLUGIN_ROOT,
        package,
        include_generated=False,
    )
    inventory = qualification._ACCEPTANCE.generate_surface_inventory(
        package,
        stage="release",
    )
    active = {
        item.path: item.reason
        for item in inventory.records
        if item.disposition == "active"
    }
    assert active == {
        ".codex-plugin/plugin.json": "qualified_release",
        "codex/skills/lp/SKILL.md": "single_public_entry",
    }
