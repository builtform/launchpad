"""Qualify the unchanged Section 9 runtime and verify release evidence.

This closure authority consumes the Section 9 acceptance report and pinned
host receipts. It never rebuilds support policy from those receipts. The
support producer remains the only graph and support-state authority, while
this module proves that the committed release evidence is the deterministic
promotion of the exact runtime bytes accepted in Section 9.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, NoReturn, cast

SCRIPT_REAL_PATH: Final = Path(os.path.realpath(__file__))
SCRIPT_DIR: Final = SCRIPT_REAL_PATH.parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
PROTOCOL_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"
SUPPORT_PATH: Final = SCRIPT_DIR / "plugin-codex-support.py"
MANIFEST_PATH: Final = SCRIPT_DIR / "plugin-codex-manifest.py"
ACCEPTANCE_PATH: Final = SCRIPT_DIR / "plugin-codex-acceptance.py"
DEFAULT_EVIDENCE_PATH: Final = PLUGIN_ROOT / "codex" / "support-evidence.json"

# Resealed after the Section 10 lifecycle gate found and corrected the missing
# self-hosted import closure and active root command surface. The affected
# Section 5 and Section 9 gates must pass again before this exact 166-file
# runtime payload can be promoted.
SECTION9_RUNTIME_PAYLOAD_DIGEST: Final = (
    "d444890666ad7a587eee92bae68c93fc89ec0ea9315a6c19bf6422c338af9b94"
)
QUALIFICATION_ID: Final = "qualification-section10-blocked-support"
QUALIFICATION_RECEIPT_IDS: Final = (
    "section7-safety-coordinator-fixture",
    "section8-harden-plan-fixture",
    "section9-lifecycle-host-blocked",
    "section9-router-host-blocked",
    "section9-whole-corpus-acceptance",
)
HOST_STATE_ALLOWLIST_VERSION: Final = 2

_CANDIDATE_LIFECYCLE_PASS: Final = frozenset(
    {
        "candidate-help",
        "candidate-package-closure",
        "cleanup",
        "claude-first-codex-second",
        "codex-first-claude-second",
        "codex-update-repair",
        "disable-enable",
        "harden-plan-refusal",
        "host-state-allowlist",
        "no-mutation-owner",
        "removal-isolation",
        "simultaneous-read-only",
        "stale-session-refusal",
        "zero-mutation-refusal",
    }
)
_CANDIDATE_LIFECYCLE_BLOCKED: Final = frozenset({"bare-lp-authenticated-routing"})


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_module("launchpad_codex_protocol_for_qualification", PROTOCOL_PATH)
_SUPPORT = _load_module("launchpad_codex_support_for_qualification", SUPPORT_PATH)
_MANIFEST = _load_module("launchpad_codex_manifest_for_qualification", MANIFEST_PATH)
_ACCEPTANCE = _load_module(
    "launchpad_codex_acceptance_for_qualification", ACCEPTANCE_PATH
)


class QualificationError(ValueError):
    """Stable qualification or implementation-closure failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise QualificationError(code, message)


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _fail("RECORD_INVALID", f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _load_json(path: Path) -> object:
    protocol = _PROTOCOL.load_protocol()
    return _SUPPORT._strict_load_json(
        path,
        maximum_bytes=protocol.limits["documentation_file_bytes"],
    )


def validate_acceptance_report(value: object) -> Mapping[str, str]:
    """Validate the exact fail-closed Section 9 qualification inputs."""

    report = _mapping(value, "acceptance report")
    expected_fields = {
        "schema_version",
        "ci_acceptance",
        "beta_release_acceptance",
        "workflow",
        "surfaces",
        "corpus",
        "fixed_beta_minimum",
        "observations",
        "boundaries",
    }
    if set(report) != expected_fields or report.get("schema_version") != 1:
        _fail("RECORD_INVALID", "acceptance report fields differ")
    if (
        report.get("ci_acceptance") != "pass"
        or report.get("beta_release_acceptance") != "blocked"
    ):
        _fail("UNVERIFIED_SUPPORT_ADVERTISED", "acceptance boundary changed")

    corpus = _mapping(report.get("corpus"), "acceptance corpus")
    classifications = corpus.get("classifications")
    if (
        corpus.get("nodes") != 94
        or corpus.get("commands") != 42
        or corpus.get("public_builtin_skills") != 2
        or corpus.get("classified_roots") != 44
        or corpus.get("advertised_roots") != []
        or corpus.get("advertised_capability_families") != []
        or not isinstance(classifications, list)
        or len(classifications) != 44
    ):
        _fail("CORPUS_CLASSIFICATION_INCOMPLETE", "acceptance corpus changed")
    for item in classifications:
        record = _mapping(item, "acceptance classification")
        if (
            record.get("base_support_state") != "blocked"
            or record.get("qualification_ids") != []
            or record.get("blocked_reason_codes")
            != ["WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN"]
        ):
            _fail(
                "UNVERIFIED_SUPPORT_ADVERTISED",
                "Section 9 contains an unqualified support claim",
            )

    fixed = _mapping(report.get("fixed_beta_minimum"), "fixed beta minimum")
    if set(fixed) != {"router_help", "zero_mutation", "harden_plan"}:
        _fail("FIXED_BETA_INCOMPLETE", "fixed beta set changed")
    for value in fixed.values():
        item = _mapping(value, "fixed beta entry")
        if (
            item.get("fixture_acceptance") != "pass"
            or item.get("real_host_acceptance") != "blocked"
        ):
            _fail("FIXED_BETA_INCOMPLETE", "fixed beta boundary changed")

    workflow = _mapping(report.get("workflow"), "acceptance workflow")
    pins = _mapping(workflow.get("pins"), "workflow pins")
    expected_pins = {"CLAUDE_CODE_VERSION", "CODEX_CLI_VERSION", "PYTHON_VERSION"}
    if set(pins) != expected_pins or any(
        not isinstance(value, str) or not value for value in pins.values()
    ):
        _fail("CI_TIER_INCOMPLETE", "qualification host pins are invalid")
    return cast(Mapping[str, str], pins)


def build_candidate(plugin_root: Path = PLUGIN_ROOT) -> Any:
    """Seal the committed production root and enforce the Section 9 digest."""

    root = plugin_root.resolve(strict=True)
    if not _MANIFEST.sync_manifest(root, root, write=False):
        _fail("INTEGRITY_MISMATCH", "production Codex manifest is absent or stale")
    candidate = _SUPPORT.build_test_candidate(root, release_stage="dogfood")
    if candidate.runtime.runtime_payload_digest != SECTION9_RUNTIME_PAYLOAD_DIGEST:
        _fail(
            "INTEGRITY_MISMATCH",
            "runtime payload differs from the exact Section 9 candidate",
        )
    if len(candidate.runtime.runtime_files) != 166:
        _fail("INTEGRITY_MISMATCH", "Section 9 runtime file count changed")
    _SUPPORT.verify_runtime_set(candidate, root)
    return candidate


def _qualification_input(candidate: Any, pins: Mapping[str, str]) -> dict[str, object]:
    predicates: list[dict[str, object]] = []
    for item in candidate.compatibility_predicates:
        value = _SUPPORT._jsonable(item)
        if not isinstance(value, dict):
            raise TypeError("predicate serialization failed")
        if (
            value.get("base_support_state") != "blocked"
            or value.get("qualification_ids") != []
        ):
            _fail(
                "UNVERIFIED_SUPPORT_ADVERTISED",
                "candidate support must remain blocked before qualification",
            )
        value["qualification_ids"] = [QUALIFICATION_ID]
        predicates.append(value)
    qualification = {
        "qualification_id": QUALIFICATION_ID,
        "runtime_payload_digest": candidate.runtime.runtime_payload_digest,
        "host": "codex-cli-and-claude-code",
        "operating_system": "darwin",
        "tool_versions": {
            "claude-code": pins["CLAUDE_CODE_VERSION"],
            "codex-cli": pins["CODEX_CLI_VERSION"],
        },
        "receipt_ids": list(QUALIFICATION_RECEIPT_IDS),
    }
    return {
        "compatibility_predicates": predicates,
        "qualifications": [qualification],
    }


def build_expected_release(
    plugin_root: Path = PLUGIN_ROOT,
    *,
    acceptance_report: object | None = None,
) -> Any:
    """Build the one deterministic blocked-support release record."""

    report = (
        _ACCEPTANCE.build_report(plugin_root=plugin_root)
        if acceptance_report is None
        else acceptance_report
    )
    pins = validate_acceptance_report(report)
    candidate = build_candidate(plugin_root)
    release = _SUPPORT.promote_release(candidate, _qualification_input(candidate, pins))
    if release.runtime.release_stage != "dogfood":
        _fail("RECORD_STAGE_INVALID", "implementation candidate must stay dogfood")
    if any(item.base_support_state != "blocked" for item in release.runtime.support):
        _fail("UNVERIFIED_SUPPORT_ADVERTISED", "qualification promoted support")
    return release


def generate_release(
    *,
    plugin_root: Path,
    acceptance_report_path: Path,
    router_receipt_path: Path,
    lifecycle_receipt_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Validate Section 9 receipts and write deterministic release evidence."""

    root = plugin_root.resolve(strict=True)
    expected_output = root / "codex" / "support-evidence.json"
    if output_path.absolute() != expected_output:
        _fail("PATH_INVALID", "release evidence must use the protocol-fixed slot")
    report = _load_json(acceptance_report_path)
    pins = validate_acceptance_report(report)
    release = build_expected_release(root, acceptance_report=report)
    _ACCEPTANCE.verify_router_host_receipt(
        router_receipt_path,
        expected_codex_version=pins["CODEX_CLI_VERSION"],
        expected_runtime_payload_digest=release.runtime.runtime_payload_digest,
    )
    _ACCEPTANCE.verify_lifecycle_host_receipt(
        lifecycle_receipt_path,
        expected_codex_version=pins["CODEX_CLI_VERSION"],
        expected_claude_version=pins["CLAUDE_CODE_VERSION"],
    )
    _SUPPORT.write_bundle(release, expected_output, trusted_root=root)
    return qualification_summary(release)


def check_release(
    *,
    plugin_root: Path = PLUGIN_ROOT,
    evidence_path: Path = DEFAULT_EVIDENCE_PATH,
) -> Any:
    """Reject stale, hand-edited, or self-inconsistent release evidence."""

    root = plugin_root.resolve(strict=True)
    expected_path = root / "codex" / "support-evidence.json"
    if evidence_path.absolute() != expected_path:
        _fail("PATH_INVALID", "release evidence must use the protocol-fixed slot")
    expected = build_expected_release(root)
    actual = _SUPPORT.load_bundle(
        expected_path,
        protocol_path=root / "codex" / "adapter-protocol.json",
    )
    if _SUPPORT.evidence_bytes(actual) != _SUPPORT.evidence_bytes(expected):
        _fail("INTEGRITY_MISMATCH", "release evidence differs from generated output")
    _SUPPORT.verify_runtime_set(actual, root)
    return actual


def qualification_summary(release: Any) -> dict[str, object]:
    supported = sum(
        item.base_support_state == "supported" for item in release.runtime.support
    )
    return {
        "status": "pass",
        "release_stage": release.runtime.release_stage,
        "runtime_payload_digest": release.runtime.runtime_payload_digest,
        "evidence_digest": _SUPPORT.evidence_digest(release),
        "qualification_ids": list(release.runtime.qualification_ids),
        "receipt_ids": list(release.qualifications[0].receipt_ids),
        "supported_roots": supported,
        "blocked_roots": len(release.runtime.support) - supported,
        "beta_release_acceptance": "blocked",
    }


def validate_candidate_lifecycle_receipt(
    value: object,
    *,
    release: Any,
    codex_version: str,
    claude_version: str,
) -> dict[str, object]:
    """Validate the isolated exact-candidate lifecycle and coexistence receipt."""

    receipt = _mapping(value, "candidate lifecycle receipt")
    expected_fields = {
        "schema_version",
        "overall",
        "runtime_payload_digest",
        "evidence_digest",
        "codex_home",
        "hosts",
        "host_state_allowlist_version",
        "results",
    }
    if set(receipt) != expected_fields or receipt.get("schema_version") != 1:
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle fields differ")
    if receipt.get("overall") != "BLOCKED":
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle must remain fail-closed")
    if receipt.get(
        "runtime_payload_digest"
    ) != release.runtime.runtime_payload_digest or receipt.get(
        "evidence_digest"
    ) != _SUPPORT.evidence_digest(release):
        _fail("INTEGRITY_MISMATCH", "candidate lifecycle binds another release")
    codex_home = receipt.get("codex_home")
    if (
        not isinstance(codex_home, str)
        or not Path(codex_home).is_absolute()
        or ".." in Path(codex_home).parts
        or not Path(codex_home).name.startswith("lp-codex-")
    ):
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle used non-isolated state")
    hosts = _mapping(receipt.get("hosts"), "candidate lifecycle hosts")
    if hosts != {
        "claude": f"{claude_version} (Claude Code)",
        "codex": f"codex-cli {codex_version}",
    }:
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle host versions differ")
    if receipt.get("host_state_allowlist_version") != HOST_STATE_ALLOWLIST_VERSION:
        _fail("HOST_RECEIPT_INVALID", "host-state allowlist version differs")

    results = receipt.get("results")
    if not isinstance(results, list):
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle results must be a list")
    by_id: dict[str, str] = {}
    maximum = _PROTOCOL.load_protocol().limits["diagnostic_field_characters"]
    for value in results:
        item = _mapping(value, "candidate lifecycle result")
        if set(item) != {"id", "status", "detail"}:
            _fail("HOST_RECEIPT_INVALID", "candidate lifecycle result fields differ")
        identifier = item.get("id")
        status = item.get("status")
        detail = item.get("detail")
        if (
            not isinstance(identifier, str)
            or _PROTOCOL.load_protocol().name_pattern.fullmatch(identifier) is None
            or identifier in by_id
            or status not in {"PASS", "BLOCKED"}
            or not isinstance(detail, str)
            or len(detail) > maximum
        ):
            _fail("HOST_RECEIPT_INVALID", "candidate lifecycle result is invalid")
        by_id[identifier] = cast(str, status)
    if set(by_id) != _CANDIDATE_LIFECYCLE_PASS | _CANDIDATE_LIFECYCLE_BLOCKED:
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle probe set differs")
    if any(by_id[item] != "PASS" for item in _CANDIDATE_LIFECYCLE_PASS) or any(
        by_id[item] != "BLOCKED" for item in _CANDIDATE_LIFECYCLE_BLOCKED
    ):
        _fail("HOST_RECEIPT_INVALID", "candidate lifecycle outcome changed")
    return {
        "status": "pass",
        "overall_support": "blocked",
        "runtime_payload_digest": release.runtime.runtime_payload_digest,
        "evidence_digest": _SUPPORT.evidence_digest(release),
        "advertised_capability_families": [],
    }


def verify_candidate_lifecycle(
    path: Path,
    *,
    plugin_root: Path,
    codex_version: str,
    claude_version: str,
) -> dict[str, object]:
    release = check_release(plugin_root=plugin_root)
    return validate_candidate_lifecycle_receipt(
        _load_json(path),
        release=release,
        codex_version=codex_version,
        claude_version=claude_version,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--plugin-root", type=Path, default=PLUGIN_ROOT)
    generate.add_argument("--acceptance-report", type=Path, required=True)
    generate.add_argument("--router-receipt", type=Path, required=True)
    generate.add_argument("--lifecycle-receipt", type=Path, required=True)
    generate.add_argument("--output", type=Path, default=DEFAULT_EVIDENCE_PATH)

    check = subparsers.add_parser("check")
    check.add_argument("--plugin-root", type=Path, default=PLUGIN_ROOT)
    check.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE_PATH)

    lifecycle = subparsers.add_parser("verify-candidate-lifecycle")
    lifecycle.add_argument("--plugin-root", type=Path, default=PLUGIN_ROOT)
    lifecycle.add_argument("--receipt", type=Path, required=True)
    lifecycle.add_argument("--codex-version", required=True)
    lifecycle.add_argument("--claude-version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            result = generate_release(
                plugin_root=args.plugin_root,
                acceptance_report_path=args.acceptance_report,
                router_receipt_path=args.router_receipt,
                lifecycle_receipt_path=args.lifecycle_receipt,
                output_path=args.output,
            )
        elif args.command == "check":
            result = qualification_summary(
                check_release(
                    plugin_root=args.plugin_root,
                    evidence_path=args.evidence,
                )
            )
        else:
            result = verify_candidate_lifecycle(
                args.receipt,
                plugin_root=args.plugin_root,
                codex_version=args.codex_version,
                claude_version=args.claude_version,
            )
        sys.stdout.buffer.write(_pretty_json(result))
        return 0
    except (
        QualificationError,
        _PROTOCOL.ProtocolValidationError,
        _SUPPORT.SupportError,
        _MANIFEST.ManifestError,
        _ACCEPTANCE.AcceptanceError,
    ) as exc:
        code = getattr(exc, "code", "UNKNOWN_ERROR")
        sys.stderr.buffer.write(
            _pretty_json(
                {
                    "error": code,
                    "message": str(exc),
                    "reporting_class": _PROTOCOL.load_protocol().reporting_class_for_error(
                        code
                    ),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
