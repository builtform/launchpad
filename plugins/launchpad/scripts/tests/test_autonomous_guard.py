#!/usr/bin/env python3
"""Regression test: the autonomous-build guard catches the same-commit
section-add + ack pattern even when SECTION_REGISTRY.md already exists.

Earlier the guard used `git log --diff-filter=A` which restricts results to
commits that ADDED the file from scratch. In a normal repo where the
registry already exists, a hostile PR could land both a new section line
and `.launchpad/autonomous-ack.md` in a single commit, and the guard's
pickaxe query would silently return no commit (because the file modify did
not match the file-add filter), so `section_added_with_ack` would return
False and the auto-approve fast path would run.

This test creates an ephemeral git repo, simulates the realistic timeline
(registry created in commit 1, hostile section + ack added in commit 2),
and asserts the guard returns True.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import autonomous_guard by file path (the module lives under
# plugin_stack_adapters/ but importing as `from plugin_stack_adapters import
# autonomous_guard` requires the parent on sys.path).
_GUARD_PATH = SCRIPT_DIR / "plugin_stack_adapters" / "autonomous_guard.py"
_spec = importlib.util.spec_from_file_location("autonomous_guard", _GUARD_PATH)
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)  # type: ignore[union-attr]
section_added_with_ack = _guard.section_added_with_ack


def _git(cwd: Path, *args: str) -> None:
    env = os.environ.copy()
    # Force a stable identity so commits don't fail on systems without
    # user.email / user.name configured.
    env.setdefault("GIT_AUTHOR_NAME", "Test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(["git", *args], cwd=cwd, check=True, env=env, capture_output=True)


def _build_repo(tmp: Path) -> None:
    _git(tmp, "init", "-q", "-b", "main")
    _git(tmp, "config", "user.email", "test@example.com")
    _git(tmp, "config", "user.name", "Test")

    # Commit 1: registry exists with one benign section.
    registry = tmp / "docs" / "tasks" / "SECTION_REGISTRY.md"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "# Section Registry\n\n"
        "## Registry\n\n"
        "### benign-section\n\n"
        "- **Status:** shaped\n",
        encoding="utf-8",
    )
    _git(tmp, "add", "docs/tasks/SECTION_REGISTRY.md")
    _git(tmp, "commit", "-q", "-m", "init: registry with benign-section")

    # Commit 2 (hostile shape): add the new section AND
    # autonomous-ack.md in the same commit. Registry is MODIFIED, not added,
    # so a --diff-filter=A pickaxe never finds this commit.
    registry.write_text(
        "# Section Registry\n\n"
        "## Registry\n\n"
        "### benign-section\n\n"
        "- **Status:** shaped\n\n"
        "### hostile-section\n\n"
        "- **Status:** shaped\n",
        encoding="utf-8",
    )
    ack = tmp / ".launchpad" / "autonomous-ack.md"
    ack.parent.mkdir(parents=True, exist_ok=True)
    ack.write_text("ack\n", encoding="utf-8")
    _git(tmp, "add", "docs/tasks/SECTION_REGISTRY.md", ".launchpad/autonomous-ack.md")
    _git(tmp, "commit", "-q", "-m", "feat: hostile-section + autonomous-ack")


def test_modify_commit_caught() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lp-guard-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        _build_repo(tmp)

        # The hostile section was added by a MODIFY commit on an
        # already-existing registry — exactly the scenario the previous
        # --diff-filter=A version missed.
        if not section_added_with_ack(tmp, "hostile-section"):
            errors.append(
                "guard returned False for hostile-section — same-commit "
                "section-add + ack pattern was not caught (regression of "
                "the --diff-filter=A bug)"
            )

        # Sanity check the false branch: benign-section was committed
        # WITHOUT the ack, so the guard should return False.
        if section_added_with_ack(tmp, "benign-section"):
            errors.append(
                "guard returned True for benign-section even though that "
                "commit did not touch autonomous-ack.md (false positive)"
            )

    return errors


def _build_cross_commit_repo(tmp: Path) -> None:
    """Simulate a hostile PR splitting ack and section across two commits.

    Timeline:
      main: commit 1 — registry created with benign-section, no ack.
      feature branch off main:
        commit 2 — adds .launchpad/autonomous-ack.md (no section change).
        commit 3 — adds hostile-section to the registry.

    The previous same-commit-only guard did not catch this: commit 3 (the
    section introduction) does not touch the ack file, so the check
    returns False. The cross-commit fix detects that the ack was first
    created in commit 2, which is on the feature branch (not on main),
    and refuses.
    """
    _git(tmp, "init", "-q", "-b", "main")
    _git(tmp, "config", "user.email", "test@example.com")
    _git(tmp, "config", "user.name", "Test")

    registry = tmp / "docs" / "tasks" / "SECTION_REGISTRY.md"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "# Section Registry\n\n## Registry\n\n"
        "### benign-section\n\n- **Status:** shaped\n",
        encoding="utf-8",
    )
    _git(tmp, "add", "docs/tasks/SECTION_REGISTRY.md")
    _git(tmp, "commit", "-q", "-m", "init: registry on main")

    # Branch off main.
    _git(tmp, "checkout", "-q", "-b", "feature/hostile")

    # Commit 2 on the branch: just the ack.
    ack = tmp / ".launchpad" / "autonomous-ack.md"
    ack.parent.mkdir(parents=True, exist_ok=True)
    ack.write_text("ack\n", encoding="utf-8")
    _git(tmp, "add", ".launchpad/autonomous-ack.md")
    _git(tmp, "commit", "-q", "-m", "chore: opt into autonomous mode")

    # Commit 3 on the branch: just the new section.
    registry.write_text(
        "# Section Registry\n\n## Registry\n\n"
        "### benign-section\n\n- **Status:** shaped\n\n"
        "### hostile-section\n\n- **Status:** shaped\n",
        encoding="utf-8",
    )
    _git(tmp, "add", "docs/tasks/SECTION_REGISTRY.md")
    _git(tmp, "commit", "-q", "-m", "feat: add hostile-section")


def test_cross_commit_caught() -> list[str]:
    """Round 9 fix: cross-commit attack must also be refused.

    Ack is added in one commit on the branch and section in a later commit
    on the same branch. The same-commit check alone misses this; the
    merge-base check catches it.
    """
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lp-guard-cross-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        _build_cross_commit_repo(tmp)

        if not section_added_with_ack(tmp, "hostile-section"):
            errors.append(
                "guard returned False for hostile-section in a cross-commit "
                "attack — ack added in one commit, section in a later commit "
                "on the same branch was not caught"
            )

        # benign-section predates the ack on main; ack itself was added on
        # the branch, but benign-section's introduction commit is in main's
        # history — the cross-commit check still triggers because the ack
        # was added in this branch, regardless of which section we ask
        # about. This is intentional: any branch that introduces ack
        # invalidates fast-path approval for ALL sections planned on that
        # branch, since the human has not had a chance to review the ack
        # in the merged base.
        if not section_added_with_ack(tmp, "benign-section"):
            errors.append(
                "guard returned False for benign-section on a branch that "
                "introduced the ack — once ack is added in a branch, every "
                "section plan on that branch must refuse fast-path approval"
            )

    return errors


def main() -> int:
    tests = [
        ("modify_commit_caught", test_modify_commit_caught),
        ("cross_commit_caught", test_cross_commit_caught),
    ]
    all_errors: list[str] = []
    for name, t in tests:
        errs = t()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: autonomous_guard regression")
        for e in all_errors:
            print(e)
        return 1
    print(f"PASS: autonomous_guard regression ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
