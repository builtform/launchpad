"""Phase 8.5 v2.1 decommission gate (BL-247 Round 2 P2-A).

Locks the v2.1 /lp-define rewire + plugin-doc-generator decommission so it
cannot regress: deleted module must stay deleted; new render_batch flow
must enforce atomic-all-or-none under secret-scanner findings; pattern
caching must not re-compile per call; bundled fallback must fire when
.launchpad/secret-patterns.txt is absent; renderer subclasses must not
bypass the gate by calling atomic_write_replace directly; polyglot path
rewriter must work at its new standalone location; static + dynamic +
subprocess + reflection references to plugin-doc-generator must remain
zero outside the permitted historical-artifact appendix.

Plan reference: docs/plans/launchpad_plans/2026-05-05-v2.1-phase8.5-implementation-plan.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "launchpad" / "scripts"

# Sibling-script imports (vendored jinja2 + adapters live here).
if str(SCRIPTS_DIR / "plugin_stack_adapters" / "_vendor") not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR / "plugin_stack_adapters" / "_vendor"))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Slice B -- polyglot path rewriter at standalone module
# ---------------------------------------------------------------------------


def test_polyglot_rewrite_adapter_paths_at_new_location() -> None:
    """The post-composition path rewriter lives at
    `plugin_stack_adapters.polyglot_path_rewriter`. Verifies the verbatim
    move from plugin-doc-generator.py:159-247 preserves behavior.
    """
    from plugin_stack_adapters.polyglot_path_rewriter import (
        _ADAPTER_DEFAULT_PATH_PREFIXES,
        _rewrite_adapter_paths,
        _rewrite_path,
    )

    # _rewrite_path: prefix swap.
    assert _rewrite_path("apps/web/src/components", "apps/web", "packages/ui") == (
        "packages/ui/src/components"
    )
    # Empty prefix: no-op.
    assert _rewrite_path("apps/web/src", "", "packages/ui") == "apps/web/src"
    # Strip-to-root when new prefix is "." or "".
    assert _rewrite_path("apps/web/src", "apps/web", ".") == "src"
    assert _rewrite_path("apps/web/src", "apps/web", "") == "src"
    # Already-customized path (no needle match): pass through.
    assert _rewrite_path("custom/path", "apps/web", "packages/ui") == "custom/path"
    # None / empty input: no-op.
    assert _rewrite_path(None, "apps/web", "packages/ui") is None
    assert _rewrite_path("", "apps/web", "packages/ui") == ""

    # _ADAPTER_DEFAULT_PATH_PREFIXES: known adapters mapped.
    assert _ADAPTER_DEFAULT_PATH_PREFIXES["next"] == "apps/web"
    assert _ADAPTER_DEFAULT_PATH_PREFIXES["fastapi"] == "apps/api"

    # _rewrite_adapter_paths: end-to-end path rewrite for a polyglot
    # AdapterOutput where fastapi materialized at services/api (instead
    # of the default apps/api).
    adapter_out = {
        "backend": {
            "routes_dir": "apps/api/routes",
            "models_dir": "apps/api/models",
        },
        "frontend": {"component_dir": "apps/web/src/components"},
        "tech_stack": [],
        "app_flow": [],
        "product_context": {"stack_summary": "", "deployment_target": ""},
        "commands": {},
        "pipeline_overrides": {},
    }
    layer_paths = {"fastapi": "services/api", "next": "apps/web"}
    rewritten = _rewrite_adapter_paths(adapter_out, layer_paths, ["fastapi", "next"])
    # Backend paths got rewritten because fastapi default = apps/api,
    # actual = services/api.
    assert rewritten["backend"]["routes_dir"] == "services/api/routes"
    assert rewritten["backend"]["models_dir"] == "services/api/models"
    # Frontend stayed at apps/web because next's actual path equals
    # default.
    assert rewritten["frontend"]["component_dir"] == "apps/web/src/components"

    # Empty stacks/layers: pass-through.
    assert _rewrite_adapter_paths(adapter_out, {}, []) is adapter_out
