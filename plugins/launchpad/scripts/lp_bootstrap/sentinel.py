"""Bootstrap sentinel + lifecycle helpers (v2.1 Phase 3 sections 3.5 + 3.6).

The sentinel `.launchpad/.bootstrap-in-progress` is a JSON file written
before the render loop and removed on successful completion. It carries:

  * `command_pid` (int)            -- for `os.kill(pid, 0)` liveness check.
  * `started_at` (str, UTC ISO-8601)
  * `pre_edit_manifest_sha256` (str | null) -- prior manifest sha so
                                                `--recover` can decide
                                                rollback semantics.
  * `target_paths` (list[str])     -- partial-rollback substrate.
  * `mode` (str)                   -- `"greenfield"` | `"brownfield-auto"`
                                       | `"refresh"` | `"refresh-all"`
                                       | `"recover"`.

Per harden C8 the sentinel does NOT carry `sentinel_schema_version`. It is
ephemeral (max lifetime: until the next bootstrap finishes); forward-compat
versioning is over-engineering. If v2.2 changes the shape, `--recover` reads
existing format, treats unknown fields as ignorable, treats missing required
fields as a `manifest_corrupt`-class abort.

Sentinel mode is 0o600 per harden B6 so `command_pid` (a process snapshot)
is not world-readable on shared dev hosts.

Liveness check uses `os.kill(pid, 0)`: signal 0 sends nothing but returns
success when the PID exists in the process table OR raises
`ProcessLookupError` when the PID is dead. Engine catches the exception and
treats it as dead-PID auto-recover.
"""
from __future__ import annotations

import errno
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import _full_fsync_darwin, _fsync_parent  # noqa: E402

from lp_bootstrap import (  # noqa: E402
    LAUNCHPAD_DIR_NAME,
    SENTINEL_NAME,
    BootstrapErrorCode,
)


class BootstrapSentinelError(RuntimeError):
    """Sentinel read/write/inspect failure raised by this module."""

    def __init__(
        self,
        message: str,
        *,
        reason: BootstrapErrorCode,
        path: Path | None = None,
        remediation: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.remediation = remediation


@dataclass(frozen=True)
class SentinelSnapshot:
    """Decoded sentinel JSON payload (section 3.6)."""
    command_pid: int
    started_at: str
    pre_edit_manifest_sha256: str | None
    target_paths: tuple[str, ...]
    mode: str


def sentinel_path(cwd: Path) -> Path:
    """Resolve `<cwd>/.launchpad/.bootstrap-in-progress`."""
    return cwd / LAUNCHPAD_DIR_NAME / SENTINEL_NAME


def _utc_iso8601_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_sentinel(
    cwd: Path,
    *,
    mode: str,
    pre_edit_manifest_sha256: str | None,
    target_paths: list[str],
    command_pid: int | None = None,
) -> SentinelSnapshot:
    """Atomically create the sentinel via `O_CREAT|O_EXCL|O_WRONLY` + 0o600.

    `target_paths` is the planned render target list; `--recover` reads it
    to know which files might be partial. Mode is 0o600 per harden B6.

    Phase 11 hardening A4: harmonized to `O_CREAT|O_EXCL` to mirror
    `lp_scaffold_stack/sentinel.write_sentinel` and
    `lp_update_identity/sentinel.write_sentinel`. Previously this used
    `atomic_write_replace` (rename-over), which would silently overwrite
    a peer's sentinel if the cross-detect-then-write window was raced.
    `_sentinel_preflight` now passes a freshly-cleared filesystem (or
    a recovered stale-PID sentinel that was deleted) and any concurrent
    peer who beats us to `os.open(O_EXCL)` makes us raise FileExistsError
    cleanly. The bootstrap engine holds `.bootstrap.lock` across
    preflight + this write, so within bootstrap the race is impossible;
    the O_EXCL is defense-in-depth against unflocked peers.
    """
    pid = command_pid if command_pid is not None else os.getpid()
    payload = {
        "command_pid": pid,
        "started_at": _utc_iso8601_now(),
        "pre_edit_manifest_sha256": pre_edit_manifest_sha256,
        "target_paths": list(target_paths),
        "mode": mode,
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

    return SentinelSnapshot(
        command_pid=pid,
        started_at=payload["started_at"],
        pre_edit_manifest_sha256=pre_edit_manifest_sha256,
        target_paths=tuple(target_paths),
        mode=mode,
    )


def read_sentinel(cwd: Path) -> SentinelSnapshot | None:
    """Decode the sentinel JSON if present.

    Returns None if the sentinel file does not exist. Raises
    `BootstrapSentinelError(MANIFEST_CORRUPT)` for any malformed JSON or
    missing required fields per the harden C8 contract: corrupt sentinel
    is treated like a corrupt manifest.
    """
    target = sentinel_path(cwd)
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise BootstrapSentinelError(
            f"sentinel {target} read failed: {exc}",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=(
                f"inspect {target} permissions; if a prior run died, remove "
                f"the sentinel manually after confirming no PID is alive"
            ),
        ) from exc
    try:
        payload: Any = json.loads(text)
    except ValueError as exc:
        raise BootstrapSentinelError(
            f"sentinel {target} JSON parse error: {exc}",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=(
                f"sentinel is corrupt; run /lp-bootstrap --recover OR remove "
                f"{target} manually after confirming no /lp-bootstrap is "
                f"running"
            ),
        ) from exc
    if not isinstance(payload, dict):
        raise BootstrapSentinelError(
            f"sentinel {target} top-level is not a mapping",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=f"remove {target} after confirming no /lp-bootstrap is running",
        )

    required = ("command_pid", "started_at", "target_paths", "mode")
    for key in required:
        if key not in payload:
            raise BootstrapSentinelError(
                f"sentinel {target} missing required field {key!r}",
                reason=BootstrapErrorCode.MANIFEST_CORRUPT,
                path=target,
                remediation=f"remove {target} after confirming no /lp-bootstrap is running",
            )
    pid = payload["command_pid"]
    if not isinstance(pid, int):
        raise BootstrapSentinelError(
            f"sentinel {target}: command_pid must be int, got {type(pid).__name__}",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=f"remove {target} after confirming no /lp-bootstrap is running",
        )
    target_paths = payload.get("target_paths") or []
    if not isinstance(target_paths, list):
        raise BootstrapSentinelError(
            f"sentinel {target}: target_paths must be a list",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=f"remove {target} after confirming no /lp-bootstrap is running",
        )
    pre_edit = payload.get("pre_edit_manifest_sha256")
    if pre_edit is not None and not isinstance(pre_edit, str):
        raise BootstrapSentinelError(
            f"sentinel {target}: pre_edit_manifest_sha256 must be str or null",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=f"remove {target} after confirming no /lp-bootstrap is running",
        )
    mode_str = payload["mode"]
    if not isinstance(mode_str, str):
        raise BootstrapSentinelError(
            f"sentinel {target}: mode must be a string",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            path=target,
            remediation=f"remove {target} after confirming no /lp-bootstrap is running",
        )
    return SentinelSnapshot(
        command_pid=pid,
        started_at=str(payload["started_at"]),
        pre_edit_manifest_sha256=pre_edit,
        target_paths=tuple(str(p) for p in target_paths),
        mode=mode_str,
    )


def clear_sentinel(cwd: Path) -> None:
    """Remove the sentinel file; idempotent if already absent."""
    target = sentinel_path(cwd)
    try:
        target.unlink()
    except FileNotFoundError:
        return


def is_pid_alive(pid: int) -> bool:
    """Liveness check using `os.kill(pid, 0)`.

    Signal 0 is the standard POSIX no-op-but-validate-existence-and-permission
    pattern. `ProcessLookupError` (ESRCH) means dead PID; `PermissionError`
    (EPERM) means the PID exists and is owned by another uid (treat as alive
    -- we cannot signal it, but it is real). Other OSErrors are propagated
    so a misbehaving system surfaces.
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
    "BootstrapSentinelError",
    "SentinelSnapshot",
    "clear_sentinel",
    "is_pid_alive",
    "read_sentinel",
    "sentinel_path",
    "write_sentinel",
]
