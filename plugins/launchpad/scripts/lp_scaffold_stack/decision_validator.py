"""scaffold-decision.json validator (HANDSHAKE §4 rules 1-13).

Implements 12 of 13 rules. Rule 12 (`brainstorm_session_id`) is BL-235
deferred per HANDSHAKE §1.5 strip-back — this validator does NOT check the
field; pick-stack writers OMIT it; consumers do NOT require it.

Returns either Accepted(payload) or Rejected(reason, field_name, ...). Each
rule failure produces a distinct `reason:` enum value (matched against the
HANDSHAKE §4 rejection reason set). The first failure wins; later rules are
skipped on failure (the user fixes one cause at a time).

Layer 8 closure: at execute-time the engine re-validates every layer.path
against §6 path validator + ancestor-symlink check; this validator runs both
checks at read-time so the rejection surfaces before subprocess execution.
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

# Make sibling-module imports work when invoked as a library from outside the
# package (mirrors lp_pick_stack/engine.py).
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash  # noqa: E402
from path_validator import (  # noqa: E402
    PathValidationError,
    validate_relative_path,
)

from lp_scaffold_stack import EXPECTED_DECISION_VERSION  # noqa: E402

# UUIDv4 hex format (32 hex chars).
_UUID4_HEX_RE = re.compile(r"^[0-9a-f]{32}$")
# ISO 8601 UTC sec-precision format with Z suffix.
_ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Replay window per HANDSHAKE §4 rule 9: 4 hours.
GENERATED_AT_MAX_AGE = timedelta(hours=4)

# Required top-level fields. brainstorm_session_id intentionally OMITTED per
# Layer 7 strip-back (BL-235).
_REQUIRED_FIELDS = (
    "version", "layers", "monorepo", "matched_category_id", "rationale_path",
    "rationale_sha256", "rationale_summary", "generated_by", "generated_at",
    "nonce", "bound_cwd", "sha256",
)

# Required scaffold-decision.json `rationale_summary` section names.
_RATIONALE_SECTIONS = (
    "project-understanding", "matched-category", "stack",
    "why-this-fits", "alternatives", "notes",
)

# Per HANDSHAKE §4 rule 2 / pick-stack plan §3.4.
ALLOWED_ROLES = frozenset({
    "frontend", "backend", "frontend-main", "frontend-dashboard",
    "fullstack", "mobile", "backend-managed", "desktop",
})

# Manual-override sentinel id (HANDSHAKE §4 rule 4).
MANUAL_OVERRIDE_ID = "manual-override"

# Sanitization filter for rationale_summary bullets — re-applied at read-time
# per HANDSHAKE §4 rule 7 + §9.1. Mirrors the pick-stack-side regex.
_FORBIDDEN_BULLET_RE = re.compile(
    r"```|<|>|http://|https://|file://|data:|javascript:|vbscript:",
    re.IGNORECASE,
)
# Maximum bullet length (HANDSHAKE §9.1 MAX_BULLET_CHARS).
_MAX_BULLET_CHARS = 240


@dataclass(frozen=True)
class Accepted:
    """Validation passed. Payload (with sha256 verified) is included."""

    payload: dict
    nonce: str
    bound_cwd: dict


@dataclass(frozen=True)
class Rejected:
    """Validation failed. `reason` is the §4 enum tag; `field_name` names
    the offending field for telemetry/forensic use."""

    reason: str
    message: str
    field_name: str | None = None
    seen_version: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _parse_iso_utc_sec(value: str) -> datetime | None:
    """Parse an ISO 8601 UTC sec-precision Z-suffix string; return None on
    format mismatch."""
    if not isinstance(value, str) or not _ISO_Z_RE.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def _validate_layer_paths(
    layers: list[dict],
    cwd: Path,
) -> Rejected | None:
    """Re-validate every layer.path against §6 (Layer 8 closure: defends
    against same-UID attacker swapping the JSON between pick-stack write and
    scaffold-stack execute, even though that threat is out-of-scope)."""
    seen_paths: set[str] = set()
    for i, layer in enumerate(layers):
        path = layer.get("path")
        if not isinstance(path, str):
            return Rejected(
                reason="layer_path_invalid",
                message=f"layers[{i}].path must be a string",
                field_name=f"layers[{i}].path",
            )
        try:
            validate_relative_path(path, cwd, field_name=f"layers[{i}].path")
        except PathValidationError as exc:
            # Distinguish path traversal from generic shape failure for the
            # rejection enum (HANDSHAKE §4 path_traversal).
            msg = str(exc)
            reason = "path_traversal" if "traversal" in msg or "escapes cwd" in msg else "layer_path_invalid"
            return Rejected(
                reason=reason,
                message=msg,
                field_name=exc.field_name,
            )
        # HANDSHAKE §4 rule 3 explicitly permits monorepo=false + len(layers)>1
        # when all layers share path == "." (single-dir overlay layers). Skip
        # duplicate-path rejection in that case so the rule 3 carve-out is
        # reachable; rule 1 already enforced the monorepo+layers shape, and
        # the writer-side `manual_override_resolver` guards against accidental
        # duplicates outside the path == "." case.
        if path in seen_paths and path != ".":
            return Rejected(
                reason="layer_paths_collide",
                message=f"layers[{i}].path={path!r} duplicates an earlier layer",
                field_name=f"layers[{i}].path",
            )
        seen_paths.add(path)
    return None


def _validate_layer_options(
    layers: list[dict],
    scaffolders: dict,
) -> Rejected | None:
    for i, layer in enumerate(layers):
        stack_id = layer.get("stack")
        scaffolder = scaffolders.get(stack_id)
        if scaffolder is None:
            return Rejected(
                reason="unknown_stack_id",
                message=f"layers[{i}].stack={stack_id!r} is not in scaffolders.yml",
                field_name=f"layers[{i}].stack",
            )
        role = layer.get("role")
        if role not in ALLOWED_ROLES:
            return Rejected(
                reason="layer_role_invalid",
                message=f"layers[{i}].role={role!r} not in ALLOWED_ROLES",
                field_name=f"layers[{i}].role",
            )
        options = layer.get("options", {}) or {}
        if not isinstance(options, dict):
            return Rejected(
                reason="layer_options_invalid",
                message=f"layers[{i}].options must be a dict, got {type(options).__name__}",
                field_name=f"layers[{i}].options",
            )
        allowed_options = set((scaffolder.get("options_schema") or {}).keys())
        for key in options:
            if key not in allowed_options:
                return Rejected(
                    reason="layer_options_unknown_key",
                    message=(
                        f"layers[{i}].options.{key!r} not in scaffolder "
                        f"options_schema {sorted(allowed_options)!r}"
                    ),
                    field_name=f"layers[{i}].options.{key}",
                )
    return None


def _validate_rationale_summary(rs: list) -> Rejected | None:
    if not isinstance(rs, list) or not rs:
        return Rejected(
            reason="rationale_summary_empty",
            message="rationale_summary must be a non-empty array",
            field_name="rationale_summary",
        )
    seen_sections: set[str] = set()
    has_any_bullet = False
    for i, section in enumerate(rs):
        if not isinstance(section, dict):
            return Rejected(
                reason="rationale_summary_invalid",
                message=f"rationale_summary[{i}] must be a dict",
                field_name=f"rationale_summary[{i}]",
            )
        name = section.get("section")
        bullets = section.get("bullets")
        if name not in _RATIONALE_SECTIONS:
            return Rejected(
                reason="rationale_summary_section_unknown",
                message=f"rationale_summary[{i}].section={name!r} not in {_RATIONALE_SECTIONS!r}",
                field_name=f"rationale_summary[{i}].section",
            )
        seen_sections.add(name)
        if not isinstance(bullets, list):
            return Rejected(
                reason="rationale_summary_invalid",
                message=f"rationale_summary[{i}].bullets must be a list",
                field_name=f"rationale_summary[{i}].bullets",
            )
        for j, bullet in enumerate(bullets):
            if not isinstance(bullet, str):
                return Rejected(
                    reason="rationale_summary_invalid",
                    message=f"rationale_summary[{i}].bullets[{j}] must be a string",
                    field_name=f"rationale_summary[{i}].bullets[{j}]",
                )
            if not bullet.strip():
                continue  # empty bullet — does not satisfy "≥1 non-empty"
            if len(bullet) > _MAX_BULLET_CHARS:
                return Rejected(
                    reason="forbidden_bullet_oversize",
                    message=(
                        f"rationale_summary[{i}].bullets[{j}] exceeds "
                        f"{_MAX_BULLET_CHARS} chars"
                    ),
                    field_name=f"rationale_summary[{i}].bullets[{j}]",
                )
            if _FORBIDDEN_BULLET_RE.search(unicodedata.normalize("NFKC", bullet)):
                return Rejected(
                    reason="forbidden_bullet_token",
                    message=(
                        f"rationale_summary[{i}].bullets[{j}] contains a "
                        "forbidden token (URL/HTML/code-fence)"
                    ),
                    field_name=f"rationale_summary[{i}].bullets[{j}]",
                )
            has_any_bullet = True
    if not has_any_bullet:
        return Rejected(
            reason="rationale_summary_empty",
            message="rationale_summary contains no non-empty bullets",
            field_name="rationale_summary",
        )
    return None


def _validate_bound_cwd(
    bc: Mapping,
    cwd: Path,
) -> Rejected | None:
    """Recompute (realpath, st_dev, st_ino) and assert all three match.

    Distinguishes UX (`bound_cwd_realpath_changed_inode_match`) from attack
    (`bound_cwd_inode_mismatch`) per HANDSHAKE §4 rule 11 + Layer 5 P1-A5.
    """
    if not isinstance(bc, dict):
        return Rejected(
            reason="bound_cwd_invalid",
            message="bound_cwd must be a dict",
            field_name="bound_cwd",
        )
    expected_realpath = bc.get("realpath")
    expected_dev = bc.get("st_dev")
    expected_ino = bc.get("st_ino")
    if not isinstance(expected_realpath, str) or not isinstance(expected_dev, int) \
            or not isinstance(expected_ino, int):
        return Rejected(
            reason="bound_cwd_invalid",
            message="bound_cwd must carry realpath:str + st_dev:int + st_ino:int",
            field_name="bound_cwd",
        )
    try:
        actual_realpath = os.path.realpath(str(cwd))
        st = os.stat(actual_realpath)
    except OSError as exc:
        return Rejected(
            reason="bound_cwd_compute_failed",
            message=f"could not stat current cwd: {exc}",
            field_name="bound_cwd",
        )
    actual_dev = int(st.st_dev)
    actual_ino = int(st.st_ino)
    realpath_matches = expected_realpath == actual_realpath
    inode_matches = expected_dev == actual_dev and expected_ino == actual_ino
    if realpath_matches and inode_matches:
        return None
    if realpath_matches and not inode_matches:
        return Rejected(
            reason="bound_cwd_inode_mismatch",
            message=(
                "bound_cwd inode (st_dev/st_ino) mismatch under matching "
                "realpath — symlink-swap or volume-remount attack signal"
            ),
            field_name="bound_cwd",
        )
    if not realpath_matches and inode_matches:
        return Rejected(
            reason="bound_cwd_realpath_changed_inode_match",
            message=(
                "directory was renamed or moved (realpath differs but inode "
                "matches); re-run /lp-pick-stack to re-bind"
            ),
            field_name="bound_cwd",
        )
    return Rejected(
        reason="bound_cwd_realpath_mismatch",
        message="bound_cwd realpath AND inode do not match current cwd",
        field_name="bound_cwd",
    )


def validate_decision(
    decision: Mapping[str, Any],
    cwd: Path,
    *,
    scaffolders: Mapping[str, Mapping[str, Any]],
    category_ids: set[str],
    nonce_seen: bool = False,
    rationale_path_for_sha: Path | None = None,
    expected_versions: frozenset[str] = EXPECTED_DECISION_VERSION,
) -> Accepted | Rejected:
    """Run all 12 active §4 rules (rule 12 BL-235 deferred).

    `nonce_seen` lets the caller pre-resolve the nonce-ledger lookup and pass
    in the result; we keep the file I/O out of this module so it stays
    pure-CPU + filesystem-validator (the path validator already touches FS).

    `rationale_path_for_sha`: when provided, we re-hash the file at this path
    and assert it equals decision[rationale_sha256]. When None, the caller
    has already verified (test fixtures may skip when rationale.md is absent).

    Returns Accepted on success, Rejected on first failure.
    """
    if not isinstance(decision, dict):
        return Rejected(
            reason="scaffold_decision_invalid_shape",
            message=f"decision must be a dict, got {type(decision).__name__}",
        )
    for fld in _REQUIRED_FIELDS:
        if fld not in decision:
            return Rejected(
                reason="scaffold_decision_missing_field",
                message=f"missing required field {fld!r}",
                field_name=fld,
            )

    # --- Rule 1: version ---
    version = decision["version"]
    if not isinstance(version, str) or version not in expected_versions:
        return Rejected(
            reason="version_unsupported",
            message=(
                f"decision file generated by older or newer plugin version; "
                f"delete .launchpad/scaffold-decision.json and re-run "
                f"/lp-pick-stack to regenerate. seen={version!r}, "
                f"expected one of {sorted(expected_versions)!r}"
            ),
            field_name="version",
            seen_version=version if isinstance(version, str) else None,
        )

    # --- Rule 8 (early): generated_by ---
    if decision["generated_by"] != "/lp-pick-stack":
        return Rejected(
            reason="generated_by_invalid",
            message=f"generated_by must be '/lp-pick-stack', got {decision['generated_by']!r}",
            field_name="generated_by",
        )

    # --- Rule 9: generated_at ISO 8601 + ≤4h old ---
    generated_at = _parse_iso_utc_sec(decision["generated_at"])
    if generated_at is None:
        return Rejected(
            reason="generated_at_invalid_format",
            message=f"generated_at must be ISO 8601 UTC sec-precision Z-suffix, got {decision['generated_at']!r}",
            field_name="generated_at",
        )
    age = datetime.now(timezone.utc) - generated_at
    if age > GENERATED_AT_MAX_AGE:
        return Rejected(
            reason="generated_at_expired",
            message=(
                f"generated_at is {age} old (>4h replay window); "
                "re-run /lp-pick-stack to regenerate"
            ),
            field_name="generated_at",
        )

    # --- Rule 10 (partial — replay): nonce shape + replay ---
    nonce = decision["nonce"]
    if not isinstance(nonce, str) or not _UUID4_HEX_RE.fullmatch(nonce):
        return Rejected(
            reason="nonce_format_invalid",
            message=f"nonce must be 32 hex chars, got {nonce!r}",
            field_name="nonce",
        )
    if nonce_seen:
        return Rejected(
            reason="nonce_seen",
            message=(
                "this decision file's nonce has already been consumed; "
                "re-run /lp-pick-stack to regenerate"
            ),
            field_name="nonce",
        )

    # --- Rule 11: bound_cwd triple ---
    bc_rej = _validate_bound_cwd(decision["bound_cwd"], cwd)
    if bc_rej is not None:
        return bc_rej

    # --- Rule 3: monorepo flag consistency with layers length ---
    monorepo = decision["monorepo"]
    layers_raw = decision["layers"]
    if not isinstance(monorepo, bool):
        return Rejected(
            reason="monorepo_invalid",
            message=f"monorepo must be bool, got {type(monorepo).__name__}",
            field_name="monorepo",
        )
    if not isinstance(layers_raw, list) or not layers_raw:
        return Rejected(
            reason="layers_empty",
            message="layers must be a non-empty array",
            field_name="layers",
        )
    layers = [dict(layer) if isinstance(layer, dict) else layer for layer in layers_raw]
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            return Rejected(
                reason="layer_invalid_shape",
                message=f"layers[{i}] must be a dict",
                field_name=f"layers[{i}]",
            )
    if monorepo and len(layers) < 2:
        return Rejected(
            reason="monorepo_inconsistent_layers",
            message="monorepo=true requires layers.length >= 2",
            field_name="monorepo",
        )
    if not monorepo and len(layers) != 1:
        # Allow N>1 layers iff all share path == "."
        if not all(layer.get("path") == "." for layer in layers):
            return Rejected(
                reason="monorepo_inconsistent_layers",
                message=(
                    "monorepo=false requires layers.length == 1 OR all "
                    "layers share path == '.'"
                ),
                field_name="monorepo",
            )

    # --- Rule 2 (path/role/options/stack-id) ---
    path_rej = _validate_layer_paths(layers, cwd)
    if path_rej is not None:
        return path_rej
    options_rej = _validate_layer_options(layers, dict(scaffolders))
    if options_rej is not None:
        return options_rej

    # --- Rule 4: matched_category_id ---
    matched = decision["matched_category_id"]
    if matched != MANUAL_OVERRIDE_ID and matched not in category_ids:
        return Rejected(
            reason="matched_category_id_unknown",
            message=(
                f"matched_category_id={matched!r} not in category-patterns.yml "
                f"and not the manual-override sentinel"
            ),
            field_name="matched_category_id",
        )

    # --- Rule 5: rationale_path ---
    if decision["rationale_path"] != ".launchpad/rationale.md":
        return Rejected(
            reason="rationale_path_invalid",
            message=(
                f"rationale_path must equal '.launchpad/rationale.md' exactly, "
                f"got {decision['rationale_path']!r}"
            ),
            field_name="rationale_path",
        )

    # --- Rule 6: rationale_sha256 ---
    declared_sha = decision["rationale_sha256"]
    if not isinstance(declared_sha, str) or len(declared_sha) != 64:
        return Rejected(
            reason="rationale_sha256_invalid",
            message="rationale_sha256 must be a 64-char hex string",
            field_name="rationale_sha256",
        )
    if rationale_path_for_sha is not None:
        try:
            import hashlib
            actual = hashlib.sha256(rationale_path_for_sha.read_bytes()).hexdigest()
        except OSError as exc:
            return Rejected(
                reason="rationale_read_failed",
                message=f"could not read rationale at {rationale_path_for_sha}: {exc}",
                field_name="rationale_path",
            )
        if actual != declared_sha:
            return Rejected(
                reason="rationale_sha256_mismatch",
                message=(
                    f"rationale_sha256 mismatch: declared {declared_sha!r}, "
                    f"actual {actual!r}"
                ),
                field_name="rationale_sha256",
            )

    # --- Rule 7: rationale_summary ---
    rs_rej = _validate_rationale_summary(decision["rationale_summary"])
    if rs_rej is not None:
        return rs_rej

    # --- Rule 12: SKIP per BL-235 strip-back ---

    # --- Rule 13: sha256 over canonical_hash(payload-sans-sha256) ---
    declared_envelope_sha = decision["sha256"]
    if not isinstance(declared_envelope_sha, str) or len(declared_envelope_sha) != 64:
        return Rejected(
            reason="sha256_invalid",
            message="sha256 must be a 64-char hex string",
            field_name="sha256",
        )
    payload_for_hash = {k: v for k, v in decision.items() if k != "sha256"}
    actual_envelope_sha = canonical_hash(payload_for_hash)
    if actual_envelope_sha != declared_envelope_sha:
        return Rejected(
            reason="sha256_mismatch",
            message=(
                f"sha256 envelope mismatch: declared {declared_envelope_sha!r}, "
                f"actual {actual_envelope_sha!r}"
            ),
            field_name="sha256",
        )

    return Accepted(
        payload=dict(decision),
        nonce=nonce,
        bound_cwd=dict(decision["bound_cwd"]),
    )


__all__ = [
    "ALLOWED_ROLES",
    "Accepted",
    "GENERATED_AT_MAX_AGE",
    "MANUAL_OVERRIDE_ID",
    "Rejected",
    "validate_decision",
]
