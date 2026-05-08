"""v2.1 Codex PR #50 cycle 6 T0-5: backup relpath traversal rejection.

DA-F8.4: backup relocation MUST reject `..`, absolute paths, null bytes,
and embedded path separators in adapter-supplied relpaths. Without this,
a malicious adapter manifest could escape `.launchpad/backups/` and
write into arbitrary filesystem locations.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
    _validate_backup_relpath,
)


def test_validate_relpath_rejects_dotdot() -> None:
    with pytest.raises(CompositionAbortError) as excinfo:
        _validate_backup_relpath(Path("..") / "etc")
    assert excinfo.value.reason == (
        CompositionRejectionCode.PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
    )


def test_validate_relpath_rejects_traversal_chain() -> None:
    """Even nested `..` components anywhere along the path."""
    with pytest.raises(CompositionAbortError) as excinfo:
        _validate_backup_relpath(Path("apps") / ".." / ".." / ".." / "etc")
    assert excinfo.value.reason == (
        CompositionRejectionCode.PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
    )


def test_validate_relpath_rejects_absolute_path() -> None:
    with pytest.raises(CompositionAbortError) as excinfo:
        _validate_backup_relpath(Path("/etc/passwd"))
    assert excinfo.value.reason == (
        CompositionRejectionCode.PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
    )


def test_validate_relpath_rejects_null_byte() -> None:
    with pytest.raises(CompositionAbortError) as excinfo:
        _validate_backup_relpath(Path("apps") / "ev\x00il")
    assert excinfo.value.reason == (
        CompositionRejectionCode.PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
    )


def test_validate_relpath_accepts_clean_relpath() -> None:
    """Sanity check: legitimate relpaths pass."""
    _validate_backup_relpath(Path("apps") / "app")
    _validate_backup_relpath(Path("packages") / "auth")
    _validate_backup_relpath(Path("apps") / "app-fe")
