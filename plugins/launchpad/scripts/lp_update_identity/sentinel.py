"""Identity-update sentinel + lifecycle helpers (Phase 10 plan §3.3 -- DA3).

The sentinel `.launchpad/.identity-update-in-progress` is a JSON file
written before any scaffold-decision mutation and removed on successful
completion. It STRUCTURALLY mirrors `lp_bootstrap/sentinel.py` with
renames called out for semantic clarity:

  * `command_pid` (int)                 -- for `os.kill(pid, 0)` liveness
  * `started_at` (str, UTC ISO-8601)
  * `pre_edit_decision_sha256` (str | null) -- prior scaffold-decision
                                                sha for rollback
                                                (renamed from bootstrap's
                                                `pre_edit_manifest_sha256`)
  * `target_paths` (list[str])          -- the 7 kernel paths in render
                                            order (reuses bootstrap's
                                            field name)
  * `mode` (str = "update-identity")    -- documented value, NOT typed
                                            Literal (mirrors bootstrap)
  * `backup_path` (str)                 -- full path to backup directory
                                            per adversarial #9

Per DA3 + Phase 3 harden C8: NO `sentinel_schema_version` field
(ephemeral; max lifetime until next /lp-update-identity finishes).

Mode bits 0o600 set at `os.open()` time via `O_CREAT|O_EXCL|O_WRONLY`
primitive (frontend-races F2 -- prevents concurrent-create race;
FileExistsError → refuse with `IDENTITY_UPDATE_IN_PROGRESS`).

Liveness via `os.kill(pid, 0)`: `ProcessLookupError` → dead;
`PermissionError` → alive (mirrors bootstrap precedent at
`lp_bootstrap/sentinel.py:227-250`).

Corrupt-JSON policy: refuse-immediately, no retry-with-backoff (matches
Phase 3 precedent per frontend-races F5).
"""
from __future__ import annotations

import errno
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import _fsync_parent, _full_fsync_darwin  # noqa: E402
from lp_bootstrap import LAUNCHPAD_DIR_NAME  # noqa: E402

from lp_update_identity import (  # noqa: E402
    IDENTITY_UPDATE_SENTINEL_NAME,
    IdentityUpdateErrorCode,
    IdentityUpdateSentinelError,
)


@dataclass(frozen=True)
class IdentitySentinelSnapshot:
    """Decoded identity-update sentinel JSON payload (Phase 10 §3.3)."""
    command_pid: int
    started_at: str
    pre_edit_decision_sha256: str | None
    target_paths: tuple[str, ...]
    mode: str
    backup_path: str


def sentinel_path(cwd: Path) -> Path:
    """Resolve `<cwd>/.launchpad/.identity-update-in-progress`."""
    return cwd / LAUNCHPAD_DIR_NAME / IDENTITY_UPDATE_SENTINEL_NAME


def _utc_iso8601_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_sentinel(
    cwd: Path,
    *,
    pre_edit_decision_sha256: str | None,
    target_paths: list[str],
    backup_path: str,
    mode: str = "update-identity",
    command_pid: int | None = None,
) -> IdentitySentinelSnapshot:
    """Atomically create the sentinel via `O_CREAT|O_EXCL|O_WRONLY` + 0o600.

    Per F2: concurrent-create race refuses cleanly; the LOSER sees
    `FileExistsError`, the engine catches and translates to
    `IDENTITY_UPDATE_IN_PROGRESS` after a liveness check.

    Raises `FileExistsError` if the sentinel already exists (engine layer
    decides whether to recover-stale or refuse-live).
    """
    pid = command_pid if command_pid is not None else os.getpid()
    payload = {
        "command_pid": pid,
        "started_at": _utc_iso8601_now(),
        "pre_edit_decision_sha256": pre_edit_decision_sha256,
        "target_paths": list(target_paths),
        "mode": mode,
        "backup_path": backup_path,
    }
    target = sentinel_path(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")

    fd = os.open(
        str(target),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        os.write(fd, encoded)
        os.fsync(fd)
        _full_fsync_darwin(fd)
    finally:
        os.close(fd)
    _fsync_parent(target)

    return IdentitySentinelSnapshot(
        command_pid=pid,
        started_at=payload["started_at"],
        pre_edit_decision_sha256=pre_edit_decision_sha256,
        target_paths=tuple(target_paths),
        mode=mode,
        backup_path=backup_path,
    )


def read_sentinel(cwd: Path) -> IdentitySentinelSnapshot | None:
    """Decode the sentinel JSON if present.

    Returns None if absent. Raises `IdentityUpdateSentinelError` for any
    malformed JSON or missing required field per Phase 3 corrupt-JSON
    refuse-immediately precedent (frontend-races F5).
    """
    target = sentinel_path(cwd)
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise IdentityUpdateSentinelError(
            f"sentinel {target} read failed: {exc}",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=(
                f"inspect {target} permissions; if a prior /lp-update-identity "
                f"died, remove the sentinel manually after confirming no PID "
                f"is alive"
            ),
        ) from exc
    try:
        payload: Any = json.loads(text)
    except ValueError as exc:
        raise IdentityUpdateSentinelError(
            f"sentinel {target} JSON parse error: {exc}",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=(
                f"sentinel is corrupt; remove {target} after confirming no "
                f"/lp-update-identity is running"
            ),
        ) from exc
    if not isinstance(payload, dict):
        raise IdentityUpdateSentinelError(
            f"sentinel {target} top-level is not a mapping",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=f"remove {target} after confirming no /lp-update-identity is running",
        )

    required = ("command_pid", "started_at", "target_paths", "mode", "backup_path")
    for key in required:
        if key not in payload:
            raise IdentityUpdateSentinelError(
                f"sentinel {target} missing required field {key!r}",
                reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
                path=target,
                remediation=f"remove {target} after confirming no /lp-update-identity is running",
            )
    pid = payload["command_pid"]
    if not isinstance(pid, int):
        raise IdentityUpdateSentinelError(
            f"sentinel {target}: command_pid must be int, got {type(pid).__name__}",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=f"remove {target} after confirming no /lp-update-identity is running",
        )
    target_paths = payload.get("target_paths") or []
    if not isinstance(target_paths, list):
        raise IdentityUpdateSentinelError(
            f"sentinel {target}: target_paths must be a list",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=f"remove {target} after confirming no /lp-update-identity is running",
        )
    pre_edit = payload.get("pre_edit_decision_sha256")
    if pre_edit is not None and not isinstance(pre_edit, str):
        raise IdentityUpdateSentinelError(
            f"sentinel {target}: pre_edit_decision_sha256 must be str or null",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=f"remove {target} after confirming no /lp-update-identity is running",
        )
    mode_str = payload["mode"]
    if not isinstance(mode_str, str):
        raise IdentityUpdateSentinelError(
            f"sentinel {target}: mode must be a string",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=f"remove {target} after confirming no /lp-update-identity is running",
        )
    backup_path = payload["backup_path"]
    if not isinstance(backup_path, str):
        raise IdentityUpdateSentinelError(
            f"sentinel {target}: backup_path must be a string",
            reason=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            path=target,
            remediation=f"remove {target} after confirming no /lp-update-identity is running",
        )
    return IdentitySentinelSnapshot(
        command_pid=pid,
        started_at=str(payload["started_at"]),
        pre_edit_decision_sha256=pre_edit,
        target_paths=tuple(str(p) for p in target_paths),
        mode=mode_str,
        backup_path=backup_path,
    )


def clear_sentinel(cwd: Path) -> None:
    """Remove the sentinel file; idempotent if already absent."""
    target = sentinel_path(cwd)
    try:
        target.unlink()
    except FileNotFoundError:
        return


def is_pid_alive(pid: int) -> bool:
    """Liveness check via `os.kill(pid, 0)`.

    Mirrors `lp_bootstrap.sentinel.is_pid_alive` exactly (POSIX signal-0
    pattern). `ProcessLookupError` (ESRCH) → dead; `PermissionError`
    (EPERM) → alive (owned by another uid; treat as alive).
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        if exc.errno == errno.EPERM:
            return True
        raise


__all__ = [
    "IdentitySentinelSnapshot",
    "clear_sentinel",
    "is_pid_alive",
    "read_sentinel",
    "sentinel_path",
    "write_sentinel",
]
