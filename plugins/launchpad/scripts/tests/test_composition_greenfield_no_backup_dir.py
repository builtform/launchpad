"""v2.1 Codex PR #50 cycle 6 T1-6: greenfield path produces no backup dir.

When composition runs against an EMPTY target (no pre-existing user
content), `_backup_existing_target` returns None — no backup is staged,
and `_relocate_backups_to_launchpad` is a no-op. Asserts the greenfield
path does not pollute `.launchpad/backups/` with empty entries.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import (
    _backup_existing_target,
    _relocate_backups_to_launchpad,
)


def test_no_backup_when_target_absent(tmp_path: Path) -> None:
    """`_backup_existing_target` returns None for absent targets."""
    composition_root = tmp_path / "project"
    composition_root.mkdir()
    target = composition_root / "apps" / "app"
    backup = _backup_existing_target(target, composition_root)
    assert backup is None


def test_relocate_with_empty_list_creates_no_backup_dir(tmp_path: Path) -> None:
    """Greenfield: empty `backups` list -> no `.launchpad/backups/<...>/` entry."""
    composition_root = tmp_path / "project"
    composition_root.mkdir()
    final = _relocate_backups_to_launchpad([], composition_root)
    assert final is None
    backups_root = composition_root / ".launchpad" / "backups"
    # Either the parent doesn't exist or it's empty.
    if backups_root.exists():
        assert list(backups_root.iterdir()) == []
