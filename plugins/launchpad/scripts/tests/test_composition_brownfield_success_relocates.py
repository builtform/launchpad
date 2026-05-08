"""v2.1 Codex PR #50 cycle 6 F8 end-to-end regression test.

Cycle 5's `shutil.rmtree` cleanup permanently deleted user code on
brownfield composition success. Cycle 6 replaces deletion with atomic
relocation. This test verifies the FULL `compose()` orchestrator path
preserves user content at `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>/`,
NOT just the helper-level contract.

Without this test, a regression that re-introduces destructive cleanup
in `compose()` (or that wires `_relocate_backups_to_launchpad` past the
success path) would not be caught — the existing helper-only tests
exercise `_relocate_backups_to_launchpad` directly, bypassing the
production wiring.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.composition import compose
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


def test_compose_brownfield_success_relocates_to_launchpad_backups(
    tmp_path: Path, cache_root_tmp: Path,
) -> None:
    """End-to-end cycle-6 contract: `compose()` over a brownfield workspace
    with pre-existing user content under `apps/app` MUST:

      1. Succeed (new scaffold materialized at `apps/app/`)
      2. Preserve pre-existing user content at
         `.launchpad/backups/<ts>-<PID>-<rand4>/apps/app/`
      3. Write `_manifest.json` with the right schema
      4. NOT leave `.pre-composition-<sha8>/` siblings in the workspace
         (cycle 4's leak — would re-trigger STALE_PRE_COMPOSITION_BACKUP)
      5. NOT delete the user content (cycle 5's destructive bug)
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

    a = NextjsStandaloneAdapter(fetcher=_next_forge_tree)

    result = compose([a], project)

    # 1. Composition succeeded — single-adapter path
    assert result.composition_root == project
    assert "app" in result.workspaces

    # 2. New scaffold materialized at apps/app
    new_app = project / "apps" / "app"
    assert (new_app / "package.json").is_file(), (
        "Expected new scaffold at apps/app/package.json"
    )

    # 3. Backup directory exists under .launchpad/backups/
    backups_root = project / ".launchpad" / "backups"
    assert backups_root.is_dir()
    backup_entries = [e for e in backups_root.iterdir() if e.is_dir()]
    # Filter out any .staging entries (should not exist post-success)
    final_entries = [
        e for e in backup_entries if not e.name.endswith(".staging")
    ]
    assert len(final_entries) == 1, (
        f"Expected exactly 1 backup entry, got {len(final_entries)}: "
        f"{[e.name for e in backup_entries]!r}"
    )
    backup_dir = final_entries[0]

    # 4. User content preserved at the backup
    preserved = backup_dir / "apps" / "app" / "user-file.txt"
    assert preserved.is_file(), (
        f"P0 regression: user content not relocated to {backup_dir}. "
        f"Backup contents: {list(backup_dir.rglob('*'))!r}"
    )
    assert preserved.read_text(encoding="utf-8") == "USER DATA — DO NOT LOSE\n"
    assert (
        backup_dir / "apps" / "app" / "important.md"
    ).read_text(encoding="utf-8") == "important\n"

    # 5. Manifest present + valid schema
    manifest_path = backup_dir / "_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert manifest["caller"] == "/lp-scaffold-stack"
    assert any(
        t["original_path"] == "apps/app" for t in manifest["targets"]
    )

    # 6. NO `.pre-composition-<sha8>/` leak in the workspace
    apps_dir = project / "apps"
    pre_comp_leaks = [
        p for p in apps_dir.iterdir()
        if p.is_dir() and ".pre-composition-" in p.name
    ]
    assert pre_comp_leaks == [], (
        f"cycle 4 leak regression: {pre_comp_leaks!r} survived "
        f"successful composition"
    )
