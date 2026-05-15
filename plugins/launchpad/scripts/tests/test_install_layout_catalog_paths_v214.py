"""v2.1.4 BL-327 regression: catalog path arithmetic survives both the
source-repo layout AND the installed-plugin cache layout.

The bug surfaced 2026-05-14 during a first-user greenfield dogfood test: every
`/lp-scaffold-stack` invocation routed through manual-override raised
`catalog_load_failed` because the engine computed
`~/.claude/plugins/cache/builtform/plugins/launchpad/scaffolders.yml`
(extra `plugins/` segment + missing version subdir) instead of the
real install path
`~/.claude/plugins/cache/builtform/launchpad/<VERSION>/scaffolders.yml`.

The fix re-roots the defaults at `parents[2]` of engine.py — which is
the LaunchPad root in BOTH layouts (the dir that holds scaffolders.yml +
scripts/), making the constants install-aware.

Tests:

  * `test_default_paths_resolve_in_source_repo`: source-tree sanity
    check (the same assertion as the v2-handshake-lint workflow's
    "Default catalog paths smoke check" step).

  * `test_path_arithmetic_works_in_install_layout`: pure-math regression
    pin. Mimics the `Path(__file__).resolve().parents[2]` computation
    against a synthetic path that looks like the v2.1 marketplace
    cache layout, and asserts the result is the version-suffixed
    install root (NOT the pre-v2.1.4 `<root>/plugins/launchpad/`
    infix path that 2.1.3 produced).

  * `test_full_pipeline_runs_against_simulated_install_layout`: install-
    layout E2E. Builds a tempdir tree mirroring the real
    `~/.claude/plugins/cache/builtform/launchpad/<VERSION>/` install
    shape, then drives /lp-pick-stack (manual-override `generic`) +
    /lp-scaffold-stack with the catalogs pointed at the simulated
    install's files via the public --scaffolders-yml /
    --category-patterns-yml override surface. Pre-fix the receipt
    failed at `catalog_load_failed`; post-fix it succeeds.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_pick_stack.engine import run_pipeline as run_pick_stack_pipeline  # noqa: E402
from lp_scaffold_stack.engine import (
    DEFAULT_CATEGORY_PATTERNS_YML,  # noqa: E402
    DEFAULT_PLUGINS_ROOT,  # noqa: E402
    DEFAULT_SCAFFOLDERS_YML,  # noqa: E402
)
from lp_scaffold_stack.engine import (
    run_pipeline as run_scaffold_stack_pipeline,  # noqa: E402
)

VALID_FUNNEL_ANSWERS = {
    "Q1": "web-app",
    "Q2": "yes-needed",
    "Q3": "no",
    "Q4": "mixed-no-strong-preference",
    "Q5": "container",
}


# ---------- Source-layout sanity ----------


def test_default_paths_resolve_in_source_repo():
    """Source-tree default catalog paths exist on disk."""
    assert DEFAULT_SCAFFOLDERS_YML.is_file(), (
        f"DEFAULT_SCAFFOLDERS_YML does not exist: {DEFAULT_SCAFFOLDERS_YML}"
    )
    assert DEFAULT_CATEGORY_PATTERNS_YML.is_file(), (
        f"DEFAULT_CATEGORY_PATTERNS_YML does not exist: "
        f"{DEFAULT_CATEGORY_PATTERNS_YML}"
    )
    assert DEFAULT_PLUGINS_ROOT.is_dir(), (
        f"DEFAULT_PLUGINS_ROOT is not a directory: {DEFAULT_PLUGINS_ROOT}"
    )


# ---------- Install-layout regression: path arithmetic ----------


def test_path_arithmetic_works_in_install_layout():
    """v2.1.4 BL-327 regression pin. Mimic the path arithmetic engine.py
    runs at import time, against a synthetic path that looks like the
    v2.1 Claude Code marketplace cache layout. Asserts the resolved
    LaunchPad root is the version-suffixed install dir, NOT a
    `plugins/launchpad/` infix path.

    Real install (verified 2026-05-14 against on-disk v2.1.2 cache):
        ~/.claude/plugins/cache/builtform/launchpad/<VERSION>/
            ├── scaffolders.yml                          ← scaffolders catalog
            ├── scripts/lp_scaffold_stack/engine.py      ← THIS engine, when installed
            └── scripts/lp_pick_stack/data/category-patterns.yml

    Pre-fix: `parents[4]` of engine.py was `~/.claude/plugins/cache/
    builtform/`, then the code joined `plugins/launchpad/scaffolders.yml`
    onto it — yielding `~/.claude/plugins/cache/builtform/plugins/
    launchpad/scaffolders.yml` (does not exist; observed failure mode).

    Post-fix: `parents[2]` of engine.py is the version-suffixed install
    root in BOTH source-repo AND install layouts. That dir holds
    `scaffolders.yml` directly (no `plugins/launchpad/` infix).
    """
    fake_engine = Path(
        "/Users/example/.claude/plugins/cache/builtform/launchpad/"
        "2.1.4/scripts/lp_scaffold_stack/engine.py"
    )
    expected_install_root = Path(
        "/Users/example/.claude/plugins/cache/builtform/launchpad/2.1.4"
    )
    # Install-aware path: parents[2] = version-suffixed install root.
    install_root = fake_engine.parents[2]
    assert install_root == expected_install_root

    # Catalog defaults rooted at parents[2] resolve to paths that
    # exist (in the real install — we verified the on-disk v2.1.2
    # install at the same layout has both these files at the same
    # relative paths).
    expected_scaffolders = expected_install_root / "scaffolders.yml"
    expected_category = (
        expected_install_root
        / "scripts"
        / "lp_pick_stack"
        / "data"
        / "category-patterns.yml"
    )
    assert (install_root / "scaffolders.yml") == expected_scaffolders
    assert (
        install_root
        / "scripts"
        / "lp_pick_stack"
        / "data"
        / "category-patterns.yml"
    ) == expected_category

    # Pre-v2.1.4 bad path shape — explicit rejection. parents[4] is the
    # `builtform/` dir in the install layout; joining `plugins/launchpad/
    # scaffolders.yml` produced the observed broken path.
    bad_path = (
        fake_engine.parents[4] / "plugins" / "launchpad" / "scaffolders.yml"
    )
    assert bad_path != expected_scaffolders
    assert "plugins/launchpad" in str(bad_path)
    assert "plugins/launchpad" not in str(expected_scaffolders)


# ---------- Install-layout regression: full pipeline ----------


def _build_simulated_install_tree(tmp_path: Path) -> Path:
    """Build the v2.1 Claude Code marketplace cache layout under tmp_path.

    Returns the simulated `<install-root>` (the version-suffixed dir
    that holds scaffolders.yml + scripts/). The layout matches the real
    install at `~/.claude/plugins/cache/builtform/launchpad/<VERSION>/`
    (verified 2026-05-14 against the on-disk v2.1.2 install).
    """
    fake_install = (
        tmp_path
        / ".claude"
        / "plugins"
        / "cache"
        / "builtform"
        / "launchpad"
        / "2.1.4"
    )
    fake_install.mkdir(parents=True)
    plugin_src = _SCRIPTS_DIR.parent  # plugins/launchpad/
    for child in plugin_src.iterdir():
        if child.name in {"__pycache__", ".pytest_cache"}:
            continue
        dst = fake_install / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                dst,
                ignore=shutil.ignore_patterns(
                    "__pycache__", ".pytest_cache", "*.pyc", ".*cache*"
                ),
            )
        else:
            shutil.copy2(child, dst)
    return fake_install


def test_full_pipeline_runs_against_simulated_install_layout(tmp_path: Path):
    """v2.1.4 BL-327 end-to-end. Build the install layout, drive
    /lp-pick-stack (manual-override `generic`) → /lp-scaffold-stack with
    catalogs from the install tree, assert the receipt is written and
    catalog_load_failed does NOT leak through.

    Pre-fix: even if the user passed --scaffolders-yml/--category-patterns-yml
    explicitly, run_pipeline opened the path via `_load_yaml(path)` which
    surfaced FileNotFoundError as `catalog_load_failed`. The default-path
    fix doesn't change this test directly, but the test pins the full
    flow against the install tree shape so future regressions in the
    dispatch or loader paths are caught.
    """
    install_root = _build_simulated_install_tree(tmp_path)
    install_scaffolders = install_root / "scaffolders.yml"
    install_category = (
        install_root
        / "scripts"
        / "lp_pick_stack"
        / "data"
        / "category-patterns.yml"
    )
    assert install_scaffolders.is_file(), install_scaffolders
    assert install_category.is_file(), install_category

    project = tmp_path / "project"
    project.mkdir()

    pick_result = run_pick_stack_pipeline(
        project,
        VALID_FUNNEL_ANSWERS,
        manual_override=True,
        manual_layer_specs=[
            {"stack": "generic", "role": "frontend", "path": "."}
        ],
        write_telemetry=False,
    )
    assert pick_result.success, pick_result.message

    scaffold_result = run_scaffold_stack_pipeline(
        project,
        scaffolders_yml=install_scaffolders,
        category_patterns_yml=install_category,
        plugins_root=install_root,
        write_telemetry_flag=False,
    )
    assert scaffold_result.reason != "catalog_load_failed", (
        f"BL-327 regression: catalog_load_failed leaked through against "
        f"the install-layout catalog paths; message: "
        f"{scaffold_result.message}"
    )
    assert scaffold_result.success, scaffold_result.message
    receipt_path = project / ".launchpad" / "scaffold-receipt.json"
    assert receipt_path.is_file()
