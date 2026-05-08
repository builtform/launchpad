"""v2.1 Codex PR #50 cycle 6 T0-4: Phase A multi-target relocation atomicity.

Verifies that a synthetic mid-loop failure during Phase A backup-relocation
rolls back ALL already-staged items to their workspace
`.pre-composition-<sha8>/` slots — never split-brain (some in
`.launchpad/backups/`, some in workspace).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import (
    _backup_existing_target,
    _relocate_backups_to_launchpad,
)


def test_phase_a_partial_failure_rolls_back_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject `os.replace` failure on the SECOND staged target. Assert:

      1. NO .launchpad/backups/<ts>-<PID>-<rand4>/ entry survives
      2. ALL backups returned to workspace as .pre-composition-<sha8>/
      3. Original exception re-raised
    """
    composition_root = tmp_path / "project"
    composition_root.mkdir()
    target1 = composition_root / "apps" / "app"
    target1.mkdir(parents=True)
    (target1 / "user-file.txt").write_text("data-1", encoding="utf-8")
    target2 = composition_root / "packages" / "auth"
    target2.mkdir(parents=True)
    (target2 / "user-file.txt").write_text("data-2", encoding="utf-8")

    backup1 = _backup_existing_target(target1, composition_root)
    backup2 = _backup_existing_target(target2, composition_root)
    assert backup1 is not None and backup2 is not None
    # Simulate scaffold placement after backup-aside (compose() did this).
    target1.mkdir()
    target2.mkdir()

    real_replace = os.replace
    call_count = {"n": 0}

    def flaky_replace(src, dst):
        call_count["n"] += 1
        # Allow Phase A first iteration to succeed; fail second iteration.
        if call_count["n"] == 2 and ".staging" in str(dst):
            raise OSError("synthetic mid-loop staging failure")
        return real_replace(src, dst)

    monkeypatch.setattr(
        "plugin_stack_adapters.composition.os.replace", flaky_replace,
    )

    with pytest.raises(OSError, match="synthetic mid-loop staging failure"):
        _relocate_backups_to_launchpad(
            [(target1, backup1), (target2, backup2)], composition_root,
        )

    # 1. No backup dir survives
    backups_root = composition_root / ".launchpad" / "backups"
    if backups_root.exists():
        # The parent may exist (helper created it) but per-operation subdirs
        # must NOT survive after rollback.
        survivors = list(backups_root.iterdir())
        assert survivors == [], (
            f"Phase A rollback failed to clean staging/final dirs: {survivors!r}"
        )

    # 2. All backups returned to workspace
    assert backup1.exists(), "first backup not restored to workspace"
    assert (backup1 / "user-file.txt").read_text(
        encoding="utf-8"
    ) == "data-1"
    # backup2 was never staged successfully (it's the one that raised), so
    # it should still be at its workspace location untouched.
    assert backup2.exists()
    assert (backup2 / "user-file.txt").read_text(
        encoding="utf-8"
    ) == "data-2"
