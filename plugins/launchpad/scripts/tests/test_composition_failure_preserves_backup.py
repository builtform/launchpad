"""v2.1.1 Phase 0 Item 0.2 — failure-path rollback contract.

End-to-end regression for `compose()` when workspace placement raises
post-`_backup_existing_target`. Cycle 6 plan T1-9 deferral: helper-level
tests exercise `_rollback` directly, but the production wiring through
`compose()` is uncovered by an end-to-end failure-path test.

Injection point per DA-0.2.1: `composition.os.replace` at
composition.py:1134 — the FIRST `os.replace` invocation after
`_backup_existing_target`, exercising the `apps/app` rollback path.
Established repo idiom: `monkeypatch.setattr` on composition internals
(see test_composition_success_relocate_atomicity.py:54-62).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import TMP_PARENT_DIRNAME, compose
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter

pytestmark = pytest.mark.slow


def _next_forge_tree(target: Path) -> None:
    """Minimal fixture mimicking next-forge fetcher output for compose()."""
    files = {
        "package.json": b'{"name": "next-forge", "engines": {"node": ">=20"}}\n',
        "turbo.json": b'{"tasks": {"build": {}}}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "apps/*"\n  - "packages/*"\n',
        "apps/app/package.json": b'{"name": "app"}\n',
        "apps/app/middleware.ts": b'export default () => null;\n',
        "packages/auth/package.json": b'{"name": "@repo/auth"}\n',
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


def test_compose_failure_preserves_backup_and_rolls_back_user_content(
    tmp_path: Path,
    cache_root_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end Phase 0 contract: when `compose()` raises mid-placement,
    `_rollback()` MUST restore user content from the
    `.pre-composition-<sha8>/` backup and leave the workspace clean.

    Assertions per DA-0.2.3:

      1. `compose()` raises (CompositionAbortError(RuntimeError) catches
         RuntimeError; match= enriches "DID NOT RAISE" failures)
      2. No OSError chained from _rollback (rollback-internal failures
         not masked into the outer exception's cause chain)
      3. Original user content restored at `apps/app/` (byte-equivalent)
      4. No scaffold leak — `apps/app/` contents are EXACTLY the user's
         original two files
      5. No `.launchpad/backups/<ts>-<PID>-<rand4>/` entry — failure path
         does not relocate (relocation is success-path-only)
      6. No `<basename>.pre-composition-<sha8>/` leak anywhere in workspace
      7. Rendered tempdirs cleaned up under `<TMP_PARENT_DIRNAME>/`
    """
    project = tmp_path / "project"
    apps_app = project / "apps" / "app"
    apps_app.mkdir(parents=True)
    (apps_app / "user-file.txt").write_text(
        "USER DATA — DO NOT LOSE\n", encoding="utf-8",
    )
    (apps_app / "important.md").write_text(
        "important\n", encoding="utf-8",
    )

    def _flaky_replace(*args, **kwargs):
        raise RuntimeError("synthetic fault: placement refused")

    monkeypatch.setattr(
        "plugin_stack_adapters.composition.os.replace",
        _flaky_replace,
    )

    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)

    # 1. Exception raised. CompositionAbortError(RuntimeError) so RuntimeError
    #    catches both; match= pattern enriches "DID NOT RAISE" failure with a
    #    clearer regression message.
    with pytest.raises(RuntimeError, match=r"synthetic fault|aborted") as exc_info:
        compose([a], project)

    # 2. No OSError chained from _rollback (rollback-internal failures aren't
    #    masked into the outer exception's __context__ chain).
    ctx = exc_info.value.__context__
    while ctx is not None:
        assert not isinstance(ctx, OSError), f"_rollback raised internally: {ctx!r}"
        ctx = ctx.__context__

    # 3. Original user content restored at original location.
    assert apps_app.is_dir()
    assert (apps_app / "user-file.txt").read_text(
        encoding="utf-8",
    ) == "USER DATA — DO NOT LOSE\n"
    assert (apps_app / "important.md").read_text(
        encoding="utf-8",
    ) == "important\n"

    # 4. NO scaffold leak (rollback didn't half-place new content).
    assert sorted(p.name for p in apps_app.iterdir()) == [
        "important.md",
        "user-file.txt",
    ]

    # 5. NO `.launchpad/backups/<...>/` entry (failure path doesn't relocate).
    backups_root = project / ".launchpad" / "backups"
    if backups_root.exists():
        entries = [
            e for e in backups_root.iterdir()
            if e.is_dir() and not e.name.endswith(".staging")
        ]
        assert entries == [], (
            f"failure path should not relocate; got: {entries!r}"
        )

    # 6. NO `<basename>.pre-composition-<sha8>/` leak anywhere in workspace.
    #    Backups are named per `_pre_composition_backup_path` (composition.py:534)
    #    as `<basename>.pre-composition-<sha8>` — the leading wildcard is REQUIRED.
    #    A bare `.pre-composition-*` glob would silently pass regardless of leak.
    assert not list(project.rglob("*.pre-composition-*"))

    # 7. Rendered tempdirs cleaned up. `TMP_PARENT_DIRNAME` is the canonical
    #    exported constant (composition.py:73, in `__all__`); plan §1 DA-0.2.3
    #    hardcoded `.launchpad/tmp` was stale (cycle 6 P1-ζ rename to `.lp-tmp`
    #    to avoid Next.js collision). Use the constant so this survives any
    #    future rename without re-breaking.
    tmp_root = project / TMP_PARENT_DIRNAME
    if tmp_root.exists():
        assert list(tmp_root.iterdir()) == []
