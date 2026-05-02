"""Path validator for paths crossing trust boundaries (HANDSHAKE §6).

Single source of truth: imported by /lp-pick-stack (write-side), /lp-scaffold-stack
(read-side), /lp-define (output adapter paths).

Internally split into a string-shape check (`_validate_path_shape`) and a
filesystem-realpath check (`_validate_filesystem_safety`); the public
`validate_relative_path()` orchestrates both. The split lets unit tests cover
string-shape rules without touching the filesystem.
"""
from __future__ import annotations

import re
from pathlib import Path

ALLOWLIST_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")
FORBIDDEN_PREFIXES = (".git/", ".launchpad/.", "node_modules/", ".env")


class PathValidationError(ValueError):
    """Raised when a path crossing a trust boundary fails validation.

    Mirrors the ConfigError pattern in plugin-config-loader.py: domain-specific
    exception subclass + field_name attribute for telemetry.
    """

    def __init__(self, message: str, field_name: str = "path"):
        super().__init__(f"{field_name}: {message}")
        self.field_name = field_name


def _validate_path_shape(raw: str, field_name: str) -> None:
    """String-only validation: type, emptiness, allowlist, traversal, reserved prefixes.

    No filesystem access. Pure-CPU; cheap to fuzz.
    """
    if not isinstance(raw, str):
        raise PathValidationError(f"expected str, got {type(raw).__name__}", field_name)
    if not raw:
        raise PathValidationError("empty path", field_name)
    if "\x00" in raw:
        raise PathValidationError("null byte in path", field_name)
    if not ALLOWLIST_RE.fullmatch(raw):
        raise PathValidationError(f"disallowed characters: {raw!r}", field_name)
    if raw.startswith("/"):
        raise PathValidationError("absolute path forbidden", field_name)
    if any(p == ".." for p in raw.split("/")):
        raise PathValidationError("parent traversal forbidden", field_name)
    for prefix in FORBIDDEN_PREFIXES:
        if raw == prefix.rstrip("/") or raw.startswith(prefix):
            raise PathValidationError(f"reserved area: {prefix}", field_name)


def _validate_filesystem_safety(raw: str, cwd: Path, field_name: str) -> Path:
    """Filesystem-bound validation: realpath cwd-containment + ancestor symlink check.

    Caller must have already passed _validate_path_shape on raw.
    """
    cwd_real = cwd.resolve(strict=True)
    candidate = (cwd_real / raw).resolve(strict=False)
    if not candidate.is_relative_to(cwd_real):
        raise PathValidationError("resolved path escapes cwd", field_name)
    cur = candidate
    while cur != cwd_real:
        if cur.is_symlink():
            raise PathValidationError(f"ancestor is symlink: {cur}", field_name)
        if cur.parent == cur:
            break
        cur = cur.parent
    return candidate


def validate_relative_path(
    raw: str,
    cwd: Path,
    field_name: str = "path",
) -> Path:
    """Validate a relative POSIX path supplied across a trust boundary.

    Orchestrates shape + filesystem checks. Raises PathValidationError on any
    rule violation; returns the resolved absolute Path on success.
    """
    _validate_path_shape(raw, field_name)
    return _validate_filesystem_safety(raw, cwd, field_name)


__all__ = [
    "ALLOWLIST_RE",
    "FORBIDDEN_PREFIXES",
    "PathValidationError",
    "validate_relative_path",
]
