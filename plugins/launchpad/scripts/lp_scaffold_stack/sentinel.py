"""Scaffold-stack sentinel + lifecycle helpers (Phase 10 cycle-2 F9 + cycle-3 P2-2 lock).

The sentinel `.launchpad/.scaffold-stack-in-progress` is a JSON file
written by `/lp-scaffold-stack` around the kernel-render + scaffold-
decision re-seal window so that concurrent `/lp-bootstrap` /
`/lp-update-identity` invocations refuse cleanly rather than racing
against the atomic-replace window.

Structurally mirrors `lp_bootstrap/sentinel.py` per cycle-3 P2-2 lock.
Field set is identical to bootstrap's (no semantic renames; the
"scaffold-stack" identity is fully captured by the filename + `mode`
field).

Liveness check via `os.kill(pid, 0)` (POSIX signal-0 pattern); same
ProcessLookupError / PermissionError handling as the bootstrap precedent.

Corrupt-JSON: refuse-immediately, no retry-with-backoff (Phase 3 harden
C8 + frontend-races F5 precedent).

This module is read by `lp_bootstrap/engine.py:_sentinel_preflight` AND
by `lp_update_identity/engine.py:_validate_preconditions` for
bidirectional cross-detect; lifecycle write/clear is owned by
`lp_scaffold_stack/engine.py`.
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

SCAFFOLD_STACK_SENTINEL_NAME = ".scaffold-stack-in-progress"


class ScaffoldStackSentinelError(RuntimeError):
    """Sentinel read/write failure raised by this module."""


@dataclass(frozen=True)
class ScaffoldStackSentinelSnapshot:
    """Decoded scaffold-stack sentinel JSON payload."""

    command_pid: int
    started_at: str
    mode: str


def sentinel_path(cwd: Path) -> Path:
    """Resolve `<cwd>/.launchpad/.scaffold-stack-in-progress`."""
    return cwd / LAUNCHPAD_DIR_NAME / SCAFFOLD_STACK_SENTINEL_NAME


def _utc_iso8601_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_sentinel(
    cwd: Path,
    *,
    mode: str = "scaffold-stack",
    command_pid: int | None = None,
) -> ScaffoldStackSentinelSnapshot:
    """Atomically create the sentinel via `O_CREAT|O_EXCL|O_WRONLY` + 0o600.

    Raises FileExistsError if the sentinel already exists; engine layer
    decides whether to recover-stale or refuse-live.
    """
    pid = command_pid if command_pid is not None else os.getpid()
    payload = {
        "command_pid": pid,
        "started_at": _utc_iso8601_now(),
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

    return ScaffoldStackSentinelSnapshot(
        command_pid=pid,
        started_at=payload["started_at"],
        mode=mode,
    )


def read_sentinel(cwd: Path) -> ScaffoldStackSentinelSnapshot | None:
    """Decode the sentinel JSON if present.

    Returns None if absent. Raises `ScaffoldStackSentinelError` for any
    malformed JSON or missing required field.
    """
    target = sentinel_path(cwd)
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScaffoldStackSentinelError(
            f"sentinel {target} read failed: {exc}"
        ) from exc
    try:
        payload: Any = json.loads(text)
    except ValueError as exc:
        raise ScaffoldStackSentinelError(
            f"sentinel {target} JSON parse error: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ScaffoldStackSentinelError(
            f"sentinel {target} top-level is not a mapping"
        )

    required = ("command_pid", "started_at", "mode")
    for key in required:
        if key not in payload:
            raise ScaffoldStackSentinelError(
                f"sentinel {target} missing required field {key!r}"
            )
    pid = payload["command_pid"]
    if not isinstance(pid, int):
        raise ScaffoldStackSentinelError(f"sentinel {target}: command_pid must be int")
    mode_str = payload["mode"]
    if not isinstance(mode_str, str):
        raise ScaffoldStackSentinelError(f"sentinel {target}: mode must be a string")
    return ScaffoldStackSentinelSnapshot(
        command_pid=pid,
        started_at=str(payload["started_at"]),
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
    """Liveness check via `os.kill(pid, 0)` (POSIX signal-0 pattern)."""
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
    "SCAFFOLD_STACK_SENTINEL_NAME",
    "ScaffoldStackSentinelError",
    "ScaffoldStackSentinelSnapshot",
    "clear_sentinel",
    "is_pid_alive",
    "read_sentinel",
    "sentinel_path",
    "write_sentinel",
]
