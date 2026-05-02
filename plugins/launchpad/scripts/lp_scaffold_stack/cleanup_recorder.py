"""scaffold-failed-<ts>.json writer (OPERATIONS §6 gate #11 schema).

Per HANDSHAKE §1.5 + BL-231 strip-back: v2.0 EMITS the structured
`recovery_commands` array as a forward-compat hint; v2.0 readers (humans)
consume `recommended_recovery_action` prose + `see_recovery_doc` URL.

What ships at v2.0:

- Structured array shape (op + path / op + command).
- Write-time destructive-path denylist: refuses to WRITE entries with
  `path` ∈ `{".", "./", "..", "/", "~", ".launchpad", ".git", ".github"}`.
- Field discipline regex `^[A-Za-z0-9_./\\-]+$` for materialized_files +
  recovery_commands.path strings.
- Distinct closed `reason:` enum from §4 scaffold-rejection (Layer 9 closes
  adversarial P2 conflation): `{layer_materialization_failed,
  auth_precondition_unmet, network_precondition_unmet,
  cross_cutting_wiring_collision, secret_scan_failed,
  recovery_precondition_unmet}`.

What v2.0 does NOT do (BL-231):

- Closed `op` enum runtime enforcement on read.
- Idempotency contract per `op`.
- `sha256` self-hash on the JSON file.
- `.recovery.lock` consumer concurrency lock.
- At-most-one-rerun rule.
- Closed `command` set for `rerun` op.
- Execute-time path re-validation.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

# Closed reason enum — distinct from §4 scaffold-rejection. v2.0 readers
# (humans + future BL-231 tooling) MUST hard-reject unknown values.
CLEANUP_REASONS = frozenset({
    "layer_materialization_failed",
    "auth_precondition_unmet",
    "network_precondition_unmet",
    "cross_cutting_wiring_collision",
    "secret_scan_failed",
    "recovery_precondition_unmet",
})

# Write-time destructive-path denylist (per HANDSHAKE/OPERATIONS §6 gate #11).
DESTRUCTIVE_PATHS = frozenset({
    ".", "./", "..", "/", "~", ".launchpad", ".git", ".github",
})

# Field-discipline regex per Layer 3 security-lens P1-S4 + Layer 5 spec-flow
# P1-LF1/LF6/LF8.
_PATH_FIELD_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")

# v2.0 recovery_commands op set per Layer 5 spec-flow P1-LF1 + Layer 8
# closure. Write-time validation only at v2.0 (BL-231 read-side enforcement
# defers to v2.2).
RECOVERY_OPS = frozenset({"rmdir_recursive", "rm", "rerun"})
RERUN_COMMANDS = frozenset({"/lp-pick-stack", "/lp-brainstorm", "/lp-scaffold-stack", "/lp-define"})

# Materialized files truncated to first 50 paths per OPERATIONS §5
# 4096-byte payload cap.
MAX_MATERIALIZED_FILES = 50

# v2.0 schema_version + version fields.
SCHEMA_VERSION = "1.0"
WRITTEN_FAILED_VERSION = "1.0"


class CleanupRecordError(RuntimeError):
    """Raised on scaffold-failed write failures or write-time validation
    rejections. Carries `reason:` field."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


def _harness_obs_dir(repo_root: Path) -> Path:
    return repo_root / ".harness" / "observations"


def _launchpad_dir(repo_root: Path) -> Path:
    return repo_root / ".launchpad"


def _utc_now_iso_sec() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now_iso_ts_filename() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _validate_path_field(p: str, *, context: str) -> None:
    if not isinstance(p, str) or not _PATH_FIELD_RE.fullmatch(p):
        raise CleanupRecordError(
            f"{context}={p!r} fails field-discipline regex",
            reason="cleanup_field_discipline_failed",
        )


def _validate_recovery_commands(recovery_commands: Sequence[Mapping[str, Any]]) -> None:
    """Write-time enforcement of the structured array shape.

    Per BL-231: v2.0 enforces denylist + field regex AT WRITE TIME so we
    don't WRITE poisonous entries; runtime read-side enforcement is deferred.
    """
    if not isinstance(recovery_commands, Sequence) or len(recovery_commands) < 1:
        raise CleanupRecordError(
            "recovery_commands must be a non-empty array (minimum: single rerun op)",
            reason="cleanup_recovery_commands_empty",
        )
    for i, entry in enumerate(recovery_commands):
        if not isinstance(entry, dict):
            raise CleanupRecordError(
                f"recovery_commands[{i}] must be a dict",
                reason="cleanup_field_discipline_failed",
            )
        op = entry.get("op")
        if op not in RECOVERY_OPS:
            raise CleanupRecordError(
                f"recovery_commands[{i}].op={op!r} not in {sorted(RECOVERY_OPS)!r}",
                reason="cleanup_recovery_op_invalid",
            )
        if op in {"rmdir_recursive", "rm"}:
            path = entry.get("path")
            _validate_path_field(path, context=f"recovery_commands[{i}].path")
            if path in DESTRUCTIVE_PATHS:
                raise CleanupRecordError(
                    f"recovery_commands[{i}].path={path!r} is in destructive-path denylist",
                    reason="cleanup_destructive_path",
                )
        elif op == "rerun":
            command = entry.get("command")
            if command not in RERUN_COMMANDS:
                raise CleanupRecordError(
                    f"recovery_commands[{i}].command={command!r} not in {sorted(RERUN_COMMANDS)!r}",
                    reason="cleanup_recovery_rerun_command_invalid",
                )


def _validate_materialized_files(materialized_files: Sequence[str]) -> list[str]:
    if not isinstance(materialized_files, Sequence):
        raise CleanupRecordError(
            "materialized_files must be a sequence",
            reason="cleanup_field_discipline_failed",
        )
    out: list[str] = []
    for i, p in enumerate(materialized_files):
        _validate_path_field(p, context=f"materialized_files[{i}]")
        out.append(p)
        if len(out) >= MAX_MATERIALIZED_FILES:
            break
    return out


def build_failed_payload(
    *,
    reason: str,
    failed_layer_index: int | None,
    materialized_files: Sequence[str],
    recovery_commands: Sequence[Mapping[str, Any]],
    recommended_recovery_action: str,
    see_recovery_doc: str = "docs/troubleshooting.md#scaffold-partial-failure",
    failed_at: str | None = None,
) -> dict:
    """Build the scaffold-failed-<ts>.json payload.

    Validates against the closed reason enum + field discipline + destructive-
    path denylist. Raises CleanupRecordError on any write-time rejection.

    `failed_layer_index: None` allowed for `cross_cutting_wiring_collision`
    + `secret_scan_failed` per Layer 5 spec-flow P3-LF8.
    """
    if reason not in CLEANUP_REASONS:
        raise CleanupRecordError(
            f"reason={reason!r} not in {sorted(CLEANUP_REASONS)!r}",
            reason="cleanup_reason_invalid",
        )
    if failed_layer_index is None and reason not in {
        "cross_cutting_wiring_collision", "secret_scan_failed",
        "recovery_precondition_unmet", "auth_precondition_unmet",
        "network_precondition_unmet",
    }:
        raise CleanupRecordError(
            f"failed_layer_index=None requires reason in cross-cutting/secret-scan/precondition set; got {reason!r}",
            reason="cleanup_reason_invalid",
        )
    if not isinstance(recommended_recovery_action, str) or not recommended_recovery_action.strip():
        raise CleanupRecordError(
            "recommended_recovery_action must be a non-empty string",
            reason="cleanup_field_discipline_failed",
        )
    truncated_files = _validate_materialized_files(materialized_files)
    _validate_recovery_commands(recovery_commands)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": WRITTEN_FAILED_VERSION,
        "failed_at": failed_at or _utc_now_iso_sec(),
        "reason": reason,
        "failed_layer_index": failed_layer_index,
        "materialized_files": truncated_files,
        "recovery_commands": [dict(c) for c in recovery_commands],
        "recommended_recovery_action": recommended_recovery_action,
        "see_recovery_doc": see_recovery_doc,
    }
    return payload


def write_failed_atomic(
    payload: Mapping[str, Any],
    repo_root: Path,
) -> Path:
    """Atomic O_CREAT|O_EXCL write of `<repo_root>/.launchpad/scaffold-failed-<ts>.json`.

    Per OPERATIONS §6 gate #11: timestamped filename is collision-free under
    the v2.0 single-process invocation model; no retry ladder needed.
    fsync(fd) + fsync(dirfd) + F_FULLFSYNC on darwin.
    """
    line = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    encoded = line.encode("utf-8")

    launchpad = _launchpad_dir(repo_root)
    launchpad.mkdir(parents=True, exist_ok=True)
    target = launchpad / f"scaffold-failed-{_utc_now_iso_ts_filename()}.json"
    if target.exists():
        # Same-second collision: append .pid suffix.
        target = launchpad / f"scaffold-failed-{_utc_now_iso_ts_filename()}.{os.getpid()}.json"

    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        os.write(fd, encoded)
        os.fsync(fd)
        if sys.platform == "darwin":
            try:
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            except (OSError, AttributeError):
                pass
    finally:
        os.close(fd)

    try:
        dirfd = os.open(str(launchpad), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except OSError:
        pass

    return target


def write_scaffold_failed(
    *,
    reason: str,
    failed_layer_index: int | None,
    materialized_files: Sequence[str],
    recovery_commands: Sequence[Mapping[str, Any]],
    recommended_recovery_action: str,
    repo_root: Path,
    see_recovery_doc: str = "docs/troubleshooting.md#scaffold-partial-failure",
) -> tuple[Path, dict]:
    """Build + atomic write of scaffold-failed-<ts>.json. Returns (path, payload)."""
    payload = build_failed_payload(
        reason=reason,
        failed_layer_index=failed_layer_index,
        materialized_files=materialized_files,
        recovery_commands=recovery_commands,
        recommended_recovery_action=recommended_recovery_action,
        see_recovery_doc=see_recovery_doc,
    )
    target = write_failed_atomic(payload, repo_root)
    return target, payload


__all__ = [
    "CLEANUP_REASONS",
    "CleanupRecordError",
    "DESTRUCTIVE_PATHS",
    "MAX_MATERIALIZED_FILES",
    "RECOVERY_OPS",
    "RERUN_COMMANDS",
    "SCHEMA_VERSION",
    "WRITTEN_FAILED_VERSION",
    "build_failed_payload",
    "write_failed_atomic",
    "write_scaffold_failed",
]
